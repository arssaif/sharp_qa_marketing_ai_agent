"""Tests for the email drafter — LLM response parsing logic."""

from __future__ import annotations

from sharpqa_agent.core.models import Finding, FindingCategory, Lead, SeverityLevel
from sharpqa_agent.drafter.email_drafter import EmailDrafter


def _sample_lead() -> Lead:
    return Lead(
        lead_id="test-id",
        company_name="TestCo",
        website_url="https://testco.io",
        source_platform="yc",
    )


def _sample_findings() -> list[Finding]:
    return [Finding(
        lead_id="test-id",
        finding_category=FindingCategory.PERFORMANCE,
        finding_title="Slow homepage",
        severity_level=SeverityLevel.HIGH,
    )]


class TestLLMResponseParsing:
    """Test the _parse_llm_response method without calling the actual LLM."""

    def setup_method(self) -> None:
        # Create drafter with dummy LLM (won't be called)
        self.drafter = EmailDrafter.__new__(EmailDrafter)

    def test_parse_valid_json_response(self) -> None:
        """Valid JSON response should be parsed correctly."""
        response = '{"subject": "Test Subject", "body": "Hello, this is the email body."}'
        subject, body = self.drafter._parse_llm_response(response, _sample_lead(), _sample_findings())

        assert subject == "Test Subject"
        assert body == "Hello, this is the email body."

    def test_parse_json_with_surrounding_text(self) -> None:
        """JSON embedded in explanation text should be extracted."""
        response = 'Here is the email:\n\n{"subject": "Quick observation", "body": "Hi Jane, I noticed..."}'
        subject, body = self.drafter._parse_llm_response(response, _sample_lead(), _sample_findings())

        assert subject == "Quick observation"
        assert "Jane" in body

    def test_parse_subject_colon_format(self) -> None:
        """'Subject: ...' format should be parsed as fallback."""
        response = "Subject: Performance issue\n\nHi, I found a problem..."
        subject, body = self.drafter._parse_llm_response(response, _sample_lead(), _sample_findings())

        assert subject == "Performance issue"
        assert "problem" in body

    def test_parse_raw_text_fallback(self) -> None:
        """Raw text without structure should use fallback subject."""
        response = "Hi there, I noticed your homepage is slow."
        subject, body = self.drafter._parse_llm_response(response, _sample_lead(), _sample_findings())

        assert subject  # Should generate a fallback
        assert "slow" in body

    def test_parse_empty_response(self) -> None:
        """Empty response should produce a fallback email."""
        subject, body = self.drafter._parse_llm_response("", _sample_lead(), _sample_findings())

        assert subject
        assert body
        assert "TestCo" in body  # Fallback mentions company
