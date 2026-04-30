"""Findings page — per-lead finding cards with severity badges and evidence."""

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

st.set_page_config(page_title="Findings | SharpQA", layout="wide")
st.title("Findings")

# Get leads that have been analyzed
try:
    leads_resp = httpx.get(f"{API_BASE}/leads", params={"limit": 200}, timeout=10)
    if leads_resp.status_code != 200:
        st.error("Cannot fetch leads")
        st.stop()

    leads = leads_resp.json()
    analyzed_leads = [l for l in leads if l["lead_status"] in ("analyzed", "drafted", "sent")]

    if not analyzed_leads:
        st.info("No analyzed leads yet. Run the pipeline first.")
        st.stop()

    # Select lead
    selected = st.selectbox(
        "Select company",
        [f"{l['company_name']} — Score: {l.get('priority_score', 0):.2f}" for l in analyzed_leads],
    )

    selected_index = [
        f"{l['company_name']} — Score: {l.get('priority_score', 0):.2f}" for l in analyzed_leads
    ].index(selected)
    lead = analyzed_leads[selected_index]

    # Fetch findings
    findings_resp = httpx.get(f"{API_BASE}/leads/{lead['lead_id']}/findings", timeout=10)
    if findings_resp.status_code != 200:
        st.error("Cannot fetch findings")
        st.stop()

    findings = findings_resp.json()

    st.write(f"**{len(findings)} findings** for {lead['company_name']}")

    # Severity color mapping
    severity_colors = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }

    for finding in findings:
        severity = finding.get("severity_level", "low")
        badge = severity_colors.get(severity, "⚪")

        with st.expander(f"{badge} [{severity.upper()}] {finding['finding_title']}", expanded=severity in ("critical", "high")):
            st.write(f"**Category:** {finding.get('finding_category', 'unknown')}")
            st.write(f"**Tool:** {finding.get('tool_source', 'unknown')}")

            if finding.get("page_url"):
                st.write(f"**Page:** {finding['page_url']}")

            if finding.get("finding_description"):
                st.write(f"**Description:** {finding['finding_description']}")

            if finding.get("business_impact"):
                st.info(f"**Business Impact:** {finding['business_impact']}")

            if finding.get("evidence_json"):
                with st.expander("Evidence JSON"):
                    st.json(finding["evidence_json"])

    # Check for screenshots
    desktop_screenshot = Path(settings.screenshots_dir) / f"{lead['lead_id']}_desktop.png"
    mobile_screenshot = Path(settings.screenshots_dir) / f"{lead['lead_id']}_mobile.png"

    if desktop_screenshot.exists() or mobile_screenshot.exists():
        st.divider()
        st.subheader("Screenshots")
        cols = st.columns(2)
        if desktop_screenshot.exists():
            cols[0].image(str(desktop_screenshot), caption="Desktop", use_container_width=True)
        if mobile_screenshot.exists():
            cols[1].image(str(mobile_screenshot), caption="Mobile", use_container_width=True)

except Exception as e:
    st.error(f"Error: {e}")
