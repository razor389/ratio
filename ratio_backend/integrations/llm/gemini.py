"""Gemini-backed implementation of the shared LLM provider interface."""

from __future__ import annotations

import json
import os

from google import genai
from google.genai import types

from ...core.logging import get_logger
from .base import LLMProvider

logger = get_logger(__name__)


class GeminiProvider(LLMProvider):
    """Use the Gemini SDK for async text generation."""

    def __init__(self) -> None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment. Please set it in your .env file.")
        self.client = genai.Client(api_key=api_key)

    async def generate_content_async(
        self,
        system_prompt: str,
        user_prompt: str,
        model_name: str | None = None,
        temperature: float = 0.5,
        max_output_tokens: int | None = None,
    ) -> str:
        """Generate text using the configured Gemini model."""
        resolved_model = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        logger.info("Calling Gemini provider", extra={"model_name": resolved_model})
        try:
            response = await self.client.aio.models.generate_content(
                model=resolved_model,
                contents=user_prompt,
                config=config,
            )
            response_text = getattr(response, "text", None)
            if not response_text and getattr(response, "parsed", None) is not None:
                response_text = json.dumps(response.parsed)

            finish_reason = getattr(response, "finish_reason", None)
            candidates = getattr(response, "candidates", None) or []
            if candidates and finish_reason is None:
                finish_reason = getattr(candidates[0], "finish_reason", None)
            if hasattr(finish_reason, "name"):
                finish_reason = finish_reason.name

            if finish_reason == "MAX_TOKENS" and response_text:
                logger.warning("Gemini response hit max tokens", extra={"model_name": resolved_model})
                return response_text.strip()
            return (response_text or "").strip()
        except ValueError:
            logger.exception("Gemini provider returned empty or blocked output", extra={"model_name": resolved_model})
            return ""
        except Exception:
            logger.exception("Gemini provider call failed", extra={"model_name": resolved_model})
            return ""
