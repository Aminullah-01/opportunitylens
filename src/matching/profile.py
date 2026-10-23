"""Student profile creation, validation, and normalization."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.ingestion.models import CANONICAL_CATEGORIES
from src.matching.models import (
    StudentProfile,
    VALID_DELIVERY_MODES,
    VALID_EDUCATION_LEVELS,
)


class ProfileValidationError(ValueError):
    """Raised when profile validation constraints fail."""


def normalize_text(text: Optional[str]) -> Optional[str]:
    """Clean and strip text, returning None if empty."""
    if text is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    return cleaned if cleaned else None


def normalize_skills(skills_input: Any) -> List[str]:
    """Normalize skill tokens from a list or comma-separated string."""
    if not skills_input:
        return []

    tokens: List[str] = []
    if isinstance(skills_input, str):
        parts = skills_input.split(",")
        tokens = [p.strip() for p in parts if p.strip()]
    elif isinstance(skills_input, (list, tuple, set)):
        for item in skills_input:
            if item and isinstance(item, str):
                cleaned = item.strip()
                if cleaned:
                    tokens.append(cleaned)

    # Deduplicate while preserving order and limit to 20 skills
    seen = set()
    unique_skills = []
    for s in tokens:
        sl = s.lower()
        if sl not in seen and len(s) <= 64:
            seen.add(sl)
            unique_skills.append(s)
            if len(unique_skills) >= 20:
                break

    return unique_skills


def validate_profile(
    education_level: str,
    field_of_study: Optional[str] = None,
    skills: Any = None,
    location: Optional[str] = None,
    preferred_categories: Optional[List[str]] = None,
    delivery_mode: str = "unspecified",
    graduation_year: Optional[Any] = None,
    cgpa: Optional[Any] = None,
    additional_goals: Optional[str] = None,
) -> StudentProfile:
    """Validate and build a StudentProfile instance.

    Args:
        education_level: Current educational standing (Required).
        field_of_study: Academic discipline or major (Optional).
        skills: List or comma-separated list of technical/academic skills (Optional).
        location: City, state, or region (Optional).
        preferred_categories: Desired opportunity categories (Optional).
        delivery_mode: 'remote', 'on-site', 'hybrid', or 'unspecified'.
        graduation_year: Projected or past graduation year (Optional).
        cgpa: Cumulative Grade Point Average on 5.0 scale (Optional).
        additional_goals: Specific career objectives (Optional).

    Returns:
        Validated StudentProfile instance.

    Raises:
        ProfileValidationError: If any constraint is violated.
    """
    # 1. Validate required education_level
    clean_edu = normalize_text(education_level)
    if not clean_edu:
        raise ProfileValidationError(
            "Education level is required for personalized opportunity matching."
        )

    matched_level: Optional[str] = None
    for lvl in VALID_EDUCATION_LEVELS:
        if clean_edu.lower() == lvl.lower():
            matched_level = lvl
            break
    if not matched_level:
        raise ProfileValidationError(
            f"Invalid education level '{clean_edu}'. Must be one of: {', '.join(VALID_EDUCATION_LEVELS)}."
        )
    clean_edu = matched_level

    # 2. Field of study
    clean_fos = normalize_text(field_of_study)
    if clean_fos and len(clean_fos) > 128:
        raise ProfileValidationError("Field of study cannot exceed 128 characters.")

    # 3. Location
    clean_loc = normalize_text(location)
    if clean_loc and len(clean_loc) > 128:
        raise ProfileValidationError("Location cannot exceed 128 characters.")

    # 4. Delivery mode
    clean_mode = str(delivery_mode).strip().lower() if delivery_mode else "unspecified"
    if clean_mode not in VALID_DELIVERY_MODES:
        raise ProfileValidationError(
            f"Invalid delivery mode '{delivery_mode}'. Must be one of: {', '.join(VALID_DELIVERY_MODES)}."
        )

    # 5. Preferred categories
    valid_categories: List[str] = []
    if preferred_categories:
        for cat in preferred_categories:
            if cat in CANONICAL_CATEGORIES and cat not in valid_categories:
                valid_categories.append(cat)

    # 6. Graduation year
    parsed_year: Optional[int] = None
    if graduation_year is not None and str(graduation_year).strip():
        try:
            parsed_year = int(graduation_year)
        except (ValueError, TypeError):
            raise ProfileValidationError("Graduation year must be a valid 4-digit integer.")

        if parsed_year < 1980 or parsed_year > 2100:
            raise ProfileValidationError(
                f"Graduation year ({parsed_year}) must be between 1980 and 2100."
            )

    # 7. CGPA
    parsed_cgpa: Optional[float] = None
    if cgpa is not None and str(cgpa).strip():
        try:
            parsed_cgpa = float(cgpa)
        except (ValueError, TypeError):
            raise ProfileValidationError("CGPA must be a valid number between 0.0 and 5.0.")

        if parsed_cgpa < 0.0 or parsed_cgpa > 5.0:
            raise ProfileValidationError(
                f"CGPA ({parsed_cgpa}) must be between 0.0 and 5.0."
            )

    # 8. Additional goals
    clean_goals = normalize_text(additional_goals)
    if clean_goals and len(clean_goals) > 500:
        raise ProfileValidationError("Additional goals cannot exceed 500 characters.")

    # 9. Skills
    parsed_skills = normalize_skills(skills)

    return StudentProfile(
        education_level=clean_edu,
        field_of_study=clean_fos,
        skills=parsed_skills,
        location=clean_loc,
        preferred_categories=valid_categories,
        delivery_mode=clean_mode,
        graduation_year=parsed_year,
        cgpa=parsed_cgpa,
        additional_goals=clean_goals,
    )
