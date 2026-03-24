"""Structured logging helpers shared by Python analysis scripts and services."""

from __future__ import annotations

import logging
from contextvars import ContextVar

from pythonjsonlogger.jsonlogger import JsonFormatter

from .config import Settings, get_settings

_request_id: ContextVar[str] = ContextVar("ratio_request_id", default="-")
_run_id: ContextVar[str] = ContextVar("ratio_run_id", default="-")
_configured = False


class RequestContextFilter(logging.Filter):
    """Inject stable service metadata into each log record."""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self.settings.app_name
        record.runtime = "python"
        record.environment = self.settings.environment
        record.component = getattr(record, "component", "analysis")
        record.request_id = _request_id.get()
        record.run_id = _run_id.get()
        return True


class PlainTextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = _request_id.get()
        return super().format(record)


def bind_request_context(request_id: str) -> None:
    """Bind a request identifier to the current execution context."""
    _request_id.set(request_id)


def clear_request_context() -> None:
    """Clear any request identifier from the current execution context."""
    _request_id.set("-")


def bind_run_context(run_id: str) -> None:
    """Bind a job or batch run identifier to the current execution context."""
    _run_id.set(run_id)


def clear_run_context() -> None:
    """Clear any job or batch run identifier from the current execution context."""
    _run_id.set("-")


def configure_logging(settings: Settings | None = None) -> None:
    """Configure process-wide logging exactly once."""
    global _configured
    if _configured:
        return

    active_settings = settings or get_settings()
    context_filter = RequestContextFilter(active_settings)

    handler = logging.StreamHandler()
    handler.addFilter(context_filter)

    if active_settings.log_format == "json":
        handler.setFormatter(
            JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(runtime)s %(environment)s %(component)s %(request_id)s %(run_id)s"
            )
        )
    else:
        handler.setFormatter(
            PlainTextFormatter(
                "%(asctime)s %(levelname)s [%(name)s] [runtime=%(runtime)s] [component=%(component)s] [req=%(request_id)s] [run=%(run_id)s] %(message)s"
            )
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(active_settings.log_level)
    root_logger.addHandler(handler)

    # Keep third-party transport libraries from flooding normal job output.
    for logger_name in ("httpx", "httpcore", "google_genai", "google_genai.models"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger and ensure logging is configured first."""
    if not _configured:
        configure_logging()
    return logging.getLogger(name)
