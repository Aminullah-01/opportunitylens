"""Unit tests for Phase 5 data quality CLI."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.quality.cli import main


def test_cli_help(capsys):
    """Verify that --help exits with 0 and prints usage."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Audit OpportunityLens data quality" in captured.out


def test_cli_file_source_dry_run(capsys):
    """Verify executing CLI against sample raw data file in dry-run mode."""
    exit_code = main([
        "--source", "file",
        "--input-file", "data/raw_opportunities.json",
        "--dry-run",
    ])
    assert exit_code in (0, 1)  # Depends on whether warnings/errors exist
    captured = capsys.readouterr()
    assert "OpportunityLens Data Quality & Verification Audit" in captured.out
    assert "Total Records Audited:" in captured.out


def test_cli_demo_source_with_json_and_csv_export(tmp_path, capsys):
    """Verify JSON and CSV file export flags."""
    json_out = tmp_path / "test_report.json"
    csv_out = tmp_path / "test_report.csv"

    # Export JSON
    code_json = main([
        "--source", "demo",
        "--output", str(json_out),
        "--format", "json",
    ])
    assert code_json in (0, 1)
    assert json_out.exists()
    parsed = json.loads(json_out.read_text())
    assert "summary" in parsed
    assert "records" in parsed

    # Export CSV
    code_csv = main([
        "--source", "demo",
        "--output", str(csv_out),
        "--format", "csv",
    ])
    assert code_csv in (0, 1)
    assert csv_out.exists()
    assert "opportunity_id" in csv_out.read_text()


def test_cli_missing_input_file(capsys):
    """Verify non-existent input file returns error code 1."""
    code = main([
        "--source", "file",
        "--input-file", "data/non_existent_file.json",
    ])
    assert code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err
