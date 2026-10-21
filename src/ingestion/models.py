"""Data models and constants for the OpportunityLens ingestion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional


CANONICAL_CATEGORIES = (
    "Scholarships",
    "Internships",
    "Tech Training",
    "Hackathons",
    "Entry-Level Jobs",
)

VALID_VERIFICATION_STATUSES = (
    "VERIFIED",
    "UNVERIFIED",
    "NEEDS_REVIEW",
)


@dataclass
class NormalizedOpportunity:
    """A fully validated and normalized opportunity record ready for database insertion."""

    opportunity_id: str
    title: str
    category: str
    organization: str
    description: str
    eligibility: str
    education_level: str
    location: str
    deadline: Optional[date]
    source_url: str
    verified_at: Optional[datetime]
    status: str  # Represents verification status in database: VERIFIED, UNVERIFIED, NEEDS_REVIEW

    def to_snowflake_dict(self) -> Dict[str, Any]:
        """Convert record to uppercase keys matching Snowflake column names."""
        return {
            "OPPORTUNITY_ID": self.opportunity_id,
            "TITLE": self.title,
            "CATEGORY": self.category,
            "ORGANIZATION": self.organization,
            "DESCRIPTION": self.description,
            "ELIGIBILITY": self.eligibility,
            "EDUCATION_LEVEL": self.education_level,
            "LOCATION": self.location,
            "DEADLINE": self.deadline,
            "SOURCE_URL": self.source_url,
            "VERIFIED_AT": self.verified_at,
            "STATUS": self.status,
        }


@dataclass
class ValidationResult:
    """The validation outcome for an individual raw opportunity record."""

    is_valid: bool
    record: Optional[NormalizedOpportunity] = None
    raw_id: str = "UNKNOWN"
    errors: List[str] = field(default_factory=list)


@dataclass
class IngestionReport:
    """Summary metrics and audit details from a pipeline execution run."""

    total_records: int = 0
    valid_records: int = 0
    rejected_records: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    dry_run: bool = False
    rejection_details: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def summary_text(self) -> str:
        """Return formatted human-readable summary of ingestion metrics."""
        mode = " [DRY RUN]" if self.dry_run else ""
        lines = [
            f"=== OpportunityLens Ingestion Report{mode} ===",
            f"Total input records:    {self.total_records}",
            f"Valid records:          {self.valid_records}",
            f"Rejected records:       {self.rejected_records}",
            f"Inserted records:       {self.inserted}",
            f"Updated records:        {self.updated}",
            f"Skipped records:        {self.skipped}",
        ]
        if self.rejection_details:
            lines.append("\nRejection Details:")
            for item in self.rejection_details:
                err_str = "; ".join(item.get("reasons", []))
                lines.append(f"  - [{item.get('raw_id', 'UNKNOWN')}] {err_str}")
        if self.errors:
            lines.append("\nPipeline System Errors:")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)
