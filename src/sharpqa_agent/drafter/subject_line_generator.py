"""Subject line generator — creates compelling email subject lines from lead context."""

from __future__ import annotations

from sharpqa_agent.core.models import Finding, FindingCategory, Lead


def generate_fallback_subject(lead: Lead, finding: Finding | None) -> str:
    """Generate a fallback subject line if the LLM output is malformed.

    Args:
        lead: The target lead.
        finding: The top finding, if any.

    Returns:
        A subject line string under 60 characters.
    """
    company = lead.company_name

    if not finding:
        return f"Quick observation about {company}'s website"

    category_subjects = {
        FindingCategory.PERFORMANCE: f"Performance issue on {company}'s site",
        FindingCategory.ACCESSIBILITY: f"Accessibility gap on {company}",
        FindingCategory.CONSOLE_ERROR: f"JS errors on {company}'s site",
        FindingCategory.BROKEN_RESOURCE: f"Broken resources on {company}",
        FindingCategory.SECURITY_HEADER: f"Security headers on {company}",
        FindingCategory.SEO: f"SEO quick win for {company}",
        FindingCategory.MOBILE: f"Mobile issue on {company}'s site",
        FindingCategory.BEST_PRACTICES: f"Quick observation about {company}",
    }

    subject = category_subjects.get(finding.finding_category, f"Found something on {company}'s site")

    # Ensure under 60 chars
    if len(subject) > 60:
        subject = subject[:57] + "..."

    return subject
