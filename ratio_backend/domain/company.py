"""Company domain types used by repositories and application services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CompanyVisibility(str, Enum):
    """Public visibility states for a tracked company."""

    DRAFT_ONLY = "draft_only"
    PUBLISHED = "published"
    HIDDEN = "hidden"


@dataclass(slots=True)
class CompanyRecord:
    """Canonical company metadata shared by public and admin surfaces."""

    ticker: str
    company_name: str
    display_name: str | None = None
    sector: str | None = None
    industry: str | None = None
    description: str | None = None
    visibility: CompanyVisibility = CompanyVisibility.DRAFT_ONLY
    is_tracked: bool = True
    is_published: bool = False
    display_order: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)
