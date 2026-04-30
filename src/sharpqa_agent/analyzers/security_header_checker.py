"""Security header checker — inspects HTTP response headers for missing security controls."""

from __future__ import annotations

import json

import httpx

from sharpqa_agent.core.exceptions import AnalyzerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel

logger = get_logger(__name__)

# Security headers to check with their importance
SECURITY_HEADERS = {
    "strict-transport-security": {
        "title": "Missing HSTS (Strict-Transport-Security) header",
        "description": "HSTS forces browsers to use HTTPS, preventing protocol downgrade attacks and cookie hijacking.",
        "severity": SeverityLevel.HIGH,
    },
    "content-security-policy": {
        "title": "Missing Content-Security-Policy (CSP) header",
        "description": "CSP mitigates XSS attacks by specifying allowed content sources. Without it, the site is more vulnerable to script injection.",
        "severity": SeverityLevel.HIGH,
    },
    "x-frame-options": {
        "title": "Missing X-Frame-Options header",
        "description": "X-Frame-Options prevents clickjacking by controlling whether the page can be embedded in iframes.",
        "severity": SeverityLevel.MEDIUM,
    },
    "x-content-type-options": {
        "title": "Missing X-Content-Type-Options header",
        "description": "Without 'nosniff', browsers may MIME-sniff responses, potentially executing malicious content.",
        "severity": SeverityLevel.MEDIUM,
    },
    "referrer-policy": {
        "title": "Missing Referrer-Policy header",
        "description": "Controls how much referrer information is included with requests. Missing it may leak sensitive URL paths.",
        "severity": SeverityLevel.LOW,
    },
    "permissions-policy": {
        "title": "Missing Permissions-Policy header",
        "description": "Controls which browser features (camera, microphone, geolocation) the page can use.",
        "severity": SeverityLevel.LOW,
    },
}


class SecurityHeaderChecker:
    """Check a website's HTTP response headers for missing security controls.

    This is a passive, non-probing check — it only inspects the headers
    returned by a standard GET request.
    """

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    async def analyze(self, lead_id: str, website_url: str) -> list[Finding]:
        """Check security headers for a website.

        Args:
            lead_id: The lead's UUID for linking findings.
            website_url: URL to check headers for.

        Returns:
            List of Finding models for missing security headers.

        Raises:
            AnalyzerError: If the HTTP request fails.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                verify=True,
            ) as client:
                response = await client.get(website_url)
        except httpx.ConnectError as error:
            raise AnalyzerError(f"Cannot connect to {website_url}: {error}") from error
        except Exception as error:
            raise AnalyzerError(f"HTTP request failed for {website_url}: {error}") from error

        response_headers = {k.lower(): v for k, v in response.headers.items()}
        findings: list[Finding] = []

        for header_name, header_info in SECURITY_HEADERS.items():
            if header_name not in response_headers:
                findings.append(Finding(
                    lead_id=lead_id,
                    finding_category=FindingCategory.SECURITY_HEADER,
                    finding_title=header_info["title"],
                    finding_description=header_info["description"],
                    severity_level=header_info["severity"],
                    evidence_json=json.dumps({
                        "missing_header": header_name,
                        "present_security_headers": [
                            h for h in response_headers if h in SECURITY_HEADERS
                        ],
                    }),
                    page_url=website_url,
                    tool_source="security_header_check",
                ))

        # Check for HTTPS
        if not website_url.startswith("https://"):
            findings.append(Finding(
                lead_id=lead_id,
                finding_category=FindingCategory.SECURITY_HEADER,
                finding_title="Site not using HTTPS",
                finding_description="The website is not served over HTTPS, exposing all traffic to interception.",
                severity_level=SeverityLevel.CRITICAL,
                page_url=website_url,
                tool_source="security_header_check",
            ))

        logger.info("security_header_check_complete", lead_id=lead_id, missing=len(findings))
        return findings
