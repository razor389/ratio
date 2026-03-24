"""Centralized environment-driven configuration for Python analysis services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}

@dataclass(frozen=True, slots=True)
class Settings:
    """Typed settings object shared across Python analysis modules."""

    app_name: str
    environment: str
    debug: bool
    log_level: str
    log_format: str
    data_dir: Path
    output_dir: Path
    base_position_size: float
    benchmark_total_score: float
    factor_count: int
    beta_floor: float
    max_position_size: float | None
    default_methodology_version: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache application settings from the environment."""
    data_dir = Path(os.getenv("RATIO_DATA_DIR", DEFAULT_DATA_DIR))
    output_dir = Path(os.getenv("RATIO_OUTPUT_DIR", PROJECT_ROOT / "output"))
    max_position = os.getenv("MAX_POSITION_SIZE")

    return Settings(
        app_name=os.getenv("APP_NAME", "ratio-analysis"),
        environment=os.getenv("APP_ENV", "development"),
        debug=_env_flag("DEBUG"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        log_format=os.getenv("LOG_FORMAT", "json").lower(),
        data_dir=data_dir,
        output_dir=output_dir,
        base_position_size=float(os.getenv("BASE_POSITION_SIZE", "0.05")),
        benchmark_total_score=float(os.getenv("BENCHMARK_TOTAL_SCORE", "20")),
        factor_count=int(os.getenv("FACTOR_COUNT", "4")),
        beta_floor=float(os.getenv("BETA_FLOOR", "0.25")),
        max_position_size=float(max_position) if max_position else None,
        default_methodology_version=os.getenv("DEFAULT_METHODOLOGY_VERSION", "beta-v1"),
    )
