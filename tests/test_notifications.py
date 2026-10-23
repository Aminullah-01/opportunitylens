"""Tests for optional notification hooks and alert policies."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from src.monitoring.notifications import (
    AlertPolicy,
    LogNotificationChannel,
    NotificationChannel,
    NotificationDispatcher,
    NotificationEvent,
    NotificationSeverity,
    NullNotificationChannel,
)


def test_null_notification_channel():
    """Verify NullNotificationChannel returns True safely without side effects."""
    channel = NullNotificationChannel()
    event = NotificationEvent(
        event_type="TEST",
        severity=NotificationSeverity.INFO,
        title="Test Title",
        summary="Test Summary",
        metrics={"count": 1},
        timestamp_utc="2026-10-22T00:00:00Z",
    )
    assert channel.send(event) is True


def test_log_notification_channel():
    """Verify LogNotificationChannel logs safely."""
    channel = LogNotificationChannel()
    event = NotificationEvent(
        event_type="TEST",
        severity=NotificationSeverity.WARNING,
        title="Warning Title",
        summary="Warning Summary",
        metrics={"count": 5},
        timestamp_utc="2026-10-22T00:00:00Z",
    )
    assert channel.send(event) is True


def test_notification_event_sanitization():
    """Verify notification events sanitize secrets in titles, summaries, and metrics."""
    event = NotificationEvent(
        event_type="LEAK_TEST",
        severity=NotificationSeverity.CRITICAL,
        title="Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        summary="Failed connection password=supersecret",
        metrics={"api_key": "hf_secrettoken", "normal_metric": 42},
        timestamp_utc="2026-10-22T00:00:00Z",
    )
    d = event.to_dict()
    assert "Bearer [REDACTED]" in d["title"]
    assert "password=[REDACTED]" in d["summary"]
    assert d["metrics"]["api_key"] == "[REDACTED]"
    assert d["metrics"]["normal_metric"] == 42


def test_notifications_suppressed_when_disabled():
    """Verify dispatcher does not call channels when enabled=False (default)."""
    mock_channel = MagicMock(spec=NotificationChannel)
    dispatcher = NotificationDispatcher(
        channels=[mock_channel],
        policy=AlertPolicy(enabled=False),
    )

    event = NotificationEvent(
        event_type="TEST",
        severity=NotificationSeverity.CRITICAL,
        title="Test",
        summary="Test",
        metrics={},
        timestamp_utc="2026-10-22T00:00:00Z",
    )
    dispatcher.notify(event)
    mock_channel.send.assert_not_called()


def test_evaluate_audit_results_thresholds():
    """Verify evaluation generates events when alert thresholds are exceeded."""
    mock_channel = MagicMock(spec=NotificationChannel)
    mock_channel.send.return_value = True

    dispatcher = NotificationDispatcher(
        channels=[mock_channel],
        policy=AlertPolicy(
            min_failures_to_alert=1,
            min_stale_to_alert=5,
            min_broken_links_to_alert=3,
            enabled=True,
        ),
    )

    events = dispatcher.evaluate_audit_results(
        total_records=20,
        fail_count=2,
        warning_count=5,
        stale_count=6,
        broken_link_count=4,
        source="test_source",
    )

    # 3 rules triggered: FAIL count >= 1, STALE count >= 5, BROKEN count >= 3
    assert len(events) == 3
    event_types = {e.event_type for e in events}
    assert "BLOCKING_DATA_ERRORS" in event_types
    assert "STALE_RECORDS_SURGE" in event_types
    assert "BROKEN_LINKS_DETECTED" in event_types

    assert mock_channel.send.call_count == 3


def test_notify_execution_failure():
    """Verify execution failure generates a critical notification."""
    mock_channel = MagicMock(spec=NotificationChannel)
    mock_channel.send.return_value = True

    dispatcher = NotificationDispatcher(
        channels=[mock_channel],
        policy=AlertPolicy(enabled=True),
    )

    event = dispatcher.notify_execution_failure(
        source="snowflake",
        error_message="Query timed out user=dev password=secret123",
    )

    assert event.severity == NotificationSeverity.CRITICAL
    assert "password=[REDACTED]" in event.summary
    assert "secret123" not in event.summary
    mock_channel.send.assert_called_once()
