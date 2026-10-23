"""Source adapters package for real external opportunity data ingestion."""

from src.ingestion.sources.base import BaseSourceAdapter, SourceCollectionResult
from src.ingestion.sources.disabled_sources import (
    AirtelCareersAdapter,
    FederalMinistryEducationAdapter,
    YsiInnovationAdapter,
)
from src.ingestion.sources.leep_jobs import LeepJobsAdapter
from src.ingestion.sources.nelex_jobs import NelexJobsAdapter
from src.ingestion.sources.ptdf_scholarship import PtdfScholarshipAdapter
from src.ingestion.sources.registry import (
    ALL_ADAPTER_CLASSES,
    get_adapter,
    get_all_adapters,
    get_enabled_adapters,
    list_sources_summary,
)

__all__ = [
    "BaseSourceAdapter",
    "SourceCollectionResult",
    "LeepJobsAdapter",
    "PtdfScholarshipAdapter",
    "NelexJobsAdapter",
    "AirtelCareersAdapter",
    "FederalMinistryEducationAdapter",
    "YsiInnovationAdapter",
    "ALL_ADAPTER_CLASSES",
    "get_adapter",
    "get_all_adapters",
    "get_enabled_adapters",
    "list_sources_summary",
]
