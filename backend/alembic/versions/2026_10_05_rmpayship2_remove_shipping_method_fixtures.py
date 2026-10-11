"""Remove the shipping-method test fixtures exposed in checkout.

Follow-up to ``rmpayship1`` (wave 7 review, 2026-10-05). Two fixture classes
were found live-visible in the storefront:

1. 1,057 methods with slug ``post-j-<hash>`` (provider NULL, name
   «پست پیشتاز <hash>», flat 50,000-Rial rate, province=تهران). These are
   e2e-test artifacts from the 2026-09-14..20 test window; they made the
   Tehran checkout quote return 1,060 options instead of 3.
2. 173 methods with slug ``post-express-<hash>`` (provider 'irpost') carrying
   173 shipments — all fixtures: a single tracking code
   (``TRK-9876543210``), orders with zero payments behind them, hex-phone
   fixture users, same test window.

Both classes are traces of the removed Iran Post integration and are deleted
here (owner's standing order for the removed modules: «هیچ اثری نمیخواهم»;
the MOCK-payment deletion set the precedent that owner-confirmed fixture
data goes with the module).

Kept deliberately: the three real storefront methods ``pishtaz``
(پست پیشتاز, 350k), ``tipax`` (تیپاکس اکسپرس, 550k) and ``express_courier``
(پیک موتوری, 650k) plus their three rates — these are the store's shipping
configuration; rates are served from ``shipping_rates`` and never depended
on the removed carrier adapters (which only fabricated tracking codes).
Deleting them would leave checkout with no usable shipping option.

``downgrade()`` restores nothing: this migration deletes data, not schema
(rows are test fixtures; same policy as ``rmrmawh1``).

Revision ID: rmpayship2
Revises: rmpayship1
Create Date: 2026-10-05
"""

from __future__ import annotations

from alembic import op

revision = "rmpayship2"
down_revision = "rmpayship1"
branch_labels = None
depends_on = None

_FIXTURE_METHODS = (
    "(SELECT id FROM shipping_methods "
    "WHERE slug LIKE 'post-j-%' OR slug LIKE 'post-express-%' "
    "OR provider = 'irpost')"
)


def upgrade() -> None:
    # Shipments first (FK RESTRICT into shipping_methods). All 173 rows sit
    # on post-express-* fixture methods; none has items or tracking events.
    op.execute(f"DELETE FROM shipments WHERE method_id IN {_FIXTURE_METHODS}")
    # Rates have ON DELETE CASCADE, but delete explicitly so the intent is
    # visible in the migration log.
    op.execute(f"DELETE FROM shipping_rates WHERE method_id IN {_FIXTURE_METHODS}")
    op.execute(
        "DELETE FROM shipping_methods "
        "WHERE slug LIKE 'post-j-%' OR slug LIKE 'post-express-%' "
        "OR provider = 'irpost'"
    )


def downgrade() -> None:
    """Data-only migration: fixture rows are not restored (see docstring)."""
    pass
