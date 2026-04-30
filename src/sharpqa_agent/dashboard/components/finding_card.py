"""Finding card component — renders a finding with severity badge and evidence."""

from __future__ import annotations

import streamlit as st

SEVERITY_COLORS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🟢",
}


def render_finding_card(finding: dict, expanded: bool = False) -> None:
    """Render a finding as an expandable card.

    Args:
        finding: Finding dictionary from the API.
        expanded: Whether the card starts expanded.
    """
    severity = finding.get("severity_level", "low")
    badge = SEVERITY_COLORS.get(severity, "⚪")
    title = finding.get("finding_title", "Unknown")

    with st.expander(f"{badge} [{severity.upper()}] {title}", expanded=expanded):
        st.write(f"**Category:** {finding.get('finding_category', 'unknown')}")
        st.write(f"**Tool:** {finding.get('tool_source', 'unknown')}")

        if finding.get("page_url"):
            st.write(f"**Page:** {finding['page_url']}")

        if finding.get("finding_description"):
            st.write(finding["finding_description"])

        if finding.get("business_impact"):
            st.info(finding["business_impact"])

        if finding.get("evidence_json"):
            with st.expander("Raw Evidence"):
                st.json(finding["evidence_json"])
