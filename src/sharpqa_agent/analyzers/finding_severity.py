"""Finding severity rules engine — assigns business-impact severity based on finding properties."""

from __future__ import annotations

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel

logger = get_logger(__name__)

# Keywords that indicate critical business impact
CRITICAL_KEYWORDS = [
    "signup", "sign up", "register", "checkout", "payment", "login", "log in",
    "purchase", "subscribe", "pricing", "crash", "fatal", "uncaught",
]

HIGH_KEYWORDS = [
    "homepage", "landing", "main page", "wcag aa", "performance score",
    "https", "ssl", "broken form", "missing hsts",
]


def assess_business_impact(finding: Finding) -> Finding:
    """Assess and optionally adjust finding severity based on business impact rules.

    This is a rules engine (not ML) that considers the finding's context
    to determine real business impact. Findings on critical user flows
    (signup, checkout) are elevated in severity.

    Args:
        finding: The Finding to assess.

    Returns:
        The finding with potentially adjusted severity and a business_impact description.
    """
    title_lower = finding.finding_title.lower()
    desc_lower = (finding.finding_description or "").lower()
    page_lower = (finding.page_url or "").lower()
    combined_text = f"{title_lower} {desc_lower} {page_lower}"

    # Rule 1: Critical user flows
    is_critical_flow = any(kw in combined_text for kw in CRITICAL_KEYWORDS)
    if is_critical_flow and finding.severity_level in (SeverityLevel.MEDIUM, SeverityLevel.HIGH):
        finding.severity_level = SeverityLevel.CRITICAL
        finding.business_impact = _generate_impact_text(finding, "critical user flow")
        return finding

    # Rule 2: Homepage issues are more impactful
    is_homepage = any(kw in combined_text for kw in HIGH_KEYWORDS)
    if is_homepage and finding.severity_level == SeverityLevel.MEDIUM:
        finding.severity_level = SeverityLevel.HIGH
        finding.business_impact = _generate_impact_text(finding, "high-traffic page")
        return finding

    # Rule 3: Accessibility violations affecting many users
    if finding.finding_category == FindingCategory.ACCESSIBILITY:
        if finding.severity_level in (SeverityLevel.HIGH, SeverityLevel.CRITICAL):
            finding.business_impact = (
                "This accessibility violation affects approximately 15% of users who rely on "
                "assistive technology. It may also create legal compliance risk under ADA/WCAG requirements."
            )
            return finding

    # Rule 4: Performance issues
    if finding.finding_category == FindingCategory.PERFORMANCE:
        if finding.severity_level in (SeverityLevel.HIGH, SeverityLevel.CRITICAL):
            finding.business_impact = (
                "Poor performance directly impacts conversion rates — each additional second "
                "of load time costs approximately 7% in conversions. This is especially impactful "
                "for a startup relying on web-based acquisition."
            )
            return finding

    # Rule 5: Security header issues
    if finding.finding_category == FindingCategory.SECURITY_HEADER:
        finding.business_impact = (
            "Missing security headers increase vulnerability to common web attacks and may "
            "be flagged during enterprise buyer security reviews or SOC2 audits."
        )
        return finding

    # Default impact text
    if not finding.business_impact:
        finding.business_impact = _generate_impact_text(finding, "general")

    return finding


def _generate_impact_text(finding: Finding, context: str) -> str:
    """Generate a human-readable business impact description.

    Args:
        finding: The finding to describe impact for.
        context: The business context (e.g., 'critical user flow').

    Returns:
        Human-readable impact string.
    """
    category_impacts = {
        FindingCategory.PERFORMANCE: "Slow page loads reduce user engagement and conversion rates.",
        FindingCategory.ACCESSIBILITY: "Accessibility issues exclude users with disabilities and risk legal exposure.",
        FindingCategory.CONSOLE_ERROR: "JavaScript errors can cause broken functionality and degrade user experience.",
        FindingCategory.BROKEN_RESOURCE: "Broken resources create a perception of neglect and reduce trust.",
        FindingCategory.SECURITY_HEADER: "Missing security controls increase attack surface and audit risk.",
        FindingCategory.SEO: "SEO issues reduce organic discovery and increase customer acquisition cost.",
        FindingCategory.MOBILE: "Mobile rendering problems affect the majority of web traffic today.",
        FindingCategory.BEST_PRACTICES: "Not following best practices can lead to maintenance and security issues.",
    }

    base_impact = category_impacts.get(finding.finding_category, "This issue may affect user experience.")

    if context == "critical user flow":
        return f"CRITICAL PATH: This issue affects a revenue-critical user flow. {base_impact}"
    elif context == "high-traffic page":
        return f"HIGH VISIBILITY: This issue is on a high-traffic page. {base_impact}"

    return base_impact
