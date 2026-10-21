"""Tests for Snowflake integration helpers, application status logic, and URL validation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import pytest

from src.db import get_application_status
from src.demo_data import filter_opportunities
from src.utils import (
    derive_categories,
    format_display_date,
    get_platform_metrics,
    is_valid_url,
)


def test_get_application_status_past_deadline():
    """Deadline in the past should resolve to 'Closed'."""
    past_date = date.today() - timedelta(days=10)
    assert get_application_status(past_date) == "Closed"

    past_iso = past_date.isoformat()
    assert get_application_status(past_iso) == "Closed"

    past_dt = datetime.now(timezone.utc) - timedelta(days=5)
    assert get_application_status(past_dt) == "Closed"


def test_get_application_status_closing_soon():
    """Deadline within 7 days should resolve to 'Closing Soon'."""
    soon_date = date.today() + timedelta(days=3)
    assert get_application_status(soon_date) == "Closing Soon"

    # Exactly today should also be Closing Soon
    assert get_application_status(date.today()) == "Closing Soon"


def test_get_application_status_open():
    """Deadline more than 7 days in the future should resolve to 'Open'."""
    future_date = date.today() + timedelta(days=30)
    assert get_application_status(future_date) == "Open"

    future_iso = future_date.isoformat()
    assert get_application_status(future_iso) == "Open"


def test_get_application_status_none_or_invalid():
    """Missing or invalid deadlines should return 'Unknown'."""
    assert get_application_status(None) == "Unknown"
    assert get_application_status("invalid-date-string") == "Unknown"
    assert get_application_status("") == "Unknown"


def test_is_valid_url():
    """Verify that only valid http/https URLs are treated as clickable."""
    assert is_valid_url("https://example.org/apply") is True
    assert is_valid_url("http://sub.domain.edu/scholarships") is True
    assert is_valid_url("HTTPS://EXAMPLE.COM") is True

    # Invalid URLs
    assert is_valid_url("") is False
    assert is_valid_url(None) is False
    assert is_valid_url("ftp://example.com") is False
    assert is_valid_url("javascript:alert(1)") is False
    assert is_valid_url("not a url") is False


def test_format_display_date():
    """Ensure dates, datetimes, strings, and None values are formatted without crashing."""
    d = date(2026, 11, 30)
    assert format_display_date(d) == "2026-11-30"

    dt = datetime(2026, 12, 15, 14, 30, 0)
    assert format_display_date(dt) == "2026-12-15"

    assert format_display_date("2026-10-01T08:00:00Z") == "2026-10-01"
    assert format_display_date(None) == "N/A"
    assert format_display_date("") == "N/A"


def test_derive_categories():
    """Verify category derivation from the active dataset."""
    sample_records = [
        {"category": "Scholarships"},
        {"category": "Internships"},
        {"category": "Scholarships"},
        {"category": "Tech Training"},
        {"category": None},
    ]
    categories = derive_categories(sample_records)
    assert categories == ["Internships", "Scholarships", "Tech Training"]

    # Empty list
    assert derive_categories([]) == []


def test_get_platform_metrics_live_vs_demo():
    """Verify metric calculations for live Snowflake and demo datasets."""
    sample_records = [
        {"category": "Scholarships"},
        {"category": "Scholarships"},
        {"category": "Internships"},
    ]
    metrics = get_platform_metrics(sample_records, is_live=True)
    assert metrics["total"] == 3
    assert metrics["scholarships"] == 2
    assert metrics["internships"] == 1
    assert metrics["training"] == 0
    assert metrics["is_live"] is True
    assert "Snowflake" in metrics["data_source"]

    # Empty records
    empty_metrics = get_platform_metrics([], is_live=True)
    assert empty_metrics["total"] == 0
    assert empty_metrics["scholarships"] == 0


def test_filter_opportunities_with_snowflake_records():
    """Verify filter_opportunities works seamlessly on live-style Snowflake records."""
    snowflake_style_records = [
        {
            "opportunity_id": "SNOW-001",
            "title": "Federal STEM Grant",
            "category": "Scholarships",
            "organization": "Ministry of Innovation",
            "description": "Tuition coverage for STEM undergraduates.",
            "eligibility": "Nigerian undergraduate students",
            "location": "Abuja / Nationwide",
            "deadline": "2026-12-01",
            "status": "Open",
            "verification_status": "VERIFIED",
            "is_sample_data": False,
        },
        {
            "opportunity_id": "SNOW-002",
            "title": "Backend Engineering Internship",
            "category": "Internships",
            "organization": "FinTech Hub",
            "description": "Python backend development.",
            "eligibility": "Recent graduates or final year students",
            "location": "Lagos",
            "deadline": "2026-10-10",
            "status": "Closed",
            "verification_status": "PENDING",
            "is_sample_data": False,
        },
    ]

    # Category filter
    internships = filter_opportunities(snowflake_style_records, category="Internships")
    assert len(internships) == 1
    assert internships[0]["opportunity_id"] == "SNOW-002"

    # Status filter
    open_records = filter_opportunities(snowflake_style_records, status="Open")
    assert len(open_records) == 1
    assert open_records[0]["opportunity_id"] == "SNOW-001"

    # Keyword search across title/org/description/location
    abuja_records = filter_opportunities(snowflake_style_records, query="Abuja")
    assert len(abuja_records) == 1
    assert abuja_records[0]["opportunity_id"] == "SNOW-001"
