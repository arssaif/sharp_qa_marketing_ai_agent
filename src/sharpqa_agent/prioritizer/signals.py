"""Scoring signals — individual signal extractors for lead prioritization."""

from __future__ import annotations

from sharpqa_agent.core.models import Contact, Finding, Lead, SeverityLevel, TechStack

# SaaS-indicating technologies
SAAS_INDICATORS = {
    "React", "Vue.js", "Angular", "Next.js", "Nuxt.js", "Svelte",
    "Stripe", "Intercom", "Mixpanel", "Segment", "Sentry",
    "Vercel", "Netlify", "AWS",
}


def funding_stage_signal(lead: Lead, weights: dict) -> float:
    """Score based on the lead's funding stage.

    Args:
        lead: The lead to score.
        weights: Funding stage weight mapping.

    Returns:
        Score between 0.0 and 1.0.
    """
    if not lead.funding_stage:
        return weights.get("unknown", 0.3)
    return weights.get(lead.funding_stage, 0.3)


def team_size_signal(lead: Lead, weights: dict) -> float:
    """Score based on the lead's team size range.

    Args:
        lead: The lead to score.
        weights: Team size weight mapping.

    Returns:
        Score between 0.0 and 1.0.
    """
    if not lead.team_size_range:
        return 0.5  # neutral if unknown
    return weights.get(lead.team_size_range, 0.5)


def max_finding_severity_signal(findings: list[Finding], weights: dict) -> float:
    """Score based on the highest severity finding.

    Args:
        findings: All findings for the lead.
        weights: Severity weight mapping.

    Returns:
        Score between 0.0 and 1.0.
    """
    if not findings:
        return weights.get("none", 0.0)

    severity_order = {
        SeverityLevel.CRITICAL: 4,
        SeverityLevel.HIGH: 3,
        SeverityLevel.MEDIUM: 2,
        SeverityLevel.LOW: 1,
    }

    max_severity = max(findings, key=lambda f: severity_order.get(f.severity_level, 0))
    severity_key = max_severity.severity_level.value if isinstance(max_severity.severity_level, SeverityLevel) else str(max_severity.severity_level)
    return weights.get(severity_key, 0.0)


def has_primary_contact_email_signal(contacts: list[Contact]) -> bool:
    """Check if the lead has a primary contact with an email.

    Args:
        contacts: Contacts associated with the lead.

    Returns:
        True if a primary contact with email exists.
    """
    return any(c.is_primary_contact and c.email_address for c in contacts)


def tech_stack_indicates_saas_signal(tech_stack: list[TechStack]) -> bool:
    """Check if the detected tech stack indicates a SaaS product.

    Args:
        tech_stack: Detected technologies.

    Returns:
        True if SaaS-indicating technologies are present.
    """
    detected_names = {t.technology_name for t in tech_stack if t.technology_name}
    return bool(detected_names & SAAS_INDICATORS)
