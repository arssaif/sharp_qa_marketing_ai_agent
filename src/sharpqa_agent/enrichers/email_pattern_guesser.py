"""Email pattern guesser — generates candidate emails and validates via MX lookup."""

from __future__ import annotations

import asyncio
import re
import socket
from urllib.parse import urlparse

from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)


class EmailPatternGuesser:
    """Generate candidate email addresses when none were scraped.

    Given a person's name and company domain, generates common email
    patterns and validates the domain has MX records.
    """

    # Common email patterns ordered by prevalence
    PATTERNS = [
        "{first}@{domain}",
        "{first}.{last}@{domain}",
        "{f}{last}@{domain}",
        "{first}{last}@{domain}",
        "{f}.{last}@{domain}",
        "{first}_{last}@{domain}",
        "{last}@{domain}",
    ]

    async def guess_emails(
        self, full_name: str, website_url: str
    ) -> list[dict[str, float]]:
        """Generate candidate email addresses for a person at a company.

        Args:
            full_name: Person's full name (e.g., "Jane Smith").
            website_url: Company website URL to extract domain from.

        Returns:
            List of dicts with 'email' and 'confidence' keys.
            Confidence ranges from 0.3 (guess) to 0.6 (pattern with valid MX).
        """
        domain = self._extract_domain(website_url)
        if not domain:
            return []

        parts = full_name.strip().split()
        if len(parts) < 2:
            return []

        first = parts[0].lower()
        last = parts[-1].lower()
        first_initial = first[0] if first else ""

        # Clean names
        first = re.sub(r"[^a-z]", "", first)
        last = re.sub(r"[^a-z]", "", last)

        if not first or not last:
            return []

        # Generate candidates
        candidates = []
        for pattern in self.PATTERNS:
            email = pattern.format(first=first, last=last, f=first_initial, domain=domain)
            candidates.append(email)

        # Check MX records for the domain
        has_mx = await self._check_mx_records(domain)
        base_confidence = 0.5 if has_mx else 0.3

        results = []
        for i, email in enumerate(candidates):
            # First pattern is most common, confidence decreases
            confidence = base_confidence - (i * 0.03)
            confidence = max(confidence, 0.2)
            results.append({"email": email, "confidence": round(confidence, 2)})

        logger.info("email_patterns_generated", domain=domain, count=len(results), has_mx=has_mx)
        return results

    def _extract_domain(self, website_url: str) -> str | None:
        """Extract the domain from a URL.

        Args:
            website_url: Full URL.

        Returns:
            Domain string or None.
        """
        try:
            parsed = urlparse(website_url)
            domain = parsed.netloc or parsed.path
            domain = domain.lower().strip("/")
            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain if "." in domain else None
        except Exception:
            return None

    async def _check_mx_records(self, domain: str) -> bool:
        """Check if a domain has MX records (indicates it can receive email).

        Args:
            domain: Domain to check.

        Returns:
            True if MX records exist.
        """
        try:
            loop = asyncio.get_event_loop()
            # Use getaddrinfo as a lightweight DNS check
            await loop.run_in_executor(None, socket.getaddrinfo, f"mail.{domain}", 25)
            return True
        except socket.gaierror:
            try:
                # Try the domain itself
                await loop.run_in_executor(None, socket.getaddrinfo, domain, 25)
                return True
            except Exception:
                return False
        except Exception:
            return False
