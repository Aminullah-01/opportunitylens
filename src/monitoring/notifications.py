"""Optional notification hooks for significant audit outcomes and system alerts.

Provides an isolated, non-intrusive notification interface that operates without
requiring external credentials. Notifications are disabled by default and suppressed
during automated tests.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from src.config import monitoring_config
from src.monitoring.logging import op_logger, sanitize_data, sanitize_text


class NotificationSeverity(str, Enum):
    """Notification severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class NotificationEvent:
    """Standardized event payload for notifications."""

    event_type: str
    severity: NotificationSeverity
    title: str
    summary: str
    metrics: Dict[str, Any]
    timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to sanitized dictionary."""
        return {
            "event_type": self.event_type,
            "severity": self.severity.value,
            "title": sanitize_text(self.title),
            "summary": sanitize_text(self.summary),
            "metrics": sanitize_data(self.metrics),
            "timestamp_utc": self.timestamp_utc,
        }


class NotificationChannel(ABC):
    """Abstract base class for notification channels."""

    @abstractmethod
    def send(self, event: NotificationEvent) -> bool:
        """Send a notification event.

        Args:
            event: The notification event payload.

        Returns:
            True if delivery succeeded or was handled safely, False otherwise.
        """
        raise NotImplementedError


class NullNotificationChannel(NotificationChannel):
    """No-op notification channel used as default or during testing."""

    def send(self, event: NotificationEvent) -> bool:
        return True


class LogNotificationChannel(NotificationChannel):
    """Notification channel that dispatches alerts to the operational log."""

    def __init__(self, logger_name: str = "opportunitylens.alerts"):
        self.logger = logging.getLogger(logger_name)

    def send(self, event: NotificationEvent) -> bool:
        level = logging.INFO
        if event.severity == NotificationSeverity.CRITICAL:
            level = logging.ERROR
        elif event.severity == NotificationSeverity.WARNING:
            level = logging.WARNING

        msg = f"[{event.severity.value}] {event.title}: {event.summary} | Metrics: {event.metrics}"
        self.logger.log(level, msg)

        op_logger.log(
            component="notifications",
            operation="dispatch_alert",
            status="SUCCESS",
            message=event.title,
            details=event.to_dict(),
        )
        return True


@dataclass
class AlertPolicy:
    """Configurable alert thresholds to prevent alert fatigue."""

    min_failures_to_alert: int = 1
    min_stale_to_alert: int = 10
    min_broken_links_to_alert: int = 5
    enabled: bool = False


class NotificationDispatcher:
    """Orchestrates alert rule evaluation and channel dispatch."""

    def __init__(
        self,
        channels: Optional[List[NotificationChannel]] = None,
        policy: Optional[AlertPolicy] = None,
    ):
        self.policy = policy or AlertPolicy(
            enabled=monitoring_config.notifications_enabled
        )
        self.channels = channels if channels is not None else [LogNotificationChannel()]

    def notify(self, event: NotificationEvent) -> bool:
        """Dispatch event to all configured channels if notifications are enabled."""
        if not self.policy.enabled:
            return True

        success = True
        for channel in self.channels:
            try:
                ok = channel.send(event)
                if not ok:
                    success = False
            except Exception as exc:
                op_logger.log(
                    component="notifications",
                    operation="channel_error",
                    status="FAILURE",
                    error=str(exc),
                )
                success = False
        return success

    def evaluate_audit_results(
        self,
        total_records: int,
        fail_count: int,
        warning_count: int,
        stale_count: int,
        broken_link_count: int,
        source: str,
    ) -> List[NotificationEvent]:
        """Evaluate audit metrics against policies and dispatch alerts when thresholds are met."""
        events: List[NotificationEvent] = []
        now_utc = datetime.now(timezone.utc).isoformat()

        # Rule 1: Blocking data errors (FAIL)
        if fail_count >= self.policy.min_failures_to_alert:
            event = NotificationEvent(
                event_type="BLOCKING_DATA_ERRORS",
                severity=NotificationSeverity.CRITICAL,
                title="Blocking Data Quality Errors Detected",
                summary=(
                    f"Audit for source '{source}' found {fail_count} record(s) with FAIL status "
                    f"out of {total_records} inspected."
                ),
                metrics={
                    "total_records": total_records,
                    "fail_count": fail_count,
                    "source": source,
                },
                timestamp_utc=now_utc,
            )
            events.append(event)
            self.notify(event)

        # Rule 2: Surge in stale records
        if stale_count >= self.policy.min_stale_to_alert:
            event = NotificationEvent(
                event_type="STALE_RECORDS_SURGE",
                severity=NotificationSeverity.WARNING,
                title="Elevated Stale Records in Pipeline",
                summary=(
                    f"Audit found {stale_count} stale record(s) (>30 days since verification) "
                    f"in source '{source}'."
                ),
                metrics={
                    "total_records": total_records,
                    "stale_count": stale_count,
                    "source": source,
                },
                timestamp_utc=now_utc,
            )
            events.append(event)
            self.notify(event)

        # Rule 3: High broken link candidates
        if broken_link_count >= self.policy.min_broken_links_to_alert:
            event = NotificationEvent(
                event_type="BROKEN_LINKS_DETECTED",
                severity=NotificationSeverity.WARNING,
                title="Multiple Unreachable Opportunity URLs Detected",
                summary=(
                    f"Audit found {broken_link_count} unreachable or broken source link(s) "
                    f"in source '{source}'."
                ),
                metrics={
                    "total_records": total_records,
                    "broken_link_count": broken_link_count,
                    "source": source,
                },
                timestamp_utc=now_utc,
            )
            events.append(event)
            self.notify(event)

        return events

    def notify_execution_failure(self, source: str, error_message: str) -> NotificationEvent:
        """Dispatch a critical notification when the audit runner or pipeline crashes."""
        now_utc = datetime.now(timezone.utc).isoformat()
        event = NotificationEvent(
            event_type="AUDIT_EXECUTION_FAILURE",
            severity=NotificationSeverity.CRITICAL,
            title="Quality Audit Pipeline Execution Failure",
            summary=f"Audit execution aborted unexpectedly on source '{source}': {sanitize_text(error_message)}",
            metrics={"source": source},
            timestamp_utc=now_utc,
        )
        self.notify(event)
        return event
