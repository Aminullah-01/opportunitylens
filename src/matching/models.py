"""Data models for OpportunityLens student profiles, scoring, and matching."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EligibilityOutcome(str, Enum):
    """Conservative, evidence-based eligibility outcomes."""

    LIKELY_ELIGIBLE = "LIKELY_ELIGIBLE"
    POSSIBLY_ELIGIBLE = "POSSIBLY_ELIGIBLE"
    LIKELY_NOT_ELIGIBLE = "LIKELY_NOT_ELIGIBLE"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"


VALID_EDUCATION_LEVELS = (
    "Undergraduate",
    "Postgraduate",
    "Secondary / O'Level",
    "OND / HND",
    "Recent Graduate / NYSC",
    "All Levels",
    "Other",
)

VALID_DELIVERY_MODES = (
    "unspecified",
    "remote",
    "on-site",
    "hybrid",
)


@dataclass
class StudentProfile:
    """Validated student and early-career profile for opportunity discovery."""

    education_level: str  # Required
    field_of_study: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    location: Optional[str] = None
    preferred_categories: List[str] = field(default_factory=list)
    delivery_mode: str = "unspecified"
    graduation_year: Optional[int] = None
    cgpa: Optional[float] = None
    additional_goals: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to serializable dictionary."""
        return {
            "education_level": self.education_level,
            "field_of_study": self.field_of_study,
            "skills": self.skills,
            "location": self.location,
            "preferred_categories": self.preferred_categories,
            "delivery_mode": self.delivery_mode,
            "graduation_year": self.graduation_year,
            "cgpa": self.cgpa,
            "additional_goals": self.additional_goals,
        }


@dataclass
class SearchRequest:
    """Parsed and validated natural-language search request."""

    query_text: str = ""
    categories: List[str] = field(default_factory=list)
    location: Optional[str] = None
    delivery_mode: Optional[str] = None
    education_level: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    closing_soon_only: bool = False


@dataclass
class EligibilityAssessment:
    """Outcome and documented evidence for an opportunity's eligibility."""

    outcome: EligibilityOutcome
    summary: str
    confirmed_facts: List[str] = field(default_factory=list)
    unverified_factors: List[str] = field(default_factory=list)
    disqualifying_factors: List[str] = field(default_factory=list)
    advice: str = ""

    @property
    def missing_information(self) -> List[str]:
        """Alias for unverified_factors to ensure backward compatibility."""
        return self.unverified_factors

    def to_dict(self) -> Dict[str, Any]:
        """Convert assessment to dictionary."""
        return {
            "outcome": self.outcome.value,
            "summary": self.summary,
            "confirmed_facts": self.confirmed_facts,
            "unverified_factors": self.unverified_factors,
            "disqualifying_factors": self.disqualifying_factors,
            "advice": self.advice,
        }


@dataclass
class MatchScoreBreakdown:
    """Configurable factor-level contributions to the final match score."""

    education_score: float = 0.0
    field_of_study_score: float = 0.0
    skills_score: float = 0.0
    category_score: float = 0.0
    location_score: float = 0.0
    delivery_mode_score: float = 0.0
    total_score: float = 0.0
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """A ranked opportunity match with transparent explanation components."""

    opportunity_id: str
    title: str
    organization: str
    category: str
    match_score: float
    ranked_position: int
    score_breakdown: MatchScoreBreakdown
    matching_factors: List[str] = field(default_factory=list)
    potential_mismatches: List[str] = field(default_factory=list)
    unknown_factors: List[str] = field(default_factory=list)
    eligibility: EligibilityAssessment = field(
        default_factory=lambda: EligibilityAssessment(
            outcome=EligibilityOutcome.INSUFFICIENT_INFORMATION,
            summary="Assessment not performed.",
        )
    )
    application_status: str = "Unknown"
    deadline: Optional[str] = None
    source_url: str = ""
    verified_at: Optional[str] = None
    opportunity_record: Dict[str, Any] = field(default_factory=dict)

    @property
    def location(self) -> str:
        """Derived location from opportunity_record with safe fallback."""
        if self.opportunity_record and self.opportunity_record.get("location"):
            return str(self.opportunity_record["location"])
        return "Nigeria"

    @property
    def education_level(self) -> str:
        """Derived education_level from opportunity_record with safe fallback."""
        if self.opportunity_record and self.opportunity_record.get("education_level"):
            return str(self.opportunity_record["education_level"])
        return "All Levels"

    @property
    def description(self) -> str:
        """Derived description from opportunity_record with safe fallback."""
        if self.opportunity_record and self.opportunity_record.get("description"):
            return str(self.opportunity_record["description"])
        return ""

    @property
    def eligibility_str(self) -> str:
        """Raw eligibility requirements string from opportunity_record."""
        if self.opportunity_record and self.opportunity_record.get("eligibility"):
            return str(self.opportunity_record["eligibility"])
        if self.eligibility and self.eligibility.summary:
            return self.eligibility.summary
        return "Requirements not specified"

    @property
    def verification_status(self) -> str:
        """Verification status from opportunity_record with safe fallback."""
        if self.opportunity_record and self.opportunity_record.get("verification_status"):
            return str(self.opportunity_record["verification_status"])
        return "VERIFIED"
