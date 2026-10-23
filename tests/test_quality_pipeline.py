"""Unit tests for the end-to-end data quality pipeline and report generation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from unittest.mock import MagicMock, patch
import pytest

from src.quality.models import (
    DataQualityReport,
    LinkCheckResult,
    QualityStatus,
    VerificationStatus,
)
from src.quality.pipeline import run_quality_pipeline


@pytest.fixture
def ref_time() -> datetime:
    """Deterministic reference time: 2026-10-21 12:00:00 UTC."""
    return datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_records() -> list[dict]:
    """Sample records containing 1 clean, 1 with warning, 1 with error."""
    return [
        {
            "opportunity_id": "OPP-001",
            "title": "Clean Opportunity",
            "organization": "Sponsor Org",
            "category": "Scholarships",
            "description": "Comprehensive scholarship program for university undergraduates.",
            "eligibility": "Minimum 3.5 CGPA required for undergraduate students.",
            "education_level": "Undergraduate",
            "location": "Gombe",
            "deadline": "2026-12-01",
            "source_url": "https://example.com/clean",
            "verified_at": "2026-10-15T00:00:00Z",
            "status": "VERIFIED",
        },
        {
            "opportunity_id": "OPP-002",
            "title": "Warning Opportunity",
            "organization": "Another Org",
            "category": "Internships",
            "description": "Brief desc.",  # Warning: < 20 chars
            "eligibility": "Check official source.",  # Warning: vague
            "education_level": "All Levels",
            "location": "Lagos",
            "deadline": None,  # Warning: unknown deadline
            "source_url": "https://example.com/warn",
            "verified_at": "2026-08-01T00:00:00Z",  # Warning: stale (>30d)
            "status": "NEEDS_REVIEW",
        },
        {
            "opportunity_id": "OPP-003",
            "title": "",  # Error: missing title
            "organization": "Bad Org",
            "category": "InvalidCat",  # Error: invalid category
            "description": "",  # Error: empty description
            "eligibility": "None",
            "education_level": "Other",
            "location": "Remote",
            "deadline": "2026-11-01",
            "source_url": "invalid-url",  # Error: invalid URL
            "verified_at": "2026-10-10T00:00:00Z",
            "status": "UNVERIFIED",
        },
    ]


def test_pipeline_on_sample_records(sample_records, ref_time):
    """Verify metrics and issue aggregation on mixed sample records."""
    report: DataQualityReport = run_quality_pipeline(
        records=sample_records,
        report_scope="test_batch",
        dry_run=True,
        check_urls=False,
        reference_now=ref_time,
    )

    s = report.summary
    assert s.total_records == 3
    assert s.passed_records == 1
    assert s.warning_records == 1
    assert s.failed_records == 1

    assert s.open_opportunities == 2  # OPP-001 and OPP-003
    assert s.unknown_deadline_opportunities == 1  # OPP-002
    assert s.stale_verification_records >= 1  # OPP-002 (>30d)


def test_pipeline_on_empty_dataset(ref_time):
    """Verify that running pipeline on an empty list handles cleanly without error."""
    report = run_quality_pipeline(
        records=[],
        report_scope="empty_test",
        dry_run=True,
        reference_now=ref_time,
    )
    assert report.summary.total_records == 0
    assert len(report.issues) == 0
    assert len(report.records) == 0


def test_report_json_and_csv_serialization(sample_records, ref_time):
    """Verify that report serializes to valid JSON and CSV rows."""
    report = run_quality_pipeline(
        records=sample_records,
        reference_now=ref_time,
    )

    # JSON serialization
    json_text = report.to_json()
    assert isinstance(json_text, str)
    parsed_json = json.loads(json_text)
    assert parsed_json["summary"]["total_records"] == 3
    assert len(parsed_json["issues"]) > 0

    # CSV serialization
    csv_rows = report.to_csv_rows()
    assert len(csv_rows) == 3
    assert csv_rows[0]["opportunity_id"] == "OPP-001"
    assert csv_rows[0]["quality_status"] == QualityStatus.PASS.value
    assert csv_rows[2]["quality_status"] == QualityStatus.FAIL.value


def test_pipeline_with_mocked_link_checks(sample_records, ref_time):
    """Verify optional link checking execution in pipeline."""
    # Mock checker to return reachable for OPP-001 and broken for OPP-002
    def mock_check(url: str):
        if "clean" in url:
            return LinkCheckResult(
                url=url,
                is_reachable=True,
                http_status=200,
                verification_status=VerificationStatus.NEEDS_REVIEW,
            )
        else:
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                http_status=404,
                verification_status=VerificationStatus.BROKEN_LINK,
                error_code="HTTP_404_NOT_FOUND",
                error_message="Not found",
            )

    with patch("src.quality.pipeline.SafeSourceChecker") as mock_checker_cls:
        mock_instance = MagicMock()
        mock_instance.check_url.side_effect = mock_check
        mock_checker_cls.return_value = mock_instance

        report = run_quality_pipeline(
            records=sample_records,
            check_urls=True,
            network_enabled=True,
            reference_now=ref_time,
        )

        assert report.summary.source_urls_checked >= 2
        assert report.summary.reachable_sources >= 1
        assert report.summary.broken_link_candidates >= 1
