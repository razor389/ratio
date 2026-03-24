"""Factory for selecting the configured LLM provider implementation."""

from __future__ import annotations

import os

from .base import LLMProvider


def get_provider() -> LLMProvider:
    """Instantiate the provider selected by the `LLM_PROVIDER` environment variable."""
    provider_name = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    if provider_name == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider()
    if provider_name == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider()

    from .gemini import GeminiProvider

    return GeminiProvider()
