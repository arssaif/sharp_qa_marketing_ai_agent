"""RAG retriever — queries ChromaDB for similar past email templates to use as few-shot examples."""

from __future__ import annotations

from sharpqa_agent.core.logging_setup import get_logger
from sharpqa_agent.core.vector_store import query_similar, seed_templates_from_directory

logger = get_logger(__name__)


class RagRetriever:
    """Retrieve similar email templates from the vector store for few-shot prompting.

    Builds a semantic query from the lead's finding category, industry, and funding stage,
    then retrieves the most similar past templates from ChromaDB.
    """

    def __init__(self, persist_dir: str = "data/chroma", collection_name: str = "email_templates") -> None:
        self.persist_dir = persist_dir
        self.collection_name = collection_name

    def ensure_templates_seeded(self, templates_dir: str = "config/email_templates") -> int:
        """Seed the vector store with email templates if not already populated.

        Args:
            templates_dir: Path to directory containing .md template files.

        Returns:
            Number of templates loaded (0 if already seeded).
        """
        return seed_templates_from_directory(templates_dir, self.collection_name, self.persist_dir)

    def retrieve_similar_templates(
        self,
        finding_category: str,
        industry: str = "",
        funding_stage: str = "",
        n_results: int = 2,
    ) -> list[str]:
        """Retrieve similar email templates for the given context.

        Args:
            finding_category: The primary finding category (e.g., 'performance').
            industry: Industry description of the target company.
            funding_stage: Funding stage (e.g., 'seed', 'series_a').
            n_results: Number of templates to return.

        Returns:
            List of template text strings, most similar first.
        """
        # Build a semantic query
        query_parts = [finding_category]
        if industry:
            query_parts.append(industry)
        if funding_stage:
            query_parts.append(f"{funding_stage} startup")
        query_parts.append("cold outreach email")

        query_text = " ".join(query_parts)

        results = query_similar(
            query_text=query_text,
            n_results=n_results,
            collection_name=self.collection_name,
            persist_dir=self.persist_dir,
        )

        templates = [r["document"] for r in results if r.get("document")]
        logger.info("rag_retrieved", query=query_text[:80], results=len(templates))
        return templates
