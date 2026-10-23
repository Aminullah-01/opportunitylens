"""Unit tests for explanation generation, JSON validation, and deterministic fallbacks."""

from __future__ import annotations

import json
from unittest.mock import MagicMock
import pytest

from src.ai.explanation import (
    generate_deterministic_explanation,
    generate_opportunity_explanation,
    parse_and_validate_ai_json,
)
from src.matching.models import (
    EligibilityAssessment,
    EligibilityOutcome,
    MatchResult,
    MatchScoreBreakdown,
    StudentProfile,
)
from src.matching.profile import validate_profile


@pytest.fixture
def sample_profile() -> StudentProfile:
    """Fixture providing a standard profile."""
    return validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        skills=["Python", "SQL"],
        location="Gombe",
    )


@pytest.fixture
def sample_matches() -> list[MatchResult]:
    """Fixture providing candidate match results."""
    m1 = MatchResult(
        opportunity_id="opp-101",
        title="Gombe Tech Scholarship",
        organization="Gombe State",
        category="Scholarships",
        match_score=92.5,
        ranked_position=1,
        score_breakdown=MatchScoreBreakdown(total_score=92.5),
        matching_factors=["Matches education level", "Matches location Gombe"],
        potential_mismatches=[],
        unknown_factors=[],
        application_status="Open",
        deadline="2026-12-01",
        source_url="https://example.com/sch",
        verified_at="2026-10-15",
        eligibility=EligibilityAssessment(
            outcome=EligibilityOutcome.LIKELY_ELIGIBLE,
            summary="Matches undergraduate criteria",
            confirmed_facts=["Confirmed undergraduate standing"],
        ),
    )
    return [m1]


def test_generate_deterministic_explanation(sample_profile, sample_matches):
    """Verify that deterministic fallback generates structured and faithful explanation."""
    resp = generate_deterministic_explanation(sample_profile, sample_matches)

    assert resp.is_ai_generated is False
    assert resp.model_name == "Deterministic Rule Engine"
    assert len(resp.items) == 1
    item = resp.items[0]
    assert item.opportunity_id == "opp-101"
    assert item.match_score == 92.5
    assert item.eligibility_outcome == "LIKELY_ELIGIBLE"
    assert "Gombe State" in item.organization
    assert "2026-12-01" in item.deadline


def test_parse_and_validate_ai_json_valid(sample_matches):
    """Verify parsing valid AI JSON output."""
    raw_json = json.dumps({
        "overall_summary": "Top recommendations for your computer science background.",
        "recommendations": [
            {
                "opportunity_id": "opp-101",
                "why_matched": "Strong alignment with your CS skills and Gombe location.",
                "eligibility_notes": "All undergraduate criteria satisfied.",
                "action_item": "Prepare your academic transcript and apply before December.",
            }
        ],
    })

    resp = parse_and_validate_ai_json(raw_json, sample_matches)
    assert resp is not None
    assert resp.is_ai_generated is True
    assert len(resp.items) == 1
    assert resp.items[0].opportunity_id == "opp-101"
    assert resp.items[0].why_matched == "Strong alignment with your CS skills and Gombe location."


def test_parse_and_validate_ai_json_rejects_hallucinations(sample_matches):
    """Verify that hallucinated opportunity IDs not in matches are rejected."""
    raw_json = json.dumps({
        "overall_summary": "Hallucinated recommendations.",
        "recommendations": [
            {
                "opportunity_id": "opp-fake-999",  # Not in sample_matches
                "why_matched": "Invented opportunity.",
                "eligibility_notes": "Fake notes.",
                "action_item": "Fake link.",
            }
        ],
    })

    resp = parse_and_validate_ai_json(raw_json, sample_matches)
    # When all recommendations are hallucinated IDs, returns None to trigger fallback
    assert resp is None


def test_parse_and_validate_ai_json_enforces_ground_truth_score(sample_matches):
    """Verify that AI cannot inflate or tamper with the deterministic match score."""
    raw_json = json.dumps({
        "overall_summary": "Summary",
        "recommendations": [
            {
                "opportunity_id": "opp-101",
                "match_score": 100.0,  # AI attempted to change 92.5 to 100.0
                "eligibility_outcome": "POSSIBLY_ELIGIBLE",  # AI attempted to override
                "why_matched": "Great match.",
                "eligibility_notes": "Notes.",
                "action_item": "Action.",
            }
        ],
    })

    resp = parse_and_validate_ai_json(raw_json, sample_matches)
    assert resp is not None
    # Score MUST remain the true deterministic score 92.5
    assert resp.items[0].match_score == 92.5
    # Outcome MUST remain the true deterministic outcome LIKELY_ELIGIBLE
    assert resp.items[0].eligibility_outcome == "LIKELY_ELIGIBLE"


def test_parse_and_validate_ai_json_markdown_fence_stripping(sample_matches):
    """Verify that JSON wrapped in markdown code blocks is correctly parsed."""
    wrapped_json = """```json
    {
        "overall_summary": "Fenced JSON response",
        "recommendations": [
            {
                "opportunity_id": "opp-101",
                "why_matched": "Fenced match",
                "eligibility_notes": "Fenced eligibility",
                "action_item": "Fenced action"
            }
        ]
    }
    ```"""
    resp = parse_and_validate_ai_json(wrapped_json, sample_matches)
    assert resp is not None
    assert len(resp.items) == 1
    assert resp.items[0].opportunity_id == "opp-101"


def test_generate_opportunity_explanation_fallback_on_client_error(sample_profile, sample_matches):
    """Verify that when AI client fails, explanation falls back cleanly to deterministic engine."""
    mock_client = MagicMock()
    mock_client.is_available = True
    mock_client.generate_chat_completion.return_value = (None, "Provider rate limit exceeded")

    resp = generate_opportunity_explanation(
        sample_profile, sample_matches, client=mock_client
    )
    assert resp.is_ai_generated is False
    assert resp.model_name == "Deterministic Rule Engine"
    assert "Provider rate limit exceeded" in resp.warning_or_notice
    assert len(resp.items) == 1
    assert resp.items[0].opportunity_id == "opp-101"
