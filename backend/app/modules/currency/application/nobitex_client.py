"""Nobitex USDT/IRT rate client (the plugin's ``fetch_current_rate``).

Follows the ``n8n_client`` / ``akismet_client`` seam: a ``Transport`` protocol
so tests swap a fake, every failure swallowed into ``None`` (the caller falls
back to the manual rate), and a bounded timeout on every call.

Endpoints, in order:

1. ``https://apiv2.nobitex.ir/v3/orderbook/USDTIRT`` (``lastTradePrice``) —
   plugin parity, the endpoint the WordPress plugin used. Measured live
   2026-10-16: this endpoint sits behind Cloudflare and answers **403 for
   non-browser clients from some networks** (verified from the dev host:
   3/3 attempts 403 with and without browser headers, while the stats
   endpoint below answers 200 from the same host). On the plugin's hosting
   it worked; on a network where it does not, a single-endpoint client
   would silently price the whole catalog off the manual fallback forever.
2. ``https://apiv2.nobitex.ir/market/stats?srcCurrency=usdt&dstCurrency=rls``
   (``stats["usdt-rls"]["latest"]``) — the official market-stats endpoint,
   same last-trade value, verified 200 from the same host on the same day.
   Deliberate resilience addition over the plugin; when endpoint 1 answers,
   its value is used (plugin parity preserved).

Both endpoints quote Rial. The plugin divided by 10 to get Toman; this
module keeps Rial as-is (site money convention, ADR-012) and lets the
display layer divide — the plugin's ``/ 10`` is the evidence for the unit,
and that assumption is pinned by a unit test.

A sanity check the plugin did not have: it wrote whatever the API returned
straight into every price, so a broken response with ``lastTradePrice: 0``
(or a string, or a negative) would have set the whole catalog to garbage.
Both parsers refuse non-positive and absurd values, and the caller falls
back to the manual rate — a failed fetch, not a worse price.
"""

from __future__ import annotations

import json
import math
from typing import Protocol

import httpx
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Plugin parity: the v3 order book for Tether against the Iranian Toman.
NOBITEX_ORDERBOOK_URL = "https://apiv2.nobitex.ir/v3/orderbook/USDTIRT"

#: Official market-stats endpoint (same last-trade price). Used when the
#: order book endpoint is unreachable or refuse-by-Cloudflare.
NOBITEX_STATS_URL = (
    "https://apiv2.nobitex.ir/market/stats?srcCurrency=usdt&dstCurrency=rls"
)

#: Plugin parity: 15-second timeout.
_TIMEOUT_SECONDS = 15.0

#: Sanity window for the parsed rate, in Rial (below 100 Toman or above
#: 10,000,000 Toman per USD the payload is broken — a stray zero, an error
#: page with a number in it, a unit-confused proxy). The window is wide
#: enough to cover any real market for years, including redenomination
#: upside; its job is to catch zero/negative/garbage, which the plugin
#: wrote straight into every price.
MIN_SANE_RATE_RIAL = 1_000
MAX_SANE_RATE_RIAL = 100_000_000


class Transport(Protocol):
    """The one method the client needs; a fake replaces it in tests."""

    async def get_json(self, url: str, timeout: float) -> tuple[int, str]: ...


class HttpxTransport:
    """Real transport over httpx."""

    async def get_json(self, url: str, timeout: float) -> tuple[int, str]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers={"Accept-Encoding": "gzip"})
            return response.status_code, response.text


def _sane_rial(raw: object) -> int | None:
    """Parse one candidate value and apply the sanity window."""
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    value_int = int(value)
    if not (MIN_SANE_RATE_RIAL <= value_int <= MAX_SANE_RATE_RIAL):
        return None
    return value_int


def parse_rate_rial(body: str) -> int | None:
    """``lastTradePrice`` (Rial) out of a Nobitex order-book body, or None.

    Accepts the string form (``"109861000"``) and the numeric form the plugin
    tolerated via PHP ``floatval``. Returns ``None`` for anything that fails
    the sanity window, so the caller falls back to the manual rate.
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    return _sane_rial(data.get("lastTradePrice"))


def parse_stats_rate_rial(body: str) -> int | None:
    """``stats["usdt-rls"]["latest"]`` (Rial) out of a market-stats body.

    ``latest`` is the last trade price — the same quantity the order-book
    endpoint reports as ``lastTradePrice`` (verified live 2026-10-16:
    ``latest: "2654710"`` Rial while the order book was 403).
    """
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    stats = data.get("stats")
    if not isinstance(stats, dict):
        return None
    pair = stats.get("usdt-rls")
    if isinstance(pair, dict):
        return _sane_rial(pair.get("latest"))
    # Tolerate the key form "USDT-RLS" some deployments return.
    for key, pair in stats.items():
        if isinstance(pair, dict) and str(key).lower() == "usdt-rls":
            return _sane_rial(pair.get("latest"))
    return None


async def fetch_rate_rial(transport: Transport | None = None) -> int | None:
    """Fetch the current USDT/IRT rate in Rial, or ``None`` on any failure.

    Order book first (plugin parity), market stats as the fallback. ``None``
    only when both give nothing usable — the caller then uses the manual
    rate or fails the run loudly.
    """
    transport = transport or HttpxTransport()

    try:
        status, body = await transport.get_json(NOBITEX_ORDERBOOK_URL, _TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001 — network failure means "try the fallback"
        await logger.awarning("nobitex_orderbook_failed", error=str(exc))
        status, body = 0, ""
    if status == 200:
        rate = parse_rate_rial(body)
        if rate is not None:
            return rate
        await logger.awarning("nobitex_orderbook_bad_payload", body_prefix=body[:200])
    else:
        await logger.awarning("nobitex_orderbook_http_error", status=status)

    try:
        status, body = await transport.get_json(NOBITEX_STATS_URL, _TIMEOUT_SECONDS)
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("nobitex_stats_failed", error=str(exc))
        return None
    if status != 200:
        await logger.awarning("nobitex_stats_http_error", status=status)
        return None
    rate = parse_stats_rate_rial(body)
    if rate is None:
        await logger.awarning("nobitex_stats_bad_payload", body_prefix=body[:200])
    return rate


__all__ = [
    "NOBITEX_ORDERBOOK_URL",
    "NOBITEX_STATS_URL",
    "HttpxTransport",
    "Transport",
    "fetch_rate_rial",
    "parse_rate_rial",
    "parse_stats_rate_rial",
]
