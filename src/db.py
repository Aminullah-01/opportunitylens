
"""Snowflake data access for OpportunityLens."""

from datetime import date, datetime, timezone

import snowflake.connector
from snowflake.connector import DictCursor

from src.config import snowflake_config


def get_connection():
    """Create a Snowflake connection."""
    if not snowflake_config.is_configured:
        raise RuntimeError(
            "Snowflake credentials are not fully configured."
        )

    return snowflake.connector.connect(
        account=snowflake_config.account,
        user=snowflake_config.user,
        password=snowflake_config.password,
        warehouse=snowflake_config.warehouse,
        database=snowflake_config.database,
        schema=snowflake_config.schema,
        role=snowflake_config.role or None,
    )


def get_application_status(deadline):
    """Determine whether an opportunity is open or closed."""
    if deadline is None:
        return "Unknown"

    if isinstance(deadline, datetime):
        deadline = deadline.date()

    if isinstance(deadline, str):
        try:
            deadline = date.fromisoformat(deadline[:10])
        except (ValueError, TypeError):
            return "Unknown"

    today = datetime.now(timezone.utc).date()

    if deadline < today:
        return "Closed"

    if (deadline - today).days <= 7:
        return "Closing Soon"

    return "Open"


def fetch_opportunities():
    """Retrieve opportunity records from Snowflake."""
    connection = get_connection()

    try:
        with connection.cursor(DictCursor) as cursor:
            cursor.execute("""
                SELECT
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
                FROM OPPORTUNITYLENS_DB.APP.OPPORTUNITIES
                ORDER BY DEADLINE ASC NULLS LAST
            """)

            rows = cursor.fetchall()

        opportunities = []

        for row in rows:
            record = {
                key.lower(): value
                for key, value in row.items()
            }

            opportunities.append({
                "opportunity_id": record["opportunity_id"],
                "title": record["title"] or "Untitled opportunity",
                "category": record["category"] or "Other",
                "organization": (
                    record["organization"] or "Not specified"
                ),
                "description": (
                    record["description"] or "No description provided."
                ),
                "eligibility": (
                    record["eligibility"] or "Check the official source."
                ),
                "education_level": (
                    record["education_level"] or "Not specified"
                ),
                "location": record["location"] or "Not specified",
                "deadline": record["deadline"],
                "source_url": record["source_url"] or "",
                "verified_at": record["verified_at"],
                "verification_status": record["status"] or "UNVERIFIED",
                "status": get_application_status(record["deadline"]),
                "is_sample_data": False,
            })

        return opportunities

    finally:
        connection.close()
