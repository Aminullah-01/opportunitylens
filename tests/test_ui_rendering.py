"""Tests for UI rendering, escaping, state handling, and public-UI hygiene.

Covers:
- HTML/Markdown safety for database-sourced values
- Safe external URL handling
- Filtering helpers and data derivation
- Full-app rendering via Streamlit's headless AppTest
- Guardrails that developer diagnostics, raw data, and errors never leak
  into the public interface
"""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest

from src.demo_data import filter_opportunities
from src.utils import (
    derive_education_levels,
    derive_locations,
    escape_markdown,
    get_safe_url,
    sanitize_html,
)

APP_PATH = Path(__file__).resolve().parent.parent / "app.py"

MOCK_OPPORTUNITIES: List[Dict[str, Any]] = [
    {
        "opportunity_id": "TEST-1",
        "title": "National AI Fellowship",
        "organization": "NITDA",
        "category": "Tech Training",
        "location": "Abuja",
        "education_level": "Undergraduate",
        "description": "Comprehensive applied AI fellowship.",
        "eligibility": "Nigerian students with basic coding skills.",
        "deadline": "2026-12-31",
        "source_url": "https://example.com/fellowship",
        "status": "Open",
        "is_sample_data": False,
    },
    {
        "opportunity_id": "TEST-2",
        "title": "STEM Undergraduate Scholarship",
        "organization": "Ministry of Education",
        "category": "Scholarships",
        "location": "Lagos",
        "education_level": "Postgraduate",
        "description": "Tuition support for STEM scholars.",
        "eligibility": "Minimum CGPA of 3.5 on a 5.0 scale.",
        "deadline": "2026-11-20",
        "source_url": "https://example.com/scholarship",
        "status": "Closing Soon",
        "is_sample_data": False,
    },
]

FORBIDDEN_PUBLIC_TERMS = [
    "OPPORTUNITYLENS_DB",
    "SELECT *",
    "SNOWFLAKE_",
    "Traceback (most recent call last)",
    "SQLException",
    "leep_jobs",
    ".venv",
    "raw_opportunities.json",
]


@pytest.fixture(autouse=True)
def _clear_streamlit_caches():
    """Isolate cached data loading between headless app test runs."""
    import streamlit as st

    st.cache_data.clear()
    yield
    st.cache_data.clear()


def _run_app(monkeypatch, records: List[Dict[str, Any]] | None = None):
    """Run the application headlessly with a mocked data source."""
    from streamlit.testing.v1 import AppTest

    if records is None:
        records = MOCK_OPPORTUNITIES

    monkeypatch.setattr(
        "src.db.fetch_opportunities",
        lambda: [dict(record) for record in records],
    )

    app = AppTest.from_file(str(APP_PATH), default_timeout=60)
    app.run()
    return app


def _visible_tree(app) -> str:
    """Collect the text of every rendered public element for assertions."""
    parts: List[str] = []

    element_collections = (
        app.title,
        app.header,
        app.subheader,
        app.markdown,
        app.caption,
        app.text,
        app.info,
        app.warning,
        app.success,
        app.error,
    )
    for elements in element_collections:
        for element in elements:
            value = getattr(element, "value", None)
            if isinstance(value, str):
                parts.append(value)

    for element in list(app.button) + list(app.link_button):
        label = getattr(element, "label", None)
        if isinstance(label, str):
            parts.append(label)

    return "\n".join(parts)


# -----------------------------------------------------------------------------
# Text escaping and URL safety
# -----------------------------------------------------------------------------
def test_sanitize_html_escapes_malicious_input():
    """Verify HTML escaping blocks XSS script tags and special characters."""
    bad_input = '<script>alert("XSS")</script> & <b>bold</b>'
    sanitized = sanitize_html(bad_input)
    assert "<script>" not in sanitized
    assert "<b>" not in sanitized
    assert "&lt;script&gt;" in sanitized
    assert "&amp;" in sanitized
    assert "&quot;XSS&quot;" in sanitized


def test_sanitize_html_handles_none_and_empty():
    """Verify sanitize_html handles None and empty inputs with clean fallbacks."""
    assert sanitize_html(None, default="N/A") == "N/A"
    assert sanitize_html("", default="Default Org") == "Default Org"
    assert sanitize_html("   ", default="Default Org") == "Default Org"
    assert sanitize_html(42) == "42"


def test_escape_markdown_neutralizes_links_images_and_html():
    """Verify untrusted values cannot form Markdown links, images, or HTML."""
    hostile = "[Apply](https://evil.example) ![img](https://evil.example/x.png) "
    hostile += "**bold** _em_ <script>alert(1)</script> :red[alert]"

    escaped = escape_markdown(hostile)

    assert "\\[Apply\\]" in escaped
    assert "\\]\\(" in escaped
    assert "\\!\\[img\\]" in escaped
    assert not any(
        token in escaped for token in ("[Apply](", "![img](", "<script>", ":red[")
    )
    assert "\\*\\*bold\\*\\*" in escaped
    assert "\\<script\\>" in escaped


def test_escape_markdown_handles_none_and_empty():
    """Verify escape_markdown uses clean defaults for missing values."""
    assert escape_markdown(None, default="Untitled") == "Untitled"
    assert escape_markdown("", default="Untitled") == "Untitled"
    assert escape_markdown("   ", default="Untitled") == "Untitled"
    assert escape_markdown("Plain title") == "Plain title"


def test_get_safe_url_accepts_valid_schemes():
    """Verify get_safe_url permits valid http and https URLs."""
    assert get_safe_url("https://example.com/apply") == "https://example.com/apply"
    assert (
        get_safe_url("http://sub.domain.org/path?q=1&b=2")
        == "http://sub.domain.org/path?q=1&amp;b=2"
    )


def test_get_safe_url_rejects_unsafe_schemes():
    """Verify get_safe_url rejects javascript, data, ftp, and file schemes."""
    assert get_safe_url("javascript:alert(1)") is None
    assert get_safe_url("data:text/html;base64,PHNjcmlwdD4=") is None
    assert get_safe_url("ftp://ftp.example.com/file") is None
    assert get_safe_url("/local/path/only") is None
    assert get_safe_url(None) is None
    assert get_safe_url("") is None


# -----------------------------------------------------------------------------
# Filtering helpers
# -----------------------------------------------------------------------------
def test_filter_opportunities_location_and_education():
    """Verify filter_opportunities supports location and education level filtering."""
    records = [
        {
            "opportunity_id": "1",
            "title": "Lagos Tech Internship",
            "category": "Internships",
            "location": "Lagos, Nigeria",
            "education_level": "Undergraduate",
            "status": "Open",
        },
        {
            "opportunity_id": "2",
            "title": "Abuja Public Policy Fellowship",
            "category": "Scholarships",
            "location": "Abuja, Nigeria",
            "education_level": "Postgraduate",
            "status": "Open",
        },
        {
            "opportunity_id": "3",
            "title": "Remote Python Bootcamp",
            "category": "Tech Training",
            "location": "Remote, Nigeria",
            "education_level": "Undergraduate",
            "status": "Closing Soon",
        },
    ]

    lagos_res = filter_opportunities(records, location="Lagos")
    assert len(lagos_res) == 1
    assert lagos_res[0]["opportunity_id"] == "1"

    postgrad_res = filter_opportunities(records, education_level="Postgraduate")
    assert len(postgrad_res) == 1
    assert postgrad_res[0]["opportunity_id"] == "2"

    multi_res = filter_opportunities(
        records,
        category="Tech Training",
        location="Remote",
        education_level="Undergraduate",
    )
    assert len(multi_res) == 1
    assert multi_res[0]["opportunity_id"] == "3"


def test_derive_locations_and_education_levels():
    """Verify derive_locations and derive_education_levels return sorted unique values."""
    records = [
        {"location": "Lagos", "education_level": "Undergraduate"},
        {"location": "Abuja", "education_level": "Postgraduate"},
        {"location": "Lagos", "education_level": "Undergraduate"},
        {"location": "Remote", "education_level": None},
    ]
    assert derive_locations(records) == ["Abuja", "Lagos", "Remote"]
    assert derive_education_levels(records) == ["Postgraduate", "Undergraduate"]


def test_match_result_properties_and_fallbacks():
    """Verify MatchResult exposes location, education_level, description, and eligibility."""
    from src.matching.models import MatchResult, MatchScoreBreakdown

    record = {
        "opportunity_id": "opp-test-1",
        "title": "Data Engineering Fellowship",
        "organization": "Gombe AI Hub",
        "category": "Tech Training",
        "location": "Gombe, Nigeria",
        "education_level": "Undergraduate",
        "description": "Intensive data pipelines training.",
        "eligibility": "Basic Python and SQL knowledge required.",
        "verification_status": "VERIFIED",
    }
    populated = MatchResult(
        opportunity_id="opp-test-1",
        title="Data Engineering Fellowship",
        organization="Gombe AI Hub",
        category="Tech Training",
        match_score=95.0,
        ranked_position=1,
        score_breakdown=MatchScoreBreakdown(total_score=95.0),
        opportunity_record=record,
    )
    assert populated.location == "Gombe, Nigeria"
    assert populated.education_level == "Undergraduate"
    assert populated.description == "Intensive data pipelines training."
    assert populated.eligibility_str == "Basic Python and SQL knowledge required."
    assert populated.verification_status == "VERIFIED"

    sparse = MatchResult(
        opportunity_id="opp-test-2",
        title="Generic Opportunity",
        organization="Unknown Org",
        category="Other",
        match_score=50.0,
        ranked_position=2,
        score_breakdown=MatchScoreBreakdown(total_score=50.0),
        opportunity_record={},
    )
    assert sparse.location == "Nigeria"
    assert sparse.education_level == "All Levels"
    assert sparse.description == ""
    assert sparse.eligibility_str in ("Assessment not performed.", "Requirements not specified")


# -----------------------------------------------------------------------------
# Package and design-system checks
# -----------------------------------------------------------------------------
def test_ui_package_exports():
    """Verify src.ui cleanly exports all public UI components and styles."""
    import src.ui as ui_mod

    expected_symbols = [
        "inject_ui_styles",
        "render_hero",
        "render_opportunity_card",
        "show_opportunity_details_dialog",
        "render_empty_state",
        "render_service_unavailable",
    ]
    for symbol in expected_symbols:
        assert hasattr(ui_mod, symbol), f"Symbol {symbol} missing from src.ui"
        assert callable(getattr(ui_mod, symbol))


def test_ui_styles_and_theme_have_no_internal_leakage():
    """Verify the design system stays brand-only and avoids brittle internals."""
    from src.ui.styles import UI_CSS

    assert ".ol-brand" in UI_CSS
    assert "max-width" in UI_CSS
    # No brittle selectors targeting Streamlit's generated internal classes.
    assert "stVerticalBlockBorderWrapper" not in UI_CSS
    for term in ("OPPORTUNITYLENS_DB", "SELECT *", "SNOWFLAKE_"):
        assert term not in UI_CSS

    theme_config = (APP_PATH.parent / ".streamlit" / "config.toml").read_text()
    assert "#2563eb" in theme_config
    assert 'base = "light"' in theme_config


def test_content_clears_the_fixed_streamlit_header():
    """Verify page content starts below the fixed 60px header.

    Without enough top padding, the brand header and primary navigation render
    underneath Streamlit's translucent fixed header and become effectively
    invisible.
    """
    from src.ui.styles import UI_CSS

    block = re.search(r"\.block-container\s*\{([^}]*)\}", UI_CSS)
    assert block is not None
    padding_top = re.search(r"padding-top:\s*([\d.]+)rem", block.group(1))
    assert padding_top is not None
    assert float(padding_top.group(1)) >= 4.5


def test_app_source_has_no_public_admin_diagnostics():
    """Verify developer diagnostics are not wired into the public app script."""
    source = APP_PATH.read_text()
    for term in (
        "Internal System Diagnostics",
        "render_analytics_section",
        "render_data_quality_section",
        'query_params.get("admin")',
    ):
        assert term not in source


# -----------------------------------------------------------------------------
# Headless application rendering
# -----------------------------------------------------------------------------
def test_headless_app_renders_discovery_view(monkeypatch):
    """Verify app.py renders the discovery experience without exceptions."""
    app = _run_app(monkeypatch)

    assert len(app.exception) == 0, [e.value for e in app.exception]
    assert len(app.segmented_control) >= 1
    assert len(app.pills) >= 1
    assert [t.value for t in app.title] == ["Find opportunities that move you forward."]

    tree = _visible_tree(app)
    assert "National AI Fellowship" in tree
    assert "2 opportunities available" in tree
    # Safe external application links only.
    assert all(link.url.startswith("https://") for link in app.link_button)


def test_public_ui_contains_no_developer_output(monkeypatch):
    """Verify the rendered public UI never exposes developer-only information."""
    app = _run_app(monkeypatch)
    tree = _visible_tree(app).lower()

    for term in FORBIDDEN_PUBLIC_TERMS:
        assert term.lower() not in tree, f"Developer term leaked into UI: {term}"


def test_snowflake_failure_shows_outage_without_demo_fallback(monkeypatch):
    """Verify Snowflake failures never silently load fictional demo records."""
    from streamlit.testing.v1 import AppTest

    def _raise():
        raise RuntimeError("Snowflake connection failed: password=hunter2")

    monkeypatch.setattr("src.db.fetch_opportunities", _raise)

    app = AppTest.from_file(str(APP_PATH), default_timeout=60)
    app.run()

    assert len(app.exception) == 0, [e.value for e in app.exception]
    tree = _visible_tree(app)
    assert "temporarily unable to load opportunities" in tree.lower()
    assert "Northern Nigeria Women in STEM" not in tree
    assert "hunter2" not in tree
    assert "RuntimeError" not in tree


def test_empty_database_shows_friendly_empty_state(monkeypatch):
    """Verify a connected-but-empty database renders a clear empty state."""
    app = _run_app(monkeypatch, records=[])

    assert len(app.exception) == 0, [e.value for e in app.exception]
    tree = _visible_tree(app)
    assert "No opportunities are available right now" in tree
    assert "Northern Nigeria Women in STEM" not in tree


def test_demo_mode_is_explicitly_labeled(monkeypatch):
    """Verify demo mode is opt-in and clearly labeled as fictional sample data."""
    monkeypatch.setattr(
        "src.config.ingestion_config",
        SimpleNamespace(demo_mode=True),
    )
    app = _run_app(monkeypatch, records=[])

    assert len(app.exception) == 0, [e.value for e in app.exception]
    tree = _visible_tree(app)
    assert "Demo mode is on" in tree
    assert "Northern Nigeria Women in STEM Undergraduate Scholarship" in tree


def test_filters_and_reset_update_results(monkeypatch):
    """Verify filters narrow results and the reset action restores them."""
    app = _run_app(monkeypatch)
    assert "2 opportunities available" in _visible_tree(app)

    app.selectbox(key="filter_location").set_value("Lagos").run()
    captions = " ".join(c.value for c in app.caption)
    assert "Showing 1 of 2 opportunities" in captions
    assert "STEM Undergraduate Scholarship" in _visible_tree(app)

    app.selectbox(key="filter_status").set_value("Closed").run()
    tree = _visible_tree(app)
    assert "No opportunities match your filters" in tree

    reset = [button for button in app.button if button.label == "Reset filters"][0]
    reset.click().run()
    assert "2 opportunities available" in _visible_tree(app)


def test_saved_flow_persists_and_removes(monkeypatch):
    """Verify saving, viewing, and removing a saved opportunity works."""
    app = _run_app(monkeypatch)

    save_button = [b for b in app.button if b.key == "discover_save_TEST-1"][0]
    save_button.click().run()
    assert "TEST-1" in app.session_state.get("saved_opportunities", set())

    app.segmented_control[0].set_value("Saved").run()
    tree = _visible_tree(app)
    assert "Saved opportunities" in tree
    assert "National AI Fellowship" in tree

    remove_button = [b for b in app.button if b.key == "saved_save_TEST-1"][0]
    remove_button.click().run()
    assert "No saved opportunities yet" in _visible_tree(app)


def test_profile_page_renders_form_and_matches(monkeypatch):
    """Verify profile setup and personalized matching render without errors."""
    app = _run_app(monkeypatch)

    app.segmented_control[0].set_value("My Profile").run()
    assert len(app.exception) == 0, [e.value for e in app.exception]
    assert [t.value for t in app.title] == ["Your profile & matches"]
    assert len(app.form) == 1

    example_button = [b for b in app.button if b.label == "Use example"][0]
    example_button.click().run()

    assert len(app.exception) == 0, [e.value for e in app.exception]
    tree = _visible_tree(app)
    assert "Computer Science" in tree
    assert "Why this matches" in tree
    assert "not a prediction of acceptance" in tree
    assert "matching opportunities" in tree.lower()
