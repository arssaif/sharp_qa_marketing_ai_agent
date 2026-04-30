"""Ollama LLM client wrapper for local model inference."""

from __future__ import annotations

import json

import httpx

from sharpqa_agent.core.exceptions import LLMError
from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)


class OllamaClient:
    """Async client for the Ollama local LLM API.

    Provides both streaming and non-streaming generation, plus model availability checks.
    """

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1:8b-instruct-q4_K_M",
                 timeout: int = 120) -> None:
        """Initialize the Ollama client.

        Args:
            base_url: Ollama server URL.
            model: Model name to use for generation.
            timeout: Request timeout in seconds.
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        """Generate a completion from the LLM.

        Args:
            prompt: The user prompt to send.
            system: Optional system prompt.
            temperature: Sampling temperature (0.0 to 1.0).

        Returns:
            The generated text response.

        Raises:
            LLMError: If the request fails or Ollama is unreachable.
        """
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except httpx.ConnectError as error:
            raise LLMError(f"Cannot connect to Ollama at {self.base_url}. Is it running?") from error
        except httpx.HTTPStatusError as error:
            raise LLMError(f"Ollama returned {error.response.status_code}: {error.response.text}") from error
        except Exception as error:
            raise LLMError(f"LLM generation failed: {error}") from error

    async def generate_streaming(self, prompt: str, system: str | None = None,
                                  temperature: float = 0.7):
        """Generate a streaming completion from the LLM.

        Args:
            prompt: The user prompt.
            system: Optional system prompt.
            temperature: Sampling temperature.

        Yields:
            Text chunks as they arrive from the model.

        Raises:
            LLMError: If the request fails.
        """
        payload: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if system:
            payload["system"] = system

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            if text := chunk.get("response"):
                                yield text
                            if chunk.get("done"):
                                break
        except httpx.ConnectError as error:
            raise LLMError(f"Cannot connect to Ollama at {self.base_url}") from error
        except Exception as error:
            raise LLMError(f"LLM streaming failed: {error}") from error

    async def is_available(self) -> bool:
        """Check if Ollama is running and the model is loaded.

        Returns:
            True if the server responds and the model is available.
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                # Check if our model (or a prefix match) exists
                return any(self.model.split(":")[0] in name for name in model_names)
        except Exception:
            return False

    async def pull_model(self) -> None:
        """Pull the configured model via Ollama API.

        Raises:
            LLMError: If the pull fails.
        """
        try:
            async with httpx.AsyncClient(timeout=600) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": self.model, "stream": False},
                )
                response.raise_for_status()
                logger.info("model_pulled", model=self.model)
        except Exception as error:
            raise LLMError(f"Failed to pull model {self.model}: {error}") from error
