"""Tests for the database CRUD operations."""

from __future__ import annotations

import pytest

from sharpqa_agent.core.database import (
    get_dashboard_stats,
    get_leads,
    insert_lead,
    update_lead_priority,
    update_lead_status,
)
from sharpqa_agent.core.models import Lead


@pytest.mark.asyncio
async def test_insert_and_retrieve_lead(tmp_db_path: str) -> None:
    """Insert a lead and retrieve it."""
    lead = Lead(
        company_name="TestCo",
        website_url="https://testco.io",
        source_platform="yc",
    )
    await insert_lead(tmp_db_path, lead)

    leads = await get_leads(tmp_db_path)
    assert len(leads) == 1
    assert leads[0].company_name == "TestCo"
    assert leads[0].website_url == "https://testco.io"


@pytest.mark.asyncio
async def test_duplicate_url_ignored(tmp_db_path: str) -> None:
    """Inserting a lead with the same URL should be silently ignored."""
    lead1 = Lead(company_name="TestCo", website_url="https://testco.io", source_platform="yc")
    lead2 = Lead(company_name="TestCo Copy", website_url="https://testco.io", source_platform="wellfound")

    await insert_lead(tmp_db_path, lead1)
    await insert_lead(tmp_db_path, lead2)

    leads = await get_leads(tmp_db_path)
    assert len(leads) == 1
    assert leads[0].company_name == "TestCo"  # First one wins


@pytest.mark.asyncio
async def test_update_lead_status(tmp_db_path: str) -> None:
    """Lead status should be updatable."""
    lead = Lead(company_name="TestCo", website_url="https://testco.io", source_platform="yc")
    await insert_lead(tmp_db_path, lead)

    await update_lead_status(tmp_db_path, lead.lead_id, "enriched")

    leads = await get_leads(tmp_db_path, status="enriched")
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_update_lead_priority(tmp_db_path: str) -> None:
    """Lead priority score should be updatable."""
    lead = Lead(company_name="TestCo", website_url="https://testco.io", source_platform="yc")
    await insert_lead(tmp_db_path, lead)

    await update_lead_priority(tmp_db_path, lead.lead_id, 0.85)

    leads = await get_leads(tmp_db_path, min_score=0.8)
    assert len(leads) == 1
    assert leads[0].priority_score == 0.85


@pytest.mark.asyncio
async def test_filter_leads_by_source(tmp_db_path: str) -> None:
    """Leads should be filterable by source platform."""
    await insert_lead(tmp_db_path, Lead(company_name="A", website_url="https://a.com", source_platform="yc"))
    await insert_lead(tmp_db_path, Lead(company_name="B", website_url="https://b.com", source_platform="wellfound"))

    yc_leads = await get_leads(tmp_db_path, source="yc")
    assert len(yc_leads) == 1
    assert yc_leads[0].company_name == "A"


@pytest.mark.asyncio
async def test_dashboard_stats_empty_db(tmp_db_path: str) -> None:
    """Dashboard stats on empty DB should return zeros."""
    stats = await get_dashboard_stats(tmp_db_path)
    assert stats["total_leads"] == 0
    assert stats["drafts_generated"] == 0
