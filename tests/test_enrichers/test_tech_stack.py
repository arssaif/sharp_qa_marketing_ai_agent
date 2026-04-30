"""Tests for the tech stack detector — parsing logic with mocked HTTP."""

from __future__ import annotations

import pytest
import respx
import httpx

from sharpqa_agent.enrichers.tech_stack_detector import TechStackDetector


@pytest.fixture
def detector() -> TechStackDetector:
    return TechStackDetector(timeout=5)


@pytest.mark.asyncio
async def test_detects_react(detector: TechStackDetector) -> None:
    """Should detect React from script src and data attributes."""
    html = '<html><head><script src="https://cdn.example.com/react.min.js"></script></head><body data-reactroot></body></html>'
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text=html, headers={"content-type": "text/html"})
        )
        tech = await detector.detect("test-lead", "https://example.com")

    names = [t.technology_name for t in tech]
    assert "React" in names


@pytest.mark.asyncio
async def test_detects_cloudflare_from_headers(detector: TechStackDetector) -> None:
    """Should detect Cloudflare from response headers."""
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text="<html></html>", headers={
                "server": "cloudflare",
                "cf-ray": "abc123",
            })
        )
        tech = await detector.detect("test-lead", "https://example.com")

    names = [t.technology_name for t in tech]
    assert "Cloudflare" in names


@pytest.mark.asyncio
async def test_detects_nextjs(detector: TechStackDetector) -> None:
    """Should detect Next.js from __NEXT_DATA__ and x-powered-by header."""
    html = '<html><head></head><body><script id="__NEXT_DATA__">{}</script></body></html>'
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text=html, headers={"x-powered-by": "Next.js"})
        )
        tech = await detector.detect("test-lead", "https://example.com")

    names = [t.technology_name for t in tech]
    assert "Next.js" in names


@pytest.mark.asyncio
async def test_empty_html_returns_nothing(detector: TechStackDetector) -> None:
    """Empty HTML with no special headers should detect nothing."""
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, text="<html><body>Hello</body></html>")
        )
        tech = await detector.detect("test-lead", "https://example.com")

    assert len(tech) == 0
