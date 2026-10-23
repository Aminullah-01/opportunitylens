"""Grounded explanation service with deterministic fallback for OpportunityLens."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from src.ai.client import HuggingFaceInferenceClient
from src.ai.prompts import SYSTEM_PROMPT_EXPLANATION, format_user_prompt
from src.ai.schemas import ExplanationItem, ExplanationResponse
from src.config import ai_config
from src.matching.models import MatchResult, StudentProfile

logger = logging.getLogger(__name__)


def generate_deterministic_explanation(
    profile: StudentProfile, matches: List[MatchResult], notice: Optional[str] = None
) -> ExplanationResponse:
    """Generate a 100% deterministic, grounded explanation when AI is unavailable or unconfigured.

    Directly synthesizes matched factors, confirmed eligibility facts, and action items
    from the deterministic scoring engine.

    Args:
        profile: Student profile.
        matches: List of ranked MatchResults.
        notice: Optional diagnostic notice string.

    Returns:
        Structured ExplanationResponse.
    """
    if not matches:
        return ExplanationResponse(
            overall_summary="No opportunities matched your current search filters or profile criteria.",
            items=[],
            is_ai_generated=False,
            model_name="Deterministic Rule Engine",
            warning_or_notice=notice,
        )

    top_count = min(len(matches), 5)
    summary = (
        f"Found {len(matches)} matching opportunities for a {profile.education_level} student"
        + (f" in {profile.field_of_study}" if profile.field_of_study else "")
        + f". Here are the top {top_count} grounded recommendations based on your profile alignment and eligibility criteria."
    )

    items: List[ExplanationItem] = []
    for m in matches[:top_count]:
        # Formulate grounded 'why matched'
        if m.matching_factors:
            why = "; ".join(m.matching_factors[:3]) + "."
        else:
            why = f"General match for {m.category} with {m.match_score}% profile alignment."

        # Formulate eligibility notes
        el_outcome = m.eligibility.outcome.value
        if m.eligibility.confirmed_facts:
            elig_notes = f"[{el_outcome}] " + "; ".join(m.eligibility.confirmed_facts[:2])
        else:
            elig_notes = f"[{el_outcome}] {m.eligibility.summary}"

        # Formulate actionable next step
        if m.deadline:
            action = f"Check portal before deadline ({m.deadline}) and verify required documents."
        elif m.application_status == "Rolling / Ongoing":
            action = "Rolling applications currently open; prepare your portfolio and apply early."
        else:
            action = "Visit official source listing to inspect active application intake windows."

        items.append(
            ExplanationItem(
                opportunity_id=m.opportunity_id,
                title=m.title,
                organization=m.organization,
                match_score=m.match_score,
                eligibility_outcome=el_outcome,
                why_matched=why,
                eligibility_notes=elig_notes,
                action_item=action,
                source_url=m.source_url,
                deadline=m.deadline,
            )
        )

    return ExplanationResponse(
        overall_summary=summary,
        items=items,
        is_ai_generated=False,
        model_name="Deterministic Rule Engine",
        warning_or_notice=notice,
    )


def parse_and_validate_ai_json(
    raw_text: str, matches: List[MatchResult]
) -> Optional[ExplanationResponse]:
    """Parse and validate JSON output from language model, strictly preserving ground truth.

    Ensures that opportunity IDs exist in the retrieved evidence, scores cannot be altered,
    and eligibility decisions cannot be overridden.

    Args:
        raw_text: Raw model generation.
        matches: The original retrieved MatchResult list.

    Returns:
        Validated ExplanationResponse or None if parsing fails.
    """
    if not raw_text or not raw_text.strip():
        return None

    # Strip markdown code blocks if model wrapped JSON in ```json ... ```
    cleaned = raw_text.strip()
    match_code_block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match_code_block:
        cleaned = match_code_block.group(1)
    else:
        # Or look for first { to last }
        brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
        if brace_match:
            cleaned = brace_match.group(1)

    try:
        data = json.loads(cleaned)
    except Exception as exc:
        logger.debug("Failed to parse JSON from AI response: %s", exc)
        return None

    if not isinstance(data, dict):
        return None

    overall_summary = str(data.get("overall_summary") or "").strip()
    if not overall_summary:
        overall_summary = "Personalized opportunity match summary based on your verified evidence."

    raw_recs = data.get("recommendations", [])
    if not isinstance(raw_recs, list):
        return None

    # Map of ground-truth matches by opportunity_id
    matches_by_id = {m.opportunity_id: m for m in matches}

    validated_items: List[ExplanationItem] = []
    for rec in raw_recs:
        if not isinstance(rec, dict):
            continue
        opp_id = str(rec.get("opportunity_id", "")).strip()
        if opp_id not in matches_by_id:
            # Model hallucinated an unknown ID or skipped matching - ignore invalid record
            continue

        true_match = matches_by_id[opp_id]
        why_matched = str(rec.get("why_matched") or "").strip()
        if not why_matched:
            why_matched = "; ".join(true_match.matching_factors) or f"Matches your profile."

        elig_notes = str(rec.get("eligibility_notes") or "").strip()
        if not elig_notes:
            elig_notes = true_match.eligibility.summary

        action_item = str(rec.get("action_item") or "").strip()
        if not action_item:
            action_item = "Inspect official portal for full prerequisites."

        # Build ExplanationItem bound to deterministic ground truth
        validated_items.append(
            ExplanationItem(
                opportunity_id=true_match.opportunity_id,
                title=true_match.title,
                organization=true_match.organization,
                match_score=true_match.match_score,  # Enforce ground truth score!
                eligibility_outcome=true_match.eligibility.outcome.value,  # Enforce ground truth!
                why_matched=why_matched,
                eligibility_notes=elig_notes,
                action_item=action_item,
                source_url=true_match.source_url,  # Enforce ground truth URL!
                deadline=true_match.deadline,  # Enforce ground truth deadline!
            )
        )

    if not validated_items:
        return None

    return ExplanationResponse(
        overall_summary=overall_summary,
        items=validated_items,
        is_ai_generated=True,
        model_name=ai_config.model_name,
        warning_or_notice=None,
    )


def generate_opportunity_explanation(
    profile: StudentProfile,
    matches: List[MatchResult],
    user_query: str = "",
    client: Optional[HuggingFaceInferenceClient] = None,
) -> ExplanationResponse:
    """Generate grounded recommendations using Hugging Face inference or deterministic fallback.

    Args:
        profile: Validated StudentProfile.
        matches: Ranked list of MatchResults.
        user_query: Optional user natural-language prompt.
        client: Optional inference client (for testing/mocking).

    Returns:
        ExplanationResponse containing overall summary and items.
    """
    if not matches:
        return generate_deterministic_explanation(profile, matches)

    inf_client = client or HuggingFaceInferenceClient()

    # If AI is not available (no key or disabled), use deterministic explanation directly
    if not inf_client.is_available:
        notice = (
            "Deterministic explanation mode active (Hugging Face API key not configured). "
            "Explanations are derived directly from verified database evidence."
        )
        return generate_deterministic_explanation(profile, matches, notice=notice)

    # Prepare prompt with untrusted evidence block
    user_prompt = format_user_prompt(profile, matches, user_query=user_query)

    completion_text, error_msg = inf_client.generate_chat_completion(
        system_prompt=SYSTEM_PROMPT_EXPLANATION,
        user_prompt=user_prompt,
    )

    if error_msg or not completion_text:
        # Fallback to deterministic explanation with diagnostic warning
        notice = f"AI Provider Notice: {error_msg}. Fallen back to deterministic explanation engine."
        return generate_deterministic_explanation(profile, matches, notice=notice)

    # Validate AI structured output
    parsed_response = parse_and_validate_ai_json(completion_text, matches)
    if not parsed_response:
        notice = "AI response was non-structured or malformed. Fallen back to deterministic explanation engine."
        return generate_deterministic_explanation(profile, matches, notice=notice)

    return parsed_response
