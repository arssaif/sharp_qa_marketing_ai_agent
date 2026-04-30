-- SharpQA Sales Agent — SQLite schema with WAL mode and FTS5

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- Leads: companies discovered from sourcers
CREATE TABLE IF NOT EXISTS leads (
    lead_id              TEXT PRIMARY KEY,
    company_name         TEXT NOT NULL,
    website_url          TEXT NOT NULL UNIQUE,
    source_platform      TEXT NOT NULL,
    source_reference_id  TEXT,
    funding_stage        TEXT,
    team_size_range      TEXT,
    industry_tags        TEXT,  -- JSON array
    country_code         TEXT,
    short_description    TEXT,
    discovered_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_analyzed_at     TIMESTAMP,
    lead_status          TEXT DEFAULT 'new',
    priority_score       REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(lead_status);
CREATE INDEX IF NOT EXISTS idx_leads_priority ON leads(priority_score DESC);

-- Contacts: people found during enrichment
CREATE TABLE IF NOT EXISTS contacts (
    contact_id           TEXT PRIMARY KEY,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    full_name            TEXT,
    job_title            TEXT,
    email_address        TEXT,
    email_confidence     REAL,
    linkedin_url         TEXT,
    twitter_handle       TEXT,
    is_primary_contact   BOOLEAN DEFAULT 0,
    discovered_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_contacts_lead ON contacts(lead_id);

-- Tech stack detections
CREATE TABLE IF NOT EXISTS tech_stacks (
    stack_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    category             TEXT,
    technology_name      TEXT,
    detection_confidence REAL
);
CREATE INDEX IF NOT EXISTS idx_tech_stacks_lead ON tech_stacks(lead_id);

-- Findings: one row per issue discovered
CREATE TABLE IF NOT EXISTS findings (
    finding_id           TEXT PRIMARY KEY,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    finding_category     TEXT NOT NULL,
    finding_title        TEXT NOT NULL,
    finding_description  TEXT,
    severity_level       TEXT,
    business_impact      TEXT,
    evidence_json        TEXT,
    page_url             TEXT,
    tool_source          TEXT,
    detected_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_findings_lead ON findings(lead_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity_level);

-- Email drafts
CREATE TABLE IF NOT EXISTS email_drafts (
    draft_id             TEXT PRIMARY KEY,
    lead_id              TEXT NOT NULL REFERENCES leads(lead_id) ON DELETE CASCADE,
    contact_id           TEXT REFERENCES contacts(contact_id),
    subject_line         TEXT NOT NULL,
    email_body           TEXT NOT NULL,
    tone_variant         TEXT,
    findings_referenced  TEXT,  -- JSON array of finding_ids
    generation_model     TEXT,
    draft_status         TEXT DEFAULT 'pending_review',
    human_edited_body    TEXT,
    operator_notes       TEXT,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at          TIMESTAMP,
    sent_at              TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_drafts_status ON email_drafts(draft_status);
CREATE INDEX IF NOT EXISTS idx_drafts_lead ON email_drafts(lead_id);

-- Pipeline runs for observability
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id               TEXT PRIMARY KEY,
    stage_name           TEXT NOT NULL,
    started_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at         TIMESTAMP,
    run_status           TEXT DEFAULT 'running',
    leads_processed      INTEGER DEFAULT 0,
    error_message        TEXT,
    run_metadata_json    TEXT
);

-- FTS5 full-text search over leads
CREATE VIRTUAL TABLE IF NOT EXISTS leads_fts USING fts5(
    company_name, short_description, content='leads', content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS leads_fts_insert AFTER INSERT ON leads BEGIN
    INSERT INTO leads_fts(rowid, company_name, short_description)
    VALUES (NEW.rowid, NEW.company_name, NEW.short_description);
END;

CREATE TRIGGER IF NOT EXISTS leads_fts_delete AFTER DELETE ON leads BEGIN
    INSERT INTO leads_fts(leads_fts, rowid, company_name, short_description)
    VALUES ('delete', OLD.rowid, OLD.company_name, OLD.short_description);
END;

CREATE TRIGGER IF NOT EXISTS leads_fts_update AFTER UPDATE ON leads BEGIN
    INSERT INTO leads_fts(leads_fts, rowid, company_name, short_description)
    VALUES ('delete', OLD.rowid, OLD.company_name, OLD.short_description);
    INSERT INTO leads_fts(rowid, company_name, short_description)
    VALUES (NEW.rowid, NEW.company_name, NEW.short_description);
END;
