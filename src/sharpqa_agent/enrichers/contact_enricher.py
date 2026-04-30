"""Contact enricher — scrapes /team, /about, /contact pages to find team member details."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from sharpqa_agent.core.exceptions import EnricherError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Contact

logger = get_logger(__name__)

# Common team/about page paths to check
TEAM_PATHS = ["/team", "/about", "/about-us", "/contact", "/people", "/our-team", "/leadership"]

# Role keywords that indicate decision-makers
ROLE_KEYWORDS = [
    "ceo", "cto", "coo", "cfo", "founder", "co-founder", "cofounder",
    "chief", "vp", "vice president", "head of", "director",
    "engineering", "product", "technology", "growth", "marketing",
]

# Email pattern
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


class ContactEnricher:
    """Discover contact information by scraping company team/about pages.

    Uses Playwright to navigate to common team pages and extract
    names, titles, and email addresses via heuristics.
    """

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless

    async def enrich(self, lead_id: str, website_url: str) -> list[Contact]:
        """Scrape team pages to find contacts for a lead.

        Args:
            lead_id: The lead's UUID.
            website_url: Base URL of the company website.

        Returns:
            List of Contact models discovered.

        Raises:
            EnricherError: If Playwright fails.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError as error:
            raise EnricherError("Playwright is required for contact enrichment") from error

        contacts: list[Contact] = []

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=self.headless)
                page = await browser.new_page()

                for path in TEAM_PATHS:
                    url = urljoin(website_url.rstrip("/") + "/", path.lstrip("/"))

                    try:
                        response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        if not response or response.status >= 400:
                            continue

                        html = await page.content()
                        page_contacts = self._extract_contacts_from_html(html, lead_id, website_url)
                        contacts.extend(page_contacts)

                    except Exception:
                        continue  # Best-effort — try next path

                await browser.close()

        except EnricherError:
            raise
        except Exception as error:
            raise EnricherError(f"Contact enrichment failed for {website_url}: {error}") from error

        # Deduplicate by email or name
        contacts = self._deduplicate_contacts(contacts)

        # Mark the best contact as primary
        if contacts:
            contacts = self._select_primary_contact(contacts)

        logger.info("contact_enrichment_complete", lead_id=lead_id, contacts_found=len(contacts))
        return contacts

    def _extract_contacts_from_html(self, html: str, lead_id: str, website_url: str) -> list[Contact]:
        """Parse HTML to extract contact information.

        Args:
            html: Raw HTML content of a team/about page.
            lead_id: Lead UUID for linking contacts.
            website_url: Base URL for context.

        Returns:
            List of extracted Contact models.
        """
        soup = BeautifulSoup(html, "lxml")
        contacts: list[Contact] = []

        # Strategy 1: Look for structured team member cards
        team_cards = soup.select(
            ".team-member, .team-card, .person, .member, "
            "[class*='team'], [class*='person'], [class*='member'], "
            "[class*='staff'], [class*='leader']"
        )

        for card in team_cards:
            contact = self._parse_team_card(card, lead_id)
            if contact and (contact.full_name or contact.email_address):
                contacts.append(contact)

        # Strategy 2: If no structured cards, scan for emails on the page
        if not contacts:
            emails = EMAIL_REGEX.findall(soup.get_text())
            # Filter out generic emails
            generic_prefixes = {"info", "hello", "contact", "support", "sales", "admin", "noreply", "no-reply"}
            personal_emails = [
                e for e in set(emails)
                if e.split("@")[0].lower() not in generic_prefixes
            ]

            for email in personal_emails[:5]:
                contacts.append(Contact(
                    lead_id=lead_id,
                    email_address=email,
                    email_confidence=0.8,
                ))

        # Strategy 3: Look for LinkedIn/Twitter links
        for contact in contacts:
            self._find_social_links(soup, contact)

        return contacts

    def _parse_team_card(self, card, lead_id: str) -> Contact | None:
        """Parse a single team member card element.

        Args:
            card: BeautifulSoup element representing a team member.
            lead_id: Lead UUID.

        Returns:
            A Contact model or None if no useful info found.
        """
        # Try to find name
        name = None
        name_elem = card.select_one("h2, h3, h4, [class*='name'], strong, b")
        if name_elem:
            name_text = name_elem.get_text(strip=True)
            # Basic validation: should look like a name (2-4 words, not too long)
            if 2 <= len(name_text.split()) <= 5 and len(name_text) < 60:
                name = name_text

        # Try to find title
        title = None
        title_elem = card.select_one(
            "[class*='title'], [class*='role'], [class*='position'], "
            "p, span"
        )
        if title_elem:
            title_text = title_elem.get_text(strip=True)
            if any(kw in title_text.lower() for kw in ROLE_KEYWORDS):
                title = title_text[:100]

        # Try to find email
        email = None
        email_confidence = 0.0
        email_link = card.select_one("a[href^='mailto:']")
        if email_link:
            email = email_link.get("href", "").replace("mailto:", "").strip()
            email_confidence = 0.95
        else:
            # Look for email text in the card
            card_text = card.get_text()
            found_emails = EMAIL_REGEX.findall(card_text)
            if found_emails:
                email = found_emails[0]
                email_confidence = 0.85

        # Find LinkedIn
        linkedin = None
        linkedin_link = card.select_one("a[href*='linkedin.com']")
        if linkedin_link:
            linkedin = linkedin_link.get("href")

        if not name and not email:
            return None

        return Contact(
            lead_id=lead_id,
            full_name=name,
            job_title=title,
            email_address=email,
            email_confidence=email_confidence,
            linkedin_url=linkedin,
        )

    def _find_social_links(self, soup: BeautifulSoup, contact: Contact) -> None:
        """Look for social links near the contact's name in the page."""
        if contact.linkedin_url:
            return

        # Try to find LinkedIn links on the page
        linkedin_links = soup.select("a[href*='linkedin.com/in/']")
        if linkedin_links and not contact.linkedin_url:
            contact.linkedin_url = linkedin_links[0].get("href")

    def _deduplicate_contacts(self, contacts: list[Contact]) -> list[Contact]:
        """Remove duplicate contacts based on email or name."""
        seen_emails: set[str] = set()
        seen_names: set[str] = set()
        unique: list[Contact] = []

        for contact in contacts:
            if contact.email_address:
                if contact.email_address.lower() in seen_emails:
                    continue
                seen_emails.add(contact.email_address.lower())
            elif contact.full_name:
                if contact.full_name.lower() in seen_names:
                    continue
                seen_names.add(contact.full_name.lower())
            unique.append(contact)

        return unique

    def _select_primary_contact(self, contacts: list[Contact]) -> list[Contact]:
        """Mark the best contact as primary based on role seniority and email availability."""
        # Score each contact
        def contact_score(contact: Contact) -> int:
            score = 0
            if contact.email_address:
                score += 10
            if contact.job_title:
                title_lower = contact.job_title.lower()
                if any(kw in title_lower for kw in ["ceo", "founder", "co-founder"]):
                    score += 5
                elif any(kw in title_lower for kw in ["cto", "head of", "vp", "director"]):
                    score += 3
            if contact.linkedin_url:
                score += 2
            return score

        contacts.sort(key=contact_score, reverse=True)
        contacts[0].is_primary_contact = True
        return contacts
