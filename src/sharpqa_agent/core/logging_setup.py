"""Structured logging configuration using structlog with JSON file output and console rendering."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import structlog


def setup_logging(log_dir: str | Path = "data/logs", log_level: str = "INFO") -> None:
    """Configure structlog for both console (human-friendly) and file (JSON) output.

    Args:
        log_dir: Directory where log files are written. Created if missing.
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    log_file = log_path / "agent.log"

    # Shared processors applied before final rendering
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # JSON file handler
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=7, encoding="utf-8"
    )
    file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Standard library logging config
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
        handlers=[file_handler, console_handler],
        force=True,
    )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Formatter for file handler (JSON)
    file_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
    )
    file_handler.setFormatter(file_formatter)

    # Formatter for console (human-readable)
    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
    )
    console_handler.setFormatter(console_formatter)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a named structlog logger.

    Args:
        name: Logger name, typically the module path.

    Returns:
        A bound structlog logger instance.
    """
    return structlog.get_logger(name)
