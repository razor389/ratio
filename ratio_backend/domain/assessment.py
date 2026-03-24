"""Assessment domain types for Ratio scoring, rationale, and publishing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class PublicationStatus(str, Enum):
    """Lifecycle states for an assessment revision."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


@dataclass(slots=True)
class FactorScores:
    """The four methodology factor scores constrained to a 0-10 range."""

    debt: int
    market_share_change: int
    market_definition_change: int
    relative_valuation: int

    def as_dict(self) -> dict[str, int]:
        """Serialize scores for persistence or APIs."""
        return {
            "debt": self.debt,
            "market_share_change": self.market_share_change,
            "market_definition_change": self.market_definition_change,
            "relative_valuation": self.relative_valuation,
        }

    def validate(self, *, min_score: int = 0, max_score: int = 10) -> None:
        """Ensure each score stays within the allowed range."""
        for name, value in self.as_dict().items():
            if value < min_score or value > max_score:
                raise ValueError(f"{name} must be between {min_score} and {max_score}, got {value}")


@dataclass(slots=True)
class FactorAssessment:
    """A single factor score and its associated internal or public rationale."""

    factor_key: str
    factor_label: str
    score: int
    score_min: int = 0
    score_max: int = 10
    internal_rationale: str | None = None
    public_rationale_override: str | None = None
    sort_order: int = 0


@dataclass(slots=True)
class SizingResult:
    """Calculated portfolio sizing output derived from factor scores."""

    total_score: int
    normalized_score: float
    custom_beta: float
    base_position_size: float
    suggested_position_size: float

    def as_dict(self) -> dict[str, float | int]:
        """Serialize sizing data for persistence or APIs."""
        return {
            "total_score": self.total_score,
            "normalized_score": self.normalized_score,
            "custom_beta": self.custom_beta,
            "base_position_size": self.base_position_size,
            "suggested_position_size": self.suggested_position_size,
        }


@dataclass(slots=True)
class AssessmentEvidenceLink:
    """A link between an assessment or factor and a source document."""

    source_document_id: int
    factor_key: str | None = None
    relevance_rank: int = 0
    evidence_note: str | None = None
    used_by_llm: bool = False
    used_in_final_review: bool = False
    id: int | None = None


@dataclass(slots=True)
class LLMDraftMetadata:
    """Metadata captured when an LLM produces a first-pass assessment draft."""

    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    assumptions: list[str] = field(default_factory=list)
    raw_response: str | None = None


@dataclass(slots=True)
class AssessmentRecord:
    """A persisted assessment revision for one company."""

    company_id: int
    factor_scores: FactorScores
    sizing: SizingResult
    aggregate_score: int
    relative_score: float
    beta_like_score: float
    status: PublicationStatus = PublicationStatus.DRAFT
    calculation_version: str = "beta-v1"
    created_by: str | None = None
    updated_by: str | None = None
    published_by: str | None = None
    public_comment: str | None = None
    public_comment_enabled: bool = False
    internal_notes: str | None = None
    llm_metadata: LLMDraftMetadata | None = None
    as_of_date: date | None = None
    published_at: datetime | None = None
    factors: list[FactorAssessment] = field(default_factory=list)
    evidence_links: list[AssessmentEvidenceLink] = field(default_factory=list)
    id: int | None = None
