"""Social handle finder — extracts social media URLs from website HTML."""

from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup

from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)

# Regex patterns for social media URLs
SOCIAL_PATTERNS = {
    "twitter": re.compile(r'https?://(?:www\.)?(?:twitter|x)\.com/([a-zA-Z0-9_]{1,15})(?:\?|/|$)', re.IGNORECASE),
    "linkedin_company": re.compile(r'https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9\-]+)', re.IGNORECASE),
    "linkedin_person": re.compile(r'https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9\-]+)', re.IGNORECASE),
    "github": re.compile(r'https?://(?:www\.)?github\.com/([a-zA-Z0-9\-]+)(?:\?|/|$)', re.IGNORECASE),
    "facebook": re.compile(r'https?://(?:www\.)?facebook\.com/([a-zA-Z0-9.\-]+)(?:\?|/|$)', re.IGNORECASE),
}


class SocialHandleFinder:
    """Extract social media links from a company's website.

    Scans the homepage HTML for links to Twitter, LinkedIn, GitHub, etc.
    """

    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    async def find_handles(self, website_url: str) -> dict[str, str]:
        """Find social media handles from a website's homepage.

        Args:
            website_url: URL to scan for social links.

        Returns:
            Dictionary mapping platform names to URLs/handles.
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(website_url)
                html = response.text
        except Exception as error:
            logger.warning("social_scan_failed", url=website_url, error=str(error))
            return {}

        soup = BeautifulSoup(html, "lxml")
        handles: dict[str, str] = {}

        # Extract all links from the page
        all_links = set()
        for link_elem in soup.find_all("a", href=True):
            all_links.add(link_elem["href"])

        # Match against patterns
        for link in all_links:
            for platform, pattern in SOCIAL_PATTERNS.items():
                if platform in handles:
                    continue
                match = pattern.search(link)
                if match:
                    handle = match.group(1)
                    # Filter out generic pages
                    if handle.lower() not in ("share", "intent", "sharer", "login", "signup"):
                        handles[platform] = link

        logger.info("social_handles_found", url=website_url, handles=list(handles.keys()))
        return handles
