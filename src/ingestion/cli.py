"""Command-line interface for the OpportunityLens ingestion pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.ingestion.pipeline import run_ingestion_pipeline


def main() -> int:
    """CLI entrypoint for running opportunity ingestion."""
    parser = argparse.ArgumentParser(
        description="Ingest and validate opportunity records into Snowflake."
    )
    parser.add_argument(
        "--input-file",
        "-i",
        type=str,
        default="data/raw_opportunities.json",
        help="Path to source JSON or CSV file (default: data/raw_opportunities.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate records and print report without modifying Snowflake database.",
    )

    args = parser.parse_args()
    input_path = Path(args.input_file)

    print(f"Starting OpportunityLens Ingestion Pipeline...")
    print(f"Source file: {input_path}")
    print(f"Dry run mode: {args.dry_run}\n")

    report = run_ingestion_pipeline(input_path, dry_run=args.dry_run)
    print(report.summary_text())

    if report.errors:
        print("\nIngestion completed with errors.")
        return 1

    print("\nIngestion completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
