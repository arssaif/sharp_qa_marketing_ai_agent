# SharpQA Sales Agent — Windows Executable Builder
# Produces SharpQAAgent.exe using PyInstaller
# Run with: powershell -ExecutionPolicy Bypass -File scripts/build_windows_exe.ps1

$ErrorActionPreference = "Stop"

Write-Host "Building SharpQA Agent Windows Executable..." -ForegroundColor Cyan

# Ensure PyInstaller is installed
uv pip install pyinstaller

# Build the launcher
uv run pyinstaller `
    --name SharpQAAgent `
    --onefile `
    --add-data "config;config" `
    --add-data "src/sharpqa_agent/core/schema.sql;sharpqa_agent/core" `
    --hidden-import sharpqa_agent `
    --hidden-import sharpqa_agent.main `
    --hidden-import sharpqa_agent.orchestrator.api `
    --hidden-import sharpqa_agent.dashboard.app `
    --hidden-import uvicorn `
    --hidden-import streamlit `
    --console `
    src/sharpqa_agent/main.py

Write-Host ""
Write-Host "Build complete!" -ForegroundColor Green
Write-Host "Executable: dist/sharpqa-agent.exe" -ForegroundColor White
Write-Host ""
Write-Host "Note: The .exe is a launcher only. Users still need:" -ForegroundColor Yellow
Write-Host "  - Ollama installed and running" -ForegroundColor Yellow
Write-Host "  - Node.js + Lighthouse CLI (for website analysis)" -ForegroundColor Yellow
