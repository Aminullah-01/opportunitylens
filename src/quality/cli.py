"""Command-line interface for Phase 5 data quality, freshness, and link verification."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List

from src.config import snowflake_config
from src.ingestion.pipeline import load_raw_records_from_file
from src.quality.models import DataQualityReport, Severity
from src.quality.pipeline import run_quality_pipeline
from src.quality.snowflake_audit import fetch_opportunities_for_audit


def print_report_summary(report: DataQualityReport) -> None:
    """Print clean, formatted terminal summary of data quality audit results."""
    s = report.summary
    dry_label = " [DRY RUN — READ ONLY]" if report.dry_run else ""
    print(f"\n=======================================================")
    print(f"🎯 OpportunityLens Data Quality & Verification Audit{dry_label}")
    print(f"Generated at: {report.generated_at} (UTC) | Scope: {report.report_scope}")
    print(f"=======================================================")
    print(f"Total Records Audited:         {s.total_records}")
    print(f"  ✓ Quality Passed:             {s.passed_records}")
    print(f"  ⚠️ Quality Warnings:          {s.warning_records}")
    print(f"  ❌ Quality Errors:            {s.failed_records}")
    print(f"  🔁 Potential Duplicates:      {s.potential_duplicates}")
    print(f"-------------------------------------------------------")
    print(f"Application Lifecycle Breakdown:")
    print(f"  🟢 Open:                      {s.open_opportunities}")
    print(f"  ⏳ Closing Soon (<= 7 days):  {s.closing_soon_opportunities}")
    print(f"  🔴 Expired:                   {s.expired_opportunities}")
    print(f"  ❓ Unknown / Unspecified:     {s.unknown_deadline_opportunities}")
    print(f"-------------------------------------------------------")
    print(f"Verification & Freshness Breakdown:")
    print(f"  🕒 Stale Verifications (>30d):{s.stale_verification_records}")
    print(f"  🌐 Source URLs Checked:       {s.source_urls_checked}")
    print(f"  ✅ Reachable URLs:            {s.reachable_sources}")
    print(f"  🚫 Broken Links:              {s.broken_link_candidates}")
    print(f"  🔒 Unverifiable / Blocked:    {s.unverifiable_sources}")
    print(f"=======================================================\n")

    if report.issues:
        print(f"📋 Detected Issues ({len(report.issues)} total):")
        # Show top issues (max 20) in terminal
        display_issues = report.issues[:20]
        for issue in display_issues:
            icon = "❌" if issue.severity == Severity.ERROR else ("⚠️" if issue.severity == Severity.WARNING else "ℹ️")
            print(f"  {icon} [{issue.severity.value}] ID: {issue.opportunity_id} | Field: {issue.field_name}")
            print(f"     Code: {issue.issue_code} - {issue.message}")
            print(f"     Action: {issue.suggested_action}")
        if len(report.issues) > 20:
            print(f"\n  ... and {len(report.issues) - 20} more issues. Use --output to export full report.")
    else:
        print("✓ All records passed data quality and freshness checks with zero issues!")


def main(argv: List[str] | None = None) -> int:
    """CLI entrypoint for data quality verification."""
    parser = argparse.ArgumentParser(
        description="Audit OpportunityLens data quality, deadline freshness, and source URLs."
    )
    parser.add_argument(
        "--source",
        choices=["snowflake", "file", "demo"],
        default="snowflake" if snowflake_config.is_configured else "file",
        help="Data source to audit (default: snowflake if configured, else file)",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="data/raw_opportunities.json",
        help="Path to JSON or CSV file if source=file (default: data/raw_opportunities.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run audit in read-only mode without mutating database (default: True).",
    )
    parser.add_argument(
        "--check-urls",
        action="store_true",
        default=False,
        help="Opt-in to performing live HTTP reachability checks on source URLs (default: False).",
    )
    parser.add_argument(
        "--no-network",
        action="store_true",
        default=False,
        help="Explicitly disable all network operations and URL checks.",
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=30,
        help="Number of days after which verification metadata is marked stale (default: 30).",
    )
    parser.add_argument(
        "--opportunity-id",
        type=str,
        default=None,
        help="Filter audit to a specific opportunity ID.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path to save audit report (JSON or CSV).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv"],
        default="json",
        help="Export format if --output is specified (default: json).",
    )

    args = parser.parse_args(argv)

    # Determine whether network is enabled
    network_enabled = args.check_urls and not args.no_network

    # 1. Load records according to selected source
    records: List[Dict[str, Any]] = []
    scope_desc = f"{args.source}"

    if args.source == "snowflake":
        print("Connecting to Snowflake (read-only audit)...")
        try:
            records = fetch_opportunities_for_audit(
                opportunity_id=args.opportunity_id
            )
            scope_desc = f"snowflake (OPPORTUNITYLENS_DB.APP.OPPORTUNITIES, {len(records)} rows)"
        except Exception as exc:
            print(f"❌ Error connecting to Snowflake: {exc}", file=sys.stderr)
            print("Falling back to local data file...", file=sys.stderr)
            input_p = Path(args.input_file)
            if input_p.exists():
                records = load_raw_records_from_file(input_p)
                scope_desc = f"file fallback ({input_p})"
            else:
                return 1

    elif args.source == "file":
        input_p = Path(args.input_file)
        if not input_p.exists():
            print(f"❌ Error: Input file '{input_p}' not found.", file=sys.stderr)
            return 1
        records = load_raw_records_from_file(input_p)
        scope_desc = f"file ({input_p})"

    elif args.source == "demo":
        from src.demo_data import get_demo_opportunities
        records = get_demo_opportunities()
        scope_desc = "demo in-memory records"

    # Filter by opportunity_id if specified and not already filtered
    if args.opportunity_id and records:
        records = [
            r for r in records
            if str(r.get("opportunity_id", "")).strip().lower() == args.opportunity_id.strip().lower()
        ]

    # 2. Execute Quality Pipeline
    report = run_quality_pipeline(
        records=records,
        report_scope=scope_desc,
        dry_run=args.dry_run,
        check_urls=args.check_urls and network_enabled,
        network_enabled=network_enabled,
        stale_threshold_days=args.stale_days,
    )

    # 3. Print terminal report
    print_report_summary(report)

    # 4. Save output file if requested
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if args.format == "json":
            out_path.write_text(report.to_json(), encoding="utf-8")
            print(f"\n💾 Saved JSON audit report to: {out_path}")
        elif args.format == "csv":
            rows = report.to_csv_rows()
            if rows:
                with open(out_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)
            else:
                out_path.write_text("No records audited.\n", encoding="utf-8")
            print(f"\n💾 Saved CSV audit report to: {out_path}")

    # Return exit code: 1 if blocking errors exist, 0 otherwise
    if report.summary.failed_records > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
