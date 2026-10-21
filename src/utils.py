"""Utility functions for OpportunityLens.

Contains URL validation, date formatting, category derivation, and
metric calculations decoupled from the Streamlit UI for testability.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List


def is_valid_url(url: Any) -> bool:
    """Check if a URL string is valid and clickable (http:// or https://).

    Args:
        url: The URL value to validate.

    Returns:
        True if the URL is a non-empty string starting with http:// or https://.
    """
    if not url or not isinstance(url, str):
        return False
    u = url.strip().lower()
    return u.startswith("http://") or u.startswith("https://")


def format_display_date(val: Any) -> str:
    """Safely format a date, datetime, or date-string for UI display.

    Args:
        val: The date value (date, datetime, ISO string, or None).

    Returns:
        A YYYY-MM-DD formatted string, or 'N/A' if missing/invalid.
    """
    if val is None:
        return "N/A"
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    val_str = str(val).strip()
    return val_str[:10] if val_str else "N/A"


def derive_categories(opportunities: List[Dict[str, Any]]) -> List[str]:
    """Derive sorted unique categories from the active opportunity records.

    Args:
        opportunities: List of opportunity dictionaries.

    Returns:
        Sorted list of unique category names present in the active dataset.
    """
    categories = {
        opp.get("category")
        for opp in opportunities
        if opp.get("category") and isinstance(opp.get("category"), str)
    }
    return sorted(list(categories))


def get_platform_metrics(
    opportunities: List[Dict[str, Any]], is_live: bool = True
) -> Dict[str, Any]:
    """Calculate platform metrics from opportunity records.

    Args:
        opportunities: List of opportunity dictionaries.
        is_live: Whether the dataset represents live Snowflake records.

    Returns:
        Dictionary with aggregate counts and data source information.
    """
    total = len(opportunities)
    scholarships = sum(1 for r in opportunities if r.get("category") == "Scholarships")
    internships = sum(1 for r in opportunities if r.get("category") == "Internships")
    training = sum(1 for r in opportunities if r.get("category") == "Tech Training")
    hackathons = sum(1 for r in opportunities if r.get("category") == "Hackathons")
    jobs = sum(1 for r in opportunities if r.get("category") == "Entry-Level Jobs")

    return {
        "total": total,
        "scholarships": scholarships,
        "internships": internships,
        "training": training,
        "hackathons": hackathons,
        "jobs": jobs,
        "is_live": is_live,
        "data_source": (
            "Snowflake (OPPORTUNITYLENS_DB.APP.OPPORTUNITIES)"
            if is_live
            else "Fictional Demo Dataset"
        ),
    }
