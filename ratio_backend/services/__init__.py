"""Business services that orchestrate domain logic and integrations."""

__all__ = [
    "DraftAssessmentInput",
    "calculate_sizing",
    "collect_evidence_for_ticker",
    "collect_evidence_for_ticker_async",
    "generate_assessment_draft",
    "generate_assessment_draft_async",
    "generate_assessment_draft_for_ticker",
    "generate_assessment_draft_for_ticker_async",
]


def __getattr__(name: str):
    """Lazily expose service entrypoints without eagerly importing submodules."""
    if name == "calculate_sizing":
        from .sizing import calculate_sizing

        return calculate_sizing
    if name in {"DraftAssessmentInput", "generate_assessment_draft", "generate_assessment_draft_async"}:
        from .drafting import DraftAssessmentInput, generate_assessment_draft, generate_assessment_draft_async

        return {
            "DraftAssessmentInput": DraftAssessmentInput,
            "generate_assessment_draft": generate_assessment_draft,
            "generate_assessment_draft_async": generate_assessment_draft_async,
        }[name]
    if name in {"collect_evidence_for_ticker", "collect_evidence_for_ticker_async", "generate_assessment_draft_for_ticker", "generate_assessment_draft_for_ticker_async"}:
        from .pipeline import (
            collect_evidence_for_ticker,
            collect_evidence_for_ticker_async,
            generate_assessment_draft_for_ticker,
            generate_assessment_draft_for_ticker_async,
        )

        return {
            "collect_evidence_for_ticker": collect_evidence_for_ticker,
            "collect_evidence_for_ticker_async": collect_evidence_for_ticker_async,
            "generate_assessment_draft_for_ticker": generate_assessment_draft_for_ticker,
            "generate_assessment_draft_for_ticker_async": generate_assessment_draft_for_ticker_async,
        }[name]
    raise AttributeError(name)
