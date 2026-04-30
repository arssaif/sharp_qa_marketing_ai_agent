"""Tech stack detector — identifies technologies used by a website via response headers, scripts, and meta tags."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import TechStack

logger = get_logger(__name__)

# Technology detection rules (simplified webappanalyzer-style)
TECH_RULES: list[dict] = [
    # Frontend frameworks
    {"name": "React", "category": "frontend", "patterns": [
        {"type": "script_src", "regex": r"react"},
        {"type": "html", "regex": r'data-reactroot|data-reactid|__NEXT_DATA__'},
    ]},
    {"name": "Vue.js", "category": "frontend", "patterns": [
        {"type": "script_src", "regex": r"vue"},
        {"type": "html", "regex": r"data-v-[a-f0-9]|__vue__"},
    ]},
    {"name": "Angular", "category": "frontend", "patterns": [
        {"type": "script_src", "regex": r"angular|ng-"},
        {"type": "html", "regex": r"ng-app|ng-controller|_ng(host|content)"},
    ]},
    {"name": "Next.js", "category": "frontend", "patterns": [
        {"type": "html", "regex": r"__NEXT_DATA__|_next/static"},
        {"type": "header", "key": "x-powered-by", "regex": r"Next\.js"},
    ]},
    {"name": "Nuxt.js", "category": "frontend", "patterns": [
        {"type": "html", "regex": r"__NUXT__|_nuxt/"},
    ]},
    {"name": "Svelte", "category": "frontend", "patterns": [
        {"type": "html", "regex": r"svelte-[a-z0-9]"},
    ]},
    # CSS frameworks
    {"name": "Tailwind CSS", "category": "css", "patterns": [
        {"type": "html", "regex": r'class="[^"]*(?:flex|grid|px-|py-|mt-|mb-|text-)[^"]*"'},
    ]},
    {"name": "Bootstrap", "category": "css", "patterns": [
        {"type": "script_src", "regex": r"bootstrap"},
        {"type": "html", "regex": r'class="[^"]*(?:container-fluid|col-md-|btn-primary)[^"]*"'},
    ]},
    # Backend / platforms
    {"name": "WordPress", "category": "cms", "patterns": [
        {"type": "html", "regex": r"wp-content|wp-includes|wordpress"},
        {"type": "header", "key": "x-powered-by", "regex": r"WordPress"},
    ]},
    {"name": "Shopify", "category": "ecommerce", "patterns": [
        {"type": "html", "regex": r"cdn\.shopify\.com|Shopify\.theme"},
    ]},
    {"name": "Webflow", "category": "cms", "patterns": [
        {"type": "html", "regex": r"webflow\.com|wf-"},
    ]},
    {"name": "Squarespace", "category": "cms", "patterns": [
        {"type": "html", "regex": r"squarespace\.com|sqsp"},
    ]},
    {"name": "Wix", "category": "cms", "patterns": [
        {"type": "html", "regex": r"wix\.com|wixsite"},
    ]},
    # Analytics
    {"name": "Google Analytics", "category": "analytics", "patterns": [
        {"type": "script_src", "regex": r"google-analytics\.com|googletagmanager\.com|gtag"},
    ]},
    {"name": "Mixpanel", "category": "analytics", "patterns": [
        {"type": "script_src", "regex": r"mixpanel"},
    ]},
    {"name": "Segment", "category": "analytics", "patterns": [
        {"type": "script_src", "regex": r"segment\.com|analytics\.js"},
    ]},
    {"name": "Hotjar", "category": "analytics", "patterns": [
        {"type": "script_src", "regex": r"hotjar"},
    ]},
    # Infrastructure
    {"name": "Cloudflare", "category": "cdn", "patterns": [
        {"type": "header", "key": "server", "regex": r"cloudflare"},
        {"type": "header", "key": "cf-ray", "regex": r".+"},
    ]},
    {"name": "Vercel", "category": "hosting", "patterns": [
        {"type": "header", "key": "x-vercel-id", "regex": r".+"},
        {"type": "header", "key": "server", "regex": r"Vercel"},
    ]},
    {"name": "Netlify", "category": "hosting", "patterns": [
        {"type": "header", "key": "server", "regex": r"Netlify"},
        {"type": "header", "key": "x-nf-request-id", "regex": r".+"},
    ]},
    {"name": "AWS", "category": "hosting", "patterns": [
        {"type": "header", "key": "server", "regex": r"AmazonS3|CloudFront|awselb"},
        {"type": "header", "key": "x-amz-request-id", "regex": r".+"},
    ]},
    # Auth / tools
    {"name": "Stripe", "category": "payments", "patterns": [
        {"type": "script_src", "regex": r"stripe\.com|js\.stripe"},
    ]},
    {"name": "Intercom", "category": "support", "patterns": [
        {"type": "script_src", "regex": r"intercom"},
        {"type": "html", "regex": r"intercomSettings|intercom-frame"},
    ]},
    {"name": "Sentry", "category": "monitoring", "patterns": [
        {"type": "script_src", "regex": r"sentry"},
    ]},
]


class TechStackDetector:
    """Detect technologies used by a website by inspecting headers, scripts, and HTML.

    Ports webappanalyzer's open-source approach: checks response headers,
    script src patterns, meta tags, and HTML content.
    """

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    async def detect(self, lead_id: str, website_url: str) -> list[TechStack]:
        """Detect the technology stack of a website.

        Args:
            lead_id: The lead's UUID.
            website_url: URL to analyze.

        Returns:
            List of TechStack models for detected technologies.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True
            ) as client:
                response = await client.get(website_url)
        except Exception as error:
            logger.warning("tech_detection_failed", url=website_url, error=str(error))
            return []

        html = response.text
        headers = {k.lower(): v for k, v in response.headers.items()}
        soup = BeautifulSoup(html, "lxml")

        # Collect all script src attributes
        script_srcs = " ".join(
            tag.get("src", "") for tag in soup.find_all("script", src=True)
        )

        detected: list[TechStack] = []

        for rule in TECH_RULES:
            confidence = self._check_rule(rule, html, headers, script_srcs)
            if confidence > 0:
                detected.append(TechStack(
                    lead_id=lead_id,
                    category=rule["category"],
                    technology_name=rule["name"],
                    detection_confidence=confidence,
                ))

        logger.info("tech_stack_detected", lead_id=lead_id, technologies=len(detected))
        return detected

    def _check_rule(self, rule: dict, html: str, headers: dict, script_srcs: str) -> float:
        """Check if a technology rule matches the page.

        Args:
            rule: Technology detection rule.
            html: Page HTML content.
            headers: Response headers (lowercased).
            script_srcs: Concatenated script src attributes.

        Returns:
            Detection confidence (0.0 to 1.0).
        """
        matches = 0
        total_patterns = len(rule.get("patterns", []))

        for pattern in rule.get("patterns", []):
            pattern_type = pattern.get("type")
            regex = pattern.get("regex", "")

            try:
                if pattern_type == "html" and re.search(regex, html, re.IGNORECASE):
                    matches += 1
                elif pattern_type == "script_src" and re.search(regex, script_srcs, re.IGNORECASE):
                    matches += 1
                elif pattern_type == "header":
                    header_key = pattern.get("key", "").lower()
                    header_value = headers.get(header_key, "")
                    if header_value and re.search(regex, header_value, re.IGNORECASE):
                        matches += 1
            except re.error:
                continue

        if matches == 0:
            return 0.0
        return round(min(matches / max(total_patterns, 1), 1.0), 2)
