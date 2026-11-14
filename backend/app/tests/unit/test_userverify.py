"""User-verification port: source pins and pure-logic tests.

Pins (exact expressions, not comments) so a regression — removing a hook,
changing a permission codename, dropping the reroute — fails loudly.
"""

from __future__ import annotations

import inspect
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3]


def _read(rel: str) -> str:
    return (BACKEND / rel).read_text(encoding="utf-8")


# ── Order status / state machine ──────────────────────────────────────────


def test_doing_verified_enum_value_exists():
    from app.modules.orders.domain.models import OrderStatus

    assert OrderStatus.DOING_VERIFIED.value == "doing_verified"


def test_doing_verified_transitions_match_pending_lane():
    """The badge lane is a working stage: forward to processing, or exit."""
    from app.modules.orders.application.order_service import _VALID_TRANSITIONS
    from app.modules.orders.domain.models import OrderStatus

    assert _VALID_TRANSITIONS[OrderStatus.DOING_VERIFIED] == frozenset(
        {OrderStatus.PROCESSING, OrderStatus.CANCELED, OrderStatus.REFUNDED}
    )
    # An operator can also move a PENDING order INTO the badge lane by hand.
    assert OrderStatus.DOING_VERIFIED in _VALID_TRANSITIONS[OrderStatus.PENDING]


# ── Payment reroute at both paid sites ────────────────────────────────────


def test_both_payment_sites_route_through_verification_service():
    src = _read("app/modules/payments/application/payment_service.py")
    # Gateway verify + admin card-to-card approval both ask for the entry lane.
    assert src.count("VerificationService.order_entry_status(") == 2, (
        "both paid-order sites (gateway verify, admin approval) must route "
        "through VerificationService.order_entry_status"
    )
    assert "OrderStatus.DOING_VERIFIED" in src, (
        "the payable-status set must accept DOING_VERIFIED (a late gateway "
        "callback on a verified order must not raise ORDER_NOT_PAYABLE)"
    )


def test_entry_status_is_pending_when_module_off_or_unverified():
    """Pure logic: the docstring contract pinned in source."""
    src = _read("app/modules/userverify/application/verification_service.py")
    assert 'if not config["enabled"]:' in src
    assert "return OrderStatus.PENDING" in src
    assert "if user is not None and user.is_verified:" in src
    assert "return OrderStatus.DOING_VERIFIED" in src


# ── Admin flip hook ───────────────────────────────────────────────────────


def test_update_user_fires_verification_hook():
    src = _read("app/modules/users/application/user_service.py")
    assert "VerificationService.notify_and_log(" in src
    assert "VerificationService.reroute_waiting_orders(db, user_id, admin_id=actor_id)" in src
    assert 'if "is_verified" in user_fields:' in src, (
        "the hook must fire only when the badge actually changes"
    )


def test_users_list_has_verified_filter():
    api = _read("app/modules/users/api/routes.py")
    svc = _read("app/modules/users/application/user_service.py")
    assert 'is_verified: bool | None = Query(' in api
    assert "User.is_verified == is_verified" in svc


# ── Telegram notify + log ─────────────────────────────────────────────────


def test_notify_and_log_writes_log_and_escapes_html():
    src = _read("app/modules/userverify/application/verification_service.py")
    assert "db.add(\n            UserVerificationLog(" in src
    # Telegram payloads carry user data — HTML escaping is mandatory.
    assert "def _esc(" in src and "parse_mode" not in src  # client owns parse_mode
    # Fallback to the chat bot when no dedicated credentials are set.
    assert "chat_config.get_config(db)" in src


def test_config_defaults_safe():
    from app.modules.userverify.application import verification_config

    merged = verification_config._merged(None)
    assert merged["enabled"] is True
    assert merged["telegram_notifications"] is True
    assert merged["telegram_bot_token"] == ""
    assert merged["telegram_chat_id"] == ""
    # Unknown keys never persist.
    merged2 = verification_config._merged({"bogus": 1, "enabled": False})
    assert "bogus" not in merged2 and merged2["enabled"] is False


def test_config_public_view_masks_token():
    from app.modules.userverify.application import verification_config

    view = verification_config.public_view(
        {"enabled": True, "telegram_notifications": True,
         "telegram_bot_token": "123:secret", "telegram_chat_id": "-100"}
    )
    assert view["telegram_bot_token"] == "********"
    assert view["telegram_chat_id"] == "-100"


# ── API surface: permissions + rate limits ────────────────────────────────


def test_admin_routes_guarded_and_rate_limited():
    import ast

    src = _read("app/modules/userverify/api/routes.py")
    assert 'RequirePermissions("userverify:read")' in src
    assert 'RequirePermissions("userverify:write")' in src
    tree = ast.parse(src)
    limited = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            names = [
                getattr(getattr(d, "func", d), "attr", None) or getattr(d, "id", "")
                for d in node.decorator_list
            ]
            if "limit" in names:
                limited += 1
    assert limited == 4, f"all 4 admin routes must be rate-limited, found {limited}"


def test_permissions_in_catalog():
    from app.modules.rbac.application.permission_catalog import PERMISSION_CATALOG

    codenames = {e["codename"] for e in PERMISSION_CATALOG}
    assert {"userverify:read", "userverify:write"} <= codenames


def test_router_mounted():
    src = _read("app/main.py")
    assert '("app.modules.userverify.api", "/userverify", ["userverify"])' in src


def test_model_registered_for_alembic():
    src = _read("alembic/env.py")
    assert "import app.modules.userverify.domain.models" in src


def test_log_model_shape():
    from app.modules.userverify.domain.models import UserVerificationLog

    assert UserVerificationLog.__tablename__ == "user_verification_logs"
    cols = set(UserVerificationLog.__table__.columns.keys())
    assert {"user_id", "admin_id", "status", "ip_address"} <= cols


def test_badge_move_is_admin_only():
    """The PENDING -> DOING_VERIFIED edge must never be exposed to customers.

    The only order-status write paths a customer can reach are the cancel
    routes; admin_update_status and the bulk variant are both behind
    RequirePermissions. Pinned so a future customer-facing endpoint cannot
    quietly mint the trust badge.
    """
    routes = _read("app/modules/orders/api/routes.py")
    for fn in ("admin_update_order_status", "admin_bulk_update_order_status"):
        idx = routes.index(f"def {fn}(")
        # The decorator block sits ABOVE the def; scan backwards for the guard.
        head = routes[:idx]
        last_perm = head.rindex("RequirePermissions(")
        assert "orders:" in head[last_perm : last_perm + 80], (
            f"{fn} must sit directly under an orders:* RequirePermissions guard"
        )


def test_customer_cancel_set_excludes_doing_verified():
    from app.modules.orders.application.order_service import _CUSTOMER_CANCELABLE
    from app.modules.orders.domain.models import OrderStatus

    assert OrderStatus.DOING_VERIFIED not in _CUSTOMER_CANCELABLE, (
        "the badge lane is a working stage (like PROCESSING is treated); "
        "if it becomes customer-cancelable that is an owner decision, "
        "not a silent side effect"
    )
