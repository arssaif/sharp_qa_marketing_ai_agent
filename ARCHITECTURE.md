# SharpQA Sales Agent — Architecture & Module Design

## Overview

SharpQA Sales Agent is a local-first pipeline that discovers funded startups, passively audits their websites for QA issues, enriches contact data, and generates personalized cold outreach emails for human review. Nothing auto-sends. Every email is approved manually.

**Stack:** Python 3.10+, SQLite + FTS5, ChromaDB, Ollama (local LLM), Playwright, Lighthouse CLI, axe-core, FastAPI, Streamlit, APScheduler.

---

## Layer Architecture

```
┌─────────────────────────────────────────────────────┐
│              Streamlit Dashboard (UI Layer)          │
│   Home · Leads · Findings · Drafts · Runs · Settings│
└────────────────────┬────────────────────────────────┘
                     │ httpx HTTP calls
┌────────────────────▼────────────────────────────────┐
│           FastAPI Orchestrator API (API Layer)       │
│         localhost:8000 — no external exposure        │
└────────────────────┬────────────────────────────────┘
                     │ direct async Python calls
┌────────────────────▼────────────────────────────────┐
│              Pipeline (Orchestration Layer)          │
│   source → enrich → analyze → prioritize → draft    │
└──┬──────────┬──────────┬────────────┬───────────────┘
   │          │          │            │
   ▼          ▼          ▼            ▼
Sourcers  Enrichers  Analyzers    Drafter
   │          │          │            │
   └──────────┴──────────┴────────────┘
                     │ read/write
         ┌───────────▼───────────┐
         │   SQLite Database     │
         │   (+ FTS5 index)      │
         └───────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   ChromaDB (RAG)      │   ← email templates + past successes
         └───────────────────────┘
                     │
         ┌───────────▼───────────┐
         │   Ollama (LLM)        │   ← localhost:11434
         └───────────────────────┘
```

---

## Module Breakdown

### 1. `config/` — Configuration Layer

| File | Purpose |
|------|---------|
| `settings.py` | `Settings` class via pydantic-settings. Reads `.env`. Single source of truth for all paths, ports, tokens, and tunable parameters. |
| `scoring_weights.yaml` | YAML config for the lead prioritizer. Weights for funding stage, team size, finding severity, and bonus signals. Edit without touching code. |
| `sources.yaml` | Enable/disable each sourcer and set daily rate limits per platform. |
| `email_templates/*.md` | 8 seed cold email templates (one per finding category). Embedded into ChromaDB on first run to seed the RAG retrieval. |

**How it connects:** Every module receives a `settings` object. The prioritizer loads `scoring_weights.yaml` directly. The sourcer registry reads `sources.yaml`. The drafter seeds ChromaDB from `email_templates/`.

---

### 2. `core/` — Foundation Layer

All other modules depend on core. Nothing in core depends on other modules.

| Module | Purpose |
|--------|---------|
| `models.py` | Pydantic v2 models for all entities: `Lead`, `Contact`, `TechStack`, `Finding`, `EmailDraft`, `PipelineRun`, `RawLead`. Enums for status, severity, category, tone. These are the data contracts between all layers. |
| `database.py` | SQLite connection manager (`sync_db`, `async_db` context managers). WAL mode + foreign keys. Full async CRUD functions for all tables. `initialize_database()` applies `schema.sql`. |
| `schema.sql` | DDL for all 6 tables + FTS5 virtual table + 3 sync triggers (INSERT/UPDATE/DELETE on `leads` keeps `leads_fts` current). |
| `exceptions.py` | Exception hierarchy rooted at `SharpQAError`. Specific subclasses: `DatabaseError`, `SourcerError`, `AnalyzerError`, `EnricherError`, `DrafterError`, `LLMError`, `VectorStoreError`. |
| `logging_setup.py` | structlog configured for dual output: JSON to rotating file (`data/logs/agent.log`) and human-readable to stderr. Every module calls `get_logger(__name__)`. |
| `llm_client.py` | `OllamaClient`: async wrapper around Ollama REST API. `generate()` for single-shot completion, `generate_streaming()` for chunk-by-chunk, `is_available()` for health check, `pull_model()` for first-run setup. |
| `embeddings.py` | sentence-transformers wrapper with module-level model cache. `embed_texts(list)` and `embed_single(str)` return float vectors. |
| `vector_store.py` | ChromaDB wrapper with client cache. `add_documents()`, `query_similar()`, `seed_templates_from_directory()`. Uses cosine similarity. |

**Data flow in core:** `database.py` takes Pydantic models and serializes them to/from SQLite. `llm_client.py` and `vector_store.py` are the two external service wrappers.

---

### 3. `sourcers/` — Lead Discovery Layer

**Purpose:** Discover funded startups from external platforms and insert them as `Lead` records with `status='new'`.

| Module | Purpose |
|--------|---------|
| `base_sourcer.py` | Abstract `BaseSourcer` with `source_name: str` and `fetch_new_leads(since, limit) -> list[RawLead]`. All sourcers implement this contract. |
| `yc_sourcer.py` | Playwright navigates `ycombinator.com/companies` filtered to recent batches (W24/S24/W25/S25). Scrolls to load JS-rendered content. Parses company cards via BeautifulSoup. Rate: 3s between requests. |
| `wellfound_sourcer.py` | Playwright with custom user-agent to bypass Cloudflare. Exponential backoff on 403s (up to 3 retries). Parses startup cards for name, description, funding stage, team size. |
| `producthunt_sourcer.py` | GraphQL API with Bearer token (free dev account). Filters by minimum upvotes. Extracts name, tagline, website, topics as industry tags. |
| `github_sourcer.py` | GitHub REST API search by topic + star count. Filters repos with a `homepage` field. Deduplicates by domain. Requires personal access token. |
| `sourcer_registry.py` | Reads `sources.yaml` and instantiates only enabled sourcers with their configured params. Returns `list[BaseSourcer]`. |

**How it connects:** `pipeline._run_source_stage()` calls `get_enabled_sourcers()` → iterates each sourcer → calls `fetch_new_leads()` → wraps `RawLead` into `Lead` → calls `database.insert_lead()`. Duplicate URLs are silently ignored (`INSERT OR IGNORE`).

---

### 4. `enrichers/` — Data Enrichment Layer

**Purpose:** Augment leads with contact info, detected technologies, social links, and guessed email addresses.

| Module | Purpose |
|--------|---------|
| `contact_enricher.py` | Playwright visits `/team`, `/about`, `/about-us`, `/contact`, `/people`, `/our-team`, `/leadership`. Strategy 1: finds structured team member cards via CSS class patterns. Strategy 2: regex-scans page text for email addresses. Scores and selects primary contact by role seniority (CEO/founder > CTO/VP > other). |
| `tech_stack_detector.py` | Plain httpx GET. 30+ technology detection rules (React, Vue, Next.js, Angular, Svelte, Bootstrap, Tailwind, WordPress, Shopify, Webflow, Google Analytics, Stripe, Cloudflare, Vercel, AWS, Sentry, etc.). Inspects response headers, script src attributes, and HTML patterns. Returns confidence scores per technology. |
| `social_handle_finder.py` | httpx GET homepage, regex-matches all `<a href>` links against patterns for Twitter/X, LinkedIn company, LinkedIn person, GitHub, Facebook. |
| `email_pattern_guesser.py` | When no email was scraped, generates 7 email format candidates (`first@domain`, `first.last@domain`, `f.last@domain`, etc.), validates MX records via DNS, assigns confidence 0.3–0.5. |

**How it connects:** `pipeline._run_enrich_stage()` fetches leads with `status='new'`, runs all four enrichers, writes results to `contacts` and `tech_stacks` tables, updates `lead_status='enriched'`. If no email is found via scraping, the email guesser runs on the primary contact.

---

### 5. `analyzers/` — Website Audit Layer

**Purpose:** Passively audit each lead's website and produce `Finding` records categorized by severity and business impact.

| Module | Purpose |
|--------|---------|
| `playwright_auditor.py` | Highest-value analyzer. Desktop + mobile Playwright sessions. Captures: console errors/warnings (capped 10), failed network requests, broken images (`naturalWidth===0`), broken external links (HEAD requests), mobile horizontal overflow. Saves screenshots to `data/screenshots/`. |
| `lighthouse_runner.py` | Shells out to `lighthouse <url> --output=json`. Extracts category scores < 0.5 as findings, plus individual failing audit items. Capped at 20 findings. |
| `axe_runner.py` | Playwright navigates to page, injects axe-core 4.9.1 from CDN, calls `axe.run()` via `page.evaluate()`. Maps violation impact levels to severity. WCAG AA violations elevated to HIGH. |
| `security_header_checker.py` | Plain httpx GET. Checks for 6 missing security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy. HTTP sites get a CRITICAL finding. |
| `finding_normalizer.py` | `normalize_finding()`: truncates fields, coerces enum values. `deduplicate_findings()`: removes duplicates by title+category+page, keeps highest severity. |
| `finding_severity.py` | Rules engine (not ML). `assess_business_impact()`: elevates findings on critical user flows (signup/checkout/login keywords) to CRITICAL; elevates homepage findings from MEDIUM to HIGH; generates human-readable `business_impact` text per category. |

**How it connects:** `pipeline._run_analyze_stage()` fetches `status='enriched'` leads, runs all 4 analyzers with per-analyzer error isolation (one failing doesn't block others), normalizes/deduplicates/assesses findings, writes to `findings` table, updates `lead_status='analyzed'`. Concurrency controlled via `asyncio.Semaphore(max_concurrent_analyzes)`.

---

### 6. `prioritizer/` — Scoring Layer

**Purpose:** Score each analyzed lead 0.0–1.0 to determine which get email drafts.

| Module | Purpose |
|--------|---------|
| `signals.py` | Five individual signal functions: `funding_stage_signal()`, `team_size_signal()`, `max_finding_severity_signal()`, `has_primary_contact_email_signal()`, `tech_stack_indicates_saas_signal()` (checks for SaaS-indicator techs like React, Stripe, Vercel). |
| `lead_scorer.py` | `LeadScorer`: loads `scoring_weights.yaml`. Computes weighted average of 3 base signals, adds additive bonus signals, caps final score at 1.0. Leads scoring above `min_priority_score_for_drafting` (default 0.6) enter the draft queue. |

**How it connects:** `pipeline._run_prioritize_stage()` fetches `status='analyzed'` leads, loads findings/contacts/tech stack for each, calls `scorer.score_lead()`, writes score to `leads.priority_score`.

---

### 7. `drafter/` — Email Generation Layer

**Purpose:** Generate personalized cold outreach emails using local LLM with RAG-retrieved examples.

| Module | Purpose |
|--------|---------|
| `rag_retriever.py` | `ensure_templates_seeded()` seeds ChromaDB from `config/email_templates/` on first run. `retrieve_similar_templates()` builds a semantic query from finding category + industry + funding stage and returns the top-N most similar past templates. |
| `prompt_builder.py` | Assembles the full LLM prompt. System prompt: rules (120 words max, one specific finding reference, soft CTA, no flattery, JSON output, operator name). User prompt: RAG examples, target company context, contact info, top finding with business impact, additional findings. Supports 3 tone variants. |
| `email_drafter.py` | `generate_draft()`: retrieve RAG → build prompt → call Ollama → parse JSON. `generate_all_tones()`: parallel generation for DIRECT/CONSULTATIVE/FRIENDLY via `asyncio.gather()`. `_parse_llm_response()`: tries JSON extraction, then "Subject:" pattern, then raw text fallback. |
| `tone_adjuster.py` | Helper returning available `ToneVariant` enum values. |
| `subject_line_generator.py` | `generate_fallback_subject()`: maps `FindingCategory` to short subject lines (<60 chars) for when LLM output is malformed. |

**How it connects:** `pipeline._run_draft_stage()` fetches analyzed leads above the priority threshold, instantiates `OllamaClient` + `RagRetriever` + `EmailDrafter`, calls `generate_draft()`, writes result to `email_drafts` table, updates `lead_status='drafted'`.

---

### 8. `exporter/` — Output Layer

| Module | Purpose |
|--------|---------|
| `excel_exporter.py` | openpyxl workbook with 14 columns: company, website, primary email, contact name, phone, LinkedIn, Twitter, top findings summary, improvements summary, business impact, draft subject, draft body, priority score, status. Dark blue header row, freeze panes, auto-sized columns. Output: `data/exports/SharpQA_leads_{timestamp}.xlsx`. |
| `csv_exporter.py` | Lightweight 9-column CSV alternative for simpler consumption. |

**How it connects:** Called from `orchestrator/api.py` (`POST /exports/excel`) and from the CLI `export` command. Reads from all database tables to assemble rows.

---

### 9. `orchestrator/` — Control Layer

| Module | Purpose |
|--------|---------|
| `pipeline.py` | `run_pipeline(stages, limit, settings)`: chains stages sequentially. Creates `PipelineRun` record. Each stage is isolated — one failing does not abort the run. Five private stage functions each reading from DB, running the appropriate modules, writing results back. |
| `scheduler.py` | `BackgroundScheduler` (APScheduler). `setup_nightly_sourcing()` registers a `CronTrigger` job that runs source+enrich at the configured hour. Started in the API lifespan. |
| `task_state.py` | In-memory stores: `_active_runs: dict[str, PipelineRun]` and `_run_logs: dict[str, list[str]]`. Functions: `create_run()`, `update_run()`, `add_log()`, `get_run()`, `get_run_logs()`. Shared state between the pipeline background task and the SSE streaming endpoint. |
| `api.py` | FastAPI application. Lifespan: setup_logging → ensure_directories → setup_nightly_sourcing. Endpoints: `POST /runs/start`, `GET /runs/{id}`, `GET /runs/{id}/stream` (SSE), `GET /leads`, `GET /leads/{id}`, findings/contacts/tech-stack sub-resources, `PATCH /drafts/{id}`, `POST /exports/excel`, `GET /stats`. Bound to `127.0.0.1` only. |

**How it connects:** The API bridges Streamlit and the pipeline. `POST /runs/start` triggers `run_pipeline()` as an async background task. `GET /runs/{id}/stream` exposes live logs from `task_state` via SSE. The scheduler runs the pipeline independently of the API on a cron schedule.

---

### 10. `dashboard/` — User Interface Layer

**Purpose:** Streamlit multi-page app for reviewing all data and taking action on drafts.

| Page / Component | Purpose |
|------------------|---------|
| `app.py` (Home) | Password gate (if configured), 5-metric KPI row (total leads, findings/lead, drafts generated/approved, approval rate), three quick-action buttons. |
| `1_Leads.py` | Filter bar (status, source, score slider, text search). Dataframe table with link column. Click-to-drill: shows contact details and detected tech stack. |
| `2_Findings.py` | Company selector. Finding cards with severity emoji badge. Evidence JSON expander. Desktop + mobile screenshot display. |
| `3_Drafts.py` | **Main workspace.** Two-column layout: left = lead context + findings, right = editable subject/body text areas. Approve / Reject / Copy-to-clipboard buttons — each PATCHes the API and reruns. |
| `4_Runs.py` | Stage multiselect + limit input to start new run. Active run status indicator. Run history list. |
| `5_Settings.py` | sources.yaml per-source checkboxes. scoring_weights.yaml raw YAML editor. Email template viewer + add-new form. Current settings JSON display. |
| `components/` | Reusable Streamlit fragments: `lead_table.py`, `finding_card.py`, `email_editor.py`, `metrics_panel.py`. |

**How it connects:** Every page calls `httpx.get/post/patch()` to the FastAPI server at `http://127.0.0.1:{api_port}`. No direct database access from the dashboard — everything goes through the API.

---

## Data Flow Summary

```
Sourcers         → leads table (status: new)
Enrichers        → contacts, tech_stacks tables (status: enriched)
Analyzers        → findings table (status: analyzed)
Prioritizer      → leads.priority_score updated
Drafter          → email_drafts table (status: drafted)
Dashboard review → email_drafts.draft_status = approved
Export           → data/exports/SharpQA_leads_{timestamp}.xlsx
```

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| No LangChain | Plain async Python is easier to debug, profile, and modify without framework magic. |
| SQLite WAL mode | Allows concurrent reads during writes; FTS5 sync triggers maintain the search index automatically without application-level bookkeeping. |
| In-process ChromaDB | No separate vector DB server process — simplifies deployment to a single machine. |
| Per-analyzer error isolation | If Lighthouse is not installed, Playwright/axe/security checks still run; one broken tool doesn't cancel the audit. |
| Human-in-the-loop | `email_drafts.draft_status` starts as `pending_review`. No email is sent without explicit approval in the dashboard. |
| Settings in one place | `config/settings.py` with pydantic-settings; all modules receive the settings object rather than reading env vars directly. |
| Local-only LLM | Ollama runs entirely on-device — no API keys, no data sent to third parties, no per-token cost. |
