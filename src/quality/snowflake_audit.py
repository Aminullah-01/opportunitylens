"""Safe, read-only Snowflake opportunity data auditing."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from snowflake.connector import DictCursor

from src.config import snowflake_config
from src.db import get_connection

logger = logging.getLogger(__name__)


def fetch_opportunities_for_audit(
    opportunity_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Retrieve opportunity records from Snowflake in a strictly read-only parameterized manner.

    Args:
        opportunity_id: Optional specific opportunity ID to audit.
        status_filter: Optional verification status to filter by (e.g. 'NEEDS_REVIEW').
        limit: Optional maximum number of records to retrieve.

    Returns:
        List of lowercase-keyed opportunity dictionaries.

    Raises:
        RuntimeError: If Snowflake is not configured or connection fails.
    """
    if not snowflake_config.is_configured:
        raise RuntimeError(
            "Snowflake credentials are not configured. Please check your .env file."
        )

    query_parts = [
        "SELECT",
        "    OPPORTUNITY_ID,",
        "    TITLE,",
        "    CATEGORY,",
        "    ORGANIZATION,",
        "    DESCRIPTION,",
        "    ELIGIBILITY,",
        "    EDUCATION_LEVEL,",
        "    LOCATION,",
        "    DEADLINE,",
        "    SOURCE_URL,",
        "    VERIFIED_AT,",
        "    STATUS",
        "FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES",
    ]

    where_clauses: List[str] = []
    params: List[Any] = []

    if opportunity_id and opportunity_id.strip():
        where_clauses.append("OPPORTUNITY_ID = %s")
        params.append(opportunity_id.strip())

    if status_filter and status_filter.strip():
        where_clauses.append("STATUS = %s")
        params.append(status_filter.strip().upper())

    if where_clauses:
        query_parts.append("WHERE " + " AND ".join(where_clauses))

    query_parts.append("ORDER BY DEADLINE ASC NULLS LAST")

    if limit and limit > 0:
        query_parts.append("LIMIT %s")
        params.append(int(limit))

    sql_statement = "\n".join(query_parts)

    connection = get_connection()
    try:
        with connection.cursor(DictCursor) as cursor:
            cursor.execute(sql_statement, tuple(params))
            rows = cursor.fetchall()

        records: List[Dict[str, Any]] = []
        for row in rows:
            record = {str(k).lower(): v for k, v in row.items()}
            records.append(record)

        return records

    except Exception as exc:
        logger.error("Failed to execute read-only Snowflake audit query: %s", exc)
        raise RuntimeError(f"Snowflake audit query failed: {exc}") from exc

    finally:
        try:
            connection.close()
        except Exception:
            pass
