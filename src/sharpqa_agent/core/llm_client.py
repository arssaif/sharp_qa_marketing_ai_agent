"""LLM client wrappers for local (Ollama) and cloud (Gemini) model inference."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator

import httpx

from sharpqa_agent.core.exceptions import LLMError
from sharpqa_agent.core.logging_setup import get_logger

logger = get_logger(__name__)


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        """Generate a completion from the LLM."""
        pass

    @abstractmethod
    async def generate_streaming(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Generate a streaming completion from the LLM."""
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM service is available."""
        pass

    @abstractmethod
    async def pull_model(self) -> None:
        """Pull the configured model if applicable."""
        pass


class OllamaClient(BaseLLMClient):
    """Async client for the Ollama local LLM API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.1:8b-instruct-q4_K_M",
                 timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
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
                                  temperature: float = 0.7) -> AsyncGenerator[str, None]:
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
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code != 200:
                    return False
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                return any(self.model.split(":")[0] in name for name in model_names)
        except Exception:
            return False

    async def pull_model(self) -> None:
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


class GeminiClient(BaseLLMClient):
    """Async client for the Google Gemini API."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required when using the Gemini provider. Please set it in your .env file.")
        
        # We import here so that google-genai is only strictly required if using Gemini
        try:
            from google import genai
            self.client = genai.Client(api_key=api_key)
        except ImportError:
            raise LLMError("google-genai package is not installed. Run: uv add google-genai")
            
        self.model = model

    async def generate(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> str:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system
            )
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )
            return response.text or ""
        except Exception as error:
            raise LLMError(f"Gemini generation failed: {error}") from error

    async def generate_streaming(self, prompt: str, system: str | None = None, temperature: float = 0.7) -> AsyncGenerator[str, None]:
        try:
            from google.genai import types
            config = types.GenerateContentConfig(
                temperature=temperature,
                system_instruction=system
            )
            response_stream = await self.client.aio.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config
            )
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as error:
            raise LLMError(f"Gemini streaming failed: {error}") from error

    async def is_available(self) -> bool:
        return True

    async def pull_model(self) -> None:
        # Cloud models don't need pulling
        pass


def get_llm_client(settings) -> BaseLLMClient:
    """Factory to get the configured LLM client."""
    provider = getattr(settings, "llm_provider", "ollama").lower()
    
    if provider == "gemini":
        return GeminiClient(api_key=settings.gemini_api_key)
        
    return OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model_name,
        timeout=settings.ollama_timeout_seconds
    )
