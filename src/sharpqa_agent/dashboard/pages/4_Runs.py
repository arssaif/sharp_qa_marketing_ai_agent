"""Runs page — live log stream and history of pipeline runs."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import streamlit as st

project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.settings import get_settings

settings = get_settings()
API_BASE = f"http://127.0.0.1:{settings.api_port}"

st.set_page_config(page_title="Runs | SharpQA", layout="wide")
st.title("Pipeline Runs")

# Start new run section
st.subheader("Start New Run")
col1, col2 = st.columns(2)
with col1:
    stages = st.multiselect(
        "Stages",
        ["source", "enrich", "analyze", "prioritize", "draft"],
        default=["source", "enrich", "analyze", "prioritize", "draft"],
    )
with col2:
    limit = st.number_input("Limit (leads per stage)", min_value=1, max_value=100, value=10)

if st.button("Start Run", type="primary"):
    try:
        response = httpx.post(
            f"{API_BASE}/runs/start",
            json={"stages": stages, "limit": limit},
            timeout=10,
        )
        if response.status_code == 200:
            run_id = response.json().get("run_id")
            st.session_state["active_run_id"] = run_id
            st.success(f"Run started: `{run_id}`")
        else:
            st.error(f"Failed: {response.text}")
    except Exception as e:
        st.error(f"Error: {e}")

st.divider()

# Active run monitor
if "active_run_id" in st.session_state:
    run_id = st.session_state["active_run_id"]
    st.subheader(f"Active Run: `{run_id[:8]}...`")

    log_placeholder = st.empty()

    try:
        run_resp = httpx.get(f"{API_BASE}/runs/{run_id}", timeout=5)
        if run_resp.status_code == 200:
            run_data = run_resp.json()
            status = run_data.get("run_status", "unknown")

            if status == "running":
                st.info("Run in progress...")
            elif status == "success":
                st.success(f"Run completed! Processed {run_data.get('leads_processed', 0)} leads.")
            elif status == "failed":
                st.error(f"Run failed: {run_data.get('error_message', 'Unknown error')}")
    except Exception:
        pass

st.divider()

# Run history
st.subheader("Run History")

try:
    runs_resp = httpx.get(f"{API_BASE}/runs", params={"limit": 30}, timeout=10)
    if runs_resp.status_code == 200:
        runs = runs_resp.json()
        if runs:
            for run in runs:
                status_emoji = {"running": "🔄", "success": "✅", "failed": "❌"}.get(run["run_status"], "❓")
                with st.expander(
                    f"{status_emoji} {run['stage_name']} — {run.get('started_at', 'Unknown')}",
                ):
                    st.write(f"**Run ID:** `{run['run_id']}`")
                    st.write(f"**Status:** {run['run_status']}")
                    st.write(f"**Leads processed:** {run.get('leads_processed', 0)}")
                    st.write(f"**Started:** {run.get('started_at', 'N/A')}")
                    st.write(f"**Completed:** {run.get('completed_at', 'N/A')}")
                    if run.get("error_message"):
                        st.error(f"Error: {run['error_message']}")
        else:
            st.info("No runs yet.")
except Exception as e:
    st.error(f"Error: {e}")
