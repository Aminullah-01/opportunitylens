"""OpportunityLens — modern opportunity discovery platform.

Helps students, graduates, and early-career professionals discover
scholarships, internships, entry-level jobs, hackathons, fellowships, and
training programs with trustworthy source links, eligibility guidance, and
personalized matching.

The public interface intentionally exposes only user-facing discovery
information. Ingestion, data-quality, and monitoring diagnostics live in the
CLI tools under ``src.quality`` and ``src.monitoring`` and in application logs.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

import streamlit as st

from src.ai import ExplanationResponse, generate_opportunity_explanation
from src.config import app_config, ingestion_config
from src.db import fetch_opportunities
from src.demo_data import VALID_CATEGORIES, filter_opportunities, get_demo_opportunities
from src.matching import (
    ProfileValidationError,
    StudentProfile,
    VALID_DELIVERY_MODES,
    VALID_EDUCATION_LEVELS,
    match_opportunities,
    validate_profile,
)
from src.ui import (
    inject_ui_styles,
    render_empty_state,
    render_hero,
    render_opportunity_card,
    render_service_unavailable,
    show_opportunity_details_dialog,
)
from src.utils import derive_categories, derive_education_levels, derive_locations, escape_markdown

logger = logging.getLogger(__name__)

NAV_OPTIONS = ["Opportunities", "My Profile", "Saved", "About"]

DELIVERY_MODE_LABELS = {
    "unspecified": "No preference",
    "remote": "Remote",
    "on-site": "On-site",
    "hybrid": "Hybrid",
}

PROFILE_WIDGET_KEYS = (
    "profile_edu",
    "profile_field",
    "profile_cgpa",
    "profile_grad",
    "profile_location",
    "profile_skills",
    "profile_delivery",
    "profile_categories",
    "profile_goals",
)

# -----------------------------------------------------------------------------
# Streamlit page setup
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title=f"{app_config.APP_NAME} — Opportunity discovery",
    page_icon=":material/travel_explore:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

inject_ui_styles()


# -----------------------------------------------------------------------------
# Data access
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300, show_spinner="Loading opportunities…")
def load_snowflake_opportunities() -> tuple[List[Dict[str, Any]], str]:
    """Load opportunity records from Snowflake with caching and safe handling.

    Returns:
        A tuple of ``(records, connection_state)`` where ``connection_state``
        is ``"Connected"`` or ``"Unavailable"``. Failures are logged with full
        detail; only a neutral state is returned to the interface.
    """
    try:
        records = fetch_opportunities()
        return records, "Connected"
    except Exception:
        logger.exception("Unable to retrieve opportunities from the data warehouse")
        return [], "Unavailable"


# -----------------------------------------------------------------------------
# Session-state helpers and filter callbacks
# -----------------------------------------------------------------------------
def reset_filters_callback() -> None:
    """Reset every search and filter control to its default state."""
    st.session_state["filter_search_query"] = ""
    st.session_state["filter_category"] = "All"
    st.session_state["filter_location"] = "All"
    st.session_state["filter_status"] = "All"
    st.session_state["filter_edu_level"] = "All"


def _ensure_valid_selection(key: str, options: List[str]) -> None:
    """Reset a widget's stored selection when it is no longer in its options."""
    if key in st.session_state and st.session_state[key] not in options:
        st.session_state[key] = options[0]


def _load_example_profile() -> None:
    """Populate the profile form with an example profile so users can preview matching."""
    example = validate_profile(
        education_level="Undergraduate",
        field_of_study="Computer Science",
        skills=["Python", "SQL", "Git", "Data Analysis"],
        location="Gombe",
        preferred_categories=["Scholarships", "Internships", "Tech Training"],
        delivery_mode="unspecified",
        graduation_year=2026,
        cgpa=3.65,
        additional_goals="Seeking software engineering or data internships and tech scholarships.",
    )
    st.session_state["student_profile"] = example
    st.session_state["profile_edu"] = example.education_level
    st.session_state["profile_field"] = example.field_of_study or ""
    st.session_state["profile_cgpa"] = float(example.cgpa or 0.0)
    st.session_state["profile_grad"] = (
        str(example.graduation_year) if example.graduation_year else "Not specified"
    )
    st.session_state["profile_location"] = example.location or ""
    st.session_state["profile_skills"] = ", ".join(example.skills)
    st.session_state["profile_delivery"] = example.delivery_mode
    st.session_state["profile_categories"] = list(example.preferred_categories)
    st.session_state["profile_goals"] = example.additional_goals or ""
    st.session_state["matching_query"] = ""


def _clear_profile() -> None:
    """Remove the saved profile and reset the profile form fields."""
    st.session_state["student_profile"] = None
    for key in PROFILE_WIDGET_KEYS:
        st.session_state.pop(key, None)
    st.session_state["matching_query"] = ""


def _clear_matching_query() -> None:
    """Clear the natural-language match query and any displayed results."""
    st.session_state["matching_query"] = ""


# -----------------------------------------------------------------------------
# Header and navigation
# -----------------------------------------------------------------------------
def render_header() -> str:
    """Render the compact brand header and primary view navigation."""
    col_brand, col_nav = st.columns([1, 2], vertical_alignment="center")

    with col_brand:
        st.html(
            """
            <div class="ol-brand">
                <span class="ol-brand-mark">🎯</span>
                <span class="ol-brand-name">OpportunityLens</span>
            </div>
            """
        )

    with col_nav:
        selected = st.segmented_control(
            "Primary navigation",
            options=NAV_OPTIONS,
            default=st.session_state.get("active_nav", NAV_OPTIONS[0]),
            key="nav_selection",
            label_visibility="collapsed",
            width="stretch",
        )

    if selected and selected in NAV_OPTIONS:
        st.session_state["active_nav"] = selected
    elif st.session_state.get("active_nav") not in NAV_OPTIONS:
        st.session_state["active_nav"] = NAV_OPTIONS[0]

    st.divider()
    return st.session_state["active_nav"]


# -----------------------------------------------------------------------------
# Opportunity discovery
# -----------------------------------------------------------------------------
def render_discover_view(opportunities: List[Dict[str, Any]]) -> None:
    """Render search, category navigation, filters, and the opportunity grid."""
    render_hero()

    if not opportunities:
        render_empty_state(
            title="No opportunities are available right now",
            description=(
                "New scholarships, internships, and jobs are added regularly. "
                "Please check back soon."
            ),
        )
        return

    st.text_input(
        "Search opportunities",
        key="filter_search_query",
        placeholder="Search scholarships, internships, jobs…",
        label_visibility="collapsed",
        help="Search titles, organizations, descriptions, locations, and requirements.",
    )

    present_categories = derive_categories(opportunities)
    ordered_categories = [c for c in VALID_CATEGORIES if c in present_categories]
    ordered_categories += [c for c in present_categories if c not in VALID_CATEGORIES]
    category_options = ["All"] + ordered_categories
    _ensure_valid_selection("filter_category", category_options)

    st.pills(
        "Category",
        options=category_options,
        key="filter_category",
        label_visibility="collapsed",
    )

    location_options = ["All"] + derive_locations(opportunities)
    education_options = ["All"] + derive_education_levels(opportunities)
    status_options = ["All", "Open", "Closing Soon", "Closed"]

    _ensure_valid_selection("filter_location", location_options)
    _ensure_valid_selection("filter_edu_level", education_options)
    _ensure_valid_selection("filter_status", status_options)

    col_location, col_education, col_status = st.columns(3)
    with col_location:
        st.selectbox("Location", options=location_options, key="filter_location")
    with col_education:
        st.selectbox("Education level", options=education_options, key="filter_edu_level")
    with col_status:
        st.selectbox("Application status", options=status_options, key="filter_status")

    filtered = filter_opportunities(
        opportunities=opportunities,
        query=st.session_state.get("filter_search_query", ""),
        category=st.session_state.get("filter_category", "All"),
        status=st.session_state.get("filter_status", "All"),
        location=st.session_state.get("filter_location", "All"),
        education_level=st.session_state.get("filter_edu_level", "All"),
    )

    has_active_filters = (
        bool(str(st.session_state.get("filter_search_query", "")).strip())
        or st.session_state.get("filter_category", "All") != "All"
        or st.session_state.get("filter_location", "All") != "All"
        or st.session_state.get("filter_status", "All") != "All"
        or st.session_state.get("filter_edu_level", "All") != "All"
    )

    total_label = "opportunity" if len(opportunities) == 1 else "opportunities"

    col_count, col_reset = st.columns([4, 1], vertical_alignment="center")
    with col_count:
        if has_active_filters:
            st.caption(f"Showing {len(filtered)} of {len(opportunities)} opportunities")
        else:
            st.caption(f"{len(opportunities)} {total_label} available")
    with col_reset:
        if has_active_filters:
            st.button(
                "Reset filters",
                on_click=reset_filters_callback,
                icon=":material/refresh:",
                width="stretch",
            )

    if not filtered:
        render_empty_state(
            title="No opportunities match your filters",
            description=(
                "Try a broader search or clear your filters to see every "
                "available opportunity."
            ),
            action_label="Clear all filters",
            on_action=reset_filters_callback,
        )
        return

    left_column, right_column = st.columns(2)
    for index, opportunity in enumerate(filtered):
        target = left_column if index % 2 == 0 else right_column
        with target:
            render_opportunity_card(opportunity, key_prefix="discover")


# -----------------------------------------------------------------------------
# Profile and personalized matching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def _cached_explanation(
    profile: StudentProfile,
    matches: tuple,
    query: str,
) -> ExplanationResponse:
    """Cache grounded match explanations so reruns do not repeat AI requests."""
    return generate_opportunity_explanation(
        profile=profile,
        matches=list(matches),
        user_query=query,
    )


def _profile_form_defaults(profile: Optional[StudentProfile]) -> Dict[str, Any]:
    """Build the initial widget values for the profile form."""
    return {
        "profile_edu": (
            profile.education_level
            if profile and profile.education_level in VALID_EDUCATION_LEVELS
            else VALID_EDUCATION_LEVELS[0]
        ),
        "profile_field": (profile.field_of_study or "") if profile else "",
        "profile_cgpa": float(profile.cgpa) if profile and profile.cgpa is not None else 0.0,
        "profile_grad": (
            str(profile.graduation_year)
            if profile and profile.graduation_year in range(2023, 2036)
            else "Not specified"
        ),
        "profile_location": (profile.location or "") if profile else "",
        "profile_skills": ", ".join(profile.skills) if profile and profile.skills else "",
        "profile_delivery": (
            profile.delivery_mode
            if profile and profile.delivery_mode in VALID_DELIVERY_MODES
            else "unspecified"
        ),
        "profile_categories": [
            category
            for category in (profile.preferred_categories if profile else [])
            if category in VALID_CATEGORIES
        ],
        "profile_goals": (profile.additional_goals or "") if profile else "",
    }


def _render_profile_form(profile: Optional[StudentProfile]) -> None:
    """Render the profile setup and editing form."""
    graduation_options = ["Not specified"] + [str(year) for year in range(2023, 2036)]

    for key, value in _profile_form_defaults(profile).items():
        st.session_state.setdefault(key, value)
    if st.session_state["profile_grad"] not in graduation_options:
        st.session_state["profile_grad"] = "Not specified"

    with st.form("profile_form"):
        col_left, col_right = st.columns(2)

        with col_left:
            st.selectbox(
                "Education level",
                options=VALID_EDUCATION_LEVELS,
                key="profile_edu",
            )
            st.text_input(
                "Field of study",
                placeholder="e.g. Computer Science, Business, Engineering",
                key="profile_field",
            )
            st.number_input(
                "CGPA on a 5.0 scale (optional)",
                min_value=0.0,
                max_value=5.0,
                step=0.01,
                key="profile_cgpa",
                help="Used only to check minimum CGPA requirements. Leave at 0 to skip.",
            )
            st.selectbox(
                "Graduation year",
                options=graduation_options,
                key="profile_grad",
            )

        with col_right:
            st.text_input(
                "Location",
                placeholder="e.g. Lagos, Abuja, or Remote",
                key="profile_location",
            )
            st.text_input(
                "Skills",
                placeholder="e.g. Python, SQL, Git, Data Analysis",
                key="profile_skills",
                help="Separate skills with commas.",
            )
            st.selectbox(
                "Preferred delivery mode",
                options=list(VALID_DELIVERY_MODES),
                format_func=lambda mode: DELIVERY_MODE_LABELS.get(mode, mode.title()),
                key="profile_delivery",
            )
            st.multiselect(
                "Opportunity interests",
                options=list(VALID_CATEGORIES),
                key="profile_categories",
            )

        st.text_area(
            "Career goals (optional)",
            placeholder="e.g. I am looking for data-focused internships and STEM scholarships.",
            max_chars=400,
            key="profile_goals",
        )

        submitted = st.form_submit_button(
            "Save profile",
            type="primary",
            icon=":material/check:",
        )

    if not submitted:
        return

    cgpa_value = float(st.session_state.get("profile_cgpa") or 0.0)
    graduation_value = st.session_state.get("profile_grad", "Not specified")

    try:
        saved_profile = validate_profile(
            education_level=st.session_state.get("profile_edu", VALID_EDUCATION_LEVELS[0]),
            field_of_study=st.session_state.get("profile_field", ""),
            skills=st.session_state.get("profile_skills", ""),
            location=st.session_state.get("profile_location", ""),
            preferred_categories=st.session_state.get("profile_categories", []),
            delivery_mode=st.session_state.get("profile_delivery", "unspecified"),
            graduation_year=(
                None if graduation_value == "Not specified" else int(graduation_value)
            ),
            cgpa=cgpa_value if cgpa_value > 0.0 else None,
            additional_goals=st.session_state.get("profile_goals", ""),
        )
    except ProfileValidationError as error:
        st.error(str(error), icon=":material/error:")
        return

    st.session_state["student_profile"] = saved_profile
    st.session_state["profile_saved_flash"] = True
    st.session_state["matching_query"] = ""
    st.rerun()


def render_profile_view(opportunities: List[Dict[str, Any]]) -> None:
    """Render profile setup, matching preferences, and personalized matches."""
    st.title("Your profile & matches")
    st.caption(
        "Share a few details about your background to see opportunities that "
        "align with your skills, location, and goals."
    )

    if st.session_state.pop("profile_saved_flash", False):
        st.success("Profile saved. Your matches are updated below.")

    profile: Optional[StudentProfile] = st.session_state.get("student_profile")

    with st.container(border=True):
        summary_col, action_col = st.columns([3, 1], vertical_alignment="center")
        with summary_col:
            if profile:
                skills = ", ".join(profile.skills[:4]) if profile.skills else "not set"
                st.markdown(f"**{profile.education_level}**")
                st.caption(
                    f"{profile.field_of_study or 'Field not set'} · "
                    f"{profile.location or 'Location not set'} · Skills: {skills}"
                )
            else:
                st.markdown("**No profile yet**")
                st.caption(
                    "Complete the form below, or load an example profile to try matching."
                )
        with action_col:
            button_col_1, button_col_2 = st.columns(2)
            with button_col_1:
                st.button(
                    "Use example",
                    on_click=_load_example_profile,
                    width="stretch",
                    help="Fill the form with an example profile",
                )
            with button_col_2:
                if profile:
                    st.button(
                        "Clear",
                        on_click=_clear_profile,
                        width="stretch",
                        help="Remove your saved profile",
                    )

        _render_profile_form(profile)

    st.divider()
    st.subheader("Matches")
    st.caption(
        "Match scores show how closely an opportunity aligns with your profile. "
        "They are guidance, not a prediction of acceptance."
    )

    query_col, clear_col = st.columns([4, 1], vertical_alignment="center")
    with query_col:
        st.text_input(
            "Refine matches",
            key="matching_query",
            placeholder="Refine with a focus, e.g. data internships for undergraduates…",
            label_visibility="collapsed",
            help="Press Enter to apply your search.",
        )
    with clear_col:
        if st.session_state.get("matching_query"):
            st.button(
                "Clear search",
                on_click=_clear_matching_query,
                width="stretch",
            )

    query_text = str(st.session_state.get("matching_query", "")).strip()

    if not profile and not query_text:
        st.info(
            "Set up your profile above to see personalized matches.",
            icon=":material/person:",
        )
        return

    matching_profile = profile or validate_profile(education_level="Undergraduate")

    matches, _ = match_opportunities(
        profile=matching_profile,
        opportunities=opportunities,
        query=query_text or None,
        top_k=6,
    )

    if not matches:
        render_empty_state(
            title="No matching opportunities found",
            description=(
                "Try adding more skills, choosing additional opportunity "
                "interests, or clearing your search."
            ),
        )
        return

    try:
        explanation = _cached_explanation(
            matching_profile,
            tuple(matches),
            query_text,
        )
    except Exception:
        logger.exception("Unable to generate match guidance")
        explanation = None

    explanation_items = {}
    if explanation and explanation.overall_summary:
        st.info(
            escape_markdown(explanation.overall_summary),
            icon=":material/lightbulb:",
        )
        explanation_items = {item.opportunity_id: item for item in explanation.items}

    left_column, right_column = st.columns(2)
    for index, match in enumerate(matches):
        record = match.opportunity_record or {}
        explanation_item = explanation_items.get(match.opportunity_id)
        why_matched = (
            explanation_item.why_matched
            if explanation_item
            else "; ".join(match.matching_factors)
        )

        card_data = {
            "opportunity_id": match.opportunity_id,
            "title": match.title,
            "organization": match.organization,
            "category": match.category,
            "location": match.location,
            "education_level": match.education_level,
            "description": match.description,
            "eligibility": match.eligibility_str,
            "deadline": match.deadline or record.get("deadline"),
            "status": match.application_status,
            "source_url": match.source_url or record.get("source_url", ""),
            "is_sample_data": record.get("is_sample_data", False),
        }

        match_meta = {
            "match_score": match.match_score,
            "eligibility_outcome": match.eligibility.outcome.value,
            "why_matched": why_matched,
        }

        target = left_column if index % 2 == 0 else right_column
        with target:
            render_opportunity_card(card_data, key_prefix="match", match_meta=match_meta)


# -----------------------------------------------------------------------------
# Saved opportunities
# -----------------------------------------------------------------------------
def render_saved_view(opportunities: List[Dict[str, Any]]) -> None:
    """Render the opportunities the user has saved for later."""
    st.title("Saved opportunities")
    st.caption("Review saved listings and apply before their deadlines.")

    saved_ids: Set[str] = st.session_state.get("saved_opportunities", set())
    if not saved_ids:
        render_empty_state(
            title="No saved opportunities yet",
            description=(
                "Select Save on any opportunity to keep it here for later review."
            ),
        )
        return

    saved = [
        opportunity
        for opportunity in opportunities
        if str(opportunity.get("opportunity_id")) in saved_ids
    ]

    if not saved:
        render_empty_state(
            title="Your saved opportunities are no longer available",
            description=(
                "These listings may have been removed by the source. Browse "
                "current opportunities to save new ones."
            ),
        )
        return

    st.caption(f"{len(saved)} saved opportunit{'y' if len(saved) == 1 else 'ies'}")

    left_column, right_column = st.columns(2)
    for index, opportunity in enumerate(saved):
        target = left_column if index % 2 == 0 else right_column
        with target:
            render_opportunity_card(opportunity, key_prefix="saved")


# -----------------------------------------------------------------------------
# About
# -----------------------------------------------------------------------------
def render_about_view() -> None:
    """Render user-facing product information."""
    st.title("About OpportunityLens")
    st.caption(
        "A free, open-source opportunity discovery platform for students and "
        "early-career professionals."
    )

    left_column, right_column = st.columns(2)

    with left_column:
        with st.container(border=True):
            st.markdown("#### What we do")
            st.write(
                "OpportunityLens gathers scholarships, internships, entry-level "
                "jobs, hackathons, fellowships, and training programs from "
                "official sources into one clear, searchable directory, with "
                "eligibility guidance to help you decide where to apply."
            )
        with st.container(border=True):
            st.markdown("#### Trust and data quality")
            st.write(
                "Listings are collected from official primary sources such as "
                "government agencies, recognized foundations, and employer "
                "career pages. Cards link directly to the original application "
                "page whenever a source URL is available, so you can verify "
                "details at the source."
            )

    with right_column:
        with st.container(border=True):
            st.markdown("#### Opportunity categories")
            st.markdown(
                "- **Scholarships:** tuition funding and academic grants\n"
                "- **Internships:** practical student and graduate placements\n"
                "- **Entry-level jobs:** graduate programs and junior roles\n"
                "- **Tech training:** bootcamps and digital-skills programs\n"
                "- **Hackathons:** competitive challenges with mentorship and prizes"
            )
        with st.container(border=True):
            st.markdown("#### Privacy and open source")
            st.markdown(
                "- **Private by default:** your profile and saved listings stay "
                "in your browser session\n"
                "- **Open source:** released under the MIT License\n"
                "- **Free to use:** no account or payment required"
            )


def render_footer() -> None:
    """Render a subtle application footer."""
    st.html(
        '<div class="ol-footer">OpportunityLens · Free and open source under the '
        "MIT License</div>"
    )


# -----------------------------------------------------------------------------
# Application entry point
# -----------------------------------------------------------------------------
def main() -> None:
    """Initialize state, load data, and route to the active view."""
    st.session_state.setdefault("saved_opportunities", set())
    st.session_state.setdefault("student_profile", None)
    st.session_state.setdefault("active_nav", NAV_OPTIONS[0])
    st.session_state.setdefault("matching_query", "")
    st.session_state.setdefault("filter_search_query", "")
    st.session_state.setdefault("filter_category", "All")

    active_nav = render_header()

    demo_mode_active = (
        ingestion_config.demo_mode or st.query_params.get("demo") == "true"
    )
    if demo_mode_active:
        opportunities = get_demo_opportunities()
        data_available = True
    else:
        opportunities, connection_state = load_snowflake_opportunities()
        data_available = connection_state != "Unavailable"

    if demo_mode_active:
        st.info(
            "Demo mode is on. You are viewing fictional sample opportunities; "
            "live listings are hidden.",
            icon=":material/science:",
        )

    if active_nav == "About":
        render_about_view()
    elif not data_available:
        render_service_unavailable()
    elif active_nav == "My Profile":
        render_profile_view(opportunities)
    elif active_nav == "Saved":
        render_saved_view(opportunities)
    else:
        render_discover_view(opportunities)

    render_footer()


if __name__ == "__main__":
    main()
