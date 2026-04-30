"""SQLite database connection manager with WAL mode, migrations, and async support."""

from __future__ import annotations

import json
import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator

import aiosqlite

from sharpqa_agent.core.exceptions import DatabaseError
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import (
    Contact,
    EmailDraft,
    Finding,
    Lead,
    PipelineRun,
    TechStack,
)

logger = get_logger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_sync_connection(db_path: str | Path) -> sqlite3.Connection:
    """Create a synchronous SQLite connection with WAL mode and foreign keys.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A configured sqlite3.Connection.
    """
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def sync_db(db_path: str | Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for synchronous database access.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        A configured sqlite3.Connection that auto-commits on success.
    """
    connection = get_sync_connection(db_path)
    try:
        yield connection
        connection.commit()
    except Exception as error:
        connection.rollback()
        raise DatabaseError(f"Database operation failed: {error}") from error
    finally:
        connection.close()


@asynccontextmanager
async def async_db(db_path: str | Path) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Context manager for asynchronous database access.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        A configured aiosqlite.Connection that auto-commits on success.
    """
    connection = await aiosqlite.connect(str(db_path))
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA journal_mode = WAL")
    await connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        await connection.commit()
    except Exception as error:
        await connection.rollback()
        raise DatabaseError(f"Database operation failed: {error}") from error
    finally:
        await connection.close()


def initialize_database(db_path: str | Path) -> None:
    """Create the database and apply the schema DDL.

    Args:
        db_path: Path to the SQLite database file. Parent directories are created.

    Raises:
        DatabaseError: If schema application fails.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    try:
        connection = sqlite3.connect(str(db_path))
        connection.executescript(schema_sql)
        connection.close()
        logger.info("database_initialized", path=str(db_path))
    except sqlite3.Error as error:
        raise DatabaseError(f"Failed to initialize database: {error}") from error


# --- CRUD helpers ---

async def insert_lead(db_path: str | Path, lead: Lead) -> None:
    """Insert a lead into the database, skipping if website_url already exists.

    Args:
        db_path: Path to the SQLite database file.
        lead: The Lead model to insert.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """INSERT OR IGNORE INTO leads
               (lead_id, company_name, website_url, source_platform, source_reference_id,
                funding_stage, team_size_range, industry_tags, country_code, short_description,
                lead_status, priority_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead.lead_id, lead.company_name, lead.website_url, lead.source_platform,
                lead.source_reference_id, lead.funding_stage, lead.team_size_range,
                json.dumps(lead.industry_tags), lead.country_code, lead.short_description,
                lead.lead_status.value, lead.priority_score,
            ),
        )


async def insert_contact(db_path: str | Path, contact: Contact) -> None:
    """Insert a contact into the database.

    Args:
        db_path: Path to the SQLite database file.
        contact: The Contact model to insert.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """INSERT OR IGNORE INTO contacts
               (contact_id, lead_id, full_name, job_title, email_address, email_confidence,
                linkedin_url, twitter_handle, is_primary_contact)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                contact.contact_id, contact.lead_id, contact.full_name, contact.job_title,
                contact.email_address, contact.email_confidence, contact.linkedin_url,
                contact.twitter_handle, int(contact.is_primary_contact),
            ),
        )


async def insert_tech_stack(db_path: str | Path, tech: TechStack) -> None:
    """Insert a tech stack detection.

    Args:
        db_path: Path to the SQLite database file.
        tech: The TechStack model to insert.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """INSERT INTO tech_stacks (lead_id, category, technology_name, detection_confidence)
               VALUES (?, ?, ?, ?)""",
            (tech.lead_id, tech.category, tech.technology_name, tech.detection_confidence),
        )


async def insert_finding(db_path: str | Path, finding: Finding) -> None:
    """Insert a finding into the database.

    Args:
        db_path: Path to the SQLite database file.
        finding: The Finding model to insert.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """INSERT OR IGNORE INTO findings
               (finding_id, lead_id, finding_category, finding_title, finding_description,
                severity_level, business_impact, evidence_json, page_url, tool_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                finding.finding_id, finding.lead_id, finding.finding_category.value,
                finding.finding_title, finding.finding_description, finding.severity_level.value,
                finding.business_impact, finding.evidence_json, finding.page_url, finding.tool_source,
            ),
        )


async def insert_draft(db_path: str | Path, draft: EmailDraft) -> None:
    """Insert an email draft.

    Args:
        db_path: Path to the SQLite database file.
        draft: The EmailDraft model to insert.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """INSERT OR IGNORE INTO email_drafts
               (draft_id, lead_id, contact_id, subject_line, email_body, tone_variant,
                findings_referenced, generation_model, draft_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                draft.draft_id, draft.lead_id, draft.contact_id, draft.subject_line,
                draft.email_body, draft.tone_variant.value if draft.tone_variant else None,
                json.dumps(draft.findings_referenced), draft.generation_model,
                draft.draft_status.value,
            ),
        )


async def insert_pipeline_run(db_path: str | Path, run: PipelineRun) -> None:
    """Insert a pipeline run record.

    Args:
        db_path: Path to the SQLite database file.
        run: The PipelineRun model to insert.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """INSERT INTO pipeline_runs (run_id, stage_name, run_status, leads_processed)
               VALUES (?, ?, ?, ?)""",
            (run.run_id, run.stage_name, run.run_status.value, run.leads_processed),
        )


async def update_pipeline_run(
    db_path: str | Path,
    run_id: str,
    run_status: str,
    leads_processed: int = 0,
    error_message: str | None = None,
) -> None:
    """Update a pipeline run's status and completion time.

    Args:
        db_path: Path to the SQLite database file.
        run_id: The run ID to update.
        run_status: New status value.
        leads_processed: Number of leads processed.
        error_message: Error message if the run failed.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """UPDATE pipeline_runs
               SET run_status = ?, completed_at = CURRENT_TIMESTAMP,
                   leads_processed = ?, error_message = ?
               WHERE run_id = ?""",
            (run_status, leads_processed, error_message, run_id),
        )


async def get_leads(
    db_path: str | Path,
    status: str | None = None,
    min_score: float | None = None,
    source: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Lead]:
    """Query leads with optional filters.

    Args:
        db_path: Path to the SQLite database file.
        status: Filter by lead_status.
        min_score: Minimum priority_score.
        source: Filter by source_platform.
        limit: Max results.
        offset: Skip N results.

    Returns:
        List of Lead models.
    """
    conditions: list[str] = []
    params: list[object] = []
    if status:
        conditions.append("lead_status = ?")
        params.append(status)
    if min_score is not None:
        conditions.append("priority_score >= ?")
        params.append(min_score)
    if source:
        conditions.append("source_platform = ?")
        params.append(source)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM leads {where_clause} ORDER BY priority_score DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with async_db(db_path) as connection:
        cursor = await connection.execute(query, params)
        rows = await cursor.fetchall()
        return [Lead(**dict(row)) for row in rows]


async def get_lead_by_id(db_path: str | Path, lead_id: str) -> Lead | None:
    """Fetch a single lead by ID.

    Args:
        db_path: Path to the SQLite database file.
        lead_id: The lead's UUID.

    Returns:
        A Lead model or None if not found.
    """
    async with async_db(db_path) as connection:
        cursor = await connection.execute("SELECT * FROM leads WHERE lead_id = ?", (lead_id,))
        row = await cursor.fetchone()
        return Lead(**dict(row)) if row else None


async def get_findings_for_lead(db_path: str | Path, lead_id: str) -> list[Finding]:
    """Fetch all findings for a given lead.

    Args:
        db_path: Path to the SQLite database file.
        lead_id: The lead's UUID.

    Returns:
        List of Finding models ordered by severity.
    """
    severity_order = "CASE severity_level WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END"
    async with async_db(db_path) as connection:
        cursor = await connection.execute(
            f"SELECT * FROM findings WHERE lead_id = ? ORDER BY {severity_order}",
            (lead_id,),
        )
        rows = await cursor.fetchall()
        return [Finding(**dict(row)) for row in rows]


async def get_contacts_for_lead(db_path: str | Path, lead_id: str) -> list[Contact]:
    """Fetch all contacts for a given lead.

    Args:
        db_path: Path to the SQLite database file.
        lead_id: The lead's UUID.

    Returns:
        List of Contact models.
    """
    async with async_db(db_path) as connection:
        cursor = await connection.execute(
            "SELECT * FROM contacts WHERE lead_id = ? ORDER BY is_primary_contact DESC",
            (lead_id,),
        )
        rows = await cursor.fetchall()
        return [Contact(**dict(row)) for row in rows]


async def get_tech_stack_for_lead(db_path: str | Path, lead_id: str) -> list[TechStack]:
    """Fetch detected tech stack for a lead.

    Args:
        db_path: Path to the SQLite database file.
        lead_id: The lead's UUID.

    Returns:
        List of TechStack models.
    """
    async with async_db(db_path) as connection:
        cursor = await connection.execute(
            "SELECT * FROM tech_stacks WHERE lead_id = ?", (lead_id,)
        )
        rows = await cursor.fetchall()
        return [TechStack(**dict(row)) for row in rows]


async def get_drafts(
    db_path: str | Path,
    status: str | None = None,
    lead_id: str | None = None,
    limit: int = 100,
) -> list[EmailDraft]:
    """Query email drafts with optional filters.

    Args:
        db_path: Path to the SQLite database file.
        status: Filter by draft_status.
        lead_id: Filter by lead_id.
        limit: Max results.

    Returns:
        List of EmailDraft models.
    """
    conditions: list[str] = []
    params: list[object] = []
    if status:
        conditions.append("draft_status = ?")
        params.append(status)
    if lead_id:
        conditions.append("lead_id = ?")
        params.append(lead_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    query = f"SELECT * FROM email_drafts {where_clause} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    async with async_db(db_path) as connection:
        cursor = await connection.execute(query, params)
        rows = await cursor.fetchall()
        return [EmailDraft(**dict(row)) for row in rows]


async def update_draft_status(
    db_path: str | Path,
    draft_id: str,
    status: str,
    human_edited_body: str | None = None,
    operator_notes: str | None = None,
) -> None:
    """Update an email draft's status and optional edits.

    Args:
        db_path: Path to the SQLite database file.
        draft_id: The draft's UUID.
        status: New draft_status value.
        human_edited_body: Operator-edited email body.
        operator_notes: Notes from the operator.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            """UPDATE email_drafts
               SET draft_status = ?, human_edited_body = ?, operator_notes = ?,
                   reviewed_at = CURRENT_TIMESTAMP
               WHERE draft_id = ?""",
            (status, human_edited_body, operator_notes, draft_id),
        )


async def update_lead_status(db_path: str | Path, lead_id: str, status: str) -> None:
    """Update a lead's status.

    Args:
        db_path: Path to the SQLite database file.
        lead_id: The lead's UUID.
        status: New lead_status value.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            "UPDATE leads SET lead_status = ? WHERE lead_id = ?",
            (status, lead_id),
        )


async def update_lead_priority(db_path: str | Path, lead_id: str, score: float) -> None:
    """Update a lead's priority score.

    Args:
        db_path: Path to the SQLite database file.
        lead_id: The lead's UUID.
        score: New priority_score.
    """
    async with async_db(db_path) as connection:
        await connection.execute(
            "UPDATE leads SET priority_score = ? WHERE lead_id = ?",
            (score, lead_id),
        )


async def search_leads_fts(db_path: str | Path, query: str, limit: int = 20) -> list[Lead]:
    """Full-text search over leads.

    Args:
        db_path: Path to the SQLite database file.
        query: FTS5 search query.
        limit: Max results.

    Returns:
        List of matching Lead models.
    """
    async with async_db(db_path) as connection:
        cursor = await connection.execute(
            """SELECT leads.* FROM leads_fts
               JOIN leads ON leads.rowid = leads_fts.rowid
               WHERE leads_fts MATCH ? LIMIT ?""",
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [Lead(**dict(row)) for row in rows]


async def get_pipeline_runs(db_path: str | Path, limit: int = 50) -> list[PipelineRun]:
    """Get recent pipeline runs.

    Args:
        db_path: Path to the SQLite database file.
        limit: Max results.

    Returns:
        List of PipelineRun models.
    """
    async with async_db(db_path) as connection:
        cursor = await connection.execute(
            "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [PipelineRun(**dict(row)) for row in rows]


async def get_dashboard_stats(db_path: str | Path) -> dict:
    """Get aggregate stats for the dashboard.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        Dictionary with total_leads, findings_per_lead_avg, drafts_generated,
        drafts_approved, approval_rate.
    """
    async with async_db(db_path) as connection:
        total = await (await connection.execute("SELECT COUNT(*) FROM leads")).fetchone()
        findings_count = await (await connection.execute("SELECT COUNT(*) FROM findings")).fetchone()
        drafts_total = await (await connection.execute("SELECT COUNT(*) FROM email_drafts")).fetchone()
        drafts_approved = await (
            await connection.execute("SELECT COUNT(*) FROM email_drafts WHERE draft_status = 'approved'")
        ).fetchone()

        total_leads = total[0] if total else 0
        total_findings = findings_count[0] if findings_count else 0
        total_drafts = drafts_total[0] if drafts_total else 0
        approved = drafts_approved[0] if drafts_approved else 0

        return {
            "total_leads": total_leads,
            "findings_per_lead_avg": round(total_findings / max(total_leads, 1), 1),
            "drafts_generated": total_drafts,
            "drafts_approved": approved,
            "approval_rate": round(approved / max(total_drafts, 1) * 100, 1),
        }
