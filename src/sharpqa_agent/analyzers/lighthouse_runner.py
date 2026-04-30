"""Lighthouse CLI runner — executes Google Lighthouse and extracts failing audits."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from sharpqa_agent.core.exceptions import AnalyzerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel

logger = get_logger(__name__)


class LighthouseRunner:
    """Run Google Lighthouse CLI and parse results into findings.

    Extracts failing audits with score < 0.5 from performance, SEO,
    and best-practices categories.
    """

    def __init__(self, timeout_seconds: int = 120) -> None:
        self.timeout_seconds = timeout_seconds

    async def analyze(self, lead_id: str, website_url: str) -> list[Finding]:
        """Run Lighthouse against a URL and extract failing audits.

        Args:
            lead_id: The lead's UUID for linking findings.
            website_url: URL to audit.

        Returns:
            List of Finding models for failing audits.

        Raises:
            AnalyzerError: If Lighthouse CLI is not installed or fails.
        """
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            output_path = tmp.name

        command = [
            "lighthouse", website_url,
            "--output=json",
            f"--output-path={output_path}",
            "--quiet",
            '--chrome-flags="--headless --no-sandbox"',
            "--only-categories=performance,seo,best-practices,accessibility",
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except FileNotFoundError:
            raise AnalyzerError("Lighthouse CLI not found. Install via: npm install -g lighthouse")
        except asyncio.TimeoutError:
            process.kill()
            raise AnalyzerError(f"Lighthouse timed out after {self.timeout_seconds}s for {website_url}")
        except Exception as error:
            raise AnalyzerError(f"Lighthouse failed for {website_url}: {error}") from error

        # Parse the output
        try:
            report_path = Path(output_path)
            if not report_path.exists():
                logger.warning("lighthouse_no_output", url=website_url)
                return []

            report = json.loads(report_path.read_text(encoding="utf-8"))
            report_path.unlink(missing_ok=True)
        except json.JSONDecodeError as error:
            raise AnalyzerError(f"Failed to parse Lighthouse JSON: {error}") from error

        return self._extract_findings(lead_id, report, website_url)

    def _extract_findings(self, lead_id: str, report: dict, page_url: str) -> list[Finding]:
        """Parse the Lighthouse JSON report and extract failing audits.

        Args:
            lead_id: Lead UUID.
            report: Parsed Lighthouse JSON report.
            page_url: The audited URL.

        Returns:
            List of findings for audits with score < 0.5.
        """
        findings: list[Finding] = []
        audits = report.get("audits", {})
        categories = report.get("categories", {})

        # Extract category scores as high-level findings
        category_mapping = {
            "performance": FindingCategory.PERFORMANCE,
            "accessibility": FindingCategory.ACCESSIBILITY,
            "seo": FindingCategory.SEO,
            "best-practices": FindingCategory.BEST_PRACTICES,
        }

        for cat_key, finding_cat in category_mapping.items():
            cat_data = categories.get(cat_key, {})
            score = cat_data.get("score")
            if score is not None and score < 0.5:
                severity = SeverityLevel.CRITICAL if score < 0.3 else SeverityLevel.HIGH
                findings.append(Finding(
                    lead_id=lead_id,
                    finding_category=finding_cat,
                    finding_title=f"Low Lighthouse {cat_key} score: {int(score * 100)}/100",
                    finding_description=f"The {cat_key} category scored {int(score * 100)}/100",
                    severity_level=severity,
                    evidence_json=json.dumps({"category": cat_key, "score": score}),
                    page_url=page_url,
                    tool_source="lighthouse",
                ))

        # Extract individual failing audits
        for audit_id, audit_data in audits.items():
            score = audit_data.get("score")
            if score is None or score >= 0.5:
                continue

            title = audit_data.get("title", audit_id)
            description = audit_data.get("description", "")

            # Map to category based on the audit group
            category = FindingCategory.PERFORMANCE  # default
            if "accessibility" in audit_id or "aria" in audit_id or "color-contrast" in audit_id:
                category = FindingCategory.ACCESSIBILITY
            elif "seo" in audit_id or "meta" in audit_id or "crawlable" in audit_id:
                category = FindingCategory.SEO
            elif "best-practice" in audit_id:
                category = FindingCategory.BEST_PRACTICES

            severity = SeverityLevel.HIGH if score < 0.3 else SeverityLevel.MEDIUM

            # Truncate evidence
            display_value = audit_data.get("displayValue", "")
            evidence = {
                "audit_id": audit_id,
                "score": score,
                "display_value": display_value[:200] if display_value else "",
            }

            findings.append(Finding(
                lead_id=lead_id,
                finding_category=category,
                finding_title=title[:120],
                finding_description=description[:500],
                severity_level=severity,
                evidence_json=json.dumps(evidence),
                page_url=page_url,
                tool_source="lighthouse",
            ))

        logger.info("lighthouse_findings_extracted", lead_id=lead_id, count=len(findings))
        return findings[:20]  # Cap findings per audit
