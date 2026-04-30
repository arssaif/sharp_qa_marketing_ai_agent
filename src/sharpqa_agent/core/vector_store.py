"""ChromaDB vector store wrapper for email template RAG."""

from __future__ import annotations

from pathlib import Path

import chromadb

from sharpqa_agent.core.exceptions import VectorStoreError
from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)

_client_cache: dict[str, chromadb.ClientAPI] = {}


def get_chroma_client(persist_dir: str = "data/chroma") -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client.

    Args:
        persist_dir: Directory where ChromaDB stores its data.

    Returns:
        A ChromaDB client instance.
    """
    if persist_dir not in _client_cache:
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        _client_cache[persist_dir] = chromadb.PersistentClient(path=persist_dir)
        logger.info("chroma_client_initialized", persist_dir=persist_dir)
    return _client_cache[persist_dir]


def get_or_create_collection(
    collection_name: str = "email_templates",
    persist_dir: str = "data/chroma",
) -> chromadb.Collection:
    """Get or create a ChromaDB collection.

    Args:
        collection_name: Name of the collection.
        persist_dir: Directory for ChromaDB persistence.

    Returns:
        A ChromaDB Collection.
    """
    client = get_chroma_client(persist_dir)
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def add_documents(
    documents: list[str],
    metadatas: list[dict] | None = None,
    ids: list[str] | None = None,
    collection_name: str = "email_templates",
    persist_dir: str = "data/chroma",
) -> None:
    """Add documents to the vector store.

    Args:
        documents: Text documents to store and embed.
        metadatas: Optional metadata dicts for each document.
        ids: Optional unique IDs for each document.
        collection_name: Target collection name.
        persist_dir: ChromaDB persistence directory.

    Raises:
        VectorStoreError: If insertion fails.
    """
    try:
        collection = get_or_create_collection(collection_name, persist_dir)
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
        logger.info("documents_added", count=len(documents), collection=collection_name)
    except Exception as error:
        raise VectorStoreError(f"Failed to add documents: {error}") from error


def query_similar(
    query_text: str,
    n_results: int = 3,
    collection_name: str = "email_templates",
    persist_dir: str = "data/chroma",
) -> list[dict]:
    """Query the vector store for similar documents.

    Args:
        query_text: The text to find similar documents for.
        n_results: Number of results to return.
        collection_name: Collection to search.
        persist_dir: ChromaDB persistence directory.

    Returns:
        List of dicts with 'document', 'metadata', 'distance' keys.

    Raises:
        VectorStoreError: If the query fails.
    """
    try:
        collection = get_or_create_collection(collection_name, persist_dir)
        if collection.count() == 0:
            return []
        results = collection.query(query_texts=[query_text], n_results=min(n_results, collection.count()))
        output = []
        for i in range(len(results["documents"][0])):
            output.append({
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0.0,
            })
        return output
    except Exception as error:
        raise VectorStoreError(f"Vector query failed: {error}") from error


def seed_templates_from_directory(
    templates_dir: str | Path,
    collection_name: str = "email_templates",
    persist_dir: str = "data/chroma",
) -> int:
    """Load email template files from a directory into the vector store.

    Args:
        templates_dir: Path to directory containing .md template files.
        collection_name: Target collection.
        persist_dir: ChromaDB persistence directory.

    Returns:
        Number of templates loaded.
    """
    templates_path = Path(templates_dir)
    if not templates_path.exists():
        logger.warning("templates_dir_not_found", path=str(templates_path))
        return 0

    documents = []
    metadatas = []
    ids = []

    for template_file in sorted(templates_path.glob("*.md")):
        content = template_file.read_text(encoding="utf-8").strip()
        if content:
            documents.append(content)
            metadatas.append({"filename": template_file.name, "source": "seed_template"})
            ids.append(f"template_{template_file.stem}")

    if documents:
        add_documents(documents, metadatas, ids, collection_name, persist_dir)
        logger.info("templates_seeded", count=len(documents))

    return len(documents)
