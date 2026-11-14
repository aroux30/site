"""Referral + bonus reward system: config math, idempotency wiring, contracts.

Pins the pure logic and the at-most-once wiring of the ported reward system
(2026-10-14, from the VPN project reference + arena champion design):

* config coercion clamps percents to 0..100 and amounts to >= 0 (the arena's
  "clamp percent" red item);
* the wallet partial unique index name and the per-order unique constraint
  appear in the MODEL declarations (a regression that drops either re-opens
  double-payment);
* the sweep task is registered in celery (beat entry + TASK_MODULES);
* integer math only — no float/Decimal in the payout service (ADR-012);
* level-2 earnings are counted for the earner (chain walk), not only level-1.

Source-pin tests use exact expressions (see test_chat_widget.py for why bare
names are vacuous — a comment satisfies a substring).
"""

from __future__ import annotations

import inspect


# ── Config coercion ───────────────────────────────────────────────────────


def test_config_clamps_percents_and_amounts():
    """Percent fields clamp to 0..100; amounts clamp to >= 0; junk → 0."""
    from app.modules.referrals.application.referral_config import (
        DEFAULT_CONFIG,
        _coerce,
    )

    merged = dict(DEFAULT_CONFIG)
    merged.update(
        {
            "commission_percent_l1": 150,
            "commission_percent_l2": -3,
            "recharge_bonus_percent": 999,
            "signup_gift_l1": -500,
            "min_order_total": "abc",
        }
    )
    out = _coerce(merged)
    assert out["commission_percent_l1"] == 100
    assert out["commission_percent_l2"] == 0
    assert out["recharge_bonus_percent"] == 100
    assert out["signup_gift_l1"] == 0
    assert out["min_order_total"] == 0


def test_config_accepts_two_decimal_percents():
    """Percents keep up to two decimals (owner: 0.01 and 1.25 must work)."""
    from app.modules.referrals.application.referral_config import _coerce

    out = _coerce({"commission_percent_l1": 1.25, "recharge_bonus_percent": 0.01})
    assert out["commission_percent_l1"] == 1.25
    assert out["recharge_bonus_percent"] == 0.01
    # More than two decimals rounds to the stored precision.
    out = _coerce({"commission_percent_l1": 1.257})
    assert out["commission_percent_l1"] == 1.26


def test_percent_to_bp_conversion_is_exact():
    """Percent → basis points is the single conversion into integer money math."""
    from app.modules.referrals.application.referral_config import (
        bp_to_percent,
        percent_to_bp,
    )

    assert percent_to_bp(1) == 100
    assert percent_to_bp(1.25) == 125
    assert percent_to_bp(0.01) == 1
    assert percent_to_bp(100) == 10_000
    assert percent_to_bp(0.001) == 0  # below the offered precision
    assert percent_to_bp("2.5") == 250  # strings from JSON round-trips
    assert percent_to_bp(None) == 0
    assert bp_to_percent(125) == 1.25


def test_reject_extra_decimals_refuses_three_decimals():
    """The direct-API gate: a 3+-decimal percent raises, 2 decimals pass.

    Float noise must not cause false rejections — 1.26 is exactly valid
    even though 1.26 * 100 is not exactly 126 in binary floating point.
    """
    import pytest

    from app.core.exceptions.handlers import ValidationError
    from app.modules.referrals.application.referral_config import (
        _reject_extra_decimals,
    )

    # Valid: zero/one/two decimals and integers.
    _reject_extra_decimals({"commission_percent_l1": 1})
    _reject_extra_decimals({"commission_percent_l1": 1.2})
    _reject_extra_decimals({"commission_percent_l1": 1.25})
    _reject_extra_decimals({"commission_percent_l1": 1.26})
    _reject_extra_decimals({"commission_percent_l1": "0.01"})
    _reject_extra_decimals({"commission_percent_l1": 100})

    # Refused: three or more decimals.
    for bad in (1.257, 0.001, "2.345", 33.333):
        with pytest.raises(ValidationError):
            _reject_extra_decimals({"recharge_bonus_percent": bad})

    # Non-numeric text is refused with the "must be a number" error.
    with pytest.raises(ValidationError):
        _reject_extra_decimals({"commission_percent_l1": "abc"})

    # Keys that are not percents are not examined.
    _reject_extra_decimals({"signup_gift_l1": 12345.678})


def test_template_sanitizer_strips_html_tags():
    """Stored-XSS defense: template fields never keep HTML tags.

    The current renderers escape, so this is depth-in-depth — it removes the
    payload from STORAGE so no future renderer (email HTML, Telegram
    parse_mode, a raw innerHTML table) can resurrect it.
    """
    from app.modules.referrals.application.referral_config import (
        _sanitize_templates,
    )

    cfg = {
        "gift_notif_text": "<img src=x onerror=alert(1)>مبلغ {amount} تومان",
        "commission_notif_text": "ok بدون تگ",
        "recharge_bonus_notif_text": "<script>evil()</script>بونوس",
    }
    _sanitize_templates(cfg)
    assert "<" not in cfg["gift_notif_text"]
    assert "{amount}" in cfg["gift_notif_text"]  # placeholder survives
    assert "مبلغ" in cfg["gift_notif_text"]  # Persian text survives
    assert cfg["commission_notif_text"] == "ok بدون تگ"  # untouched
    assert "<" not in cfg["recharge_bonus_notif_text"]
    # Non-template keys are never touched by the sanitizer.
    cfg2 = {"signup_gift_l1": 5000}
    _sanitize_templates(cfg2)
    assert cfg2["signup_gift_l1"] == 5000


def test_set_config_runs_the_sanitizer():
    """The sanitizer must be WIRED into set_config (presence is not wiring)."""
    from app.modules.referrals.application import referral_config

    src = inspect.getsource(referral_config.set_config)
    assert "_sanitize_templates(merged)" in src


def test_per_module_switches_gate_each_payout_path():
    """Owner: the modules must be switchable ONE BY ONE, not only all at once.

    Each module gate must be CALLED inside its payout path (wiring, not
    presence): gift gate in pay_signup_gift_for_referral, commission gate in
    process_order_commissions AND the commission payout pass, recharge gate
    in both recharge-bonus paths.
    """
    from app.modules.referrals.application import referral_service

    gift_src = inspect.getsource(
        referral_service.ReferralService.pay_signup_gift_for_referral
    )
    assert 'referral_config.module_enabled(cfg, "gift")' in gift_src

    create_src = inspect.getsource(
        referral_service.ReferralService.process_order_commissions
    )
    assert 'referral_config.module_enabled(cfg, "commission")' in create_src

    pay_src = inspect.getsource(referral_service.ReferralService._pay_commission_row)
    assert 'referral_config.module_enabled(cfg, "commission")' in pay_src

    recharge_src = inspect.getsource(
        referral_service.ReferralService.apply_recharge_bonus
    )
    assert 'referral_config.module_enabled(cfg, "recharge_bonus")' in recharge_src

    sweep_src = inspect.getsource(
        referral_service.ReferralService.pay_pending_recharge_bonuses
    )
    assert 'referral_config.module_enabled(cfg, "recharge_bonus")' in sweep_src


def test_module_enabled_logic():
    """module_enabled: switch off OR payouts zero → the module is off."""
    from app.modules.referrals.application.referral_config import (
        DEFAULT_CONFIG,
        module_enabled,
    )

    cfg = dict(DEFAULT_CONFIG)
    # all payouts zero → everything off
    assert not module_enabled(cfg, "gift")
    assert not module_enabled(cfg, "commission")
    assert not module_enabled(cfg, "recharge_bonus")

    # payouts configured → on
    cfg.update({"signup_gift_l1": 100_000, "commission_percent_l1": 5,
                "recharge_bonus_percent": 3})
    assert module_enabled(cfg, "gift")
    assert module_enabled(cfg, "commission")
    assert module_enabled(cfg, "recharge_bonus")

    # switch off overrides a non-zero payout — and ONLY for that module
    cfg["gift_enabled"] = False
    assert not module_enabled(cfg, "gift")
    assert module_enabled(cfg, "commission")
    assert module_enabled(cfg, "recharge_bonus")


def test_switching_one_module_off_does_not_stop_the_others():
    """The activation helper must treat 'any module on' as active.

    If gift is off but commission is on with payouts, the program is active —
    a regression here would freeze the whole program's cut-off logic.
    """
    from app.modules.referrals.application.referral_config import (
        DEFAULT_CONFIG,
        _has_payouts,
    )

    cfg = dict(DEFAULT_CONFIG)
    cfg.update({"gift_enabled": False, "commission_percent_l1": 5})
    assert _has_payouts(cfg) is True

    cfg2 = dict(DEFAULT_CONFIG)
    cfg2.update({"gift_enabled": False, "commission_enabled": False,
                 "recharge_bonus_enabled": False, "signup_gift_l1": 100_000})
    assert _has_payouts(cfg2) is False


def test_config_merge_keeps_defaults_for_missing_keys():
    """A stored partial config never loses keys — defaults fill the gaps."""
    from app.modules.referrals.application.referral_config import (
        DEFAULT_CONFIG,
        _merged,
    )

    out = _merged({"signup_gift_l1": 50_000})
    assert out["signup_gift_l1"] == 50_000
    assert out["commission_percent_l1"] == DEFAULT_CONFIG["commission_percent_l1"]


def test_render_template_formats_amount_in_toman():
    """{amount} renders Rial → Toman (1 Toman = 10 Rial), never raw Rial."""
    from app.modules.referrals.application.referral_config import render_template

    text = render_template("مبلغ {amount} تومان", amount_rial=50_000)
    assert "5,000" in text
    assert "50,000" not in text


# ── Activation cut-off (off → on must refresh the stamp) ──────────────────


def _active(percent: float = 5) -> dict:
    """A minimal config that is switched on and pays something."""
    from app.modules.referrals.application.referral_config import DEFAULT_CONFIG

    cfg = dict(DEFAULT_CONFIG)
    cfg.update({"enabled": True, "commission_percent_l1": percent})
    return cfg


def test_first_activation_stamps_now():
    """Turning the program on for the first time stamps the cut-off."""
    from app.modules.referrals.application.referral_config import (
        DEFAULT_CONFIG,
        _next_started_at,
    )

    now = "2026-10-14T10:00:00+00:00"
    current = dict(DEFAULT_CONFIG)  # never activated
    merged = _active()
    assert _next_started_at(current, merged, now) == now


def test_reactivation_refreshes_the_stamp():
    """off → on after days off must move the cut-off to the new activation.

    The owner's question: خاموش کنیم و بعد چند روز روشن کنیم — تاریخ باید
    بهروز شود، وگرنه دورهٔ خاموشی هنگام روشن‌شدن پرداخت می‌شود.
    """
    from app.modules.referrals.application.referral_config import _next_started_at

    old = "2026-10-10T10:00:00+00:00"
    now = "2026-10-14T10:00:00+00:00"
    current = _active()
    current["program_started_at"] = old
    current["enabled"] = False  # the program was switched off

    merged = dict(current)
    merged["enabled"] = True  # now switched back on

    assert _next_started_at(current, merged, now) == now


def test_editing_while_active_keeps_the_stamp():
    """Changing a percent while ON must not move the cut-off.

    Moving it would strip eligibility from every order placed since the
    last save — the opposite of a harmless settings tweak.
    """
    from app.modules.referrals.application.referral_config import _next_started_at

    old = "2026-10-10T10:00:00+00:00"
    now = "2026-10-14T10:00:00+00:00"
    current = _active(percent=5)
    current["program_started_at"] = old

    merged = _active(percent=7)  # same activation, different percent
    merged["program_started_at"] = old

    assert _next_started_at(current, merged, now) == old


def test_zero_amounts_do_not_activate():
    """Saving with every payout at zero must not stamp an activation."""
    from app.modules.referrals.application.referral_config import (
        DEFAULT_CONFIG,
        _next_started_at,
    )

    now = "2026-10-14T10:00:00+00:00"
    current = dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)  # all payouts zero
    assert _next_started_at(current, merged, now) is None


def test_disabling_keeps_the_stamp_until_reactivation():
    """Switching off alone changes nothing; the stamp survives to be replaced."""
    from app.modules.referrals.application.referral_config import _next_started_at

    old = "2026-10-10T10:00:00+00:00"
    now = "2026-10-14T10:00:00+00:00"
    current = _active()
    current["program_started_at"] = old

    merged = dict(current)
    merged["enabled"] = False

    assert _next_started_at(current, merged, now) == old


# ── Model-level at-most-once wiring (exact anchors) ───────────────────────


def test_wallet_partial_unique_index_declared_in_model():
    """The money-level backstop must stay declared on the wallet model.

    A regression that drops this index re-opens double-payment of any reward;
    the anchor is the exact index name inside the model source.
    """
    from app.modules.wallet.domain import models as wallet_models

    src = inspect.getsource(wallet_models)
    assert '"uq_wallet_referral_rewards_once"' in src
    # The partial WHERE must cover the referral/bonus reference types —
    # without it the index would either not apply or block unrelated rows.
    assert "'referral_signup_gift_l1', 'referral_signup_gift_l2', " in src
    assert "'referral_commission_l1', 'referral_commission_l2', " in src


def test_commission_order_earner_unique_constraint_declared():
    """One commission per order per earner — the sweep's concurrency backstop."""
    from app.modules.referrals.domain import models as referral_models

    src = inspect.getsource(referral_models)
    assert 'name="uq_referral_commissions_order_earner"' in src


def test_reward_history_index_declared_in_model():
    """The history-paging index must stay declared (migration refbon2).

    Measured at 20k reward rows: the kind-filtered page went from 31ms to
    0.07ms with this index. A regression that drops the declaration lets
    autogenerate remove it and the admin tab slows down silently.
    """
    from app.modules.wallet.domain import models as wallet_models

    src = inspect.getsource(wallet_models)
    assert '"ix_wallet_reward_history"' in src
    assert 'text("created_at DESC")' in src


def test_commission_status_has_expired_member():
    """Dead commissions must be terminally closed, not swept forever."""
    from app.modules.referrals.domain.models import CommissionStatus

    assert CommissionStatus.EXPIRED.value == "expired"


# ── Service wiring (exact anchors, per the repo's pinning discipline) ─────


def test_payout_credits_inside_savepoint_on_exact_reference_types():
    """_credit_reward must attempt the credit inside a savepoint and catch
    IntegrityError — that IS the at-most-once-or-retryable structure.

    Anchors are the exact expressions; a comment cannot satisfy them.
    """
    from app.modules.referrals.application import referral_service

    src = inspect.getsource(referral_service._credit_reward)
    assert "async with db.begin_nested():" in src
    assert "except IntegrityError:" in src
    assert "reference_type=reference_type" in src
    assert "reference_id=reference_id" in src


def test_recharge_bonus_uses_integer_math_and_wallet_index_reference():
    """Percent math must be integer bp math (// 10_000), never float."""
    from app.modules.referrals.application import referral_service

    src = inspect.getsource(referral_service.ReferralService.apply_recharge_bonus)
    assert "bonus = (amount_rial * percent_bp) // 10_000" in src
    assert "referral_config.percent_to_bp(" in src
    assert "REF_RECHARGE_BONUS" in src


def test_commission_percent_is_integer_math_with_cap():
    """Commission = integer bp math of total, honouring the per-event cap."""
    from app.modules.referrals.application import referral_service

    src = inspect.getsource(referral_service.ReferralService.process_order_commissions)
    assert "amount = (order.total * percent_bp) // 10_000" in src
    assert "if cap > 0 and amount > cap:" in src


def test_no_float_or_decimal_in_payout_service():
    """ADR-012: money code is integer Rial — no float(, no Decimal, no round(.

    Comments are stripped first so an explanatory comment cannot trip it.
    """
    import io
    import tokenize

    from app.modules.referrals.application import referral_service

    source = inspect.getsource(referral_service)
    tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    code = " ".join(
        tok.string for tok in tokens if tok.type not in (tokenize.COMMENT, tokenize.STRING)
    )
    assert "float(" not in code
    assert "Decimal" not in code
    assert "round(" not in code


def test_earner_eligibility_gate_checks_is_active():
    """A deactivated account must not earn new rewards."""
    from app.modules.referrals.application import referral_service

    src = inspect.getsource(referral_service.ReferralService._earner_is_eligible)
    assert "user.is_active" in src


def test_track_referral_refuses_reverse_edge_cycles():
    """A↔B cycles are refused at the door (red-team 2026-10-14).

    Not exploitable economically (each side earns only the other's L1 gift,
    and the buyer-as-L2 guard blocks self-commission), but a cycle pollutes
    every chain walk — cheap to refuse.
    """
    from app.modules.referrals.application import referral_service

    src = inspect.getsource(referral_service.ReferralService.track_referral)
    assert "Referral.referrer_id == referred_id" in src
    assert "Referral.referred_id == referrer_id" in src
    assert 'raise ValueError("This referral would create a cycle.")' in src


def test_anti_farming_gate_requires_invited_verified():
    """Anti-farming: the INVITED user must have a verified phone before ANY
    gift pays. Without this, the password path creates is_verified=False
    rows and an attacker farms gifts with fake numbers (the hole found in
    the 2026-10-14 red-team pass)."""
    from app.modules.referrals.application import referral_service

    # the helper checks the right column
    helper = inspect.getsource(referral_service.ReferralService._invited_is_verified)
    assert "user.is_verified" in helper
    # the payout path CALLS it before paying (wiring, not presence)
    payout = inspect.getsource(referral_service.ReferralService.pay_signup_gift_for_referral)
    assert "await ReferralService._invited_is_verified(db, referral.referred_id)" in payout
    # held rows stay PENDING (the sweep pays them once verified)
    assert "referral_gift_held_unverified" in payout


def test_otp_verify_releases_held_gift():
    """The other half: when the invited user verifies, the held gift pays.

    Anchors: the just_verified flag and the release call inside
    auth_service.verify_otp.
    """
    from app.modules.auth.application import auth_service

    src = inspect.getsource(auth_service.verify_otp)
    assert "just_verified = not user.is_verified" in src
    assert "await ReferralService.pay_signup_gift_for_referral(db, referral_row)" in src


def test_gift_card_redeem_locks_one_row_only():
    """DoS shield: the redeem must lock ONLY the requested card's row.

    The old version locked every active card and filtered in Python — any
    authenticated user could block ALL other redeems with two concurrent
    requests (found in the 2026-10-14 red-team pass). The single-row lookup
    is what makes the lock proportional.
    """
    from app.modules.gamification.application import gift_card_service

    src = inspect.getsource(gift_card_service.redeem_internal_gift_card)
    assert "InternalGiftCard.code == clean_code" in src
    assert ".with_for_update()" in src
    # the table-wide lock pattern must NOT come back
    assert "InternalGiftCard.is_active.is_(True)).with_for_update()" not in src
    assert "active_cards" not in src


def test_level2_earner_resolved_by_chain_walk_not_second_row():
    """Level 2 is derived (referrer's referrer), never a second referrals row.

    ``referrals.referred_id`` is UNIQUE — inserting a second row sharing it
    would violate the constraint at runtime.
    """
    from app.modules.referrals.application import referral_service

    src = inspect.getsource(referral_service.ReferralService._resolve_level2_earner)
    assert "Referral.referred_id == level1_referrer_id" in src


# ── Celery registration ───────────────────────────────────────────────────


def test_referral_sweep_task_registered_and_scheduled():
    """The sweep must be in TASK_MODULES and have a beat entry."""
    from app.worker import celery_app as celery_module

    assert "app.modules.referrals.application.tasks" in celery_module.TASK_MODULES
    beat = celery_module.celery_app.conf.beat_schedule
    assert "process-referral-rewards" in beat
    assert (
        beat["process-referral-rewards"]["task"]
        == "app.modules.referrals.application.tasks.process_referral_rewards"
    )


# ── Admin API guards ──────────────────────────────────────────────────────


def test_admin_referral_routes_require_permissions():
    """Every admin referral route must be guarded (exact dependency anchors)."""
    from app.modules.referrals.api import routes

    src = inspect.getsource(routes)
    assert 'RequirePermissions("referrals:read")' in src
    assert 'RequirePermissions("referrals:write")' in src
    # The write guard must appear on the mutating route (config PUT).
    assert src.count("dependencies=[_require_write]") == 1
    # The read guard covers config GET + history GET + history export.
    assert src.count("dependencies=[_require_read]") == 3


def test_every_referral_route_is_rate_limited_with_correct_order():
    """Security shield: EVERY referral route carries @limiter.limit, and the
    decorator sits closest to the function (listed after the route decorator).

    The inverted order silently never runs — the repo has a prior bug from
    exactly that. This AST check fails on a missing OR misordered limiter.
    """
    import ast
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2]
        / "modules"
        / "referrals"
        / "api"
        / "routes.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(src)

    routes_found = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        limiter_idx = route_idx = None
        for i, dec in enumerate(node.decorator_list):
            if isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                if dec.func.attr == "limit":
                    limiter_idx = i
                elif dec.func.attr in ("get", "post", "put", "patch", "delete"):
                    route_idx = i
        if route_idx is None:
            continue  # helper, not a route
        routes_found += 1
        assert limiter_idx is not None, f"{node.name} has NO @limiter.limit"
        assert limiter_idx > route_idx, (
            f"{node.name}: @limiter.limit is ABOVE the route decorator — "
            "slowapi never wraps it (the silent-never-runs trap)"
        )
    # 8 route handlers exist: 4 customer + 4 admin (config GET + config PUT
    # share one path but are two handlers).
    assert routes_found == 8, f"expected 8 referral routes, found {routes_found}"
    # The manual sweep endpoint is gone (owner: no log to check first made it
    # useless; rewards pay eagerly and the background task only retries).
    assert '"/sweep"' not in src
    assert "run_reward_sweep" not in src


def test_eager_payouts_wired_into_event_paths():
    """Rewards must pay at the event, not wait for the sweep.

    Signup gift at registration, commission at both order-completion paths —
    each call site is pinned by its exact expression.
    """
    from app.modules.auth.application import auth_service
    from app.modules.orders.application import order_service
    from app.modules.shipping.application import shipping_service

    assert "await ReferralService.pay_signup_gift_for_referral(db, referral)" in (
        inspect.getsource(auth_service)
    )
    assert "await ReferralService.settle_order_rewards(db, order.id)" in (
        inspect.getsource(order_service)
    )
    assert "await ReferralService.settle_order_rewards(db, order.id)" in (
        inspect.getsource(shipping_service)
    )


def test_history_reads_the_wallet_ledger_and_names_profiles():
    """The history audit view reads paid rows from the ledger, not PENDING intent.

    Anchors: the wallet table join and the UserProfile name source (User has
    no name columns — the display_name trap).
    """
    from app.modules.referrals.application import reward_history

    src = inspect.getsource(reward_history)
    assert "WalletTransaction.reference_type.in_(refs)" in src
    assert "UserProfile.user_id == User.id" in src
    assert "outerjoin(UserProfile" in src


def test_history_supports_search_and_date_range():
    """Owner: paging 25-at-a-time through 20k rows is not a search.

    The history query must accept a free-text filter (earner identity via
    User/UserProfile, order number via the commission join, invited user via
    the referral join) and an inclusive date range on created_at.
    """
    from app.modules.referrals.application import reward_history

    src = inspect.getsource(reward_history.fetch_reward_history)
    assert "WalletTransaction.created_at >= date_from" in src
    assert "timedelta(days=1)" in src  # inclusive end date
    assert "Order.order_number.ilike(like)" in src
    assert "UserProfile.display_name.ilike(like)" in src


def test_history_export_is_excel_safe_and_filter_sharing():
    """The CSV export reuses the reporting builder (BOM + injection-safe).

    Re-implementing CSV here would drift from the project's one convention;
    the anchor pins the import from the reporting module.
    """
    from app.modules.referrals.application import reward_history

    src = inspect.getsource(reward_history.build_reward_history_csv)
    assert "from app.modules.reporting.application.csv_builder import build_csv_bytes" in src
    assert "_EXPORT_MAX_ROWS" in inspect.getsource(reward_history)


def test_referral_permissions_in_catalog():
    """Guarded routes without catalog entries fail the RBAC completeness test."""
    from app.modules.rbac.application.permission_catalog import CATALOG_CODENAMES

    assert "referrals:read" in CATALOG_CODENAMES
    assert "referrals:write" in CATALOG_CODENAMES


# ── Registration hook (existing behaviour preserved) ─────────────────────


def test_registration_still_tracks_referrals():
    """The signup hook must keep calling track_referral (wiring, not presence)."""
    from app.modules.auth.application import auth_service

    src = inspect.getsource(auth_service)
    assert "await ReferralService.track_referral(" in src
