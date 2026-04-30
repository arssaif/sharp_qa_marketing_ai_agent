"""Settings page — configure sources, scoring weights, and email templates."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

project_root = str(Path(__file__).resolve().parent.parent.parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from config.settings import get_settings

settings = get_settings()

st.set_page_config(page_title="Settings | SharpQA", layout="wide")
st.title("Settings")

# --- Sources Configuration ---
st.subheader("Lead Sources")

sources_path = Path("config/sources.yaml")
if sources_path.exists():
    sources_config = yaml.safe_load(sources_path.read_text(encoding="utf-8"))
    sources = sources_config.get("sources", {})

    for source_name, source_config in sources.items():
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            enabled = st.checkbox(
                f"Enable {source_name.upper()}",
                value=source_config.get("enabled", False),
                key=f"source_{source_name}",
            )
        with col2:
            daily_limit = st.number_input(
                f"Daily limit ({source_name})",
                value=source_config.get("daily_limit", 50),
                min_value=1,
                max_value=200,
                key=f"limit_{source_name}",
            )
        with col3:
            st.write("")  # Spacer

        sources[source_name]["enabled"] = enabled
        sources[source_name]["daily_limit"] = daily_limit

    if st.button("Save Source Settings"):
        sources_config["sources"] = sources
        sources_path.write_text(yaml.dump(sources_config, default_flow_style=False), encoding="utf-8")
        st.success("Sources configuration saved!")

st.divider()

# --- Scoring Weights ---
st.subheader("Scoring Weights")

weights_path = Path("config/scoring_weights.yaml")
if weights_path.exists():
    weights_text = weights_path.read_text(encoding="utf-8")
    edited_weights = st.text_area(
        "Edit scoring_weights.yaml",
        weights_text,
        height=300,
    )

    if st.button("Save Scoring Weights"):
        try:
            # Validate YAML
            yaml.safe_load(edited_weights)
            weights_path.write_text(edited_weights, encoding="utf-8")
            st.success("Scoring weights saved!")
        except yaml.YAMLError as e:
            st.error(f"Invalid YAML: {e}")

st.divider()

# --- Email Templates ---
st.subheader("Email Templates")

templates_dir = Path("config/email_templates")
if templates_dir.exists():
    templates = sorted(templates_dir.glob("*.md"))
    st.write(f"**{len(templates)} templates loaded**")

    for template_file in templates:
        with st.expander(template_file.name):
            content = template_file.read_text(encoding="utf-8")
            st.text_area(
                f"Edit {template_file.name}",
                content,
                height=200,
                key=f"template_{template_file.stem}",
            )

    # Add new template
    st.divider()
    st.write("**Add New Template**")
    new_template_name = st.text_input("Template filename (e.g., template_009.md)")
    new_template_content = st.text_area("Template content", height=200, key="new_template")

    if st.button("Add Template") and new_template_name and new_template_content:
        new_path = templates_dir / new_template_name
        if new_path.exists():
            st.error("Template with this name already exists.")
        else:
            new_path.write_text(new_template_content, encoding="utf-8")
            st.success(f"Template `{new_template_name}` added!")
            st.info("The template will be automatically embedded in the vector store on the next draft run.")
            st.rerun()

st.divider()

# --- Current Settings Display ---
st.subheader("Current Configuration")
st.json({
    "sqlite_db_path": settings.sqlite_db_path,
    "ollama_model": settings.ollama_model_name,
    "embedding_model": settings.embedding_model_name,
    "operator_name": settings.operator_name,
    "operator_company": settings.operator_company,
    "api_port": settings.api_port,
    "dashboard_port": settings.dashboard_port,
    "max_concurrent_analyzes": settings.max_concurrent_analyzes,
    "min_priority_for_drafting": settings.min_priority_score_for_drafting,
})
