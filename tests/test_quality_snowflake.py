"""Unit tests for safe, read-only Snowflake audit query execution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from src.quality.snowflake_audit import fetch_opportunities_for_audit


def test_fetch_opportunities_unconfigured_error():
    """Verify that fetch raises informative RuntimeError when Snowflake credentials are missing."""
    with patch("src.quality.snowflake_audit.snowflake_config") as mock_conf:
        mock_conf.is_configured = False
        with pytest.raises(RuntimeError, match="Snowflake credentials are not configured"):
            fetch_opportunities_for_audit()


def test_fetch_opportunities_successful_mock_query():
    """Verify query structure and parameterization with mocked Snowflake connector."""
    mock_rows = [
        {
            "OPPORTUNITY_ID": "OPP-001",
            "TITLE": "Test Opportunity",
            "CATEGORY": "Scholarships",
            "ORGANIZATION": "Test Org",
            "DESCRIPTION": "Desc",
            "ELIGIBILITY": "Elig",
            "EDUCATION_LEVEL": "Undergraduate",
            "LOCATION": "Lagos",
            "DEADLINE": "2026-12-01",
            "SOURCE_URL": "https://example.com",
            "VERIFIED_AT": "2026-10-15T00:00:00",
            "STATUS": "VERIFIED",
        }
    ]

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = mock_rows
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("src.quality.snowflake_audit.snowflake_config") as mock_conf:
        mock_conf.is_configured = True
        with patch("src.quality.snowflake_audit.get_connection", return_value=mock_conn):
            records = fetch_opportunities_for_audit(
                opportunity_id="OPP-001",
                status_filter="VERIFIED",
                limit=10,
            )

            assert len(records) == 1
            assert records[0]["opportunity_id"] == "OPP-001"
            assert records[0]["title"] == "Test Opportunity"

            # Verify query parameterization
            executed_sql, params = mock_cursor.execute.call_args[0]
            assert "WHERE" in executed_sql
            assert "OPPORTUNITY_ID = %s" in executed_sql
            assert "STATUS = %s" in executed_sql
            assert "LIMIT %s" in executed_sql
            assert params == ("OPP-001", "VERIFIED", 10)

            mock_conn.close.assert_called_once()


def test_fetch_opportunities_handles_db_exception():
    """Verify query failures raise clean RuntimeError and safely close connection."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.execute.side_effect = Exception("Snowflake warehouse suspended")
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("src.quality.snowflake_audit.snowflake_config") as mock_conf:
        mock_conf.is_configured = True
        with patch("src.quality.snowflake_audit.get_connection", return_value=mock_conn):
            with pytest.raises(RuntimeError, match="Snowflake audit query failed"):
                fetch_opportunities_for_audit()

            mock_conn.close.assert_called_once()
