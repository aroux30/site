"""Structured JSON logging configuration using ``structlog``.

Call :func:`setup_logging` once at application startup (inside the lifespan
context manager) to configure both ``structlog`` and the stdlib ``logging``
module to emit machine-readable JSON logs.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def setup_logging(*, log_level: str = "INFO", json_output: bool = True) -> None:
    """Configure structlog processors and stdlib logging integration.

    Parameters
    ----------
    log_level:
        Root log level (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``).
    json_output:
        If ``True``, render events as JSON.  If ``False`` (useful for local dev),
        use the coloured console renderer instead.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging so third-party libraries go through structlog
    root = logging.getLogger()
    root.setLevel(log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    ))
    root.handlers = [handler]

    # Quieten noisy loggers
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(**initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Convenience wrapper that returns a bound structlog logger."""
    return structlog.get_logger(**initial_values)
