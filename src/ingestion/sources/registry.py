"""Registry and discovery service for OpportunityLens external source adapters."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from src.config import ingestion_config
from src.ingestion.sources.base import BaseSourceAdapter
from src.ingestion.sources.disabled_sources import (
    AirtelCareersAdapter,
    FederalMinistryEducationAdapter,
    YsiInnovationAdapter,
)
from src.ingestion.sources.leep_jobs import LeepJobsAdapter
from src.ingestion.sources.nelex_jobs import NelexJobsAdapter
from src.ingestion.sources.ptdf_scholarship import PtdfScholarshipAdapter

ALL_ADAPTER_CLASSES: List[Type[BaseSourceAdapter]] = [
    LeepJobsAdapter,
    PtdfScholarshipAdapter,
    NelexJobsAdapter,
    AirtelCareersAdapter,
    FederalMinistryEducationAdapter,
    YsiInnovationAdapter,
]


def get_adapter(
    source_id: str,
    network_enabled: bool = True,
    timeout_seconds: Optional[float] = None,
    connect_timeout_seconds: Optional[float] = None,
    read_timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    retry_backoff_factor: Optional[float] = None,
    rate_limit_delay_seconds: Optional[float] = None,
) -> BaseSourceAdapter:
    """Retrieve an initialized source adapter instance by its source identifier.

    Args:
        source_id: Unique source identifier (e.g. 'leep_jobs', 'ptdf_scholarships').
        network_enabled: Whether outbound HTTP requests are permitted.
        timeout_seconds: Optional request timeout in seconds.
        connect_timeout_seconds: Optional connect timeout in seconds.
        read_timeout_seconds: Optional read timeout in seconds.
        max_retries: Optional maximum retry attempts.
        retry_backoff_factor: Optional backoff factor for retries.
        rate_limit_delay_seconds: Optional rate limit delay between requests.

    Returns:
        Instantiated BaseSourceAdapter.

    Raises:
        KeyError: If source_id is not registered.
    """
    c_timeout = (
        connect_timeout_seconds
        if connect_timeout_seconds is not None
        else ingestion_config.connect_timeout_seconds
    )
    r_timeout = (
        read_timeout_seconds
        if read_timeout_seconds is not None
        else (timeout_seconds or ingestion_config.read_timeout_seconds)
    )
    retries = (
        max_retries if max_retries is not None else ingestion_config.max_retries
    )
    backoff = (
        retry_backoff_factor
        if retry_backoff_factor is not None
        else ingestion_config.retry_backoff_factor
    )
    rate_limit = (
        rate_limit_delay_seconds
        if rate_limit_delay_seconds is not None
        else ingestion_config.rate_limit_delay_seconds
    )

    for cls in ALL_ADAPTER_CLASSES:
        if cls.source_id == source_id:
            return cls(
                network_enabled=network_enabled,
                timeout_seconds=r_timeout,
                connect_timeout_seconds=c_timeout,
                read_timeout_seconds=r_timeout,
                max_retries=retries,
                retry_backoff_factor=backoff,
                rate_limit_delay_seconds=rate_limit,
            )
    available = [cls.source_id for cls in ALL_ADAPTER_CLASSES]
    raise KeyError(
        f"Unknown source adapter '{source_id}'. Registered sources: {', '.join(available)}"
    )


def get_all_adapters(
    network_enabled: bool = True,
    timeout_seconds: Optional[float] = None,
    connect_timeout_seconds: Optional[float] = None,
    read_timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    retry_backoff_factor: Optional[float] = None,
    rate_limit_delay_seconds: Optional[float] = None,
) -> List[BaseSourceAdapter]:
    """Return instances of all registered source adapters."""
    c_timeout = (
        connect_timeout_seconds
        if connect_timeout_seconds is not None
        else ingestion_config.connect_timeout_seconds
    )
    r_timeout = (
        read_timeout_seconds
        if read_timeout_seconds is not None
        else (timeout_seconds or ingestion_config.read_timeout_seconds)
    )
    retries = (
        max_retries if max_retries is not None else ingestion_config.max_retries
    )
    backoff = (
        retry_backoff_factor
        if retry_backoff_factor is not None
        else ingestion_config.retry_backoff_factor
    )
    rate_limit = (
        rate_limit_delay_seconds
        if rate_limit_delay_seconds is not None
        else ingestion_config.rate_limit_delay_seconds
    )

    return [
        cls(
            network_enabled=network_enabled,
            timeout_seconds=r_timeout,
            connect_timeout_seconds=c_timeout,
            read_timeout_seconds=r_timeout,
            max_retries=retries,
            retry_backoff_factor=backoff,
            rate_limit_delay_seconds=rate_limit,
        )
        for cls in ALL_ADAPTER_CLASSES
    ]


def get_enabled_adapters(
    network_enabled: bool = True,
    timeout_seconds: Optional[float] = None,
    connect_timeout_seconds: Optional[float] = None,
    read_timeout_seconds: Optional[float] = None,
    max_retries: Optional[int] = None,
    retry_backoff_factor: Optional[float] = None,
    rate_limit_delay_seconds: Optional[float] = None,
) -> List[BaseSourceAdapter]:
    """Return instances of all enabled source adapters ready for ingestion."""
    return [
        adapter
        for adapter in get_all_adapters(
            network_enabled=network_enabled,
            timeout_seconds=timeout_seconds,
            connect_timeout_seconds=connect_timeout_seconds,
            read_timeout_seconds=read_timeout_seconds,
            max_retries=max_retries,
            retry_backoff_factor=retry_backoff_factor,
            rate_limit_delay_seconds=rate_limit_delay_seconds,
        )
        if adapter.enabled
    ]


def list_sources_summary() -> List[Dict[str, Any]]:
    """Return structured catalog of registered adapters and their enablement status."""
    summaries = []
    for cls in ALL_ADAPTER_CLASSES:
        summaries.append({
            "source_id": cls.source_id,
            "source_name": cls.source_name,
            "base_url": cls.base_url,
            "default_category": cls.default_category,
            "enabled": cls.enabled,
            "status": "ENABLED" if cls.enabled else "DISABLED",
            "disabled_reason": cls.disabled_reason,
        })
    return summaries
