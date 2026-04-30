#!/usr/bin/env bash
# SharpQA Sales Agent — Unix Installer (Linux/macOS)
set -e

echo "========================================"
echo "  SharpQA Sales Agent — Unix Setup"
echo "========================================"
echo ""

# 1. Check Python
echo "[1/7] Checking Python..."
if command -v python3 &> /dev/null; then
    PYTHON=$(which python3)
    echo "  Found: $($PYTHON --version)"
else
    echo "  ERROR: Python 3 not found. Install from https://python.org"
    exit 1
fi

# 2. Check/install uv
echo "[2/7] Checking uv..."
if command -v uv &> /dev/null; then
    echo "  Found: $(uv --version)"
else
    echo "  Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    echo "  uv installed"
fi

# 3. Check Node.js
echo "[3/7] Checking Node.js..."
if command -v node &> /dev/null; then
    echo "  Found: Node.js $(node --version)"
else
    echo "  WARNING: Node.js not found. Install from https://nodejs.org"
    echo "  (Required for Lighthouse CLI — optional)"
fi

# 4. Install Lighthouse
echo "[4/7] Installing Lighthouse CLI..."
if command -v npm &> /dev/null; then
    npm install -g lighthouse 2>/dev/null || echo "  Lighthouse install skipped"
    echo "  Lighthouse installed"
else
    echo "  Skipped (npm not available)"
fi

# 5. Install Python dependencies
echo "[5/7] Installing Python dependencies..."
uv sync
echo "  Dependencies installed"

# 6. Install Playwright browsers
echo "[6/7] Installing Playwright Chromium..."
uv run playwright install chromium --with-deps
echo "  Chromium installed"

# 7. Initialize project
echo "[7/7] Initializing project..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  Created .env from template"
fi

uv run python -m sharpqa_agent.main init
echo "  Database initialized"

echo ""
echo "========================================"
echo "  Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Install Ollama from https://ollama.com/download"
echo "  2. Run: ollama pull llama3.1:8b-instruct-q4_K_M"
echo "  3. Edit .env with your settings"
echo "  4. Start: uv run python -m sharpqa_agent.main serve"
