"""Assessment artifact types for Python-side draft scoring and rationale generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(slots=True)
class FactorScores:
    """The four methodology factor scores constrained to a 0-10 range."""

    debt: int
    market_share_change: int
    market_definition_change: int
    relative_valuation: int

    def as_dict(self) -> dict[str, int]:
        """Return the factor scores as a stable dictionary."""
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
    """A Python-generated draft assessment artifact."""

    company_id: int
    factor_scores: FactorScores
    sizing: SizingResult
    aggregate_score: int
    relative_score: float
    beta_like_score: float
    calculation_version: str = "beta-v1"
    llm_metadata: LLMDraftMetadata | None = None
    as_of_date: date | None = None
    factors: list[FactorAssessment] = field(default_factory=list)
