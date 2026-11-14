"""USD→Toman updater (Nobitex): rate parsing, rounding, config, and wiring.

Pins the ported WordPress plugin's business rules and this project's
conventions around them:

* the Nobitex payload carries Rial (the plugin divided by 10 for Toman) —
  ``parse_rate_rial`` returns Rial and refuses insane payloads the plugin
  would have written straight into every price;
* ``smart_round_rial`` reproduces the plugin's own worked example
  (111,612 with rounding 200 → 111,600);
* the manual rate defaults to 0, NOT the plugin's 50000 — a stale default
  would silently halve the catalog the first time the API is unreachable;
* ``log_enabled`` off must NOT stop price updates (the plugin's switch did);
* server-owned ``last_*`` fields are refused from client writes;
* the task is registered in celery (beat + TASK_MODULES), the admin router is
  mounted, permissions exist, and the audit registry captures the USD fields.

Source-pin tests use exact expressions (a bare name is satisfied by a
comment — see test_chat_widget.py).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

# ── Nobitex payload parsing ───────────────────────────────────────────────


def test_parse_accepts_string_and_numeric_last_trade_price():
    """The API returns the number as a string; the plugin tolerated both."""
    from app.modules.currency.application.nobitex_client import parse_rate_rial

    # A realistic 2026 free-market rate: 185,000 Toman = 1,850,000 Rial.
    assert parse_rate_rial(json.dumps({"lastTradePrice": "1850000"})) == 1850000
    assert parse_rate_rial(json.dumps({"lastTradePrice": 1850000})) == 1850000
    assert parse_rate_rial(json.dumps({"lastTradePrice": "1850000.0"})) == 1850000


def test_parse_refuses_insane_or_missing_payloads():
    """A zero/negative/absurd/hostile body must yield None (manual fallback).

    The plugin wrote whatever came back into every product price —
    ``lastTradePrice: 0`` would have zeroed the whole catalog.
    """
    from app.modules.currency.application.nobitex_client import parse_rate_rial

    assert parse_rate_rial(json.dumps({"lastTradePrice": "0"})) is None
    assert parse_rate_rial(json.dumps({"lastTradePrice": -5})) is None
    assert parse_rate_rial(json.dumps({"lastTradePrice": "abc"})) is None
    assert parse_rate_rial(json.dumps({"lastTradePrice": None})) is None
    assert parse_rate_rial(json.dumps({"status": "ok"})) is None
    # Below/above the sanity window: a broken or unit-confused payload.
    assert parse_rate_rial(json.dumps({"lastTradePrice": 999})) is None  # < 100 Toman
    assert parse_rate_rial(json.dumps({"lastTradePrice": 200_000_000})) is None  # > 10M Toman
    # Not JSON, not even an object.
    assert parse_rate_rial("<html>502</html>") is None
    assert parse_rate_rial(json.dumps([1, 2, 3])) is None
    assert parse_rate_rial(json.dumps({"lastTradePrice": float("nan")})) is None


def test_parse_stats_endpoint_body_and_fallback_chain():
    """The stats endpoint is the live fallback when the order book 403s.

    Measured live 2026-10-16: the order-book endpoint answers 403 to
    non-browser clients from some networks (Cloudflare) while
    ``/market/stats`` answers 200 with the same last-trade value. A
    single-endpoint client would silently price off the manual fallback
    forever on such a host.
    """
    import asyncio

    from app.modules.currency.application.nobitex_client import (
        NOBITEX_ORDERBOOK_URL,
        NOBITEX_STATS_URL,
        fetch_rate_rial,
        parse_stats_rate_rial,
    )

    real_body = (
        '{"status":"ok","stats":{"usdt-rls":{"isClosed":false,'
        '"bestSell":"2667800","bestBuy":"2654710","latest":"2654710"}}}'
    )
    assert parse_stats_rate_rial(real_body) == 2654710
    # Uppercase key tolerance.
    assert (
        parse_stats_rate_rial('{"stats":{"USDT-RLS":{"latest":"2654710"}}}') == 2654710
    )
    # Garbage shapes refuse.
    assert parse_stats_rate_rial("not json") is None
    assert parse_stats_rate_rial('{"stats":{}}') is None
    assert parse_stats_rate_rial('{"stats":{"usdt-rls":{"latest":"0"}}}') is None
    assert parse_stats_rate_rial('{"stats":{"usdt-rls":{}}}') is None

    class RoutingTransport:
        """403s the order book, serves stats — the measured live shape."""

        def __init__(self):
            self.calls: list[str] = []

        async def get_json(self, url: str, timeout: float):
            self.calls.append(url)
            if url == NOBITEX_ORDERBOOK_URL:
                return 403, "<html>cloudflare</html>"
            if url == NOBITEX_STATS_URL:
                return 200, real_body
            raise AssertionError(f"unexpected url {url}")

    t = RoutingTransport()
    rate = asyncio.run(fetch_rate_rial(t))
    assert rate == 2654710
    assert t.calls == [NOBITEX_ORDERBOOK_URL, NOBITEX_STATS_URL]

    class AllDownTransport:
        async def get_json(self, url: str, timeout: float):
            raise ConnectionError("down")

    assert asyncio.run(fetch_rate_rial(AllDownTransport())) is None

    class OrderbookWinsTransport:
        """When the order book answers, stats is never consulted."""

        def __init__(self):
            self.calls: list[str] = []

        async def get_json(self, url: str, timeout: float):
            self.calls.append(url)
            return 200, json.dumps({"lastTradePrice": "1850000"})

    t2 = OrderbookWinsTransport()
    assert asyncio.run(fetch_rate_rial(t2)) == 1850000
    assert t2.calls == [NOBITEX_ORDERBOOK_URL]


# ── Rounding (the plugin's smart_round_price) ─────────────────────────────


def test_smart_round_matches_the_plugins_worked_example():
    """The plugin's own doc example, translated to Rial: 111,612 Toman → 111,600.

    111,612 Toman is 1,116,120 Rial; rounding 200 Toman = 2,000 Rial step.
    """
    from decimal import Decimal

    from app.modules.currency.application.price_update_service import smart_round_rial

    assert smart_round_rial(Decimal("1116120"), 200) == 1116000
    # Half-up, mirroring PHP round()'s half-away-from-zero. 1,116,100 Rial is
    # 558.05 steps → 558 steps × 2,000 = 1,116,000.
    assert smart_round_rial(Decimal("1116100"), 200) == 1116000
    assert smart_round_rial(Decimal("1115000"), 200) == 1116000  # 557.5 → 558 steps
    # Rounding 1 Toman = whole-Toman rounding (the plugin's <=1 branch):
    # 1,116,125 Rial = 111,612.5 Toman → 111,613 Toman = 1,116,130 Rial.
    assert smart_round_rial(Decimal("1116125"), 1) == 1116130
    assert smart_round_rial(Decimal("0"), 100) == 0


# ── Config: defaults, coercion, server-owned fields ───────────────────────


def test_defaults_follow_site_rules_not_the_plugins():
    """manual_rate_rial defaults to 0 (plugin: 50000); log switch is ours."""
    from app.modules.currency.application.rate_config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["manual_rate_rial"] == 0
    assert DEFAULT_CONFIG["update_interval_minutes"] == 5
    assert DEFAULT_CONFIG["price_rounding_toman"] == 100
    assert DEFAULT_CONFIG["api_enabled"] is True
    assert DEFAULT_CONFIG["enabled"] is True


def test_coerce_clamps_integers_into_bounds():
    from app.modules.currency.application.rate_config import DEFAULT_CONFIG, _coerce

    merged = dict(DEFAULT_CONFIG)
    merged.update(
        {
            "manual_rate_rial": -50,
            "update_interval_minutes": 0,
            "price_rounding_toman": "abc",
            "enabled": 0,
        }
    )
    out = _coerce(merged)
    assert out["manual_rate_rial"] == 0
    assert out["update_interval_minutes"] == 1
    assert out["price_rounding_toman"] == 1  # junk falls back to the lower bound
    assert out["enabled"] is False

    merged = dict(DEFAULT_CONFIG)
    merged.update({"update_interval_minutes": 99999, "manual_rate_rial": 10**12})
    out = _coerce(merged)
    assert out["update_interval_minutes"] == 1440
    assert out["manual_rate_rial"] <= 1_000_000_000


def test_server_owned_runtime_keys_are_refused_from_writes():
    """A client echo of last_rate_rial must not be accepted (server-owned)."""
    from app.modules.currency.application import rate_config

    assert "last_rate_rial" in rate_config.SERVER_OWNED_KEYS
    assert "last_attempt_at" in rate_config.SERVER_OWNED_KEYS
    # The filter is the exact expression in set_config.
    import inspect

    src = inspect.getsource(rate_config.set_config)
    assert "if key not in DEFAULT_CONFIG or key in SERVER_OWNED_KEYS:" in src


def test_runtime_state_update_refuses_non_runtime_keys():
    """update_runtime_state(scheduled=True) would round-trip operator settings."""
    from app.modules.currency.application import rate_config

    async def _boom():
        await rate_config.update_runtime_state(None, scheduled=True)  # type: ignore[arg-type]

    import asyncio

    try:
        asyncio.run(_boom())
    except ValueError as exc:
        assert "scheduled" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("non-runtime key was accepted")


# ── is_due: the interval gate the beat tick reads ─────────────────────────


def test_is_due_respects_interval_switch_and_failed_attempts():
    from app.modules.currency.application.rate_config import is_due

    now = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
    cfg = {"enabled": True, "update_interval_minutes": 5}

    # Never ran → due.
    assert is_due({**cfg, "last_attempt_at": None}, now=now) is True
    # Ran 4 minutes ago → not due; 5 minutes ago → due.
    recent = (now - timedelta(minutes=4)).isoformat()
    assert is_due({**cfg, "last_attempt_at": recent}, now=now) is False
    old = (now - timedelta(minutes=5)).isoformat()
    assert is_due({**cfg, "last_attempt_at": old}, now=now) is True
    # A FAILED attempt still counts (no per-minute retry storm).
    assert is_due({**cfg, "last_attempt_at": recent}, now=now) is False
    # Disabled → never due automatically.
    assert is_due({**cfg, "enabled": False, "last_attempt_at": None}, now=now) is False
    # Unparseable timestamp → due (self-heals a corrupted row).
    assert is_due({**cfg, "last_attempt_at": "garbage"}, now=now) is True


def test_next_run_at_is_attempt_plus_interval_and_none_when_disabled():
    from app.modules.currency.application.rate_config import next_run_at

    stamp = "2026-10-16T12:00:00+00:00"
    value = next_run_at(
        {
            "enabled": True,
            "update_interval_minutes": 5,
            "last_attempt_at": stamp,
        }
    )
    assert value is not None
    assert datetime.fromisoformat(value) == datetime(2026, 10, 16, 12, 5, tzinfo=UTC)
    assert next_run_at({"enabled": False, "last_attempt_at": stamp}) is None


# ── Rate resolution: API first, manual fallback, none → failure ───────────


def test_resolve_rate_prefers_api_then_manual_then_none():
    import asyncio

    from app.modules.currency.application.price_update_service import resolve_rate_rial

    class FakeTransport:
        def __init__(self, body: str | None):
            self._body = body

        async def get_json(self, url: str, timeout: float):
            if self._body is None:
                raise ConnectionError("down")
            return 200, self._body

    cfg_api = {"api_enabled": True, "manual_rate_rial": 900000}
    rate, source = asyncio.run(
        resolve_rate_rial(cfg_api, FakeTransport(json.dumps({"lastTradePrice": "1850000"})))
    )
    assert (rate, source) == (1850000, "api")

    # API down → manual.
    rate, source = asyncio.run(resolve_rate_rial(cfg_api, FakeTransport(None)))
    assert (rate, source) == (900000, "manual")

    # API off → manual without a call.
    rate, source = asyncio.run(
        resolve_rate_rial(
            {"api_enabled": False, "manual_rate_rial": 900000}, FakeTransport(None)
        )
    )
    assert (rate, source) == (900000, "manual")

    # Neither → none (the run must fail loudly, not price at a guess).
    rate, source = asyncio.run(
        resolve_rate_rial({"api_enabled": False, "manual_rate_rial": 0}, FakeTransport(None))
    )
    assert (rate, source) == (None, "none")


# ── Wiring pins ───────────────────────────────────────────────────────────


def test_sweep_task_is_registered_and_scheduled():
    from app.worker.celery_app import TASK_MODULES, celery_app

    assert "app.modules.currency.application.tasks" in TASK_MODULES
    beat = celery_app.conf.beat_schedule
    assert "run-usd-rate-update" in beat
    assert (
        beat["run-usd-rate-update"]["task"]
        == "app.modules.currency.application.tasks.run_usd_rate_update"
    )


def test_admin_router_is_mounted_in_main():
    """A module missing from module_router_specs 404s while everything looks fine."""
    import inspect

    from app import main as main_module

    src = inspect.getsource(main_module._include_routers)
    assert '("app.modules.currency.api", "/currency", ["currency"]),' in src


def test_permissions_are_in_the_catalog():
    from app.modules.rbac.application.permission_catalog import CATALOG_CODENAMES

    assert "currency:read" in CATALOG_CODENAMES
    assert "currency:write" in CATALOG_CODENAMES


def test_variant_model_has_numeric_usd_columns_not_float():
    """Money is never a float — 9.99 must survive the round trip exactly."""
    import inspect

    from app.modules.catalog.domain import models as catalog_models

    src = inspect.getsource(catalog_models.ProductVariant)
    assert "usd_price: Mapped[Decimal | None] = mapped_column(" in src
    assert "Numeric(12, 2)" in src
    assert "usd_price: Mapped[float" not in src


def test_audit_registry_captures_usd_fields():
    from app.modules.audit.application.change_tracking import TRACKED_ENTITIES

    fields = TRACKED_ENTITIES["variant"]["fields"]
    assert "usd_price" in fields
    assert "usd_sale_price" in fields


def test_log_switch_does_not_stop_the_update():
    """The plugin returned early when its log switch was off; this must not.

    Structural pin, searched on the config KEY (``log_enabled``), not on one
    guard spelling: an early return can be written ``if not
    config.get("log_enabled", True): return`` (the plugin's exact shape) and
    an exact-positive-form search would not see it. The FIRST mention of the
    key anywhere in ``_apply_rate`` must come after the price write — so no
    early-exit can gate the writes on it, whatever its phrasing.
    """
    import inspect

    from app.modules.currency.application import price_update_service as svc

    apply_src = inspect.getsource(svc._apply_rate)
    write_idx = apply_src.index("variant.price = new_price")
    first_mention_idx = apply_src.index("log_enabled")
    runtime_idx = apply_src.index("await rate_config.update_runtime_state(")
    assert write_idx < first_mention_idx, "log switch is consulted before the price write"
    assert first_mention_idx < runtime_idx, "runtime state update stays outside the guard"
    # The plugin's wp-option early-return pattern does not exist here at all.
    assert "if get_option" not in apply_src


def test_variant_update_zero_clears_usd_price():
    """0 on usd_price takes the variant OUT of the sweep (None in the DB)."""
    import inspect

    from app.modules.catalog.application.catalog_service import ProductService

    src = inspect.getsource(ProductService.update_variant)
    assert 'for usd_field in ("usd_price", "usd_sale_price"):' in src
    assert "update_data[usd_field] = None" in src
