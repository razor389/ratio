"""Application bootstrap helpers for backend processes and scripts."""

from __future__ import annotations

from .core.config import Settings, get_settings
from .core.logging import configure_logging, get_logger
from .db.session import create_database


def bootstrap_backend(
    settings: Settings | None = None,
    *,
    initialize_database: bool = True,
) -> Settings:
    """Configure logging and initialize persistent infrastructure."""
    active_settings = settings or get_settings()
    configure_logging(active_settings)

    if initialize_database:
        create_database(active_settings)

    get_logger(__name__).info(
        "Backend bootstrap complete",
        extra={
            "database_url": active_settings.database_url,
            "environment": active_settings.environment,
        },
    )
    return active_settings
