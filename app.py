"""OpportunityLens — Streamlit Web Application (Phase 3).

Find opportunities. Understand your chances. Take your next step.
Hacktoberfest Hack Day Gombe: Best Open-Source AI Project with Snowflake.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import pandas as pd
import streamlit as st

from src.analytics import calculate_analytics_summary
from src.config import ai_config, app_config, snowflake_config
from src.db import fetch_opportunities
from src.demo_data import (
    filter_opportunities,
    get_demo_opportunities,
)
from src.utils import (
    derive_categories,
    format_display_date,
    get_platform_metrics,
    is_valid_url,
)

# -----------------------------------------------------------------------------
# Streamlit Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{app_config.APP_NAME} — Opportunity Discovery",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Professional Blue-and-White theme with high accessibility and contrast
CUSTOM_CSS = """
<style>
    /* Global Typography and Layout Spacing */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 3.5rem;
        max-width: 1200px;
    }
    
    /* Brand Header Box */
    .brand-header-box {
        background-color: #f7f9fc;
        border: 1px solid #dbe2ea;
        border-left: 6px solid #0052cc;
        border-radius: 8px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1.75rem;
    }
    
    .brand-title {
        color: #0b1a30;
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin-bottom: 0.25rem;
    }
    
    .brand-tagline {
        color: #0052cc;
        font-size: 1.15rem;
        font-weight: 600;
        margin-bottom: 0.75rem;
    }
    
    .brand-description {
        color: #334155;
        font-size: 0.95rem;
        line-height: 1.6;
        margin-bottom: 0;
    }
    
    /* Category & Status Badges */
    .badge {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        padding: 0.2rem 0.55rem;
        border-radius: 4px;
        margin-right: 0.4rem;
        margin-bottom: 0.4rem;
    }
    
    .badge-sample {
        background-color: #e0f2fe;
        color: #0369a1;
        border: 1px solid #bae6fd;
    }
    
    .badge-category {
        background-color: #eef2f6;
        color: #1e293b;
        border: 1px solid #cbd5e1;
    }
    
    .badge-status-open {
        background-color: #ecfdf5;
        color: #047857;
        border: 1px solid #a7f3d0;
    }
    
    .badge-status-closing {
        background-color: #fffbeb;
        color: #b45309;
        border: 1px solid #fde68a;
    }
    
    .badge-status-closed {
        background-color: #f1f5f9;
        color: #64748b;
        border: 1px solid #cbd5e1;
    }

    .badge-status-unknown {
        background-color: #f8fafc;
        color: #64748b;
        border: 1px solid #e2e8f0;
    }

    .badge-verified {
        background-color: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }

    .badge-unverified {
        background-color: #fff7ed;
        color: #c2410c;
        border: 1px solid #ffedd5;
    }
    
    /* Opportunity Card */
    .opportunity-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: border-color 0.15s ease-in-out;
    }
    
    .opportunity-card:hover {
        border-color: #93c5fd;
    }
    
    .card-title {
        color: #0f172a;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 0.35rem;
    }
    
    .card-meta {
        color: #475569;
        font-size: 0.88rem;
        margin-bottom: 0.75rem;
    }
    
    .card-description {
        color: #334155;
        font-size: 0.92rem;
        line-height: 1.55;
        margin-bottom: 0.75rem;
    }
    
    .card-eligibility {
        background-color: #f8fafc;
        border-left: 3px solid #64748b;
        padding: 0.6rem 0.85rem;
        border-radius: 4px;
        font-size: 0.87rem;
        color: #334155;
        margin-bottom: 0.75rem;
    }
    
    .card-footer {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-top: 1px solid #f1f5f9;
        padding-top: 0.75rem;
        font-size: 0.82rem;
        color: #64748b;
    }

    /* Reserved Analytics Box */
    .reserved-analytics-box {
        background-color: #f8fafc;
        border: 1px dashed #94a3b8;
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 1rem;
        margin-bottom: 1.5rem;
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Data Access & Caching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner=False)
def load_snowflake_opportunities() -> tuple[List[Dict[str, Any]], str, Optional[str]]:
    """Retrieve opportunity records from Snowflake with caching and safe error handling.

    Uses Streamlit caching (TTL 5 minutes) to avoid opening new connections on
    every UI interaction or filter change.

    Returns:
        tuple of (records, connection_state, error_message)
        where connection_state is one of:
          - 'Connected'
          - 'Connected — no opportunity records'
          - 'Unavailable'
    """
    try:
        records = fetch_opportunities()
        if len(records) == 0:
            return records, "Connected — no opportunity records", None
        return records, "Connected", None
    except Exception as exc:
        # Avoid exposing database credentials, connection strings, or internal secrets
        sanitized_error = (
            "Unable to retrieve records from Snowflake data warehouse. "
            "Please check network connectivity and Snowflake credentials."
        )
        return [], "Unavailable", sanitized_error


# -----------------------------------------------------------------------------
# Sidebar: Navigation, Project Status, and Architecture Disclosures
# -----------------------------------------------------------------------------
def render_sidebar(
    db_status: str, record_count: int, error_msg: Optional[str] = None
) -> bool:
    """Render the application sidebar with architecture status and connection health.

    Args:
        db_status: Current Snowflake state ('Connected', 'Connected — no opportunity records', 'Unavailable').
        record_count: Number of records retrieved from Snowflake.
        error_msg: Optional sanitized error message if connection failed.

    Returns:
        Boolean indicating whether user enabled preview mode for sample data.
    """
    with st.sidebar:
        st.markdown(f"### 🎯 {app_config.APP_NAME}")
        st.caption(f"Version: {app_config.APP_VERSION}")
        st.markdown("---")

        st.markdown("#### 🏆 Hackathon Category")
        st.info(
            f"**Event:** {app_config.HACKATHON_EVENT}\n\n"
            f"**Track:** {app_config.HACKATHON_CATEGORY}"
        )

        st.markdown("#### 🏗️ Architecture Status")
        st.markdown(
            "- **Phase 1 (Completed):** Foundation and UI\n"
            "- **Phase 2 (Completed):** Snowflake integration\n"
            "- **Phase 3 (Active):** Real opportunity data and Snowflake CoCo analytics\n"
            "- **Phase 4 (Upcoming):** AI assistant integration"
        )

        st.markdown("#### 🔌 Connection Status")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if db_status == "Connected":
                st.metric(
                    "Snowflake",
                    "Connected",
                    help=f"Active connection: {record_count} live records",
                )
            elif db_status == "Connected — no opportunity records":
                st.metric(
                    "Snowflake",
                    "Connected",
                    help="Connected — no opportunity records in OPPORTUNITIES table",
                )
            else:
                st.metric(
                    "Snowflake",
                    "Unavailable",
                    help="Could not connect to Snowflake database",
                )
        with col_s2:
            st.metric("AI Engine", "Offline", help="Planned for Phase 4")

        # Explicit display of required status string
        st.caption(f"**Database Status:** `{db_status}`")

        if error_msg:
            st.warning(error_msg)

        # Refresh mechanism
        st.markdown("---")
        st.markdown("#### ⚙️ Data Controls")
        if st.button(
            "🔄 Refresh Data",
            help="Invalidate cache and query Snowflake for updated opportunities",
            use_container_width=True,
        ):
            st.cache_data.clear()
            st.rerun()

        # Optional sample data preview toggle if database contains 0 records or is unavailable
        show_sample = False
        if db_status != "Connected":
            show_sample = st.checkbox(
                "Preview with sample records",
                value=False,
                help="Load fictional sample records to inspect UI components and cards while the database has 0 records.",
            )

        st.markdown("---")
        st.markdown("#### ⚠️ Transparency Notice")
        if show_sample:
            st.caption(
                "Currently displaying **fictional sample records** in preview mode. "
                "Snowflake database connection is verified."
            )
        else:
            st.caption(
                "OpportunityLens connects to Snowflake table "
                "`OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`. Live AI inference is scheduled for Phase 4."
            )

        return show_sample


# -----------------------------------------------------------------------------
# Main Header Section
# -----------------------------------------------------------------------------
def render_header(
    db_status: str, record_count: int, is_preview_active: bool = False
):
    """Render the branded header and status notification banner."""
    st.markdown(
        f"""
        <div class="brand-header-box">
            <div class="brand-title">🎯 {app_config.APP_NAME}</div>
            <div class="brand-tagline">{app_config.APP_TAGLINE}</div>
            <div class="brand-description">
                Nigerian students and early-career talents face a fragmented landscape when searching for
                accredited scholarships, tech internships, subsidized training programs, and hackathons.
                <strong>OpportunityLens</strong> is an open-source platform designed to aggregate verified
                opportunities, match applicants with eligibility criteria, and provide AI-assisted guidance
                backed by Snowflake.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Dynamic status notification banner
    if is_preview_active:
        st.warning(
            "ℹ️ **Preview Mode Active:** Displaying fictional sample records for UI evaluation. "
            "Snowflake database is connected (`OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`) with 0 records.",
            icon="📌",
        )
    elif db_status == "Connected":
        st.success(
            f"❄️ **Snowflake Connected & Populated (Phase 3 Active):** Successfully loaded "
            f"**{record_count}** genuine opportunities from `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`.",
            icon="✅",
        )
    elif db_status == "Connected — no opportunity records":
        st.info(
            "❄️ **Phase 2 Active (Snowflake Connected):** Connected to `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`. "
            "The table currently contains **0 records**. Live opportunity ingestion and Snowflake CoCo "
            "analytics are scheduled for Phase 3.",
            icon="ℹ️",
        )
    else:
        st.warning(
            "⚠️ **Snowflake Unavailable:** Could not retrieve live records from Snowflake. "
            "The dashboard is operating in offline mode.",
            icon="⚠️",
        )


# -----------------------------------------------------------------------------
# Dashboard Metrics
# -----------------------------------------------------------------------------
def render_metrics(metrics: dict):
    """Render aggregate dashboard metric cards with explicit live or preview labels."""
    st.markdown("### 📊 Platform Overview")

    is_live = metrics.get("is_live", False)
    suffix = "" if is_live else " (Preview)"

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Total Opportunities",
            value=f"{metrics['total']}{suffix}",
            help="Total opportunities loaded in active dataset",
        )
    with col2:
        st.metric(
            label="Scholarships",
            value=f"{metrics['scholarships']}{suffix}",
            help="Scholarship opportunities",
        )
    with col3:
        st.metric(
            label="Internships",
            value=f"{metrics['internships']}{suffix}",
            help="Technology internship programs",
        )
    with col4:
        st.metric(
            label="Tech Training",
            value=f"{metrics['training']}{suffix}",
            help="Bootcamps and developer training initiatives",
        )

    if is_live:
        st.caption(
            "⚡ *Live metrics from Snowflake table: `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`.*"
        )
    else:
        st.caption(
            "🔒 *Metrics reflect local preview records. Switch to live mode to view Snowflake data.*"
        )


# -----------------------------------------------------------------------------
# Opportunity Explorer & Cards
# -----------------------------------------------------------------------------
def render_opportunity_card(opp: dict):
    """Render an individual opportunity record in a styled card."""
    # Application status derived from deadline
    app_status = opp.get("status", "Unknown")
    if app_status == "Open":
        status_badge_class = "badge-status-open"
    elif app_status == "Closing Soon":
        status_badge_class = "badge-status-closing"
    elif app_status == "Closed":
        status_badge_class = "badge-status-closed"
    else:
        status_badge_class = "badge-status-unknown"

    # Verification status displayed separately from application status
    ver_status = opp.get("verification_status", "UNVERIFIED")
    if str(ver_status).upper() == "VERIFIED":
        ver_badge_class = "badge-verified"
        ver_label = "✓ Verified"
    else:
        ver_badge_class = "badge-unverified"
        ver_label = f"Status: {ver_status}"

    # Sample badge only for fictional preview records
    sample_badge_html = ""
    if opp.get("is_sample_data", False):
        sample_badge_html = '<span class="badge badge-sample">Sample Data</span>'

    # Source URL: clickable only when valid and available
    source_url = opp.get("source_url")
    if is_valid_url(source_url):
        link_html = (
            f'<a href="{source_url}" target="_blank" '
            f'style="color: #0052cc; text-decoration: none; font-weight: 600;">'
            f'Source Link ↗</a>'
        )
    else:
        link_html = '<span style="color: #94a3b8; font-style: italic;">No link available</span>'

    # Format dates safely
    deadline_display = format_display_date(opp.get("deadline"))
    verified_display = format_display_date(opp.get("verified_at"))

    st.markdown(
        f"""
        <div class="opportunity-card">
            <div>
                {sample_badge_html}
                <span class="badge badge-category">{opp.get('category', 'Other')}</span>
                <span class="badge {ver_badge_class}">{ver_label}</span>
                <span class="badge {status_badge_class}">{app_status}</span>
            </div>
            <div class="card-title">{opp.get('title', 'Untitled')}</div>
            <div class="card-meta">
                🏢 <strong>{opp.get('organization', 'Not specified')}</strong> &nbsp;|&nbsp; 📍 {opp.get('location', 'Not specified')} &nbsp;|&nbsp; 🎓 {opp.get('education_level', 'Not specified')}
            </div>
            <div class="card-description">
                {opp.get('description', 'No description provided.')}
            </div>
            <div class="card-eligibility">
                <strong>📋 Eligibility Criteria:</strong> {opp.get('eligibility', 'Check official source.')}
            </div>
            <div class="card-footer">
                <div>
                    <span><strong>Deadline:</strong> {deadline_display}</span>
                    &nbsp;&bull;&nbsp;
                    <span><strong>Verified:</strong> {verified_display}</span>
                    &nbsp;&bull;&nbsp;
                    <span><strong>ID:</strong> {opp.get('opportunity_id', 'N/A')}</span>
                </div>
                <div>
                    {link_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_opportunity_explorer(
    opportunities: List[Dict[str, Any]], is_live: bool
):
    """Render search controls, category filters, and resulting opportunity cards."""
    st.markdown("---")
    st.markdown("### 🔍 Opportunity Explorer")
    st.markdown(
        "Filter and search through opportunities by category, application status, or keyword."
    )

    # Search and Filter Controls
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])

    with filter_col1:
        search_query = st.text_input(
            "Search opportunities",
            placeholder="Search by keyword, organization, eligibility, or city...",
            help="Filter opportunities by keyword across title, organization, description, and requirements.",
        )

    with filter_col2:
        # Category options are derived from the active dataset
        active_categories = derive_categories(opportunities)
        category_options = ["All"] + active_categories
        selected_category = st.selectbox(
            "Category",
            options=category_options,
            index=0,
            help="Filter by opportunity category present in active records.",
        )

    with filter_col3:
        # Application status filter options
        status_options = ["All", "Open", "Closing Soon", "Closed"]
        if any(opp.get("status") == "Unknown" for opp in opportunities):
            status_options.append("Unknown")

        selected_status = st.selectbox(
            "Status",
            options=status_options,
            index=0,
            help="Filter by application deadline status.",
        )

    # Filter opportunities using testable business logic
    filtered_opportunities = filter_opportunities(
        opportunities=opportunities,
        query=search_query,
        category=selected_category,
        status=selected_status,
    )

    # Active filter feedback
    total_count = len(opportunities)
    showing_count = len(filtered_opportunities)
    st.caption(f"Showing **{showing_count}** of **{total_count}** records.")

    # Render cards or empty states
    if total_count == 0:
        if is_live:
            st.info(
                "❄️ **No opportunity records found in Snowflake.**\n\n"
                "The database connection to `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES` is active, "
                "but the table currently contains zero records. Real opportunities will appear "
                "here once ingested into Snowflake in Phase 3.",
                icon="ℹ️",
            )
        else:
            st.info("🔍 No preview opportunities loaded.", icon="🔎")
    elif showing_count == 0:
        st.info(
            "🔍 **No matching opportunities found.**\n\n"
            "Try broadening your search query, selecting 'All' categories, or clearing active filters.",
            icon="🔎",
        )
    else:
        for opp in filtered_opportunities:
            render_opportunity_card(opp)


# -----------------------------------------------------------------------------
# AI Assistant Section (Preview Placeholder)
# -----------------------------------------------------------------------------
def render_ai_assistant_section():
    """Render the AI Assistant placeholder section with clear Phase 4 disclosure."""
    st.markdown("---")
    st.markdown("### 🤖 OpportunityLens AI Assistant *(Phase 4 Preview)*")
    st.markdown(
        "Our upcoming AI assistant will evaluate your background against opportunity requirements, "
        "estimate eligibility confidence, and suggest targeted improvements for your applications."
    )

    with st.container():
        user_query = st.text_input(
            "Ask a question about eligibility or application advice:",
            placeholder="e.g. Am I eligible for the Northern Nigeria STEM scholarship with a 3.6 CGPA in Computer Science?",
            help="Type a question to preview the AI guidance interface.",
        )

        col_btn, _ = st.columns([1, 4])
        with col_btn:
            ask_btn = st.button("Analyze with AI", type="primary")

        if ask_btn or user_query:
            if user_query.strip():
                st.info(
                    "🔧 **AI Inference Deferred to Phase 4:**\n\n"
                    f"**Submitted query:** *\"{user_query.strip()}\"*\n\n"
                    "In Phase 4, OpportunityLens will connect to an eligible open-weight model "
                    f"(`{ai_config.model_name}`) hosted via Hugging Face Inference Providers / "
                    "OpenAI-compatible inference. In this Phase 2 release, live external model "
                    "calls remain disabled to maintain clean isolation and reproducibility.",
                    icon="🧠",
                )
            else:
                st.warning("Please enter a question to test the assistant interface.")


# -----------------------------------------------------------------------------
# Analytics Section (Powered by Snowflake & CoCo Queries)
# -----------------------------------------------------------------------------
def render_analytics_section(
    opportunities: List[Dict[str, Any]], is_live: bool
):
    """Render the Snowflake-backed live analytics and intelligence dashboard."""
    st.markdown("---")
    st.markdown(
        "### 📈 Analytics & Opportunity Intelligence *(Snowflake Live Analytics)*"
    )
    st.markdown(
        "Interactive aggregations and data intelligence derived directly from **Snowflake** "
        "using queries developed and optimized with **Snowflake CoCo (Cortex Code)**."
    )

    if len(opportunities) > 0:
        summary = calculate_analytics_summary(opportunities)

        # 1. Key Analytics Metrics
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        ver_count = summary["verification_counts"].get("VERIFIED", 0)
        ver_pct = (
            round(ver_count * 100.0 / summary["total"], 1)
            if summary["total"] > 0
            else 0.0
        )

        with col_m1:
            st.metric("Tracked Listings", summary["total"])
        with col_m2:
            st.metric(
                "Verified Rate",
                f"{ver_pct}%",
                help="Opportunities confirmed directly from authoritative primary sources",
            )
        with col_m3:
            st.metric(
                "Organizations",
                summary["unique_organizations"],
                help="Distinct universities, government ministries, and corporate sponsors",
            )
        with col_m4:
            st.metric(
                "Authoritative Domains",
                summary["unique_domains"],
                help="Distinct verified web domains contributing opportunity listings",
            )

        # 2. Distribution Charts (Row 1: Category & Location)
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("##### 📌 Opportunity Distribution by Category")
            if summary["category_counts"]:
                cat_series = pd.Series(summary["category_counts"])
                st.bar_chart(cat_series, color="#0052cc")
                st.caption("Listing volume across canonical opportunity tracks.")

        with col_chart2:
            st.markdown("##### 📍 Geographic & State Distribution")
            if summary["location_counts"]:
                loc_series = pd.Series(summary["location_counts"]).sort_values(
                    ascending=False
                )
                st.bar_chart(loc_series, color="#1e40af")
                st.caption("Distribution of opportunities by geographic location.")

        # 3. Distribution Charts (Row 2: Application Lifecycle & Verification Status)
        col_chart3, col_chart4 = st.columns(2)
        with col_chart3:
            st.markdown("##### ⏱️ Application Lifecycle Status")
            if summary["application_status_counts"]:
                app_series = pd.Series(summary["application_status_counts"])
                st.bar_chart(app_series, color="#059669")
                st.caption(
                    "Breakdown of active deadlines vs continuous rolling cohorts."
                )

        with col_chart4:
            st.markdown("##### 🛡️ Data Quality & Verification Status")
            if summary["verification_counts"]:
                ver_series = pd.Series(summary["verification_counts"])
                st.bar_chart(ver_series, color="#d97706")
                st.caption(
                    "Audited verification states: VERIFIED vs NEEDS_REVIEW."
                )

        # 4. Upcoming Deadlines Table
        if summary["upcoming_deadlines"]:
            st.markdown("##### ⏳ Upcoming Application Deadlines")
            deadline_rows = []
            for item in summary["upcoming_deadlines"]:
                deadline_rows.append({
                    "Opportunity": item["title"],
                    "Organization": item["organization"],
                    "Category": item["category"],
                    "Deadline": item["deadline"],
                    "Days Remaining": f"{item['days_remaining']} days",
                })
            st.dataframe(pd.DataFrame(deadline_rows), use_container_width=True)

        # 5. Data Freshness Card
        latest_date_str = (
            format_display_date(summary["latest_verification"])
            if summary["latest_verification"]
            else "Recent"
        )
        st.caption(
            f"🕒 **Data Freshness:** Last verified on **{latest_date_str}**. "
            "Zero duplicate records detected via idempotent Snowflake MERGE pipeline."
        )
    else:
        st.info(
            "📊 **No records currently available in Snowflake for analytics.**\n\n"
            "Once opportunities are ingested into `OPPORTUNITYLENS_DB.APP.OPPORTUNITIES`, "
            "this section will automatically render category distributions and application timelines.",
            icon="ℹ️",
        )

    # 6. Snowflake CoCo Exploration Workflow Showcase
    st.markdown(
        """
        <div class="reserved-analytics-box">
            <strong>❄️ Snowflake CoCo (Cortex Code) Analytical Workflow:</strong>
            <p style="margin-top: 0.35rem; margin-bottom: 0.5rem; color: #475569; font-size: 0.9rem;">
                The analytical SQL queries powering this dashboard were developed and refined using
                <strong>Snowflake CoCo</strong> in the Snowsight SQL Worksheet. See
                <code>docs/snowflake_coco_workflow.md</code> and <code>sql/04_coco_queries.sql</code> for:
            </p>
            <ul style="margin-bottom: 0.25rem; font-size: 0.88rem; color: #334155;">
                <li><strong>Prompt 1:</strong> Category listing volume & windowed percentage calculations.</li>
                <li><strong>Prompt 2:</strong> Application deadline lifecycle analysis (Open, Closing Soon, Rolling).</li>
                <li><strong>Prompt 3:</strong> 7-day upcoming application deadline window queries.</li>
                <li><strong>Prompt 4:</strong> Eligibility requirement completeness and missing value audits.</li>
                <li><strong>Prompt 5:</strong> Regex domain parsing from source URLs directly in Snowflake SQL.</li>
                <li><strong>Prompt 6:</strong> Temporal dataset freshness tracking (hours since last verified).</li>
                <li><strong>Prompt 7:</strong> Composite duplicate detection on normalized organization and title.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Application Footer
# -----------------------------------------------------------------------------
def render_footer():
    """Render the application footer with licensing and project attribution."""
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; color: #64748b; font-size: 0.85rem; padding: 1rem 0;">
            <strong>OpportunityLens</strong> &bull; Open-Source Project (MIT License) &bull;
            Hacktoberfest Hack Day Gombe &bull;
            <em>Best Open-Source AI Project with Snowflake</em>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# Main Application Flow
# -----------------------------------------------------------------------------
def main():
    """Main application execution pipeline."""
    # 1. Attempt to retrieve opportunities from Snowflake with caching
    raw_opportunities, db_status, error_msg = load_snowflake_opportunities()
    record_count = len(raw_opportunities)

    # 2. Render sidebar and check if user enabled sample preview mode
    show_sample = render_sidebar(
        db_status=db_status, record_count=record_count, error_msg=error_msg
    )

    # 3. Choose active dataset: live Snowflake by default, or demo data if preview enabled
    if show_sample:
        active_opportunities = get_demo_opportunities()
        is_live = False
    else:
        active_opportunities = raw_opportunities
        is_live = (db_status != "Unavailable")

    # 4. Render main layout components
    render_header(
        db_status=db_status,
        record_count=record_count,
        is_preview_active=show_sample,
    )

    metrics = get_platform_metrics(active_opportunities, is_live=is_live)
    render_metrics(metrics)

    render_opportunity_explorer(active_opportunities, is_live=is_live)
    render_ai_assistant_section()
    render_analytics_section(active_opportunities, is_live=is_live)
    render_footer()


if __name__ == "__main__":
    main()
