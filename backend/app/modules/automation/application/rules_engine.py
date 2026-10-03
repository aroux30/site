"""Automation rules engine: trigger → conditions → actions.

``evaluate`` is the single entry point: given a trigger type and the event
context, it loads the active rules hooked to that trigger, matches their
conditions against the context, and executes the matching rules' actions.

Guarantees:

* **Isolation** — one failing action never aborts the others (each action is
  wrapped; failures are logged with structlog and reported per action).
* **Cooldown** — a rule that fired within its ``cooldown_minutes`` window is
  skipped; ``last_triggered_at`` is stamped only when the rule actually fires.
* **Fail-closed conditions** — a context field missing from the event never
  matches, so a typo in a condition cannot fire on arbitrary payloads.

Action execution goes through the *read-only imports* of the sibling
services: notifications (email + in-app) and integrations (outbound
webhooks). The engine is called from the Celery task in
``app.modules.automation.application.tasks`` with its own session.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import structlog

from app.modules.automation.domain.rule_models import AutomationRule, AutomationTriggerType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CONDITION_OPERATORS: frozenset[str] = frozenset({"eq", "ne", "gt", "lt", "gte", "lte", "contains"})
ACTION_TYPES: frozenset[str] = frozenset({"send_email", "send_notification", "fire_webhook"})


# ── Condition matching ───────────────────────────────────────────────────────


def _resolve_field(context: dict[str, Any], field: str) -> tuple[bool, Any]:
    """Resolve a dotted path (``order.total``) in the trigger context.

    Returns ``(found, value)`` — a missing field is a *match failure* by
    contract, never an exception and never ``None``-versus-absent guesswork.
    """
    current: Any = context
    for segment in field.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _compare(actual: Any, operator: str, expected: Any) -> bool:
    """Apply one comparison operator; unknown operators fail closed."""
    try:
        if operator == "eq":
            return actual == expected
        if operator == "ne":
            return actual != expected
        if operator == "gt":
            return actual > expected
        if operator == "lt":
            return actual < expected
        if operator == "gte":
            return actual >= expected
        if operator == "lte":
            return actual <= expected
        if operator == "contains":
            return expected in actual
    except TypeError:
        # Incomparable types (e.g. "abc" > 5): the condition simply fails.
        return False
    return False


def matches_condition(condition: dict[str, Any], context: dict[str, Any]) -> bool:
    """Evaluate a single condition dict against the context."""
    field = condition.get("field")
    operator = condition.get("operator")
    if not field or not operator:
        return False
    if operator not in CONDITION_OPERATORS:
        logger.warning(
            "automation_condition_unknown_operator", operator=str(operator), field=str(field)
        )
        return False
    found, actual = _resolve_field(context, str(field))
    if not found:
        return False
    return _compare(actual, str(operator), condition.get("value"))


def match_conditions(conditions: Any, context: dict[str, Any]) -> bool:
    """All conditions must pass (AND); empty/absent conditions always match."""
    if not conditions:
        return True
    if not isinstance(conditions, list):
        return False
    if not all(isinstance(cond, dict) for cond in conditions):
        return False
    return all(matches_condition(cond, context) for cond in conditions)


# ── Action execution ─────────────────────────────────────────────────────────


async def _action_send_email(db: Any, params: dict[str, Any], context: dict[str, Any]) -> bool:
    """Send an email via the notifications email service (or a named template)."""
    from app.modules.notifications.application import email_service

    recipient = str(params.get("recipient") or "").strip()
    if "@" not in recipient:
        raise ValueError("send_email requires a valid 'recipient' email address")
    subject = str(params.get("subject") or "اعلان خودکار")
    message = str(params.get("message") or "").strip()
    template_name = params.get("template")

    rendered_html: str | None = None
    rendered_text: str | None = None
    if template_name:
        # DB first, built-in as the fallback, so an admin's saved override is
        # what an automation rule actually sends. See resolve_template.
        from app.modules.notifications.application.email_template_service import (
            resolve_template,
        )

        try:
            content = await resolve_template(db, str(template_name))
        except Exception as exc:  # noqa: BLE001 — a named template that does not exist
            logger.warning("email_template_unresolved", name=str(template_name), error=str(exc))
            content = None  # falls back to the message below
        if content is not None:
            rendered = email_service.render_template(content, _stringify(params.get("variables")))
            subject = rendered.subject if not message else subject
            rendered_html, rendered_text = rendered.html, rendered.text

    if rendered_html is None:
        rendered_text = message or "اعلان خودکار سیستم"
        # Same resolver as the transactional templates: an automation rule
        # firing "your order shipped" and the order-confirmation email it
        # complements were printed with two different store names.
        rendered_html = await email_service.wrap_html_for_store(
            db,
            f"<p>{rendered_text}</p>".replace("\n", "<br>"),
        )

    success, _log = await email_service.send_email(
        db,
        recipient=recipient,
        subject=subject,
        html_body=rendered_html,
        text_body=rendered_text or message,
        template=str(template_name) if template_name else "automation",
    )
    if not success:
        raise RuntimeError("email delivery reported failure")
    return True


async def _action_send_notification(
    db: Any, params: dict[str, Any], context: dict[str, Any]
) -> bool:
    """Create an in-app notification via the notifications service."""
    import uuid as uuid_mod

    from app.modules.notifications.application.notification_service import NotificationService

    user_id = params.get("user_id")
    if not user_id:
        raise ValueError("send_notification requires 'user_id'")
    title = str(params.get("title") or "اعلان خودکار")
    body = str(params.get("body") or "").strip() or "اعلان خودکار سیستم"
    notification_type = str(params.get("type") or "automation")

    notification = await NotificationService.create_notification(
        db,
        user_id=uuid_mod.UUID(str(user_id)),
        type=notification_type,
        title=title,
        body=body,
        data={"automation_context": _jsonable(context)},
    )
    # Fire-and-forget channel dispatch: the in-app row exists either way.
    try:
        from app.modules.notifications.application.tasks import send_notification_task

        send_notification_task.delay(str(notification.id))
    except Exception as exc:
        await logger.awarning(
            "automation_notification_dispatch_skipped",
            notification_id=str(notification.id),
            error=str(exc),
        )
    return True


async def _action_fire_webhook(db: Any, params: dict[str, Any], context: dict[str, Any]) -> bool:
    """Queue an outbound webhook via the integrations webhook service."""
    from app.modules.integrations.application import webhook_service

    event = str(params.get("event") or "").strip()
    if not event:
        raise ValueError("fire_webhook requires an 'event' name")
    if event not in webhook_service.EVENTS:
        supported = ", ".join(sorted(webhook_service.EVENTS))
        raise ValueError(f"unknown webhook event '{event}'; supported: {supported}")
    payload = params.get("payload")
    if not isinstance(payload, dict):
        payload = _jsonable(context)
    await webhook_service.enqueue_event(db, event, payload)
    return True


# Registry indirection keeps the engine unit-testable: tests monkeypatch
# entries here instead of faking SMTP/HTTP.
ACTION_HANDLERS: dict[str, Any] = {
    "send_email": _action_send_email,
    "send_notification": _action_send_notification,
    "fire_webhook": _action_fire_webhook,
}


async def run_actions(
    actions: Any,
    db: Any,
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    """Execute each action independently; failures never abort the rest."""
    results: list[dict[str, Any]] = []
    if not isinstance(actions, list):
        return results
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type") or "")
        params = action.get("params") if isinstance(action.get("params"), dict) else {}
        entry: dict[str, Any] = {"type": action_type}
        try:
            handler = ACTION_HANDLERS.get(action_type)
            if handler is None:
                supported = ", ".join(sorted(ACTION_TYPES))
                raise ValueError(f"unknown action type '{action_type}'; supported: {supported}")
            await handler(db, params, context)
            entry["status"] = "ok"
        except Exception as exc:
            await logger.aexception(
                "automation_action_failed",
                action_type=action_type,
                error=str(exc),
            )
            entry["status"] = "failed"
            entry["error"] = str(exc)
        results.append(entry)
    return results


# ── Evaluation ───────────────────────────────────────────────────────────────


def _is_in_cooldown(rule: AutomationRule, now: datetime) -> bool:
    if not rule.cooldown_minutes or rule.cooldown_minutes <= 0:
        return False
    if rule.last_triggered_at is None:
        return False
    return now < rule.last_triggered_at + timedelta(minutes=rule.cooldown_minutes)


def normalize_trigger_type(trigger_type: AutomationTriggerType | str) -> str:
    """Accept the enum or its value; unknown names raise ``ValueError``."""
    if isinstance(trigger_type, AutomationTriggerType):
        return trigger_type.value
    value = str(trigger_type).strip().lower()
    return AutomationTriggerType(value).value


async def evaluate(
    db: AsyncSession,
    trigger_type: AutomationTriggerType | str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate every active rule for *trigger_type* against *context*.

    Returns a summary dict (fired / skipped / failed rule names) suitable
    for the Celery task's JSON result. Never raises for rule-level problems:
    the caller (commerce flow → Celery) must be insulated from rule bugs.
    """
    from sqlalchemy import select

    trigger_value = normalize_trigger_type(trigger_type)
    now = datetime.now(UTC)

    stmt = select(AutomationRule).where(
        AutomationRule.trigger_type == AutomationTriggerType(trigger_value),
        AutomationRule.is_active.is_(True),
    )
    rules = list((await db.execute(stmt)).scalars().all())

    fired: list[str] = []
    skipped: list[str] = []
    failed: list[str] = []

    for rule in rules:
        if _is_in_cooldown(rule, now):
            skipped.append(rule.name)
            await logger.ainfo(
                "automation_rule_cooldown_skip",
                rule=str(rule.name),
                trigger=trigger_value,
                last_triggered_at=str(rule.last_triggered_at),
            )
            continue

        if not match_conditions(rule.conditions, context):
            continue

        results = await run_actions(rule.actions, db, context)
        rule.last_triggered_at = now
        if any(r.get("status") == "failed" for r in results):
            failed.append(rule.name)
        else:
            fired.append(rule.name)
        await logger.ainfo(
            "automation_rule_fired",
            rule=str(rule.name),
            trigger=trigger_value,
            actions=results,
        )

    await db.flush()
    return {"trigger": trigger_value, "fired": fired, "skipped": skipped, "failed": failed}


def _stringify(variables: Any) -> dict[str, str]:
    """Coerce a template-variables payload into ``dict[str, str]``."""
    if not isinstance(variables, dict):
        return {}
    return {str(key): str(value) for key, value in variables.items()}


def _jsonable(context: dict[str, Any]) -> dict[str, Any]:
    """Best-effort JSON-safe projection of the trigger context."""
    safe: dict[str, Any] = {}
    for key, value in context.items():
        try:
            import json

            json.dumps(value)
            safe[str(key)] = value
        except (TypeError, ValueError):
            safe[str(key)] = str(value)
    return safe
