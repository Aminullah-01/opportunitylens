"""End-to-end opportunity ingestion pipeline for OpportunityLens.

Handles file loading, data validation, deduplication, and idempotent Snowflake
loading using parameterized SQL MERGE operations.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.db import get_connection
from src.ingestion.models import IngestionReport, NormalizedOpportunity
from src.ingestion.validator import validate_raw_record

MERGE_OPPORTUNITY_SQL = """
MERGE INTO OPPORTUNITYLENS_DB.APP.OPPORTUNITIES AS target
USING (
    SELECT %s AS OPPORTUNITY_ID,
           %s AS TITLE,
           %s AS CATEGORY,
           %s AS ORGANIZATION,
           %s AS DESCRIPTION,
           %s AS ELIGIBILITY,
           %s AS EDUCATION_LEVEL,
           %s AS LOCATION,
           %s AS DEADLINE,
           %s AS SOURCE_URL,
           %s AS VERIFIED_AT,
           %s AS STATUS
) AS source
ON target.OPPORTUNITY_ID = source.OPPORTUNITY_ID
WHEN MATCHED THEN UPDATE SET
    TITLE = source.TITLE,
    CATEGORY = source.CATEGORY,
    ORGANIZATION = source.ORGANIZATION,
    DESCRIPTION = source.DESCRIPTION,
    ELIGIBILITY = source.ELIGIBILITY,
    EDUCATION_LEVEL = source.EDUCATION_LEVEL,
    LOCATION = source.LOCATION,
    DEADLINE = source.DEADLINE,
    SOURCE_URL = source.SOURCE_URL,
    VERIFIED_AT = source.VERIFIED_AT,
    STATUS = source.STATUS
WHEN NOT MATCHED THEN INSERT (
    OPPORTUNITY_ID,
    TITLE,
    CATEGORY,
    ORGANIZATION,
    DESCRIPTION,
    ELIGIBILITY,
    EDUCATION_LEVEL,
    LOCATION,
    DEADLINE,
    SOURCE_URL,
    VERIFIED_AT,
    STATUS
) VALUES (
    source.OPPORTUNITY_ID,
    source.TITLE,
    source.CATEGORY,
    source.ORGANIZATION,
    source.DESCRIPTION,
    source.ELIGIBILITY,
    source.EDUCATION_LEVEL,
    source.LOCATION,
    source.DEADLINE,
    source.SOURCE_URL,
    source.VERIFIED_AT,
    source.STATUS
);
"""


def load_raw_records_from_file(file_path: str | Path) -> List[Dict[str, Any]]:
    """Load raw opportunity records from JSON or CSV file.

    Args:
        file_path: Path to raw data file.

    Returns:
        List of raw opportunity dictionaries.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Source file not found at: {file_path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                raise ValueError("JSON file root must contain a list of objects.")
            return data
    elif suffix == ".csv":
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    else:
        raise ValueError(f"Unsupported file format '{suffix}'. Use .json or .csv.")


def validate_and_deduplicate(
    raw_records: List[Dict[str, Any]]
) -> Tuple[List[NormalizedOpportunity], List[Dict[str, Any]], int]:
    """Validate raw records and eliminate in-batch duplicates.

    Args:
        raw_records: List of raw opportunity dictionaries.

    Returns:
        Tuple of (valid_unique_records, rejection_details, duplicates_skipped_in_batch).
    """
    valid_records_by_id: Dict[str, NormalizedOpportunity] = {}
    seen_org_title_keys: Dict[Tuple[str, str], str] = {}
    rejections: List[Dict[str, Any]] = []
    in_batch_duplicates = 0

    for raw in raw_records:
        res = validate_raw_record(raw)
        if not res.is_valid:
            rejections.append({
                "raw_id": res.raw_id,
                "reasons": res.errors,
                "raw_record": raw,
            })
            continue

        record = res.record
        assert record is not None

        # Check deduplication by normalized org + title key
        dedup_key = (record.organization.strip().lower(), record.title.strip().lower())
        if dedup_key in seen_org_title_keys:
            existing_id = seen_org_title_keys[dedup_key]
            # Replace previous record with latest updated version
            valid_records_by_id[existing_id] = record
            in_batch_duplicates += 1
            continue

        if record.opportunity_id in valid_records_by_id:
            # Duplicate ID: update to latest
            valid_records_by_id[record.opportunity_id] = record
            in_batch_duplicates += 1
            continue

        seen_org_title_keys[dedup_key] = record.opportunity_id
        valid_records_by_id[record.opportunity_id] = record

    return list(valid_records_by_id.values()), rejections, in_batch_duplicates


def execute_snowflake_merge(
    records: List[NormalizedOpportunity], connection=None
) -> Tuple[int, int]:
    """Load normalized records into Snowflake using parameterized MERGE.

    Args:
        records: List of normalized opportunities.
        connection: Optional existing Snowflake connection (for testing/mocking).

    Returns:
        Tuple of (inserted_count, updated_count).
    """
    if not records:
        return 0, 0

    close_connection = False
    if connection is None:
        connection = get_connection()
        close_connection = True

    total_inserted = 0
    total_updated = 0

    try:
        cursor = connection.cursor()
        try:
            for rec in records:
                # Format parameters safely
                deadline_val = rec.deadline.isoformat() if rec.deadline else None
                verified_val = (
                    rec.verified_at.strftime("%Y-%m-%d %H:%M:%S")
                    if rec.verified_at
                    else None
                )

                params = (
                    rec.opportunity_id,
                    rec.title,
                    rec.category,
                    rec.organization,
                    rec.description,
                    rec.eligibility,
                    rec.education_level,
                    rec.location,
                    deadline_val,
                    rec.source_url,
                    verified_val,
                    rec.status,
                )

                cursor.execute(MERGE_OPPORTUNITY_SQL, params)
                row = cursor.fetchone()
                if row:
                    # Snowflake returns (rows_inserted, rows_updated)
                    try:
                        total_inserted += int(row[0])
                        total_updated += int(row[1])
                    except (IndexError, ValueError, TypeError):
                        pass
        finally:
            cursor.close()
    finally:
        if close_connection:
            connection.close()

    return total_inserted, total_updated


def run_ingestion_pipeline(
    file_path: str | Path,
    connection=None,
    dry_run: bool = False,
) -> IngestionReport:
    """Run the complete ingestion pipeline on a source file.

    Args:
        file_path: Path to source data file.
        connection: Optional Snowflake connection.
        dry_run: If True, validates and reports without executing Snowflake MERGE.

    Returns:
        IngestionReport summarizing pipeline execution results.
    """
    report = IngestionReport(dry_run=dry_run)

    try:
        raw_records = load_raw_records_from_file(file_path)
    except Exception as exc:
        report.errors.append(f"Failed to load source file: {exc}")
        return report

    report.total_records = len(raw_records)
    valid_records, rejections, in_batch_dups = validate_and_deduplicate(raw_records)

    report.valid_records = len(valid_records)
    report.rejected_records = len(rejections)
    report.rejection_details = rejections
    report.skipped = in_batch_dups

    if dry_run or not valid_records:
        return report

    try:
        inserted, updated = execute_snowflake_merge(valid_records, connection=connection)
        report.inserted = inserted
        report.updated = updated
    except Exception as exc:
        report.errors.append(f"Snowflake database loading error: {exc}")

    return report
