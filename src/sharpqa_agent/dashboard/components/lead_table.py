"""Lead table component — reusable Streamlit table for displaying leads."""

from __future__ import annotations

import streamlit as st


def render_lead_table(leads: list[dict]) -> None:
    """Render a formatted lead table in Streamlit.

    Args:
        leads: List of lead dictionaries from the API.
    """
    if not leads:
        st.info("No leads to display.")
        return

    table_data = [
        {
            "Company": lead.get("company_name", ""),
            "Website": lead.get("website_url", ""),
            "Source": lead.get("source_platform", ""),
            "Score": round(lead.get("priority_score", 0), 2),
            "Status": lead.get("lead_status", ""),
        }
        for lead in leads
    ]

    st.dataframe(
        table_data,
        use_container_width=True,
        column_config={
            "Website": st.column_config.LinkColumn("Website"),
            "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=1),
        },
    )
