"""Wellfound (formerly AngelList) lead sourcer — scrapes wellfound.com/startups."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime

from bs4 import BeautifulSoup

from sharpqa_agent.core.exceptions import SourcerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import RawLead
from sharpqa_agent.sourcers.base_sourcer import BaseSourcer

logger = get_logger(__name__)

WELLFOUND_URL = "https://wellfound.com/startups"


class WellfoundSourcer(BaseSourcer):
    """Discover startups from Wellfound's directory.

    Requires Playwright. Heavily rate-limited by Cloudflare — uses 5s delays
    with exponential backoff on 403 errors. Max 100 leads per day.
    """

    source_name = "wellfound"

    def __init__(self, rate_limit_seconds: float = 5.0, max_retries: int = 3, headless: bool = True) -> None:
        self.rate_limit_seconds = rate_limit_seconds
        self.max_retries = max_retries
        self.headless = headless

    async def fetch_new_leads(self, since: datetime | None = None, limit: int = 30) -> list[RawLead]:
        """Fetch startup leads from Wellfound's directory.

        Args:
            since: Not used directly.
            limit: Maximum number of leads to return.

        Returns:
            List of RawLead models.

        Raises:
            SourcerError: If scraping fails after retries.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise SourcerError("Playwright is required for Wellfound sourcer") from error

        leads: list[RawLead] = []
        retry_delay = self.rate_limit_seconds

        for attempt in range(self.max_retries):
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(headless=self.headless)
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()

                    logger.info("wellfound_sourcer_fetching", url=WELLFOUND_URL, attempt=attempt + 1)
                    response = await page.goto(WELLFOUND_URL, wait_until="domcontentloaded", timeout=30000)

                    if response and response.status == 403:
                        logger.warning("wellfound_cloudflare_block", attempt=attempt + 1)
                        await browser.close()
                        retry_delay *= 2
                        await asyncio.sleep(retry_delay)
                        continue

                    # Scroll to load content
                    for _ in range(2):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await asyncio.sleep(self.rate_limit_seconds)

                    html = await page.content()
                    await browser.close()

                leads = self._parse_startups_page(html, limit)
                logger.info("wellfound_sourcer_complete", leads_found=len(leads))
                return leads

            except SourcerError:
                raise
            except Exception as error:
                if attempt == self.max_retries - 1:
                    raise SourcerError(f"Wellfound sourcer failed after {self.max_retries} attempts: {error}") from error
                logger.warning("wellfound_sourcer_retry", attempt=attempt + 1, error=str(error))
                await asyncio.sleep(retry_delay)
                retry_delay *= 2

        return leads

    def _parse_startups_page(self, html: str, limit: int) -> list[RawLead]:
        """Parse Wellfound's startup listing page.

        Args:
            html: Raw HTML content.
            limit: Max leads to return.

        Returns:
            List of parsed RawLead models.
        """
        soup = BeautifulSoup(html, "lxml")
        leads: list[RawLead] = []

        # Wellfound uses various class patterns for startup cards
        startup_cards = soup.select(
            "[data-test='startup-card'], "
            "[class*='startup'], "
            "[class*='StartupResult'], "
            "div[class*='styles_component']"
        )

        for card in startup_cards:
            if len(leads) >= limit:
                break

            # Extract company name
            name_elem = card.select_one("h2, h3, [class*='name'], a[class*='startup']")
            if not name_elem:
                continue
            company_name = name_elem.get_text(strip=True)
            if not company_name or len(company_name) > 100:
                continue

            # Extract website/profile link
            link_elem = card.select_one("a[href]")
            profile_url = link_elem.get("href", "") if link_elem else ""

            # Extract description
            desc_elem = card.select_one("[class*='pitch'], [class*='tagline'], p")
            description = desc_elem.get_text(strip=True) if desc_elem else ""

            # Extract team size
            team_size = None
            size_elem = card.select_one("[class*='size'], [class*='employee']")
            if size_elem:
                size_text = size_elem.get_text(strip=True)
                if re.search(r"\d", size_text):
                    team_size = size_text

            # Extract funding info
            funding_stage = "unknown"
            funding_elem = card.select_one("[class*='funding'], [class*='raised']")
            if funding_elem:
                funding_text = funding_elem.get_text(strip=True).lower()
                if "seed" in funding_text:
                    funding_stage = "seed"
                elif "series a" in funding_text:
                    funding_stage = "series_a"
                elif "series b" in funding_text:
                    funding_stage = "series_b"

            # Construct website URL from profile
            slug = profile_url.rstrip("/").split("/")[-1] if profile_url else company_name.lower().replace(" ", "-")
            website_url = f"https://{slug}.com"

            leads.append(RawLead(
                company_name=company_name,
                website_url=website_url,
                source_platform="wellfound",
                source_reference_id=slug,
                funding_stage=funding_stage,
                team_size_range=team_size,
                short_description=description or None,
            ))

        return leads

    async def healthcheck(self) -> bool:
        """Check if Wellfound is reachable."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(WELLFOUND_URL, follow_redirects=True)
                return response.status_code in (200, 403)  # 403 means Cloudflare but site is up
        except Exception:
            return False
