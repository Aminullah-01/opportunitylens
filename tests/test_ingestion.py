"""Unit tests for OpportunityLens data ingestion, validation, and analytics."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from src.analytics import calculate_analytics_summary, extract_domain
from src.ingestion.models import NormalizedOpportunity
from src.ingestion.pipeline import (
    execute_snowflake_merge,
    load_raw_records_from_file,
    run_ingestion_pipeline,
    validate_and_deduplicate,
)
from src.ingestion.validator import (
    generate_stable_id,
    normalize_category,
    parse_date_value,
    parse_datetime_value,
    validate_raw_record,
)


def test_normalize_category():
    """Ensure categories normalize case-insensitively to canonical values."""
    assert normalize_category("scholarships") == "Scholarships"
    assert normalize_category("TECH TRAINING") == "Tech Training"
    assert normalize_category("Internships") == "Internships"
    assert normalize_category("invalid category") is None
    assert normalize_category(None) is None


def test_parse_date_value():
    """Ensure date values parse cleanly and report errors on bad input."""
    # Valid ISO string
    d, err = parse_date_value("2026-11-30")
    assert d == date(2026, 11, 30)
    assert err is None

    # Date object
    d, err = parse_date_value(date(2026, 12, 1))
    assert d == date(2026, 12, 1)
    assert err is None

    # Datetime object
    d, err = parse_date_value(datetime(2026, 12, 5, 10, 0))
    assert d == date(2026, 12, 5)
    assert err is None

    # None / empty
    d, err = parse_date_value(None)
    assert d is None and err is None

    # Malformed date string
    d, err = parse_date_value("not-a-date")
    assert d is None and err is not None


def test_validate_raw_record_valid():
    """Valid raw record returns a NormalizedOpportunity without errors."""
    raw = {
        "opportunity_id": "OPP-TEST-001",
        "title": "National Tech Fellowship",
        "category": "Tech Training",
        "organization": "National Innovation Hub",
        "description": "Fellowship for software engineers.",
        "eligibility": "Nigerian graduates",
        "education_level": "BSc / HND",
        "location": "Abuja / Remote",
        "deadline": "2026-11-30",
        "source_url": "https://example.gov.ng/apply",
        "verified_at": "2026-10-21T10:00:00Z",
        "status": "VERIFIED",
    }
    result = validate_raw_record(raw)
    assert result.is_valid is True
    assert result.record is not None
    assert result.record.title == "National Tech Fellowship"
    assert result.record.category == "Tech Training"
    assert result.record.deadline == date(2026, 11, 30)
    assert result.record.status == "VERIFIED"


def test_validate_raw_record_missing_fields_and_invalid_data():
    """Ensure required field omissions and invalid attributes trigger explicit rejection reasons."""
    raw = {
        "opportunity_id": "BAD-001",
        "title": "",  # Missing title
        "category": "Invalid Cat",  # Invalid category
        "organization": "   ",  # Blank org
        "deadline": "bad-date",  # Bad deadline
        "source_url": "ftp://not-http.org",  # Bad URL
        "status": "UNKNOWN_STATUS",  # Bad status
    }
    result = validate_raw_record(raw)
    assert result.is_valid is False
    assert result.record is None
    assert any("title" in e for e in result.errors)
    assert any("organization" in e for e in result.errors)
    assert any("category" in e for e in result.errors)
    assert any("source_url" in e for e in result.errors)
    assert any("date format" in e for e in result.errors)
    assert any("verification status" in e for e in result.errors)


def test_generate_stable_id():
    """Ensure deterministic identifier generation."""
    id1 = generate_stable_id("NITDA Nigeria", "Cloud Fellowship 2026")
    id2 = generate_stable_id("NITDA Nigeria", "Cloud Fellowship 2026")
    id3 = generate_stable_id("NITDA Nigeria", "Different Title")
    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("OPP-NITDAN-")


def test_validate_and_deduplicate_in_batch():
    """Ensure in-batch deduplication correctly resolves duplicate records."""
    records = [
        {
            "opportunity_id": "REC-001",
            "title": "Scholarship A",
            "category": "Scholarships",
            "organization": "Org Alpha",
            "source_url": "https://alpha.org/apply",
            "deadline": "2026-12-01",
            "status": "VERIFIED",
        },
        {
            "opportunity_id": "REC-001",  # Same ID
            "title": "Scholarship A Updated",
            "category": "Scholarships",
            "organization": "Org Alpha",
            "source_url": "https://alpha.org/apply",
            "deadline": "2026-12-01",
            "status": "VERIFIED",
        },
        {
            "opportunity_id": "REC-BAD",
            "title": "",  # Invalid
            "category": "Scholarships",
            "organization": "Org Beta",
            "source_url": "https://beta.org/apply",
        },
    ]

    valid, rejections, skipped = validate_and_deduplicate(records)
    assert len(valid) == 1
    assert len(rejections) == 1
    assert skipped == 1
    assert valid[0].opportunity_id == "REC-001"
    assert valid[0].title == "Scholarship A Updated"


def test_load_raw_records_from_file(tmp_path: Path):
    """Test loading records from valid JSON and CSV, and catching missing files."""
    json_file = tmp_path / "test_data.json"
    json_file.write_text(json.dumps([{"title": "Test"}]), encoding="utf-8")

    loaded_json = load_raw_records_from_file(json_file)
    assert len(loaded_json) == 1
    assert loaded_json[0]["title"] == "Test"

    # Missing file
    with pytest.raises(FileNotFoundError):
        load_raw_records_from_file(tmp_path / "nonexistent.json")


def test_execute_snowflake_merge_with_mock():
    """Verify parameterized Snowflake MERGE execution using mocked database connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = (1, 0)  # 1 inserted, 0 updated

    record = NormalizedOpportunity(
        opportunity_id="MOCK-001",
        title="Mock Opportunity",
        category="Tech Training",
        organization="Mock Org",
        description="Description",
        eligibility="Eligibility",
        education_level="Undergraduate",
        location="Lagos",
        deadline=date(2026, 11, 15),
        source_url="https://mock.org/apply",
        verified_at=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc),
        status="VERIFIED",
    )

    inserted, updated = execute_snowflake_merge([record], connection=mock_conn)
    assert inserted == 1
    assert updated == 0
    assert mock_cursor.execute.call_count == 1
    call_args = mock_cursor.execute.call_args
    # Check that SQL is MERGE and params are tuple of 12 elements
    assert "MERGE INTO OPPORTUNITYLENS_DB.APP.OPPORTUNITIES" in call_args[0][0]
    assert len(call_args[0][1]) == 12
    assert call_args[0][1][0] == "MOCK-001"


def test_run_ingestion_pipeline_dry_run(tmp_path: Path):
    """Test pipeline execution in dry-run mode without live DB calls."""
    test_file = tmp_path / "dry_run_records.json"
    records = [
        {
            "opportunity_id": "DRY-001",
            "title": "Dry Run Training",
            "category": "Tech Training",
            "organization": "Dry Run Org",
            "source_url": "https://dryrun.org/fellowship",
            "deadline": "2026-11-20",
            "status": "VERIFIED",
        },
        {
            "opportunity_id": "DRY-002",
            "title": "",  # Invalid
            "category": "Tech Training",
            "organization": "Dry Run Org",
            "source_url": "not-a-url",
        },
    ]
    test_file.write_text(json.dumps(records), encoding="utf-8")

    report = run_ingestion_pipeline(test_file, dry_run=True)
    assert report.total_records == 2
    assert report.valid_records == 1
    assert report.rejected_records == 1
    assert report.inserted == 0  # Dry run: no DB insertion
    assert report.dry_run is True
    assert "DRY-002" in report.summary_text()


def test_run_ingestion_pipeline_empty_file(tmp_path: Path):
    """Test pipeline handling an empty list of records."""
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("[]", encoding="utf-8")

    report = run_ingestion_pipeline(empty_file, dry_run=True)
    assert report.total_records == 0
    assert report.valid_records == 0
    assert report.rejected_records == 0


def test_analytics_calculations():
    """Verify analytical metrics, distributions, upcoming deadlines, and domain extraction."""
    today = datetime.now(timezone.utc).date()
    soon_deadline = today + timedelta(days=5)
    far_deadline = today + timedelta(days=25)

    sample_opps = [
        {
            "opportunity_id": "AN-01",
            "title": "Closing Soon Scholarship",
            "category": "Scholarships",
            "organization": "Org 1",
            "location": "Lagos",
            "deadline": soon_deadline,
            "status": "Closing Soon",
            "verification_status": "VERIFIED",
            "source_url": "https://portal.org1.ng/apply",
            "verified_at": datetime(2026, 10, 21, 10, 0),
        },
        {
            "opportunity_id": "AN-02",
            "title": "Open Tech Training",
            "category": "Tech Training",
            "organization": "Org 2",
            "location": "Remote",
            "deadline": far_deadline,
            "status": "Open",
            "verification_status": "VERIFIED",
            "source_url": "https://careers.org2.com/fellowship",
            "verified_at": datetime(2026, 10, 21, 12, 0),
        },
        {
            "opportunity_id": "AN-03",
            "title": "Rolling Community Bootcamp",
            "category": "Tech Training",
            "organization": "Org 1",
            "location": "Lagos",
            "deadline": None,
            "status": "Unknown",
            "verification_status": "NEEDS_REVIEW",
            "source_url": "https://community.org1.ng/bootcamp",
            "verified_at": datetime(2026, 10, 20, 8, 0),
        },
    ]

    summary = calculate_analytics_summary(sample_opps)
    assert summary["total"] == 3
    assert summary["category_counts"]["Scholarships"] == 1
    assert summary["category_counts"]["Tech Training"] == 2
    assert summary["location_counts"]["Lagos"] == 2
    assert summary["verification_counts"]["VERIFIED"] == 2
    assert summary["verification_counts"]["NEEDS_REVIEW"] == 1
    assert summary["application_status_counts"]["Rolling / Ongoing"] == 1
    assert summary["unique_organizations"] == 2
    assert summary["unique_domains"] == 3
    assert len(summary["upcoming_deadlines"]) == 2
    # Verify sorting: soonest deadline first
    assert summary["upcoming_deadlines"][0]["opportunity_id"] == "AN-01"
    assert summary["latest_verification"] == datetime(2026, 10, 21, 12, 0)
    assert extract_domain("https://sub.domain.org/path") == "sub.domain.org"


def test_calculate_analytics_summary_empty():
    """Verify calculate_analytics_summary handles empty dataset gracefully."""
    summary = calculate_analytics_summary([])
    assert summary["total"] == 0
    assert summary["category_counts"] == {}
    assert summary["upcoming_deadlines"] == []
    assert summary["latest_verification"] is None
