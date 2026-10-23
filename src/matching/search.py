"""Natural-language query parser and search filter engine for OpportunityLens."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.ingestion.models import CANONICAL_CATEGORIES
from src.matching.models import SearchRequest


CATEGORY_INTENT_MAP = {
    "scholarship": "Scholarships",
    "scholarships": "Scholarships",
    "grant": "Scholarships",
    "grants": "Scholarships",
    "fellowship": "Scholarships",
    "internship": "Internships",
    "internships": "Internships",
    "intern": "Internships",
    "training": "Tech Training",
    "bootcamp": "Tech Training",
    "course": "Tech Training",
    "courses": "Tech Training",
    "hackathon": "Hackathons",
    "hackathons": "Hackathons",
    "challenge": "Hackathons",
    "job": "Entry-Level Jobs",
    "jobs": "Entry-Level Jobs",
    "trainee": "Entry-Level Jobs",
    "entry-level": "Entry-Level Jobs",
}

LOCATION_KEYWORDS = (
    "lagos",
    "gombe",
    "abuja",
    "northern nigeria",
    "kaduna",
    "kano",
    "ibadan",
    "enugu",
    "nationwide",
)

EDUCATION_INTENT_MAP = {
    "undergraduate": "Undergraduate",
    "undergrad": "Undergraduate",
    "bachelor": "Undergraduate",
    "postgraduate": "Postgraduate",
    "masters": "Postgraduate",
    "msc": "Postgraduate",
    "phd": "Postgraduate",
    "ond": "OND / HND",
    "hnd": "OND / HND",
    "polytechnic": "OND / HND",
    "graduate": "Recent Graduate / NYSC",
    "graduates": "Recent Graduate / NYSC",
    "nysc": "Recent Graduate / NYSC",
    "secondary": "Secondary / O'Level",
}


def parse_natural_language_query(query: str) -> SearchRequest:
    """Parse user natural language query into a structured SearchRequest.

    Deterministic rule-based intent parsing: extracts categories, education levels,
    delivery modes, locations, deadline intent, and search keywords.

    Args:
        query: Free-text user question or prompt.

    Returns:
        Structured SearchRequest.
    """
    if not query or not isinstance(query, str):
        return SearchRequest(query_text="")

    q_lower = query.strip().lower()

    # 1. Detect categories
    detected_categories: List[str] = []
    for term, cat in CATEGORY_INTENT_MAP.items():
        if re.search(r"\b" + re.escape(term) + r"\b", q_lower):
            if cat not in detected_categories:
                detected_categories.append(cat)

    # 2. Detect education levels
    detected_edu: Optional[str] = None
    for term, edu in EDUCATION_INTENT_MAP.items():
        if re.search(r"\b" + re.escape(term) + r"\b", q_lower):
            detected_edu = edu
            break

    # 3. Detect delivery mode
    detected_mode: Optional[str] = None
    if re.search(r"\b(remote|virtual|online|work from home)\b", q_lower):
        detected_mode = "remote"
    elif re.search(r"\b(hybrid)\b", q_lower):
        detected_mode = "hybrid"
    elif re.search(r"\b(in-person|on-site|onsite|physical)\b", q_lower):
        detected_mode = "on-site"

    # 4. Detect location
    detected_loc: Optional[str] = None
    for loc in LOCATION_KEYWORDS:
        if re.search(r"\b" + re.escape(loc) + r"\b", q_lower):
            detected_loc = loc.title()
            break

    # 5. Detect deadline urgency
    closing_soon = bool(
        re.search(
            r"\b(closing soon|closing|upcoming deadline|urgent|soon|ending soon)\b",
            q_lower,
        )
    )

    # 6. Extract meaningful keyword tokens (filtering common stop words)
    stop_words = {
        "find",
        "show",
        "me",
        "search",
        "which",
        "for",
        "in",
        "at",
        "with",
        "and",
        "or",
        "to",
        "a",
        "an",
        "the",
        "opportunities",
        "opportunity",
        "programs",
        "program",
        "nigeria",
        "nigerian",
        "students",
        "student",
        "what",
        "is",
        "are",
        "can",
        "i",
        "my",
        "check",
        "get",
    }
    raw_tokens = re.findall(r"\b[a-zA-Z0-9+#.-]{2,}\b", q_lower)
    keywords = [
        t
        for t in raw_tokens
        if t not in stop_words
        and t not in CATEGORY_INTENT_MAP
        and t not in EDUCATION_INTENT_MAP
    ]

    return SearchRequest(
        query_text=query.strip(),
        categories=detected_categories,
        location=detected_loc,
        delivery_mode=detected_mode,
        education_level=detected_edu,
        keywords=keywords,
        closing_soon_only=closing_soon,
    )


def filter_by_search_request(
    opportunities: List[Dict[str, Any]], request: SearchRequest
) -> List[Dict[str, Any]]:
    """Filter opportunity records using parsed SearchRequest constraints.

    Args:
        opportunities: List of opportunity records.
        request: Parsed SearchRequest.

    Returns:
        Filtered list of opportunity dictionaries.
    """
    filtered = opportunities

    # 1. Filter by detected categories (OR logic across matched categories)
    if request.categories:
        filtered = [
            opp for opp in filtered if opp.get("category") in request.categories
        ]

    # 2. Filter by closing soon / application status
    if request.closing_soon_only:
        filtered = [
            opp
            for opp in filtered
            if opp.get("status") in ("Closing Soon", "Open")
        ]

    # 3. Filter by delivery mode if remote explicitly requested
    if request.delivery_mode == "remote":
        filtered = [
            opp
            for opp in filtered
            if any(
                kw in f"{opp.get('location', '')} {opp.get('description', '')}".lower()
                for kw in ("remote", "virtual", "online", "nationwide")
            )
        ]

    # 4. Filter by location if specific state requested
    if request.location and request.location.lower() != "nationwide":
        loc_term = request.location.lower()
        filtered = [
            opp
            for opp in filtered
            if loc_term in str(opp.get("location", "")).lower()
            or "nationwide" in str(opp.get("location", "")).lower()
            or "remote" in str(opp.get("location", "")).lower()
        ]

    # 5. Filter by keywords if provided
    if request.keywords:
        matching = []
        for opp in filtered:
            full_text = (
                f"{opp.get('title', '')} {opp.get('description', '')} "
                f"{opp.get('organization', '')} {opp.get('eligibility', '')}"
            ).lower()
            # If any keyword matches
            if any(kw in full_text for kw in request.keywords):
                matching.append(opp)
        if matching:
            filtered = matching

    return filtered
