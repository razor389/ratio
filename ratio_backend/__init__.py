"""Python analysis and ingestion helpers for the Ratio project."""

__all__ = [
    "DraftAssessmentInput",
    "Settings",
    "calculate_sizing",
    "collect_evidence_for_ticker",
    "generate_assessment_draft",
    "generate_assessment_draft_async",
    "generate_assessment_draft_for_ticker",
    "generate_assessment_draft_for_ticker_async",
    "get_settings",
]


def __getattr__(name: str):
    """Lazily expose top-level Python analysis entrypoints."""
    if name in {"Settings", "get_settings"}:
        from .core.config import Settings, get_settings

        return {"Settings": Settings, "get_settings": get_settings}[name]
    if name in {
        "DraftAssessmentInput",
        "calculate_sizing",
        "collect_evidence_for_ticker",
        "generate_assessment_draft",
        "generate_assessment_draft_async",
        "generate_assessment_draft_for_ticker",
        "generate_assessment_draft_for_ticker_async",
    }:
        from . import services

        return getattr(services, name)
    raise AttributeError(name)
