"""Tests for OpportunityLens demo data and filter business logic."""

from __future__ import annotations

import pytest
from src.config import app_config, snowflake_config, ai_config
from src.demo_data import (
    DEMO_OPPORTUNITIES,
    VALID_CATEGORIES,
    VALID_STATUSES,
    filter_opportunities,
    get_categories,
    get_demo_metrics,
    get_demo_opportunities,
)

REQUIRED_FIELDS = {
    "opportunity_id",
    "title",
    "category",
    "organization",
    "description",
    "eligibility",
    "education_level",
    "location",
    "deadline",
    "source_url",
    "verified_at",
    "status",
    "is_sample_data",
}


def test_demo_data_is_non_empty_list():
    """Ensure demo opportunities is a non-empty list of dictionaries."""
    data = get_demo_opportunities()
    assert isinstance(data, list)
    assert len(data) > 0
    assert all(isinstance(item, dict) for item in data)


def test_demo_data_required_fields():
    """Ensure every opportunity record contains all required fields."""
    data = get_demo_opportunities()
    for record in data:
        missing_fields = REQUIRED_FIELDS - set(record.keys())
        assert not missing_fields, (
            f"Record {record.get('opportunity_id')} is missing fields: {missing_fields}"
        )
        # Check that none of the required string fields are empty
        for field in ("opportunity_id", "title", "category", "organization", "description"):
            assert str(record[field]).strip(), f"Field '{field}' should not be blank in {record}"


def test_explicit_sample_labelling():
    """Ensure every record is explicitly flagged as sample data."""
    data = get_demo_opportunities()
    for record in data:
        assert record.get("is_sample_data") is True, (
            f"Record {record.get('opportunity_id')} must have is_sample_data=True"
        )
        assert record.get("opportunity_id", "").startswith("DEMO-"), (
            f"Record ID {record.get('opportunity_id')} must clearly indicate demo/sample data"
        )


def test_valid_categories():
    """Ensure every record belongs to an approved canonical category."""
    data = get_demo_opportunities()
    assert len(get_categories()) == len(VALID_CATEGORIES)
    for record in data:
        assert record["category"] in VALID_CATEGORIES, (
            f"Invalid category '{record['category']}' in record {record.get('opportunity_id')}"
        )


def test_valid_statuses():
    """Ensure every record has a recognized status value."""
    data = get_demo_opportunities()
    for record in data:
        assert record["status"] in VALID_STATUSES, (
            f"Invalid status '{record['status']}' in record {record.get('opportunity_id')}"
        )


def test_filter_by_category():
    """Test filtering opportunities by specific category and 'All'."""
    data = get_demo_opportunities()

    scholarships = filter_opportunities(data, category="Scholarships")
    assert len(scholarships) > 0
    assert all(r["category"] == "Scholarships" for r in scholarships)

    internships = filter_opportunities(data, category="Internships")
    assert len(internships) > 0
    assert all(r["category"] == "Internships" for r in internships)

    all_records = filter_opportunities(data, category="All")
    assert len(all_records) == len(data)


def test_filter_by_status():
    """Test filtering opportunities by open/closed status."""
    data = get_demo_opportunities()

    open_items = filter_opportunities(data, status="Open")
    assert len(open_items) > 0
    assert all(r["status"] == "Open" for r in open_items)

    closing_items = filter_opportunities(data, status="Closing Soon")
    assert len(closing_items) > 0
    assert all(r["status"] == "Closing Soon" for r in closing_items)


def test_filter_by_search_query():
    """Test case-insensitive keyword search across fields."""
    data = get_demo_opportunities()

    # Search by organization
    results = filter_opportunities(data, query="Arewa")
    assert len(results) >= 1
    assert any("Arewa" in r["organization"] for r in results)

    # Search by location
    results = filter_opportunities(data, query="Gombe")
    assert len(results) >= 1
    assert any("Gombe" in r["location"] for r in results)

    # Search by topic in description
    results = filter_opportunities(data, query="Python")
    assert len(results) >= 1

    # Search with non-matching string
    results_empty = filter_opportunities(data, query="xyznonexistenttoken123")
    assert len(results_empty) == 0


def test_filter_combined_query_and_category():
    """Test applying both category filter and search query simultaneously."""
    data = get_demo_opportunities()

    results = filter_opportunities(
        data,
        query="Engineering",
        category="Internships",
    )
    assert all(r["category"] == "Internships" for r in results)
    assert all(
        "engineering" in (r["title"] + r["description"] + r["eligibility"]).lower()
        for r in results
    )


def test_get_demo_metrics():
    """Ensure aggregate metrics calculate correct counts and are marked as preview."""
    data = get_demo_opportunities()
    metrics = get_demo_metrics(data)

    assert metrics["is_preview"] is True
    assert metrics["total"] == len(data)
    assert metrics["scholarships"] == sum(1 for r in data if r["category"] == "Scholarships")
    assert metrics["internships"] == sum(1 for r in data if r["category"] == "Internships")
    assert metrics["training"] == sum(1 for r in data if r["category"] == "Tech Training")
    assert metrics["hackathons"] == sum(1 for r in data if r["category"] == "Hackathons")
    assert metrics["jobs"] == sum(1 for r in data if r["category"] == "Entry-Level Jobs")
    assert "Fictional Demo" in metrics["data_source"]


def test_config_initialization():
    """Ensure configuration objects load safely without making network calls."""
    assert app_config.APP_NAME == "OpportunityLens"
    assert "Find opportunities" in app_config.APP_TAGLINE
    assert app_config.HACKATHON_EVENT == "Hacktoberfest Hack Day Gombe"
    # Snowflake and AI connections should be unconfigured in Phase 1 default state
    assert isinstance(snowflake_config.is_configured, bool)
    assert isinstance(ai_config.is_configured, bool)
