"""Pydantic v2 models for all entities crossing module boundaries."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# --- Enums ---

class LeadStatus(str, Enum):
    NEW = "new"
    ENRICHED = "enriched"
    ANALYZED = "analyzed"
    DRAFTED = "drafted"
    SENT = "sent"
    REPLIED = "replied"
    DEAD = "dead"


class FundingStage(str, Enum):
    PRE_SEED = "pre_seed"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    SERIES_C_PLUS = "series_c_plus"
    UNKNOWN = "unknown"


class FindingCategory(str, Enum):
    PERFORMANCE = "performance"
    ACCESSIBILITY = "accessibility"
    CONSOLE_ERROR = "console_error"
    BROKEN_RESOURCE = "broken_resource"
    SECURITY_HEADER = "security_header"
    SEO = "seo"
    MOBILE = "mobile"
    BEST_PRACTICES = "best_practices"


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DraftStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SENT = "sent"
    REPLIED = "replied"


class ToneVariant(str, Enum):
    DIRECT = "direct"
    CONSULTATIVE = "consultative"
    FRIENDLY = "friendly"


class RunStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


# --- Models ---

def _generate_uuid() -> str:
    return str(uuid4())


class RawLead(BaseModel):
    """A lead as initially scraped from a source, before database insertion."""
    company_name: str
    website_url: str
    source_platform: str
    source_reference_id: str | None = None
    funding_stage: str | None = None
    team_size_range: str | None = None
    industry_tags: list[str] = Field(default_factory=list)
    country_code: str | None = None
    short_description: str | None = None


class Lead(BaseModel):
    """A lead stored in the database."""
    lead_id: str = Field(default_factory=_generate_uuid)
    company_name: str
    website_url: str
    source_platform: str
    source_reference_id: str | None = None
    funding_stage: str | None = None
    team_size_range: str | None = None
    industry_tags: list[str] = Field(default_factory=list)
    country_code: str | None = None
    short_description: str | None = None
    discovered_at: datetime | None = None
    last_analyzed_at: datetime | None = None
    lead_status: LeadStatus = LeadStatus.NEW
    priority_score: float = 0.0

    @field_validator("industry_tags", mode="before")
    @classmethod
    def parse_industry_tags(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return [value] if value else []
        return value or []


class Contact(BaseModel):
    """A person associated with a lead."""
    contact_id: str = Field(default_factory=_generate_uuid)
    lead_id: str
    full_name: str | None = None
    job_title: str | None = None
    email_address: str | None = None
    email_confidence: float | None = None
    linkedin_url: str | None = None
    twitter_handle: str | None = None
    is_primary_contact: bool = False
    discovered_at: datetime | None = None


class TechStack(BaseModel):
    """A detected technology in a lead's website."""
    stack_id: int | None = None
    lead_id: str
    category: str | None = None
    technology_name: str | None = None
    detection_confidence: float | None = None


class Finding(BaseModel):
    """A normalized issue discovered during website analysis."""
    finding_id: str = Field(default_factory=_generate_uuid)
    lead_id: str
    finding_category: FindingCategory
    finding_title: str
    finding_description: str | None = None
    severity_level: SeverityLevel = SeverityLevel.LOW
    business_impact: str | None = None
    evidence_json: str | None = None
    page_url: str | None = None
    tool_source: str | None = None
    detected_at: datetime | None = None


class EmailDraft(BaseModel):
    """A generated cold outreach email draft."""
    draft_id: str = Field(default_factory=_generate_uuid)
    lead_id: str
    contact_id: str | None = None
    subject_line: str
    email_body: str
    tone_variant: ToneVariant | None = None
    findings_referenced: list[str] = Field(default_factory=list)
    generation_model: str | None = None
    draft_status: DraftStatus = DraftStatus.PENDING_REVIEW
    human_edited_body: str | None = None
    operator_notes: str | None = None
    created_at: datetime | None = None
    reviewed_at: datetime | None = None
    sent_at: datetime | None = None

    @field_validator("findings_referenced", mode="before")
    @classmethod
    def parse_findings_referenced(cls, value: Any) -> list[str]:
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return []
        return value or []


class PipelineRun(BaseModel):
    """Metadata for a pipeline execution run."""
    run_id: str = Field(default_factory=_generate_uuid)
    stage_name: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    run_status: RunStatus = RunStatus.RUNNING
    leads_processed: int = 0
    error_message: str | None = None
    run_metadata_json: str | None = None
