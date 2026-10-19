"""OpportunityLens — Streamlit Web Application (Phase 1).

Find opportunities. Understand your chances. Take your next step.
Hacktoberfest Hack Day Gombe: Best Open-Source AI Project with Snowflake.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.config import app_config, snowflake_config, ai_config
from src.demo_data import (
    filter_opportunities,
    get_categories,
    get_demo_metrics,
    get_demo_opportunities,
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
# Sidebar: Navigation, Project Status, and Architecture Disclosures
# -----------------------------------------------------------------------------
def render_sidebar():
    """Render the application sidebar with architecture status and project disclosures."""
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
            "- **Phase 1 (Current):** Project foundation & UI explorer\n"
            "- **Phase 2 (Upcoming):** Snowflake connection & open dataset\n"
            "- **Phase 3 (Upcoming):** Snowflake CoCo SQL pipeline & analytics\n"
            "- **Phase 4 (Upcoming):** Open-weight AI assistant"
        )

        st.markdown("#### 🔌 Connection Status")
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            st.metric("Snowflake", "Offline", help="Planned for Phase 2")
        with col_s2:
            st.metric("AI Engine", "Offline", help="Planned for Phase 4")

        st.markdown("---")
        st.markdown("#### ⚠️ Transparency Notice")
        st.caption(
            "All opportunity records currently displayed in this interface are "
            "**fictional sample records** created strictly for user interface "
            "evaluation. No live database queries or external AI inference calls "
            "are executed during Phase 1."
        )


# -----------------------------------------------------------------------------
# Main Header Section
# -----------------------------------------------------------------------------
def render_header():
    """Render the branded header and concise problem statement."""
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

    # Clear phase status notification banner
    st.warning(
        "ℹ️ **Phase 1 Prototype Notice:** Database connections and live AI services are intentionally "
        "deferred to subsequent phases. Displayed metrics and listings below are clearly labelled "
        "preview records.",
        icon="📌",
    )


# -----------------------------------------------------------------------------
# Dashboard Metrics
# -----------------------------------------------------------------------------
def render_metrics(metrics: dict):
    """Render aggregate dashboard metric cards with explicit preview disclosures."""
    st.markdown("### 📊 Platform Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            label="Total Opportunities",
            value=f"{metrics['total']} (Preview)",
            help="Total sample records currently loaded in UI memory",
        )
    with col2:
        st.metric(
            label="Scholarships",
            value=f"{metrics['scholarships']} (Preview)",
            help="Fictional scholarship opportunities",
        )
    with col3:
        st.metric(
            label="Internships",
            value=f"{metrics['internships']} (Preview)",
            help="Fictional technology internship programs",
        )
    with col4:
        st.metric(
            label="Tech Training",
            value=f"{metrics['training']} (Preview)",
            help="Fictional bootcamps and developer training initiatives",
        )
    st.caption("🔒 *Metrics reflect local preview records. Live statistics will connect to Snowflake in Phase 2.*")


# -----------------------------------------------------------------------------
# Opportunity Explorer & Cards
# -----------------------------------------------------------------------------
def render_opportunity_card(opp: dict):
    """Render an individual opportunity record in a styled card."""
    status = opp.get("status", "Open")
    if status == "Open":
        status_badge_class = "badge-status-open"
    elif status == "Closing Soon":
        status_badge_class = "badge-status-closing"
    else:
        status_badge_class = "badge-status-closed"

    st.markdown(
        f"""
        <div class="opportunity-card">
            <div>
                <span class="badge badge-sample">Sample Data</span>
                <span class="badge badge-category">{opp.get('category')}</span>
                <span class="badge {status_badge_class}">{status}</span>
            </div>
            <div class="card-title">{opp.get('title')}</div>
            <div class="card-meta">
                🏢 <strong>{opp.get('organization')}</strong> &nbsp;|&nbsp; 📍 {opp.get('location')} &nbsp;|&nbsp; 🎓 {opp.get('education_level')}
            </div>
            <div class="card-description">
                {opp.get('description')}
            </div>
            <div class="card-eligibility">
                <strong>📋 Eligibility Criteria:</strong> {opp.get('eligibility')}
            </div>
            <div class="card-footer">
                <div>
                    <span><strong>Deadline:</strong> {opp.get('deadline')}</span>
                    &nbsp;&bull;&nbsp;
                    <span><strong>Verified:</strong> {opp.get('verified_at')[:10]}</span>
                    &nbsp;&bull;&nbsp;
                    <span><strong>ID:</strong> {opp.get('opportunity_id')}</span>
                </div>
                <div>
                    <a href="{opp.get('source_url')}" target="_blank" style="color: #0052cc; text-decoration: none; font-weight: 600;">
                        Source Link ↗
                    </a>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_opportunity_explorer():
    """Render search controls, category filters, and resulting opportunity cards."""
    st.markdown("---")
    st.markdown("### 🔍 Opportunity Explorer")
    st.markdown("Filter and search through sample opportunities by category, status, or keyword.")

    # Search and Filter Controls
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])

    with filter_col1:
        search_query = st.text_input(
            "Search opportunities",
            placeholder="Search by keyword, organization, eligibility, or city...",
            help="Filter opportunities by keyword across title, organization, description, and requirements.",
        )

    with filter_col2:
        category_options = ["All"] + get_categories()
        selected_category = st.selectbox(
            "Category",
            options=category_options,
            index=0,
            help="Filter by specific opportunity type.",
        )

    with filter_col3:
        status_options = ["All", "Open", "Closing Soon", "Closed"]
        selected_status = st.selectbox(
            "Status",
            options=status_options,
            index=0,
            help="Filter by application timeline status.",
        )

    # Retrieve and filter opportunities
    all_opportunities = get_demo_opportunities()
    filtered_opportunities = filter_opportunities(
        opportunities=all_opportunities,
        query=search_query,
        category=selected_category,
        status=selected_status,
    )

    # Active filter feedback
    total_count = len(all_opportunities)
    showing_count = len(filtered_opportunities)
    st.caption(f"Showing **{showing_count}** of **{total_count}** preview records.")

    # Render cards or empty state
    if filtered_opportunities:
        for opp in filtered_opportunities:
            render_opportunity_card(opp)
    else:
        st.info(
            "🔍 **No matching opportunities found.**\n\n"
            "Try broadening your search query, selecting 'All' categories, or clearing active filters.",
            icon="🔎",
        )


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
                    "OpenAI-compatible inference. In this Phase 1 foundation, live external model "
                    "calls are disabled to maintain clean isolation and reproducibility.",
                    icon="🧠",
                )
            else:
                st.warning("Please enter a question to test the assistant interface.")


# -----------------------------------------------------------------------------
# Analytics Section (Reserved for Snowflake)
# -----------------------------------------------------------------------------
def render_analytics_section():
    """Render the Snowflake-backed analytics placeholder section."""
    st.markdown("---")
    st.markdown("### 📈 Analytics & Opportunity Intelligence *(Snowflake Reserved)*")
    st.markdown(
        "This section will showcase data aggregation pipelines and automated trend analysis "
        "powered by **Snowflake CoCo** and the **Snowflake Python Connector** in Phases 2 and 3."
    )

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("##### 📌 Sample Category Distribution (Preview)")
        demo_records = get_demo_opportunities()
        df = pd.DataFrame(demo_records)
        category_counts = df["category"].value_counts()
        st.bar_chart(category_counts, color="#0052cc")
        st.caption("Local preview breakdown of sample records by category.")

    with col_chart2:
        st.markdown("##### ⏱️ Sample Application Status Breakdown (Preview)")
        status_counts = df["status"].value_counts()
        st.bar_chart(status_counts, color="#2563eb")
        st.caption("Local preview breakdown of sample records by status.")

    st.markdown(
        """
        <div class="reserved-analytics-box">
            <strong>❄️ Snowflake CoCo Integration Roadmap:</strong>
            <ul style="margin-top: 0.5rem; margin-bottom: 0.25rem;">
                <li><strong>Phase 2:</strong> Connect Snowflake Python Connector to query free public datasets on education and career opportunities.</li>
                <li><strong>Phase 3:</strong> Use Snowflake CoCo to build automated aggregation queries, materialized views, and deadline monitoring pipelines.</li>
                <li><strong>Phase 4:</strong> Ground LLM context retrieval on verified Snowflake opportunity tables.</li>
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
    render_sidebar()
    render_header()
    
    metrics = get_demo_metrics()
    render_metrics(metrics)
    
    render_opportunity_explorer()
    render_ai_assistant_section()
    render_analytics_section()
    render_footer()


if __name__ == "__main__":
    main()
