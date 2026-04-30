"""Sentence-transformers embedding wrapper for local vector similarity."""

from __future__ import annotations

from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)

_model_cache: dict = {}


def get_embedding_model(model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
    """Load and cache a sentence-transformers model.

    Args:
        model_name: HuggingFace model identifier.

    Returns:
        A SentenceTransformer model instance.
    """
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        logger.info("loading_embedding_model", model=model_name)
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def embed_texts(texts: list[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> list[list[float]]:
    """Embed a list of texts into dense vectors.

    Args:
        texts: Strings to embed.
        model_name: HuggingFace model identifier.

    Returns:
        List of embedding vectors (each a list of floats).
    """
    model = get_embedding_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


def embed_single(text: str, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> list[float]:
    """Embed a single text string.

    Args:
        text: String to embed.
        model_name: HuggingFace model identifier.

    Returns:
        Embedding vector as a list of floats.
    """
    return embed_texts([text], model_name)[0]
