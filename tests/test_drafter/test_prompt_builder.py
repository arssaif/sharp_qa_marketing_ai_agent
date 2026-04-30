"""Tests for the prompt builder."""

from __future__ import annotations

from sharpqa_agent.core.models import (
    Contact,
    Finding,
    FindingCategory,
    Lead,
    SeverityLevel,
    TechStack,
    ToneVariant,
)
from sharpqa_agent.drafter.prompt_builder import PromptBuilder


def _sample_lead() -> Lead:
    return Lead(
        lead_id="test-id",
        company_name="TestCo",
        website_url="https://testco.io",
        source_platform="yc",
        funding_stage="seed",
        short_description="AI-powered testing platform",
    )


def _sample_findings() -> list[Finding]:
    return [
        Finding(
            lead_id="test-id",
            finding_category=FindingCategory.PERFORMANCE,
            finding_title="Low Lighthouse performance score: 35/100",
            severity_level=SeverityLevel.HIGH,
            business_impact="Poor performance costs conversions",
        ),
        Finding(
            lead_id="test-id",
            finding_category=FindingCategory.ACCESSIBILITY,
            finding_title="Missing alt text on 5 images",
            severity_level=SeverityLevel.MEDIUM,
        ),
    ]


def _sample_contact() -> Contact:
    return Contact(
        lead_id="test-id",
        full_name="Jane Smith",
        job_title="CTO",
        email_address="jane@testco.io",
        is_primary_contact=True,
    )


def test_build_prompt_includes_company_context() -> None:
    """Prompt should contain the lead's company name and details."""
    builder = PromptBuilder(operator_name="Arslan", operator_company="SharpQA")
    system, user = builder.build_prompt(
        lead=_sample_lead(),
        findings=_sample_findings(),
        contact=_sample_contact(),
        tech_stack=[],
        similar_templates=[],
        tone=ToneVariant.DIRECT,
    )

    assert "TestCo" in user
    assert "testco.io" in user
    assert "seed" in user.lower()


def test_build_prompt_includes_finding() -> None:
    """Prompt should contain the top finding."""
    builder = PromptBuilder()
    _, user = builder.build_prompt(
        lead=_sample_lead(),
        findings=_sample_findings(),
        contact=_sample_contact(),
        tech_stack=[],
        similar_templates=[],
    )

    assert "performance" in user.lower()
    assert "35/100" in user


def test_build_prompt_includes_rag_examples() -> None:
    """Prompt should include RAG-retrieved templates."""
    builder = PromptBuilder()
    _, user = builder.build_prompt(
        lead=_sample_lead(),
        findings=_sample_findings(),
        contact=None,
        tech_stack=[],
        similar_templates=["Example email template about performance"],
    )

    assert "Example email template about performance" in user
    assert "PAST EXAMPLES THAT WORKED" in user


def test_build_prompt_handles_no_contact() -> None:
    """Prompt should work without a specific contact."""
    builder = PromptBuilder()
    _, user = builder.build_prompt(
        lead=_sample_lead(),
        findings=_sample_findings(),
        contact=None,
        tech_stack=[],
        similar_templates=[],
    )

    assert "there" in user.lower()  # fallback salutation


def test_build_prompt_includes_tech_stack() -> None:
    """Prompt should include tech stack when provided."""
    builder = PromptBuilder()
    _, user = builder.build_prompt(
        lead=_sample_lead(),
        findings=_sample_findings(),
        contact=None,
        tech_stack=[
            TechStack(lead_id="test-id", category="frontend", technology_name="React"),
            TechStack(lead_id="test-id", category="hosting", technology_name="Vercel"),
        ],
        similar_templates=[],
    )

    assert "React" in user
    assert "Vercel" in user


def test_system_prompt_contains_rules() -> None:
    """System prompt should contain email generation rules."""
    builder = PromptBuilder(operator_name="Arslan", operator_company="SharpQA")
    system, _ = builder.build_prompt(
        lead=_sample_lead(),
        findings=_sample_findings(),
        contact=None,
        tech_stack=[],
        similar_templates=[],
    )

    assert "120 words" in system
    assert "Arslan" in system
    assert "SharpQA" in system
    assert "JSON" in system
