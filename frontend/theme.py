"""Minimal theme utilities for custom HTML components.

Streamlit handles light/dark theme switching via .streamlit/config.toml. This
module only styles the small custom hero/label elements that native Streamlit
components do not cover.
"""

from __future__ import annotations

import streamlit as st

# Pastel accent palette used only for custom HTML components.
_ACCENT_COLORS = {
    "sage": "#8ABFA3",
    "mint": "#CDE8DD",
    "lavender": "#D8D3F0",
    "peach": "#F5D6C6",
    "slate": "#263238",
}


def inject_theme_variables() -> None:
    """Inject minimal CSS for custom HTML components only."""
    st.markdown(
        f"""
        <style>
        :root {{
            --pv-accent-sage: {_ACCENT_COLORS["sage"]};
            --pv-accent-mint: {_ACCENT_COLORS["mint"]};
            --pv-accent-lavender: {_ACCENT_COLORS["lavender"]};
            --pv-accent-peach: {_ACCENT_COLORS["peach"]};
            --pv-accent-slate: {_ACCENT_COLORS["slate"]};
        }}

        .pv-hero {{
            padding: 3.5rem 2rem;
            border: 1px solid var(--border-color);
            border-radius: 1.5rem;
            background:
                radial-gradient(circle at top left, color-mix(in srgb, var(--primary-color) 24%, transparent), transparent 36%),
                radial-gradient(circle at bottom right, color-mix(in srgb, var(--pv-accent-lavender) 34%, transparent), transparent 34%),
                linear-gradient(135deg, var(--secondary-background-color), var(--background-color));
            color: var(--text-color);
            margin-bottom: 1.5rem;
        }}

        .pv-eyebrow {{
            color: var(--pv-accent-sage);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.12em;
            margin-bottom: 0.75rem;
            text-transform: uppercase;
        }}

        .pv-hero-title {{
            font-size: clamp(2.25rem, 6vw, 4.25rem);
            font-weight: 750;
            letter-spacing: -0.05em;
            line-height: 0.98;
            margin: 0;
        }}

        .pv-hero-subtitle {{
            font-size: 1.1rem;
            line-height: 1.7;
            margin: 1rem 0 0;
            max-width: 44rem;
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )
