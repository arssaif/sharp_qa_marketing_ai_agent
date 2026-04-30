"""CLI entrypoint for the SharpQA Sales Agent."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from rich.console import Console

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import get_settings
from sharpqa_agent.core.database import initialize_database
from sharpqa_agent.core.logging_setup import get_logger, setup_logging

console = Console()
logger = get_logger(__name__)


@click.group()
def cli() -> None:
    """SharpQA Sales Agent — local-first lead sourcing and cold outreach automation."""


@cli.command()
def init() -> None:
    """Initialize the database, create directories, and verify external dependencies."""
    settings = get_settings()
    setup_logging(settings.log_dir)

    console.print("[bold blue]SharpQA Sales Agent — Initialization[/bold blue]\n")

    # 1. Create directories
    console.print("  Creating data directories...", end=" ")
    settings.ensure_directories()
    console.print("[green]OK[/green]")

    # 2. Initialize database
    console.print("  Initializing SQLite database...", end=" ")
    initialize_database(settings.sqlite_db_path)
    console.print("[green]OK[/green]")

    # 3. Check Ollama
    console.print("  Checking Ollama...", end=" ")
    ollama_ok = _check_ollama(settings.ollama_base_url)
    if ollama_ok:
        console.print("[green]OK[/green]")
    else:
        console.print("[yellow]NOT REACHABLE[/yellow] (optional — needed for email drafting)")

    # 4. Check Lighthouse CLI
    console.print("  Checking Lighthouse CLI...", end=" ")
    lighthouse_ok = _check_lighthouse()
    if lighthouse_ok:
        console.print("[green]OK[/green]")
    else:
        console.print("[yellow]NOT FOUND[/yellow] (install via: npm install -g lighthouse)")

    # 5. Check Playwright browsers
    console.print("  Checking Playwright browsers...", end=" ")
    playwright_ok = _check_playwright()
    if playwright_ok:
        console.print("[green]OK[/green]")
    else:
        console.print("[yellow]NOT INSTALLED[/yellow] (install via: playwright install chromium)")

    console.print("\n[bold green]Initialization complete![/bold green]")
    console.print(f"  Database: {Path(settings.sqlite_db_path).resolve()}")
    console.print(f"  Logs: {Path(settings.log_dir).resolve()}")

    logger.info("initialization_complete")


@cli.command()
@click.option("--stages", "-s", multiple=True, default=["source", "enrich", "analyze", "prioritize", "draft"])
@click.option("--limit", "-l", default=10, help="Max leads to process per stage")
def run(stages: tuple[str, ...], limit: int) -> None:
    """Run the pipeline with specified stages."""
    settings = get_settings()
    setup_logging(settings.log_dir)
    console.print(f"[bold]Running pipeline stages: {', '.join(stages)} (limit={limit})[/bold]")
    asyncio.run(_run_pipeline(list(stages), limit, settings))


async def _run_pipeline(stages: list[str], limit: int, settings: object) -> None:
    """Execute the pipeline stages sequentially."""
    from sharpqa_agent.orchestrator.pipeline import run_pipeline
    await run_pipeline(stages, limit, settings)


@cli.command()
def serve() -> None:
    """Start the FastAPI backend and Streamlit dashboard."""
    import subprocess

    settings = get_settings()
    setup_logging(settings.log_dir)

    console.print("[bold blue]Starting SharpQA Agent...[/bold blue]")

    # Start FastAPI in background
    api_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "sharpqa_agent.orchestrator.api:app",
         "--host", "127.0.0.1", "--port", str(settings.api_port)],
        cwd=str(Path(__file__).parent.parent),
    )

    console.print(f"  API server: http://127.0.0.1:{settings.api_port}")
    console.print(f"  Dashboard: http://127.0.0.1:{settings.dashboard_port}")

    try:
        # Start Streamlit (foreground)
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run",
             str(Path(__file__).parent / "dashboard" / "app.py"),
             "--server.port", str(settings.dashboard_port),
             "--server.address", "127.0.0.1"],
        )
    finally:
        api_process.terminate()


@cli.command()
def export() -> None:
    """Export approved leads and drafts to Excel."""
    settings = get_settings()
    setup_logging(settings.log_dir)
    console.print("[bold]Exporting to Excel...[/bold]")
    asyncio.run(_export(settings))


async def _export(settings: object) -> None:
    """Run the Excel export."""
    from sharpqa_agent.exporter.excel_exporter import export_leads_to_excel
    output_path = await export_leads_to_excel(settings)
    console.print(f"[green]Exported to: {output_path}[/green]")


def _check_ollama(base_url: str) -> bool:
    """Check if Ollama is running."""
    try:
        import httpx
        response = httpx.get(f"{base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def _check_lighthouse() -> bool:
    """Check if Lighthouse CLI is installed."""
    import subprocess
    try:
        result = subprocess.run(["lighthouse", "--version"], capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def _check_playwright() -> bool:
    """Check if Playwright Chromium is installed."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        return False


if __name__ == "__main__":
    cli()
