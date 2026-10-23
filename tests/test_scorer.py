"""Unit tests for the deterministic scoring engine."""

from __future__ import annotations

import pytest

from src.matching.models import MatchScoreBreakdown, StudentProfile
from src.matching.profile import validate_profile
from src.matching.scorer import (
    WEIGHT_CATEGORY,
    WEIGHT_DELIVERY_MODE,
    WEIGHT_EDUCATION,
    WEIGHT_FIELD_OF_STUDY,
    WEIGHT_LOCATION,
    WEIGHT_SKILLS,
    rank_opportunities,
    score_opportunity,
)


@pytest.fixture
def base_profile() -> StudentProfile:
    """Fixture providing a standard Nigerian student profile."""
    return validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        skills=["Python", "SQL", "Git"],
        location="Gombe",
        preferred_categories=["Scholarships", "Internships"],
        delivery_mode="remote",
        graduation_year=2026,
        cgpa=3.8,
    )


@pytest.fixture
def perfect_match_opportunity() -> dict:
    """Fixture providing an opportunity that aligns with base_profile on all factors."""
    return {
        "opportunity_id": "opp-perfect-01",
        "title": "Gombe STEM Undergraduate Internship",
        "category": "Internships",
        "organization": "Gombe State Ministry of Science & Tech",
        "description": "Remote internship for computer science students skilled in Python, SQL, and Git.",
        "eligibility": "Undergraduate students in Computer Science or IT. Minimum CGPA 3.5.",
        "education_level": "Undergraduate",
        "location": "Gombe, Nigeria (Remote)",
        "deadline": "2026-11-30",
        "source_url": "https://gombe.gov.ng/stem-internship",
        "verified_at": "2026-10-15",
        "status": "Open",
    }


def test_score_weights_sum_to_one():
    """Verify that all scoring factor weights sum exactly to 1.0."""
    total_weight = (
        WEIGHT_EDUCATION
        + WEIGHT_FIELD_OF_STUDY
        + WEIGHT_SKILLS
        + WEIGHT_CATEGORY
        + WEIGHT_LOCATION
        + WEIGHT_DELIVERY_MODE
    )
    assert round(total_weight, 4) == 1.0
    assert WEIGHT_EDUCATION == 0.25
    assert WEIGHT_FIELD_OF_STUDY == 0.20
    assert WEIGHT_SKILLS == 0.20
    assert WEIGHT_CATEGORY == 0.15
    assert WEIGHT_LOCATION == 0.10
    assert WEIGHT_DELIVERY_MODE == 0.10


def test_deterministic_scoring_reproducibility(base_profile, perfect_match_opportunity):
    """Verify that multiple score calculations on identical inputs yield exact same results."""
    res1 = score_opportunity(base_profile, perfect_match_opportunity)
    res2 = score_opportunity(base_profile, perfect_match_opportunity)

    assert res1.match_score == res2.match_score
    assert res1.score_breakdown == res2.score_breakdown
    assert res1.matching_factors == res2.matching_factors
    assert res1.match_score >= 80.0  # Strong match across criteria


def test_score_bounds_always_0_to_100(base_profile):
    """Verify that calculated scores are always within [0.0, 100.0]."""
    empty_opp = {
        "opportunity_id": "opp-empty-00",
        "title": "Unrelated Opportunity",
        "category": "Other",
        "organization": "Unknown",
        "description": "",
        "eligibility": "",
        "education_level": "None",
        "location": "Other",
        "deadline": None,
        "source_url": None,
        "verified_at": None,
        "status": "Closed",
    }
    res_low = score_opportunity(base_profile, empty_opp)
    assert 0.0 <= res_low.match_score <= 100.0

    opp_all = {
        "opportunity_id": "opp-all-levels",
        "title": "All Welcome Opportunity",
        "category": "Scholarships",
        "organization": "Global Org",
        "description": "Python, SQL, Git",
        "eligibility": "All Levels welcome in Computer Science",
        "education_level": "All Levels",
        "location": "Gombe",
        "deadline": "2026-12-01",
        "source_url": "https://example.com",
        "verified_at": "2026-10-01",
        "status": "Open",
    }
    res_high = score_opportunity(base_profile, opp_all)
    assert 0.0 <= res_high.match_score <= 100.0


def test_education_factor_scoring(base_profile):
    """Verify education level matching scores."""
    # Exact match: Undergraduate -> Undergraduate (100% of education weight)
    opp_exact = {
        "opportunity_id": "opp-edu-1",
        "title": "Undergraduate Scholarship",
        "category": "Scholarships",
        "education_level": "Undergraduate",
        "location": "Other",
        "description": "",
        "eligibility": "",
    }
    res_exact = score_opportunity(base_profile, opp_exact)
    assert res_exact.score_breakdown.education_score == 100.0

    # Universal match: All Levels (80% of education weight)
    opp_all = {
        "opportunity_id": "opp-edu-2",
        "title": "Universal Training",
        "category": "Tech Training",
        "education_level": "All Levels",
        "location": "Other",
        "description": "",
        "eligibility": "",
    }
    res_all = score_opportunity(base_profile, opp_all)
    assert res_all.score_breakdown.education_score == 80.0

    # Mismatch: Postgraduate (0%)
    opp_mismatch = {
        "opportunity_id": "opp-edu-3",
        "title": "PhD Fellowship",
        "category": "Scholarships",
        "education_level": "Postgraduate",
        "location": "Other",
        "description": "",
        "eligibility": "",
    }
    res_mismatch = score_opportunity(base_profile, opp_mismatch)
    assert res_mismatch.score_breakdown.education_score == 0.0


def test_skills_matching_proportional_score(base_profile):
    """Verify skills scoring awards points proportional to matched skills."""
    opp_two_skills = {
        "opportunity_id": "opp-skill-2",
        "title": "Python & SQL Developer",
        "category": "Internships",
        "education_level": "Undergraduate",
        "description": "We are seeking Python developers with SQL knowledge.",
        "eligibility": "",
        "location": "Other",
    }
    res = score_opportunity(base_profile, opp_two_skills)
    assert res.score_breakdown.skills_score > 0.0
    assert "Python" in res.score_breakdown.matched_skills
    assert "SQL" in res.score_breakdown.matched_skills


def test_tie_breaking_order(base_profile):
    """Verify that identical scores are sorted deterministically."""
    opp1 = {
        "opportunity_id": "opp-b",
        "title": "Beta Opportunity",
        "category": "Scholarships",
        "education_level": "Undergraduate",
        "status": "Open",
    }
    opp2 = {
        "opportunity_id": "opp-a",
        "title": "Alpha Opportunity",
        "category": "Scholarships",
        "education_level": "Undergraduate",
        "status": "Open",
    }
    ranked = rank_opportunities(base_profile, [opp1, opp2])
    assert len(ranked) == 2
    # Alphabetical by title for ties: Alpha should rank before Beta
    assert ranked[0].opportunity_id == "opp-a"
    assert ranked[1].opportunity_id == "opp-b"
    assert ranked[0].ranked_position == 1
    assert ranked[1].ranked_position == 2
