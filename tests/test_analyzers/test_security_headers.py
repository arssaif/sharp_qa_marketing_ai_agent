"""Tests for the security header checker — uses respx to mock HTTP responses."""

from __future__ import annotations

import pytest
import respx
import httpx

from sharpqa_agent.analyzers.security_header_checker import SecurityHeaderChecker


@pytest.fixture
def checker() -> SecurityHeaderChecker:
    return SecurityHeaderChecker(timeout=5)


@pytest.mark.asyncio
async def test_missing_all_headers(checker: SecurityHeaderChecker) -> None:
    """Site with no security headers should produce multiple findings."""
    with respx.mock:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(200, headers={"content-type": "text/html"})
        )
        findings = await checker.analyze("test-lead-id", "https://example.com")

    assert len(findings) >= 4  # At least CSP, HSTS, X-Frame-Options, X-Content-Type-Options
    categories = {f.finding_category.value for f in findings}
    assert "security_header" in categories


@pytest.mark.asyncio
async def test_all_headers_present(checker: SecurityHeaderChecker) -> None:
    """Site with all security headers should produce no findings."""
    with respx.mock:
        respx.get("https://secure.example.com").mock(
            return_value=httpx.Response(200, headers={
                "content-type": "text/html",
                "strict-transport-security": "max-age=31536000",
                "content-security-policy": "default-src 'self'",
                "x-frame-options": "DENY",
                "x-content-type-options": "nosniff",
                "referrer-policy": "strict-origin",
                "permissions-policy": "camera=()",
            })
        )
        findings = await checker.analyze("test-lead-id", "https://secure.example.com")

    assert len(findings) == 0


@pytest.mark.asyncio
async def test_http_site_flagged(checker: SecurityHeaderChecker) -> None:
    """HTTP (non-HTTPS) site should produce a critical finding."""
    with respx.mock:
        respx.get("http://insecure.example.com").mock(
            return_value=httpx.Response(200, headers={"content-type": "text/html"})
        )
        findings = await checker.analyze("test-lead-id", "http://insecure.example.com")

    https_findings = [f for f in findings if "HTTPS" in f.finding_title]
    assert len(https_findings) == 1
    assert https_findings[0].severity_level.value == "critical"
