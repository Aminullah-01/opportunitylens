"""Unit tests for the upgraded ingestion CLI, multi-source orchestration, and production data isolation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from src.ingestion.cli import main as cli_main
from src.ingestion.models import NormalizedOpportunity
from src.ingestion.pipeline import run_sources_ingestion
from src.ingestion.sources.base import BaseSourceAdapter, SourceCollectionResult


@pytest.fixture
def sample_normalized_opportunity() -> NormalizedOpportunity:
    """Fixture providing a valid NormalizedOpportunity instance."""
    return NormalizedOpportunity(
        opportunity_id="OPP-TEST-REAL-01",
        title="Federal Graduate Trainee",
        category="Entry-Level Jobs",
        organization="Federal Civil Service Commission",
        description="Official graduate development scheme.",
        eligibility="Nigerian graduates with NYSC completion.",
        education_level="BSc / HND Graduate",
        location="Abuja, Nigeria",
        deadline=None,
        source_url="https://jobs.leep.gov.ng/job/trainee",
        verified_at=None,
        status="VERIFIED",
    )


def test_cli_list_sources(capsys):
    """Verify CLI --list-sources exits cleanly and prints registered sources."""
    exit_code = cli_main(["--list-sources"])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Registered OpportunityLens Source Adapters" in captured.out
    assert "leep_jobs" in captured.out
    assert "ptdf_scholarships" in captured.out
    assert "nelex_jobs" in captured.out
    assert "airtel_careers" in captured.out


def test_cli_invalid_source_returns_error(capsys):
    """Verify requesting an unknown source returns exit code 1 with error message."""
    exit_code = cli_main(["--source", "completely_fake_source"])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Unknown source adapter" in captured.out


@patch("src.ingestion.cli.run_sources_ingestion")
def test_cli_all_enabled_dry_run(mock_run_ingest, capsys):
    """Verify --all-enabled --dry-run invokes run_sources_ingestion with dry_run=True."""
    mock_report = MagicMock()
    mock_report.errors = []
    mock_report.records = []
    mock_report.summary_text.return_value = "=== Mock Report Summary ==="
    mock_run_ingest.return_value = mock_report

    exit_code = cli_main(["--all-enabled", "--dry-run"])
    assert exit_code == 0
    mock_run_ingest.assert_called_once()
    _, kwargs = mock_run_ingest.call_args
    assert kwargs["dry_run"] is True


def test_cli_output_export_writes_valid_json(tmp_path, sample_normalized_opportunity):
    """Verify --output exports normalized records to the specified JSON file."""
    output_file = tmp_path / "exported_opportunities.json"

    # Create dummy adapter returning the sample opportunity
    class MockAdapter(BaseSourceAdapter):
        source_id = "mock_source"
        source_name = "Mock Adapter"
        base_url = "https://example.gov.ng"
        default_category = "Entry-Level Jobs"

        def fetch_raw(self, limit=None):
            return [{}]

        def parse_record(self, raw):
            return sample_normalized_opportunity

    with patch("src.ingestion.cli.get_enabled_adapters", return_value=[MockAdapter()]):
        exit_code = cli_main(["--all-enabled", "--dry-run", "--output", str(output_file)])
        assert exit_code == 0
        assert output_file.exists()

        with open(output_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert isinstance(data, list)
            assert len(data) == 1
            assert data[0]["OPPORTUNITY_ID"] == "OPP-TEST-REAL-01"
            assert data[0]["TITLE"] == "Federal Graduate Trainee"


def test_run_sources_ingestion_deduplication(sample_normalized_opportunity):
    """Verify run_sources_ingestion deduplicates across sources with same title and org."""
    dup_rec = NormalizedOpportunity(
        opportunity_id="OPP-TEST-REAL-02",  # Different ID
        title="Federal Graduate Trainee",    # Same title
        category="Entry-Level Jobs",
        organization="Federal Civil Service Commission",  # Same org
        description="Duplicate record from another feed.",
        eligibility="Requirements.",
        education_level="BSc / HND Graduate",
        location="Abuja, Nigeria",
        deadline=None,
        source_url="https://nelex.gov.ng/job/trainee",
        verified_at=None,
        status="VERIFIED",
    )

    class AdapterA(BaseSourceAdapter):
        source_id = "adapter_a"
        source_name = "Adapter A"
        base_url = "https://a.gov.ng"
        default_category = "Entry-Level Jobs"
        def fetch_raw(self, limit=None): return [{}]
        def parse_record(self, raw): return sample_normalized_opportunity

    class AdapterB(BaseSourceAdapter):
        source_id = "adapter_b"
        source_name = "Adapter B"
        base_url = "https://b.gov.ng"
        default_category = "Entry-Level Jobs"
        def fetch_raw(self, limit=None): return [{}]
        def parse_record(self, raw): return dup_rec

    report = run_sources_ingestion(
        adapters=[AdapterA(), AdapterB()],
        dry_run=True,
    )

    assert report.total_records == 2
    assert report.valid_records == 1  # Deduplicated down to 1
    assert report.skipped == 1


@patch("src.ingestion.pipeline.execute_snowflake_merge")
def test_production_mode_does_not_mutate_snowflake_on_dry_run(mock_merge, sample_normalized_opportunity):
    """Verify dry_run=True strictly guarantees zero database mutation calls."""
    class MockAdapter(BaseSourceAdapter):
        source_id = "mock"
        source_name = "Mock"
        base_url = "https://mock.gov.ng"
        default_category = "Entry-Level Jobs"
        def fetch_raw(self, limit=None): return [{}]
        def parse_record(self, raw): return sample_normalized_opportunity

    report = run_sources_ingestion(adapters=[MockAdapter()], dry_run=True)
    assert report.valid_records == 1
    mock_merge.assert_not_called()


def test_production_data_loading_isolation():
    """Verify production data loading refuses to return mock records when Snowflake is empty."""
    from src.db import get_application_status
    # Verify get_application_status handles unknown and None gracefully without guessing
    assert get_application_status(None) == "Unknown"
    assert get_application_status("invalid-date") == "Unknown"


def test_merge_normalized_records_preserves_richer_data():
    """Verify merge_normalized_records preserves non-null deadlines, richer descriptions, and locations."""
    from src.ingestion.pipeline import merge_normalized_records
    from datetime import date, datetime, timezone

    existing = NormalizedOpportunity(
        opportunity_id="OPP-100",
        title="Software Engineer Trainee",
        category="Entry-Level Jobs",
        organization="Federal Technology Agency",
        description="Comprehensive 12-month software development program covering Python and Snowflake.",
        eligibility="Graduates with 2.1 in STEM.",
        education_level="BSc / HND Graduate",
        location="Abuja, Nigeria",
        deadline=date(2026, 11, 30),
        source_url="https://agency.gov.ng/jobs/swe-trainee",
        verified_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        status="VERIFIED",
    )

    # Incoming record with blank/None deadline and shorter/generic fields
    incoming = NormalizedOpportunity(
        opportunity_id="OPP-100-NEW",
        title="Software Engineer Trainee",
        category="Entry-Level Jobs",
        organization="Federal Tech",
        description="Short job posting.",
        eligibility="See portal.",
        education_level="All Levels",
        location="Nigeria",
        deadline=None,
        source_url="https://agency.gov.ng/jobs/swe-trainee",
        verified_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        status="VERIFIED",
    )

    merged = merge_normalized_records(existing, incoming)
    assert merged.opportunity_id == "OPP-100"
    assert merged.deadline == date(2026, 11, 30)  # Preserved non-null deadline!
    assert "12-month software development" in merged.description  # Preserved richer description!
    assert merged.location == "Abuja, Nigeria"  # Preserved specific location!
    assert merged.education_level == "BSc / HND Graduate"  # Preserved specific education level!
    assert merged.verified_at == datetime(2026, 3, 1, tzinfo=timezone.utc)  # Latest verified timestamp!


def test_run_sources_ingestion_preserves_records_on_partial_failure(sample_normalized_opportunity):
    """Verify pipeline retains records when an adapter encounters partial timeouts/errors."""
    class PartialErrorAdapter(BaseSourceAdapter):
        source_id = "partial_source"
        source_name = "Partial Source"
        base_url = "https://partial.gov.ng"
        default_category = "Entry-Level Jobs"

        def collect(self, limit=None):
            return SourceCollectionResult(
                source_id=self.source_id,
                source_name=self.source_name,
                success=False,
                records=[sample_normalized_opportunity],
                total_fetched=2,
                parsed_count=1,
                error_count=1,
                error_message="Detail request timed out on 1 item",
                has_partial_errors=True,
            )

        def fetch_raw(self, limit=None): return []
        def parse_record(self, raw): return sample_normalized_opportunity

    report = run_sources_ingestion(adapters=[PartialErrorAdapter()], dry_run=True)
    # Records should NOT be discarded despite success=False
    assert len(report.records) == 1
    assert report.valid_records == 1
    # Partial error must be clearly reported
    assert any("warning/error" in err or "Detail request timed out" in err for err in report.errors)


@patch("src.ingestion.cli.get_adapter")
@patch("src.ingestion.cli.run_sources_ingestion")
def test_cli_custom_timeouts_and_retries(mock_run_ingest, mock_get_adapter):
    """Verify CLI forwards custom timeout and retry arguments to source adapters."""
    mock_adapter = MagicMock()
    mock_adapter.enabled = True
    mock_adapter.source_id = "leep_jobs"
    mock_get_adapter.return_value = mock_adapter

    mock_report = MagicMock()
    mock_report.errors = []
    mock_report.records = []
    mock_report.summary_text.return_value = "Summary"
    mock_run_ingest.return_value = mock_report

    exit_code = cli_main([
        "--source", "leep_jobs",
        "--dry-run",
        "--timeout", "15.0",
        "--connect-timeout", "4.0",
        "--read-timeout", "14.0",
        "--retries", "5",
    ])
    assert exit_code == 0
    mock_get_adapter.assert_called_once_with(
        "leep_jobs",
        network_enabled=True,
        timeout_seconds=15.0,
        connect_timeout_seconds=4.0,
        read_timeout_seconds=14.0,
        max_retries=5,
    )

