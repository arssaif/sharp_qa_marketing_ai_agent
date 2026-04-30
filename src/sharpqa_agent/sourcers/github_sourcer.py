"""GitHub lead sourcer — discovers startups via repo searches filtered by homepage field."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx

from sharpqa_agent.core.exceptions import SourcerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import RawLead
from sharpqa_agent.sourcers.base_sourcer import BaseSourcer

logger = get_logger(__name__)

GITHUB_API_URL = "https://api.github.com"


class GitHubSourcer(BaseSourcer):
    """Discover startups from GitHub by searching repos with homepage URLs.

    Uses the authenticated REST API (free personal token, 5000 req/hr).
    Searches repos by topic tags and star count, filters those with a
    homepage field, and derives company info from the homepage.
    """

    source_name = "github"

    def __init__(
        self,
        token: str = "",
        min_stars: int = 100,
        topics: list[str] | None = None,
    ) -> None:
        self.token = token
        self.min_stars = min_stars
        self.topics = topics or ["saas", "startup", "webapp"]

    async def fetch_new_leads(self, since: datetime | None = None, limit: int = 50) -> list[RawLead]:
        """Fetch leads from GitHub repo search.

        Args:
            since: Only consider repos pushed after this date.
            limit: Maximum number of leads to return.

        Returns:
            List of RawLead models.

        Raises:
            SourcerError: If the GitHub API request fails.
        """
        if not self.token:
            logger.warning("github_no_token", msg="Skipping — no GITHUB_PERSONAL_TOKEN configured")
            return []

        pushed_after = since or (datetime.utcnow() - timedelta(days=30))
        pushed_str = pushed_after.strftime("%Y-%m-%d")

        headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
        }

        leads: list[RawLead] = []
        seen_domains: set[str] = set()

        for topic in self.topics:
            if len(leads) >= limit:
                break

            query = f"topic:{topic} stars:>={self.min_stars} pushed:>={pushed_str}"

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(
                        f"{GITHUB_API_URL}/search/repositories",
                        headers=headers,
                        params={"q": query, "sort": "stars", "order": "desc", "per_page": 30},
                    )

                    if response.status_code == 403:
                        logger.warning("github_rate_limited")
                        break
                    response.raise_for_status()
                    data = response.json()

            except httpx.HTTPStatusError as error:
                raise SourcerError(f"GitHub API returned {error.response.status_code}") from error
            except Exception as error:
                raise SourcerError(f"GitHub API request failed: {error}") from error

            for repo in data.get("items", []):
                if len(leads) >= limit:
                    break

                homepage = repo.get("homepage", "")
                if not homepage or "github.io" in homepage:
                    continue

                # Normalize and deduplicate by domain
                if not homepage.startswith("http"):
                    homepage = f"https://{homepage}"

                domain = urlparse(homepage).netloc.lower()
                if domain in seen_domains or not domain:
                    continue
                seen_domains.add(domain)

                # Derive company name from repo owner or repo name
                owner = repo.get("owner", {})
                company_name = owner.get("login", repo.get("name", "Unknown"))

                # Use repo topics as industry tags
                topics = repo.get("topics", [])[:5]

                leads.append(RawLead(
                    company_name=company_name,
                    website_url=homepage,
                    source_platform="github",
                    source_reference_id=repo.get("full_name", ""),
                    short_description=repo.get("description", ""),
                    industry_tags=topics,
                ))

            # Rate limit between topic queries
            await asyncio.sleep(1)

        logger.info("github_sourcer_complete", leads_found=len(leads))
        return leads

    async def healthcheck(self) -> bool:
        """Check if GitHub API is reachable and token is valid."""
        if not self.token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    f"{GITHUB_API_URL}/rate_limit",
                    headers={"Authorization": f"token {self.token}"},
                )
                return response.status_code == 200
        except Exception:
            return False
