"""CLI command for OpportunityLens health checks and operational readiness.

Usage:
    python -m src.monitoring.cli --health
    python -m src.monitoring.cli --health --json
    python -m src.monitoring.cli --check-connectivity --check-inference
"""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from src.monitoring.health import HealthStatus, check_system_health


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for health and readiness diagnostics."""
    parser = argparse.ArgumentParser(
        prog="python -m src.monitoring.cli",
        description="OpportunityLens System Health & Readiness Diagnostics",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        default=True,
        help="Run system health checks across all components (default: True)",
    )
    parser.add_argument(
        "--check-connectivity",
        action="store_true",
        default=False,
        help="Opt-in: test live Snowflake database connectivity (SELECT 1)",
    )
    parser.add_argument(
        "--check-inference",
        action="store_true",
        default=False,
        help="Opt-in: test live AI provider inference availability",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Timeout in seconds for opt-in network checks (default: 5.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output machine-readable JSON report",
    )

    args = parser.parse_args(argv)

    report = check_system_health(
        check_connectivity=args.check_connectivity,
        check_inference=args.check_inference,
        timeout_seconds=args.timeout,
    )

    if args.json:
        print(report.to_json(indent=2))
    else:
        status_symbol = {
            HealthStatus.HEALTHY: "✅",
            HealthStatus.DEGRADED: "⚠️",
            HealthStatus.UNAVAILABLE: "❌",
            HealthStatus.NOT_CHECKED: "⚪",
        }.get(report.overall_status, "ℹ️")

        print("=" * 65)
        print(f" {status_symbol} OpportunityLens System Health: {report.overall_status.value}")
        print(f" Environment: {report.environment} | Version: {report.app_version}")
        print(f" Timestamp (UTC): {report.timestamp_utc}")
        print("=" * 65)
        print(f"{'Component':<20} | {'Status':<12} | {'Message'}")
        print("-" * 65)
        for comp_name, comp in report.components.items():
            sym = {
                HealthStatus.HEALTHY: "✅",
                HealthStatus.DEGRADED: "⚠️",
                HealthStatus.UNAVAILABLE: "❌",
                HealthStatus.NOT_CHECKED: "⚪",
            }.get(comp.status, "")
            print(f"{comp_name:<20} | {sym} {comp.status.value:<9} | {comp.message}")
        print("=" * 65)

    # Return 0 if operational (HEALTHY or DEGRADED), 1 if UNAVAILABLE
    return 0 if report.overall_status != HealthStatus.UNAVAILABLE else 1


if __name__ == "__main__":
    sys.exit(main())
