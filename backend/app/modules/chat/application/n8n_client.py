"""Outbound n8n webhook client.

The WordPress plugin proxied chat messages to an n8n webhook server-side
(``wp_remote_post``) to hide the URL and dodge CORS. This module is the same
proxy: it POSTs ``{message, sessionId, role, ...formFields}`` and extracts the
reply text from whichever of the plugin's accepted response shapes n8n returns.

Follows the ``akismet_client`` seam: a ``Transport`` protocol so tests can swap
a fake, every failure swallowed into ``None`` (the caller stores no AI reply),
and a bounded timeout on every call.
"""

from __future__ import annotations

from typing import Any, Protocol

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger()

#: n8n reply keys the plugin accepted, in priority order.
_REPLY_KEYS = ("output", "text", "message", "content")


class Transport(Protocol):
    """The one method the client needs; a fake replaces it in tests."""

    async def post_json(
        self, url: str, payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]: ...


class HttpxTransport:
    """Real transport over httpx."""

    async def post_json(
        self, url: str, payload: dict[str, Any], timeout: float
    ) -> tuple[int, str]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            return response.status_code, response.text


def _extract_reply(body: str) -> str:
    """Pull the reply text out of n8n's response, mirroring the plugin's parser.

    Accepts ``{output|text|message|content}``, ``[{...}]`` (first element), a
    bare JSON string, a plain-text body, or any JSON object (stringified).
    """
    if not body:
        return ""
    import json

    text = body.strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return text

    if isinstance(data, str):
        return data.strip()
    if isinstance(data, list):
        if not data:
            return ""
        first = data[0]
        if isinstance(first, str):
            return first.strip()
        if isinstance(first, dict):
            for key in _REPLY_KEYS:
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        return json.dumps(first, ensure_ascii=False)
    if isinstance(data, dict):
        for key in _REPLY_KEYS:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        # Generic object: first string value, else stringify.
        for value in data.values():
            if isinstance(value, str) and value.strip():
                return value.strip()
        return json.dumps(data, ensure_ascii=False)
    return text


class N8nClient:
    """Posts a chat message to n8n and returns the reply text (or ``None``)."""

    def __init__(self, transport: Transport | None = None) -> None:
        self._transport: Transport = transport or HttpxTransport()

    async def ask(
        self,
        *,
        webhook_url: str,
        message: str,
        session_key: str,
        role: str = "user",
        extra: dict[str, Any] | None = None,
        timeout: float = 90.0,
    ) -> str | None:
        """Send ``message`` to the webhook; return the reply text, else ``None``.

        Never raises: a webhook that is unset, slow, down, or answers junk must
        not take the visitor's message down with it — the message is already
        saved, the AI reply is simply absent.
        """
        if not webhook_url:
            return None

        payload: dict[str, Any] = {
            "message": message,
            "sessionId": session_key,
            "role": role,
        }
        if extra:
            # Form fields are flattened onto the payload (plugin parity): n8n
            # reads ``user_name``, ``user_phone``, etc. as top-level keys.
            payload.update(extra)

        try:
            status, body = await self._transport.post_json(webhook_url, payload, timeout)
        except (httpx.HTTPError, TimeoutError, OSError) as exc:
            logger.warning("n8n_request_failed", error=str(exc))
            return None

        if status != 200:
            logger.warning("n8n_bad_status", status=status)
            return None

        reply = _extract_reply(body)
        return reply or None
