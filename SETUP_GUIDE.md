# SharpQA Sales Agent — Setup & Running Guide

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Quick Start (Recommended)](#2-quick-start-recommended)
3. [Detailed Setup — Windows](#3-detailed-setup--windows)
4. [Detailed Setup — Linux / macOS](#4-detailed-setup--linux--macos)
5. [Running the Agent](#5-running-the-agent)
6. [Running Individual Components](#6-running-individual-components)
7. [Running Tests](#7-running-tests)
8. [Docker Deployment](#8-docker-deployment)
9. [Building a Windows .exe](#9-building-a-windows-exe)
10. [Android / .apk Support](#10-android--apk-support)
11. [Environment Configuration](#11-environment-configuration)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Prerequisites

| Dependency | Required? | Version | Purpose |
|---|---|---|---|
| Python | Yes | 3.10+ | Runtime |
| uv | Yes | latest | Package manager (10-100x faster than pip) |
| Ollama | Yes (for drafting) | latest | Local LLM inference |
| Node.js | Optional | 18+ | Required only for Lighthouse CLI |
| Lighthouse | Optional | latest | Website performance/SEO auditing |
| Git | Optional | any | Cloning the repo |

### Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB |
| Disk | 5 GB (models + browser) | 10 GB |
| GPU | Not required | NVIDIA GPU for faster LLM inference |
| CPU | 4 cores | 8 cores (parallel analysis runs) |

---

## 2. Quick Start (Recommended)

The fastest path from zero to running:

```bash
# 1. Clone the repository
git clone <repo-url> sharpqa-agent
cd sharpqa-agent

# 2. Install uv (if not already installed)
# Windows (PowerShell):
pip install uv
# Linux/macOS:
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install all Python dependencies + create virtual environment
uv sync

# 4. Install Playwright's Chromium browser
uv run playwright install chromium

# 5. Copy environment config
cp .env.example .env          # Linux/macOS
copy .env.example .env        # Windows CMD

# 6. Install and start Ollama (separate terminal)
# Download from: https://ollama.com/download
ollama pull llama3.1:8b-instruct-q4_K_M

# 7. Initialize the database
uv run sharpqa init

# 8. Start the agent (API + Dashboard)
uv run sharpqa serve
```

After step 8:
- API server: http://127.0.0.1:8000 (with docs at http://127.0.0.1:8000/docs)
- Dashboard: http://127.0.0.1:8501

---

## 3. Detailed Setup — Windows

### Option A: Automated Installer

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

This script checks/installs Python, uv, Node.js, Lighthouse, Playwright, creates `.env`, and initializes the database.

### Option B: Manual Step-by-Step

**Step 1 — Install Python 3.10+**

Download from https://python.org/downloads. During installation, check "Add Python to PATH".

Verify:
```cmd
python --version
```

**Step 2 — Install uv**

```cmd
pip install uv
```

Verify:
```cmd
uv --version
```

**Step 3 — Install dependencies**

```cmd
cd sharpqa-agent
uv sync
```

This creates a `.venv` directory and installs all packages from `pyproject.toml` and `uv.lock`.

**Step 4 — Install Playwright Chromium**

```cmd
uv run playwright install chromium
```

This downloads a Chromium binary (~150 MB) into the Playwright cache.

**Step 5 — Install Lighthouse CLI (optional)**

Requires Node.js from https://nodejs.org.

```cmd
npm install -g lighthouse
lighthouse --version
```

**Step 6 — Install and start Ollama**

Download from https://ollama.com/download/windows.

After installation:
```cmd
ollama pull llama3.1:8b-instruct-q4_K_M
```

This downloads the model (~4.7 GB). Ollama runs as a background service on Windows automatically after installation.

**Step 7 — Configure environment**

```cmd
copy .env.example .env
```

Edit `.env` with your settings (operator name, API tokens, etc.).

**Step 8 — Initialize and run**

```cmd
uv run sharpqa init
uv run sharpqa serve
```

---

## 4. Detailed Setup — Linux / macOS

### Option A: Automated Installer

```bash
chmod +x scripts/install_unix.sh
./scripts/install_unix.sh
```

### Option B: Manual Step-by-Step

```bash
# Python (most distros ship with it)
python3 --version   # needs 3.10+

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc    # or restart terminal

# Install dependencies
cd sharpqa-agent
uv sync

# Playwright (with system deps on Linux)
uv run playwright install chromium --with-deps

# Lighthouse (optional)
sudo npm install -g lighthouse

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.1:8b-instruct-q4_K_M

# Configure
cp .env.example .env
nano .env

# Initialize and run
uv run sharpqa init
uv run sharpqa serve
```

---

## 5. Running the Agent

### Full Server (API + Dashboard)

```bash
uv run sharpqa serve
```

This starts **two** processes:
1. **FastAPI** backend on `http://127.0.0.1:8000` (background subprocess)
2. **Streamlit** dashboard on `http://127.0.0.1:8501` (foreground)

Both are bound to `127.0.0.1` only — not accessible from other machines on the network.

Press `Ctrl+C` to stop both.

### CLI-Only Pipeline (No GUI)

Run the entire pipeline from the command line without starting any server:

```bash
# Run all 5 stages with default limit of 10 leads
uv run sharpqa run

# Run specific stages
uv run sharpqa run --stages source --stages enrich --limit 20

# Run just sourcing
uv run sharpqa run -s source -l 50

# Run analysis + prioritization only
uv run sharpqa run -s analyze -s prioritize -l 10
```

Available stages (in order): `source`, `enrich`, `analyze`, `prioritize`, `draft`

### Export Only

```bash
uv run sharpqa export
```

Generates an Excel file at `data/exports/SharpQA_leads_<timestamp>.xlsx`.

### Initialize / Reset Database

```bash
uv run sharpqa init
```

Creates the SQLite database and all data directories. Safe to run multiple times — existing data is preserved (`CREATE TABLE IF NOT EXISTS`).

To fully reset, delete the database file first:
```bash
rm data/sharpqa.db        # Linux/macOS
del data\sharpqa.db       # Windows
uv run sharpqa init
```

---

## 6. Running Individual Components

### FastAPI Backend Only (No Dashboard)

```bash
uv run uvicorn sharpqa_agent.orchestrator.api:app --host 127.0.0.1 --port 8000
```

Interactive API docs available at http://127.0.0.1:8000/docs.

Useful for:
- Testing API endpoints directly
- Connecting a custom frontend
- Running in production behind a reverse proxy

### Streamlit Dashboard Only (No Backend)

```bash
uv run streamlit run src/sharpqa_agent/dashboard/app.py --server.port 8501 --server.address 127.0.0.1
```

The dashboard expects the FastAPI backend to be running separately. Start the API first.

### Ollama Warmup / Model Check

```bash
uv run python scripts/warmup_ollama.py
```

Checks if Ollama is running, pulls the model if needed, and runs a test generation.

### Run a Single Sourcer (for testing)

```python
# In a Python shell:
import asyncio
from sharpqa_agent.sourcers.yc_sourcer import YCSourcer

async def test():
    sourcer = YCSourcer(headless=True)
    leads = await sourcer.fetch_new_leads(limit=5)
    for lead in leads:
        print(f"{lead.company_name}: {lead.website_url}")

asyncio.run(test())
```

### Run a Single Analyzer (for testing)

```python
import asyncio
from sharpqa_agent.analyzers.security_header_checker import SecurityHeaderChecker

async def test():
    checker = SecurityHeaderChecker()
    findings = await checker.analyze("test-lead-123", "https://example.com")
    for f in findings:
        print(f"{f.severity_level}: {f.finding_title}")

asyncio.run(test())
```

---

## 7. Running Tests

### Install Dev Dependencies

```bash
uv sync --extra dev
```

### Run All Tests

```bash
uv run pytest
```

### Run Tests with Coverage

```bash
uv run pytest --cov=sharpqa_agent --cov-report=term-missing
```

### Run Specific Test Files

```bash
# Database tests
uv run pytest tests/test_orchestrator/test_database.py -v

# Analyzer tests
uv run pytest tests/test_analyzers/ -v

# Drafter tests
uv run pytest tests/test_drafter/ -v

# Enricher tests
uv run pytest tests/test_enrichers/ -v

# Sourcer tests
uv run pytest tests/test_sourcers/ -v
```

### Run a Single Test

```bash
uv run pytest tests/test_analyzers/test_security_headers.py::test_missing_headers -v
```

### Skip Slow Tests (Network-Dependent)

Tests that hit real networks are marked with `@pytest.mark.slow`:

```bash
uv run pytest -m "not slow"
```

### Run Linter

```bash
uv run ruff check src/ tests/
uv run ruff check src/ tests/ --fix   # auto-fix
```

---

## 8. Docker Deployment

Docker is the recommended approach for server/VPS deployment. It packages everything (Python, Playwright, Lighthouse, Node.js) into a container.

### With Docker Compose (Recommended)

```bash
docker-compose up -d
```

This starts 3 containers:

| Container | Port | Purpose |
|---|---|---|
| `SharpQA-ollama` | 11434 | Ollama LLM server (with GPU passthrough if available) |
| `SharpQA-backend` | 8000 | FastAPI backend |
| `SharpQA-ui` | 8501 | Streamlit dashboard |

Pull the model into the Ollama container:
```bash
docker exec SharpQA-ollama ollama pull llama3.1:8b-instruct-q4_K_M
```

View logs:
```bash
docker-compose logs -f agent-backend
docker-compose logs -f agent-ui
```

Stop everything:
```bash
docker-compose down
```

Data is persisted via volume mounts:
- `./data/` → all databases, logs, screenshots, exports
- `./config/` → settings, weights, templates
- `ollama_data` → Docker volume for model weights

### Build Image Only

```bash
docker build -t sharpqa-agent .
```

### Run Without Compose

```bash
# Start Ollama separately
docker run -d -p 11434:11434 --name ollama ollama/ollama

# Start SharpQA agent
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config:/app/config \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  sharpqa-agent
```

### GPU Support (NVIDIA)

The `docker-compose.yml` is pre-configured for NVIDIA GPU passthrough via the `deploy.resources.reservations.devices` block. Requirements:
- NVIDIA GPU with CUDA support
- `nvidia-container-toolkit` installed on the host
- Docker runtime configured for NVIDIA

Without a GPU, Ollama runs on CPU (slower, but functional). Remove the `deploy` block from `docker-compose.yml` if you have no GPU.

---

## 9. Building a Windows .exe

SharpQA can be packaged as a standalone Windows executable using PyInstaller. This creates a single `.exe` file that bundles the Python runtime and all code.

### Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1
```

Output: `dist/SharpQAAgent.exe`

### What the .exe Does

The `.exe` is a **CLI launcher** — it runs the same Click commands as `uv run sharpqa`:

```cmd
SharpQAAgent.exe init
SharpQAAgent.exe run --stages source --stages enrich --limit 20
SharpQAAgent.exe serve
SharpQAAgent.exe export
```

### What the .exe Does NOT Include

The `.exe` bundles Python code only. Users still need these installed separately on their system:

| External Dependency | Why It Cannot Be Bundled |
|---|---|
| **Ollama** | Separate server process with its own model storage (~5 GB). Must be running as a service. |
| **Chromium (Playwright)** | ~150 MB browser binary managed by Playwright's own cache. Run `playwright install chromium` after first launch. |
| **Node.js + Lighthouse** | Optional. Lighthouse is a ~50 MB npm package with Node.js runtime dependency. |

### Distributing the .exe

To distribute to a non-developer user:

1. Build the `.exe` on your machine
2. Create a zip with:
   ```
   SharpQAAgent.exe
   .env.example
   config/
     scoring_weights.yaml
     sources.yaml
     email_templates/
   SETUP_GUIDE.md
   ```
3. Instruct the user to:
   - Install Ollama from https://ollama.com/download
   - Run `ollama pull llama3.1:8b-instruct-q4_K_M`
   - Rename `.env.example` to `.env` and edit it
   - Run `SharpQAAgent.exe init`
   - Run `SharpQAAgent.exe serve`

### Limitations of the .exe Approach

- **Large file size:** The bundled `.exe` is ~200–400 MB due to PyTorch, sentence-transformers, and other ML libraries
- **Startup time:** PyInstaller extracts to a temp directory on first run — initial launch takes 10–30 seconds
- **No auto-update:** Users must re-download the `.exe` for new versions
- **Antivirus false positives:** PyInstaller executables are sometimes flagged by Windows Defender. Users may need to add an exception.

---

## 10. Android / .apk Support

### Short Answer: Not Supported

SharpQA is a **desktop/server application**. There is no `.apk` build and no mobile support. Here's why:

| Reason | Detail |
|---|---|
| **Playwright requires a desktop OS** | Chromium browser automation does not work on Android. Playwright only supports Windows, Linux, and macOS. |
| **Ollama requires x86/ARM server hardware** | Ollama cannot run on Android. The LLM inference requires 5+ GB RAM dedicated to the model. |
| **Lighthouse is a Node.js CLI** | Not available on Android. |
| **SQLite with FTS5 + WAL** | Python's `sqlite3` module on Android (via Kivy/BeeWare) does not reliably support FTS5 extensions. |
| **FastAPI + Streamlit** | Both are server-side frameworks designed for desktop browsers, not mobile apps. |

### Workaround: Access From a Phone

If you want to use SharpQA from a mobile device:

**Option 1 — Run on a local PC, access from phone**
```bash
# Start with network-accessible binding (instead of localhost):
uv run uvicorn sharpqa_agent.orchestrator.api:app --host 0.0.0.0 --port 8000
uv run streamlit run src/sharpqa_agent/dashboard/app.py --server.port 8501 --server.address 0.0.0.0
```
Then open `http://<your-pc-ip>:8501` on your phone's browser. Both devices must be on the same network.

**Option 2 — Deploy to a VPS with Docker**

Deploy using Docker Compose on a cloud VPS (DigitalOcean, Hetzner, AWS EC2). Access the Streamlit dashboard from any browser on any device.

```bash
# On the VPS:
docker-compose up -d
docker exec SharpQA-ollama ollama pull llama3.1:8b-instruct-q4_K_M
```

Add a reverse proxy (Nginx/Caddy) with HTTPS for secure remote access.

**Option 3 — Tailscale / Cloudflare Tunnel**

Expose your local machine securely without opening ports:
```bash
# Tailscale (mesh VPN):
tailscale up
# Access via https://your-machine.tailnet:8501

# Cloudflare Tunnel (free):
cloudflared tunnel --url http://localhost:8501
# Gives you a public https URL
```

### What About a Mobile App in the Future?

If mobile support were ever needed, the architecture already supports it:

1. The **FastAPI backend** exposes a clean REST API at `/leads`, `/findings`, `/drafts`, etc.
2. A **React Native** or **Flutter** app could consume this API directly
3. The backend would run on a server (VPS or home machine), and the mobile app would be a thin client

The dashboard (Streamlit) would be replaced, but the entire pipeline backend and API layer would remain unchanged.

---

## 11. Environment Configuration

All configuration is in `.env` (copy from `.env.example`).

### Critical Settings

```env
# Your name and company (used in email drafts)
OPERATOR_NAME=Ali
OPERATOR_COMPANY=SharpQA

# Ollama — must match a running Ollama instance
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_NAME=llama3.1:8b-instruct-q4_K_M
```

### Optional API Tokens

```env
# GitHub sourcer (higher rate limits with token)
GITHUB_PERSONAL_TOKEN=ghp_xxxxxxxxxxxx

# Product Hunt sourcer (required for GraphQL API)
PRODUCT_HUNT_TOKEN=xxxxxxxxxxxxxxxx
```

### Performance Tuning

```env
# How many websites to analyze simultaneously (higher = faster but more RAM)
MAX_CONCURRENT_ANALYZES=2    # default; set to 4 on 16GB+ RAM

# Minimum score to generate an email draft (0.0 to 1.0)
MIN_PRIORITY_SCORE_FOR_DRAFTING=0.6
```

### Dashboard Security

```env
# Set a password to protect the dashboard (leave empty for no password)
DASHBOARD_PASSWORD=my-secret-password
```

### Nightly Auto-Sourcing

```env
# Run source + enrich automatically at 2:00 AM daily
NIGHTLY_SOURCE_CRON_HOUR=2
NIGHTLY_SOURCE_CRON_MINUTE=0
```

---

## 12. Troubleshooting

### "Cannot connect to Ollama"

```
LLMError: Cannot connect to Ollama at http://localhost:11434. Is it running?
```

**Fix:** Start Ollama:
- Windows: Ollama should run as a system tray app. If not, run `ollama serve` in a terminal.
- Linux/macOS: `ollama serve` or `systemctl start ollama`

Then pull the model: `ollama pull llama3.1:8b-instruct-q4_K_M`

### "Playwright browser not installed"

```
playwright._impl._errors.Error: Executable doesn't exist
```

**Fix:**
```bash
uv run playwright install chromium
# On Linux, also install system deps:
uv run playwright install chromium --with-deps
```

### "Lighthouse not found"

```
FileNotFoundError: lighthouse
```

**Fix:** This is optional. Analysis continues without Lighthouse. To install:
```bash
npm install -g lighthouse
```

### "ModuleNotFoundError: No module named 'sharpqa_agent'"

**Fix:** The package must be installed in the venv:
```bash
uv sync
```

If that doesn't work, ensure `[build-system]` exists in `pyproject.toml` and run:
```bash
uv sync --reinstall
```

### Tests Fail With Import Errors

**Fix:** Install dev dependencies:
```bash
uv sync --extra dev
uv run pytest
```

### Database Locked

```
sqlite3.OperationalError: database is locked
```

**Fix:** Only one process should write at a time. If you have both `sharpqa serve` and `sharpqa run` active, stop one. WAL mode handles concurrent reads but not concurrent writes from separate processes well.

### High Memory Usage During Analysis

Each Playwright Chromium instance uses ~150 MB. If analyzing multiple leads concurrently:

**Fix:** Lower the concurrency:
```env
MAX_CONCURRENT_ANALYZES=1
```

### Windows: PowerShell Script Blocked

```
File cannot be loaded because running scripts is disabled
```

**Fix:**
```powershell
powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1
```

### Docker: Ollama GPU Not Detected

**Fix:** Install the NVIDIA container toolkit:
```bash
# Ubuntu/Debian
sudo apt install nvidia-container-toolkit
sudo systemctl restart docker
```

If you have no GPU, remove the `deploy` block from the `ollama` service in `docker-compose.yml`.
