"""Abstract base class for all lead sourcers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from sharpqa_agent.core.models import RawLead


class BaseSourcer(ABC):
    """Contract that all lead sourcers must implement.

    Each sourcer discovers potential leads from a specific platform
    (e.g., YC, Wellfound) and returns them as RawLead models.
    """

    source_name: str = "unknown"

    @abstractmethod
    async def fetch_new_leads(self, since: datetime | None = None, limit: int = 50) -> list[RawLead]:
        """Fetch new leads from this source.

        Args:
            since: Only fetch leads discovered/updated after this timestamp.
                   If None, fetch the most recent leads.
            limit: Maximum number of leads to return.

        Returns:
            List of RawLead models.

        Raises:
            SourcerError: If fetching fails due to network, rate limit, or parsing issues.
        """
        ...

    async def healthcheck(self) -> bool:
        """Check if this sourcer's target platform is reachable.

        Returns:
            True if the platform responds, False otherwise.
        """
        return True
