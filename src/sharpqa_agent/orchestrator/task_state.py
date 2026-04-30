"""Pipeline run tracking — manages run state and progress updates."""

from __future__ import annotations

from datetime import datetime

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import PipelineRun, RunStatus

logger = get_logger(__name__)

# In-memory store of active runs (for SSE streaming)
_active_runs: dict[str, PipelineRun] = {}
_run_logs: dict[str, list[str]] = {}


def create_run(stage_name: str) -> PipelineRun:
    """Create a new pipeline run record.

    Args:
        stage_name: Name of the pipeline stage.

    Returns:
        A new PipelineRun model.
    """
    run = PipelineRun(stage_name=stage_name, started_at=datetime.utcnow())
    _active_runs[run.run_id] = run
    _run_logs[run.run_id] = []
    logger.info("pipeline_run_created", run_id=run.run_id, stage=stage_name)
    return run


def update_run(run_id: str, status: RunStatus, leads_processed: int = 0, error_message: str | None = None) -> None:
    """Update a run's status.

    Args:
        run_id: The run's UUID.
        status: New status.
        leads_processed: Count of processed leads.
        error_message: Error message if failed.
    """
    if run_id in _active_runs:
        _active_runs[run_id].run_status = status
        _active_runs[run_id].leads_processed = leads_processed
        _active_runs[run_id].error_message = error_message
        if status in (RunStatus.SUCCESS, RunStatus.FAILED):
            _active_runs[run_id].completed_at = datetime.utcnow()


def add_log(run_id: str, message: str) -> None:
    """Add a log message to a run.

    Args:
        run_id: The run's UUID.
        message: Log message.
    """
    if run_id not in _run_logs:
        _run_logs[run_id] = []
    timestamp = datetime.utcnow().isoformat()
    _run_logs[run_id].append(f"[{timestamp}] {message}")


def get_run(run_id: str) -> PipelineRun | None:
    """Get a run by ID.

    Args:
        run_id: The run's UUID.

    Returns:
        PipelineRun or None.
    """
    return _active_runs.get(run_id)


def get_run_logs(run_id: str) -> list[str]:
    """Get log messages for a run.

    Args:
        run_id: The run's UUID.

    Returns:
        List of log message strings.
    """
    return _run_logs.get(run_id, [])
