"""API routes for Native Captcha and System Preflight Diagnostics (Karta Phase 10)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.observability.system_establish import run_system_preflight_check
from app.core.security.dependencies import RequirePermissions
from app.core.security.native_captcha import generate_captcha, verify_captcha

router = APIRouter(tags=["security-captcha"])


class CaptchaChallengeResponse(BaseModel):
    captcha_id: str
    image_base64: str
    expires_in_seconds: int


class CaptchaVerifyRequest(BaseModel):
    captcha_id: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class CaptchaVerifyResponse(BaseModel):
    is_valid: bool
    message: str


# ── Native Captcha Endpoints ──────────────────────────────────────────────


@router.get(
    "/auth/captcha/generate",
    response_model=CaptchaChallengeResponse,
    summary="Generate offline-capable native captcha challenge (Karta Phase 10)",
)
async def get_captcha() -> CaptchaChallengeResponse:
    data = await generate_captcha()
    return CaptchaChallengeResponse.model_validate(data)


@router.post(
    "/auth/captcha/verify",
    response_model=CaptchaVerifyResponse,
    summary="Verify user submitted captcha answer",
)
async def check_captcha(body: CaptchaVerifyRequest) -> CaptchaVerifyResponse:
    valid = await verify_captcha(body.captcha_id, body.answer)
    msg = "پاسخ کد امنیتی صحیح است" if valid else "کد امنیتی نادرست یا منقضی شده است"
    return CaptchaVerifyResponse(is_valid=valid, message=msg)


# ── System Preflight Diagnostics Endpoint ─────────────────────────────────


@router.get(
    "/diagnostics/preflight",
    summary="Run full preflight environment & database diagnostics (Karta Establish.php)",
    dependencies=[Depends(RequirePermissions("settings:read"))],
)
async def get_preflight_report() -> dict[str, Any]:
    return await run_system_preflight_check()
