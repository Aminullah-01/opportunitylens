"""Safe, SSRF-protected, and rate-limited source link reachability checker."""

from __future__ import annotations

from datetime import datetime, timezone
import ipaddress
import logging
import socket
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from src.quality.models import LinkCheckResult, VerificationStatus

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "OpportunityLens-Auditor/1.0 (+https://github.com/opportunitylens)"
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_REDIRECTS = 3

# Forbidden IP networks for Server-Side Request Forgery (SSRF) defense
FORBIDDEN_NETWORKS = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),          # Loopback IPv4
    ipaddress.ip_network("10.0.0.0/8"),           # Private Class A
    ipaddress.ip_network("172.16.0.0/12"),        # Private Class B
    ipaddress.ip_network("192.168.0.0/16"),       # Private Class C
    ipaddress.ip_network("169.254.0.0/16"),       # Link-Local / Cloud Metadata
    ipaddress.ip_network("224.0.0.0/4"),          # Multicast IPv4
    ipaddress.ip_network("240.0.0.0/4"),          # Reserved IPv4
    ipaddress.ip_network("::1/128"),              # Loopback IPv6
    ipaddress.ip_network("fc00::/7"),             # Unique Local IPv6
    ipaddress.ip_network("fe80::/10"),            # Link-Local IPv6
    ipaddress.ip_network("ff00::/8"),             # Multicast IPv6
)


def is_safe_destination_ip(ip_str: str) -> Tuple[bool, Optional[str]]:
    """Verify that an IP address is a safe, publicly routable address.

    Blocks private, loopback, link-local, cloud metadata, and multicast addresses.

    Args:
        ip_str: IPv4 or IPv6 address string.

    Returns:
        Tuple of (is_safe, failure_reason).
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return False, f"Invalid IP address format: '{ip_str}'"

    for forbidden_net in FORBIDDEN_NETWORKS:
        if ip_obj in forbidden_net:
            return False, f"Destination IP '{ip_str}' falls within forbidden network {forbidden_net} (SSRF defense)."

    if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
        return False, f"Destination IP '{ip_str}' is non-public or reserved (SSRF defense)."

    return True, None


def validate_url_syntax_and_destination(url: Optional[str]) -> Tuple[bool, Optional[str], Optional[str]]:
    """Validate URL scheme, structure, and resolve destination host for SSRF safety.

    Args:
        url: URL string to inspect.

    Returns:
        Tuple of (is_valid, resolved_ip, error_message).
    """
    if not url or not isinstance(url, str):
        return False, None, "URL is empty or not a string."

    clean_url = url.strip()
    if not clean_url:
        return False, None, "URL is empty."

    try:
        parsed = urlparse(clean_url)
    except Exception as exc:
        return False, None, f"Malformed URL syntax: {exc}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, None, f"Unsupported URL scheme '{parsed.scheme}'; only http:// and https:// allowed."

    hostname = parsed.hostname
    if not hostname:
        return False, None, "URL contains no hostname or network location."

    # Prevent localhost explicitly
    if hostname.lower() in ("localhost", "localhost.localdomain", "broadcasthost"):
        return False, None, f"Access to '{hostname}' is blocked (SSRF defense)."

    # Check if hostname is an IP literal directly before DNS lookup
    try:
        ip_obj = ipaddress.ip_address(hostname)
        resolved_ip = str(ip_obj)
    except ValueError:
        # Resolve hostname to detect internal routing or loopback spoofing
        try:
            addr_info = socket.getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
            if not addr_info:
                return False, None, f"Unable to resolve DNS for hostname '{hostname}'."

            resolved_ip = addr_info[0][4][0]
        except socket.gaierror as dns_err:
            return False, None, f"DNS resolution failed for '{hostname}': {dns_err}"
        except Exception as exc:
            return False, None, f"Failed to resolve host '{hostname}': {exc}"

    is_safe, safety_err = is_safe_destination_ip(resolved_ip)
    if not is_safe:
        return False, resolved_ip, safety_err

    return True, resolved_ip, None


class SafeSourceChecker:
    """Configurable, timeout-controlled, SSRF-protected HTTP link checker."""

    def __init__(
        self,
        network_enabled: bool = False,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        user_agent: str = DEFAULT_USER_AGENT,
        max_retries: int = 1,
        rate_limit_delay_seconds: float = 0.0,
    ):
        self.network_enabled = network_enabled
        self.timeout = timeout_seconds
        self.max_redirects = max_redirects
        self.user_agent = user_agent
        self.max_retries = max_retries
        self.rate_limit_delay = rate_limit_delay_seconds
        self._session: Optional[requests.Session] = None

    def _get_session(self) -> requests.Session:
        """Create or return reusable configured requests Session with bounded retries."""
        if self._session is None:
            session = requests.Session()
            session.max_redirects = self.max_redirects
            retries = Retry(
                total=self.max_retries,
                backoff_factor=0.3,
                status_forcelist=(500, 502, 503, 504),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retries)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            self._session = session
        return self._session

    def check_url(self, url: str) -> LinkCheckResult:
        """Evaluate source link reachability safely.

        Args:
            url: Opportunity source URL.

        Returns:
            LinkCheckResult containing reachability status and diagnostics.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Check network_enabled mode
        if not self.network_enabled:
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.NOT_CHECKED,
                error_code="NETWORK_DISABLED",
                error_message="Network verification disabled (offline / dry-run mode).",
                checked_at=now_iso,
            )

        # 2. Syntax & SSRF pre-check
        is_valid, resolved_ip, validation_err = validate_url_syntax_and_destination(url)
        if not is_valid:
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.BROKEN_LINK,
                error_code="INVALID_OR_FORBIDDEN_URL",
                error_message=validation_err,
                checked_at=now_iso,
            )

        # Rate-limiting delay if configured
        if self.rate_limit_delay > 0:
            time.sleep(self.rate_limit_delay)

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        start_time = time.perf_counter()
        session = self._get_session()

        try:
            # First attempt HEAD request to avoid pulling large payloads
            try:
                response = session.head(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                )
                # Some web servers reject HEAD with 405 Method Not Allowed or 403
                if response.status_code in (405, 403):
                    response = session.get(
                        url,
                        headers=headers,
                        timeout=self.timeout,
                        allow_redirects=True,
                        stream=True,  # Stream to avoid loading large assets
                    )
            except (requests.exceptions.RequestException, Exception):
                # Fall back to GET if HEAD failed
                response = session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    stream=True,
                )

            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            status_code = response.status_code
            final_url = response.url

            # Re-validate final destination URL if redirected to prevent open-redirect SSRF
            if final_url and final_url != url:
                dest_valid, _, dest_err = validate_url_syntax_and_destination(final_url)
                if not dest_valid:
                    return LinkCheckResult(
                        url=url,
                        is_reachable=False,
                        http_status=status_code,
                        verification_status=VerificationStatus.BROKEN_LINK,
                        error_code="UNSAFE_REDIRECT",
                        error_message=f"Redirected to forbidden or unsafe destination: {dest_err}",
                        latency_ms=latency_ms,
                        final_url=final_url,
                        checked_at=now_iso,
                    )

            # Map HTTP response status carefully:
            # 2xx Success: reachable, but NOT proof of open opportunity
            if 200 <= status_code < 300:
                return LinkCheckResult(
                    url=url,
                    is_reachable=True,
                    http_status=status_code,
                    verification_status=VerificationStatus.NEEDS_REVIEW,
                    latency_ms=latency_ms,
                    final_url=final_url,
                    checked_at=now_iso,
                )

            # 404 Not Found: definitely broken
            if status_code == 404:
                return LinkCheckResult(
                    url=url,
                    is_reachable=False,
                    http_status=status_code,
                    verification_status=VerificationStatus.BROKEN_LINK,
                    error_code="HTTP_404_NOT_FOUND",
                    error_message=f"Source URL returned HTTP 404 Not Found.",
                    latency_ms=latency_ms,
                    final_url=final_url,
                    checked_at=now_iso,
                )

            # 403 Forbidden or 429 Too Many Requests: site exists, but bot/rate blocked -> UNVERIFIABLE
            if status_code in (403, 429):
                return LinkCheckResult(
                    url=url,
                    is_reachable=False,
                    http_status=status_code,
                    verification_status=VerificationStatus.UNVERIFIABLE,
                    error_code=f"HTTP_{status_code}_RESTRICTED",
                    error_message=f"Source protected by access controls or rate limits (HTTP {status_code}).",
                    latency_ms=latency_ms,
                    final_url=final_url,
                    checked_at=now_iso,
                )

            # 5xx Server Error: server experiencing downtime
            if status_code >= 500:
                return LinkCheckResult(
                    url=url,
                    is_reachable=False,
                    http_status=status_code,
                    verification_status=VerificationStatus.UNVERIFIABLE,
                    error_code=f"HTTP_{status_code}_SERVER_ERROR",
                    error_message=f"Source server returned error HTTP {status_code}.",
                    latency_ms=latency_ms,
                    final_url=final_url,
                    checked_at=now_iso,
                )

            # Other 4xx client errors
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                http_status=status_code,
                verification_status=VerificationStatus.BROKEN_LINK,
                error_code=f"HTTP_{status_code}_CLIENT_ERROR",
                error_message=f"Source returned client error HTTP {status_code}.",
                latency_ms=latency_ms,
                final_url=final_url,
                checked_at=now_iso,
            )

        except requests.exceptions.Timeout as timeout_err:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.UNVERIFIABLE,
                error_code="REQUEST_TIMEOUT",
                error_message=f"Connection timed out after {self.timeout}s: {timeout_err}",
                latency_ms=latency_ms,
                checked_at=now_iso,
            )

        except requests.exceptions.TooManyRedirects as redir_err:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.BROKEN_LINK,
                error_code="TOO_MANY_REDIRECTS",
                error_message=f"Exceeded redirect limit ({self.max_redirects}): {redir_err}",
                latency_ms=latency_ms,
                checked_at=now_iso,
            )

        except requests.exceptions.SSLError as ssl_err:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.UNVERIFIABLE,
                error_code="TLS_SSL_ERROR",
                error_message=f"SSL certificate or TLS handshake error: {ssl_err}",
                latency_ms=latency_ms,
                checked_at=now_iso,
            )

        except (requests.exceptions.ConnectionError, socket.error) as conn_err:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.BROKEN_LINK,
                error_code="CONNECTION_FAILED",
                error_message=f"Network connection failed: {conn_err}",
                latency_ms=latency_ms,
                checked_at=now_iso,
            )

        except Exception as exc:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 1)
            return LinkCheckResult(
                url=url,
                is_reachable=False,
                verification_status=VerificationStatus.UNVERIFIABLE,
                error_code="UNEXPECTED_ERROR",
                error_message=f"Unexpected error during source check: {exc}",
                latency_ms=latency_ms,
                checked_at=now_iso,
            )
