"""Unit tests for StudentProfile validation and normalization."""

from __future__ import annotations

import pytest

from src.matching.models import StudentProfile, VALID_DELIVERY_MODES, VALID_EDUCATION_LEVELS
from src.matching.profile import (
    ProfileValidationError,
    normalize_skills,
    normalize_text,
    validate_profile,
)


def test_valid_profile_creation():
    """Verify that a valid profile is instantiated with correct attributes."""
    profile = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        skills="Python, SQL, Git",
        location="Gombe",
        preferred_categories=["Scholarships", "Internships"],
        delivery_mode="remote",
        graduation_year=2026,
        cgpa=3.75,
        additional_goals="Seeking AI internships",
    )
    assert profile.education_level == "Undergraduate"
    assert profile.field_of_study == "Computer Science"
    assert profile.skills == ["Python", "SQL", "Git"]
    assert profile.location == "Gombe"
    assert profile.preferred_categories == ["Scholarships", "Internships"]
    assert profile.delivery_mode == "remote"
    assert profile.graduation_year == 2026
    assert profile.cgpa == 3.75
    assert profile.additional_goals == "Seeking AI internships"


def test_education_level_required():
    """Verify that empty or missing education_level raises ProfileValidationError."""
    with pytest.raises(ProfileValidationError, match="Education level is required"):
        validate_profile(education_level="")

    with pytest.raises(ProfileValidationError, match="Education level is required"):
        validate_profile(education_level="   ")

    with pytest.raises(ProfileValidationError, match="Invalid education level"):
        validate_profile(education_level="Astronaut Training")


def test_education_level_case_insensitivity():
    """Verify that case variations in education level normalize to valid options."""
    profile = validate_profile(education_level="undergraduate")
    assert profile.education_level == "Undergraduate"

    profile2 = validate_profile(education_level="postgraduate")
    assert profile2.education_level == "Postgraduate"


def test_cgpa_validation():
    """Verify bounds and string parsing for CGPA."""
    # Valid numeric string
    p1 = validate_profile(education_level="Undergraduate", cgpa="4.15")
    assert p1.cgpa == 4.15

    # Out of upper bounds (> 5.0)
    with pytest.raises(ProfileValidationError, match=r"CGPA.*must be between 0\.0 and 5\.0"):
        validate_profile(education_level="Undergraduate", cgpa=5.5)

    # Out of lower bounds (< 0.0)
    with pytest.raises(ProfileValidationError, match=r"CGPA.*must be between 0\.0 and 5\.0"):
        validate_profile(education_level="Undergraduate", cgpa=-0.5)

    # Non-numeric
    with pytest.raises(ProfileValidationError, match="CGPA must be a valid number"):
        validate_profile(education_level="Undergraduate", cgpa="first-class")


def test_graduation_year_validation():
    """Verify bounds and string parsing for graduation year."""
    # Valid string year
    p1 = validate_profile(education_level="Undergraduate", graduation_year="2027")
    assert p1.graduation_year == 2027

    # Year too early (< 1980)
    with pytest.raises(ProfileValidationError, match=r"Graduation year.*must be between 1980 and 2100"):
        validate_profile(education_level="Undergraduate", graduation_year=1975)

    # Year too far in future (> 2100)
    with pytest.raises(ProfileValidationError, match=r"Graduation year.*must be between 1980 and 2100"):
        validate_profile(education_level="Undergraduate", graduation_year=2150)

    # Invalid string
    with pytest.raises(ProfileValidationError, match="Graduation year must be a valid 4-digit integer"):
        validate_profile(education_level="Undergraduate", graduation_year="soon")


def test_skills_normalization():
    """Verify skill token stripping, deduplication, and bounds."""
    # Comma-separated string with mixed case and duplicates
    skills = normalize_skills(" Python , sql, PYTHON, Machine Learning,   , sql ")
    assert skills == ["Python", "sql", "Machine Learning"]

    # List of skills
    skills_list = normalize_skills(["React", "FastAPI", "react", "Docker"])
    assert skills_list == ["React", "FastAPI", "Docker"]

    # Max 20 skills capping
    many_skills = [f"Skill{i}" for i in range(30)]
    capped = normalize_skills(many_skills)
    assert len(capped) == 20
    assert capped[0] == "Skill0"
    assert capped[19] == "Skill19"


def test_delivery_mode_validation():
    """Verify delivery mode validation and casing normalization."""
    p_remote = validate_profile(education_level="Undergraduate", delivery_mode="REMOTE")
    assert p_remote.delivery_mode == "remote"

    p_hybrid = validate_profile(education_level="Undergraduate", delivery_mode="Hybrid")
    assert p_hybrid.delivery_mode == "hybrid"

    p_unspecified = validate_profile(education_level="Undergraduate", delivery_mode=None)
    assert p_unspecified.delivery_mode == "unspecified"

    with pytest.raises(ProfileValidationError, match="Invalid delivery mode"):
        validate_profile(education_level="Undergraduate", delivery_mode="teleport")


def test_field_and_text_length_limits():
    """Verify that excessively long fields are rejected with ProfileValidationError."""
    too_long = "a" * 150
    with pytest.raises(ProfileValidationError, match=r"Field of study cannot exceed 128"):
        validate_profile(education_level="Undergraduate", field_of_study=too_long)

    with pytest.raises(ProfileValidationError, match=r"Location cannot exceed 128"):
        validate_profile(education_level="Undergraduate", location=too_long)

    too_long_goals = "g" * 550
    with pytest.raises(ProfileValidationError, match=r"Additional goals cannot exceed 500"):
        validate_profile(education_level="Undergraduate", additional_goals=too_long_goals)
