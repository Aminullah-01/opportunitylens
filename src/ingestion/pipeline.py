"""End-to-end opportunity ingestion pipeline for OpportunityLens.

Handles file loading, data validation, deduplication, and idempotent Snowflake
loading using parameterized SQL MERGE operations.
"""

from __future__ import annotations

import csv
import json
from datetime import date
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
    TITLE = COALESCE(source.TITLE, target.TITLE),
    CATEGORY = COALESCE(source.CATEGORY, target.CATEGORY),
    ORGANIZATION = CASE
        WHEN LENGTH(COALESCE(source.ORGANIZATION, '')) >= LENGTH(COALESCE(target.ORGANIZATION, ''))
        THEN source.ORGANIZATION
        ELSE target.ORGANIZATION
    END,
    DESCRIPTION = CASE
        WHEN LENGTH(COALESCE(source.DESCRIPTION, '')) >= LENGTH(COALESCE(target.DESCRIPTION, ''))
        THEN source.DESCRIPTION
        ELSE target.DESCRIPTION
    END,
    ELIGIBILITY = CASE
        WHEN LENGTH(COALESCE(source.ELIGIBILITY, '')) >= LENGTH(COALESCE(target.ELIGIBILITY, ''))
        THEN source.ELIGIBILITY
        ELSE target.ELIGIBILITY
    END,
    EDUCATION_LEVEL = CASE
        WHEN source.EDUCATION_LEVEL IS NOT NULL AND source.EDUCATION_LEVEL != 'All Levels'
        THEN source.EDUCATION_LEVEL
        ELSE COALESCE(target.EDUCATION_LEVEL, source.EDUCATION_LEVEL)
    END,
    LOCATION = CASE
        WHEN source.LOCATION IS NOT NULL AND source.LOCATION NOT IN ('Nigeria', 'Nationwide')
        THEN source.LOCATION
        ELSE COALESCE(target.LOCATION, source.LOCATION)
    END,
    DEADLINE = COALESCE(source.DEADLINE, target.DEADLINE),
    SOURCE_URL = COALESCE(source.SOURCE_URL, target.SOURCE_URL),
    VERIFIED_AT = COALESCE(source.VERIFIED_AT, target.VERIFIED_AT),
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


def merge_normalized_records(
    existing: NormalizedOpportunity, incoming: NormalizedOpportunity
) -> NormalizedOpportunity:
    """Merge an incoming record into an existing normalized record preserving richer data.

    Preserves existing non-null deadline, longer descriptions, more specific eligibility
    and education level, and most recent verification timestamp.
    """
    title = incoming.title if incoming.title else existing.title
    category = incoming.category if incoming.category else existing.category
    org = (
        incoming.organization
        if len(incoming.organization) >= len(existing.organization)
        else existing.organization
    )
    desc = (
        incoming.description
        if len(incoming.description) >= len(existing.description)
        else existing.description
    )
    elig = (
        incoming.eligibility
        if len(incoming.eligibility) >= len(existing.eligibility)
        else existing.eligibility
    )

    if incoming.education_level and incoming.education_level != "All Levels":
        edu = incoming.education_level
    else:
        edu = existing.education_level or incoming.education_level

    if incoming.location and incoming.location not in ("Nationwide", "Nigeria"):
        loc = incoming.location
    elif existing.location and existing.location not in ("Nationwide", "Nigeria"):
        loc = existing.location
    else:
        loc = incoming.location or existing.location

    # Preserve non-null deadline if incoming is None
    deadline = incoming.deadline if incoming.deadline is not None else existing.deadline
    source_url = incoming.source_url or existing.source_url

    if incoming.verified_at and existing.verified_at:
        verified_at = max(incoming.verified_at, existing.verified_at)
    else:
        verified_at = incoming.verified_at or existing.verified_at

    # Preserve verification status
    if incoming.status == "VERIFIED" or existing.status == "VERIFIED":
        status = "VERIFIED"
    elif incoming.status == "NEEDS_REVIEW" or existing.status == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"
    else:
        status = incoming.status or existing.status

    return NormalizedOpportunity(
        opportunity_id=existing.opportunity_id,
        title=title,
        category=category,
        organization=org,
        description=desc,
        eligibility=elig,
        education_level=edu,
        location=loc,
        deadline=deadline,
        source_url=source_url,
        verified_at=verified_at,
        status=status,
    )


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
            # Merge with existing record preserving richer data
            valid_records_by_id[existing_id] = merge_normalized_records(
                valid_records_by_id[existing_id], record
            )
            in_batch_duplicates += 1
            continue

        if record.opportunity_id in valid_records_by_id:
            # Duplicate ID: merge with existing
            valid_records_by_id[record.opportunity_id] = merge_normalized_records(
                valid_records_by_id[record.opportunity_id], record
            )
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
    report.records = valid_records

    if dry_run or not valid_records:
        return report

    try:
        inserted, updated = execute_snowflake_merge(valid_records, connection=connection)
        report.inserted = inserted
        report.updated = updated
    except Exception as exc:
        report.errors.append(f"Snowflake database loading error: {exc}")

    return report


def run_sources_ingestion(
    adapters: List[Any],
    limit_per_source: Optional[int] = None,
    connection=None,
    dry_run: bool = False,
) -> IngestionReport:
    """Run real external opportunity collection across multiple source adapters.

    Args:
        adapters: List of initialized BaseSourceAdapter instances.
        limit_per_source: Optional record limit per individual source.
        connection: Optional Snowflake connection for testing or overrides.
        dry_run: If True, collects and normalizes without writing to Snowflake.

    Returns:
        IngestionReport with detailed per-source metrics, deduplication counts,
        and database upsert outcomes.
    """
    report = IngestionReport(dry_run=dry_run)
    collected_records: List[NormalizedOpportunity] = []

    for adapter in adapters:
        res = adapter.collect(limit=limit_per_source)
        report.source_summaries.append({
            "source_id": res.source_id,
            "source_name": res.source_name,
            "success": res.success,
            "total_fetched": res.total_fetched,
            "parsed_count": res.parsed_count,
            "error_count": res.error_count,
            "error_message": res.error_message,
            "duration_seconds": res.duration_seconds,
        })
        # Always retain collected records from this source, even if partial errors occurred
        if res.records:
            collected_records.extend(res.records)

        # Clearly report partial errors or failures so the run is not falsely marked clean
        if not res.success or res.has_partial_errors or res.error_message:
            err_msg = (
                res.error_message
                or f"{res.source_name}: encountered {res.error_count} error(s) or partial timeouts"
            )
            report.errors.append(f"Source [{res.source_id}] warning/error: {err_msg}")

    report.total_records = len(collected_records)

    # Perform cross-source deduplication preserving richer data
    valid_by_id: Dict[str, NormalizedOpportunity] = {}
    seen_org_title: Dict[Tuple[str, str], str] = {}
    duplicates = 0

    for rec in collected_records:
        org_title_key = (rec.organization.strip().lower(), rec.title.strip().lower())
        if org_title_key in seen_org_title:
            existing_id = seen_org_title[org_title_key]
            valid_by_id[existing_id] = merge_normalized_records(
                valid_by_id[existing_id], rec
            )
            duplicates += 1
            continue

        if rec.opportunity_id in valid_by_id:
            valid_by_id[rec.opportunity_id] = merge_normalized_records(
                valid_by_id[rec.opportunity_id], rec
            )
            duplicates += 1
            continue

        seen_org_title[org_title_key] = rec.opportunity_id
        valid_by_id[rec.opportunity_id] = rec

    final_records = list(valid_by_id.values())
    report.valid_records = len(final_records)
    report.skipped = duplicates
    report.records = final_records

    if dry_run or not final_records:
        return report

    try:
        inserted, updated = execute_snowflake_merge(final_records, connection=connection)
        report.inserted = inserted
        report.updated = updated
    except Exception as exc:
        report.errors.append(f"Snowflake database loading error: {exc}")

    return report

