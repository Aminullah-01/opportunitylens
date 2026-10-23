"""Deterministic deadline and verification freshness evaluation module."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Tuple

from src.quality.models import LifecycleStatus


def parse_reference_datetime(ref: Optional[datetime | date | str] = None) -> datetime:
    """Normalize a reference point in time to a timezone-aware UTC datetime.

    Args:
        ref: Optional datetime, date, or ISO string. Defaults to current UTC time.

    Returns:
        Timezone-aware UTC datetime.
    """
    if ref is None:
        return datetime.now(timezone.utc)
    if isinstance(ref, datetime):
        if ref.tzinfo is None:
            return ref.replace(tzinfo=timezone.utc)
        return ref.astimezone(timezone.utc)
    if isinstance(ref, date):
        return datetime.combine(ref, datetime.min.time(), tzinfo=timezone.utc)
    if isinstance(ref, str):
        val = ref.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (ValueError, TypeError):
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def parse_deadline_date(val: Any) -> Tuple[Optional[date], Optional[str]]:
    """Parse a deadline value into a date object.

    Args:
        val: date, datetime, ISO string, or None.

    Returns:
        Tuple of (parsed_date, error_message).
    """
    if val is None or val == "":
        return None, None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val, None
    if isinstance(val, datetime):
        return val.date(), None
    if isinstance(val, str):
        clean = val.strip()
        try:
            return date.fromisoformat(clean[:10]), None
        except (ValueError, TypeError):
            return None, f"Invalid deadline date format '{val}'; expected YYYY-MM-DD"
    return None, f"Unsupported deadline type '{type(val).__name__}'"


def evaluate_deadline_lifecycle(
    deadline_val: Any,
    source_status: Optional[str] = None,
    reference_now: Optional[datetime | date | str] = None,
    closing_soon_days: int = 7,
) -> Tuple[LifecycleStatus, Optional[int]]:
    """Evaluate application lifecycle status from deadline and source status.

    Args:
        deadline_val: Deadline as date, datetime, ISO string, or None.
        source_status: Raw or source-provided status (e.g. 'Closed', 'Open', 'Archived').
        reference_now: Deterministic reference timestamp (defaults to current UTC).
        closing_soon_days: Number of days remaining before deadline considered closing soon.

    Returns:
        Tuple of (LifecycleStatus, days_remaining).
    """
    ref_dt = parse_reference_datetime(reference_now)
    ref_date = ref_dt.date()

    # 1. Check if source explicitly marked closed
    if source_status:
        clean_src = source_status.strip().lower()
        if clean_src in ("closed", "expired", "archived", "completed"):
            parsed_d, _ = parse_deadline_date(deadline_val)
            days_rem = (parsed_d - ref_date).days if parsed_d else None
            return LifecycleStatus.CLOSED, days_rem

    # 2. Parse deadline
    parsed_date, parse_err = parse_deadline_date(deadline_val)
    if parse_err or parsed_date is None:
        # Missing or unparseable deadlines are UNKNOWN, not assumed open
        return LifecycleStatus.UNKNOWN, None

    days_remaining = (parsed_date - ref_date).days

    # 3. Deadline has passed
    if days_remaining < 0:
        return LifecycleStatus.EXPIRED, days_remaining

    # 4. Closing soon threshold
    if days_remaining <= closing_soon_days:
        return LifecycleStatus.CLOSING_SOON, days_remaining

    # 5. Active open application window
    return LifecycleStatus.OPEN, days_remaining


def evaluate_verification_freshness(
    verified_at_val: Any,
    reference_now: Optional[datetime | date | str] = None,
    stale_threshold_days: int = 30,
) -> Tuple[bool, Optional[int], Optional[str]]:
    """Assess whether verification metadata is fresh, stale, missing, or in the future.

    Args:
        verified_at_val: Verification timestamp as datetime, string, or None.
        reference_now: Deterministic reference timestamp (defaults to current UTC).
        stale_threshold_days: Days after which verification is considered stale.

    Returns:
        Tuple of (is_stale, days_since_verified, warning_or_error_message).
    """
    if verified_at_val is None or verified_at_val == "":
        return True, None, "Record has no verification timestamp recorded."

    ref_dt = parse_reference_datetime(reference_now)

    # Parse verified_at
    parsed_dt: Optional[datetime] = None
    if isinstance(verified_at_val, datetime):
        parsed_dt = (
            verified_at_val.replace(tzinfo=timezone.utc)
            if verified_at_val.tzinfo is None
            else verified_at_val.astimezone(timezone.utc)
        )
    elif isinstance(verified_at_val, date):
        parsed_dt = datetime.combine(
            verified_at_val, datetime.min.time(), tzinfo=timezone.utc
        )
    elif isinstance(verified_at_val, str):
        clean = verified_at_val.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(clean)
            parsed_dt = (
                parsed.replace(tzinfo=timezone.utc)
                if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc)
            )
        except (ValueError, TypeError):
            return True, None, f"Unparseable verification timestamp '{verified_at_val}'."
    else:
        return True, None, f"Unsupported timestamp type '{type(verified_at_val).__name__}'."

    # Future verification timestamp check (clock skew or falsified audit)
    if parsed_dt > ref_dt:
        days_future = (parsed_dt.date() - ref_dt.date()).days
        return (
            True,
            -days_future,
            f"Verification timestamp is set {days_future} days in the future ({parsed_dt.isoformat()}).",
        )

    days_since = (ref_dt.date() - parsed_dt.date()).days

    if days_since > stale_threshold_days:
        return (
            True,
            days_since,
            f"Verification is stale: last checked {days_since} days ago (threshold: {stale_threshold_days} days).",
        )

    return False, days_since, None
