"""Shared pytest fixtures for the SharpQA test suite."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from sharpqa_agent.core.database import initialize_database


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Create a temporary SQLite database with the full schema applied.

    Returns:
        Path string to the temporary database file.
    """
    db_path = str(tmp_path / "test.db")
    initialize_database(db_path)
    return db_path


@pytest.fixture
def tmp_db_connection(tmp_db_path: str) -> sqlite3.Connection:
    """Provide a synchronous connection to the temporary test database.

    Returns:
        A configured sqlite3.Connection.
    """
    conn = sqlite3.connect(tmp_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@pytest.fixture
def sample_html_yc() -> str:
    """Sample HTML mimicking a YC companies listing page."""
    return """
    <html>
    <body>
    <div class="_company_i9oky_339">
        <a class="_company_i9oky_339" href="/companies/testco">
            <span class="_coName_i9oky_453">TestCo</span>
            <span class="_coDescription_i9oky_478">AI-powered testing platform</span>
        </a>
        <a href="https://testco.io" class="_website_i9oky_527" target="_blank">testco.io</a>
        <span class="_pillWrapper_i9oky_33">
            <span>S24</span>
            <span>San Francisco, CA</span>
        </span>
    </div>
    <div class="_company_i9oky_339">
        <a class="_company_i9oky_339" href="/companies/acmeinc">
            <span class="_coName_i9oky_453">AcmeInc</span>
            <span class="_coDescription_i9oky_478">Developer tools for QA</span>
        </a>
        <a href="https://acme.dev" class="_website_i9oky_527" target="_blank">acme.dev</a>
        <span class="_pillWrapper_i9oky_33">
            <span>W24</span>
            <span>New York, NY</span>
        </span>
    </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_html_about_page() -> str:
    """Sample HTML for an /about page with team member info."""
    return """
    <html>
    <body>
    <div class="team">
        <div class="team-member">
            <h3>Jane Smith</h3>
            <p class="title">CEO & Co-Founder</p>
            <a href="mailto:jane@testco.io">jane@testco.io</a>
            <a href="https://linkedin.com/in/janesmith">LinkedIn</a>
            <a href="https://twitter.com/janesmith">Twitter</a>
        </div>
        <div class="team-member">
            <h3>Bob Johnson</h3>
            <p class="title">CTO</p>
            <a href="mailto:bob@testco.io">bob@testco.io</a>
        </div>
    </div>
    </body>
    </html>
    """


@pytest.fixture
def tmp_templates_dir(tmp_path: Path) -> Path:
    """Create a temporary email templates directory with sample templates."""
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "template_001.md").write_text(
        "Subject: Test template\n\nHi {contact_name}, this is a test.", encoding="utf-8"
    )
    return templates_dir
