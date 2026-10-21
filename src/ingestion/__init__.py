"""OpportunityLens data ingestion module."""

from src.ingestion.models import (
    CANONICAL_CATEGORIES,
    IngestionReport,
    NormalizedOpportunity,
    VALID_VERIFICATION_STATUSES,
    ValidationResult,
)
from src.ingestion.pipeline import (
    load_raw_records_from_file,
    run_ingestion_pipeline,
    validate_and_deduplicate,
)
from src.ingestion.validator import validate_raw_record

__all__ = [
    "CANONICAL_CATEGORIES",
    "VALID_VERIFICATION_STATUSES",
    "NormalizedOpportunity",
    "ValidationResult",
    "IngestionReport",
    "validate_raw_record",
    "load_raw_records_from_file",
    "validate_and_deduplicate",
    "run_ingestion_pipeline",
]
