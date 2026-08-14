"""Structured logging.

JSON logs in staging/production (machine-parseable, ships to SIEM);
human-readable console logs locally. Every request gets a request_id
bound via middleware so log lines correlate across the stack.
"""

import logging

import structlog

from aegis_api.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    renderer = (
        structlog.dev.ConsoleRenderer()
        if settings.env in ("local", "test")
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
