# SharpQA Sales Agent — Windows Installer
# Run with: powershell -ExecutionPolicy Bypass -File scripts/install_windows.ps1

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SharpQA Sales Agent — Windows Setup"   -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Python
Write-Host "[1/7] Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "  Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "  Python not found! Install from https://python.org/downloads" -ForegroundColor Red
    exit 1
}

# 2. Check/install uv
Write-Host "[2/7] Checking uv..." -ForegroundColor Yellow
try {
    $uvVersion = uv --version 2>&1
    Write-Host "  Found: $uvVersion" -ForegroundColor Green
} catch {
    Write-Host "  Installing uv..." -ForegroundColor Yellow
    pip install uv
    Write-Host "  uv installed" -ForegroundColor Green
}

# 3. Check Node.js (for Lighthouse)
Write-Host "[3/7] Checking Node.js..." -ForegroundColor Yellow
try {
    $nodeVersion = node --version 2>&1
    Write-Host "  Found: Node.js $nodeVersion" -ForegroundColor Green
} catch {
    Write-Host "  Node.js not found. Install from https://nodejs.org" -ForegroundColor Red
    Write-Host "  (Required for Lighthouse CLI — optional, analysis will still work without it)" -ForegroundColor Yellow
}

# 4. Install Lighthouse CLI
Write-Host "[4/7] Installing Lighthouse CLI..." -ForegroundColor Yellow
try {
    npm install -g lighthouse 2>&1 | Out-Null
    Write-Host "  Lighthouse installed" -ForegroundColor Green
} catch {
    Write-Host "  Lighthouse install skipped (Node.js required)" -ForegroundColor Yellow
}

# 5. Install Python dependencies
Write-Host "[5/7] Installing Python dependencies..." -ForegroundColor Yellow
uv sync
Write-Host "  Dependencies installed" -ForegroundColor Green

# 6. Install Playwright browsers
Write-Host "[6/7] Installing Playwright Chromium..." -ForegroundColor Yellow
uv run playwright install chromium
Write-Host "  Chromium installed" -ForegroundColor Green

# 7. Initialize project
Write-Host "[7/7] Initializing project..." -ForegroundColor Yellow

# Copy .env if it doesn't exist
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  Created .env from template" -ForegroundColor Green
}

# Initialize database
uv run python -m sharpqa_agent.main init
Write-Host "  Database initialized" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Setup Complete!"                        -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Install Ollama from https://ollama.com/download" -ForegroundColor White
Write-Host "  2. Run: ollama pull llama3.1:8b-instruct-q4_K_M" -ForegroundColor White
Write-Host "  3. Edit .env with your settings" -ForegroundColor White
Write-Host "  4. Start the agent: uv run python -m sharpqa_agent.main serve" -ForegroundColor White
