"""Application health check and readiness subsystem for OpportunityLens.

Evaluates independent component health states (HEALTHY, DEGRADED, UNAVAILABLE, NOT_CHECKED)
without requiring network access by default. Network-dependent checks (Snowflake connectivity,
AI provider availability) are strictly opt-in with bounded timeouts and zero secret leakage.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import (
    ai_config,
    app_config,
    monitoring_config,
    quality_config,
    snowflake_config,
)
from src.monitoring.logging import op_logger, sanitize_data, sanitize_text


class HealthStatus(str, Enum):
    """Component health status classification."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_CHECKED = "NOT_CHECKED"


@dataclass(frozen=True)
class ComponentHealth:
    """Individual component health report."""

    name: str
    status: HealthStatus
    message: str
    duration_ms: float
    details: Dict[str, Any]
    timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert component health to a sanitized dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "message": sanitize_text(self.message),
            "duration_ms": round(self.duration_ms, 2),
            "details": sanitize_data(self.details),
            "timestamp_utc": self.timestamp_utc,
        }


@dataclass(frozen=True)
class SystemHealthReport:
    """Consolidated system-wide health and readiness report."""

    overall_status: HealthStatus
    app_name: str
    app_version: str
    environment: str
    timestamp_utc: str
    components: Dict[str, ComponentHealth]

    @property
    def is_operational(self) -> bool:
        """Indicate whether the application runtime is functional."""
        runtime = self.components.get("app_runtime")
        return bool(runtime and runtime.status == HealthStatus.HEALTHY)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "overall_status": self.overall_status.value,
            "app_name": self.app_name,
            "app_version": self.app_version,
            "environment": self.environment,
            "timestamp_utc": self.timestamp_utc,
            "is_operational": self.is_operational,
            "components": {k: v.to_dict() for k, v in self.components.items()},
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize report to formatted JSON."""
        import json

        return json.dumps(self.to_dict(), indent=indent, default=str)


def check_app_runtime() -> ComponentHealth:
    """Verify local Python runtime and application metadata readiness."""
    start = time.perf_counter()
    now_utc = datetime.now(timezone.utc).isoformat()
    duration_ms = (time.perf_counter() - start) * 1000.0

    return ComponentHealth(
        name="app_runtime",
        status=HealthStatus.HEALTHY,
        message=f"{app_config.APP_NAME} runtime v{app_config.APP_VERSION} initialized.",
        duration_ms=duration_ms,
        details={
            "python_version": sys.version.split()[0],
            "app_version": app_config.APP_VERSION,
            "app_env": app_config.APP_ENV,
            "debug": app_config.DEBUG,
        },
        timestamp_utc=now_utc,
    )


def check_reports_storage() -> ComponentHealth:
    """Verify local report output directory existence and write permissions."""
    start = time.perf_counter()
    now_utc = datetime.now(timezone.utc).isoformat()
    reports_dir = monitoring_config.reports_dir

    try:
        reports_dir.mkdir(parents=True, exist_ok=True)
        # Test write permission using a temporary test file
        with tempfile.NamedTemporaryFile(
            dir=str(reports_dir), prefix=".health_check_", delete=True
        ) as tmp:
            tmp.write(b"health_check_ok")
            tmp.flush()

        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="reports_storage",
            status=HealthStatus.HEALTHY,
            message=f"Report storage directory is writable at '{reports_dir}'.",
            duration_ms=duration_ms,
            details={"path": str(reports_dir), "writable": True},
            timestamp_utc=now_utc,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="reports_storage",
            status=HealthStatus.DEGRADED,
            message=f"Report storage directory is not writable: {exc}",
            duration_ms=duration_ms,
            details={"path": str(reports_dir), "writable": False, "error": str(exc)},
            timestamp_utc=now_utc,
        )


def check_quality_subsystem() -> ComponentHealth:
    """Verify data quality and freshness audit components are importable and configured."""
    start = time.perf_counter()
    now_utc = datetime.now(timezone.utc).isoformat()

    try:
        from src.quality.freshness import (
            evaluate_deadline_lifecycle,
            evaluate_verification_freshness,
        )
        from src.quality.pipeline import run_quality_pipeline
        from src.quality.validator import audit_single_record

        assert callable(evaluate_deadline_lifecycle)
        assert callable(evaluate_verification_freshness)
        assert callable(audit_single_record)
        assert callable(run_quality_pipeline)

        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="quality_subsystem",
            status=HealthStatus.HEALTHY,
            message="Data quality, validation, and freshness modules are operational.",
            duration_ms=duration_ms,
            details={
                "stale_threshold_days": quality_config.stale_threshold_days,
                "network_checks_enabled": quality_config.network_enabled,
                "timeout_seconds": quality_config.timeout_seconds,
            },
            timestamp_utc=now_utc,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="quality_subsystem",
            status=HealthStatus.UNAVAILABLE,
            message=f"Quality subsystem components failed validation: {exc}",
            duration_ms=duration_ms,
            details={"error": str(exc)},
            timestamp_utc=now_utc,
        )


def check_snowflake_health(
    check_connectivity: bool = False,
    timeout_seconds: Optional[float] = None,
) -> ComponentHealth:
    """Evaluate Snowflake integration status.

    Checks configuration presence by default without revealing credentials.
    Live connectivity check is opt-in and timeout-bounded.
    """
    start = time.perf_counter()
    now_utc = datetime.now(timezone.utc).isoformat()
    timeout = timeout_seconds or monitoring_config.health_timeout_seconds

    if not snowflake_config.is_configured:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="snowflake",
            status=HealthStatus.DEGRADED,
            message="Snowflake credentials not configured (running in preview/offline mode).",
            duration_ms=duration_ms,
            details={
                "configured": False,
                "account_provided": bool(snowflake_config.account),
                "database_provided": bool(snowflake_config.database),
            },
            timestamp_utc=now_utc,
        )

    if not check_connectivity:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="snowflake",
            status=HealthStatus.HEALTHY,
            message="Snowflake credentials configured. Live connection check skipped (offline mode).",
            duration_ms=duration_ms,
            details={
                "configured": True,
                "account_provided": bool(snowflake_config.account),
                "database_provided": bool(snowflake_config.database),
                "live_connectivity_checked": False,
            },
            timestamp_utc=now_utc,
        )

    # Opt-in live connectivity check
    try:
        import snowflake.connector

        conn = snowflake.connector.connect(
            user=snowflake_config.user,
            password=snowflake_config.password,
            account=snowflake_config.account,
            warehouse=snowflake_config.warehouse,
            database=snowflake_config.database,
            schema=snowflake_config.schema,
            login_timeout=int(timeout),
            network_timeout=int(timeout),
        )
        try:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.close()
        finally:
            conn.close()

        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="snowflake",
            status=HealthStatus.HEALTHY,
            message="Snowflake live connectivity verified successfully (SELECT 1).",
            duration_ms=duration_ms,
            details={
                "configured": True,
                "live_connectivity_checked": True,
                "database": snowflake_config.database,
                "schema": snowflake_config.schema,
            },
            timestamp_utc=now_utc,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000.0
        sanitized_err = sanitize_text(str(exc))
        return ComponentHealth(
            name="snowflake",
            status=HealthStatus.UNAVAILABLE,
            message=f"Snowflake live connection failed: {sanitized_err}",
            duration_ms=duration_ms,
            details={
                "configured": True,
                "live_connectivity_checked": True,
                "error": sanitized_err,
            },
            timestamp_utc=now_utc,
        )


def check_ai_health(
    check_inference: bool = False,
    timeout_seconds: Optional[float] = None,
) -> ComponentHealth:
    """Evaluate AI provider integration status.

    Checks configuration presence by default without revealing credentials.
    Inference reachability check is opt-in and timeout-bounded.
    """
    start = time.perf_counter()
    now_utc = datetime.now(timezone.utc).isoformat()
    timeout = timeout_seconds or monitoring_config.health_timeout_seconds

    if not ai_config.is_configured:
        duration_ms = (time.perf_counter() - start) * 1000.0
        reason = "disabled by configuration" if not ai_config.ai_enabled else "missing HF_API_KEY"
        return ComponentHealth(
            name="ai_inference",
            status=HealthStatus.DEGRADED,
            message=f"AI provider not configured ({reason}). Deterministic fallbacks active.",
            duration_ms=duration_ms,
            details={
                "configured": False,
                "ai_enabled": ai_config.ai_enabled,
                "has_api_key": bool(ai_config.hf_api_key),
                "model_name": ai_config.model_name,
            },
            timestamp_utc=now_utc,
        )

    if not check_inference:
        duration_ms = (time.perf_counter() - start) * 1000.0
        return ComponentHealth(
            name="ai_inference",
            status=HealthStatus.HEALTHY,
            message="AI provider credentials configured. Live inference check skipped (offline mode).",
            duration_ms=duration_ms,
            details={
                "configured": True,
                "model_name": ai_config.model_name,
                "provider": ai_config.provider,
                "live_inference_checked": False,
            },
            timestamp_utc=now_utc,
        )

    # Opt-in live inference check
    try:
        from src.ai.hf_client import HuggingFaceInferenceClient

        client = HuggingFaceInferenceClient(
            api_key=ai_config.hf_api_key,
            model_name=ai_config.model_name,
            timeout_seconds=int(timeout),
        )
        # Lightweight test prompt
        resp = client.generate_explanation(
            opportunity_title="Health Check Probe",
            organization="System",
            student_profile={"education_level": "Undergraduate", "interests": ["Tech"]},
            match_score=100.0,
        )
        duration_ms = (time.perf_counter() - start) * 1000.0
        if resp.source == "model":
            msg = f"AI inference endpoint verified with model '{ai_config.model_name}'."
            status = HealthStatus.HEALTHY
        else:
            msg = f"AI inference fell back to deterministic provider: {resp.fallback_reason or 'fallback'}"
            status = HealthStatus.DEGRADED

        return ComponentHealth(
            name="ai_inference",
            status=status,
            message=msg,
            duration_ms=duration_ms,
            details={
                "configured": True,
                "live_inference_checked": True,
                "response_source": resp.source,
                "model_name": ai_config.model_name,
            },
            timestamp_utc=now_utc,
        )
    except Exception as exc:
        duration_ms = (time.perf_counter() - start) * 1000.0
        sanitized_err = sanitize_text(str(exc))
        return ComponentHealth(
            name="ai_inference",
            status=HealthStatus.UNAVAILABLE,
            message=f"AI live inference failed: {sanitized_err}",
            duration_ms=duration_ms,
            details={
                "configured": True,
                "live_inference_checked": True,
                "error": sanitized_err,
            },
            timestamp_utc=now_utc,
        )


def check_system_health(
    check_connectivity: bool = False,
    check_inference: bool = False,
    timeout_seconds: Optional[float] = None,
) -> SystemHealthReport:
    """Run consolidated health checks across all components.

    Args:
        check_connectivity: If True, execute a live SELECT 1 against Snowflake.
        check_inference: If True, execute a live probe against the AI model endpoint.
        timeout_seconds: Bounded timeout for opt-in network calls.

    Returns:
        SystemHealthReport summarizing component states and overall health.
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    components = {
        "app_runtime": check_app_runtime(),
        "reports_storage": check_reports_storage(),
        "quality_subsystem": check_quality_subsystem(),
        "snowflake": check_snowflake_health(
            check_connectivity=check_connectivity,
            timeout_seconds=timeout_seconds,
        ),
        "ai_inference": check_ai_health(
            check_inference=check_inference,
            timeout_seconds=timeout_seconds,
        ),
    }

    # Determine overall status:
    # 1. If any critical component (app_runtime, quality_subsystem) is UNAVAILABLE -> UNAVAILABLE
    # 2. If any component is UNAVAILABLE -> DEGRADED
    # 3. If any component is DEGRADED -> DEGRADED
    # 4. Otherwise -> HEALTHY
    if components["app_runtime"].status == HealthStatus.UNAVAILABLE or components["quality_subsystem"].status == HealthStatus.UNAVAILABLE:
        overall = HealthStatus.UNAVAILABLE
    elif any(c.status == HealthStatus.UNAVAILABLE for c in components.values()):
        overall = HealthStatus.DEGRADED
    elif any(c.status == HealthStatus.DEGRADED for c in components.values()):
        overall = HealthStatus.DEGRADED
    else:
        overall = HealthStatus.HEALTHY

    report = SystemHealthReport(
        overall_status=overall,
        app_name=app_config.APP_NAME,
        app_version=app_config.APP_VERSION,
        environment=app_config.APP_ENV,
        timestamp_utc=now_utc,
        components=components,
    )

    op_logger.log(
        component="health_check",
        operation="check_system_health",
        status=overall.value,
        message=f"System health check completed with status {overall.value}",
        details={"components": {k: v.status.value for k, v in components.items()}},
    )

    return report
