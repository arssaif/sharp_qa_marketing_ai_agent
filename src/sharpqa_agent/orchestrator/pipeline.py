"""Pipeline orchestrator — chains stages with per-lead error isolation."""

from __future__ import annotations

import asyncio

from sharpqa_agent.core.database import (
    async_db,
    get_contacts_for_lead,
    get_findings_for_lead,
    get_leads,
    get_tech_stack_for_lead,
    insert_contact,
    insert_draft,
    insert_finding,
    insert_lead,
    insert_pipeline_run,
    insert_tech_stack,
    update_lead_priority,
    update_lead_status,
    update_pipeline_run,
)
from sharpqa_agent.core.llm_client import OllamaClient
from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.models import Lead, PipelineRun, RunStatus
from sharpqa_agent.orchestrator.task_state import add_log, create_run, update_run

logger = get_logger(__name__)


async def run_pipeline(stages: list[str], limit: int, settings) -> str:
    """Execute pipeline stages sequentially.

    Args:
        stages: List of stage names to run (e.g., ['source', 'enrich', 'analyze', 'prioritize', 'draft']).
        limit: Max leads to process per stage.
        settings: Application settings object.

    Returns:
        The run_id of the created pipeline run.
    """
    db_path = settings.sqlite_db_path
    stage_names = ", ".join(stages)
    run = create_run(stage_names)
    await insert_pipeline_run(db_path, run)

    add_log(run.run_id, f"Starting pipeline: {stage_names} (limit={limit})")
    total_processed = 0

    try:
        for stage in stages:
            add_log(run.run_id, f"Running stage: {stage}")

            if stage == "source":
                processed = await _run_source_stage(db_path, limit, settings, run.run_id)
            elif stage == "enrich":
                processed = await _run_enrich_stage(db_path, limit, settings, run.run_id)
            elif stage == "analyze":
                processed = await _run_analyze_stage(db_path, limit, settings, run.run_id)
            elif stage == "prioritize":
                processed = await _run_prioritize_stage(db_path, limit, settings, run.run_id)
            elif stage == "draft":
                processed = await _run_draft_stage(db_path, limit, settings, run.run_id)
            else:
                add_log(run.run_id, f"Unknown stage: {stage}, skipping")
                processed = 0

            total_processed += processed
            add_log(run.run_id, f"Stage {stage} complete: {processed} leads processed")

        update_run(run.run_id, RunStatus.SUCCESS, total_processed)
        await update_pipeline_run(db_path, run.run_id, "success", total_processed)
        add_log(run.run_id, f"Pipeline complete: {total_processed} total leads processed")

    except Exception as error:
        error_msg = str(error)
        update_run(run.run_id, RunStatus.FAILED, total_processed, error_msg)
        await update_pipeline_run(db_path, run.run_id, "failed", total_processed, error_msg)
        add_log(run.run_id, f"Pipeline failed: {error_msg}")
        logger.error("pipeline_failed", run_id=run.run_id, error=error_msg)

    return run.run_id


async def _run_source_stage(db_path: str, limit: int, settings, run_id: str) -> int:
    """Run all enabled sourcers and insert discovered leads."""
    from sharpqa_agent.sourcers.sourcer_registry import get_enabled_sourcers

    sourcers = get_enabled_sourcers(
        headless=settings.playwright_headless,
        github_token=settings.github_personal_token,
        producthunt_token=settings.product_hunt_token,
    )

    total = 0
    for sourcer in sourcers:
        try:
            add_log(run_id, f"Sourcing from {sourcer.source_name}...")
            raw_leads = await sourcer.fetch_new_leads(limit=limit)
            for raw_lead in raw_leads:
                lead = Lead(
                    company_name=raw_lead.company_name,
                    website_url=raw_lead.website_url,
                    source_platform=raw_lead.source_platform,
                    source_reference_id=raw_lead.source_reference_id,
                    funding_stage=raw_lead.funding_stage,
                    team_size_range=raw_lead.team_size_range,
                    industry_tags=raw_lead.industry_tags,
                    country_code=raw_lead.country_code,
                    short_description=raw_lead.short_description,
                )
                await insert_lead(db_path, lead)
                total += 1
            add_log(run_id, f"  {sourcer.source_name}: {len(raw_leads)} leads found")
        except Exception as error:
            add_log(run_id, f"  {sourcer.source_name} failed: {error}")
            logger.warning("sourcer_failed", sourcer=sourcer.source_name, error=str(error))

    return total


async def _run_enrich_stage(db_path: str, limit: int, settings, run_id: str) -> int:
    """Enrich leads with contacts, tech stack, and social handles."""
    from sharpqa_agent.enrichers.contact_enricher import ContactEnricher
    from sharpqa_agent.enrichers.email_pattern_guesser import EmailPatternGuesser
    from sharpqa_agent.enrichers.social_handle_finder import SocialHandleFinder
    from sharpqa_agent.enrichers.tech_stack_detector import TechStackDetector

    leads = await get_leads(db_path, status="new", limit=limit)
    contact_enricher = ContactEnricher(headless=settings.playwright_headless)
    tech_detector = TechStackDetector()
    social_finder = SocialHandleFinder()
    email_guesser = EmailPatternGuesser()

    processed = 0
    for lead in leads:
        try:
            add_log(run_id, f"  Enriching: {lead.company_name}")

            # Contacts
            contacts = await contact_enricher.enrich(lead.lead_id, lead.website_url)
            for contact in contacts:
                await insert_contact(db_path, contact)

            # If no email found, try guessing
            if contacts and not any(c.email_address for c in contacts):
                for contact in contacts:
                    if contact.full_name:
                        guesses = await email_guesser.guess_emails(contact.full_name, lead.website_url)
                        if guesses:
                            contact.email_address = guesses[0]["email"]
                            contact.email_confidence = guesses[0]["confidence"]
                            await insert_contact(db_path, contact)
                        break

            # Tech stack
            tech = await tech_detector.detect(lead.lead_id, lead.website_url)
            for t in tech:
                await insert_tech_stack(db_path, t)

            # Social handles
            handles = await social_finder.find_handles(lead.website_url)
            # Store on primary contact if available
            if contacts and handles:
                primary = next((c for c in contacts if c.is_primary_contact), contacts[0])
                if "twitter" in handles and not primary.twitter_handle:
                    primary.twitter_handle = handles["twitter"]
                if "linkedin_person" in handles and not primary.linkedin_url:
                    primary.linkedin_url = handles["linkedin_person"]

            await update_lead_status(db_path, lead.lead_id, "enriched")
            processed += 1

        except Exception as error:
            add_log(run_id, f"  Enrichment failed for {lead.company_name}: {error}")
            logger.warning("enrichment_failed", lead_id=lead.lead_id, error=str(error))

    return processed


async def _run_analyze_stage(db_path: str, limit: int, settings, run_id: str) -> int:
    """Run website analyzers on enriched leads."""
    from sharpqa_agent.analyzers.axe_runner import AxeRunner
    from sharpqa_agent.analyzers.finding_normalizer import deduplicate_findings, normalize_finding
    from sharpqa_agent.analyzers.finding_severity import assess_business_impact
    from sharpqa_agent.analyzers.lighthouse_runner import LighthouseRunner
    from sharpqa_agent.analyzers.playwright_auditor import PlaywrightAuditor
    from sharpqa_agent.analyzers.security_header_checker import SecurityHeaderChecker

    leads = await get_leads(db_path, status="enriched", limit=limit)

    playwright_auditor = PlaywrightAuditor(
        headless=settings.playwright_headless,
        screenshots_dir=settings.screenshots_dir,
    )
    lighthouse_runner = LighthouseRunner()
    axe_runner = AxeRunner(headless=settings.playwright_headless)
    security_checker = SecurityHeaderChecker()

    semaphore = asyncio.Semaphore(settings.max_concurrent_analyzes)
    processed = 0

    async def analyze_lead(lead: Lead) -> None:
        nonlocal processed
        async with semaphore:
            try:
                add_log(run_id, f"  Analyzing: {lead.company_name}")
                all_findings = []

                # Run analyzers — catch per-analyzer errors
                for analyzer_name, analyzer_fn in [
                    ("playwright", lambda: playwright_auditor.analyze(lead.lead_id, lead.website_url)),
                    ("lighthouse", lambda: lighthouse_runner.analyze(lead.lead_id, lead.website_url)),
                    ("axe", lambda: axe_runner.analyze(lead.lead_id, lead.website_url)),
                    ("security", lambda: security_checker.analyze(lead.lead_id, lead.website_url)),
                ]:
                    try:
                        findings = await analyzer_fn()
                        all_findings.extend(findings)
                    except Exception as error:
                        add_log(run_id, f"    {analyzer_name} failed for {lead.company_name}: {error}")

                # Normalize, assess impact, and deduplicate
                all_findings = [normalize_finding(f) for f in all_findings]
                all_findings = [assess_business_impact(f) for f in all_findings]
                all_findings = deduplicate_findings(all_findings)

                # Store findings
                for finding in all_findings:
                    await insert_finding(db_path, finding)

                await update_lead_status(db_path, lead.lead_id, "analyzed")
                processed += 1
                add_log(run_id, f"    {lead.company_name}: {len(all_findings)} findings")

            except Exception as error:
                add_log(run_id, f"  Analysis failed for {lead.company_name}: {error}")

    # Run analysis with concurrency control
    tasks = [analyze_lead(lead) for lead in leads]
    await asyncio.gather(*tasks)
    return processed


async def _run_prioritize_stage(db_path: str, limit: int, settings, run_id: str) -> int:
    """Score and rank analyzed leads."""
    from sharpqa_agent.prioritizer.lead_scorer import LeadScorer

    leads = await get_leads(db_path, status="analyzed", limit=limit)
    scorer = LeadScorer()
    processed = 0

    for lead in leads:
        try:
            findings = await get_findings_for_lead(db_path, lead.lead_id)
            contacts = await get_contacts_for_lead(db_path, lead.lead_id)
            tech_stack = await get_tech_stack_for_lead(db_path, lead.lead_id)

            score = scorer.score_lead(lead, findings, contacts, tech_stack)
            await update_lead_priority(db_path, lead.lead_id, score)
            add_log(run_id, f"  {lead.company_name}: score={score:.2f}")
            processed += 1

        except Exception as error:
            add_log(run_id, f"  Scoring failed for {lead.company_name}: {error}")

    return processed


async def _run_draft_stage(db_path: str, limit: int, settings, run_id: str) -> int:
    """Generate email drafts for high-priority analyzed leads."""
    from sharpqa_agent.drafter.email_drafter import EmailDrafter
    from sharpqa_agent.drafter.rag_retriever import RagRetriever

    llm = OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model_name,
        timeout=settings.ollama_timeout_seconds,
    )

    rag = RagRetriever(persist_dir=settings.chroma_persist_dir)
    rag.ensure_templates_seeded()

    drafter = EmailDrafter(
        llm_client=llm,
        rag_retriever=rag,
        operator_name=settings.operator_name,
        operator_company=settings.operator_company,
    )

    # Get analyzed leads above the priority threshold
    leads = await get_leads(
        db_path,
        status="analyzed",
        min_score=settings.min_priority_score_for_drafting,
        limit=limit,
    )

    processed = 0
    for lead in leads:
        try:
            add_log(run_id, f"  Drafting for: {lead.company_name}")
            findings = await get_findings_for_lead(db_path, lead.lead_id)
            contacts = await get_contacts_for_lead(db_path, lead.lead_id)
            tech_stack = await get_tech_stack_for_lead(db_path, lead.lead_id)

            primary_contact = next((c for c in contacts if c.is_primary_contact), contacts[0] if contacts else None)

            draft = await drafter.generate_draft(lead, findings, primary_contact, tech_stack)
            await insert_draft(db_path, draft)
            await update_lead_status(db_path, lead.lead_id, "drafted")
            processed += 1

        except Exception as error:
            add_log(run_id, f"  Draft failed for {lead.company_name}: {error}")
            logger.warning("draft_failed", lead_id=lead.lead_id, error=str(error))

    return processed
