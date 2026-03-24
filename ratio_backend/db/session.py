"""Engine and session factory helpers for local or cloud databases."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..core.config import Settings, get_settings
from ..core.logging import get_logger
from .base import Base

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None
logger = get_logger(__name__)


def _ensure_sqlite_directory(database_url: str) -> None:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return

    database_path = Path(database_url[len(prefix) :])
    database_path.parent.mkdir(parents=True, exist_ok=True)


def get_engine(settings: Settings | None = None) -> Engine:
    """Return a cached SQLAlchemy engine for the configured database."""
    global _engine
    if _engine is not None:
        return _engine

    active_settings = settings or get_settings()
    _ensure_sqlite_directory(active_settings.database_url)
    _engine = create_engine(
        active_settings.database_url,
        echo=active_settings.sql_echo,
        future=True,
    )
    return _engine


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    """Return a cached SQLAlchemy session factory."""
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    _session_factory = sessionmaker(bind=get_engine(settings), expire_on_commit=False, class_=Session)
    return _session_factory


def create_database(settings: Settings | None = None) -> None:
    """Create database tables for the current environment if they do not exist."""
    active_settings = settings or get_settings()
    engine = get_engine(active_settings)
    Base.metadata.create_all(engine)
    logger.info("Database schema ensured", extra={"database_url": active_settings.database_url})
