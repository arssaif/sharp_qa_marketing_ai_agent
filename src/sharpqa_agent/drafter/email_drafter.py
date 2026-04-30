"""Email drafter — main draft generation loop using LLM + RAG."""

from __future__ import annotations

import asyncio
import json
import re

from sharpqa_agent.core.exceptions import DrafterError
from sharpqa_agent.core.llm_client import OllamaClient
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import (
    Contact,
    EmailDraft,
    Finding,
    Lead,
    TechStack,
    ToneVariant,
)
from sharpqa_agent.drafter.prompt_builder import PromptBuilder
from sharpqa_agent.drafter.rag_retriever import RagRetriever
from sharpqa_agent.drafter.subject_line_generator import generate_fallback_subject

logger = get_logger(__name__)


class EmailDrafter:
    """Generate personalized cold outreach emails using LLM with RAG context.

    Retrieves similar templates, builds a prompt with lead context,
    and generates email drafts via the local Ollama LLM.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        rag_retriever: RagRetriever,
        operator_name: str = "Arslan",
        operator_company: str = "SharpQA",
    ) -> None:
        self.llm = llm_client
        self.rag = rag_retriever
        self.prompt_builder = PromptBuilder(operator_name, operator_company)

    async def generate_draft(
        self,
        lead: Lead,
        findings: list[Finding],
        contact: Contact | None,
        tech_stack: list[TechStack],
        tone: ToneVariant = ToneVariant.DIRECT,
    ) -> EmailDraft:
        """Generate a single email draft for a lead.

        Args:
            lead: Target company lead.
            findings: Findings sorted by severity.
            contact: Primary contact, if available.
            tech_stack: Detected technologies.
            tone: Desired email tone.

        Returns:
            An EmailDraft model with generated subject and body.

        Raises:
            DrafterError: If the LLM fails to generate a valid draft.
        """
        # Retrieve similar templates
        finding_category = findings[0].finding_category.value if findings else "general"
        industry = lead.short_description or ""
        funding_stage = lead.funding_stage or ""

        similar_templates = self.rag.retrieve_similar_templates(
            finding_category=finding_category,
            industry=industry,
            funding_stage=funding_stage,
        )

        # Build prompt
        system_prompt, user_prompt = self.prompt_builder.build_prompt(
            lead=lead,
            findings=findings,
            contact=contact,
            tech_stack=tech_stack,
            similar_templates=similar_templates,
            tone=tone,
        )

        # Generate via LLM
        try:
            raw_response = await self.llm.generate(
                prompt=user_prompt,
                system=system_prompt,
                temperature=0.7,
            )
        except Exception as error:
            raise DrafterError(f"LLM generation failed for {lead.company_name}: {error}") from error

        # Parse JSON response
        subject, body = self._parse_llm_response(raw_response, lead, findings)

        # Create draft
        finding_ids = [f.finding_id for f in findings[:3]]
        draft = EmailDraft(
            lead_id=lead.lead_id,
            contact_id=contact.contact_id if contact else None,
            subject_line=subject,
            email_body=body,
            tone_variant=tone,
            findings_referenced=finding_ids,
            generation_model=self.llm.model,
        )

        logger.info("draft_generated", lead_id=lead.lead_id, tone=tone.value, subject=subject[:50])
        return draft

    async def generate_all_tones(
        self,
        lead: Lead,
        findings: list[Finding],
        contact: Contact | None,
        tech_stack: list[TechStack],
    ) -> list[EmailDraft]:
        """Generate drafts in all three tone variants in parallel.

        Args:
            lead: Target lead.
            findings: Findings sorted by severity.
            contact: Primary contact.
            tech_stack: Detected tech stack.

        Returns:
            List of EmailDraft models, one per tone variant.
        """
        tones = [ToneVariant.DIRECT, ToneVariant.CONSULTATIVE, ToneVariant.FRIENDLY]

        tasks = [
            self.generate_draft(lead, findings, contact, tech_stack, tone)
            for tone in tones
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        drafts = []
        for result in results:
            if isinstance(result, EmailDraft):
                drafts.append(result)
            elif isinstance(result, Exception):
                logger.warning("draft_generation_failed", error=str(result))

        return drafts

    def _parse_llm_response(
        self, raw_response: str, lead: Lead, findings: list[Finding]
    ) -> tuple[str, str]:
        """Parse the LLM response to extract subject and body.

        Args:
            raw_response: Raw text from the LLM.
            lead: The target lead (for fallback subject).
            findings: Findings (for fallback subject).

        Returns:
            Tuple of (subject_line, email_body).
        """
        # Try to extract JSON
        try:
            # Find JSON in the response
            json_match = re.search(r'\{[^{}]*"subject"[^{}]*"body"[^{}]*\}', raw_response, re.DOTALL)
            if not json_match:
                json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)

            if json_match:
                data = json.loads(json_match.group())
                subject = data.get("subject", "")
                body = data.get("body", "")
                if subject and body:
                    return subject.strip(), body.strip()
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: try to split on "Subject:" pattern
        subject_match = re.search(r'Subject:\s*(.+?)(?:\n|$)', raw_response)
        if subject_match:
            subject = subject_match.group(1).strip()
            body = raw_response[subject_match.end():].strip()
            if body:
                return subject, body

        # Last resort: use the raw response as body with a generated subject
        top_finding = findings[0] if findings else None
        fallback_subject = generate_fallback_subject(lead, top_finding)
        body = raw_response.strip()

        # Clean up any leftover JSON artifacts
        body = re.sub(r'^\s*\{?\s*"?subject"?\s*:.*?\n', '', body)
        body = re.sub(r'^\s*"?body"?\s*:\s*"?', '', body)
        body = body.rstrip('"}').strip()

        if not body:
            body = f"Hi,\n\nI noticed an issue with {lead.company_name}'s website that might be worth a look.\n\nWould a quick 20-minute walkthrough be useful?\n\nBest,\nArslan at SharpQA"

        return fallback_subject, body
