"""Drafts page — the main workspace for reviewing and editing email drafts."""

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

st.set_page_config(page_title="Drafts | SharpQA", layout="wide")
st.title("Email Drafts")

# Filter by status
status_filter = st.selectbox("Filter by status", ["pending_review", "approved", "rejected", "All"])
query_status = status_filter if status_filter != "All" else None

try:
    params = {"limit": 100}
    if query_status:
        params["status"] = query_status

    drafts_resp = httpx.get(f"{API_BASE}/drafts", params=params, timeout=10)
    if drafts_resp.status_code != 200:
        st.error("Cannot fetch drafts")
        st.stop()

    drafts = drafts_resp.json()

    if not drafts:
        st.info("No drafts found. Run the pipeline to generate drafts.")
        st.stop()

    st.write(f"**{len(drafts)} drafts**")

    for draft in drafts:
        lead_id = draft["lead_id"]

        # Get lead context
        lead_resp = httpx.get(f"{API_BASE}/leads/{lead_id}", timeout=5)
        lead_data = lead_resp.json() if lead_resp.status_code == 200 else {}

        with st.expander(
            f"{'✅' if draft['draft_status'] == 'approved' else '⏳' if draft['draft_status'] == 'pending_review' else '❌'} "
            f"{lead_data.get('company_name', 'Unknown')} — {draft['subject_line'][:60]}",
            expanded=draft["draft_status"] == "pending_review",
        ):
            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.subheader("Context")
                st.write(f"**Company:** {lead_data.get('company_name', 'Unknown')}")
                st.write(f"**Website:** {lead_data.get('website_url', '')}")
                st.write(f"**Score:** {lead_data.get('priority_score', 0):.2f}")
                st.write(f"**Tone:** {draft.get('tone_variant', 'direct')}")

                # Show findings context
                if lead_id:
                    findings_resp = httpx.get(f"{API_BASE}/leads/{lead_id}/findings", timeout=5)
                    if findings_resp.status_code == 200:
                        findings = findings_resp.json()
                        if findings:
                            st.write("**Key Findings:**")
                            for f in findings[:3]:
                                severity = f.get("severity_level", "low")
                                st.write(f"- [{severity}] {f['finding_title']}")

            with col_right:
                st.subheader("Email Draft")
                st.text_input("Subject", draft["subject_line"], key=f"subject_{draft['draft_id']}", disabled=True)

                # Editable body
                edited_body = st.text_area(
                    "Body",
                    draft.get("human_edited_body") or draft["email_body"],
                    height=250,
                    key=f"body_{draft['draft_id']}",
                )

                notes = st.text_input(
                    "Operator Notes",
                    draft.get("operator_notes", ""),
                    key=f"notes_{draft['draft_id']}",
                )

                # Action buttons
                btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

                with btn_col1:
                    if st.button("Approve", key=f"approve_{draft['draft_id']}", type="primary"):
                        resp = httpx.patch(
                            f"{API_BASE}/drafts/{draft['draft_id']}",
                            json={
                                "status": "approved",
                                "human_edited_body": edited_body,
                                "operator_notes": notes,
                            },
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            st.success("Approved!")
                            st.rerun()

                with btn_col2:
                    if st.button("Reject", key=f"reject_{draft['draft_id']}"):
                        resp = httpx.patch(
                            f"{API_BASE}/drafts/{draft['draft_id']}",
                            json={"status": "rejected", "operator_notes": notes},
                            timeout=5,
                        )
                        if resp.status_code == 200:
                            st.warning("Rejected")
                            st.rerun()

                with btn_col3:
                    if st.button("Copy to Clipboard", key=f"copy_{draft['draft_id']}"):
                        body_to_copy = edited_body or draft["email_body"]
                        st.code(f"Subject: {draft['subject_line']}\n\n{body_to_copy}", language=None)
                        st.info("Copy the text above and paste into your email client.")

except Exception as e:
    st.error(f"Error: {e}")
