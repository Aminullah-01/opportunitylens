"""Utility functions for OpportunityLens.

Contains URL validation, date formatting, category derivation, safe text
escaping helpers, and metric calculations decoupled from the Streamlit UI
for testability.
"""

from __future__ import annotations

from datetime import date, datetime
import html
from typing import Any, Dict, List, Optional


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


def sanitize_html(text: Any, default: str = "") -> str:
    """Escape HTML special characters to prevent XSS and layout corruption.

    Args:
        text: Raw text or object to be safely displayed in HTML.
        default: Fallback string if text is empty or None.

    Returns:
        HTML-escaped string safe for insertion into markup.
    """
    if text is None:
        return default
    s = str(text).strip()
    return html.escape(s, quote=True) if s else default


def get_safe_url(url: Any) -> Optional[str]:
    """Validate and sanitize a URL string, rejecting unsafe schemes.

    Args:
        url: Candidate URL value.

    Returns:
        Sanitized URL string if starting with http:// or https://, else None.
    """
    if not is_valid_url(url):
        return None
    url_str = str(url).strip()
    return html.escape(url_str, quote=True)


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


def derive_locations(opportunities: List[Dict[str, Any]]) -> List[str]:
    """Derive sorted unique locations present in the active dataset.

    Args:
        opportunities: List of opportunity dictionaries.

    Returns:
        Sorted list of unique location strings present in the active dataset.
    """
    locations = {
        opp.get("location")
        for opp in opportunities
        if opp.get("location") and isinstance(opp.get("location"), str)
    }
    return sorted(list(locations))


def derive_education_levels(opportunities: List[Dict[str, Any]]) -> List[str]:
    """Derive sorted unique education levels present in the active dataset.

    Args:
        opportunities: List of opportunity dictionaries.

    Returns:
        Sorted list of unique education levels present in the active dataset.
    """
    levels = {
        opp.get("education_level")
        for opp in opportunities
        if opp.get("education_level") and isinstance(opp.get("education_level"), str)
    }
    return sorted(list(levels))


_MARKDOWN_SPECIALS = "\\`*_{}[]()#+-.!|~<>"


def escape_markdown(text: Any, default: str = "") -> str:
    """Escape Markdown special characters so untrusted text renders as plain text.

    Streamlit renders strings through a Markdown pipeline by default. Escaping
    punctuation such as brackets, asterisks, and angle brackets prevents
    database-sourced values from triggering Markdown formatting, link/image
    directives, or Streamlit color-badge shortcodes.

    Args:
        text: Raw text or object (e.g. an opportunity title from Snowflake).
        default: Fallback string if text is empty or None.

    Returns:
        Markdown-escaped string safe to embed in st.markdown / st.write text.
    """
    if text is None:
        return default
    s = str(text).strip()
    if not s:
        return default
    return "".join(
        ("\\" + ch) if ch in _MARKDOWN_SPECIALS else ch for ch in s
    )


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
