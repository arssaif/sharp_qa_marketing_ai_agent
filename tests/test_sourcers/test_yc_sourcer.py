"""Tests for the YC sourcer — HTML parsing logic (no live network)."""

from __future__ import annotations

import pytest

from sharpqa_agent.sourcers.yc_sourcer import YCSourcer


class TestYCSourcerParsing:
    """Test the HTML parsing logic of the YC sourcer."""

    def setup_method(self) -> None:
        self.sourcer = YCSourcer()

    def test_parse_companies_page_extracts_leads(self, sample_html_yc: str) -> None:
        """Happy path: parse valid YC HTML and extract leads."""
        leads = self.sourcer._parse_companies_page(sample_html_yc, limit=50)

        assert len(leads) >= 1
        for lead in leads:
            assert lead.company_name
            assert lead.website_url.startswith("http")
            assert lead.source_platform == "yc"

    def test_parse_companies_page_respects_limit(self, sample_html_yc: str) -> None:
        """Parser stops at the limit."""
        leads = self.sourcer._parse_companies_page(sample_html_yc, limit=1)
        assert len(leads) <= 1

    def test_parse_companies_page_empty_html(self) -> None:
        """Empty HTML returns no leads."""
        leads = self.sourcer._parse_companies_page("<html><body></body></html>", limit=50)
        assert leads == []

    def test_parse_companies_page_malformed_html(self) -> None:
        """Malformed HTML doesn't crash."""
        leads = self.sourcer._parse_companies_page("<div><a href='/companies/'></a></div>", limit=50)
        # Should return empty or gracefully handle
        assert isinstance(leads, list)

    def test_parse_deduplicates_by_slug(self) -> None:
        """Same company slug appearing twice should be deduplicated."""
        html = """
        <html><body>
        <a href="/companies/testco"><span class="_coName_i9oky_453">TestCo</span></a>
        <a href="/companies/testco"><span class="_coName_i9oky_453">TestCo</span></a>
        </body></html>
        """
        leads = self.sourcer._parse_companies_page(html, limit=50)
        slugs = [l.source_reference_id for l in leads]
        assert len(slugs) == len(set(slugs))
