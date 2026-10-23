"""Unit tests for the evidence-based eligibility assessment engine."""

from __future__ import annotations

import pytest

from src.matching.eligibility import assess_eligibility, extract_cgpa_threshold
from src.matching.models import EligibilityOutcome
from src.matching.profile import validate_profile


def test_extract_cgpa_threshold():
    """Verify regex extraction of CGPA thresholds from unstructured requirement text."""
    assert extract_cgpa_threshold("Minimum 3.5 CGPA required") == 3.5
    assert extract_cgpa_threshold("Applicants must have a CGPA of 3.0 / 5.0") == 3.0
    assert extract_cgpa_threshold("Must have 3.25/5.0 or second class upper") == 3.25
    assert extract_cgpa_threshold("Open to all students with good standing") is None


def test_likely_eligible_when_all_criteria_met():
    """Verify LIKELY_ELIGIBLE when student meets education level, field, and CGPA."""
    profile = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        cgpa=3.8,
    )
    opp = {
        "opportunity_id": "opp-elig-01",
        "title": "STEM Undergraduate Scholarship",
        "education_level": "Undergraduate",
        "eligibility": "Undergraduate students in Computer Science. Minimum CGPA of 3.5.",
    }
    assessment = assess_eligibility(profile, opp)
    assert assessment.outcome == EligibilityOutcome.LIKELY_ELIGIBLE
    assert len(assessment.confirmed_facts) >= 2
    assert len(assessment.disqualifying_factors) == 0


def test_possibly_eligible_when_unverified_factors_exist():
    """Verify POSSIBLY_ELIGIBLE when base criteria met but optional or missing profile attributes exist."""
    # Profile has no CGPA specified, but opportunity requires min 3.0
    profile = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        cgpa=None,
    )
    opp = {
        "opportunity_id": "opp-elig-02",
        "title": "University Merit Award",
        "education_level": "Undergraduate",
        "eligibility": "Open to undergraduate students with minimum CGPA of 3.0.",
    }
    assessment = assess_eligibility(profile, opp)
    assert assessment.outcome == EligibilityOutcome.POSSIBLY_ELIGIBLE
    assert len(assessment.confirmed_facts) >= 1  # Education level confirmed
    assert any("CGPA" in f for f in assessment.unverified_factors)


def test_likely_not_eligible_when_cgpa_too_low():
    """Verify LIKELY_NOT_ELIGIBLE when student's CGPA is below the minimum."""
    profile = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        cgpa=2.8,
    )
    opp = {
        "opportunity_id": "opp-elig-03",
        "title": "Competitive Excellence Award",
        "education_level": "Undergraduate",
        "eligibility": "Undergraduate students with a minimum CGPA of 3.5.",
    }
    assessment = assess_eligibility(profile, opp)
    assert assessment.outcome == EligibilityOutcome.LIKELY_NOT_ELIGIBLE
    assert len(assessment.disqualifying_factors) >= 1
    assert any("below the required minimum" in f for f in assessment.disqualifying_factors)


def test_likely_not_eligible_when_education_level_conflicts():
    """Verify LIKELY_NOT_ELIGIBLE when student education level contradicts opportunity."""
    profile = validate_profile(
        education_level="Secondary / O'Level",
        field_of_study=None,
    )
    opp = {
        "opportunity_id": "opp-elig-04",
        "title": "University Undergraduate Bursary",
        "education_level": "Undergraduate",
        "eligibility": "Must be an enrolled university undergraduate.",
    }
    assessment = assess_eligibility(profile, opp)
    assert assessment.outcome == EligibilityOutcome.LIKELY_NOT_ELIGIBLE
    assert any("undergraduate" in f.lower() for f in assessment.disqualifying_factors)


def test_insufficient_information_when_eligibility_unspecified():
    """Verify INSUFFICIENT_INFORMATION when opportunity has placeholder eligibility."""
    profile = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
    )
    opp = {
        "opportunity_id": "opp-elig-05",
        "title": "New Emerging Initiative",
        "education_level": "Other",
        "eligibility": "Check official source.",
    }
    assessment = assess_eligibility(profile, opp)
    assert assessment.outcome == EligibilityOutcome.INSUFFICIENT_INFORMATION
    assert len(assessment.disqualifying_factors) == 0


def test_missing_information_property_alias():
    """Verify missing_information property alias matches unverified_factors."""
    profile = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        cgpa=None,
    )
    opp = {
        "opportunity_id": "opp-elig-02",
        "title": "University Merit Award",
        "education_level": "Undergraduate",
        "eligibility": "Open to undergraduate students with minimum CGPA of 3.0.",
    }
    assessment = assess_eligibility(profile, opp)
    assert assessment.missing_information == assessment.unverified_factors
    assert len(assessment.missing_information) > 0

