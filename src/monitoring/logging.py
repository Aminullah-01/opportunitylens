"""Structured operational logging and credential redaction for OpportunityLens.

Provides sanitization for secrets, timestamps in UTC, duration measurement,
and standardized operational telemetry across ingestion, quality auditing,
and health monitoring.
"""

from __future__ import annotations

import json
import logging
import re
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Generator, Optional

# Secret redaction patterns
_SECRET_KEY_PATTERN = re.compile(
    r"(?i)(password|secret|token|api_?key|auth|credential|snowflake_password|hf_api_key)"
)
_BEARER_PATTERN = re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]+")
_HF_TOKEN_PATTERN = re.compile(r"hf_[A-Za-z0-9_]{8,}")
_GENERIC_KEY_VALUE_PATTERN = re.compile(
    r"(?i)(password|token|secret|api_?key)\s*[:=]\s*['\"]?([^'\"\s,]+)['\"]?"
)


def sanitize_text(text: str) -> str:
    """Sanitize sensitive substrings (passwords, tokens, authorization headers) from text.

    Args:
        text: Input string that may contain sensitive data.

    Returns:
        Clean string with sensitive values replaced with [REDACTED].
    """
    if not text:
        return text

    sanitized = _BEARER_PATTERN.sub("Bearer [REDACTED]", text)
    sanitized = _HF_TOKEN_PATTERN.sub("hf_[REDACTED]", sanitized)
    sanitized = _GENERIC_KEY_VALUE_PATTERN.sub(r"\1=[REDACTED]", sanitized)
    return sanitized


def sanitize_data(data: Any) -> Any:
    """Recursively sanitize dictionaries, lists, and primitives.

    Replaces values for sensitive keys (e.g. password, token, key) with [REDACTED].
    """
    if isinstance(data, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in data.items():
            if _SECRET_KEY_PATTERN.search(str(k)):
                cleaned[str(k)] = "[REDACTED]"
            else:
                cleaned[str(k)] = sanitize_data(v)
        return cleaned
    elif isinstance(data, (list, tuple)):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, str):
        return sanitize_text(data)
    return data


@dataclass(frozen=True)
class OperationalLogEntry:
    """Structured operational log payload."""

    timestamp_utc: str
    component: str
    operation: str
    status: str  # "SUCCESS", "FAILURE", "WARNING", "INFO"
    duration_ms: Optional[float] = None
    records_processed: Optional[int] = None
    warnings_count: Optional[int] = None
    errors_count: Optional[int] = None
    message: str = ""
    error: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert entry to a clean sanitized dictionary."""
        raw = asdict(self)
        return sanitize_data(raw)

    def to_json(self) -> str:
        """Serialize entry to a compact JSON string."""
        return json.dumps(self.to_dict(), default=str)


class OperationalLogger:
    """Standardized logger providing structured telemetry and safe error logging."""

    def __init__(self, name: str = "opportunitylens"):
        self.logger = logging.getLogger(name)

    def log(
        self,
        component: str,
        operation: str,
        status: str,
        message: str = "",
        duration_ms: Optional[float] = None,
        records_processed: Optional[int] = None,
        warnings_count: Optional[int] = None,
        errors_count: Optional[int] = None,
        error: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        level: int = logging.INFO,
    ) -> OperationalLogEntry:
        """Create and emit a structured operational log entry."""
        now_utc = datetime.now(timezone.utc).isoformat()
        entry = OperationalLogEntry(
            timestamp_utc=now_utc,
            component=component,
            operation=operation,
            status=status.upper(),
            duration_ms=round(duration_ms, 2) if duration_ms is not None else None,
            records_processed=records_processed,
            warnings_count=warnings_count,
            errors_count=errors_count,
            message=sanitize_text(message),
            error=sanitize_text(error) if error else None,
            details=sanitize_data(details) if details else None,
        )

        log_level = level
        if status.upper() == "FAILURE":
            log_level = logging.ERROR
        elif status.upper() == "WARNING":
            log_level = logging.WARNING

        self.logger.log(log_level, entry.to_json())
        return entry

    @contextmanager
    def measure_operation(
        self,
        component: str,
        operation: str,
        message: str = "",
        records_processed: Optional[int] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Context manager that measures duration and logs success or failure.

        Yields a mutable dictionary for callers to attach records_processed,
        warnings_count, errors_count, and details before completion.
        """
        start = time.perf_counter()
        meta: Dict[str, Any] = {
            "records_processed": records_processed,
            "warnings_count": 0,
            "errors_count": 0,
            "details": {},
            "message": message,
        }
        try:
            yield meta
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            status = "WARNING" if meta.get("errors_count", 0) > 0 or meta.get("warnings_count", 0) > 0 else "SUCCESS"
            self.log(
                component=component,
                operation=operation,
                status=status,
                message=meta.get("message", message),
                duration_ms=elapsed_ms,
                records_processed=meta.get("records_processed"),
                warnings_count=meta.get("warnings_count"),
                errors_count=meta.get("errors_count"),
                details=meta.get("details"),
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            self.log(
                component=component,
                operation=operation,
                status="FAILURE",
                message=meta.get("message", f"Failed {operation}"),
                duration_ms=elapsed_ms,
                records_processed=meta.get("records_processed"),
                warnings_count=meta.get("warnings_count"),
                errors_count=(meta.get("errors_count") or 0) + 1,
                error=str(exc),
                details=meta.get("details"),
            )
            raise


# Global default operational logger
op_logger = OperationalLogger()
