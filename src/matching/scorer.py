"""Deterministic scoring and ranking engine for OpportunityLens."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.matching.models import (
    MatchResult,
    MatchScoreBreakdown,
    StudentProfile,
)

# Configurable matching weights (must sum to 1.0)
WEIGHT_EDUCATION = 0.25
WEIGHT_FIELD_OF_STUDY = 0.20
WEIGHT_SKILLS = 0.20
WEIGHT_CATEGORY = 0.15
WEIGHT_LOCATION = 0.10
WEIGHT_DELIVERY_MODE = 0.10

STEM_KEYWORDS = {
    "computer science",
    "software",
    "engineering",
    "technology",
    "computing",
    "data",
    "stem",
    "information technology",
    "cybersecurity",
    "cloud",
    "ai",
    "artificial intelligence",
    "petroleum",
    "electrical",
    "mechanical",
}


def evaluate_education_compatibility(
    profile_level: str, opp_level: Optional[str], opp_eligibility: Optional[str]
) -> Tuple[float, Optional[str], Optional[str]]:
    """Evaluate education level compatibility.

    Returns:
        Tuple of (subscore_0_to_1, match_note, mismatch_note).
    """
    clean_prof = profile_level.strip().lower()
    clean_opp = (opp_level or "").strip().lower()
    clean_elig = (opp_eligibility or "").strip().lower()

    if not clean_opp or clean_opp in ("not specified", "all levels"):
        return 0.8, "Open to all educational standings", None

    if clean_prof in clean_opp:
        return 1.0, f"Matches your education level ({profile_level})", None

    # Explicit conflicts take precedence
    if "undergraduate" in clean_prof and "postgraduate" in clean_opp and "undergraduate" not in clean_opp:
        return 0.0, None, f"Intended for postgraduates; you are {profile_level}"

    if "postgraduate" in clean_prof and "undergraduate" in clean_opp and "postgraduate" not in clean_opp:
        return 0.0, None, f"Intended for undergraduates; you are {profile_level}"

    # Partial overlaps: Undergraduate vs 100L/200L/300L
    if "undergraduate" in clean_prof and (
        "undergraduate" in clean_opp
        or "undergraduate" in clean_elig
        or "100l" in clean_elig
        or "200l" in clean_elig
        or "300l" in clean_elig
    ):
        return 1.0, "Matches undergraduate academic standing", None

    # OND / HND matching
    if ("ond" in clean_prof or "hnd" in clean_prof) and (
        "ond" in clean_opp or "hnd" in clean_opp or "polytechnic" in clean_elig
    ):
        return 1.0, "Matches polytechnic / OND / HND qualification", None

    # Recent Graduate / NYSC
    if ("recent graduate" in clean_prof or "nysc" in clean_prof) and (
        "recent graduate" in clean_opp or "nysc" in clean_elig or "graduate" in clean_opp
    ):
        return 1.0, "Matches graduate standing", None

    return 0.3, None, f"Target level is {opp_level}"


def evaluate_field_of_study(
    profile_fos: Optional[str], opp_record: Dict[str, Any]
) -> Tuple[float, Optional[str], Optional[str]]:
    """Evaluate field of study relevance against opportunity record."""
    if not profile_fos:
        return 0.5, None, None  # Neutral when unspecified

    clean_fos = profile_fos.strip().lower()
    full_text = (
        f"{opp_record.get('title', '')} {opp_record.get('description', '')} "
        f"{opp_record.get('eligibility', '')} {opp_record.get('category', '')}"
    ).lower()

    # Exact or substring match of field of study
    if clean_fos in full_text:
        return 1.0, f"Directly aligns with {profile_fos}", None

    # STEM discipline cross-matching
    is_profile_stem = any(kw in clean_fos for kw in STEM_KEYWORDS)
    is_opp_stem = any(kw in full_text for kw in STEM_KEYWORDS)

    if is_profile_stem and is_opp_stem:
        return 0.9, f"Aligns with STEM discipline ({profile_fos})", None

    # General opportunity
    if "all disciplines" in full_text or "all courses" in full_text or "any field" in full_text:
        return 0.7, "Open to all disciplines", None

    return 0.2, None, f"No direct mention of {profile_fos}"


def evaluate_skills(
    profile_skills: List[str], opp_record: Dict[str, Any]
) -> Tuple[float, Optional[str], List[str]]:
    """Evaluate skills overlap against opportunity title and description."""
    if not profile_skills:
        return 0.5, None, []  # Neutral when unspecified

    full_text = (
        f"{opp_record.get('title', '')} {opp_record.get('description', '')} "
        f"{opp_record.get('eligibility', '')}"
    ).lower()

    matched_skills = [
        s for s in profile_skills if re.search(r"\b" + re.escape(s.lower()) + r"\b", full_text)
    ]

    if len(matched_skills) >= 2:
        return 1.0, f"Matches your skills: {', '.join(matched_skills[:3])}", matched_skills
    elif len(matched_skills) == 1:
        return 0.75, f"Matches skill: {matched_skills[0]}", matched_skills

    # Check if opportunity requires technical skills at all
    opp_has_tech = any(kw in full_text for kw in STEM_KEYWORDS)
    if not opp_has_tech:
        return 0.6, None, []  # General program not requiring specific technical skills

    return 0.2, None, []


def evaluate_category(
    preferred_categories: List[str], opp_category: str
) -> Tuple[float, Optional[str]]:
    """Evaluate match with student's preferred opportunity categories."""
    if not preferred_categories:
        return 0.6, None  # Neutral when student has no preference

    if opp_category in preferred_categories:
        return 1.0, f"Matches preferred category ({opp_category})"

    return 0.2, None


def evaluate_location(
    profile_loc: Optional[str], opp_location: Optional[str]
) -> Tuple[float, Optional[str], Optional[str]]:
    """Evaluate location compatibility."""
    clean_opp_loc = (opp_location or "Nationwide").strip().lower()

    # Nationwide or remote is compatible with any student location
    if any(kw in clean_opp_loc for kw in ("nationwide", "remote", "online", "all 36 states")):
        return 1.0, "Nationwide or remote availability", None

    if not profile_loc:
        return 0.6, None, None

    clean_prof_loc = profile_loc.strip().lower()

    # Exact or substring match (e.g. Lagos, Gombe, Abuja, Northern Nigeria)
    if clean_prof_loc in clean_opp_loc or clean_opp_loc in clean_prof_loc:
        return 1.0, f"Located in {profile_loc}", None

    # Regional matching: Gombe / Northern Nigeria
    northern_states = {"gombe", "kaduna", "kano", "bauchi", "adamawa", "borno", "northern nigeria"}
    if clean_prof_loc in northern_states and any(ns in clean_opp_loc for ns in northern_states):
        return 0.85, "Regional northern Nigeria availability", None

    return 0.3, None, f"Opportunity located in {opp_location}"


def evaluate_delivery_mode(
    profile_mode: str, opp_record: Dict[str, Any]
) -> Tuple[float, Optional[str]]:
    """Evaluate delivery mode compatibility (remote, on-site, hybrid)."""
    if profile_mode == "unspecified":
        return 0.7, None

    full_text = (
        f"{opp_record.get('location', '')} {opp_record.get('description', '')}"
    ).lower()

    is_remote = "remote" in full_text or "virtual" in full_text
    is_hybrid = "hybrid" in full_text
    is_onsite = not is_remote and ("in-person" in full_text or "lagos" in full_text or "gombe" in full_text)

    if profile_mode == "remote":
        if is_remote or is_hybrid:
            return 1.0, "Offers remote or hybrid participation"
        return 0.2, None

    if profile_mode in ("on-site", "hybrid"):
        if is_hybrid or is_onsite or not is_remote:
            return 1.0, "Offers in-person / on-site engagement"
        return 0.4, None

    return 0.5, None


def score_opportunity(
    profile: StudentProfile, opp_record: Dict[str, Any]
) -> MatchResult:
    """Calculate deterministic match score and explanatory factors for an opportunity.

    Args:
        profile: Student profile.
        opp_record: Raw or normalized opportunity dictionary.

    Returns:
        MatchResult populated with scores, factor contributions, and metadata.
    """
    matching_factors: List[str] = []
    potential_mismatches: List[str] = []
    unknown_factors: List[str] = []

    # 1. Education
    edu_score, edu_match, edu_mismatch = evaluate_education_compatibility(
        profile.education_level,
        opp_record.get("education_level"),
        opp_record.get("eligibility"),
    )
    if edu_match:
        matching_factors.append(edu_match)
    if edu_mismatch:
        potential_mismatches.append(edu_mismatch)

    # 2. Field of study
    fos_score, fos_match, fos_mismatch = evaluate_field_of_study(
        profile.field_of_study, opp_record
    )
    if fos_match:
        matching_factors.append(fos_match)
    if fos_mismatch:
        potential_mismatches.append(fos_mismatch)
    if not profile.field_of_study:
        unknown_factors.append("Field of study not specified in profile")

    # 3. Skills
    skills_score, skills_match, matched_skills_list = evaluate_skills(
        profile.skills, opp_record
    )
    if skills_match:
        matching_factors.append(skills_match)
    if not profile.skills:
        unknown_factors.append("Skills not specified in profile")

    # Compute missing/target skills if any STEM keywords exist in opportunity
    opp_text = f"{opp_record.get('title', '')} {opp_record.get('description', '')} {opp_record.get('eligibility', '')}".lower()
    profile_skills_lower = {s.lower() for s in profile.skills}
    missing_skills_list = [
        kw.title()
        for kw in sorted(STEM_KEYWORDS)
        if kw in opp_text and kw not in profile_skills_lower and kw not in {m.lower() for m in matched_skills_list}
    ][:3]

    # 4. Category
    cat_score, cat_match = evaluate_category(
        profile.preferred_categories, opp_record.get("category", "")
    )
    if cat_match:
        matching_factors.append(cat_match)

    # 5. Location
    loc_score, loc_match, loc_mismatch = evaluate_location(
        profile.location, opp_record.get("location")
    )
    if loc_match:
        matching_factors.append(loc_match)
    if loc_mismatch:
        potential_mismatches.append(loc_mismatch)

    # 6. Delivery mode
    dm_score, dm_match = evaluate_delivery_mode(
        profile.delivery_mode, opp_record
    )
    if dm_match:
        matching_factors.append(dm_match)

    # Weighted calculation normalized to 0-100 scale
    total = (
        (edu_score * WEIGHT_EDUCATION)
        + (fos_score * WEIGHT_FIELD_OF_STUDY)
        + (skills_score * WEIGHT_SKILLS)
        + (cat_score * WEIGHT_CATEGORY)
        + (loc_score * WEIGHT_LOCATION)
        + (dm_score * WEIGHT_DELIVERY_MODE)
    ) * 100.0

    normalized_total = round(max(0.0, min(100.0, total)), 1)

    breakdown = MatchScoreBreakdown(
        education_score=round(edu_score * 100, 1),
        field_of_study_score=round(fos_score * 100, 1),
        skills_score=round(skills_score * 100, 1),
        category_score=round(cat_score * 100, 1),
        location_score=round(loc_score * 100, 1),
        delivery_mode_score=round(dm_score * 100, 1),
        total_score=normalized_total,
        matched_skills=matched_skills_list,
        missing_skills=missing_skills_list,
    )

    opp_id = str(opp_record.get("opportunity_id", "N/A"))
    title = str(opp_record.get("title", "Untitled Opportunity"))
    org = str(opp_record.get("organization", "Not specified"))
    cat = str(opp_record.get("category", "Other"))

    return MatchResult(
        opportunity_id=opp_id,
        title=title,
        organization=org,
        category=cat,
        match_score=normalized_total,
        ranked_position=1,
        score_breakdown=breakdown,
        matching_factors=matching_factors,
        potential_mismatches=potential_mismatches,
        unknown_factors=unknown_factors,
        application_status=str(opp_record.get("status", "Unknown")),
        deadline=str(opp_record.get("deadline")) if opp_record.get("deadline") else None,
        source_url=str(opp_record.get("source_url", "")),
        verified_at=str(opp_record.get("verified_at")) if opp_record.get("verified_at") else None,
        opportunity_record=opp_record,
    )


def rank_opportunities(
    profile: StudentProfile, opportunities: List[Dict[str, Any]]
) -> List[MatchResult]:
    """Score and rank a list of opportunities for a given student profile.

    Stable tie-breaking by match_score DESC, then title ASC, then opportunity_id ASC.

    Args:
        profile: Student profile.
        opportunities: List of opportunity dictionaries.

    Returns:
        Sorted list of MatchResult objects with assigned ranked_position.
    """
    scored = [score_opportunity(profile, opp) for opp in opportunities]

    # Stable sort: score desc, title asc, id asc
    scored.sort(
        key=lambda m: (-m.match_score, m.title.lower(), m.opportunity_id)
    )

    for idx, match in enumerate(scored, start=1):
        match.ranked_position = idx

    return scored
