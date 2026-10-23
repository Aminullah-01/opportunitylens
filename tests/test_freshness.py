"""Unit tests for deadline lifecycle and verification freshness evaluation."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import pytest

from src.quality.freshness import (
    evaluate_deadline_lifecycle,
    evaluate_verification_freshness,
    parse_deadline_date,
    parse_reference_datetime,
)
from src.quality.models import LifecycleStatus


@pytest.fixture
def ref_time() -> datetime:
    """Deterministic reference time: 2026-10-21 12:00:00 UTC."""
    return datetime(2026, 10, 21, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_reference_datetime():
    """Verify normalization of various datetime, date, and string representations."""
    # None defaults to current UTC
    now_dt = parse_reference_datetime(None)
    assert now_dt.tzinfo == timezone.utc

    # Naive datetime gets UTC timezone
    naive = datetime(2026, 10, 20, 10, 0)
    aware = parse_reference_datetime(naive)
    assert aware.tzinfo == timezone.utc
    assert aware.hour == 10

    # Date object becomes midnight UTC
    d = date(2026, 10, 20)
    aware_d = parse_reference_datetime(d)
    assert aware_d.tzinfo == timezone.utc
    assert aware_d.date() == d

    # ISO string
    iso_dt = parse_reference_datetime("2026-10-20T14:30:00Z")
    assert iso_dt.year == 2026
    assert iso_dt.hour == 14


def test_parse_deadline_date():
    """Verify parsing valid and invalid deadline values."""
    assert parse_deadline_date("2026-11-30")[0] == date(2026, 11, 30)
    assert parse_deadline_date(date(2026, 12, 1))[0] == date(2026, 12, 1)
    assert parse_deadline_date(datetime(2026, 12, 1, 10, 0))[0] == date(2026, 12, 1)
    assert parse_deadline_date(None) == (None, None)
    assert parse_deadline_date("")[0] is None

    # Invalid string format
    d_bad, err = parse_deadline_date("invalid-date")
    assert d_bad is None
    assert "Invalid deadline date format" in err


def test_evaluate_deadline_lifecycle_open(ref_time):
    """Verify open opportunity when deadline is well in future (> 7 days)."""
    # Reference is 2026-10-21. Deadline is 2026-11-30 (40 days remaining).
    status, days = evaluate_deadline_lifecycle("2026-11-30", reference_now=ref_time)
    assert status == LifecycleStatus.OPEN
    assert days == 40


def test_evaluate_deadline_lifecycle_closing_soon(ref_time):
    """Verify closing soon status when deadline is within 7 days."""
    # 2026-10-25 is 4 days after 2026-10-21
    status, days = evaluate_deadline_lifecycle("2026-10-25", reference_now=ref_time)
    assert status == LifecycleStatus.CLOSING_SOON
    assert days == 4


def test_evaluate_deadline_lifecycle_expired(ref_time):
    """Verify expired status when deadline is in the past."""
    # 2026-10-15 is 6 days before 2026-10-21
    status, days = evaluate_deadline_lifecycle("2026-10-15", reference_now=ref_time)
    assert status == LifecycleStatus.EXPIRED
    assert days == -6


def test_evaluate_deadline_lifecycle_explicit_closed(ref_time):
    """Verify that source-confirmed closure is distinguished from inferred expiry."""
    # Even if deadline is in the future, if source marked it closed, status must be CLOSED
    status, days = evaluate_deadline_lifecycle(
        "2026-12-01", source_status="Closed", reference_now=ref_time
    )
    assert status == LifecycleStatus.CLOSED
    assert days == 41

    status_arch, _ = evaluate_deadline_lifecycle(
        "2026-12-01", source_status="archived", reference_now=ref_time
    )
    assert status_arch == LifecycleStatus.CLOSED


def test_evaluate_deadline_lifecycle_missing_is_unknown(ref_time):
    """Verify that missing deadline is UNKNOWN, not assumed open."""
    status_none, days_none = evaluate_deadline_lifecycle(None, reference_now=ref_time)
    assert status_none == LifecycleStatus.UNKNOWN
    assert days_none is None

    status_empty, _ = evaluate_deadline_lifecycle("", reference_now=ref_time)
    assert status_empty == LifecycleStatus.UNKNOWN


def test_evaluate_verification_freshness_fresh(ref_time):
    """Verify verification timestamp within threshold (<= 30 days) is fresh."""
    # Verified 5 days ago: 2026-10-16
    verified_5d = ref_time - timedelta(days=5)
    is_stale, days, msg = evaluate_verification_freshness(
        verified_5d, reference_now=ref_time, stale_threshold_days=30
    )
    assert is_stale is False
    assert days == 5
    assert msg is None


def test_evaluate_verification_freshness_stale(ref_time):
    """Verify verification timestamp older than threshold is marked stale."""
    # Verified 45 days ago: 2026-09-06
    verified_45d = ref_time - timedelta(days=45)
    is_stale, days, msg = evaluate_verification_freshness(
        verified_45d, reference_now=ref_time, stale_threshold_days=30
    )
    assert is_stale is True
    assert days == 45
    assert "Verification is stale" in msg


def test_evaluate_verification_freshness_future_anomaly(ref_time):
    """Verify that verification timestamps in the future are flagged as anomalies."""
    verified_future = ref_time + timedelta(days=10)
    is_stale, days, msg = evaluate_verification_freshness(
        verified_future, reference_now=ref_time
    )
    assert is_stale is True
    assert days == -10
    assert "in the future" in msg


def test_evaluate_verification_freshness_missing(ref_time):
    """Verify that missing verification timestamp is marked stale."""
    is_stale, days, msg = evaluate_verification_freshness(None, reference_now=ref_time)
    assert is_stale is True
    assert days is None
    assert "no verification timestamp" in msg
