"""FastAPI application — localhost-only API for pipeline control and data access."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from config.settings import get_settings
from sharpqa_agent.core.database import (
    get_contacts_for_lead,
    get_dashboard_stats,
    get_drafts,
    get_findings_for_lead,
    get_lead_by_id,
    get_leads,
    get_pipeline_runs,
    get_tech_stack_for_lead,
    search_leads_fts,
    update_draft_status,
)
from sharpqa_agent.core.logging_setup import get_logger, setup_logging
from sharpqa_agent.orchestrator.pipeline import run_pipeline
from sharpqa_agent.orchestrator.scheduler import setup_nightly_sourcing, shutdown_scheduler
from sharpqa_agent.orchestrator.task_state import get_run, get_run_logs

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Application lifespan handler — setup and teardown."""
    setup_logging(settings.log_dir)
    settings.ensure_directories()
    setup_nightly_sourcing(settings)
    logger.info("api_started", port=settings.api_port)
    yield
    shutdown_scheduler()
    logger.info("api_shutdown")


app = FastAPI(
    title="SharpQA Sales Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # localhost only anyway
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request/Response models ---

class RunStartRequest(BaseModel):
    stages: list[str] = ["source", "enrich", "analyze", "prioritize", "draft"]
    limit: int = 10


class RunStartResponse(BaseModel):
    run_id: str


class DraftUpdateRequest(BaseModel):
    status: str
    human_edited_body: str | None = None
    operator_notes: str | None = None


class ExportRequest(BaseModel):
    lead_ids: list[str] = []


# --- Pipeline endpoints ---

@app.post("/runs/start", response_model=RunStartResponse)
async def start_run(request: RunStartRequest):
    """Start a pipeline run with the specified stages."""
    run_id = await run_pipeline(request.stages, request.limit, settings)
    return RunStartResponse(run_id=run_id)


@app.get("/runs/{run_id}")
async def get_run_status(run_id: str):
    """Get the status of a pipeline run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.model_dump()


@app.get("/runs/{run_id}/stream")
async def stream_run_logs(run_id: str):
    """Stream live log lines for a run via Server-Sent Events."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        last_index = 0
        while True:
            logs = get_run_logs(run_id)
            for i in range(last_index, len(logs)):
                yield {"data": logs[i]}
            last_index = len(logs)

            current_run = get_run(run_id)
            if current_run and current_run.run_status.value in ("success", "failed"):
                # Send remaining logs
                remaining = get_run_logs(run_id)
                for i in range(last_index, len(remaining)):
                    yield {"data": remaining[i]}
                yield {"data": f"[DONE] Status: {current_run.run_status.value}"}
                break

            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())


@app.get("/runs")
async def list_runs(limit: int = 50):
    """List recent pipeline runs."""
    runs = await get_pipeline_runs(settings.sqlite_db_path, limit=limit)
    return [r.model_dump() for r in runs]


# --- Lead endpoints ---

@app.get("/leads")
async def list_leads(
    status: str | None = None,
    min_score: float | None = None,
    source: str | None = None,
    search: str | None = None,
    limit: int = Query(default=100, le=500),
    offset: int = 0,
):
    """List leads with optional filters."""
    if search:
        leads = await search_leads_fts(settings.sqlite_db_path, search, limit=limit)
    else:
        leads = await get_leads(
            settings.sqlite_db_path,
            status=status,
            min_score=min_score,
            source=source,
            limit=limit,
            offset=offset,
        )
    return [l.model_dump() for l in leads]


@app.get("/leads/{lead_id}")
async def get_lead(lead_id: str):
    """Get a single lead by ID."""
    lead = await get_lead_by_id(settings.sqlite_db_path, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.model_dump()


@app.get("/leads/{lead_id}/findings")
async def get_lead_findings(lead_id: str):
    """Get all findings for a lead."""
    findings = await get_findings_for_lead(settings.sqlite_db_path, lead_id)
    return [f.model_dump() for f in findings]


@app.get("/leads/{lead_id}/contacts")
async def get_lead_contacts(lead_id: str):
    """Get all contacts for a lead."""
    contacts = await get_contacts_for_lead(settings.sqlite_db_path, lead_id)
    return [c.model_dump() for c in contacts]


@app.get("/leads/{lead_id}/tech-stack")
async def get_lead_tech_stack(lead_id: str):
    """Get detected tech stack for a lead."""
    stack = await get_tech_stack_for_lead(settings.sqlite_db_path, lead_id)
    return [s.model_dump() for s in stack]


# --- Draft endpoints ---

@app.get("/drafts")
async def list_drafts(
    status: str | None = None,
    lead_id: str | None = None,
    limit: int = 100,
):
    """List email drafts with optional filters."""
    drafts = await get_drafts(settings.sqlite_db_path, status=status, lead_id=lead_id, limit=limit)
    return [d.model_dump() for d in drafts]


@app.patch("/drafts/{draft_id}")
async def update_draft(draft_id: str, request: DraftUpdateRequest):
    """Update an email draft's status (approve/reject/edit)."""
    await update_draft_status(
        settings.sqlite_db_path,
        draft_id=draft_id,
        status=request.status,
        human_edited_body=request.human_edited_body,
        operator_notes=request.operator_notes,
    )
    return {"status": "updated"}


# --- Export endpoints ---

@app.post("/exports/excel")
async def export_excel(request: ExportRequest):
    """Export leads and drafts to Excel."""
    from sharpqa_agent.exporter.excel_exporter import export_leads_to_excel
    output_path = await export_leads_to_excel(settings, lead_ids=request.lead_ids or None)
    return {"path": str(output_path)}


# --- Dashboard stats ---

@app.get("/stats")
async def get_stats():
    """Get aggregate dashboard statistics."""
    return await get_dashboard_stats(settings.sqlite_db_path)
