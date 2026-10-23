"""Reusable operational audit runner for OpportunityLens.

Designed for automated execution by cron, CI workflows, or operational schedulers.
Features process locking to prevent overlapping executions, deterministic exit codes,
timestamped report persistence, and optional threshold-based alert dispatching.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, Generator, List, Optional

from src.config import monitoring_config, quality_config, snowflake_config
from src.demo_data import get_demo_opportunities
from src.ingestion.pipeline import load_raw_records_from_file
from src.monitoring.logging import op_logger, sanitize_text
from src.monitoring.notifications import NotificationDispatcher
from src.quality.models import DataQualityReport, QualityStatus
from src.quality.pipeline import run_quality_pipeline
from src.quality.snowflake_audit import fetch_opportunities_for_audit

# Standard process exit codes
EXIT_SUCCESS = 0
EXIT_EXECUTION_FAILURE = 1
EXIT_BLOCKING_DATA_ERRORS = 2
EXIT_QUALITY_WARNINGS = 3


class AuditLockAcquisitionError(RuntimeError):
    """Raised when an existing active audit process holds the lock."""


@contextmanager
def audit_process_lock(lock_path: Path) -> Generator[Path, None, None]:
    """Lightweight process lock preventing concurrent audit executions.

    Writes the current PID to the lock file. Cleans up the lock upon completion.
    If a previous process crashed, detects whether the PID is still alive and
    safely reclaims stale locks.
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    if lock_path.exists():
        try:
            content = lock_path.read_text().strip()
            old_pid = int(content) if content.isdigit() else None
        except Exception:
            old_pid = None

        if old_pid is not None and old_pid > 0:
            # Check if old_pid is still running
            pid_running = False
            try:
                os.kill(old_pid, 0)
                pid_running = True
            except OSError:
                pid_running = False

            if pid_running:
                raise AuditLockAcquisitionError(
                    f"Audit run already in progress by active process (PID {old_pid}). "
                    f"Lock file: {lock_path}"
                )
            else:
                op_logger.log(
                    component="audit_runner",
                    operation="reclaim_stale_lock",
                    status="WARNING",
                    message=f"Reclaimed stale lock from inactive PID {old_pid}.",
                )

    # Write current PID
    current_pid = os.getpid()
    try:
        lock_path.write_text(str(current_pid))
    except Exception as exc:
        raise RuntimeError(f"Unable to write lock file at '{lock_path}': {exc}")

    try:
        yield lock_path
    finally:
        try:
            if lock_path.exists():
                lock_path.unlink()
        except OSError:
            pass


def get_latest_audit_report(
    reports_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent audit report dictionary from the reports directory.

    Returns:
        Report dictionary or None if no prior reports exist.
    """
    directory = reports_dir or monitoring_config.reports_dir
    if not directory.exists():
        return None

    report_files = sorted(
        directory.glob("audit_report_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not report_files:
        return None

    try:
        content = report_files[0].read_text(encoding="utf-8")
        return json.loads(content)
    except Exception as exc:
        op_logger.log(
            component="audit_runner",
            operation="read_latest_report",
            status="FAILURE",
            error=str(exc),
        )
        return None


def run_operational_audit(
    source: str = "demo",
    input_file: Optional[str] = None,
    output_dir: Optional[Path] = None,
    check_network: bool = False,
    stale_threshold_days: Optional[int] = None,
    export_csv: bool = False,
    fail_on_warnings: bool = False,
    notification_dispatcher: Optional[NotificationDispatcher] = None,
) -> tuple[int, Optional[DataQualityReport], Optional[Path]]:
    """Execute end-to-end operational quality audit with persistence and exit codes.

    Args:
        source: "demo", "file", or "snowflake".
        input_file: Path to file when source="file".
        output_dir: Directory where timestamped reports are persisted.
        check_network: If True, test external HTTP link reachability.
        stale_threshold_days: Days after which verification is considered stale.
        export_csv: If True, also export a CSV report.
        fail_on_warnings: If True, return EXIT_QUALITY_WARNINGS when warnings exist.
        notification_dispatcher: Optional dispatcher for alerts.

    Returns:
        Tuple of (exit_code, DataQualityReport or None, report_json_path or None)
    """
    start_time = time.perf_counter()
    dispatcher = notification_dispatcher or NotificationDispatcher()
    out_dir = output_dir or monitoring_config.reports_dir
    stale_days = stale_threshold_days or quality_config.stale_threshold_days

    # 1. Acquire process lock
    lock_file = out_dir / ".audit_runner.lock"
    try:
        with audit_process_lock(lock_file):
            # 2. Fetch records
            records: List[Dict[str, Any]] = []
            try:
                if source == "snowflake":
                    if not snowflake_config.is_configured:
                        raise RuntimeError(
                            "Snowflake credentials are not configured in environment."
                        )
                    records = fetch_opportunities_for_audit()
                elif source == "file":
                    file_path = Path(input_file or "data/raw_opportunities.json")
                    if not file_path.exists():
                        raise FileNotFoundError(f"Input file not found: {file_path}")
                    records = load_raw_records_from_file(file_path)
                elif source == "demo":
                    records = get_demo_opportunities()
                else:
                    raise ValueError(f"Unknown data source: '{source}'")
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                err_msg = sanitize_text(str(exc))
                op_logger.log(
                    component="audit_runner",
                    operation="fetch_records",
                    status="FAILURE",
                    duration_ms=duration_ms,
                    error=err_msg,
                )
                dispatcher.notify_execution_failure(source, err_msg)
                return EXIT_EXECUTION_FAILURE, None, None

            # 3. Execute quality pipeline
            report = run_quality_pipeline(
                records=records,
                report_scope=f"operational_runner:{source}",
                dry_run=True,
                check_urls=check_network,
                network_enabled=check_network,
                stale_threshold_days=stale_days,
            )

            # 4. Save timestamped JSON report
            out_dir.mkdir(parents=True, exist_ok=True)
            timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            json_filename = f"audit_report_{source}_{timestamp_str}.json"
            json_path = out_dir / json_filename

            report_dict = report.to_dict()
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            report_dict["execution_metadata"] = {
                "runner_source": source,
                "duration_ms": round(duration_ms, 2),
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "check_network": check_network,
                "stale_threshold_days": stale_days,
            }

            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, default=str)

            # Optional CSV export
            if export_csv:
                csv_filename = f"audit_report_{source}_{timestamp_str}.csv"
                csv_path = out_dir / csv_filename
                report.export_csv(str(csv_path))

            # 5. Evaluate alert rules & notifications
            dispatcher.evaluate_audit_results(
                total_records=report.summary.total_records,
                fail_count=report.summary.failed_records,
                warning_count=report.summary.warning_records,
                stale_count=report.summary.stale_verification_records,
                broken_link_count=report.summary.broken_link_candidates,
                source=source,
            )

            # 6. Operational logging
            op_logger.log(
                component="audit_runner",
                operation="run_operational_audit",
                status="SUCCESS" if report.summary.failed_records == 0 else "WARNING",
                duration_ms=duration_ms,
                records_processed=report.summary.total_records,
                warnings_count=report.summary.warning_records,
                errors_count=report.summary.failed_records,
                message=f"Audit completed: {report.summary.passed_records} pass, {report.summary.warning_records} warn, {report.summary.failed_records} fail.",
            )

            # 7. Compute deterministic exit code
            if report.summary.failed_records > 0:
                return EXIT_BLOCKING_DATA_ERRORS, report, json_path
            elif fail_on_warnings and report.summary.warning_records > 0:
                return EXIT_QUALITY_WARNINGS, report, json_path
            else:
                return EXIT_SUCCESS, report, json_path

    except AuditLockAcquisitionError as lock_err:
        op_logger.log(
            component="audit_runner",
            operation="acquire_lock",
            status="FAILURE",
            error=str(lock_err),
        )
        return EXIT_EXECUTION_FAILURE, None, None


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for operational audit runner."""
    parser = argparse.ArgumentParser(
        prog="python -m src.quality.runner",
        description="OpportunityLens Operational Quality Audit Runner",
    )
    parser.add_argument(
        "--source",
        choices=["snowflake", "file", "demo"],
        default="demo",
        help="Data source to audit (default: demo)",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default=None,
        help="Path to JSON or CSV file if source=file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=f"Directory for timestamped report storage (default: {monitoring_config.reports_dir})",
    )
    parser.add_argument(
        "--check-urls",
        action="store_true",
        default=False,
        help="Opt-in: check live external opportunity source links",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        default=True,
        help="Enforce offline execution (default: True)",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=None,
        help="Stale verification threshold in days (default: 30)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        default=False,
        help="Export CSV report alongside JSON",
    )
    parser.add_argument(
        "--fail-on-warnings",
        action="store_true",
        default=False,
        help="Return exit code 3 if any quality warnings exist",
    )

    args = parser.parse_args(argv)

    check_network = args.check_urls and not args.no_network
    out_dir = Path(args.output_dir) if args.output_dir else monitoring_config.reports_dir

    exit_code, report, report_path = run_operational_audit(
        source=args.source,
        input_file=args.input_file,
        output_dir=out_dir,
        check_network=check_network,
        stale_threshold_days=args.stale_days,
        export_csv=args.csv,
        fail_on_warnings=args.fail_on_warnings,
    )

    if report is not None:
        print(f"Audit completed for source '{args.source}'.")
        print(
            f"Summary: {report.summary.total_records} records | "
            f"{report.summary.passed_records} PASS | "
            f"{report.summary.warning_records} WARN | "
            f"{report.summary.failed_records} FAIL"
        )
        if report_path:
            print(f"Persisted report: {report_path}")
    else:
        print(f"Audit execution aborted with exit code {exit_code}.", file=sys.stderr)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
