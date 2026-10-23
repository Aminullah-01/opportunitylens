"""OpportunityLens UI/UX styles and design system.

A minimal, focused stylesheet complementing the Streamlit theme configured in
.streamlit/config.toml. Contains only the layout rules the theme system cannot
express: content max-width, header polish, brand block, and footer styling.

Colors follow the product identity: deep navy text (#0f172a), refined blue
accents (#2563eb), white surfaces, and light slate borders (#e2e8f0).
"""

from __future__ import annotations

import streamlit as st

SAAS_THEME_CSS = """
<style>
.block-container {
    max-width: 1140px;
    /* Clear Streamlit's fixed 60px header so the brand and primary
       navigation are never hidden behind it. */
    padding-top: 5rem;
    padding-bottom: 2rem;
}

header[data-testid="stHeader"] {
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(6px);
}

.ol-brand {
    display: flex;
    align-items: center;
    gap: 0.55rem;
    padding: 0.25rem 0;
}

.ol-brand-mark {
    font-size: 1.5rem;
    line-height: 1;
}

.ol-brand-name {
    font-size: 1.3rem;
    font-weight: 800;
    color: #0f172a;
    letter-spacing: -0.02em;
    line-height: 1.2;
}

.ol-footer {
    text-align: center;
    color: #64748b;
    font-size: 0.82rem;
    padding: 1rem 0 0.5rem;
}

@media (max-width: 640px) {
    .block-container {
        padding-top: 4.5rem;
    }
    .ol-brand-name {
        font-size: 1.15rem;
    }
}
</style>
"""

UI_CSS = SAAS_THEME_CSS

__all__ = ["SAAS_THEME_CSS", "UI_CSS", "inject_ui_styles"]


def inject_ui_styles() -> None:
    """Inject the minimal design-system CSS into the Streamlit app."""
    st.html(SAAS_THEME_CSS)
