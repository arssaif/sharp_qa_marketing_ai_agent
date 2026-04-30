"""Product Hunt lead sourcer — uses the free GraphQL API for recently launched products."""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from sharpqa_agent.core.exceptions import SourcerError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import RawLead
from sharpqa_agent.sourcers.base_sourcer import BaseSourcer

logger = get_logger(__name__)

PH_API_URL = "https://api.producthunt.com/v2/api/graphql"

POSTS_QUERY = """
query($postedAfter: DateTime, $first: Int) {
  posts(order: NEWEST, postedAfter: $postedAfter, first: $first) {
    edges {
      node {
        id
        name
        tagline
        url
        website
        votesCount
        topics {
          edges {
            node {
              name
            }
          }
        }
        makers {
          name
          headline
        }
      }
    }
  }
}
"""


class ProductHuntSourcer(BaseSourcer):
    """Discover recently launched products from Product Hunt.

    Uses the free GraphQL API. Requires a developer token (free, no card).
    """

    source_name = "producthunt"

    def __init__(self, api_token: str = "", min_upvotes: int = 50) -> None:
        self.api_token = api_token
        self.min_upvotes = min_upvotes

    async def fetch_new_leads(self, since: datetime | None = None, limit: int = 50) -> list[RawLead]:
        """Fetch recently launched products from Product Hunt.

        Args:
            since: Only fetch products launched after this timestamp.
            limit: Maximum number of leads to return.

        Returns:
            List of RawLead models.

        Raises:
            SourcerError: If the API request fails.
        """
        if not self.api_token:
            logger.warning("producthunt_no_token", msg="Skipping — no PRODUCT_HUNT_TOKEN configured")
            return []

        posted_after = since or (datetime.utcnow() - timedelta(days=7))

        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        variables = {
            "postedAfter": posted_after.isoformat(),
            "first": min(limit * 2, 100),  # fetch extra to filter by upvotes
        }

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    PH_API_URL,
                    headers=headers,
                    json={"query": POSTS_QUERY, "variables": variables},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as error:
            raise SourcerError(f"Product Hunt API returned {error.response.status_code}") from error
        except Exception as error:
            raise SourcerError(f"Product Hunt API request failed: {error}") from error

        return self._parse_response(data, limit)

    def _parse_response(self, data: dict, limit: int) -> list[RawLead]:
        """Parse the GraphQL response into RawLead models.

        Args:
            data: Parsed JSON response from the API.
            limit: Max leads to return.

        Returns:
            List of RawLead models filtered by minimum upvotes.
        """
        leads: list[RawLead] = []
        posts = data.get("data", {}).get("posts", {}).get("edges", [])

        for edge in posts:
            if len(leads) >= limit:
                break

            node = edge.get("node", {})
            votes = node.get("votesCount", 0)

            if votes < self.min_upvotes:
                continue

            website = node.get("website", "") or node.get("url", "")
            if not website or "producthunt.com" in website:
                continue

            # Normalize URL
            if not website.startswith("http"):
                website = f"https://{website}"

            # Extract topics as industry tags
            topics = []
            for topic_edge in node.get("topics", {}).get("edges", []):
                topic_name = topic_edge.get("node", {}).get("name", "")
                if topic_name:
                    topics.append(topic_name)

            leads.append(RawLead(
                company_name=node.get("name", "Unknown"),
                website_url=website,
                source_platform="producthunt",
                source_reference_id=str(node.get("id", "")),
                funding_stage="pre_seed",  # PH launches are typically early stage
                short_description=node.get("tagline", ""),
                industry_tags=topics,
            ))

        logger.info("producthunt_sourcer_complete", leads_found=len(leads))
        return leads

    async def healthcheck(self) -> bool:
        """Check if Product Hunt API is reachable."""
        if not self.api_token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    PH_API_URL,
                    headers={"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"},
                    json={"query": "{ viewer { id } }"},
                )
                return response.status_code == 200
        except Exception:
            return False
