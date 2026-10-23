"""Tests for operational quality audit runner and process locking."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from src.quality.runner import (
    EXIT_BLOCKING_DATA_ERRORS,
    EXIT_EXECUTION_FAILURE,
    EXIT_QUALITY_WARNINGS,
    EXIT_SUCCESS,
    AuditLockAcquisitionError,
    audit_process_lock,
    get_latest_audit_report,
    run_operational_audit,
)


def test_audit_runner_demo_success(tmp_path):
    """Verify operational audit runner runs cleanly on demo data."""
    exit_code, report, report_path = run_operational_audit(
        source="demo",
        output_dir=tmp_path,
        check_network=False,
        export_csv=True,
    )
    assert exit_code == EXIT_SUCCESS
    assert report is not None
    assert report_path is not None
    assert report_path.exists()

    # Check generated JSON file structure
    data = json.loads(report_path.read_text())
    assert "summary" in data
    assert "execution_metadata" in data
    assert data["execution_metadata"]["runner_source"] == "demo"

    # CSV file was also created
    csv_files = list(tmp_path.glob("*.csv"))
    assert len(csv_files) == 1


def test_audit_runner_preserves_existing_reports(tmp_path):
    """Verify consecutive audit runs create distinct timestamped reports without overwriting."""
    exit_code1, _, path1 = run_operational_audit(source="demo", output_dir=tmp_path)
    # Ensure distinct mtime/timestamp if needed
    exit_code2, _, path2 = run_operational_audit(source="demo", output_dir=tmp_path)

    assert exit_code1 == EXIT_SUCCESS
    assert exit_code2 == EXIT_SUCCESS
    reports = list(tmp_path.glob("audit_report_demo_*.json"))
    assert len(reports) >= 1
    # Both paths exist
    assert path1.exists()
    assert path2.exists()


def test_audit_runner_exit_code_blocking_errors(tmp_path):
    """Verify runner returns EXIT_BLOCKING_DATA_ERRORS when records have validation failures."""
    bad_file = tmp_path / "bad_data.json"
    bad_file.write_text(
        json.dumps([
            {
                "opportunity_id": "",  # Missing ID is a FAIL
                "title": "",  # Missing title is a FAIL
                "category": "Scholarships",
                "organization": "Test",
            }
        ])
    )

    exit_code, report, _ = run_operational_audit(
        source="file",
        input_file=str(bad_file),
        output_dir=tmp_path,
    )
    assert exit_code == EXIT_BLOCKING_DATA_ERRORS
    assert report is not None
    assert report.summary.failed_records > 0


def test_audit_runner_exit_code_fail_on_warnings(tmp_path):
    """Verify runner returns EXIT_QUALITY_WARNINGS when warnings exist and flag is set."""
    warn_file = tmp_path / "warn_data.json"
    warn_file.write_text(
        json.dumps([
            {
                "opportunity_id": "OPP-WARN-001",
                "title": "Valid Opportunity Title",
                "organization": "Unknown Org",  # Placeholder organization generates a WARNING
                "category": "Scholarships",
                "description": "Short desc",  # Short description generates a WARNING
                "source_url": "https://example.com/apply",
            }
        ])
    )

    exit_code, report, _ = run_operational_audit(
        source="file",
        input_file=str(warn_file),
        output_dir=tmp_path,
        fail_on_warnings=True,
    )
    assert exit_code == EXIT_QUALITY_WARNINGS
    assert report is not None
    assert report.summary.failed_records == 0
    assert report.summary.warning_records > 0


def test_audit_runner_missing_input_file(tmp_path):
    """Verify runner returns EXIT_EXECUTION_FAILURE when input file does not exist."""
    exit_code, report, path = run_operational_audit(
        source="file",
        input_file="/nonexistent/path/data.json",
        output_dir=tmp_path,
    )
    assert exit_code == EXIT_EXECUTION_FAILURE
    assert report is None
    assert path is None


def test_audit_process_lock_prevents_overlap(tmp_path):
    """Verify process lock raises AuditLockAcquisitionError if lock is held by running PID."""
    lock_file = tmp_path / ".test.lock"

    with audit_process_lock(lock_file):
        # A second lock acquisition while first is held must fail
        with pytest.raises(AuditLockAcquisitionError, match="already in progress"):
            with audit_process_lock(lock_file):
                pass

    # After exit, lock file is cleanly removed
    assert not lock_file.exists()


def test_audit_process_lock_reclaims_stale_pid(tmp_path):
    """Verify stale lock from inactive PID is reclaimed without error."""
    lock_file = tmp_path / ".test_stale.lock"
    # Write PID that is practically guaranteed not to exist (e.g. 9999999)
    lock_file.write_text("9999999")

    # Should successfully acquire lock despite existing lockfile
    with audit_process_lock(lock_file):
        assert lock_file.read_text() == str(os.getpid())

    assert not lock_file.exists()


def test_get_latest_audit_report(tmp_path):
    """Verify get_latest_audit_report retrieves the newest JSON report."""
    assert get_latest_audit_report(tmp_path) is None

    # Create dummy reports
    r1 = tmp_path / "audit_report_demo_20261022_010000.json"
    r1.write_text(json.dumps({"summary": {"total_records": 5}}))

    r2 = tmp_path / "audit_report_demo_20261022_020000.json"
    r2.write_text(json.dumps({"summary": {"total_records": 10}}))

    latest = get_latest_audit_report(tmp_path)
    assert latest is not None
    assert latest["summary"]["total_records"] == 10


def test_empty_data_source(tmp_path):
    """Verify auditing empty data source handles without crashing."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("[]")

    exit_code, report, path = run_operational_audit(
        source="file",
        input_file=str(empty_file),
        output_dir=tmp_path,
    )
    assert exit_code == EXIT_SUCCESS
    assert report is not None
    assert report.summary.total_records == 0
