"""Remove the free-shipping threshold and default-shipping-fee settings.

Owner order 2026-10-09 (screenshot of /admin/settings → مالی و پرداخت):
«این دو مورد اضافه هستن … میخوام پاک کنی کامل پاک کن از کد هیچ اثری
نمیخوام ازشون باشه برای سایت فروشگاه اینترنتی کارایی ندارن!» — the two
fields were «حداقل سفارش برای ارسال رایگان (ریال)» and «هزینه پیشفرض
ارسال عادی (ریال)» in the ``store.shipping_tax`` settings group.

Both were dead: no backend code ever read either key. The storefront's
«ارسال رایگان بالای ۵۰۰٬۰۰۰ تومان» promises were hard-coded client-side
and the checkout never honoured them (real prices come from
``shipping_rates``). The rate-level ``shipping_rates.min_order_amount``
column was the same feature's implementation on the rate table — no writer,
no reader, no admin UI; verified live 2026-10-09: 0 of 3 rows had a value.

This migration removes the data half and the dead column:

- drops the two keys from the ``store.shipping_tax`` JSONB document
  (``tax_rate_percent`` stays — the admin form still edits it);
- drops ``shipping_rates.min_order_amount`` (all NULL at removal time).

The code half (admin fields, cart/drawer/checkout free-shipping surfaces,
quote ``is_free``/``order_amount``) is archived under
``_archived/free-shipping-removal-2026-10-09/``.

``downgrade()`` restores the two keys with the exact captured values
(strings, as stored) and recreates the nullable column. Column values were
all NULL, so nothing is lost by the drop.

Revision ID: rmfreeship1
Revises: seord1
Create Date: 2026-10-09
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "rmfreeship1"
down_revision = "seord1"
branch_labels = None
depends_on = None

#: The two keys as they existed at removal (captured live 2026-10-09 from
#: site_settings key='store.shipping_tax'; values are stored as strings).
_CAPTURED_VALUE_JSON = '{"free_shipping_threshold_rials": "25000000", "default_shipping_fee_rials": "500000"}'


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE site_settings "
            "SET value = value - 'free_shipping_threshold_rials' "
            "- 'default_shipping_fee_rials' "
            "WHERE key = 'store.shipping_tax'"
        )
    )
    op.drop_column("shipping_rates", "min_order_amount")


def downgrade() -> None:
    op.add_column(
        "shipping_rates",
        sa.Column("min_order_amount", sa.BigInteger(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE site_settings "
            f"SET value = value || '{_CAPTURED_VALUE_JSON}'::jsonb "
            "WHERE key = 'store.shipping_tax'"
        )
    )
