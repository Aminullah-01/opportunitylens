"""Unit tests for data quality and integrity auditor."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest

from src.quality.models import QualityStatus, Severity
from src.quality.validator import audit_batch_records, audit_single_record


@pytest.fixture
def ref_time() -> datetime:
    """Deterministic reference time: 2026-10-21 12:00:00 UTC."""
    return datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def valid_record() -> dict:
    """Standard valid opportunity record."""
    return {
        "opportunity_id": "OPP-NITDA-001",
        "title": "NITDA 3MTT Tech Training",
        "organization": "NITDA Nigeria",
        "category": "Tech Training",
        "description": "Subsidized 3 million technical talent training program across Nigeria.",
        "eligibility": "Nigerian youth aged 18-35 interested in tech skills.",
        "education_level": "All Levels",
        "location": "Nationwide",
        "deadline": "2026-12-15",
        "source_url": "https://3mtt.nitda.gov.ng",
        "verified_at": "2026-10-10T10:00:00Z",
        "status": "VERIFIED",
    }


def test_valid_record_passes(valid_record, ref_time):
    """Verify clean record produces QualityStatus.PASS with zero issues."""
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.PASS
    assert len(result.issues) == 0
    assert result.opportunity_id == "OPP-NITDA-001"


def test_missing_or_whitespace_title(valid_record, ref_time):
    """Verify missing title triggers MISSING_TITLE error and FAIL quality status."""
    valid_record["title"] = "   "
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "MISSING_TITLE" for i in result.issues)


def test_missing_or_placeholder_organization(valid_record, ref_time):
    """Verify placeholder organization triggers MISSING_ORGANIZATION error."""
    valid_record["organization"] = "Not specified"
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "MISSING_ORGANIZATION" for i in result.issues)


def test_invalid_category(valid_record, ref_time):
    """Verify unrecognized category triggers INVALID_CATEGORY error."""
    valid_record["category"] = "Cooking Competitions"
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "INVALID_CATEGORY" for i in result.issues)


def test_missing_and_invalid_source_url(valid_record, ref_time):
    """Verify missing and invalid URLs are rejected."""
    # Blank URL
    valid_record["source_url"] = ""
    res_blank = audit_single_record(valid_record, reference_now=ref_time)
    assert res_blank.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "MISSING_URL" for i in res_blank.issues)

    # Invalid syntax (ftp)
    valid_record["source_url"] = "ftp://files.example.com"
    res_bad = audit_single_record(valid_record, reference_now=ref_time)
    assert res_bad.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "INVALID_URL_SYNTAX" for i in res_bad.issues)


def test_empty_and_short_description(valid_record, ref_time):
    """Verify empty description fails, and brief description triggers warning."""
    # Empty description
    valid_record["description"] = ""
    res_empty = audit_single_record(valid_record, reference_now=ref_time)
    assert res_empty.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "EMPTY_DESCRIPTION" for i in res_empty.issues)

    # Brief description (<20 chars)
    valid_record["description"] = "Short info."
    res_short = audit_single_record(valid_record, reference_now=ref_time)
    assert res_short.quality_status == QualityStatus.WARNING
    assert any(i.issue_code == "INCOMPLETE_DESCRIPTION" for i in res_short.issues)


def test_vague_eligibility_warning(valid_record, ref_time):
    """Verify placeholder eligibility triggers non-blocking warning."""
    valid_record["eligibility"] = "Check official source."
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.WARNING
    assert any(i.issue_code == "VAGUE_ELIGIBILITY" for i in result.issues)


def test_future_verification_timestamp(valid_record, ref_time):
    """Verify verification timestamp in the future triggers ERROR."""
    # ref_time is 2026-10-21. Set verified_at to 2026-11-01
    valid_record["verified_at"] = "2026-11-01T12:00:00Z"
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "FUTURE_VERIFICATION_TIMESTAMP" for i in result.issues)


def test_contradiction_verified_status_with_critical_errors(valid_record, ref_time):
    """Verify that claiming VERIFIED on an incomplete record triggers contradiction error."""
    valid_record["title"] = ""  # Critical error
    valid_record["status"] = "VERIFIED"
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert result.quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "CONTRADICTORY_VERIFICATION_STATE" for i in result.issues)


def test_contradiction_closed_status_with_future_deadline(valid_record, ref_time):
    """Verify that status=Closed with deadline far in future triggers warning."""
    valid_record["status"] = "Closed"
    valid_record["deadline"] = "2027-02-01"  # > 100 days in future
    result = audit_single_record(valid_record, reference_now=ref_time)
    assert any(i.issue_code == "CONTRADICTORY_LIFECYCLE_STATUS" for i in result.issues)


def test_batch_duplicate_opportunity_ids(valid_record, ref_time):
    """Verify that duplicate opportunity IDs in a batch are detected and marked FAIL."""
    rec1 = dict(valid_record)
    rec2 = dict(valid_record)
    rec2["title"] = "Different Title Same ID"

    audited, issues = audit_batch_records([rec1, rec2], reference_now=ref_time)
    assert len(audited) == 2
    assert audited[0].quality_status == QualityStatus.FAIL
    assert audited[1].quality_status == QualityStatus.FAIL
    assert any(i.issue_code == "DUPLICATE_OPPORTUNITY_ID" for i in issues)


def test_batch_duplicate_content(valid_record, ref_time):
    """Verify duplicate content across different IDs triggers WARNING."""
    rec1 = dict(valid_record)
    rec1["opportunity_id"] = "OPP-001"

    rec2 = dict(valid_record)
    rec2["opportunity_id"] = "OPP-002"  # Different ID, same title & org & url

    audited, issues = audit_batch_records([rec1, rec2], reference_now=ref_time)
    assert len(audited) == 2
    assert any(i.issue_code == "DUPLICATE_OPPORTUNITY_CONTENT" for i in issues)
