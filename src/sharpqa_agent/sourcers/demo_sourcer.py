"""Demo lead sourcer — provides hardcoded leads for testing and demonstrations."""

from __future__ import annotations

import asyncio
from datetime import datetime

from sharpqa_agent.core.models import RawLead
from sharpqa_agent.sourcers.base_sourcer import BaseSourcer


class DemoSourcer(BaseSourcer):
    """Provide hardcoded leads for testing without hitting rate limits or captchas."""

    source_name = "demo"

    async def fetch_new_leads(self, since: datetime | None = None, limit: int = 50) -> list[RawLead]:
        """Return a few hardcoded SaaS startups for demo purposes."""
        await asyncio.sleep(1)  # Simulate network request

        leads = [
            RawLead(
                company_name="Cal.com",
                website_url="https://cal.com",
                source_platform="demo",
                source_reference_id="cal-com",
                funding_stage="series_a",
                team_size_range="11-50",
                industry_tags=["scheduling", "saas", "open-source"],
                country_code="US",
                short_description="Open source scheduling infrastructure.",
            ),
            RawLead(
                company_name="Dub.co",
                website_url="https://dub.co",
                source_platform="demo",
                source_reference_id="dub-co",
                funding_stage="seed",
                team_size_range="1-10",
                industry_tags=["marketing", "saas", "link-management"],
                country_code="US",
                short_description="Open source link management tool for modern marketing teams.",
            ),
            RawLead(
                company_name="Resend",
                website_url="https://resend.com",
                source_platform="demo",
                source_reference_id="resend",
                funding_stage="series_a",
                team_size_range="11-50",
                industry_tags=["email", "developer-tools", "api"],
                country_code="US",
                short_description="Email for developers. The best API to reach humans instead of spam folders.",
            )
        ]
        
        return leads[:limit]

    async def healthcheck(self) -> bool:
        return True
