"""YC (Y Combinator) lead sourcer — scrapes ycombinator.com/companies."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sharpqa_agent.core.exceptions import SourcerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import RawLead
from sharpqa_agent.sourcers.base_sourcer import BaseSourcer

logger = get_logger(__name__)

YC_BASE_URL = "https://www.ycombinator.com"
YC_COMPANIES_URL = f"{YC_BASE_URL}/companies"


class YCSourcer(BaseSourcer):
    """Discover funded startups from Y Combinator's company directory.

    Uses Playwright for JS-rendered pages. Rate limited to 1 request per 3 seconds.
    """

    source_name = "yc"

    def __init__(self, rate_limit_seconds: float = 3.0, headless: bool = True) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self.headless = headless

    async def fetch_new_leads(self, since: datetime | None = None, limit: int = 50) -> list[RawLead]:
        """Fetch startup leads from YC's company directory.

        Args:
            since: Not used directly — YC pages are sorted by batch.
            limit: Maximum number of leads to return.

        Returns:
            List of RawLead models parsed from the YC directory.

        Raises:
            SourcerError: If Playwright fails or the page structure changes.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise SourcerError("Playwright is required for YC sourcer. Install via: playwright install chromium") from error

        leads: list[RawLead] = []

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                # Load the companies page with filters for recently funded
                url = f"{YC_COMPANIES_URL}?batch=W24&batch=S24&batch=W25&batch=S25"
                logger.info("yc_sourcer_fetching", url=url)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Scroll to load more results
                for _ in range(3):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(self.rate_limit_seconds)

                html = await page.content()
                await browser.close()

            leads = self._parse_companies_page(html, limit)
            logger.info("yc_sourcer_complete", leads_found=len(leads))

        except SourcerError:
            raise
        except Exception as error:
            raise SourcerError(f"YC sourcer failed: {error}") from error

        return leads

    def _parse_companies_page(self, html: str, limit: int) -> list[RawLead]:
        """Parse the YC companies listing HTML into RawLead models.

        Args:
            html: Raw HTML content of the companies page.
            limit: Max leads to return.

        Returns:
            List of parsed RawLead models.
        """
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []

        # YC uses dynamic class names, so we look for common patterns
        company_links = soup.select("a[href*='/companies/']")
        seen_slugs: set[str] = set()

        for link in company_links:
            if len(leads) >= limit:
                break

            href = link.get("href", "")
            slug_match = re.search(r"/companies/([^/?#]+)", href)
            if not slug_match:
                continue

            slug = slug_match.group(1)
            if slug in seen_slugs or slug in ("", "top-companies"):
                continue
            seen_slugs.add(slug)

            # Extract company name — look in various possible elements
            company_name = ""
            name_elem = link.select_one("[class*='coName'], [class*='name'], h4, h3")
            if name_elem:
                company_name = name_elem.get_text(strip=True)
            elif link.get_text(strip=True):
                company_name = link.get_text(strip=True).split("\n")[0].strip()

            if not company_name or len(company_name) > 100:
                continue

            # Extract description
            description = ""
            desc_elem = link.select_one("[class*='coDescription'], [class*='description']")
            if desc_elem:
                description = desc_elem.get_text(strip=True)

            # Look for website URL in sibling elements
            parent = link.parent
            website_url = ""
            if parent:
                website_link = parent.select_one("a[href*='http'][target='_blank']")
                if website_link:
                    website_url = website_link.get("href", "")

            # Extract batch info for funding context
            batch_text = ""
            if parent:
                pill_spans = parent.select("span")
                for span in pill_spans:
                    text = span.get_text(strip=True)
                    if re.match(r"^[WS]\d{2}$", text):
                        batch_text = text
                        break

            # If no website found, construct from slug
            if not website_url:
                website_url = f"https://{slug}.com"

            # Normalize URL
            if not website_url.startswith("http"):
                website_url = f"https://{website_url}"

            leads.append(RawLead(
                company_name=company_name,
                website_url=website_url,
                source_platform="yc",
                source_reference_id=slug,
                funding_stage="seed",  # YC companies are typically seed-stage
                short_description=description or None,
                industry_tags=[],
                country_code="US",  # default for YC
            ))

        return leads

    async def healthcheck(self) -> bool:
        """Check if YC website is reachable.

        Returns:
            True if the companies page loads.
        """
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(YC_COMPANIES_URL, follow_redirects=True)
                return response.status_code == 200
        except Exception:
            return False
