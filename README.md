# SharpQA Sales Agent

Local-first automation system that sources funded startups, performs passive website analysis to surface QA-relevant findings, enriches contact data, and drafts personalized cold outreach emails for human review.

## Core Principles

- **Local-first** — nothing leaves your machine except scraping requests and manual email sends
- **Human-in-the-loop** — every email is reviewed before send, no auto-send
- **Passive analysis only** — no probing, no pentesting, no legal gray areas
- **Modular pipeline** — each stage independently runnable and testable
- **Zero subscriptions** — 100% free and open source stack

## Architecture

```
Streamlit Dashboard → FastAPI API → Pipeline Stages → SQLite + ChromaDB
                                         ↓
                    Sourcers → Enrichers → Analyzers → Prioritizer → Drafter
```

**Pipeline stages:**
1. **Source** — discover startups from YC, Wellfound, Product Hunt, GitHub
2. **Enrich** — find contacts, tech stack, social handles, guess emails
3. **Analyze** — Playwright audit, Lighthouse, axe-core accessibility, security headers
4. **Prioritize** — score leads using configurable weights
5. **Draft** — generate personalized emails using local LLM + RAG

## Quick Start (Windows)

```powershell
# 1. Install prerequisites
#    - Python 3.10+ from python.org
#    - Ollama from ollama.com/download
#    - Node.js from nodejs.org (for Lighthouse)

# 2. Clone and setup
git clone <repo-url> && cd sharpqa-agent
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1

# 3. Pull the LLM model
ollama pull llama3.1:8b-instruct-q4_K_M

# 4. Start the agent
uv run python -m sharpqa_agent.main serve
```

## Quick Start (Linux/Mac)

```bash
git clone <repo-url> && cd sharpqa-agent
chmod +x scripts/install_unix.sh && ./scripts/install_unix.sh
ollama pull llama3.1:8b-instruct-q4_K_M
uv run python -m sharpqa_agent.main serve
```

## Quick Start (Docker)

```bash
docker-compose up -d
# Dashboard: http://localhost:8501
# API: http://localhost:8000/docs
```

## CLI Commands

```bash
SharpQA init          # Initialize database and verify dependencies
SharpQA run           # Run the full pipeline
SharpQA run -s source -s enrich -l 20   # Run specific stages
SharpQA serve         # Start API + Dashboard
SharpQA export        # Export to Excel
```

## Configuration

Copy `.env.example` to `.env` and adjust:

```bash
OPERATOR_NAME=Arslan
OPERATOR_COMPANY=SharpQA
OLLAMA_MODEL_NAME=llama3.1:8b-instruct-q4_K_M
```

Edit `config/scoring_weights.yaml` to tune lead prioritization.
Edit `config/sources.yaml` to enable/disable lead sources.
Add email templates to `config/email_templates/` for RAG improvement.

## Dashboard Pages

- **Home** — metrics overview and quick actions
- **Leads** — filterable table with drill-down to contacts and tech stack
- **Findings** — per-lead finding cards with severity badges and screenshots
- **Drafts** — the main workspace: review, edit, approve/reject emails
- **Runs** — pipeline execution history and live log streaming
- **Settings** — configure sources, weights, and templates

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Database | SQLite + FTS5 |
| Vector DB | ChromaDB (embedded) |
| LLM | Ollama + Llama 3.1 8B |
| Embeddings | sentence-transformers |
| Browser | Playwright |
| Site audit | Lighthouse CLI, axe-core |
| API | FastAPI |
| Dashboard | Streamlit |
| Scheduler | APScheduler |

## Testing

```bash
uv run pytest -v
uv run pytest --cov=sharpqa_agent
```

## Project Structure

```
src/sharpqa_agent/
├── main.py              # CLI entrypoint
├── core/                # Database, models, LLM client, vector store
├── sourcers/            # YC, Wellfound, ProductHunt, GitHub
├── enrichers/           # Contacts, tech stack, social, email guesser
├── analyzers/           # Playwright, Lighthouse, axe, security headers
├── prioritizer/         # Lead scoring engine
├── drafter/             # RAG-powered email generation
├── exporter/            # Excel/CSV export
├── orchestrator/        # Pipeline, scheduler, FastAPI
└── dashboard/           # Streamlit multi-page UI
```

## License

Qanalyz
