"""Metrics panel component — displays aggregate stats on the dashboard home."""

from __future__ import annotations

import streamlit as st


def render_metrics(stats: dict) -> None:
    """Render the metrics panel with key KPIs.

    Args:
        stats: Dictionary with total_leads, findings_per_lead_avg,
               drafts_generated, drafts_approved, approval_rate.
    """
    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Total Leads", stats.get("total_leads", 0))
    col2.metric("Findings/Lead", stats.get("findings_per_lead_avg", 0))
    col3.metric("Drafts Generated", stats.get("drafts_generated", 0))
    col4.metric("Drafts Approved", stats.get("drafts_approved", 0))
    col5.metric("Approval Rate", f"{stats.get('approval_rate', 0)}%")
