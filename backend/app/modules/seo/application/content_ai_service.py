"""Content AI — meta title/description generation (Rank Math's Content AI).

An honest skeleton with one real capability: when the operator configures an
OpenAI-compatible endpoint + key, the "generate meta" action calls it and
returns the suggestion for review — nothing is auto-written to any post.

Design rules:

- **No key → no request.** The status endpoint reports "not connected" and
  the generate endpoint refuses with a clear message; a credential-less
  request would fail silently and the UI would claim a suggestion was made.
- **Suggestions are suggestions.** The endpoint returns text; the operator
  copies it into the field. Auto-writing model output into live meta tags is
  how a hallucination ships to Google.
- **The provider is configurable** (base URL + model), the Akismet pattern:
  a self-hosted or gateway endpoint works without code changes.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx
import structlog

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

AI_KEY_OPTION = "content_ai_api_key"
AI_BASE_URL_OPTION = "content_ai_base_url"
AI_MODEL_OPTION = "content_ai_model"
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

_REQUEST_TIMEOUT = 30.0


async def get_config(db: AsyncSession) -> dict[str, str]:
    """The configured endpoint/model; key presence is reported separately
    (the key itself is never echoed back)."""
    from app.modules.settings.application.site_options_service import SiteOptionsService

    return {
        "base_url": await SiteOptionsService.get(db, AI_BASE_URL_OPTION) or DEFAULT_BASE_URL,
        "model": await SiteOptionsService.get(db, AI_MODEL_OPTION) or DEFAULT_MODEL,
    }


async def status(db: AsyncSession) -> dict[str, Any]:
    from app.modules.settings.application.site_options_service import SiteOptionsService

    key = await SiteOptionsService.get(db, AI_KEY_OPTION)
    config = await get_config(db)
    return {
        "connected": bool(key),
        "model": config["model"],
        "note": (
            "برای تولید پیشنهاد متا، کلید سرویس هوش مصنوعی (سازگار با OpenAI) را "
            "در همین کارت وارد کنید. پیشنهادها فقط نمایش داده می‌شوند و به‌صورت "
            "خودکار در متاها نوشته نمی‌شوند."
        ),
    }


async def generate_meta_suggestion(
    db: AsyncSession,
    *,
    title: str,
    content: str,
    kind: str = "description",
) -> dict[str, Any]:
    """One suggestion for a meta title or description. Never raises.

    The prompt asks for a single line in Persian within the field limits;
    the response is trimmed and length-clamped so a chatty model cannot
    produce a 400-character "description".
    """
    from app.modules.settings.application.site_options_service import SiteOptionsService

    key = await SiteOptionsService.get(db, AI_KEY_OPTION)
    if not key:
        return {
            "status": "not_connected",
            "suggestion": None,
            "reason": "کلید سرویس هوش مصنوعی تنظیم نشده است",
        }

    config = await get_config(db)
    limit = 60 if kind == "title" else 160
    instruction = (
        f"یک {('عنوان متا' if kind == 'title' else 'توضیحات متا')} فارسی برای صفحهٔ زیر بنویس. "
        f"حداکثر {limit} کاراکتر. فقط خود متن را برگردان، بدون توضیح یا گیومه."
    )
    prompt = f"{instruction}\n\nعنوان: {title}\n\nمحتوا (خلاصه):\n{content[:2000]}"

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT, trust_env=False) as client:
            response = await client.post(
                f"{config['base_url'].rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(
                    {
                        "model": config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 200,
                    }
                ),
            )
    except Exception as exc:  # noqa: BLE001 — additive side effect
        logger.warning("content_ai_request_failed", error=str(exc)[:200])
        return {"status": "error", "suggestion": None, "reason": str(exc)[:200]}

    if response.status_code != 200:
        logger.warning(
            "content_ai_rejected", status=response.status_code, body=response.text[:200]
        )
        return {
            "status": "rejected",
            "suggestion": None,
            "reason": f"کد {response.status_code}: {response.text[:200]}",
        }

    try:
        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError, TypeError):
        return {"status": "error", "suggestion": None, "reason": "پاسخ نامعتبر از سرویس"}

    return {
        "status": "ok",
        "suggestion": text[:limit],
        "reason": None,
    }
