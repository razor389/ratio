"""Audit and publication event domain types for admin-side traceability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class AuditEventRecord:
    """Immutable event describing a backend mutation."""

    actor_user_id: int | None
    event_type: str
    entity_type: str
    entity_id: int
    before_json: dict[str, object] = field(default_factory=dict)
    after_json: dict[str, object] = field(default_factory=dict)
    created_at: datetime | None = None
    id: int | None = None


@dataclass(slots=True)
class PublishEventRecord:
    """Publication trail for archived and newly published assessments."""

    company_id: int
    assessment_id: int
    published_by: str | None = None
    published_at: datetime | None = None
    notes: str | None = None
    id: int | None = None
