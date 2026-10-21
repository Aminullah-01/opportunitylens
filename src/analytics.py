"""Analytics computation and aggregation helpers for OpportunityLens.

Computes aggregations for categories, locations, verification health,
application lifecycle status, upcoming deadlines, and data freshness.
Decoupled from Streamlit for automated testing.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from src.utils import format_display_date


def extract_domain(url: Optional[str]) -> str:
    """Extract hostname from URL or return 'Unknown'."""
    if not url or not isinstance(url, str):
        return "Unknown"
    try:
        parsed = urlparse(url)
        return parsed.netloc or "Unknown"
    except Exception:
        return "Unknown"


def calculate_analytics_summary(opportunities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate comprehensive analytics and summary metrics from opportunity records.

    Args:
        opportunities: List of opportunity dictionaries.

    Returns:
        Dictionary containing counts, distributions, upcoming deadlines, and freshness metadata.
    """
    total = len(opportunities)
    if total == 0:
        return {
            "total": 0,
            "category_counts": {},
            "location_counts": {},
            "verification_counts": {},
            "application_status_counts": {},
            "unique_organizations": 0,
            "unique_domains": 0,
            "upcoming_deadlines": [],
            "latest_verification": None,
            "earliest_verification": None,
        }

    # 1. Category counts
    category_counts: Dict[str, int] = {}
    for opp in opportunities:
        cat = opp.get("category") or "Other"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    # 2. Location counts
    location_counts: Dict[str, int] = {}
    for opp in opportunities:
        loc = opp.get("location") or "Not Specified"
        location_counts[loc] = location_counts.get(loc, 0) + 1

    # 3. Verification status counts
    verification_counts: Dict[str, int] = {}
    for opp in opportunities:
        v_status = str(opp.get("verification_status") or opp.get("status") or "UNVERIFIED").upper()
        verification_counts[v_status] = verification_counts.get(v_status, 0) + 1

    # 4. Application status counts (Open, Closing Soon, Closed, Rolling / No Deadline)
    app_status_counts: Dict[str, int] = {}
    for opp in opportunities:
        deadline = opp.get("deadline")
        if deadline is None or deadline == "":
            status_label = "Rolling / Ongoing"
        else:
            status_label = opp.get("status") or "Unknown"
        app_status_counts[status_label] = app_status_counts.get(status_label, 0) + 1

    # 5. Unique organizations & source domains
    orgs = {opp.get("organization") for opp in opportunities if opp.get("organization")}
    domains = {extract_domain(opp.get("source_url")) for opp in opportunities if opp.get("source_url")}
    domains.discard("Unknown")

    # 6. Upcoming deadlines (within next 45 days)
    today = datetime.now(timezone.utc).date()
    upcoming: List[Dict[str, Any]] = []

    for opp in opportunities:
        dl = opp.get("deadline")
        if dl:
            if isinstance(dl, datetime):
                dl_date = dl.date()
            elif isinstance(dl, date):
                dl_date = dl
            elif isinstance(dl, str):
                try:
                    dl_date = date.fromisoformat(dl[:10])
                except (ValueError, TypeError):
                    continue
            else:
                continue

            if dl_date >= today:
                days_left = (dl_date - today).days
                upcoming.append({
                    "opportunity_id": opp.get("opportunity_id"),
                    "title": opp.get("title"),
                    "organization": opp.get("organization"),
                    "category": opp.get("category"),
                    "deadline": format_display_date(dl_date),
                    "days_remaining": days_left,
                    "source_url": opp.get("source_url"),
                })

    upcoming.sort(key=lambda x: x["days_remaining"])

    # 7. Verification timestamps
    verification_timestamps: List[datetime] = []
    for opp in opportunities:
        vt = opp.get("verified_at")
        if isinstance(vt, datetime):
            verification_timestamps.append(vt)
        elif isinstance(vt, str):
            try:
                verification_timestamps.append(
                    datetime.fromisoformat(vt.replace("Z", "+00:00"))
                )
            except (ValueError, TypeError):
                pass

    latest_ver = max(verification_timestamps) if verification_timestamps else None
    earliest_ver = min(verification_timestamps) if verification_timestamps else None

    return {
        "total": total,
        "category_counts": category_counts,
        "location_counts": location_counts,
        "verification_counts": verification_counts,
        "application_status_counts": app_status_counts,
        "unique_organizations": len(orgs),
        "unique_domains": len(domains),
        "upcoming_deadlines": upcoming,
        "latest_verification": latest_ver,
        "earliest_verification": earliest_ver,
    }
