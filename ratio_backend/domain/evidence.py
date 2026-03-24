"""Source-document types used by the Python ingestion and analysis layer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EvidenceSourceType(str, Enum):
    """Supported evidence origins for ingestion and draft analysis."""

    OUTLOOK_EMAIL = "outlook_email"
    FORUM_POST = "forum_post"
    NOTE = "note"
    LINK = "link"


@dataclass(slots=True)
class EvidenceItem:
    """Source document payload consumed by Python draft analysis."""

    company_id: int
    source_type: EvidenceSourceType
    title: str
    content: str
    external_source_id: str | None = None
    author_email: str | None = None
    source_timestamp: datetime | None = None
    ingested_at: datetime | None = None
    source_uri: str | None = None
    content_hash: str | None = None
    source_metadata: dict[str, str] | None = None
    id: int | None = None
