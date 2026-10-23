"""Reusable UI components for OpportunityLens.

Native-first, accessible components built on Streamlit primitives:
- Hero headline and search
- Opportunity cards and detail dialogs
- Category and status badges via st.badge
- Saved-opportunity bookmarking
- User-friendly empty, loading, and outage states

All database-sourced strings are Markdown-escaped before rendering so raw
HTML, Markdown directives, and Streamlit shortcodes in untrusted values can
never execute or corrupt layout.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Set

import streamlit as st

from src.utils import escape_markdown, format_display_date, get_safe_url

# Status -> (display label, st.badge color). Unknown statuses render no badge.
_STATUS_BADGES: Dict[str, tuple] = {
    "open": ("Open", "green"),
    "closing soon": ("Closing soon", "orange"),
    "closing_soon": ("Closing soon", "orange"),
    "closed": ("Closed", "gray"),
    "expired": ("Closed", "gray"),
}

# Eligibility outcome -> (display label, st.badge color)
_ELIGIBILITY_BADGES: Dict[str, tuple] = {
    "ELIGIBLE": ("Eligible", "green"),
    "LIKELY_ELIGIBLE": ("Likely eligible", "green"),
    "POSSIBLY_ELIGIBLE": ("Possibly eligible", "orange"),
    "LIKELY_NOT_ELIGIBLE": ("May not qualify", "red"),
    "NOT_ELIGIBLE": ("May not qualify", "red"),
    "INSUFFICIENT_INFORMATION": ("Not enough info", "gray"),
}


def _toggle_saved(opp_id: str) -> None:
    """Add or remove an opportunity from the session-state saved set."""
    saved: Set[str] = st.session_state.get("saved_opportunities", set())
    if opp_id in saved:
        saved.discard(opp_id)
    else:
        saved.add(opp_id)
    st.session_state["saved_opportunities"] = saved


def _status_badge(status_raw: Any) -> Optional[tuple]:
    """Map a raw status value to a (label, color) badge pair, or None if unknown."""
    key = str(status_raw or "").strip().lower()
    return _STATUS_BADGES.get(key)


@st.dialog("Opportunity details", width="medium")
def show_opportunity_details_dialog(opp: Dict[str, Any]) -> None:
    """Display a focused dialog with the full opportunity information.

    Args:
        opp: Opportunity dictionary with title, organization, description, etc.
    """
    title = escape_markdown(opp.get("title"), "Untitled opportunity")
    org = escape_markdown(opp.get("organization"), "Not specified")
    category = str(opp.get("category") or "General")
    location = escape_markdown(opp.get("location"), "Not specified")
    edu_level = escape_markdown(opp.get("education_level"), "Not specified")
    desc = str(opp.get("description") or "").strip()
    eligibility = str(opp.get("eligibility") or "").strip()
    deadline_display = format_display_date(opp.get("deadline"))
    safe_url = get_safe_url(opp.get("source_url"))
    opp_id = str(opp.get("opportunity_id") or "")

    st.markdown(f"### {title}")
    st.markdown(f"**{org}**")

    with st.container(horizontal=True, vertical_alignment="center"):
        st.badge(escape_markdown(category, "General"), color="blue")
        status_badge = _status_badge(opp.get("status"))
        if status_badge:
            st.badge(status_badge[0], color=status_badge[1])
        if opp.get("is_sample_data"):
            st.badge("Sample", color="gray", help="Fictional example data")

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Location**")
        st.write(location)
    with col2:
        st.markdown("**Education level**")
        st.write(edu_level)
    with col3:
        st.markdown("**Application deadline**")
        st.write(deadline_display)

    st.markdown("**Description**")
    if desc:
        st.write(escape_markdown(desc))
    else:
        st.caption("No detailed description was provided by the source.")

    st.markdown("**Eligibility & requirements**")
    if eligibility:
        st.info(escape_markdown(eligibility))
    else:
        st.caption("Review the official application page for specific prerequisites.")

    st.divider()

    action_col1, action_col2 = st.columns([3, 1], vertical_alignment="center")
    with action_col1:
        if safe_url:
            st.link_button(
                "Apply on official website",
                url=safe_url,
                type="primary",
                width="stretch",
                icon=":material/open_in_new:",
                help="Opens the official application page in a new tab",
            )
        else:
            st.button(
                "Application link unavailable",
                disabled=True,
                width="stretch",
            )
    with action_col2:
        saved: Set[str] = st.session_state.get("saved_opportunities", set())
        is_saved = opp_id in saved
        if st.button(
            "Saved" if is_saved else "Save",
            key=f"dlg_save_{opp_id}",
            icon=":material/bookmark:" if is_saved else ":material/bookmark_border:",
            help="Remove from saved" if is_saved else "Save for later",
            width="stretch",
        ):
            _toggle_saved(opp_id)
            st.rerun()


def render_opportunity_card(
    opp: Dict[str, Any],
    key_prefix: str = "card",
    match_meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Render a compact, modern opportunity card.

    Args:
        opp: Opportunity dictionary.
        key_prefix: Unique key prefix for widget isolation across sections.
        match_meta: Optional personalized match score and eligibility metadata.
    """
    title = escape_markdown(opp.get("title"), "Untitled opportunity")
    org = escape_markdown(opp.get("organization"), "Not specified")
    category = str(opp.get("category") or "General")
    location = escape_markdown(opp.get("location"), "Not specified")
    edu_level = escape_markdown(opp.get("education_level"), "Not specified")
    desc = str(opp.get("description") or "").strip()
    deadline_display = format_display_date(opp.get("deadline"))
    safe_url = get_safe_url(opp.get("source_url"))
    opp_id = str(opp.get("opportunity_id") or "")

    preview_desc = desc[:170].rstrip() + "…" if len(desc) > 175 else desc

    with st.container(border=True):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.badge(escape_markdown(category, "General"), color="blue")
            status_badge = _status_badge(opp.get("status"))
            if status_badge:
                st.badge(status_badge[0], color=status_badge[1])
            if opp.get("is_sample_data"):
                st.badge("Sample", color="gray", help="Fictional example data")
            if match_meta:
                score = int(round(float(match_meta.get("match_score", 0))))
                st.badge(
                    f"{score}% match",
                    color="violet",
                    help="How closely this opportunity aligns with your profile. "
                    "It is not a prediction of acceptance.",
                )
                outcome_key = str(match_meta.get("eligibility_outcome") or "")
                outcome = _ELIGIBILITY_BADGES.get(outcome_key)
                if outcome:
                    st.badge(outcome[0], color=outcome[1])

        st.markdown(f"**{title}**")
        st.caption(f"{org} · {location} · {edu_level}")

        if preview_desc:
            st.write(escape_markdown(preview_desc))

        if match_meta and match_meta.get("why_matched"):
            st.caption(f"Why this matches: {escape_markdown(match_meta['why_matched'])}")

        if deadline_display != "N/A":
            st.caption(f"Deadline: {deadline_display}")

        btn_col1, btn_col2, btn_col3 = st.columns([3, 4, 2], vertical_alignment="center")
        with btn_col1:
            if st.button("Details", key=f"{key_prefix}_det_{opp_id}", width="stretch"):
                show_opportunity_details_dialog(opp)
        with btn_col2:
            if safe_url:
                st.link_button(
                    "Apply",
                    url=safe_url,
                    width="stretch",
                    icon=":material/open_in_new:",
                    help="Opens the official application page in a new tab",
                )
            else:
                st.button("No link", disabled=True, width="stretch")
        with btn_col3:
            saved: Set[str] = st.session_state.get("saved_opportunities", set())
            is_saved = opp_id in saved
            if st.button(
                "Saved" if is_saved else "Save",
                key=f"{key_prefix}_save_{opp_id}",
                icon=":material/bookmark:" if is_saved else ":material/bookmark_border:",
                help="Remove from saved" if is_saved else "Save for later review",
                width="stretch",
            ):
                _toggle_saved(opp_id)
                st.rerun()


def render_hero() -> None:
    """Render the discovery-page headline and supporting sentence."""
    st.title("Find opportunities that move you forward.")
    st.caption(
        "Discover relevant scholarships, internships, entry-level jobs, "
        "hackathons, fellowships, and training programs in one place."
    )


def render_empty_state(
    title: str,
    description: str,
    action_label: Optional[str] = None,
    on_action: Optional[Callable[[], None]] = None,
) -> None:
    """Render a friendly empty state with an optional reset action.

    Args:
        title: Short headline for the empty state.
        description: Supporting explanation with a suggested next step.
        action_label: Optional button label.
        on_action: Optional callback invoked by the action button.
    """
    with st.container(border=True):
        st.markdown(f"#### {escape_markdown(title)}")
        st.write(escape_markdown(description))
        if action_label and on_action:
            st.button(action_label, on_click=on_action, type="primary")


def render_service_unavailable() -> None:
    """Render a user-friendly outage message without exposing backend internals."""
    with st.container(border=True):
        st.markdown("#### We're temporarily unable to load opportunities")
        st.write(
            "We're having trouble connecting to our data service. "
            "Please try again in a moment."
        )
        if st.button("Try again", type="primary", icon=":material/refresh:"):
            st.cache_data.clear()
            st.rerun()
