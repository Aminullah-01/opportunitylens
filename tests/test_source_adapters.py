"""Offline unit tests for external opportunity source adapters.

Tests parsing logic, Schema.org extraction, SSRF security, rate-limiting,
and disabled source policies without live network requests.
"""

from __future__ import annotations

from datetime import date, datetime
import json
from unittest.mock import MagicMock, patch
import pytest

from src.ingestion.models import NormalizedOpportunity
from src.ingestion.sources.base import BaseSourceAdapter, SourceCollectionResult
from src.ingestion.sources.disabled_sources import (
    AirtelCareersAdapter,
    FederalMinistryEducationAdapter,
    YsiInnovationAdapter,
)
from src.ingestion.sources.leep_jobs import LeepJobsAdapter
from src.ingestion.sources.nelex_jobs import NelexJobsAdapter
from src.ingestion.sources.ptdf_scholarship import PtdfScholarshipAdapter
from src.ingestion.sources.registry import (
    get_adapter,
    get_all_adapters,
    get_enabled_adapters,
    list_sources_summary,
)


# Sample Mock HTML / JSON-LD for LEEP Jobs
MOCK_LEEP_JOB_JSON_LD = {
    "@context": "https://schema.org/",
    "@type": "JobPosting",
    "title": "Junior Python Data Analyst",
    "url": "https://jobs.leep.gov.ng/job/junior-python-data-analyst",
    "description": "<p>We are seeking entry-level data analysts with Python and SQL foundations.</p>",
    "identifier": {
        "@type": "PropertyValue",
        "name": "Federal Ministry of Labour",
        "value": "LEEP-9941",
    },
    "datePosted": "2026-03-01T10:00:00+01:00",
    "validThrough": "2026-12-15T23:59:00+01:00",
    "hiringOrganization": {
        "@type": "Organization",
        "name": "Naija Analytics Lab",
    },
    "jobLocation": {
        "@type": "Place",
        "address": {
            "@type": "PostalAddress",
            "addressRegion": "Abuja",
            "addressCountry": "Nigeria",
        },
    },
}

MOCK_LEEP_DETAIL_HTML = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Junior Python Data Analyst - LEEP Jobs</title>
    <script type="application/ld+json">
    {json.dumps(MOCK_LEEP_JOB_JSON_LD)}
    </script>
</head>
<body>
    <h1>Junior Python Data Analyst</h1>
</body>
</html>
"""

MOCK_LEEP_LISTING_HTML = """
<!DOCTYPE html>
<html>
<body>
    <a href="/job/junior-python-data-analyst">Junior Python Data Analyst</a>
    <a href="/job/devops-intern">DevOps Intern</a>
</body>
</html>
"""

# Sample Mock HTML for PTDF Guidelines
MOCK_PTDF_GUIDELINES_HTML = """
<!DOCTYPE html>
<html>
<head><title>PTDF - Guidelines & Sponsored Courses</title></head>
<body>
    <h1>2026/27 IN-COUNTRY SCHOLARSHIP SCHEME (ISS)</h1>
    <p>Deadline: November 30, 2026</p>
    <h2>A. ISS Undergraduate</h2>
    <p>Must be in 200 level with minimum CGPA 3.5.</p>
    <h2>B. ISS MSc</h2>
    <p>Minimum 2.1 in engineering or geosciences.</p>
</body>
</html>
"""

# Sample Mock HTML for NELEX
MOCK_NELEX_JOB_HTML = """
<!DOCTYPE html>
<html>
<head><title>NELEX - Merchant Sales Associate</title></head>
<body>
    <h1>Merchant Sales Associate</h1>
    <h3>Employer: Global Fintech Services</h3>
    <h3>Job Description</h3>
    <p>Coordinate mobile POS merchant integrations across Nigerian regional markets.</p>
    <h3>Qualifications and Requirements</h3>
    <p>Degree in Business, Computing, or Marketing with 0-2 years experience.</p>
    <p>Location: <strong>Lagos, Nigeria</strong></p>
    <p>Deadline: Dec 15, 2026</p>
</body>
</html>
"""


def test_ssrf_protection_blocks_forbidden_destinations():
    """Verify that safe_request rejects loopback, private networks, and cloud metadata."""
    adapter = LeepJobsAdapter()

    # Loopback IP
    with pytest.raises(ValueError, match="SSRF defense blocked"):
        adapter.safe_request("http://127.0.0.1:8000/internal")

    # Localhost
    with pytest.raises(ValueError, match="SSRF defense blocked"):
        adapter.safe_request("http://localhost/admin")

    # Private network
    with pytest.raises(ValueError, match="SSRF defense blocked"):
        adapter.safe_request("http://192.168.1.1/router")

    # Cloud metadata endpoint (AWS / GCP / Azure)
    with pytest.raises(ValueError, match="SSRF defense blocked"):
        adapter.safe_request("http://169.254.169.254/latest/meta-data/")

    # Non-HTTP scheme
    with pytest.raises(ValueError, match="SSRF defense blocked"):
        adapter.safe_request("ftp://example.com/file")


def test_network_disabled_raises_runtime_error():
    """Verify that adapter with network_enabled=False refuses outbound requests."""
    adapter = LeepJobsAdapter(network_enabled=False)
    with pytest.raises(RuntimeError, match="Network collection is disabled"):
        adapter.safe_request("https://jobs.leep.gov.ng/jobs")


def test_leep_jobs_adapter_parses_json_ld():
    """Verify LeepJobsAdapter correctly parses Schema.org JobPosting JSON-LD."""
    adapter = LeepJobsAdapter()
    raw = {
        "source_url": "https://jobs.leep.gov.ng/job/junior-python-data-analyst",
        "html": MOCK_LEEP_DETAIL_HTML,
        "json_ld": MOCK_LEEP_JOB_JSON_LD,
    }

    record = adapter.parse_record(raw)
    assert isinstance(record, NormalizedOpportunity)
    assert record.opportunity_id == "OPP-LEEP-LEEP-9941"
    assert record.title == "Junior Python Data Analyst"
    assert record.organization == "Naija Analytics Lab"
    assert record.category == "Entry-Level Jobs"
    assert "data analysts with Python" in record.description
    assert record.location == "Abuja, Nigeria"
    assert record.deadline == date(2026, 12, 15)
    assert record.status == "VERIFIED"
    assert record.source_url == "https://jobs.leep.gov.ng/job/junior-python-data-analyst"


def test_leep_jobs_adapter_internship_categorization():
    """Verify LeepJobsAdapter assigns Internships category when title mentions intern."""
    adapter = LeepJobsAdapter()
    raw = {
        "source_url": "https://jobs.leep.gov.ng/job/cloud-intern",
        "html": "<html><body><h1>Cloud Infrastructure Intern</h1></body></html>",
        "json_ld": {
            "title": "Cloud Infrastructure Intern",
            "hiringOrganization": {"name": "HostAfrica"},
            "description": "Internship for computer science students.",
        },
    }
    record = adapter.parse_record(raw)
    assert record.category == "Internships"
    assert record.organization == "HostAfrica"
    assert record.deadline is None  # Missing validThrough handled cleanly as None


@patch.object(BaseSourceAdapter, "safe_request")
def test_leep_jobs_adapter_collect_lifecycle(mock_safe_request):
    """Verify full LeepJobsAdapter collect() flow with mocked HTTP responses."""
    # Mock listing response and detail response
    mock_list_resp = MagicMock()
    mock_list_resp.text = MOCK_LEEP_LISTING_HTML
    mock_detail_resp = MagicMock()
    mock_detail_resp.text = MOCK_LEEP_DETAIL_HTML

    mock_safe_request.side_effect = [mock_list_resp, mock_detail_resp, mock_detail_resp]

    adapter = LeepJobsAdapter()
    result = adapter.collect(limit=1)

    assert result.success is True
    assert result.source_id == "leep_jobs"
    assert len(result.records) == 1
    assert result.records[0].title == "Junior Python Data Analyst"
    assert result.duration_seconds >= 0.0


@patch.object(BaseSourceAdapter, "safe_request")
def test_ptdf_scholarship_adapter_parsing(mock_safe_request):
    """Verify PtdfScholarshipAdapter generates 3 distinct official schemes."""
    mock_resp = MagicMock()
    mock_resp.text = MOCK_PTDF_GUIDELINES_HTML
    mock_safe_request.return_value = mock_resp

    adapter = PtdfScholarshipAdapter()
    raw_schemes = adapter.fetch_raw()

    assert len(raw_schemes) == 3
    records = [adapter.parse_record(s) for s in raw_schemes]

    ug_rec = next(r for r in records if "Undergraduate" in r.title)
    msc_rec = next(r for r in records if "Master" in r.title)
    phd_rec = next(r for r in records if "Doctoral" in r.title)

    assert ug_rec.opportunity_id == "OPP-PTDF-ISS-UG"
    assert ug_rec.category == "Scholarships"
    assert ug_rec.organization == "Petroleum Technology Development Fund (PTDF)"
    assert ug_rec.education_level == "Undergraduate"
    assert "200 level" in ug_rec.eligibility
    assert ug_rec.deadline == date(2026, 11, 30)

    assert msc_rec.opportunity_id == "OPP-PTDF-ISS-MSC"
    assert msc_rec.education_level == "Postgraduate"
    assert "Second Class Upper" in msc_rec.eligibility

    assert phd_rec.opportunity_id == "OPP-PTDF-ISS-PHD"
    assert phd_rec.education_level == "Postgraduate"


def test_nelex_jobs_adapter_parsing():
    """Verify NelexJobsAdapter extracts title, organization, deadline, and eligibility."""
    adapter = NelexJobsAdapter()
    raw = {
        "source_url": "https://nelex.gov.ng/job/merchant-sales-associate",
        "html": MOCK_NELEX_JOB_HTML,
    }

    record = adapter.parse_record(raw)
    assert record.opportunity_id == "OPP-NELEX-MERCHANT-SALES-ASSOC"
    assert "Merchant Sales Associate" in record.title
    assert "Global Fintech Services" in record.organization
    assert record.category == "Entry-Level Jobs"
    assert record.deadline == date(2026, 12, 15)
    assert record.location == "Lagos, Nigeria"
    assert "0-2 years experience" in record.eligibility



def test_disabled_adapters_policy():
    """Verify disabled adapters have enabled=False and explicit limitation reasons."""
    disabled_adapters = [
        AirtelCareersAdapter(),
        FederalMinistryEducationAdapter(),
        YsiInnovationAdapter(),
    ]

    for adapter in disabled_adapters:
        assert adapter.enabled is False
        assert adapter.disabled_reason is not None
        assert len(adapter.disabled_reason) > 20

        # collect() returns success=False with disabled_reason
        res = adapter.collect()
        assert res.success is False
        assert res.error_message == adapter.disabled_reason
        assert len(res.records) == 0


def test_adapter_registry_discovery():
    """Verify source adapter registry functions and catalog queries."""
    # List summaries
    summaries = list_sources_summary()
    assert len(summaries) >= 6
    ids = [s["source_id"] for s in summaries]
    assert "leep_jobs" in ids
    assert "ptdf_scholarships" in ids
    assert "nelex_jobs" in ids
    assert "airtel_careers" in ids

    # Get single adapter
    leep = get_adapter("leep_jobs")
    assert isinstance(leep, LeepJobsAdapter)

    # Get enabled adapters
    enabled = get_enabled_adapters()
    assert all(a.enabled for a in enabled)
    enabled_ids = [a.source_id for a in enabled]
    assert "leep_jobs" in enabled_ids
    assert "ptdf_scholarships" in enabled_ids
    assert "nelex_jobs" in enabled_ids
    assert "airtel_careers" not in enabled_ids

    # Unknown adapter raises KeyError
    with pytest.raises(KeyError, match="Unknown source adapter"):
        get_adapter("non_existent_adapter")


def test_adapter_timeout_and_retry_configuration():
    """Verify adapters initialize with configurable connect and read timeouts and retry strategies."""
    adapter = LeepJobsAdapter(
        connect_timeout_seconds=3.5,
        read_timeout_seconds=18.0,
        max_retries=4,
        retry_backoff_factor=0.8,
    )
    assert adapter.connect_timeout_seconds == 3.5
    assert adapter.read_timeout_seconds == 18.0
    assert adapter.max_retries == 4
    assert adapter.retry_backoff_factor == 0.8

    # Verify session mount has retries configured
    https_adapter = adapter.session.adapters.get("https://")
    assert https_adapter is not None
    assert https_adapter.max_retries.total == 4
    assert 504 in https_adapter.max_retries.status_forcelist


def test_leep_adapter_extracts_listing_cards_when_detail_fails():
    """Verify LeepJobsAdapter preserves listing page card data when detail requests timeout."""
    sample_listing_html = """
    <html><body>
    <div class="col-md-6">
        <a href="https://jobs.leep.gov.ng/job/frontend-developer-intern" class="tw-card jobcardStyle1">
            <div>
                <span class="tw-text-lg tw-font-medium">Frontend Developer Intern</span>
                <span class="tw-card-title">GovTech Nigeria</span>
                <span class="tw-location">Abuja, Nigeria</span>
                <span class="tw-text-[#0BA02C]">Full Time</span>
                <span>Salary: 120,000 NGN</span>
            </div>
        </a>
    </div>
    <div class="col-md-6">
        <a href="https://jobs.leep.gov.ng/job/cybersecurity-trainee" class="tw-card jobcardStyle1">
            <div>
                <span class="tw-text-lg tw-font-medium">Cybersecurity Trainee</span>
                <span class="tw-card-title">CyberShield NG</span>
                <span class="tw-location">Lagos, Nigeria</span>
                <span class="tw-text-[#0BA02C]">Remote</span>
                <span>Salary: 150,000 NGN</span>
            </div>
        </a>
    </div>
    </body></html>
    """
    adapter = LeepJobsAdapter()

    # Mock safe_request: first request returns listing HTML, detail requests raise ReadTimeout
    import requests
    def mock_safe_request(url, *args, **kwargs):
        if url == adapter.base_url:
            resp = MagicMock()
            resp.text = sample_listing_html
            resp.status_code = 200
            return resp
        raise requests.exceptions.ReadTimeout(f"Timed out fetching {url}")

    with patch.object(adapter, "safe_request", side_effect=mock_safe_request):
        raw_cards = adapter.fetch_raw()

    assert len(raw_cards) == 2
    assert raw_cards[0]["listing_title"] == "Frontend Developer Intern"
    assert raw_cards[0]["listing_org"] == "GovTech Nigeria"
    assert raw_cards[0]["listing_location"] == "Abuja, Nigeria"
    assert raw_cards[0]["detail_fetched"] is False
    assert "Timed out fetching" in raw_cards[0]["detail_error"]

    # Parse baseline record
    norm = adapter.parse_record(raw_cards[0])
    assert norm.title == "Frontend Developer Intern"
    assert norm.category == "Internships"
    assert norm.organization == "GovTech Nigeria"
    assert "Abuja, Nigeria" in norm.location
    assert "GovTech Nigeria" in norm.description
    assert norm.deadline is None
    assert norm.status == "VERIFIED"


def test_leep_adapter_expired_deadline_marks_needs_review():
    """Verify opportunities with expired deadlines are marked NEEDS_REVIEW, not VERIFIED."""
    adapter = LeepJobsAdapter()
    raw = {
        "source_url": "https://jobs.leep.gov.ng/job/expired-post",
        "html": "<html><h1>Expired Position</h1></html>",
        "json_ld": {
            "title": "Expired Database Admin",
            "hiringOrganization": {"name": "Old Systems Ltd"},
            "validThrough": "2024-01-15T00:00:00+01:00",  # Expired
            "description": "Historical posting.",
        },
    }
    record = adapter.parse_record(raw)
    assert record.deadline == date(2024, 1, 15)
    assert record.status == "NEEDS_REVIEW"


def test_leep_adapter_malformed_listing_page_handled_safely():
    """Verify corrupt or empty HTML does not crash the collector."""
    adapter = LeepJobsAdapter()
    resp = MagicMock()
    resp.text = "<<<<bad html>>>> <a not-a-link>"
    with patch.object(adapter, "safe_request", return_value=resp):
        raw_cards = adapter.fetch_raw()
    assert raw_cards == []


def test_source_collection_result_partial_success_telemetry():
    """Verify SourceCollectionResult telemetry, warning reporting, and summary lines."""
    # Case 1: Full success
    res_success = SourceCollectionResult(
        source_id="src_1",
        source_name="Source One",
        success=True,
        records=[MagicMock()],
        duration_seconds=1.2,
    )
    assert res_success.partial_success is False
    assert "[✓] Source One (src_1): 1 records collected" in res_success.summary_line()

    # Case 2: Partial collection with warnings
    res_partial = SourceCollectionResult(
        source_id="src_2",
        source_name="Source Two",
        success=True,
        records=[MagicMock(), MagicMock()],
        warning_messages=["Detail timeout on item 1"],
        has_partial_errors=True,
        duration_seconds=2.5,
    )
    assert res_partial.partial_success is True
    assert "[!] Source Two (src_2): 2 records collected with 1 warning(s)" in res_partial.summary_line()

    # Case 3: Complete failure
    res_fail = SourceCollectionResult(
        source_id="src_3",
        source_name="Source Three",
        success=False,
        error_message="Connection refused",
        duration_seconds=0.5,
    )
    assert res_fail.partial_success is False
    assert "[✗] Source Three (src_3): Failed (Connection refused)" in res_fail.summary_line()

