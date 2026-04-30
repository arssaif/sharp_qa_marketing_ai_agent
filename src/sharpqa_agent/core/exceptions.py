"""Custom exception hierarchy for the SharpQA agent."""


class SharpQAError(Exception):
    """Base exception for all SharpQA errors."""


class DatabaseError(SharpQAError):
    """Raised when a database operation fails."""


class SourcerError(SharpQAError):
    """Raised when a sourcer cannot fetch leads."""


class AnalyzerError(SharpQAError):
    """Raised when a website analysis step fails."""


class EnricherError(SharpQAError):
    """Raised when enrichment of a lead fails."""


class DrafterError(SharpQAError):
    """Raised when email draft generation fails."""


class LLMError(SharpQAError):
    """Raised when the local LLM is unreachable or returns an error."""


class VectorStoreError(SharpQAError):
    """Raised when ChromaDB operations fail."""


class PipelineError(SharpQAError):
    """Raised when the orchestration pipeline encounters a fatal error."""
