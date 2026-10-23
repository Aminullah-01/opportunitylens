"""Data schemas for AI explanation responses and structured validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExplanationItem:
    """Grounded explanation for a single recommended opportunity."""

    opportunity_id: str
    title: str
    organization: str
    match_score: float
    eligibility_outcome: str
    why_matched: str
    eligibility_notes: str
    action_item: str
    source_url: str
    deadline: Optional[str] = None


@dataclass
class ExplanationResponse:
    """Structured response containing grounded explanations for recommended matches."""

    overall_summary: str
    items: List[ExplanationItem] = field(default_factory=list)
    is_ai_generated: bool = False
    model_name: Optional[str] = None
    warning_or_notice: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "overall_summary": self.overall_summary,
            "items": [
                {
                    "opportunity_id": it.opportunity_id,
                    "title": it.title,
                    "organization": it.organization,
                    "match_score": it.match_score,
                    "eligibility_outcome": it.eligibility_outcome,
                    "why_matched": it.why_matched,
                    "eligibility_notes": it.eligibility_notes,
                    "action_item": it.action_item,
                    "source_url": it.source_url,
                    "deadline": it.deadline,
                }
                for it in self.items
            ],
            "is_ai_generated": self.is_ai_generated,
            "model_name": self.model_name,
            "warning_or_notice": self.warning_or_notice,
        }
