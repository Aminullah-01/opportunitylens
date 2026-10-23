"""Base adapter interface and collection result models for external opportunity sources.

Provides an extensible, resilient base class with integrated SSRF protection,
rate-limiting, timeout controls, and unified error handling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from src.ingestion.models import NormalizedOpportunity
from src.quality.source_checker import (
    DEFAULT_USER_AGENT,
    is_safe_destination_ip,
    validate_url_syntax_and_destination,
)

logger = logging.getLogger(__name__)


@dataclass
class SourceCollectionResult:
    """Outcome and collected records from a single external source adapter execution."""

    source_id: str
    source_name: str
    success: bool
    records: List[NormalizedOpportunity] = field(default_factory=list)
    total_fetched: int = 0
    parsed_count: int = 0
    error_count: int = 0
    error_message: Optional[str] = None
    warning_messages: List[str] = field(default_factory=list)
    has_partial_errors: bool = False
    collection_timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_seconds: float = 0.0

    @property
    def partial_success(self) -> bool:
        """True if some records were collected despite warnings or errors."""
        return len(self.records) > 0 and (
            not self.success or self.has_partial_errors or self.error_count > 0
        )

    def summary_line(self) -> str:
        """Single-line human-readable execution summary."""
        dur = f"{self.duration_seconds:.2f}s"
        rec_cnt = len(self.records)
        if not self.success and rec_cnt == 0:
            return f"[✗] {self.source_name} ({self.source_id}): Failed ({self.error_message}) [{dur}]"
        elif not self.success and rec_cnt > 0:
            return f"[~] {self.source_name} ({self.source_id}): Partial collection ({rec_cnt} records collected, error: {self.error_message}) [{dur}]"
        elif self.has_partial_errors or self.warning_messages or self.error_count > 0:
            warn_cnt = len(self.warning_messages) + self.error_count
            return f"[!] {self.source_name} ({self.source_id}): {rec_cnt} records collected with {warn_cnt} warning(s) [{dur}]"
        return f"[✓] {self.source_name} ({self.source_id}): {rec_cnt} records collected [{dur}]"


class BaseSourceAdapter(ABC):
    """Abstract base class for all opportunity source ingestion adapters."""

    source_id: str
    source_name: str
    base_url: str
    default_category: str
    enabled: bool = True
    disabled_reason: Optional[str] = None
    timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 5.0
    read_timeout_seconds: float = 25.0
    max_retries: int = 3
    retry_backoff_factor: float = 0.5
    rate_limit_delay_seconds: float = 0.5

    def __init__(
        self,
        timeout_seconds: Optional[float] = None,
        connect_timeout_seconds: Optional[float] = None,
        read_timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
        retry_backoff_factor: Optional[float] = None,
        rate_limit_delay_seconds: Optional[float] = None,
        network_enabled: bool = True,
    ) -> None:
        if connect_timeout_seconds is not None:
            self.connect_timeout_seconds = connect_timeout_seconds
        if read_timeout_seconds is not None:
            self.read_timeout_seconds = read_timeout_seconds
        elif timeout_seconds is not None:
            self.read_timeout_seconds = timeout_seconds

        if timeout_seconds is not None:
            self.timeout_seconds = timeout_seconds
        else:
            self.timeout_seconds = self.read_timeout_seconds

        if max_retries is not None:
            self.max_retries = max_retries
        if retry_backoff_factor is not None:
            self.retry_backoff_factor = retry_backoff_factor
        if rate_limit_delay_seconds is not None:
            self.rate_limit_delay_seconds = rate_limit_delay_seconds

        self.network_enabled = network_enabled
        self._last_request_time: float = 0.0
        self.warning_messages: List[str] = []

        # Configure session with bounded exponential backoff retries
        self.session = requests.Session()
        if self.max_retries > 0:
            retry_strategy = Retry(
                total=self.max_retries,
                backoff_factor=self.retry_backoff_factor,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"],
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry_strategy)
            self.session.mount("https://", adapter)
            self.session.mount("http://", adapter)

    def _apply_rate_limit(self) -> None:
        """Enforce polite inter-request delay to prevent overwhelming remote servers."""
        if self.rate_limit_delay_seconds > 0.0:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.rate_limit_delay_seconds:
                sleep_time = self.rate_limit_delay_seconds - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.monotonic()

    def safe_request(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        """Execute an outbound HTTP request with SSRF validation, rate limiting, and timeout.

        Args:
            url: Absolute destination URL.
            method: HTTP method (GET by default).
            headers: Optional HTTP headers dict.
            params: Optional query parameters.

        Returns:
            requests.Response object.

        Raises:
            RuntimeError: If network collection is disabled.
            ValueError: If URL fails syntax validation or destination IP resolves to forbidden space.
            requests.RequestException: On transport or HTTP errors.
        """
        if not self.network_enabled:
            raise RuntimeError(
                f"Network collection is disabled. Cannot request '{url}'."
            )

        # 1. SSRF and URL validation
        is_valid, resolved_ip, err = validate_url_syntax_and_destination(url)
        if not is_valid:
            raise ValueError(f"SSRF defense blocked request to '{url}': {err}")

        # 2. Rate limit enforcement
        self._apply_rate_limit()

        req_headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if headers:
            req_headers.update(headers)

        # 3. Execute request with strict connect and read timeouts
        timeout_val = (self.connect_timeout_seconds, self.read_timeout_seconds)
        response = self.session.request(
            method=method,
            url=url,
            headers=req_headers,
            params=params,
            timeout=timeout_val,
            allow_redirects=True,
        )

        # 4. Check redirect target if redirected
        if response.history:
            final_url = response.url
            is_valid_dest, _, dest_err = validate_url_syntax_and_destination(final_url)
            if not is_valid_dest:
                raise ValueError(
                    f"Redirected to forbidden or unsafe destination '{final_url}': {dest_err}"
                )

        response.raise_for_status()
        return response

    @abstractmethod
    def fetch_raw(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch raw unparsed opportunity payloads from external source.

        Args:
            limit: Optional maximum number of raw records to fetch.

        Returns:
            List of raw dictionaries / metadata payloads.
        """
        pass

    @abstractmethod
    def parse_record(self, raw: Dict[str, Any]) -> NormalizedOpportunity:
        """Parse an individual raw source payload into a NormalizedOpportunity model.

        Args:
            raw: Dictionary extracted from source.

        Returns:
            NormalizedOpportunity populated with normalized fields.
        """
        pass

    def collect(self, limit: Optional[int] = None) -> SourceCollectionResult:
        """Safely execute the end-to-end collection lifecycle for this source.

        Handles network, parsing, and normalization errors gracefully without
        crashing the parent process or other source adapters.

        Args:
            limit: Optional maximum number of opportunities to collect.

        Returns:
            SourceCollectionResult with collected records, counts, and diagnostic telemetry.
        """
        start_time = time.monotonic()
        now_utc = datetime.now(timezone.utc)
        result = SourceCollectionResult(
            source_id=self.source_id,
            source_name=self.source_name,
            success=False,
            collection_timestamp=now_utc,
        )

        if not self.enabled:
            result.error_message = (
                self.disabled_reason or "Source adapter is currently disabled."
            )
            result.duration_seconds = time.monotonic() - start_time
            return result

        self.warning_messages = []
        normalized_records: List[NormalizedOpportunity] = []
        parse_errors = 0

        try:
            raw_records = self.fetch_raw(limit=limit)
            result.total_fetched = len(raw_records)

            for raw in raw_records:
                try:
                    norm = self.parse_record(raw)
                    normalized_records.append(norm)
                except Exception as parse_exc:
                    parse_errors += 1
                    logger.warning(
                        "Failed to parse opportunity payload from %s: %s",
                        self.source_id,
                        parse_exc,
                    )
                    self.warning_messages.append(f"Parse error: {parse_exc}")

            result.records = normalized_records
            result.parsed_count = len(normalized_records)
            result.error_count = parse_errors
            result.warning_messages = list(self.warning_messages)
            result.has_partial_errors = (
                parse_errors > 0 or len(self.warning_messages) > 0
            )
            # Only marked full clean success if there were zero errors and zero warnings
            result.success = (
                parse_errors == 0 and len(self.warning_messages) == 0
            ) and (len(normalized_records) > 0 or result.total_fetched == 0)

        except Exception as exc:
            result.records = normalized_records
            result.parsed_count = len(normalized_records)
            result.error_count = parse_errors + 1
            result.error_message = str(exc)
            result.warning_messages = list(self.warning_messages)
            result.has_partial_errors = True
            result.success = False
            logger.error("Source collection failed for %s: %s", self.source_id, exc)

        result.duration_seconds = time.monotonic() - start_time
        return result
