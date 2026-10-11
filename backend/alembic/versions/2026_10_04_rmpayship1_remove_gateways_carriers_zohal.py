"""Remove NowPayments/IDPay/simulation gateways, Zohal identity, and carrier adapters.

Owner order (2026-10-04, wave 6): «NowPayments (crypto) / zohal / In-house
delivery / Tipax courier / Iran Post (express) / Simulation gateway / IDPay —
هرچیزی مربوط به این ماژول‌ها هست میخوام پاک کنی کامل پاک کن ... برای سایت
فروشگاه اینترنتی کارایی ندارن». The code is archived under
``_archived/payship-zohal-2026-10-04/``.

Verified at removal time (live probe 2026-10-04, confirmed by owner as
test-only data):
- ``payments`` by provider: MOCK=670 (449 COMPLETED / 219 REFUNDED / 2
  PROCESSING, 2026-09-12..09-20 — the test window), CARD_TRANSFER=545,
  ZARINPAL=10. No IDPAY or CRYPTO rows ever existed.
- Child rows of MOCK payments: ``refunds``=219, ``payment_transactions``=1336,
  ``payment_webhook_events``=665 (+52 with NULL payment_id), all other FK
  tables 0. The owner explicitly confirmed the MOCK rows are test data and
  may be deleted.
- ``saved_payment_methods``: 4 rows, all provider='mock', inactive.
- ``installment_plans``, ``payment_allocations``: 0 rows.
- ``gateway_settings``: rows for 'idpay' and 'crypto' (zarinpal stays).
- ``user_trust_profiles``: 1 row (a test user); the ``shahkar_verified``
  column is dropped with the Zohal removal.

``downgrade()`` recreates the ``shahkar_verified`` column and the two
gateway_settings rows; deleted payment rows are data, not schema, and are
*not* restored (owner-approved).

Revision ID: rmpayship1
Revises: rmwhlog1
Create Date: 2026-10-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "rmpayship1"
down_revision = "rmwhlog1"
branch_labels = None
depends_on = None

_MOCK_PAYMENTS = "(SELECT id FROM payments WHERE provider = 'MOCK')"


def upgrade() -> None:
    # ── Payment data of the removed gateways (test-only, owner-approved) ──
    # Children first: every FK into payments must go before the parents.
    op.execute(f"DELETE FROM refunds WHERE payment_id IN {_MOCK_PAYMENTS}")
    op.execute(f"DELETE FROM payment_transactions WHERE payment_id IN {_MOCK_PAYMENTS}")
    op.execute(f"DELETE FROM payment_webhook_events WHERE payment_id IN {_MOCK_PAYMENTS}")
    # Webhook rows that never matched a payment (replay table) but came from
    # the mock provider's callback fan-out.
    op.execute("DELETE FROM payment_webhook_events WHERE provider = 'mock'")
    op.execute("DELETE FROM payments WHERE provider = 'MOCK'")
    op.execute("DELETE FROM saved_payment_methods WHERE provider = 'mock'")

    # ── Gateway runtime settings of the removed gateways ──
    op.execute("DELETE FROM gateway_settings WHERE provider_key IN ('idpay', 'crypto')")

    # ── Zohal identity: the Shahkar verification flag dies with its provider ──
    op.drop_column("user_trust_profiles", "shahkar_verified")


def downgrade() -> None:
    """Recreate the schema pieces; deleted rows are not restored (data loss is
    documented and owner-approved — the MOCK payments were test-only)."""
    op.add_column(
        "user_trust_profiles",
        sa.Column(
            "shahkar_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    # Restore the two gateway_settings rows exactly as the seed had them.
    op.execute(
        """
        INSERT INTO gateway_settings
            (id, provider_key, title_fa, is_active, is_default, priority,
             min_amount, max_amount, credentials, created_at, updated_at)
        VALUES
            (gen_random_uuid(), 'idpay', 'آیدی‌پی', true, false, 10,
             10000, 500000000, NULL, now(), now()),
            (gen_random_uuid(), 'crypto', 'ارز دیجیتال', true, false, 20,
             10000, 500000000, NULL, now(), now())
        """
    )
