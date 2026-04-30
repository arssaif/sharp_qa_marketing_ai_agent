"""CSV exporter — lightweight alternative to Excel export."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sharpqa_agent.core.database import (
    get_contacts_for_lead,
    get_drafts,
    get_findings_for_lead,
    get_leads,
)
from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)


async def export_leads_to_csv(
    settings,
    lead_ids: list[str] | None = None,
) -> Path:
    """Export leads to a CSV file.

    Args:
        settings: Application settings.
        lead_ids: Optional specific lead IDs to export.

    Returns:
        Path to the generated CSV file.
    """
    db_path = settings.sqlite_db_path
    exports_dir = Path(settings.exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)

    leads = await get_leads(db_path, limit=1000)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = exports_dir / f"SharpQA_leads_{timestamp}.csv"

    with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Company Name", "Website", "Email", "Contact", "LinkedIn",
            "Top Finding", "Priority Score", "Status", "Draft Subject",
        ])

        for lead in leads:
            contacts = await get_contacts_for_lead(db_path, lead.lead_id)
            findings = await get_findings_for_lead(db_path, lead.lead_id)
            drafts = await get_drafts(db_path, lead_id=lead.lead_id, limit=1)

            primary = next((c for c in contacts if c.is_primary_contact), contacts[0] if contacts else None)
            top_finding = findings[0].finding_title if findings else ""
            draft = drafts[0] if drafts else None

            writer.writerow([
                lead.company_name,
                lead.website_url,
                primary.email_address if primary else "",
                primary.full_name if primary else "",
                primary.linkedin_url if primary else "",
                top_finding,
                round(lead.priority_score, 2),
                lead.lead_status.value if hasattr(lead.lead_status, 'value') else lead.lead_status,
                draft.subject_line if draft else "",
            ])

    logger.info("csv_exported", path=str(output_path), leads=len(leads))
    return output_path
