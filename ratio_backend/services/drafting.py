"""LLM-backed first-pass assessment drafting focused on scores and rationale."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime
from textwrap import dedent
from typing import Any

from ..core.config import Settings, get_settings
from ..core.logging import get_logger
from ..domain import AssessmentRecord, EvidenceItem, FactorAssessment, FactorScores, LLMDraftMetadata
from ..integrations.llm import get_provider
from .sizing import calculate_sizing

logger = get_logger(__name__)

PROMPT_VERSION = "assessment-draft-v3"


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
    candidates = [raw_text.strip()]

    fenced = re.search(r"```json\s*(\{.*?\})\s*```", raw_text, flags=re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1))

    balanced = _extract_balanced_json_candidate(raw_text)
    if balanced:
        candidates.append(balanced)

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    if last_error is not None:
        raise ValueError(f"Draft response JSON was invalid or truncated: {last_error}") from last_error
    raise ValueError("Draft response did not contain a JSON object")


def _extract_balanced_json_candidate(raw_text: str) -> str | None:
    """Return the first balanced top-level JSON object candidate from free-form text."""
    start = raw_text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(raw_text)):
        char = raw_text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw_text[start : index + 1]

    return raw_text[start:].strip() or None


def _build_factor_assessments(payload: dict[str, Any], settings: Settings) -> tuple[FactorScores, list[FactorAssessment]]:
    """Convert an LLM draft payload into domain factor objects."""
    factor_payload = payload.get("factor_scores") or {}
    assessments = [
        FactorAssessment(
            factor_key="debt",
            factor_label="Debt",
            score=int((factor_payload.get("debt") or {}).get("score", 0)),
            score_min=0,
            score_max=10,
            internal_rationale=(factor_payload.get("debt") or {}).get("rationale"),
            sort_order=1,
        ),
        FactorAssessment(
            factor_key="market_share_change",
            factor_label="Change in Market Share",
            score=int((factor_payload.get("market_share_change") or {}).get("score", 0)),
            score_min=0,
            score_max=10,
            internal_rationale=(factor_payload.get("market_share_change") or {}).get("rationale"),
            sort_order=2,
        ),
        FactorAssessment(
            factor_key="market_definition_change",
            factor_label="Change in Definition of Market",
            score=int((factor_payload.get("market_definition_change") or {}).get("score", 0)),
            score_min=0,
            score_max=10,
            internal_rationale=(factor_payload.get("market_definition_change") or {}).get("rationale"),
            sort_order=3,
        ),
        FactorAssessment(
            factor_key="relative_valuation",
            factor_label="Relative Valuation",
            score=int((factor_payload.get("relative_valuation") or {}).get("score", 0)),
            score_min=0,
            score_max=10,
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
    scores.validate()
    return scores, assessments


def _build_system_prompt(settings: Settings) -> str:
    """Build the system prompt from the documented factor and sizing methodology."""
    max_total_score = 10 * settings.factor_count
    benchmark_normalized_score = settings.benchmark_total_score / max_total_score
    max_position_line = (
        f"- max_position_size cap = {settings.max_position_size}"
        if settings.max_position_size is not None
        else "- max_position_size cap = none"
    )

    return dedent(
        f"""
        You are an expert financial analyst producing a first-pass internal assessment draft for Ratio.

        Your job is to score one company on exactly four factors, explain the reasoning concisely,
        and produce a draft set of calculations that match the Ratio sizing methodology.
        This is an internal draft only. Human review determines the final published assessment.

        METHODOLOGY OVERVIEW
        - Each factor is scored from 0 to 10.
        - Higher score means higher risk and a higher beta contribution.
        - Lower score means lower risk and a lower beta contribution.
        - The four factor scores are additive and all four are required.
        - Use exactly these four factors:
          1. debt
          2. market_share_change
          3. market_definition_change
          4. relative_valuation
        - The objective is not to predict a stock move directly. The objective is to translate
          qualitative company risk into a consistent beta-like sizing input.

        FACTOR SCORING GUIDANCE
        - debt:
          - low (0-3): strong balance sheet, low leverage, ample flexibility
          - high (7-10): heavy leverage, refinancing risk, constrained flexibility
          - what matters: leverage, maturity wall, interest burden, covenant pressure, liquidity
        - market_share_change:
          - low: stable or improving share
          - high: declining share, competitive pressure, customer loss
          - what matters: customer wins/losses, channel checks, pricing pressure, unit growth versus peers
        - market_definition_change:
          - low: stable market structure and value chain
          - high: disruption, platform shift, value-chain change, structural market redefinition
          - what matters: whether the company's category is being redefined by technology, regulation,
            distribution shifts, or changing buyer behavior
        - relative_valuation:
          - low: inexpensive valuation, muted expectations, margin of safety
          - high: expensive valuation, demanding expectations, limited room for disappointment
          - what matters: valuation versus peers/history, quality of the multiple, and how much
            future success appears already priced in

        SCORING PHILOSOPHY
        - A score near 0 means the factor contributes little risk.
        - A score near 10 means the factor contributes substantial risk.
        - Use the middle of the range for mixed evidence or ordinary risk.
        - Reserve extreme scores for unusually clear evidence.
        - When evidence is thin, avoid fake precision and explain the uncertainty in `assumptions`.

        SIZING LOGIC CONTEXT
        - total_score = debt + market_share_change + market_definition_change + relative_valuation
        - max_total_score = {max_total_score}
        - normalized_score = total_score / max_total_score
        - benchmark_total_score = {settings.benchmark_total_score}
        - benchmark_normalized_score = {benchmark_normalized_score:.2f}
        - raw_beta = total_score / {settings.benchmark_total_score}
        - custom_beta = max(raw_beta, {settings.beta_floor})
        - base_position_size = {settings.base_position_size}
        - suggested_position_size = base_position_size / custom_beta
        {max_position_line}
        - lower total score implies lower beta and a larger position
        - higher total score implies higher beta and a smaller position
        - benchmark interpretation: a total_score of {settings.benchmark_total_score} maps to custom_beta 1.0,
          which corresponds to the base position size
        - the system will recompute the calculations independently, so your main task is to choose
          defensible scores and rationale that support the math

        WORKED EXAMPLE
        - Example factor scores: debt=4, market_share_change=6, market_definition_change=5, relative_valuation=3
        - Example total_score = 18
        - Example normalized_score = 18 / {max_total_score} = {18 / max_total_score:.3f}
        - Example raw_beta = 18 / {settings.benchmark_total_score} = {18 / settings.benchmark_total_score:.3f}
        - Example custom_beta = max({18 / settings.benchmark_total_score:.3f}, {settings.beta_floor}) = {max(18 / settings.benchmark_total_score, settings.beta_floor):.3f}
        - Example suggested_position_size = {settings.base_position_size} / {max(18 / settings.benchmark_total_score, settings.beta_floor):.3f} = {settings.base_position_size / max(18 / settings.benchmark_total_score, settings.beta_floor):.4f}

        ANALYST INSTRUCTIONS
        - Ground scores in the supplied evidence.
        - Weight more recent evidence more heavily, but keep durable structural evidence in mind.
        - If evidence is mixed, acknowledge the tension in the rationale and choose the most defensible single score.
        - Tie each rationale to concrete signals from the documents, not generic market commentary.
        - If there is not enough evidence for a factor, say that explicitly in the rationale or assumptions.
        - Keep each factor rationale brief: 1-2 sentences and under 50 words when possible.
        - Keep the assumptions list short and concrete.
        - Do not fabricate company facts that are not supported or reasonably inferred from the documents.
        - Do not return score ranges. Return one integer score per factor.
        - Put missing information, uncertainty, or inference gaps into `assumptions`.
        - Return only JSON and no surrounding commentary.

        Return this shape:
        {{
          "factor_scores": {{
            "debt": {{ "score": 0, "rationale": "..." }},
            "market_share_change": {{ "score": 0, "rationale": "..." }},
            "market_definition_change": {{ "score": 0, "rationale": "..." }},
            "relative_valuation": {{ "score": 0, "rationale": "..." }}
          }},
          "calculations": {{
            "total_score": 0,
            "normalized_score": 0.0,
            "custom_beta": 0.0,
            "base_position_size": {settings.base_position_size},
            "suggested_position_size": 0.0
          }},
          "assumptions": ["..."],
          "confidence": "low|medium|high"
        }}
        """
    ).strip()


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
    system_prompt = _build_system_prompt(active_settings)

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
        max_output_tokens=5000,
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
