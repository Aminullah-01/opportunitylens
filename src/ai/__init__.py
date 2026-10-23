"""OpportunityLens AI explanation package."""

from src.ai.client import HuggingFaceInferenceClient
from src.ai.explanation import (
    generate_deterministic_explanation,
    generate_opportunity_explanation,
    parse_and_validate_ai_json,
)
from src.ai.prompts import SYSTEM_PROMPT_EXPLANATION, format_user_prompt
from src.ai.schemas import ExplanationItem, ExplanationResponse

__all__ = [
    "HuggingFaceInferenceClient",
    "ExplanationItem",
    "ExplanationResponse",
    "SYSTEM_PROMPT_EXPLANATION",
    "format_user_prompt",
    "generate_deterministic_explanation",
    "generate_opportunity_explanation",
    "parse_and_validate_ai_json",
]
