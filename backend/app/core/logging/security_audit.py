"""Tamper-evident Security Audit & Compliance Logging (FATA & Shaparak).

Provides cryptographically chained, immutable audit logging for sensitive operations:
1. Admin authentication (logins, MFA challenges, session management).
2. RBAC and permissions changes (Casbin policy edits, role grants).
3. Sensitive financial transactions (payments, refunds, wallet top-ups, card transfers).
4. Identity inquiries (Shahkar KYC, bank card PAN lookup).
5. Threat detections (rate limiting, brute force, token reuse).

Complies with Iranian Cyber Police (FATA) and Shaparak audit requirements:
- Real client IP resolution through trusted reverse proxy hops.
- Client request fingerprinting (SHA-256 of User-Agent and headers).
- Tracking, trace, and retrieval reference IDs (RRN).
- PII and financial card PAN masking.
- Sequential hash chaining (prev_hash -> record_hash) for mathematical tamper evidence.
- Isolated storage channel decoupled from standard application stdout logs.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal

import structlog

from app.core.config.settings import get_settings
from app.core.logging.config import _redact_value
from app.core.observability.tracer import get_current_trace_id
from app.core.security.data_protection import mask_card_pan, mask_national_code, mask_phone

logger = structlog.get_logger("security.audit")

GENESIS_HASH: str = "0" * 64
DEFAULT_AUDIT_LOG_FILE: str = "logs/security_audit.log"


def generate_request_fingerprint(
    user_agent: str | None = None,
    client_ip: str | None = None,
    extra_entropy: str | None = None,
) -> str:
    """Generate a deterministic 32-character SHA-256 fingerprint of request client attributes."""
    raw = f"{user_agent or ''}|{client_ip or ''}|{extra_entropy or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def resolve_client_ip(request: Any = None, ip_address: str | None = None) -> str:
    """Safely resolve client IP address adhering to reverse proxy configurations."""
    if ip_address and ip_address.strip():
        return ip_address.strip()

    if request is not None:
        try:
            settings = get_settings()
            trusted = max(1, getattr(settings, "TRUSTED_PROXY_COUNT", 1))
        except Exception:
            trusted = 1

        headers = getattr(request, "headers", {})
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            hops = [h.strip() for h in str(forwarded).split(",") if h.strip()]
            if len(hops) >= trusted:
                candidate = hops[-trusted]
                if candidate:
                    return str(candidate)

        real_ip = headers.get("x-real-ip")
        if real_ip and str(real_ip).strip():
            return str(real_ip).strip()

        client = getattr(request, "client", None)
        if client and getattr(client, "host", None):
            return str(client.host)

    return "unknown"


def compute_record_hash(
    prev_hash: str,
    payload_fields: dict[str, Any],
    secret_key: str | bytes | None = None,
) -> str:
    """Calculate HMAC-SHA256 (or SHA-256) signature over canonical record payload."""
    canonical_body = json.dumps(
        payload_fields,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    message = f"{prev_hash}|{canonical_body}".encode()
    if secret_key:
        key_bytes = secret_key.encode("utf-8") if isinstance(secret_key, str) else secret_key
        return hmac.new(key_bytes, message, hashlib.sha256).hexdigest()
    return hashlib.sha256(message).hexdigest()


class SecurityAuditLogger:
    """Tamper-evident, thread-safe audit logger with hash chaining and isolated storage."""

    def __init__(
        self,
        file_path: str | Path | None = None,
        secret_key: str | bytes | None = None,
        enabled: bool | None = None,
        max_bytes: int | None = None,
        backup_count: int | None = None,
    ) -> None:
        self._lock = threading.Lock()
        self._file_path = Path(file_path) if file_path else None
        self._secret_key = secret_key
        self._enabled = enabled
        self._max_bytes = max_bytes
        self._backup_count = backup_count

        self._channel_logger: logging.Logger | None = None
        self._handler: logging.Handler | None = None
        self._last_hash: str = GENESIS_HASH
        self._sequence: int = 0
        self._initialized: bool = False

    def _ensure_initialized(self) -> None:
        """Lazy initialization of storage channel and recovery of latest chain state."""
        if self._initialized:
            return

        with self._lock:
            if self._initialized:
                return

            try:
                settings = get_settings()
            except Exception:
                settings = None

            if self._enabled is None:
                self._enabled = getattr(settings, "AUDIT_LOG_ENABLED", True) if settings else True

            if self._file_path is None:
                log_file = (
                    getattr(settings, "AUDIT_LOG_FILE", DEFAULT_AUDIT_LOG_FILE)
                    if settings
                    else DEFAULT_AUDIT_LOG_FILE
                )
                self._file_path = Path(log_file)

            if self._secret_key is None and settings:
                self._secret_key = getattr(settings, "AUDIT_LOG_HMAC_KEY", "") or getattr(
                    settings, "JWT_SECRET_KEY", ""
                )

            if self._max_bytes is None:
                self._max_bytes = (
                    getattr(settings, "AUDIT_LOG_MAX_BYTES", 50 * 1024 * 1024)
                    if settings
                    else 50 * 1024 * 1024
                )

            if self._backup_count is None:
                self._backup_count = (
                    getattr(settings, "AUDIT_LOG_BACKUP_COUNT", 30) if settings else 30
                )

            self._channel_logger = logging.getLogger(f"security.audit.channel.{id(self)}")
            self._channel_logger.propagate = False
            self._channel_logger.setLevel(logging.INFO)

            if self._enabled and self._file_path:
                self._file_path.parent.mkdir(parents=True, exist_ok=True)
                self._handler = RotatingFileHandler(
                    filename=str(self._file_path),
                    maxBytes=self._max_bytes,
                    backupCount=self._backup_count,
                    encoding="utf-8",
                )
                self._handler.setFormatter(logging.Formatter("%(message)s"))
                self._channel_logger.handlers = [self._handler]
                self._recover_chain_state()

            self._initialized = True

    def _recover_chain_state(self) -> None:
        """Scan the end of the existing log file to restore sequence and previous hash."""
        if not self._file_path or not self._file_path.exists():
            self._last_hash = GENESIS_HASH
            self._sequence = 0
            return
        if self._file_path.stat().st_size == 0:
            self._last_hash = GENESIS_HASH
            self._sequence = 0
            return

        try:
            last_line = ""
            with open(self._file_path, "rb") as f:
                # Seek near the end to find the final line efficiently
                file_size = f.seek(0, os.SEEK_END)
                buffer_size = min(file_size, 8192)
                f.seek(file_size - buffer_size)
                lines = f.read().decode("utf-8", errors="replace").strip().splitlines()
                if lines:
                    last_line = lines[-1]

            if last_line:
                parsed = json.loads(last_line)
                self._last_hash = parsed.get("record_hash", GENESIS_HASH)
                self._sequence = int(parsed.get("seq", 0))
        except Exception as exc:
            # Fallback to genesis on corrupted log head; upgrade to archive-and-reset if frequent
            logger.warning("audit_chain_state_recovery_failed", error=str(exc))
            self._last_hash = GENESIS_HASH
            self._sequence = 0

    def log_audit_event(
        self,
        event_type: str,
        action: str,
        actor_id: str | None = None,
        target_id: str | None = None,
        client_ip: str | None = None,
        request_fingerprint: str | None = None,
        trace_id: str | None = None,
        tracking_id: str | None = None,
        status: Literal["SUCCESS", "FAILURE", "BLOCKED"] = "SUCCESS",
        reason: str | None = None,
        severity: Literal["INFO", "WARNING", "CRITICAL", "ALERT"] = "INFO",
        compliance_category: str = "FATA_SHAPARAK_COMPLIANCE",
        user_agent: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record a tamper-evident audit record into the isolated storage channel."""
        self._ensure_initialized()

        safe_ip = (client_ip or "unknown").strip()
        safe_actor = (actor_id or "anonymous").strip()
        safe_target = (target_id or "none").strip()
        resolved_trace_id = trace_id or get_current_trace_id() or "none"
        resolved_tracking_id = tracking_id or "none"

        if not request_fingerprint:
            request_fingerprint = generate_request_fingerprint(
                user_agent=user_agent,
                client_ip=safe_ip,
            )

        sanitized_extra: dict[str, Any] = {}
        if extra:
            for k, v in extra.items():
                sanitized_extra[k] = _redact_value(k, v)

        now_utc = datetime.now(UTC).isoformat()
        record_id = str(uuid.uuid4())

        with self._lock:
            self._sequence += 1
            seq = self._sequence
            prev_hash = self._last_hash

            payload_fields: dict[str, Any] = {
                "record_id": record_id,
                "seq": seq,
                "timestamp": now_utc,
                "compliance_category": compliance_category,
                "event_type": event_type,
                "action": action,
                "actor_id": safe_actor,
                "target_id": safe_target,
                "client_ip": safe_ip,
                "request_fingerprint": request_fingerprint,
                "trace_id": resolved_trace_id,
                "tracking_id": resolved_tracking_id,
                "status": status,
                "reason": reason or "none",
                "severity": severity,
                "extra": sanitized_extra,
                "prev_hash": prev_hash,
            }

            rec_hash = compute_record_hash(
                prev_hash=prev_hash,
                payload_fields=payload_fields,
                secret_key=self._secret_key,
            )
            payload_fields["record_hash"] = rec_hash
            self._last_hash = rec_hash

            # Write to isolated security channel
            if self._channel_logger and self._handler:
                raw_json = json.dumps(payload_fields, ensure_ascii=False)
                self._channel_logger.info(raw_json)

        # Real-time alert line for Fail2Ban / CrowdSec compatibility
        syslog_line = (
            f"[SECURITY_ALERT] IP={safe_ip} event={event_type} action={action} "
            f"user={safe_actor} status={status} reason={reason or 'none'} "
            f"tracking_id={resolved_tracking_id} ts={now_utc}"
        )
        if status == "SUCCESS":
            logger.info(
                syslog_line,
                event_type=event_type,
                action=action,
                ip=safe_ip,
                user=safe_actor,
                success=True,
                reason=reason,
                tracking_id=resolved_tracking_id,
                trace_id=resolved_trace_id,
                user_agent=user_agent,
                extra=sanitized_extra,
            )
        else:
            logger.warning(
                syslog_line,
                event_type=event_type,
                action=action,
                ip=safe_ip,
                user=safe_actor,
                success=False,
                reason=reason,
                tracking_id=resolved_tracking_id,
                trace_id=resolved_trace_id,
                user_agent=user_agent,
                extra=sanitized_extra,
            )

        return payload_fields

    def log_admin_login(
        self,
        actor_id: str,
        client_ip: str,
        success: bool,
        user_agent: str | None = None,
        request_fingerprint: str | None = None,
        trace_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record administrative authentication events."""
        status_val: Literal["SUCCESS", "FAILURE"] = "SUCCESS" if success else "FAILURE"
        severity_val: Literal["INFO", "WARNING"] = "INFO" if success else "WARNING"
        return self.log_audit_event(
            event_type="admin_authentication",
            action="LOGIN_SUCCESS" if success else "LOGIN_FAILED",
            actor_id=actor_id,
            target_id="admin_portal",
            client_ip=client_ip,
            request_fingerprint=request_fingerprint,
            trace_id=trace_id,
            status=status_val,
            reason=reason or ("Authentication successful" if success else "Invalid credentials"),
            severity=severity_val,
            compliance_category="FATA_ADMIN_AUDIT",
            user_agent=user_agent,
            extra=extra,
        )

    def log_rbac_change(
        self,
        actor_id: str,
        action: str,
        role: str,
        resource: str,
        client_ip: str | None = None,
        success: bool = True,
        target_user_id: str | None = None,
        trace_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record Casbin/IAM role and permission policy adjustments."""
        status_val: Literal["SUCCESS", "FAILURE"] = "SUCCESS" if success else "FAILURE"
        meta = extra.copy() if extra else {}
        meta.update({"role": role, "resource": resource, "action_type": action})
        return self.log_audit_event(
            event_type="rbac_policy_change",
            action=action.upper(),
            actor_id=actor_id,
            target_id=target_user_id or role,
            client_ip=client_ip,
            trace_id=trace_id,
            status=status_val,
            reason=reason or f"RBAC policy update: {role} -> {resource}",
            severity="WARNING" if success else "CRITICAL",
            compliance_category="FATA_ACCESS_CONTROL",
            extra=meta,
        )

    def log_financial_transaction(
        self,
        actor_id: str,
        transaction_id: str,
        amount: int | float,
        currency: str,
        action: str,
        client_ip: str | None = None,
        status: Literal["SUCCESS", "FAILURE", "BLOCKED"] = "SUCCESS",
        trace_id: str | None = None,
        tracking_id: str | None = None,
        card_pan: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record high-value or regulated financial transactions (Shaparak compliance)."""
        meta = extra.copy() if extra else {}
        meta.update({
            "amount": amount,
            "currency": currency,
            "masked_pan": mask_card_pan(card_pan) if card_pan else None,
        })
        return self.log_audit_event(
            event_type="financial_transaction",
            action=action.upper(),
            actor_id=actor_id,
            target_id=str(transaction_id),
            client_ip=client_ip,
            trace_id=trace_id,
            tracking_id=tracking_id or str(transaction_id),
            status=status,
            reason=reason or f"Financial transaction: {action}",
            severity="INFO" if status == "SUCCESS" else "WARNING",
            compliance_category="SHAPARAK_FINANCIAL_AUDIT",
            extra=meta,
        )

    def log_identity_inquiry(
        self,
        actor_id: str,
        inquiry_type: Literal["SHAHKAR", "CARD_TO_CARD", "CIVIL_REGISTRY"],
        national_code: str | None = None,
        mobile: str | None = None,
        card_pan: str | None = None,
        result: str = "VERIFIED",
        client_ip: str | None = None,
        trace_id: str | None = None,
        tracking_id: str | None = None,
        reason: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record official identity verifications (Shahkar, Card-to-Card inquiry)."""
        is_success = result.upper() in ("VERIFIED", "MATCH", "SUCCESS")
        status_val: Literal["SUCCESS", "FAILURE"] = "SUCCESS" if is_success else "FAILURE"
        meta = extra.copy() if extra else {}
        meta.update({
            "inquiry_type": inquiry_type,
            "masked_national_code": mask_national_code(national_code) if national_code else None,
            "masked_mobile": mask_phone(mobile) if mobile else None,
            "masked_card_pan": mask_card_pan(card_pan) if card_pan else None,
            "inquiry_result": result,
        })
        return self.log_audit_event(
            event_type="identity_inquiry",
            action=f"{inquiry_type}_{result.upper()}",
            actor_id=actor_id,
            target_id=meta.get("masked_national_code") or meta.get("masked_card_pan") or "none",
            client_ip=client_ip,
            trace_id=trace_id,
            tracking_id=tracking_id,
            status=status_val,
            reason=reason or f"Identity inquiry {inquiry_type} result: {result}",
            severity="INFO" if is_success else "WARNING",
            compliance_category="FATA_IDENTITY_AUDIT",
            extra=meta,
        )

    def close(self) -> None:
        """Flush and close storage handlers."""
        with self._lock:
            if self._handler:
                self._handler.flush()
                self._handler.close()
                if self._channel_logger:
                    self._channel_logger.removeHandler(self._handler)
                self._handler = None
            self._initialized = False


# Global singleton instance
audit_logger: SecurityAuditLogger = SecurityAuditLogger()


def log_security_event(
    event: str,
    ip_address: str | None = None,
    identifier: str | None = None,
    success: bool = False,
    reason: str | None = None,
    user_agent: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit a standardized, tamper-evident security audit event (backward compatible)."""
    status_val: Literal["SUCCESS", "FAILURE"] = "SUCCESS" if success else "FAILURE"
    severity_val: Literal["INFO", "WARNING"] = "INFO" if success else "WARNING"
    return audit_logger.log_audit_event(
        event_type=event,
        action="SUCCESS" if success else "FAILURE",
        actor_id=identifier,
        client_ip=ip_address,
        user_agent=user_agent,
        status=status_val,
        reason=reason,
        severity=severity_val,
        extra=extra,
    )


def log_admin_login(
    actor_id: str,
    client_ip: str,
    success: bool,
    user_agent: str | None = None,
    request_fingerprint: str | None = None,
    trace_id: str | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return audit_logger.log_admin_login(
        actor_id=actor_id,
        client_ip=client_ip,
        success=success,
        user_agent=user_agent,
        request_fingerprint=request_fingerprint,
        trace_id=trace_id,
        reason=reason,
        extra=extra,
    )


def log_rbac_change(
    actor_id: str,
    action: str,
    role: str,
    resource: str,
    client_ip: str | None = None,
    success: bool = True,
    target_user_id: str | None = None,
    trace_id: str | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return audit_logger.log_rbac_change(
        actor_id=actor_id,
        action=action,
        role=role,
        resource=resource,
        client_ip=client_ip,
        success=success,
        target_user_id=target_user_id,
        trace_id=trace_id,
        reason=reason,
        extra=extra,
    )


def log_financial_transaction(
    actor_id: str,
    transaction_id: str,
    amount: int | float,
    currency: str,
    action: str,
    client_ip: str | None = None,
    status: Literal["SUCCESS", "FAILURE", "BLOCKED"] = "SUCCESS",
    trace_id: str | None = None,
    tracking_id: str | None = None,
    card_pan: str | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return audit_logger.log_financial_transaction(
        actor_id=actor_id,
        transaction_id=transaction_id,
        amount=amount,
        currency=currency,
        action=action,
        client_ip=client_ip,
        status=status,
        trace_id=trace_id,
        tracking_id=tracking_id,
        card_pan=card_pan,
        reason=reason,
        extra=extra,
    )


def log_identity_inquiry(
    actor_id: str,
    inquiry_type: Literal["SHAHKAR", "CARD_TO_CARD", "CIVIL_REGISTRY"],
    national_code: str | None = None,
    mobile: str | None = None,
    card_pan: str | None = None,
    result: str = "VERIFIED",
    client_ip: str | None = None,
    trace_id: str | None = None,
    tracking_id: str | None = None,
    reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return audit_logger.log_identity_inquiry(
        actor_id=actor_id,
        inquiry_type=inquiry_type,
        national_code=national_code,
        mobile=mobile,
        card_pan=card_pan,
        result=result,
        client_ip=client_ip,
        trace_id=trace_id,
        tracking_id=tracking_id,
        reason=reason,
        extra=extra,
    )


def verify_audit_chain(
    records: list[dict[str, Any]],
    secret_key: str | bytes | None = None,
    initial_prev_hash: str | None = None,
) -> tuple[bool, str | None, int]:
    """Verify cryptographic integrity of an audit record chain.

    Returns:
        tuple (is_valid, error_detail_or_none, verified_count)
    """
    if not records:
        return True, None, 0

    expected_prev = (
        initial_prev_hash
        if initial_prev_hash is not None
        else records[0].get("prev_hash", GENESIS_HASH)
    )

    for idx, rec in enumerate(records):
        rec_copy = dict(rec)
        actual_hash = rec_copy.pop("record_hash", None)
        if not actual_hash:
            return False, f"Record #{idx} (seq={rec.get('seq')}) is missing 'record_hash'", idx

        actual_prev = rec_copy.get("prev_hash")
        if actual_prev != expected_prev:
            return (
                False,
                f"Chain broken at record #{idx} (seq={rec.get('seq')}): "
                f"expected prev_hash '{expected_prev}', got '{actual_prev}'",
                idx,
            )

        calculated = compute_record_hash(
            prev_hash=actual_prev,
            payload_fields=rec_copy,
            secret_key=secret_key,
        )

        if not hmac.compare_digest(calculated, str(actual_hash)):
            return (
                False,
                f"Tamper detected at record #{idx} (seq={rec.get('seq')}): payload hash mismatch",
                idx,
            )

        expected_prev = actual_hash

    return True, None, len(records)


def verify_audit_log_file(
    file_path: str | Path | None = None,
    secret_key: str | bytes | None = None,
) -> tuple[bool, str | None, int]:
    """Verify integrity of all records in an audit log file."""
    path = Path(file_path) if file_path else Path(DEFAULT_AUDIT_LOG_FILE)
    if not path.exists():
        return True, None, 0

    if secret_key is None:
        try:
            settings = get_settings()
            secret_key = getattr(settings, "AUDIT_LOG_HMAC_KEY", "") or getattr(
                settings, "JWT_SECRET_KEY", ""
            )
        except Exception:
            secret_key = None

    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                records.append(json.loads(stripped))
            except json.JSONDecodeError as err:
                return False, f"Malformed JSON at line {line_num}: {err}", line_num - 1

    return verify_audit_chain(records, secret_key=secret_key)
