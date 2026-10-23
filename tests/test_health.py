"""Tests for system health and readiness diagnostics subsystem."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
import pytest

from src.monitoring.health import (
    ComponentHealth,
    HealthStatus,
    SystemHealthReport,
    check_ai_health,
    check_app_runtime,
    check_quality_subsystem,
    check_reports_storage,
    check_snowflake_health,
    check_system_health,
)


def test_health_status_enum_values():
    """Verify standard health status enum values."""
    assert HealthStatus.HEALTHY.value == "HEALTHY"
    assert HealthStatus.DEGRADED.value == "DEGRADED"
    assert HealthStatus.UNAVAILABLE.value == "UNAVAILABLE"
    assert HealthStatus.NOT_CHECKED.value == "NOT_CHECKED"


def test_component_health_serialization():
    """Verify ComponentHealth dataclass to_dict serializes correctly."""
    ch = ComponentHealth(
        name="test_comp",
        status=HealthStatus.HEALTHY,
        message="Operating normally",
        duration_ms=12.34,
        details={"key": "val", "password": "supersecretpassword"},
        timestamp_utc="2026-10-22T00:00:00Z",
    )
    d = ch.to_dict()
    assert d["name"] == "test_comp"
    assert d["status"] == "HEALTHY"
    assert d["duration_ms"] == 12.34
    assert d["details"]["key"] == "val"
    # Secret must be redacted
    assert d["details"]["password"] == "[REDACTED]"


def test_app_runtime_health():
    """Verify local application runtime check succeeds."""
    res = check_app_runtime()
    assert res.status == HealthStatus.HEALTHY
    assert "runtime" in res.message.lower()
    assert "python_version" in res.details


def test_reports_storage_health_success(tmp_path):
    """Verify reports storage check returns HEALTHY for writable path."""
    with patch("src.monitoring.health.monitoring_config") as mock_conf:
        mock_conf.reports_dir = tmp_path / "reports"
        res = check_reports_storage()
        assert res.status == HealthStatus.HEALTHY
        assert res.details["writable"] is True


def test_reports_storage_health_failure():
    """Verify reports storage check handles un-writable path gracefully."""
    with patch("src.monitoring.health.monitoring_config") as mock_conf:
        # Invalid path that cannot be created
        mock_conf.reports_dir = "/proc/invalid_readonly_dir/test"
        res = check_reports_storage()
        assert res.status == HealthStatus.DEGRADED
        assert res.details["writable"] is False


def test_quality_subsystem_health():
    """Verify quality subsystem check returns HEALTHY."""
    res = check_quality_subsystem()
    assert res.status == HealthStatus.HEALTHY
    assert res.name == "quality_subsystem"


def test_snowflake_health_unconfigured():
    """Verify Snowflake health check returns DEGRADED when credentials are not configured."""
    with patch("src.monitoring.health.snowflake_config") as mock_conf:
        mock_conf.is_configured = False
        mock_conf.account = ""
        mock_conf.database = ""
        res = check_snowflake_health(check_connectivity=False)
        assert res.status == HealthStatus.DEGRADED
        assert "not configured" in res.message


def test_snowflake_health_configured_offline():
    """Verify Snowflake health check returns HEALTHY without network calls when configured."""
    with patch("src.monitoring.health.snowflake_config") as mock_conf:
        mock_conf.is_configured = True
        mock_conf.account = "my_account"
        mock_conf.database = "my_db"
        res = check_snowflake_health(check_connectivity=False)
        assert res.status == HealthStatus.HEALTHY
        assert res.details["live_connectivity_checked"] is False


def test_snowflake_health_live_success():
    """Verify opt-in Snowflake connectivity returns HEALTHY on successful SELECT 1."""
    with patch("src.monitoring.health.snowflake_config") as mock_conf:
        mock_conf.is_configured = True
        mock_conf.user = "usr"
        mock_conf.password = "pwd"
        mock_conf.account = "acc"
        mock_conf.warehouse = "wh"
        mock_conf.database = "db"
        mock_conf.schema = "sch"

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value = mock_cur

        with patch("snowflake.connector.connect", return_value=mock_conn):
            res = check_snowflake_health(check_connectivity=True, timeout_seconds=2.0)
            assert res.status == HealthStatus.HEALTHY
            assert "verified successfully" in res.message
            mock_cur.execute.assert_called_with("SELECT 1")


def test_snowflake_health_live_failure():
    """Verify opt-in Snowflake connectivity returns UNAVAILABLE on connection failure."""
    with patch("src.monitoring.health.snowflake_config") as mock_conf:
        mock_conf.is_configured = True
        mock_conf.user = "usr"
        mock_conf.password = "secret_pass"
        mock_conf.account = "acc"
        mock_conf.warehouse = "wh"
        mock_conf.database = "db"
        mock_conf.schema = "sch"

        with patch(
            "snowflake.connector.connect",
            side_effect=RuntimeError("Connection timeout password=secret_pass"),
        ):
            res = check_snowflake_health(check_connectivity=True, timeout_seconds=2.0)
            assert res.status == HealthStatus.UNAVAILABLE
            assert "failed" in res.message
            # Ensure password was sanitized out
            assert "secret_pass" not in res.message
            assert "[REDACTED]" in res.message


def test_ai_health_unconfigured():
    """Verify AI provider health check returns DEGRADED when API key is missing."""
    with patch("src.monitoring.health.ai_config") as mock_conf:
        mock_conf.is_configured = False
        mock_conf.ai_enabled = True
        mock_conf.hf_api_key = ""
        mock_conf.model_name = "test-model"
        res = check_ai_health(check_inference=False)
        assert res.status == HealthStatus.DEGRADED
        assert "not configured" in res.message


def test_ai_health_configured_offline():
    """Verify AI provider health check returns HEALTHY in offline mode when configured."""
    with patch("src.monitoring.health.ai_config") as mock_conf:
        mock_conf.is_configured = True
        mock_conf.model_name = "test-model"
        mock_conf.provider = "hf-inference"
        res = check_ai_health(check_inference=False)
        assert res.status == HealthStatus.HEALTHY
        assert res.details["live_inference_checked"] is False


def test_system_health_report_offline_default():
    """Verify consolidated system health check runs completely offline by default."""
    report = check_system_health(check_connectivity=False, check_inference=False)
    assert isinstance(report, SystemHealthReport)
    assert report.is_operational is True
    assert "app_runtime" in report.components
    assert "snowflake" in report.components
    assert "ai_inference" in report.components
    assert "quality_subsystem" in report.components
    assert "reports_storage" in report.components

    d = report.to_dict()
    assert d["app_name"] == "OpportunityLens"
    assert "components" in d

    json_str = report.to_json()
    assert json.loads(json_str)["app_name"] == "OpportunityLens"
