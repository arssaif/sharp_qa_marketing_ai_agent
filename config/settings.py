"""Application configuration loaded from environment variables and .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the SharpQA Sales Agent.

    All values can be overridden via environment variables or a .env file
    in the project root.
    """

    # Paths
    sqlite_db_path: str = "data/sharpqa.db"
    chroma_persist_dir: str = "data/chroma"
    log_dir: str = "data/logs"
    screenshots_dir: str = "data/screenshots"
    exports_dir: str = "data/exports"

    # LLM Provider Configuration
    llm_provider: str = "ollama"  # 'ollama' or 'gemini'

    # Ollama settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model_name: str = "llama3.1:8b-instruct-q4_K_M"
    ollama_timeout_seconds: int = 120

    # Gemini settings
    gemini_api_key: str = ""

    # Embeddings
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Playwright
    playwright_headless: bool = True

    # Rate limits
    max_concurrent_analyzes: int = 2
    daily_source_limit_yc: int = 50
    daily_source_limit_wellfound: int = 30
    daily_source_limit_producthunt: int = 50
    daily_source_limit_github: int = 50

    # Operator info (used in email templates)
    operator_name: str = "Ali"
    operator_company: str = "SharpQA"
    operator_booking_link: str = ""

    # Optional API tokens
    github_personal_token: str = ""
    product_hunt_token: str = ""

    # Dashboard
    dashboard_password: str = ""
    dashboard_port: int = 8501
    api_port: int = 8000

    # Scheduler
    nightly_source_cron_hour: int = 2
    nightly_source_cron_minute: int = 0

    # Prioritizer
    min_priority_score_for_drafting: float = 0.6

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    def ensure_directories(self) -> None:
        """Create all data directories if they don't exist."""
        for directory in [
            self.sqlite_db_path.rsplit("/", 1)[0] if "/" in self.sqlite_db_path else "data",
            self.chroma_persist_dir,
            self.log_dir,
            self.screenshots_dir,
            self.exports_dir,
        ]:
            Path(directory).mkdir(parents=True, exist_ok=True)


def get_settings() -> Settings:
    """Create and return a Settings instance.

    Returns:
        Configured Settings object.
    """
    return Settings()
