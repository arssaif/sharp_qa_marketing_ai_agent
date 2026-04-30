"""Leads page — filterable table of discovered leads with drill-down."""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import streamlit as st

project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.settings import get_settings

settings = get_settings()
API_BASE = f"http://127.0.0.1:{settings.api_port}"

st.set_page_config(page_title="Leads | SharpQA", layout="wide")
st.title("Leads")

# Filters
col1, col2, col3, col4 = st.columns(4)
with col1:
    status_filter = st.selectbox("Status", ["All", "new", "enriched", "analyzed", "drafted", "sent", "replied", "dead"])
with col2:
    source_filter = st.selectbox("Source", ["All", "yc", "wellfound", "producthunt", "github"])
with col3:
    min_score = st.slider("Min Priority Score", 0.0, 1.0, 0.0, 0.1)
with col4:
    search_query = st.text_input("Search", placeholder="Company name or description...")

# Build query params
params = {"limit": 100}
if status_filter != "All":
    params["status"] = status_filter
if source_filter != "All":
    params["source"] = source_filter
if min_score > 0:
    params["min_score"] = min_score
if search_query:
    params["search"] = search_query

# Fetch leads
try:
    response = httpx.get(f"{API_BASE}/leads", params=params, timeout=10)
    if response.status_code == 200:
        leads = response.json()

        if not leads:
            st.info("No leads found matching the filters.")
        else:
            st.write(f"**{len(leads)} leads found**")

            # Display as a table
            table_data = []
            for lead in leads:
                table_data.append({
                    "Company": lead["company_name"],
                    "Website": lead["website_url"],
                    "Source": lead["source_platform"],
                    "Stage": lead.get("funding_stage", ""),
                    "Score": round(lead.get("priority_score", 0), 2),
                    "Status": lead["lead_status"],
                })

            st.dataframe(
                table_data,
                use_container_width=True,
                column_config={
                    "Website": st.column_config.LinkColumn("Website"),
                    "Score": st.column_config.ProgressColumn("Score", min_value=0, max_value=1),
                },
            )

            # Lead detail view
            st.divider()
            selected_company = st.selectbox(
                "Select lead for details",
                [f"{l['company_name']} ({l['website_url']})" for l in leads],
            )

            if selected_company:
                selected_index = [
                    f"{l['company_name']} ({l['website_url']})" for l in leads
                ].index(selected_company)
                lead = leads[selected_index]
                lead_id = lead["lead_id"]

                col_a, col_b = st.columns(2)

                with col_a:
                    st.subheader(f"Details: {lead['company_name']}")
                    st.write(f"**Website:** {lead['website_url']}")
                    st.write(f"**Source:** {lead['source_platform']}")
                    st.write(f"**Funding:** {lead.get('funding_stage', 'Unknown')}")
                    st.write(f"**Team Size:** {lead.get('team_size_range', 'Unknown')}")
                    st.write(f"**Score:** {lead.get('priority_score', 0):.2f}")
                    st.write(f"**Status:** {lead['lead_status']}")
                    if lead.get("short_description"):
                        st.write(f"**Description:** {lead['short_description']}")

                with col_b:
                    # Contacts
                    contacts_resp = httpx.get(f"{API_BASE}/leads/{lead_id}/contacts", timeout=5)
                    if contacts_resp.status_code == 200:
                        contacts = contacts_resp.json()
                        if contacts:
                            st.subheader("Contacts")
                            for c in contacts:
                                primary_badge = " ⭐" if c.get("is_primary_contact") else ""
                                st.write(f"**{c.get('full_name', 'Unknown')}**{primary_badge}")
                                if c.get("job_title"):
                                    st.write(f"  Title: {c['job_title']}")
                                if c.get("email_address"):
                                    st.write(f"  Email: {c['email_address']} (confidence: {c.get('email_confidence', 0):.0%})")
                                if c.get("linkedin_url"):
                                    st.write(f"  LinkedIn: {c['linkedin_url']}")

                    # Tech stack
                    tech_resp = httpx.get(f"{API_BASE}/leads/{lead_id}/tech-stack", timeout=5)
                    if tech_resp.status_code == 200:
                        tech = tech_resp.json()
                        if tech:
                            st.subheader("Tech Stack")
                            for t in tech:
                                st.write(f"- {t['technology_name']} ({t['category']}) — {t.get('detection_confidence', 0):.0%}")
    else:
        st.error(f"API error: {response.status_code}")
except Exception as e:
    st.error(f"Cannot connect to API: {e}")
