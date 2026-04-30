"""Warmup script — pulls the configured LLM model via Ollama on first run."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from sharpqa_agent.core.llm_client import OllamaClient


async def main() -> None:
    settings = get_settings()
    client = OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model_name,
    )

    print(f"Checking Ollama at {settings.ollama_base_url}...")

    if not await client.is_available():
        print(f"Model '{settings.ollama_model_name}' not found. Pulling...")
        try:
            await client.pull_model()
            print("Model pulled successfully!")
        except Exception as e:
            print(f"Failed to pull model: {e}")
            print(f"\nManually run: ollama pull {settings.ollama_model_name}")
            sys.exit(1)
    else:
        print(f"Model '{settings.ollama_model_name}' is available.")

    # Quick test generation
    print("\nRunning test generation...")
    try:
        response = await client.generate("Say hello in one sentence.", temperature=0.5)
        print(f"LLM response: {response[:100]}")
        print("\nOllama is ready!")
    except Exception as e:
        print(f"Generation test failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
