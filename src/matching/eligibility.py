"""Evidence-based eligibility assessment engine for OpportunityLens."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from src.matching.models import (
    EligibilityAssessment,
    EligibilityOutcome,
    StudentProfile,
)


def extract_cgpa_threshold(eligibility_text: str) -> Optional[float]:
    """Extract explicit numeric CGPA threshold if mentioned in text (e.g. 3.5/5.0)."""
    # Pattern 1: 3.5 CGPA or 3.5 GPA
    match_before = re.search(
        r"\b([1-4]\.[0-9]{1,2})\s*(?:cgpa|gpa)\b",
        eligibility_text,
        re.IGNORECASE,
    )
    if match_before:
        try:
            return float(match_before.group(1))
        except ValueError:
            pass

    # Pattern 2: CGPA of 3.5, minimum CGPA 3.5
    match_after = re.search(
        r"(?:cgpa|gpa)\s*(?:of|minimum|min|at least)?\s*([1-4]\.[0-9]{1,2})\b",
        eligibility_text,
        re.IGNORECASE,
    )
    if match_after:
        try:
            return float(match_after.group(1))
        except ValueError:
            pass

    # Pattern 3: 3.5 / 5.0
    match_scale = re.search(r"\b([1-4]\.[0-9]{1,2})\s*/\s*5\.0", eligibility_text)
    if match_scale:
        try:
            return float(match_scale.group(1))
        except ValueError:
            pass

    return None


def assess_eligibility(
    profile: StudentProfile, opp_record: Dict[str, Any]
) -> EligibilityAssessment:
    """Assess student eligibility against documented opportunity criteria.

    Strictly applies evidence-based, conservative rules:
    - LIKELY_ELIGIBLE: Explicit requirements compatible, no material uncertainty.
    - POSSIBLY_ELIGIBLE: Compatible, but some requirements remain unverified (e.g. CGPA, department).
    - LIKELY_NOT_ELIGIBLE: Explicit requirement contradicts a known profile attribute.
    - INSUFFICIENT_INFORMATION: Lacks enough stated criteria to evaluate.

    Args:
        profile: The student profile.
        opp_record: Opportunity record dictionary.

    Returns:
        EligibilityAssessment instance with outcome, evidence, and advice.
    """
    eligibility_text = str(opp_record.get("eligibility") or "").strip()
    education_level_text = str(opp_record.get("education_level") or "").strip()

    confirmed_facts: List[str] = []
    unverified_factors: List[str] = []
    disqualifying_factors: List[str] = []

    # Check for empty / placeholder eligibility
    if not eligibility_text or eligibility_text.lower() in (
        "check official source.",
        "check the official source.",
        "n/a",
        "none",
    ):
        return EligibilityAssessment(
            outcome=EligibilityOutcome.INSUFFICIENT_INFORMATION,
            summary="The opportunity listing does not specify detailed eligibility requirements.",
            unverified_factors=["Official eligibility prerequisites not published in record."],
            advice="Please review the official program link directly to inspect full prerequisites.",
        )

    elig_lower = eligibility_text.lower()
    edu_lower = education_level_text.lower()
    prof_edu = profile.education_level.lower()

    # 1. Education Level Audit
    if "all levels" in edu_lower or "all levels" in elig_lower:
        confirmed_facts.append(
            f"Opportunity welcomes all education levels (your level: {profile.education_level})."
        )
    elif "undergraduate" in edu_lower or "undergraduate" in elig_lower:
        if "undergraduate" in prof_edu:
            confirmed_facts.append("Matches required undergraduate status.")
        elif "postgraduate" in prof_edu:
            disqualifying_factors.append(
                f"Program is restricted to undergraduates; you are currently {profile.education_level}."
            )
        elif "secondary" in prof_edu:
            disqualifying_factors.append(
                "Requires university undergraduate matriculation; you are in secondary school."
            )
    elif "postgraduate" in edu_lower or "master" in elig_lower:
        if "postgraduate" in prof_edu:
            confirmed_facts.append("Matches required postgraduate / Master's status.")
        else:
            disqualifying_factors.append(
                f"Requires postgraduate standing; you are {profile.education_level}."
            )
    elif "ond" in edu_lower or "hnd" in edu_lower:
        if "ond" in prof_edu or "hnd" in prof_edu or "graduate" in prof_edu:
            confirmed_facts.append("Matches technical / polytechnic graduate criteria.")
        else:
            unverified_factors.append("Check if university degree is accepted in lieu of OND/HND.")

    # 2. CGPA Threshold Audit (if stated in listing)
    min_cgpa = extract_cgpa_threshold(eligibility_text)
    if min_cgpa is not None:
        if profile.cgpa is not None:
            if profile.cgpa >= min_cgpa:
                confirmed_facts.append(
                    f"Your CGPA ({profile.cgpa}) meets the stated requirement (minimum {min_cgpa})."
                )
            else:
                disqualifying_factors.append(
                    f"Your CGPA ({profile.cgpa}) is below the required minimum of {min_cgpa}."
                )
        else:
            unverified_factors.append(
                f"Program requires a minimum CGPA of {min_cgpa}; your profile does not specify a CGPA."
            )

    # 3. Field of Study / STEM Criteria Audit
    is_stem_req = any(kw in elig_lower for kw in ("stem", "engineering", "computer science", "science"))
    if is_stem_req:
        if profile.field_of_study:
            fos_lower = profile.field_of_study.lower()
            if any(kw in fos_lower for kw in ("computer", "engineering", "tech", "data", "science", "physics", "math")):
                confirmed_facts.append(
                    f"Your major ({profile.field_of_study}) matches the requested STEM discipline."
                )
            else:
                unverified_factors.append(
                    f"Program emphasizes STEM/technical majors; verify if {profile.field_of_study} is eligible."
                )
        else:
            unverified_factors.append(
                "Requires STEM or technical course of study; field of study not specified in your profile."
            )

    # 4. Level-specific academic years (e.g. 200L or 300L)
    if any(lvl in elig_lower for lvl in ("100l", "200l", "300l", "400l", "pre-final")):
        unverified_factors.append(
            "Listing specifies specific academic year standing (e.g. 100L/200L/300L). Verify your current level."
        )

    # 5. Determine Overall Outcome
    if disqualifying_factors:
        outcome = EligibilityOutcome.LIKELY_NOT_ELIGIBLE
        summary = (
            "One or more explicit requirements conflict with your profile attributes."
        )
        advice = "Review disqualifying factors below or check if alternative application tracks exist."
    elif unverified_factors and not confirmed_facts:
        outcome = EligibilityOutcome.INSUFFICIENT_INFORMATION
        summary = "Insufficient profile information to confirm alignment with stated criteria."
        advice = "Complete additional profile details (e.g. CGPA or field of study) to improve assessment."
    elif unverified_factors:
        outcome = EligibilityOutcome.POSSIBLY_ELIGIBLE
        summary = (
            "Your profile matches available criteria, but additional material prerequisites require verification."
        )
        advice = "Verify the unverified criteria on the official source portal before applying."
    else:
        outcome = EligibilityOutcome.LIKELY_ELIGIBLE
        summary = (
            "Your profile meets all explicitly stated eligibility requirements documented in this record."
        )
        advice = "Review application deadlines and prepare your application documents."

    return EligibilityAssessment(
        outcome=outcome,
        summary=summary,
        confirmed_facts=confirmed_facts,
        unverified_factors=unverified_factors,
        disqualifying_factors=disqualifying_factors,
        advice=advice,
    )
