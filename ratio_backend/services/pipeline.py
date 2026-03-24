"""End-to-end Python workflow for collecting evidence and drafting an assessment."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from ..core.logging import get_logger
from ..domain import AssessmentRecord, EvidenceItem, EvidenceSourceType
from ..ingestion.forum_posts import collect_forum_posts_for_ticker, write_forum_posts_snapshot
from ..ingestion.outlook_ticker_search import filter_emails_by_config, write_outlook_email_snapshot
from .drafting import DraftAssessmentInput, generate_assessment_draft_async

logger = get_logger(__name__)


def _to_datetime(timestamp: Any) -> datetime | None:
    """Convert a unix timestamp into a naive UTC datetime when possible."""
    if timestamp in (None, ""):
        return None
    try:
        return datetime.utcfromtimestamp(int(timestamp))
    except (TypeError, ValueError, OSError):
        return None


def _stringify_metadata(values: dict[str, Any]) -> dict[str, str]:
    """Normalize source metadata values into strings for domain transport."""
    return {key: str(value) for key, value in values.items() if value not in (None, "")}


def _build_forum_evidence_items(payload: dict[str, Any]) -> list[EvidenceItem]:
    """Adapt collected forum posts into draft-analysis evidence items."""
    items: list[EvidenceItem] = []

    for post in payload.get("posts", []):
        items.append(
            EvidenceItem(
                company_id=0,
                source_type=EvidenceSourceType.FORUM_POST,
                title=post.get("topicTitle") or f"{payload.get('ticker', 'UNKNOWN')} forum post",
                content=post.get("message", ""),
                external_source_id=str(post.get("postId")) if post.get("postId") is not None else None,
                author_email=post.get("authorEmail"),
                source_timestamp=_to_datetime(post.get("timestamp")),
                ingested_at=datetime.utcnow(),
                source_metadata=_stringify_metadata(
                    {
                        "topic_id": post.get("topicId"),
                        "topic_title": post.get("topicTitle"),
                        "category_id": post.get("categoryId"),
                        "category_title": post.get("categoryTitle"),
                    }
                ),
            )
        )

    return items


def _build_outlook_evidence_items(ticker: str, emails: list[dict[str, Any]]) -> list[EvidenceItem]:
    """Adapt collected Outlook emails into draft-analysis evidence items."""
    items: list[EvidenceItem] = []

    for email in emails:
        subject = email.get("subject") or f"{ticker} sent email"
        timestamp = email.get("timestamp")

        items.append(
            EvidenceItem(
                company_id=0,
                source_type=EvidenceSourceType.OUTLOOK_EMAIL,
                title=subject,
                content=email.get("message", ""),
                external_source_id=f"{timestamp}:{subject}" if timestamp else subject,
                author_email=email.get("authorEmail"),
                source_timestamp=_to_datetime(timestamp),
                ingested_at=datetime.utcnow(),
                source_uri=email.get("sourceFolder"),
                source_metadata=_stringify_metadata({"source_folder": email.get("sourceFolder")}),
            )
        )

    return items


def collect_evidence_for_ticker(
    ticker: str,
    *,
    include_forum: bool = True,
    include_outlook: bool = True,
    lookback_years: int = 15,
    persist_artifacts: bool = True,
) -> list[EvidenceItem]:
    """Collect all configured evidence sources for a ticker and normalize them for analysis."""
    normalized_ticker = ticker.upper()
    evidence_items: list[EvidenceItem] = []

    if include_forum:
        forum_payload = collect_forum_posts_for_ticker(normalized_ticker)
        if forum_payload:
            if persist_artifacts:
                write_forum_posts_snapshot(forum_payload["ticker"], forum_payload)
            forum_items = _build_forum_evidence_items(forum_payload)
            evidence_items.extend(forum_items)
            logger.info(
                "Collected forum evidence",
                extra={"ticker": normalized_ticker, "document_count": len(forum_items), "component": "ingestion"},
            )

    if include_outlook:
        email_payload = filter_emails_by_config(normalized_ticker, lookback_years=lookback_years)
        if email_payload:
            if persist_artifacts:
                write_outlook_email_snapshot(normalized_ticker, email_payload)
            email_items = _build_outlook_evidence_items(normalized_ticker, email_payload)
            evidence_items.extend(email_items)
            logger.info(
                "Collected Outlook evidence",
                extra={"ticker": normalized_ticker, "document_count": len(email_items), "component": "ingestion"},
            )

    return evidence_items


async def generate_assessment_draft_for_ticker_async(
    ticker: str,
    *,
    company_name: str | None = None,
    as_of_date: str | None = None,
    include_forum: bool = True,
    include_outlook: bool = True,
    lookback_years: int = 15,
    persist_artifacts: bool = True,
    model_name: str | None = None,
) -> AssessmentRecord:
    """Collect evidence for a ticker and generate an LLM-backed draft assessment."""
    evidence_items = collect_evidence_for_ticker(
        ticker,
        include_forum=include_forum,
        include_outlook=include_outlook,
        lookback_years=lookback_years,
        persist_artifacts=persist_artifacts,
    )
    if not evidence_items:
        raise ValueError(f"No evidence collected for ticker {ticker.upper()}")

    draft_input = DraftAssessmentInput(
        ticker=ticker.upper(),
        company_name=company_name or ticker.upper(),
        source_documents=evidence_items,
        as_of_date=as_of_date,
    )
    return await generate_assessment_draft_async(draft_input, model_name=model_name)


def generate_assessment_draft_for_ticker(
    ticker: str,
    *,
    company_name: str | None = None,
    as_of_date: str | None = None,
    include_forum: bool = True,
    include_outlook: bool = True,
    lookback_years: int = 15,
    persist_artifacts: bool = True,
    model_name: str | None = None,
) -> AssessmentRecord:
    """Synchronous wrapper for evidence collection plus draft generation."""
    return asyncio.run(
        generate_assessment_draft_for_ticker_async(
            ticker,
            company_name=company_name,
            as_of_date=as_of_date,
            include_forum=include_forum,
            include_outlook=include_outlook,
            lookback_years=lookback_years,
            persist_artifacts=persist_artifacts,
            model_name=model_name,
        )
    )
