"""OpenAI-backed implementation of the shared LLM provider interface."""

from __future__ import annotations

import os

from ...core.logging import get_logger
from .base import LLMProvider

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """Use the OpenAI Chat Completions API for async text generation."""

    def __init__(self) -> None:
        from openai import AsyncOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment.")
        self.client = AsyncOpenAI(api_key=api_key)

    async def generate_content_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        temperature: float = 0.5,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate text using the configured OpenAI model."""
        resolved_model = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
        max_tokens = max_output_tokens or 4096

        logger.info("Calling OpenAI provider", extra={"model_name": resolved_model})
        try:
            response = await self.client.chat.completions.create(
                model=resolved_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            logger.exception("OpenAI provider call failed", extra={"model_name": resolved_model})
            return ""
