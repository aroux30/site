"""Structured Security Audit Logger.

Emits standardized security telemetry suitable for real-time ingestion by:
1. CrowdSec / Fail2Ban (via [SECURITY_ALERT] IP=<ip> syntax)
2. Wazuh / SIEM (via structured JSON fields)
3. Sentry / Datadog
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

logger = structlog.get_logger("security.audit")


def log_security_event(
    event: str,
    ip_address: str | None = None,
    identifier: str | None = None,
    success: bool = False,
    reason: str | None = None,
    user_agent: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit a standardized security audit event."""
    safe_ip = (ip_address or "unknown").strip()
    safe_id = (identifier or "anonymous").strip()
    safe_reason = (reason or "none").strip()
    timestamp = datetime.now(UTC).isoformat()

    # Formatted syslog line for Fail2Ban / CrowdSec parsing
    log_line = (
        f"[SECURITY_ALERT] IP={safe_ip} event={event} user={safe_id} "
        f"success={success} reason={safe_reason} ts={timestamp}"
    )

    if success:
        logger.info(
            log_line,
            event_type=event,
            ip=safe_ip,
            user=safe_id,
            success=True,
            reason=safe_reason,
            user_agent=user_agent,
            extra=extra or {},
        )
    else:
        logger.warning(
            log_line,
            event_type=event,
            ip=safe_ip,
            user=safe_id,
            success=False,
            reason=safe_reason,
            user_agent=user_agent,
            extra=extra or {},
        )
