"""Streamlit dashboard — main entrypoint for the SharpQA Sales Agent UI."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Ensure project root is importable
project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

st.set_page_config(
    page_title="SharpQA Sales Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Optional password protection
from config.settings import get_settings

settings = get_settings()

if settings.dashboard_password:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password = st.text_input("Enter dashboard password:", type="password")
        if password == settings.dashboard_password:
            st.session_state.authenticated = True
            st.rerun()
        elif password:
            st.error("Incorrect password")
        st.stop()


# Main dashboard page
st.title("SharpQA Sales Agent")
st.markdown("**Local-first lead sourcing, website analysis, and cold outreach automation.**")

# API base URL
API_BASE = f"http://127.0.0.1:{settings.api_port}"

# Quick stats
import httpx

try:
    response = httpx.get(f"{API_BASE}/stats", timeout=5)
    if response.status_code == 200:
        stats = response.json()
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Leads", stats.get("total_leads", 0))
        col2.metric("Findings/Lead", stats.get("findings_per_lead_avg", 0))
        col3.metric("Drafts Generated", stats.get("drafts_generated", 0))
        col4.metric("Drafts Approved", stats.get("drafts_approved", 0))
        col5.metric("Approval Rate", f"{stats.get('approval_rate', 0)}%")
    else:
        st.warning("API server not responding. Start with: `SharpQA serve`")
except Exception:
    st.warning(
        "Cannot connect to the API server. Make sure it's running on "
        f"`{API_BASE}`. Start with: `python -m sharpqa_agent.main serve`"
    )

st.divider()

# Quick actions
st.subheader("Quick Actions")

col_a, col_b, col_c = st.columns(3)

with col_a:
    if st.button("Run Full Pipeline", type="primary", use_container_width=True):
        try:
            response = httpx.post(
                f"{API_BASE}/runs/start",
                json={"stages": ["source", "enrich", "analyze", "prioritize", "draft"], "limit": 10},
                timeout=10,
            )
            if response.status_code == 200:
                run_id = response.json().get("run_id")
                st.success(f"Pipeline started! Run ID: `{run_id}`")
                st.info("Go to the Runs page to monitor progress.")
            else:
                st.error(f"Failed to start pipeline: {response.text}")
        except Exception as e:
            st.error(f"Error: {e}")

with col_b:
    if st.button("Source New Leads", use_container_width=True):
        try:
            response = httpx.post(
                f"{API_BASE}/runs/start",
                json={"stages": ["source"], "limit": 20},
                timeout=10,
            )
            if response.status_code == 200:
                st.success("Sourcing started!")
        except Exception as e:
            st.error(f"Error: {e}")

with col_c:
    if st.button("Export to Excel", use_container_width=True):
        try:
            response = httpx.post(f"{API_BASE}/exports/excel", json={}, timeout=30)
            if response.status_code == 200:
                path = response.json().get("path")
                st.success(f"Exported to: `{path}`")
        except Exception as e:
            st.error(f"Error: {e}")

st.divider()
st.caption("Navigate using the sidebar pages: Leads, Findings, Drafts, Runs, Settings")
