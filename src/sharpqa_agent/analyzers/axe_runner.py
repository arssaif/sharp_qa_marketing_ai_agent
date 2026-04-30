"""Axe-core accessibility runner — injects axe-core into Playwright pages to find WCAG violations."""

from __future__ import annotations

import json

from sharpqa_agent.core.exceptions import AnalyzerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel

logger = get_logger(__name__)

# Axe-core CDN URL for injection
AXE_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"


class AxeRunner:
    """Accessibility auditor using axe-core injected into Playwright.

    Navigates to the page, injects the axe-core library, runs axe.run(),
    and converts violations into Finding models.
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    async def analyze(self, lead_id: str, website_url: str) -> list[Finding]:
        """Run axe-core accessibility audit on a URL.

        Args:
            lead_id: The lead's UUID for linking findings.
            website_url: URL to audit for accessibility.

        Returns:
            List of Finding models for WCAG violations.

        Raises:
            AnalyzerError: If Playwright or axe injection fails.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise AnalyzerError("Playwright is required for axe-core audits") from error

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                await page.goto(website_url, wait_until="networkidle", timeout=30000)

                # Inject axe-core
                await page.add_script_tag(url=AXE_CDN_URL)

                # Run axe and get results
                results = await page.evaluate("""
                    async () => {
                        try {
                            const results = await axe.run();
                            return {
                                violations: results.violations.map(v => ({
                                    id: v.id,
                                    impact: v.impact,
                                    description: v.description,
                                    help: v.help,
                                    helpUrl: v.helpUrl,
                                    nodes_count: v.nodes.length,
                                    tags: v.tags,
                                })),
                                passes: results.passes.length,
                                violations_count: results.violations.length,
                            };
                        } catch(e) {
                            return { error: e.message, violations: [] };
                        }
                    }
                """)

                await browser.close()

        except AnalyzerError:
            raise
        except Exception as error:
            raise AnalyzerError(f"Axe audit failed for {website_url}: {error}") from error

        if results.get("error"):
            logger.warning("axe_injection_error", url=website_url, error=results["error"])
            return []

        return self._convert_violations(lead_id, results.get("violations", []), website_url)

    def _convert_violations(
        self, lead_id: str, violations: list[dict], page_url: str
    ) -> list[Finding]:
        """Convert axe-core violations into Finding models.

        Args:
            lead_id: Lead UUID.
            violations: List of violation dicts from axe.run().
            page_url: The audited URL.

        Returns:
            List of accessibility Finding models.
        """
        findings: list[Finding] = []

        # Map axe impact levels to severity
        impact_to_severity = {
            "critical": SeverityLevel.CRITICAL,
            "serious": SeverityLevel.HIGH,
            "moderate": SeverityLevel.MEDIUM,
            "minor": SeverityLevel.LOW,
        }

        for violation in violations:
            impact = violation.get("impact", "moderate")
            severity = impact_to_severity.get(impact, SeverityLevel.MEDIUM)

            # Check if this is a WCAG AA violation
            tags = violation.get("tags", [])
            is_wcag_aa = any("wcag2aa" in tag or "wcag21aa" in tag for tag in tags)
            if is_wcag_aa and severity == SeverityLevel.MEDIUM:
                severity = SeverityLevel.HIGH

            findings.append(Finding(
                lead_id=lead_id,
                finding_category=FindingCategory.ACCESSIBILITY,
                finding_title=violation.get("help", violation.get("id", "Unknown violation"))[:120],
                finding_description=violation.get("description", "")[:500],
                severity_level=severity,
                evidence_json=json.dumps({
                    "axe_id": violation.get("id"),
                    "impact": impact,
                    "nodes_affected": violation.get("nodes_count", 0),
                    "help_url": violation.get("helpUrl", ""),
                    "tags": tags[:5],
                }),
                page_url=page_url,
                tool_source="axe",
            ))

        logger.info("axe_audit_complete", lead_id=lead_id, violations=len(findings))
        return findings
