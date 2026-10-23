"""Command-line interface for the OpportunityLens real opportunity ingestion pipeline."""

from __future__ import annotations

import argparse
from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import List, Optional

from src.config import snowflake_config
from src.ingestion.pipeline import run_ingestion_pipeline, run_sources_ingestion
from src.ingestion.sources import (
    get_adapter,
    get_all_adapters,
    get_enabled_adapters,
    list_sources_summary,
)


def _json_serial(obj):
    """JSON serializer helper for date/datetime objects."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def print_sources_table() -> None:
    """Print formatted catalog table of all registered source adapters."""
    summaries = list_sources_summary()
    print("=== Registered OpportunityLens Source Adapters ===")
    print(f"{'Source ID':<22} {'Status':<10} {'Category':<18} {'Source Name'}")
    print("-" * 80)
    for s in summaries:
        status_str = f"[{s['status']}]"
        print(f"{s['source_id']:<22} {status_str:<10} {s['default_category']:<18} {s['source_name']}")
        if s.get("disabled_reason"):
            print(f"   ↳ Note: {s['disabled_reason']}")
    print("-" * 80)


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for running opportunity ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest and validate real opportunity records into Snowflake or local files."
    )

    # Source selection options
    src_group = parser.add_argument_group("Source Selection")
    src_group.add_argument(
        "--list-sources",
        action="store_true",
        help="Display all available external source adapters and exit.",
    )
    src_group.add_argument(
        "--all-enabled",
        action="store_true",
        help="Collect real opportunities from all enabled external sources.",
    )
    src_group.add_argument(
        "--source",
        "-s",
        type=str,
        help="Collect opportunities from a specific registered source identifier (e.g. leep_jobs, ptdf_scholarships).",
    )
    src_group.add_argument(
        "--input-file",
        "-i",
        type=str,
        help="Optional path to legacy JSON or CSV fixture file for offline/test ingestion.",
    )

    # Execution controls
    exec_group = parser.add_argument_group("Execution Controls")
    exec_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Run collection, normalization, and deduplication without modifying Snowflake data warehouse.",
    )
    exec_group.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Maximum number of records to collect per individual source.",
    )
    exec_group.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Optional file path to export collected and normalized records as JSON.",
    )
    exec_group.add_argument(
        "--no-network",
        action="store_true",
        help="Disable outbound network requests (fails if source requires live HTTP collection).",
    )
    exec_group.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Overall HTTP request timeout in seconds.",
    )
    exec_group.add_argument(
        "--connect-timeout",
        type=float,
        default=None,
        help="HTTP connection establishment timeout in seconds (default: 5.0).",
    )
    exec_group.add_argument(
        "--read-timeout",
        type=float,
        default=None,
        help="HTTP response read timeout in seconds (default: 25.0).",
    )
    exec_group.add_argument(
        "--retries",
        type=int,
        default=None,
        help="Maximum bounded retry attempts with exponential backoff (default: 3).",
    )

    args = parser.parse_args(argv)

    # 1. Handle --list-sources
    if args.list_sources:
        print_sources_table()
        return 0

    # 2. Determine mode: Source adapters vs Input file
    network_enabled = not args.no_network

    if args.all_enabled or args.source:
        adapters = []
        if args.source:
            try:
                adapter = get_adapter(
                    args.source,
                    network_enabled=network_enabled,
                    timeout_seconds=args.timeout,
                    connect_timeout_seconds=args.connect_timeout,
                    read_timeout_seconds=args.read_timeout,
                    max_retries=args.retries,
                )
                if not adapter.enabled:
                    print(f"Warning: Adapter '{args.source}' is currently disabled: {adapter.disabled_reason}")
                adapters.append(adapter)
            except KeyError as err:
                print(f"Error: {err}")
                return 1
        else:
            adapters = get_enabled_adapters(
                network_enabled=network_enabled,
                timeout_seconds=args.timeout,
                connect_timeout_seconds=args.connect_timeout,
                read_timeout_seconds=args.read_timeout,
                max_retries=args.retries,
            )
            if not adapters:
                print("No enabled source adapters available.")
                return 1

        print("Starting OpportunityLens Real-Data Ingestion...")
        print(f"Target sources: {[a.source_id for a in adapters]}")
        print(f"Dry run mode:   {args.dry_run}")
        print(f"Network enabled: {network_enabled}")
        print(f"Snowflake warehouse: {'Configured' if snowflake_config.is_configured else 'Not configured'}\n")

        report = run_sources_ingestion(
            adapters=adapters,
            limit_per_source=args.limit,
            dry_run=args.dry_run,
        )

    elif args.input_file:
        input_path = Path(args.input_file)
        print("Starting OpportunityLens File Ingestion Pipeline...")
        print(f"Source file:  {input_path}")
        print(f"Dry run mode: {args.dry_run}\n")

        report = run_ingestion_pipeline(input_path, dry_run=args.dry_run)

    else:
        # Default behavior if neither flag passed: print help and exit
        print("Notice: No ingestion source specified. Specify --all-enabled, --source <name>, or --input-file <path>.")
        print("Use --list-sources to see all registered external adapters, or --help for full usage instructions.\n")
        print_sources_table()
        return 0

    # Print summary
    print(report.summary_text())

    # Export to output file if requested
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        export_payload = [
            rec.to_snowflake_dict() for rec in getattr(report, "records", [])
        ]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2, default=_json_serial)
        print(f"\n✓ Exported {len(export_payload)} normalized records to: {out_path}")

    if report.errors:
        print("\nIngestion completed with warnings or errors.")
        return 1

    print("\n✓ Ingestion completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
