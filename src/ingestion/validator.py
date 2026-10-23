"""Validation and normalization logic for raw opportunity records."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import re
from typing import Any, Dict, Optional

from src.ingestion.models import (
    CANONICAL_CATEGORIES,
    NormalizedOpportunity,
    VALID_VERIFICATION_STATUSES,
    ValidationResult,
)
from src.utils import is_valid_url


def normalize_category(category_input: Optional[str]) -> Optional[str]:
    """Map category case-insensitively to approved canonical category name."""
    if not category_input or not isinstance(category_input, str):
        return None
    cleaned = category_input.strip()
    for canonical in CANONICAL_CATEGORIES:
        if cleaned.lower() == canonical.lower():
            return canonical
    return None


def parse_date_value(val: Any) -> tuple[Optional[date], Optional[str]]:
    """Parse date from date, datetime, ISO string, or human-readable date.

    Returns:
        tuple of (parsed_date, error_message).
    """
    if val is None or val == "":
        return None, None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val, None
    if isinstance(val, datetime):
        return val.date(), None
    if isinstance(val, str):
        val_str = val.strip()
        try:
            return date.fromisoformat(val_str[:10]), None
        except (ValueError, TypeError):
            pass

        try:
            from dateutil import parser as dt_parser

            parsed_dt = dt_parser.parse(val_str, fuzzy=True)
            return parsed_dt.date(), None
        except Exception:
            return None, f"Invalid date format '{val}'; could not parse date."

    return None, f"Unsupported date type '{type(val).__name__}'"


def parse_datetime_value(val: Any) -> tuple[Optional[datetime], Optional[str]]:
    """Parse datetime from datetime, ISO string, or None.

    Returns:
        tuple of (parsed_datetime, error_message).
    """
    if val is None or val == "":
        return None, None
    if isinstance(val, datetime):
        return val, None
    if isinstance(val, str):
        val_str = val.strip().replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(val_str), None
        except (ValueError, TypeError):
            return None, f"Invalid datetime format '{val}'"
    return None, f"Unsupported datetime type '{type(val).__name__}'"


def generate_stable_id(organization: str, title: str) -> str:
    """Generate a deterministic, reproducible opportunity identifier from org and title."""
    clean_org = re.sub(r"[^a-zA-Z0-9]+", "", organization).lower()
    clean_title = re.sub(r"[^a-zA-Z0-9]+", "", title).lower()
    raw_key = f"{clean_org}::{clean_title}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:10].upper()
    prefix = clean_org[:6].upper() or "OPP"
    return f"OPP-{prefix}-{digest}"


def validate_raw_record(raw: Dict[str, Any]) -> ValidationResult:
    """Validate a raw opportunity dictionary and return a normalized record or error list.

    Args:
        raw: Dictionary containing raw opportunity fields.

    Returns:
        ValidationResult with validation status, errors, and normalized model.
    """
    errors = []
    raw_id = str(raw.get("opportunity_id") or "UNSPECIFIED").strip()

    # 1. Title validation
    title = raw.get("title")
    if not title or not isinstance(title, str) or not title.strip():
        errors.append("Missing required field: 'title' must be a non-empty string")
        clean_title = ""
    else:
        clean_title = title.strip()

    # 2. Organization validation
    org = raw.get("organization")
    if not org or not isinstance(org, str) or not org.strip():
        errors.append("Missing required field: 'organization' must be a non-empty string")
        clean_org = "Unspecified Organization"
    else:
        clean_org = org.strip()

    # 3. Category validation and normalization
    raw_cat = raw.get("category")
    normalized_cat = normalize_category(raw_cat)
    if not normalized_cat:
        errors.append(
            f"Invalid category '{raw_cat}'. Must be one of: {', '.join(CANONICAL_CATEGORIES)}"
        )

    # 4. Source URL validation
    source_url = raw.get("source_url")
    if not is_valid_url(source_url):
        errors.append(
            f"Missing or invalid source_url '{source_url}'. Must be a valid http:// or https:// URL"
        )
    clean_url = str(source_url).strip() if source_url else ""

    # 5. Deadline parsing
    deadline, deadline_err = parse_date_value(raw.get("deadline"))
    if deadline_err:
        errors.append(deadline_err)

    # 6. Verified timestamp parsing
    verified_at, verified_err = parse_datetime_value(raw.get("verified_at"))
    if verified_err:
        errors.append(verified_err)

    # 7. Verification status validation
    status = raw.get("status", "UNVERIFIED")
    if not status or not isinstance(status, str):
        status = "UNVERIFIED"
    status_upper = status.strip().upper()
    if status_upper not in VALID_VERIFICATION_STATUSES:
        errors.append(
            f"Invalid verification status '{status}'. Must be one of: {', '.join(VALID_VERIFICATION_STATUSES)}"
        )

    # 8. Identifier handling
    if raw.get("opportunity_id") and str(raw["opportunity_id"]).strip():
        opp_id = str(raw["opportunity_id"]).strip()
    else:
        opp_id = generate_stable_id(clean_org, clean_title)

    if errors:
        return ValidationResult(is_valid=False, record=None, raw_id=raw_id, errors=errors)

    normalized_record = NormalizedOpportunity(
        opportunity_id=opp_id,
        title=clean_title,
        category=normalized_cat,  # type: ignore[arg-type]
        organization=clean_org,
        description=str(raw.get("description") or "").strip() or "No description provided.",
        eligibility=str(raw.get("eligibility") or "").strip() or "Check official source.",
        education_level=str(raw.get("education_level") or "").strip() or "All Levels",
        location=str(raw.get("location") or "").strip() or "Nationwide",
        deadline=deadline,
        source_url=clean_url,
        verified_at=verified_at,
        status=status_upper,
    )

    return ValidationResult(
        is_valid=True,
        record=normalized_record,
        raw_id=opp_id,
        errors=[],
    )
