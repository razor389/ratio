"""End-to-end Python workflow for collecting evidence and drafting an assessment."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..core.config import get_settings
from ..core.logging import get_logger
from ..domain import AssessmentRecord, EvidenceItem, EvidenceSourceType
from ..ingestion.forum_posts import collect_forum_posts_for_ticker_async, write_forum_posts_snapshot
from ..ingestion.outlook_ticker_search import filter_emails_by_config, write_outlook_email_snapshot
from .drafting import DraftAssessmentInput, generate_assessment_draft_async

logger = get_logger(__name__)


def _to_datetime(timestamp: Any) -> datetime | None:
    """Convert a unix timestamp into a naive UTC datetime when possible."""
    if timestamp in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(timestamp), UTC)
    except (TypeError, ValueError, OSError):
        return None


def _stringify_metadata(values: dict[str, Any]) -> dict[str, str]:
    """Normalize source metadata values into strings for domain transport."""
    return {key: str(value) for key, value in values.items() if value not in (None, "")}


def _get_output_dir() -> Path:
    """Return the configured output directory for generated analysis artifacts."""
    output_dir = get_settings().output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


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
                ingested_at=datetime.now(UTC),
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
                ingested_at=datetime.now(UTC),
                source_uri=email.get("sourceFolder"),
                source_metadata=_stringify_metadata({"source_folder": email.get("sourceFolder")}),
            )
        )

    return items


async def collect_evidence_for_ticker_async(
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

    if not include_forum and not include_outlook:
        logger.info(
            "No evidence sources selected",
            extra={"ticker": normalized_ticker, "component": "ingestion"},
        )
        return []

    if include_forum:
        forum_payload = await collect_forum_posts_for_ticker_async(normalized_ticker)
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
        email_payload = await asyncio.to_thread(
            filter_emails_by_config,
            normalized_ticker,
            lookback_years=lookback_years,
        )
        if email_payload:
            if persist_artifacts:
                await asyncio.to_thread(write_outlook_email_snapshot, normalized_ticker, email_payload)
            email_items = _build_outlook_evidence_items(normalized_ticker, email_payload)
            evidence_items.extend(email_items)
            logger.info(
                "Collected Outlook evidence",
                extra={"ticker": normalized_ticker, "document_count": len(email_items), "component": "ingestion"},
            )

    return evidence_items


def collect_evidence_for_ticker(
    ticker: str,
    *,
    include_forum: bool = True,
    include_outlook: bool = True,
    lookback_years: int = 15,
    persist_artifacts: bool = True,
) -> list[EvidenceItem]:
    """Synchronously collect all configured evidence sources for a ticker."""
    return asyncio.run(
        collect_evidence_for_ticker_async(
            ticker,
            include_forum=include_forum,
            include_outlook=include_outlook,
            lookback_years=lookback_years,
            persist_artifacts=persist_artifacts,
        )
    )


async def _generate_draft_from_evidence_items_async(
    ticker: str,
    evidence_items: list[EvidenceItem],
    *,
    company_name: str | None = None,
    as_of_date: str | None = None,
    model_name: str | None = None,
) -> AssessmentRecord:
    """Generate an LLM-backed draft assessment from already-collected evidence."""
    if not evidence_items:
        raise ValueError(f"No evidence collected for ticker {ticker.upper()}")

    draft_input = DraftAssessmentInput(
        ticker=ticker.upper(),
        company_name=company_name or ticker.upper(),
        source_documents=evidence_items,
        as_of_date=as_of_date,
    )
    return await generate_assessment_draft_async(draft_input, model_name=model_name)


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
    evidence_items = await collect_evidence_for_ticker_async(
        ticker,
        include_forum=include_forum,
        include_outlook=include_outlook,
        lookback_years=lookback_years,
        persist_artifacts=persist_artifacts,
    )
    draft = await _generate_draft_from_evidence_items_async(
        ticker,
        evidence_items,
        company_name=company_name,
        as_of_date=as_of_date,
        model_name=model_name,
    )
    if persist_artifacts:
        output_path = write_llm_analysis_snapshot(ticker, draft)
        logger.info(
            "Wrote LLM analysis artifact",
            extra={"ticker": ticker.upper(), "component": "analysis", "output_path": str(output_path)},
        )
    return draft


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


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line interface for evidence collection and draft generation."""
    parser = argparse.ArgumentParser(
        prog="python -m ratio_backend.services.pipeline",
        description="Collect evidence for a ticker and optionally generate an LLM draft assessment.",
    )
    parser.add_argument("ticker", help="Ticker symbol to process")
    parser.add_argument("--company-name", help="Optional company name to pass to the draft generator")
    parser.add_argument("--as-of-date", help="Optional as-of date string for the draft output")
    parser.add_argument("--lookback-years", type=int, default=15, help="Outlook lookback window in years")
    parser.add_argument("--model", help="Optional provider-specific model override")
    parser.add_argument("--collect-only", action="store_true", help="Collect and normalize evidence without calling the LLM")
    parser.add_argument("--ignore-email", action="store_true", help="Skip Outlook email collection")
    parser.add_argument("--ignore-forum", action="store_true", help="Skip forum post collection")
    parser.add_argument(
        "--no-persist-artifacts",
        action="store_true",
        help="Do not write collected source or LLM analysis artifacts into the output directory",
    )
    return parser


def _summarize_evidence(ticker: str, evidence_items: list[EvidenceItem]) -> dict[str, Any]:
    """Build a compact CLI summary of collected evidence."""
    forum_count = sum(1 for item in evidence_items if item.source_type == EvidenceSourceType.FORUM_POST)
    email_count = sum(1 for item in evidence_items if item.source_type == EvidenceSourceType.OUTLOOK_EMAIL)
    return {
        "ticker": ticker.upper(),
        "document_count": len(evidence_items),
        "forum_count": forum_count,
        "email_count": email_count,
    }


def _serialize_draft_result(ticker: str, draft: AssessmentRecord) -> dict[str, Any]:
    """Serialize a draft assessment into a CLI-friendly JSON payload."""
    payload = asdict(draft)
    payload["ticker"] = ticker.upper()
    llm_metadata = payload.get("llm_metadata")
    if llm_metadata:
        llm_metadata.pop("raw_response", None)
    return payload


def write_llm_analysis_snapshot(
    ticker: str,
    draft: AssessmentRecord,
    output_dir: Path | None = None,
) -> Path:
    """Write the serialized LLM draft analysis to the canonical JSON artifact."""
    target_dir = output_dir or _get_output_dir()
    output_path = target_dir / f"{ticker.upper()}_llm_analysis.json"

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(_serialize_draft_result(ticker, draft), handle, indent=2, default=str)

    return output_path


def main(argv: list[str] | None = None) -> int:
    """Command-line entrypoint for the combined Python evidence and draft pipeline."""
    args = _build_argument_parser().parse_args(argv)
    include_outlook = not args.ignore_email
    include_forum = not args.ignore_forum

    if not include_outlook and not include_forum:
        print("Nothing to run. Include email or forum or both.")
        return 0

    try:
        evidence_items = collect_evidence_for_ticker(
            args.ticker,
            include_forum=include_forum,
            include_outlook=include_outlook,
            lookback_years=args.lookback_years,
            persist_artifacts=not args.no_persist_artifacts,
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    if not evidence_items:
        print(f"No evidence collected for {args.ticker.upper()} from the selected sources.")
        return 0

    if args.collect_only:
        print(json.dumps(_summarize_evidence(args.ticker, evidence_items), indent=2))
        return 0

    try:
        draft = asyncio.run(
            _generate_draft_from_evidence_items_async(
                args.ticker,
                evidence_items,
                company_name=args.company_name,
                as_of_date=args.as_of_date,
                model_name=args.model,
            )
        )
    except ValueError as exc:
        print(str(exc))
        return 1

    if not args.no_persist_artifacts:
        output_path = write_llm_analysis_snapshot(args.ticker, draft)
        logger.info(
            "Wrote LLM analysis artifact",
            extra={"ticker": args.ticker.upper(), "component": "analysis", "output_path": str(output_path)},
        )

    print(json.dumps(_serialize_draft_result(args.ticker, draft), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
