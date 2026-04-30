"""Tests for the finding severity rules engine."""

from __future__ import annotations

from sharpqa_agent.analyzers.finding_severity import assess_business_impact
from sharpqa_agent.core.models import Finding, FindingCategory, SeverityLevel


def _make_finding(**kwargs) -> Finding:
    defaults = {
        "lead_id": "test-lead",
        "finding_category": FindingCategory.CONSOLE_ERROR,
        "finding_title": "Test finding",
        "severity_level": SeverityLevel.MEDIUM,
    }
    defaults.update(kwargs)
    return Finding(**defaults)


def test_critical_flow_elevates_severity() -> None:
    """Findings on signup/checkout pages should be elevated to critical."""
    finding = _make_finding(
        finding_title="JavaScript error on signup page",
        page_url="https://example.com/signup",
    )
    result = assess_business_impact(finding)
    assert result.severity_level == SeverityLevel.CRITICAL
    assert "CRITICAL PATH" in (result.business_impact or "")


def test_homepage_elevates_medium_to_high() -> None:
    """Medium findings on homepage should be elevated to high."""
    finding = _make_finding(
        finding_title="Broken image on homepage",
        page_url="https://example.com/",
        finding_description="homepage rendering issue",
    )
    result = assess_business_impact(finding)
    assert result.severity_level == SeverityLevel.HIGH


def test_accessibility_gets_impact_text() -> None:
    """Accessibility findings should get compliance-related impact text."""
    finding = _make_finding(
        finding_category=FindingCategory.ACCESSIBILITY,
        finding_title="Missing alt text on images",
        severity_level=SeverityLevel.HIGH,
    )
    result = assess_business_impact(finding)
    assert "assistive technology" in (result.business_impact or "").lower()


def test_performance_gets_conversion_impact() -> None:
    """Performance findings should mention conversion impact."""
    finding = _make_finding(
        finding_category=FindingCategory.PERFORMANCE,
        finding_title="Large Contentful Paint too slow",
        severity_level=SeverityLevel.HIGH,
    )
    result = assess_business_impact(finding)
    assert "conversion" in (result.business_impact or "").lower()


def test_low_severity_stays_low() -> None:
    """Low severity findings without special context should remain low."""
    finding = _make_finding(
        finding_title="Minor CSS warning",
        severity_level=SeverityLevel.LOW,
        page_url="https://example.com/blog/old-post",
    )
    result = assess_business_impact(finding)
    assert result.severity_level == SeverityLevel.LOW
