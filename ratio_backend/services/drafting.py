"""LLM-backed first-pass assessment drafting focused on scores and rationale."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..core.config import Settings, get_settings
from ..core.logging import get_logger
from ..domain import AssessmentRecord, EvidenceItem, FactorAssessment, FactorScores, LLMDraftMetadata
from ..integrations.llm import get_provider
from .sizing import calculate_sizing

logger = get_logger(__name__)

PROMPT_VERSION = "assessment-draft-v1"


@dataclass(slots=True)
class DraftAssessmentInput:
    """Inputs required to generate a first-pass assessment draft."""

    ticker: str
    company_name: str
    source_documents: list[EvidenceItem]
    as_of_date: str | None = None


def _normalize_text(text: str) -> str:
    """Normalize evidence text before prompt assembly."""
    return re.sub(r"\s+", " ", (text or "").strip())


def _render_source_documents(documents: list[EvidenceItem], max_chars: int = 30_000) -> str:
    """Render source documents into a prompt-friendly evidence block."""
    rendered_parts: list[str] = []
    used = 0
    for document in sorted(documents, key=_document_sort_key, reverse=True):
        text = _normalize_text(document.content)
        chunk = (
            f"Source Type: {document.source_type.value}\n"
            f"Title: {document.title or '(untitled)'}\n"
            f"Author: {document.author_email or 'unknown'}\n"
            f"Timestamp: {document.source_timestamp or document.ingested_at or 'unknown'}\n"
            f"Body: {text}\n\n"
        )
        if used + len(chunk) > max_chars:
            break
        rendered_parts.append(chunk)
        used += len(chunk)
    return "".join(rendered_parts)


def _document_sort_key(document: EvidenceItem) -> float:
    """Sort documents newest-first using any available timestamp."""
    timestamp = document.source_timestamp or document.ingested_at
    if isinstance(timestamp, datetime):
        return timestamp.timestamp()
    return 0.0


def _extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object from an LLM response."""
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    direct = re.search(r"(\{.*\})", raw_text, flags=re.DOTALL)
    if direct:
        return json.loads(direct.group(1))

    raise ValueError("Draft response did not contain a JSON object")


def _build_factor_assessments(payload: dict[str, Any], settings: Settings) -> tuple[FactorScores, list[FactorAssessment]]:
    """Convert an LLM draft payload into domain factor objects."""
    factor_payload = payload.get("factor_scores") or {}
    assessments = [
        FactorAssessment(
            factor_key="debt",
            factor_label="Debt",
            score=int((factor_payload.get("debt") or {}).get("score", 0)),
            score_min=0,
            score_max=settings.factor_score_max,
            internal_rationale=(factor_payload.get("debt") or {}).get("rationale"),
            sort_order=1,
        ),
        FactorAssessment(
            factor_key="market_share_change",
            factor_label="Change in Market Share",
            score=int((factor_payload.get("market_share_change") or {}).get("score", 0)),
            score_min=0,
            score_max=settings.factor_score_max,
            internal_rationale=(factor_payload.get("market_share_change") or {}).get("rationale"),
            sort_order=2,
        ),
        FactorAssessment(
            factor_key="market_definition_change",
            factor_label="Change in Definition of Market",
            score=int((factor_payload.get("market_definition_change") or {}).get("score", 0)),
            score_min=0,
            score_max=settings.factor_score_max,
            internal_rationale=(factor_payload.get("market_definition_change") or {}).get("rationale"),
            sort_order=3,
        ),
        FactorAssessment(
            factor_key="relative_valuation",
            factor_label="Relative Valuation",
            score=int((factor_payload.get("relative_valuation") or {}).get("score", 0)),
            score_min=0,
            score_max=settings.factor_score_max,
            internal_rationale=(factor_payload.get("relative_valuation") or {}).get("rationale"),
            sort_order=4,
        ),
    ]
    scores = FactorScores(
        debt=assessments[0].score,
        market_share_change=assessments[1].score,
        market_definition_change=assessments[2].score,
        relative_valuation=assessments[3].score,
    )
    scores.validate(max_score=settings.factor_score_max)
    return scores, assessments


async def generate_assessment_draft_async(
    draft_input: DraftAssessmentInput,
    *,
    settings: Settings | None = None,
    model_name: str | None = None,
) -> AssessmentRecord:
    """Generate a first-pass assessment draft from source documents."""
    active_settings = settings or get_settings()
    llm = get_provider()
    evidence_blob = _render_source_documents(draft_input.source_documents)

    system_prompt = f"""You are an expert financial analyst producing a first-pass internal assessment draft for Ratio.

Use the four-factor scoring method exactly as defined below:
- debt
- market_share_change
- market_definition_change
- relative_valuation

Rules:
- Each score must be an integer from 0 to {active_settings.factor_score_max}.
- Higher score means higher risk.
- Return only JSON.
- The output is internal and should include concise factor rationale plus assumptions.
- Do not fabricate evidence beyond reasonable inference from the supplied documents.

Return this shape:
{{
  "factor_scores": {{
    "debt": {{ "score": 0, "rationale": "..." }},
    "market_share_change": {{ "score": 0, "rationale": "..." }},
    "market_definition_change": {{ "score": 0, "rationale": "..." }},
    "relative_valuation": {{ "score": 0, "rationale": "..." }}
  }},
  "assumptions": ["..."],
  "confidence": "low|medium|high"
}}"""

    user_prompt = (
        f"Ticker: {draft_input.ticker}\n"
        f"Company: {draft_input.company_name}\n"
        f"As Of Date: {draft_input.as_of_date or 'not provided'}\n\n"
        "Source documents:\n\n"
        f"{evidence_blob}"
    )

    logger.info(
        "Generating assessment draft",
        extra={"ticker": draft_input.ticker, "document_count": len(draft_input.source_documents)},
    )
    raw_response = await llm.generate_content_async(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_name=model_name,
        temperature=0.2,
        max_output_tokens=3000,
    )
    payload = _extract_json_object(raw_response)
    scores, factors = _build_factor_assessments(payload, active_settings)
    sizing = calculate_sizing(scores, active_settings)

    return AssessmentRecord(
        company_id=0,
        factor_scores=scores,
        sizing=sizing,
        aggregate_score=sizing.total_score,
        relative_score=sizing.normalized_score,
        beta_like_score=sizing.custom_beta,
        calculation_version=active_settings.default_methodology_version,
        llm_metadata=LLMDraftMetadata(
            provider=getattr(llm, "__class__", type(llm)).__name__,
            model=model_name,
            prompt_version=PROMPT_VERSION,
            assumptions=[str(item) for item in payload.get("assumptions", [])],
            raw_response=raw_response,
        ),
        as_of_date=None,
        factors=factors,
    )


def generate_assessment_draft(
    draft_input: DraftAssessmentInput,
    *,
    settings: Settings | None = None,
    model_name: str | None = None,
) -> AssessmentRecord:
    """Synchronous wrapper for LLM-backed draft generation."""
    return asyncio.run(generate_assessment_draft_async(draft_input, settings=settings, model_name=model_name))
