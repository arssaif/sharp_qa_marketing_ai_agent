"""Finding normalizer — ensures all findings from different tools conform to the unified schema."""

from __future__ import annotations

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel

logger = get_logger(__name__)


def normalize_finding(finding: Finding) -> Finding:
    """Validate and normalize a finding to ensure it conforms to the unified schema.

    Args:
        finding: The Finding model to normalize.

    Returns:
        A normalized Finding model with cleaned fields.
    """
    # Ensure title is not too long
    if len(finding.finding_title) > 120:
        finding.finding_title = finding.finding_title[:117] + "..."

    # Ensure description is reasonable length
    if finding.finding_description and len(finding.finding_description) > 1000:
        finding.finding_description = finding.finding_description[:997] + "..."

    # Validate category
    if isinstance(finding.finding_category, str):
        try:
            finding.finding_category = FindingCategory(finding.finding_category)
        except ValueError:
            finding.finding_category = FindingCategory.BEST_PRACTICES

    # Validate severity
    if isinstance(finding.severity_level, str):
        try:
            finding.severity_level = SeverityLevel(finding.severity_level)
        except ValueError:
            finding.severity_level = SeverityLevel.LOW

    return finding


def deduplicate_findings(findings: list[Finding]) -> list[Finding]:
    """Remove duplicate findings based on title + category + page_url.

    Args:
        findings: List of findings that may contain duplicates.

    Returns:
        Deduplicated list of findings, keeping the highest severity for duplicates.
    """
    seen: dict[str, Finding] = {}
    severity_order = {SeverityLevel.CRITICAL: 4, SeverityLevel.HIGH: 3, SeverityLevel.MEDIUM: 2, SeverityLevel.LOW: 1}

    for finding in findings:
        key = f"{finding.finding_category}:{finding.finding_title}:{finding.page_url}"
        if key not in seen:
            seen[key] = finding
        else:
            existing = seen[key]
            if severity_order.get(finding.severity_level, 0) > severity_order.get(existing.severity_level, 0):
                seen[key] = finding

    result = list(seen.values())
    if len(result) < len(findings):
        logger.info("findings_deduplicated", before=len(findings), after=len(result))
    return result
