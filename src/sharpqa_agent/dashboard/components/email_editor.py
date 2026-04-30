"""Email editor component — editable draft with approve/reject actions."""

from __future__ import annotations

import httpx
import streamlit as st


def render_email_editor(draft: dict, api_base: str) -> None:
    """Render an email draft editor with action buttons.

    Args:
        draft: Draft dictionary from the API.
        api_base: Base URL of the FastAPI server.
    """
    draft_id = draft["draft_id"]

    st.text_input("Subject", draft["subject_line"], key=f"subj_{draft_id}", disabled=True)

    edited_body = st.text_area(
        "Email Body",
        draft.get("human_edited_body") or draft["email_body"],
        height=200,
        key=f"body_{draft_id}",
    )

    notes = st.text_input("Notes", draft.get("operator_notes", ""), key=f"notes_{draft_id}")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Approve", key=f"approve_{draft_id}", type="primary"):
            resp = httpx.patch(
                f"{api_base}/drafts/{draft_id}",
                json={"status": "approved", "human_edited_body": edited_body, "operator_notes": notes},
                timeout=5,
            )
            if resp.status_code == 200:
                st.success("Approved!")
                st.rerun()

    with col2:
        if st.button("Reject", key=f"reject_{draft_id}"):
            resp = httpx.patch(
                f"{api_base}/drafts/{draft_id}",
                json={"status": "rejected", "operator_notes": notes},
                timeout=5,
            )
            if resp.status_code == 200:
                st.warning("Rejected")
                st.rerun()

    with col3:
        if st.button("Copy", key=f"copy_{draft_id}"):
            st.code(f"Subject: {draft['subject_line']}\n\n{edited_body}", language=None)
