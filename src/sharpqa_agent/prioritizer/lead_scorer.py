"""Lead scorer — computes priority scores using configurable YAML weights."""

from __future__ import annotations

from pathlib import Path

import yaml

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Contact, Finding, Lead, TechStack
from sharpqa_agent.prioritizer.signals import (
    funding_stage_signal,
    has_primary_contact_email_signal,
    max_finding_severity_signal,
    team_size_signal,
    tech_stack_indicates_saas_signal,
)

logger = get_logger(__name__)


class LeadScorer:
    """Score and rank leads based on configurable weights from scoring_weights.yaml.

    The final score is a weighted average of multiple signals, normalized to [0, 1].
    Bonus signals are additive on top of the base score.
    """

    def __init__(self, weights_path: str | Path = "config/scoring_weights.yaml") -> None:
        self.weights = self._load_weights(weights_path)

    def _load_weights(self, weights_path: str | Path) -> dict:
        """Load scoring weights from YAML configuration.

        Args:
            weights_path: Path to the scoring weights YAML file.

        Returns:
            Parsed weights dictionary.
        """
        path = Path(weights_path)
        if not path.exists():
            logger.warning("scoring_weights_not_found", path=str(path))
            return {}

        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def score_lead(
        self,
        lead: Lead,
        findings: list[Finding],
        contacts: list[Contact],
        tech_stack: list[TechStack],
    ) -> float:
        """Compute a priority score for a lead.

        Args:
            lead: The lead to score.
            findings: All findings associated with the lead.
            contacts: All contacts for the lead.
            tech_stack: Detected tech stack for the lead.

        Returns:
            Priority score normalized to [0.0, 1.0].
        """
        # Base signals (each 0-1, equally weighted)
        funding_score = funding_stage_signal(lead, self.weights.get("funding_stage", {}))
        team_score = team_size_signal(lead, self.weights.get("team_size", {}))
        severity_score = max_finding_severity_signal(findings, self.weights.get("max_finding_severity", {}))

        # Weighted average of base signals
        base_score = (funding_score + team_score + severity_score) / 3.0

        # Bonus signals (additive)
        bonus = 0.0
        if has_primary_contact_email_signal(contacts):
            bonus += self.weights.get("has_primary_contact_email", 0.3)

        if tech_stack_indicates_saas_signal(tech_stack):
            bonus += self.weights.get("tech_stack_indicates_saas", 0.2)

        # Finding count bonus — more findings = more email material
        if len(findings) >= 5:
            bonus += 0.1
        elif len(findings) >= 3:
            bonus += 0.05

        # Final score capped at 1.0
        final_score = min(base_score + bonus, 1.0)
        final_score = round(final_score, 3)

        logger.debug(
            "lead_scored",
            lead_id=lead.lead_id,
            funding=funding_score,
            team=team_score,
            severity=severity_score,
            bonus=bonus,
            final=final_score,
        )

        return final_score
