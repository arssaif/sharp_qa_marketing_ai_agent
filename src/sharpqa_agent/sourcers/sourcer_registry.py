"""Registry of all available sourcers — dynamically instantiates based on configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.sourcers.base_sourcer import BaseSourcer
from sharpqa_agent.sourcers.github_sourcer import GitHubSourcer
from sharpqa_agent.sourcers.producthunt_sourcer import ProductHuntSourcer
from sharpqa_agent.sourcers.wellfound_sourcer import WellfoundSourcer
from sharpqa_agent.sourcers.yc_sourcer import YCSourcer

logger = get_logger(__name__)


def load_sources_config(config_path: str | Path = "config/sources.yaml") -> dict:
    """Load the sources configuration YAML.

    Args:
        config_path: Path to the sources.yaml file.

    Returns:
        Parsed configuration dictionary.
    """
    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning("sources_config_missing", path=str(config_file))
        return {"sources": {}}

    with open(config_file, encoding="utf-8") as f:
        return yaml.safe_load(f) or {"sources": {}}


def get_enabled_sourcers(
    config_path: str | Path = "config/sources.yaml",
    github_token: str = "",
    producthunt_token: str = "",
    headless: bool = True,
) -> list[BaseSourcer]:
    """Create and return sourcer instances for all enabled sources.

    Args:
        config_path: Path to sources.yaml.
        github_token: GitHub personal access token.
        producthunt_token: Product Hunt developer token.
        headless: Whether Playwright runs in headless mode.

    Returns:
        List of configured sourcer instances.
    """
    config = load_sources_config(config_path)
    sources = config.get("sources", {})
    sourcers: list[BaseSourcer] = []

    if sources.get("yc", {}).get("enabled", False):
        yc_config = sources["yc"]
        sourcers.append(YCSourcer(
            rate_limit_seconds=yc_config.get("rate_limit_seconds", 3),
            headless=headless,
        ))

    if sources.get("wellfound", {}).get("enabled", False):
        wf_config = sources["wellfound"]
        sourcers.append(WellfoundSourcer(
            rate_limit_seconds=wf_config.get("rate_limit_seconds", 5),
            max_retries=wf_config.get("max_retries", 3),
            headless=headless,
        ))

    if sources.get("producthunt", {}).get("enabled", False):
        ph_config = sources["producthunt"]
        sourcers.append(ProductHuntSourcer(
            api_token=producthunt_token,
            min_upvotes=ph_config.get("min_upvotes", 50),
        ))

    if sources.get("github", {}).get("enabled", False):
        gh_config = sources["github"]
        sourcers.append(GitHubSourcer(
            token=github_token,
            min_stars=gh_config.get("min_stars", 100),
            topics=gh_config.get("topics", ["saas", "startup", "webapp"]),
        ))

    logger.info("sourcers_loaded", count=len(sourcers), names=[s.source_name for s in sourcers])
    return sourcers
