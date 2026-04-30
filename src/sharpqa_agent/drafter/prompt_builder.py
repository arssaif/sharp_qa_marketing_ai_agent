"""Prompt builder — assembles LLM prompts with RAG context for email generation."""

from __future__ import annotations

from sharpqa_agent.core.models import Contact, Finding, Lead, TechStack, ToneVariant

SYSTEM_PROMPT = """You are drafting a cold outreach email from a QA services company to a startup.

RULES:
- Max 120 words.
- Reference exactly one specific finding — the highest severity one.
- Soft CTA: offer a free 20-min audit call, not a services pitch.
- No flattery, no "I hope this finds you well."
- Mention finding as observation, not criticism.
- End with the operator's name and company.
- Output valid JSON: {"subject": "...", "body": "..."}
- Subject line should be under 60 characters, specific, not generic.
"""

TONE_INSTRUCTIONS = {
    ToneVariant.DIRECT: "Tone: Direct and to-the-point. Lead with the finding, state impact, make the ask.",
    ToneVariant.CONSULTATIVE: "Tone: Consultative and expert. Frame as a fellow professional sharing observations. Use 'we noticed' language.",
    ToneVariant.FRIENDLY: "Tone: Warm and casual. Congrats on their progress, mention finding casually, friendly CTA.",
}


class PromptBuilder:
    """Construct LLM prompts by combining system instructions, RAG examples, and lead context."""

    def __init__(self, operator_name: str = "Ali", operator_company: str = "SharpQA") -> None:
        self.operator_name = operator_name
        self.operator_company = operator_company

    def build_prompt(
        self,
        lead: Lead,
        findings: list[Finding],
        contact: Contact | None,
        tech_stack: list[TechStack],
        similar_templates: list[str],
        tone: ToneVariant = ToneVariant.DIRECT,
    ) -> tuple[str, str]:
        """Build the system and user prompts for email generation.

        Args:
            lead: Target company lead.
            findings: Findings for the lead (sorted by severity).
            contact: Primary contact, if available.
            tech_stack: Detected technologies.
            similar_templates: RAG-retrieved example templates.
            tone: Desired email tone variant.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        # System prompt with tone adjustment
        system = SYSTEM_PROMPT
        tone_instruction = TONE_INSTRUCTIONS.get(tone, TONE_INSTRUCTIONS[ToneVariant.DIRECT])
        system += f"\n{tone_instruction}\n"
        system += f"\nOperator name: {self.operator_name}\nOperator company: {self.operator_company}\n"

        # User prompt sections
        sections: list[str] = []

        # RAG examples
        if similar_templates:
            sections.append("PAST EXAMPLES THAT WORKED:")
            for i, template in enumerate(similar_templates, 1):
                sections.append(f"--- Example {i} ---")
                sections.append(template.strip())
            sections.append("")

        # Target company context
        sections.append("TARGET COMPANY:")
        sections.append(f"Name: {lead.company_name}")
        sections.append(f"Website: {lead.website_url}")
        if lead.funding_stage:
            sections.append(f"Stage: {lead.funding_stage}")
        if lead.short_description:
            sections.append(f"What they do: {lead.short_description}")
        if tech_stack:
            tech_names = ", ".join(t.technology_name for t in tech_stack[:5] if t.technology_name)
            if tech_names:
                sections.append(f"Tech stack: {tech_names}")
        sections.append("")

        # Contact info
        if contact:
            contact_name = contact.full_name or "there"
            sections.append(f"RECIPIENT: {contact_name}")
            if contact.job_title:
                sections.append(f"Title: {contact.job_title}")
            sections.append("")
        else:
            sections.append("RECIPIENT: there (no specific name found)")
            sections.append("")

        # Top finding
        if findings:
            top_finding = findings[0]
            sections.append("TOP FINDING:")
            sections.append(f"Category: {top_finding.finding_category.value if hasattr(top_finding.finding_category, 'value') else top_finding.finding_category}")
            sections.append(f"Title: {top_finding.finding_title}")
            if top_finding.business_impact:
                sections.append(f"Business impact: {top_finding.business_impact}")
            sections.append("")

            # Additional findings for context
            if len(findings) > 1:
                sections.append(f"ADDITIONAL FINDINGS ({len(findings) - 1} more):")
                for f in findings[1:3]:
                    sections.append(f"- [{f.severity_level.value if hasattr(f.severity_level, 'value') else f.severity_level}] {f.finding_title}")
                sections.append("")

        sections.append('Generate JSON: {"subject": "...", "body": "..."}')

        user_prompt = "\n".join(sections)
        return system, user_prompt
