"""Abstract provider contract for asynchronous LLM calls."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Shared interface for all configured LLM backends."""

    @abstractmethod
    async def generate_content_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        temperature: float = 0.5,
        max_output_tokens: int | None = None,
    ) -> str:
        """Return raw model output text for the supplied prompts."""
