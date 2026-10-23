"""High-level opportunity matching service orchestrating search, scoring, and eligibility."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from src.matching.eligibility import assess_eligibility
from src.matching.models import (
    EligibilityOutcome,
    MatchResult,
    SearchRequest,
    StudentProfile,
)
from src.matching.scorer import rank_opportunities
from src.matching.search import filter_by_search_request, parse_natural_language_query


def match_opportunities(
    profile: StudentProfile,
    opportunities: List[Dict[str, Any]],
    query: Optional[str] = None,
    include_closed: bool = False,
    top_k: int = 10,
) -> Tuple[List[MatchResult], Optional[SearchRequest]]:
    """Match, rank, and evaluate opportunities for a student profile and optional query.

    Args:
        profile: Validated StudentProfile.
        opportunities: List of opportunity records from Snowflake.
        query: Optional free-text natural language query.
        include_closed: Whether to include expired/closed opportunities.
        top_k: Maximum number of top ranked matches to return.

    Returns:
        Tuple of (ranked_match_results, parsed_search_request).
    """
    if not opportunities:
        return [], None

    # Exclude closed opportunities from recommendations unless explicitly requested
    candidate_records = opportunities
    if not include_closed:
        candidate_records = [
            opp for opp in candidate_records if opp.get("status") != "Closed"
        ]

    # Parse and apply natural language search query if provided
    search_req: Optional[SearchRequest] = None
    if query and query.strip():
        search_req = parse_natural_language_query(query.strip())
        candidate_records = filter_by_search_request(candidate_records, search_req)

    if not candidate_records:
        return [], search_req

    # 1. Deterministic scoring and ranking
    ranked_results = rank_opportunities(profile, candidate_records)

    # 2. Evidence-based eligibility assessment for each match
    for result in ranked_results:
        assessment = assess_eligibility(profile, result.opportunity_record)
        result.eligibility = assessment

        # Apply eligibility priority rule:
        # A disqualifying eligibility outcome must never be masked by a high relevance score.
        if assessment.outcome == EligibilityOutcome.LIKELY_NOT_ELIGIBLE:
            result.potential_mismatches.extend(assessment.disqualifying_factors)

    return ranked_results[:top_k], search_req
