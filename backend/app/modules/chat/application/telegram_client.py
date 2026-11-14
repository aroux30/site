"""Telegram Bot API client for the live-chat human hand-off.

Ports the WordPress plugin's Telegram path (``send_to_telegram`` /
``create_telegram_topic`` / ``delete_telegram_topic`` / ``answer_telegram_callback``)
into an httpx client. The bot token and group chat id come from the chat config
row (admin settings), never from env — the owner asked for admin-config parity.

Retry shape lifted from the archived ``notifications/telegram_service.py``: one
retry on transient statuses (429/5xx) and transport errors, permanent 4xx not
retried. Every method returns a result object and never raises for delivery
problems, so a bot outage cannot take the visitor's hand-off down.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_TRANSIENT_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})
_API_BASE = "https://api.telegram.org"


@dataclass(frozen=True)
class TelegramConfig:
    """Resolved Telegram credentials for one dispatch."""

    bot_token: str = ""
    chat_id: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token.strip()) and bool(self.chat_id.strip())


@dataclass(frozen=True)
class TelegramResult:
    """Outcome of one Bot API call chain."""

    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None


class TelegramClient:
    """Thin Bot API client — one method per endpoint the hand-off needs."""

    def __init__(self, config: TelegramConfig, *, timeout: float = 15.0) -> None:
        self._config = config
        self._timeout = timeout

    async def _call(self, method: str, payload: dict[str, Any]) -> TelegramResult:
        if not self._config.is_configured:
            return TelegramResult(ok=False, error="telegram_not_configured")
        url = f"{_API_BASE}/bot{self._config.bot_token}/{method}"
        attempts = 0
        retried = False
        while True:
            attempts += 1
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    resp = await client.post(url, json=payload)
                if resp.status_code in _TRANSIENT_HTTP_STATUSES and not retried:
                    retried = True
                    await asyncio.sleep(0.5)
                    continue
                data = resp.json()
                if resp.status_code == 200 and data.get("ok"):
                    return TelegramResult(ok=True, result=data.get("result") or {})
                return TelegramResult(
                    ok=False,
                    error=f"HTTP {resp.status_code}: {data.get('description', '')}",
                )
            except (httpx.TransportError, ValueError) as exc:
                if not retried:
                    retried = True
                    await asyncio.sleep(0.5)
                    continue
                await logger.awarning("telegram_call_failed", method=method, error=str(exc))
                return TelegramResult(ok=False, error=f"{type(exc).__name__}: {exc}")

    async def send_message(
        self,
        text: str,
        *,
        thread_id: int | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> TelegramResult:
        """``sendMessage`` with HTML parse mode (the plugin's format)."""
        payload: dict[str, Any] = {
            "chat_id": self._config.chat_id,
            "text": text[:4096],
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if thread_id:
            payload["message_thread_id"] = thread_id
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self._call("sendMessage", payload)

    async def create_forum_topic(self, name: str) -> TelegramResult:
        """``createForumTopic`` — one topic per conversation (plugin parity)."""
        return await self._call(
            "createForumTopic",
            {"chat_id": self._config.chat_id, "name": name[:128]},
        )

    async def delete_forum_topic(self, thread_id: int) -> TelegramResult:
        return await self._call(
            "deleteForumTopic",
            {"chat_id": self._config.chat_id, "message_thread_id": thread_id},
        )

    async def answer_callback_query(self, callback_query_id: str, text: str) -> TelegramResult:
        return await self._call(
            "answerCallbackQuery",
            {"callback_query_id": callback_query_id, "text": text, "show_alert": True},
        )


def topic_thread_id(result: TelegramResult) -> int | None:
    """Extract ``message_thread_id`` from a createForumTopic result."""
    if result.ok and result.result:
        value = result.result.get("message_thread_id")
        if isinstance(value, int):
            return value
    return None
