"""Portfolio sizing calculations derived from the Ratio sizing logic doc."""

from __future__ import annotations

from ..core.config import Settings, get_settings
from ..domain import FactorScores, SizingResult


def calculate_sizing(scores: FactorScores, settings: Settings | None = None) -> SizingResult:
    """Apply the documented four-factor sizing methodology."""
    active_settings = settings or get_settings()
    scores.validate()

    total_score = sum(scores.as_dict().values())
    max_total_score = 10 * active_settings.factor_count
    normalized_score = total_score / max_total_score
    raw_beta = total_score / active_settings.benchmark_total_score
    custom_beta = max(raw_beta, active_settings.beta_floor)
    suggested_position_size = active_settings.base_position_size / custom_beta

    if active_settings.max_position_size is not None:
        suggested_position_size = min(suggested_position_size, active_settings.max_position_size)

    return SizingResult(
        total_score=total_score,
        normalized_score=normalized_score,
        custom_beta=custom_beta,
        base_position_size=active_settings.base_position_size,
        suggested_position_size=suggested_position_size,
    )
