"""Structured logging configuration using ``structlog``, OpenTelemetry, and async queue buffering.

Provides high-performance, non-blocking structured logging with:
1. Deep OpenTelemetry correlation (trace_id, span_id, request_id)
2. Automatic callsite parameters (func_name, lineno, filename, process, thread)
3. Specialized renderers:
   - Optimized ANSI colored console renderer for Development
   - High-throughput, compact JSON renderer for Production
4. Memory-buffered async queue worker completely decoupled from the ASGI event loop
5. Dual-destination logging (Async Console + Async Rotating debug.log file)
6. Recursive PII and confidential credential redaction
"""

from __future__ import annotations

import contextlib
import datetime
import json
import logging
import os
import re
import sys
from collections.abc import MutableMapping
from decimal import Decimal
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, ClassVar, cast
from uuid import UUID

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder

from app.core.logging.async_handler import AsyncLogQueueManager
from app.core.observability.tracer import get_current_span_id, get_current_trace_id

# Global async logging manager singleton
_queue_manager: AsyncLogQueueManager | None = None

# Keys containing sensitive data that must always be masked
_SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "password_hash",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "auth_header",
        "proxy-authorization",
        "cookie",
        "session",
        "api_key",
        "secret",
        "jwt_secret",
        "jwt_secret_key",
        "private_key",
        "card_number",
        "card_pan",
        "card_no",
        "pan",
        "cvv",
        "cvv2",
        "security_code",
        "pin",
        "digital_cards_encryption_key",
        "national_code",
        "sheba",
        "iban",
    }
)

_MASK = "[REDACTED]"
_JWT_PATTERN = re.compile(r"eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]+")
_BEARER_PATTERN = re.compile(r"(Bearer\s+)[a-zA-Z0-9._~+/-]+", re.IGNORECASE)
_BASIC_AUTH_PATTERN = re.compile(r"(Basic\s+)[a-zA-Z0-9+/=]+", re.IGNORECASE)
_CARD_PAN_PATTERN = re.compile(r"\b(\d{4})[- ]?(\d{4})[- ]?(\d{4})[- ]?(\d{4})\b")


def _redact_value(key: str, val: Any) -> Any:
    """Recursively redact sensitive dictionary values and strings."""
    if isinstance(key, str):
        key_lower = key.lower()
        if key_lower.startswith("masked_") or (isinstance(val, str) and "*" in val):
            return val

        if any(s in key_lower for s in _SENSITIVE_KEYS):
            if key_lower in ("card_number", "card_pan", "pan", "card_no") and isinstance(val, str):
                try:
                    from app.core.security.data_protection import mask_card_pan

                    masked = mask_card_pan(val)
                    return masked if masked else _MASK
                except Exception:
                    return _MASK
            if key_lower in ("national_code", "national_id") and isinstance(val, str):
                try:
                    from app.core.security.data_protection import mask_national_code

                    masked = mask_national_code(val)
                    return masked if masked else _MASK
                except Exception:
                    return _MASK
            return _MASK
    if isinstance(val, dict):
        return {k: _redact_value(k, v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_redact_value("", item) for item in val]
    if isinstance(val, str):
        s = val
        if "Bearer " in s or "bearer " in s:
            s = _BEARER_PATTERN.sub(r"\g<1>[REDACTED]", s)
        if "Basic " in s or "basic " in s:
            s = _BASIC_AUTH_PATTERN.sub(r"\g<1>[REDACTED]", s)
        if "eyJ" in s:
            s = _JWT_PATTERN.sub("[REDACTED_JWT]", s)
        if any(c.isdigit() for c in s) and len(s) >= 16:
            s = _CARD_PAN_PATTERN.sub(r"\1-****-****-\4", s)
        return s
    return val


def redact_sensitive_data(
    logger: logging.Logger | None, method_name: str, event_dict: MutableMapping[str, Any]
) -> dict[str, Any]:
    """Structlog processor to sanitize confidential keys and PII from log dictionaries."""
    return {k: _redact_value(k, v) for k, v in event_dict.items()}


# Structlog processor-protocol alias: the name used when registering this
# function directly in a ``structlog.configure(processors=[...])`` chain.
redact_sensitive_data_processor = redact_sensitive_data


def add_opentelemetry_context(
    logger: logging.Logger | None, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Inject active OpenTelemetry trace_id, span_id, and request_id into log context."""
    # 1. request_id / correlation_id from structlog contextvars if not already present
    if "request_id" not in event_dict:
        ctx = structlog.contextvars.get_contextvars()
        req_id = ctx.get("request_id") or ctx.get("correlation_id")
        if req_id:
            event_dict["request_id"] = str(req_id)

    # 2. OpenTelemetry trace_id and span_id
    trace_id = get_current_trace_id()
    if trace_id and "trace_id" not in event_dict:
        event_dict["trace_id"] = trace_id

    span_id = get_current_span_id()
    if span_id and "span_id" not in event_dict:
        event_dict["span_id"] = span_id

    return event_dict


# ── Fast JSON Serializer for Production ──────────────────────────────────────


def _fast_json_default(obj: Any) -> Any:
    """Fallback serializer for non-primitive Python types."""
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if isinstance(obj, Exception):
        return f"{type(obj).__name__}: {obj}"
    return str(obj)


def fast_json_serializer(obj: Any, **kwargs: Any) -> str:
    """High-performance compact JSON serializer with safe UTF-8 encoding."""
    return json.dumps(
        obj,
        default=_fast_json_default,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ── Custom Development Formatter ─────────────────────────────────────────────


class DevConsoleRenderer:
    """Optimized ANSI colorized console renderer for local development environments."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    LEVEL_COLORS: ClassVar[dict[str, str]] = {
        "debug": "\033[36m",      # Cyan
        "info": "\033[32m",       # Green
        "warning": "\033[33m",    # Yellow
        "error": "\033[31m",      # Red
        "critical": "\033[1;31m", # Bold Red
        "exception": "\033[1;31m",
    }

    KEY_COLOR = "\033[34m"        # Blue
    VAL_COLOR = "\033[37m"        # Light Gray
    TRACE_COLOR = "\033[35m"      # Magenta
    CALLSITE_COLOR = "\033[90m"   # Dark Gray

    def __call__(
        self, logger: logging.Logger | None, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> str:
        timestamp = event_dict.pop("timestamp", "")
        level = str(event_dict.pop("level", "info")).lower()
        event = event_dict.pop("event", "")
        logger_name = event_dict.pop("logger", "")

        # Extract callsite and trace info
        filename = event_dict.pop("filename", "")
        lineno = event_dict.pop("lineno", "")
        func_name = event_dict.pop("func_name", "")
        process = event_dict.pop("process", "")
        thread = event_dict.pop("thread", "")
        event_dict.pop("process_name", None)
        event_dict.pop("thread_name", None)

        trace_id = event_dict.pop("trace_id", None)
        span_id = event_dict.pop("span_id", None)
        request_id = event_dict.pop("request_id", None)

        # Build output components
        level_color = self.LEVEL_COLORS.get(level, "\033[37m")
        level_badge = f"{level_color}[{level.upper():<7}]{self.RESET}"

        time_part = f"{self.DIM}{timestamp}{self.RESET} " if timestamp else ""
        logger_part = f"[{self.BOLD}{logger_name}{self.RESET}] " if logger_name else ""

        callsite_items = []
        if filename and lineno:
            callsite_items.append(f"{filename}:{lineno}")
        if func_name:
            callsite_items.append(func_name)
        if process and thread:
            callsite_items.append(f"p:{process}/t:{thread}")
        callsite_str = (
            f" {self.CALLSITE_COLOR}({','.join(callsite_items)}){self.RESET}"
            if callsite_items
            else ""
        )

        trace_items = []
        if request_id:
            trace_items.append(f"req={request_id}")
        if trace_id:
            trace_items.append(f"trace={trace_id[:8]}..")
        if span_id:
            trace_items.append(f"span={span_id[:8]}..")
        trace_str = (
            f" {self.TRACE_COLOR}[{', '.join(trace_items)}]{self.RESET}"
            if trace_items
            else ""
        )

        # Render key-values
        kv_pairs = []
        for k in sorted(event_dict.keys()):
            val = event_dict[k]
            kv_pairs.append(f"{self.KEY_COLOR}{k}{self.RESET}={self.VAL_COLOR}{val}{self.RESET}")
        kv_str = (" " + " ".join(kv_pairs)) if kv_pairs else ""

        return (
            f"{time_part}{level_badge} {logger_part}{self.BOLD}{event}{self.RESET}"
            f"{callsite_str}{trace_str}{kv_str}"
        )


# ── WordPress Style File Formatter for debug.log ─────────────────────────────


class WordPressStyleFileFormatter(logging.Formatter):
    """Format log records as JSON Lines for ``debug.log``.

    The ``debug.log`` sink is a machine-read audit stream: it is tailed by
    Grafana Alloy (``monitoring/alloy/config.alloy`` -> ``loki.process
    .enrich_logs`` -> ``stage.json``) and asserted line-by-line as parseable
    JSON by the debug-log integration suite. Each record must therefore be
    exactly one JSON object per line — a multi-line human-readable rendering
    would break both the ``stage.json`` extraction and the JSONL contract.

    The human-readable ``origin``/``trigger`` classification is preserved as
    extra fields inside the JSON object rather than as prose lines, so the
    operational detail is retained without breaking the format.
    """

    def format(self, record: logging.LogRecord) -> str:
        now_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
        level = record.levelname

        msg_data: dict[str, Any] = {}
        if isinstance(record.msg, dict):
            msg_data = dict(record.msg)
        else:
            raw_msg = record.getMessage()
            if raw_msg.startswith("{") and raw_msg.endswith("}"):
                try:
                    msg_data = json.loads(raw_msg)
                except Exception:
                    msg_data = {"event": raw_msg}
            else:
                msg_data = {"event": raw_msg}

        event = str(msg_data.get("event") or msg_data.get("message") or "log_event")
        trace_id = str(msg_data.get("trace_id") or get_current_trace_id() or "-")
        request_id = str(msg_data.get("request_id") or "-")
        module_name = str(msg_data.get("module") or msg_data.get("logger") or record.name)

        # Origin identification
        origin = f"MODULE:{module_name}"
        evt_lower = event.lower()
        if "sql" in evt_lower or "db" in evt_lower or "query" in evt_lower:
            origin = "DATABASE:PostgreSQL"
        elif "redis" in evt_lower or "cache" in evt_lower:
            origin = "CACHE:Redis"
        elif "payment" in evt_lower or "zarinpal" in evt_lower or "idpay" in evt_lower:
            origin = "PAYMENT:Gateway"
        elif "http_request" in evt_lower or "fastapi" in evt_lower:
            origin = "API:FastAPI"
        elif "security" in evt_lower or "auth" in evt_lower:
            origin = "SECURITY:Audit"

        # Trigger origin
        trigger = "Internal Application Logic"
        if "route" in msg_data or "path" in msg_data:
            method = msg_data.get("method", "HTTP")
            path = msg_data.get("route") or msg_data.get("path")
            client_ip = msg_data.get("client") or msg_data.get("ip") or "unknown"
            trigger = f"Inbound {method} request to '{path}' from [{client_ip}]"
        elif "operation" in msg_data:
            operation = msg_data.get("operation")
            key = msg_data.get("key", "")
            trigger = f"Storage operation '{operation}' on '{key}'"

        # Preserve every structured field verbatim; the origin/trigger
        # classification rides alongside as discrete keys.
        payload: dict[str, Any] = dict(msg_data)
        payload.setdefault("event", event)
        payload.setdefault("level", level.lower())
        payload.setdefault("logger", module_name)
        payload["origin"] = origin
        payload["trigger"] = trigger
        payload["timestamp"] = payload.get("timestamp") or now_str
        payload["trace_id"] = trace_id
        payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # No trailing newline: ``logging.Handler.emit`` appends its own
        # terminator, so returning one here would emit a blank line after
        # every record and break the one-JSON-object-per-line contract that
        # the log shipper and the JSONL tests rely on. Exception text is
        # embedded as a single escaped string field for the same reason.
        return fast_json_serializer(payload, sort_keys=False)


# ── Shared Processors ────────────────────────────────────────────────────────


def get_shared_processors(
    service_name: str = "iranian-ecommerce-backend",
) -> list[structlog.types.Processor]:
    """Assemble shared processors applied to both structlog and foreign stdlib logs."""
    return [
        structlog.contextvars.merge_contextvars,
        add_opentelemetry_context,
        redact_sensitive_data,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        CallsiteParameterAdder(
            parameters={
                CallsiteParameter.FUNC_NAME,
                CallsiteParameter.LINENO,
                CallsiteParameter.FILENAME,
                CallsiteParameter.PROCESS,
                CallsiteParameter.PROCESS_NAME,
                CallsiteParameter.THREAD,
                CallsiteParameter.THREAD_NAME,
            },
            additional_ignores=["app.core.logging", "structlog", "logging"],
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]


def _teardown_root_handlers() -> None:
    """Stop the async queue and close every handler on the root logger.

    Called at the start of :func:`setup_logging` so repeated configuration
    cannot leave stale handlers attached — each one would keep its own file
    offset on the shared audit log and interleave writes.
    """
    global _queue_manager
    if _queue_manager is not None:
        with contextlib.suppress(Exception):
            _queue_manager.stop()
        _queue_manager = None

    root = logging.getLogger()
    for handler in list(root.handlers):
        with contextlib.suppress(Exception):
            handler.flush()
        with contextlib.suppress(Exception):
            handler.close()
    root.handlers = []


def setup_logging(
    *,
    log_level: str = "INFO",
    json_output: bool = True,
    service_name: str = "iranian-ecommerce-backend",
    environment: str = "development",
    async_mode: bool = True,
    queue_max_size: int = 10000,
    log_file_path: str | Path | None = None,
    log_file: str | Path | None = None,
    enable_file_logging: bool = True,
) -> None:
    """Configure structlog processors, custom renderers, and async queue log worker."""
    global _queue_manager
    if log_file is not None and log_file_path is None:
        log_file_path = log_file

    # Close and detach handlers from any previous configuration before
    # installing new ones. RotatingFileHandler keeps its own file offset and
    # its own lock, so two live handlers on the same path will interleave
    # their writes and corrupt each other's lines — which is how a re-
    # configuration (a test calling setup_logging repeatedly, or an app
    # reloading) produced torn records in the audit log. Idempotent
    # re-configuration must not stack handlers.
    _teardown_root_handlers()

    # Ensure stdout handles UTF-8 characters properly
    if hasattr(sys.stdout, "reconfigure"):
        with contextlib.suppress(Exception):
            sys.stdout.reconfigure(encoding="utf-8")

    shared_processors = get_shared_processors(service_name)

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer(
            serializer=fast_json_serializer
        )
    else:
        renderer = DevConsoleRenderer()

    # Formatter applied by background listener to console records
    console_formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    async_handlers: list[logging.Handler] = [console_handler]

    # ── Audit file sink (debug.log) — deliberately SYNCHRONOUS ────────────
    # This handler is attached to the root logger directly, NOT routed
    # through the async queue, for two reasons that matter for an audit
    # stream:
    #   1. Durability. The queue drops records when it overflows (see
    #      NonFormattingQueueHandler.enqueue), and a process crash can lose
    #      whatever is still buffered. An audit trail that silently loses
    #      lines under load is not an audit trail.
    #   2. Observability. A synchronous write means a record is on disk
    #      before the logging call returns, so a reader (a test, a log
    #      shipper tailing the file, an operator) never sees a torn or
    #      missing line.
    # The latency cost is confined to this file handler; console output —
    # the high-volume path — stays asynchronous.
    audit_handler: logging.Handler | None = None
    if enable_file_logging:
        try:
            if log_file_path is None:
                base_dir = Path(__file__).resolve().parents[4]
                target_log_dir = base_dir / "logs"
                target_log_file = target_log_dir / "debug.log"
            else:
                target_log_file = Path(log_file_path)
                target_log_dir = target_log_file.parent

            os.makedirs(target_log_dir, exist_ok=True)

            file_handler = RotatingFileHandler(
                filename=str(target_log_file),
                maxBytes=20 * 1024 * 1024,  # 20 MB max per file
                backupCount=5,
                encoding="utf-8",
            )
            file_handler.setFormatter(WordPressStyleFileFormatter())
            file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
            audit_handler = file_handler
        except Exception as exc:
            logging.getLogger(__name__).warning("Could not initialize file handler: %s", exc)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if async_mode:
        if _queue_manager is not None:
            _queue_manager.stop()
        _queue_manager = AsyncLogQueueManager(
            handlers=async_handlers,
            max_queue_size=queue_max_size,
            drop_on_overflow=True,
        )
        queue_handler = _queue_manager.start()
        root.handlers = [queue_handler] + ([audit_handler] if audit_handler else [])
    else:
        root.handlers = async_handlers + ([audit_handler] if audit_handler else [])

    # Configure structlog to route through stdlib logger and async queue handler
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Quieten noisy third-party loggers
    for noisy in ("uvicorn.access", "uvicorn.error", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def shutdown_logging(timeout: float = 3.0) -> None:
    """Cleanly drain in-memory log buffer and stop background listener worker."""
    global _queue_manager
    if _queue_manager is not None:
        _queue_manager.stop(timeout=timeout)
        _queue_manager = None


def flush_logging(timeout: float = 1.0) -> None:
    """Flush pending log records from the async buffer."""
    if _queue_manager is not None:
        _queue_manager.flush(timeout=timeout)


def get_logger(*args: Any, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger with optional pre-bound context."""
    return cast("structlog.stdlib.BoundLogger", structlog.get_logger(*args, **initial_values))


def bind_context(**kwargs: Any) -> None:
    """Bind contextual variables (e.g. request_id, user_id) to current async task context."""
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """Unbind specified context variables."""
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all contextual variables for current task."""
    structlog.contextvars.clear_contextvars()
