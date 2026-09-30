"""External identity verification adapters (Karta Zohal gateway).

The legacy Karta platform verifies identity through the Zohal inquiry
service:

- ``POST {base}/services/inquiry/shahkar`` — mobile ↔ national-code match
- ``POST {base}/services/inquiry/national_identity_inquiry`` — civil
  registry data (name, father, birth date) plus liveness

This module ports that behavior to the modern stack as an httpx adapter.
Without a configured token the adapter reports NOT_CONFIGURED and callers
must return UNAVAILABLE — **never fake success** (P0.1).
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
import structlog

from app.core.config.settings import get_settings
from app.core.exceptions.handlers import ValidationError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ShahkarResult = Literal["matched", "mismatch", "unavailable"]


class ZohalIdentityProvider:
    """httpx adapter for the Zohal identity-inquiry service (Karta Zohal.php)."""

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.IDENTITY_PROVIDER_BASE_URL).rstrip("/")
        self._token = token if token is not None else settings.IDENTITY_PROVIDER_TOKEN
        self._timeout = settings.IDENTITY_PROVIDER_TIMEOUT_SECONDS

    @property
    def is_configured(self) -> bool:
        """A provider without a real credential must never be queried."""
        return bool(self._token.strip())

    async def shahkar_match(self, mobile: str, national_code: str) -> ShahkarResult:
        """Verify that a mobile number belongs to the given national code.

        Returns ``matched`` / ``mismatch`` based on the provider answer and
        ``unavailable`` when the service is not configured or unreachable —
        an outage must look like an outage, not like a verification failure.
        """
        if not self.is_configured:
            return "unavailable"

        payload = {"mobile": mobile, "national_code": national_code}
        url = f"{self._base_url}/services/inquiry/shahkar"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            await logger.awarning("identity_provider_unreachable", error=str(exc))
            return "unavailable"

        if resp.status_code != 200:
            await logger.awarning(
                "identity_provider_http_error",
                status_code=resp.status_code,
            )
            return "unavailable"

        try:
            body: dict[str, Any] = resp.json()
        except ValueError:
            return "unavailable"

        data = (body.get("response_body") or {}).get("data") or {}
        if body.get("result") == 1 and isinstance(data.get("matched"), bool):
            return "matched" if data["matched"] is True else "mismatch"

        await logger.awarning("identity_provider_unexpected_response")
        return "unavailable"

    async def national_identity_inquiry(
        self, national_code: str, birth_date: str
    ) -> dict[str, Any] | None:
        """Fetch civil-registry data (Zahel/Zohal) for a national code.

        Returns the provider ``data`` payload on success, ``None`` when the
        provider is unconfigured/unreachable. Callers must treat ``None``
        as UNAVAILABLE — data is only persisted from a real response.
        """
        if not self.is_configured:
            return None

        payload = {"national_code": national_code, "birth_date": birth_date}
        url = f"{self._base_url}/services/inquiry/national_identity_inquiry"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.HTTPError as exc:
            await logger.awarning("identity_provider_unreachable", error=str(exc))
            return None

        if resp.status_code != 200:
            return None
        try:
            body: dict[str, Any] = resp.json()
        except ValueError:
            return None

        data = (body.get("response_body") or {}).get("data") or {}
        if body.get("result") == 1 and data.get("matched") is True:
            if data.get("alive") is False:
                raise ValidationError("این کد ملی در قید حیات نیست")
            return data
        return None


def get_identity_provider() -> ZohalIdentityProvider:
    """Build the configured identity provider adapter."""
    return ZohalIdentityProvider()
