"""Playwright-based website auditor — captures console errors, broken resources, mobile issues."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

from sharpqa_agent.core.exceptions import AnalyzerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel

logger = get_logger(__name__)


class PlaywrightAuditor:
    """Highest-value analyzer: loads pages and captures real browser issues.

    Captures console errors/warnings, failed network requests, broken images,
    broken links, and mobile viewport rendering problems.
    """

    def __init__(self, headless: bool = True, screenshots_dir: str = "data/screenshots") -> None:
        self.headless = headless
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    async def analyze(self, lead_id: str, website_url: str) -> list[Finding]:
        """Run a comprehensive browser-based audit on the website.

        Args:
            lead_id: The lead's UUID for linking findings.
            website_url: URL to audit.

        Returns:
            List of Finding models discovered during the audit.

        Raises:
            AnalyzerError: If Playwright fails to load the page.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise AnalyzerError("Playwright is required. Install via: playwright install chromium") from error

        findings: list[Finding] = []
        console_messages: list[dict] = []
        failed_requests: list[dict] = []

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)

                # Desktop viewport audit
                desktop_context = await browser.new_context(viewport={"width": 1920, "height": 1080})
                desktop_page = await desktop_context.new_page()

                # Collect console messages
                desktop_page.on("console", lambda msg: console_messages.append({
                    "type": msg.type, "text": msg.text, "url": desktop_page.url,
                }))

                # Collect failed network requests
                desktop_page.on("requestfailed", lambda req: failed_requests.append({
                    "url": req.url, "method": req.method,
                    "failure": req.failure if hasattr(req, "failure") else "unknown",
                }))

                # Navigate to the site
                try:
                    response = await desktop_page.goto(website_url, wait_until="networkidle", timeout=30000)
                except Exception as nav_error:
                    findings.append(Finding(
                        lead_id=lead_id,
                        finding_category=FindingCategory.BROKEN_RESOURCE,
                        finding_title="Website failed to load",
                        finding_description=f"Navigation to {website_url} failed: {nav_error}",
                        severity_level=SeverityLevel.CRITICAL,
                        page_url=website_url,
                        tool_source="playwright",
                    ))
                    await browser.close()
                    return findings

                # Check HTTP response status
                if response and response.status >= 400:
                    findings.append(Finding(
                        lead_id=lead_id,
                        finding_category=FindingCategory.BROKEN_RESOURCE,
                        finding_title=f"Homepage returns HTTP {response.status}",
                        finding_description=f"The homepage at {website_url} returned status {response.status}",
                        severity_level=SeverityLevel.CRITICAL,
                        page_url=website_url,
                        tool_source="playwright",
                    ))

                await asyncio.sleep(2)  # Let JS execute

                # Take desktop screenshot
                await self._take_screenshot(desktop_page, lead_id, "desktop")

                # Check for console errors
                findings.extend(self._analyze_console_messages(lead_id, console_messages, website_url))

                # Check for failed requests
                findings.extend(self._analyze_failed_requests(lead_id, failed_requests, website_url))

                # Check for broken images
                broken_images = await self._check_broken_images(desktop_page)
                findings.extend(self._create_broken_image_findings(lead_id, broken_images, website_url))

                # Check for broken links (sample)
                broken_links = await self._check_broken_links(desktop_page, website_url)
                findings.extend(self._create_broken_link_findings(lead_id, broken_links, website_url))

                await desktop_context.close()

                # Mobile viewport audit
                mobile_context = await browser.new_context(
                    viewport={"width": 375, "height": 812},
                    user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                               "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
                )
                mobile_page = await mobile_context.new_page()

                try:
                    await mobile_page.goto(website_url, wait_until="networkidle", timeout=30000)
                    await asyncio.sleep(2)
                    await self._take_screenshot(mobile_page, lead_id, "mobile")

                    # Check for horizontal overflow (mobile layout issue)
                    overflow_findings = await self._check_mobile_overflow(mobile_page, lead_id, website_url)
                    findings.extend(overflow_findings)
                except Exception:
                    pass  # Mobile audit is best-effort

                await mobile_context.close()
                await browser.close()

        except AnalyzerError:
            raise
        except Exception as error:
            raise AnalyzerError(f"Playwright audit failed for {website_url}: {error}") from error

        logger.info("playwright_audit_complete", lead_id=lead_id, findings=len(findings))
        return findings

    def _analyze_console_messages(
        self, lead_id: str, messages: list[dict], page_url: str
    ) -> list[Finding]:
        """Convert browser console messages into findings."""
        findings: list[Finding] = []
        error_messages = [m for m in messages if m["type"] in ("error", "warning")]

        # Group similar errors
        seen_errors: set[str] = set()
        for msg in error_messages:
            text = msg["text"][:200]
            if text in seen_errors:
                continue
            seen_errors.add(text)

            severity = SeverityLevel.HIGH if msg["type"] == "error" else SeverityLevel.MEDIUM
            category = FindingCategory.CONSOLE_ERROR

            findings.append(Finding(
                lead_id=lead_id,
                finding_category=category,
                finding_title=f"Console {msg['type']}: {text[:80]}",
                finding_description=text,
                severity_level=severity,
                evidence_json=json.dumps(msg),
                page_url=page_url,
                tool_source="playwright",
            ))

        return findings[:10]  # Cap at 10 console findings

    def _analyze_failed_requests(
        self, lead_id: str, requests: list[dict], page_url: str
    ) -> list[Finding]:
        """Convert failed network requests into findings."""
        findings: list[Finding] = []

        for req in requests[:5]:
            findings.append(Finding(
                lead_id=lead_id,
                finding_category=FindingCategory.BROKEN_RESOURCE,
                finding_title=f"Failed network request: {req['method']} {urlparse(req['url']).path[:60]}",
                finding_description=f"Request to {req['url']} failed",
                severity_level=SeverityLevel.MEDIUM,
                evidence_json=json.dumps(req),
                page_url=page_url,
                tool_source="playwright",
            ))

        return findings

    async def _check_broken_images(self, page) -> list[str]:
        """Detect images that failed to load."""
        return await page.evaluate("""
            () => {
                const broken = [];
                document.querySelectorAll('img').forEach(img => {
                    if (img.naturalWidth === 0 && img.src && !img.src.startsWith('data:')) {
                        broken.push(img.src);
                    }
                });
                return broken;
            }
        """)

    def _create_broken_image_findings(
        self, lead_id: str, broken_images: list[str], page_url: str
    ) -> list[Finding]:
        """Create findings for broken images."""
        findings: list[Finding] = []
        for img_url in broken_images[:5]:
            findings.append(Finding(
                lead_id=lead_id,
                finding_category=FindingCategory.BROKEN_RESOURCE,
                finding_title=f"Broken image: {urlparse(img_url).path[:60]}",
                finding_description=f"Image at {img_url} failed to load (naturalWidth === 0)",
                severity_level=SeverityLevel.MEDIUM,
                evidence_json=json.dumps({"image_url": img_url}),
                page_url=page_url,
                tool_source="playwright",
            ))
        return findings

    async def _check_broken_links(self, page, base_url: str) -> list[dict]:
        """Check a sample of external links via HEAD requests."""
        import httpx

        links = await page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a[href^="http"]').forEach(a => {
                    if (!a.href.includes(window.location.hostname)) {
                        links.push(a.href);
                    }
                });
                return [...new Set(links)].slice(0, 10);
            }
        """)

        broken: list[dict] = []
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            for url in links:
                try:
                    response = await client.head(url)
                    if response.status_code >= 400:
                        broken.append({"url": url, "status": response.status_code})
                except Exception:
                    broken.append({"url": url, "status": 0})

        return broken

    def _create_broken_link_findings(
        self, lead_id: str, broken_links: list[dict], page_url: str
    ) -> list[Finding]:
        """Create findings for broken external links."""
        findings: list[Finding] = []
        for link in broken_links[:5]:
            findings.append(Finding(
                lead_id=lead_id,
                finding_category=FindingCategory.BROKEN_RESOURCE,
                finding_title=f"Broken link: {urlparse(link['url']).netloc}{urlparse(link['url']).path[:40]}",
                finding_description=f"External link {link['url']} returned status {link['status']}",
                severity_level=SeverityLevel.LOW,
                evidence_json=json.dumps(link),
                page_url=page_url,
                tool_source="playwright",
            ))
        return findings

    async def _check_mobile_overflow(self, page, lead_id: str, page_url: str) -> list[Finding]:
        """Check if page content overflows the mobile viewport."""
        overflow_info = await page.evaluate("""
            () => {
                const body = document.body;
                const html = document.documentElement;
                const viewportWidth = window.innerWidth;
                const scrollWidth = Math.max(body.scrollWidth, html.scrollWidth);
                return {
                    viewport_width: viewportWidth,
                    scroll_width: scrollWidth,
                    overflows: scrollWidth > viewportWidth + 5,
                };
            }
        """)

        if overflow_info.get("overflows"):
            return [Finding(
                lead_id=lead_id,
                finding_category=FindingCategory.MOBILE,
                finding_title="Horizontal overflow on mobile viewport",
                finding_description=(
                    f"Page content ({overflow_info['scroll_width']}px) exceeds mobile viewport "
                    f"({overflow_info['viewport_width']}px), causing horizontal scroll"
                ),
                severity_level=SeverityLevel.HIGH,
                evidence_json=json.dumps(overflow_info),
                page_url=page_url,
                tool_source="playwright",
            )]
        return []

    async def _take_screenshot(self, page, lead_id: str, viewport_type: str) -> str | None:
        """Take a page screenshot and save it."""
        try:
            screenshot_path = self.screenshots_dir / f"{lead_id}_{viewport_type}.png"
            await page.screenshot(path=str(screenshot_path), full_page=False)
            return str(screenshot_path)
        except Exception:
            return None
