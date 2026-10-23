"""OpportunityLens matching and eligibility package."""

from src.matching.eligibility import assess_eligibility
from src.matching.models import (
    EligibilityAssessment,
    EligibilityOutcome,
    MatchResult,
    MatchScoreBreakdown,
    SearchRequest,
    StudentProfile,
    VALID_DELIVERY_MODES,
    VALID_EDUCATION_LEVELS,
)
from src.matching.profile import ProfileValidationError, validate_profile
from src.matching.scorer import rank_opportunities, score_opportunity
from src.matching.search import filter_by_search_request, parse_natural_language_query
from src.matching.service import match_opportunities

__all__ = [
    "EligibilityAssessment",
    "EligibilityOutcome",
    "MatchResult",
    "MatchScoreBreakdown",
    "SearchRequest",
    "StudentProfile",
    "VALID_DELIVERY_MODES",
    "VALID_EDUCATION_LEVELS",
    "ProfileValidationError",
    "validate_profile",
    "rank_opportunities",
    "score_opportunity",
    "assess_eligibility",
    "filter_by_search_request",
    "parse_natural_language_query",
    "match_opportunities",
]
