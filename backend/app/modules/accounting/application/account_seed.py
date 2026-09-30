"""Idempotent chart-of-accounts seeding (Iranian standard skeleton).

Mirrors ``rbac/application/permission_seed.py``: upserts every account from
:data:`ACCOUNT_SKELETON` by its stable ``code`` and never mutates an existing
row, so running it on every boot (and from the admin API) is a no-op after the
first run.

The codes are **load-bearing**: the automatic posting rules
(``application/posting_rules.py``) resolve accounts by these constants, so a
renamed ``name_fa`` is safe but a changed ``code`` would orphan the feed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog
from sqlalchemy import select

from app.modules.accounting.domain.models import Account, AccountType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# ── Stable account codes used by the posting rules ────────────────────────────

CASH = "1001"  # صندوق
BANK = "1002"  # بانک
RECEIVABLE = "1003"  # حسابهای دریافتنی تجاری
INVENTORY = "1004"  # موجودی کالا
PSP_CLEARING = "1005"  # حساب واسط درگاه پرداخت
PAYABLE = "2001"  # حسابهای پرداختنی تجاری
VAT_PAYABLE = "2002"  # مالیات بر ارزش افزوده پرداختنی
WALLET_LIABILITY = "2003"  # کیف پول کاربران
VENDOR_PAYABLE = "2004"  # بدهی به فروشندگان
EQUITY_CAPITAL = "3001"  # سرمایه
SALES_REVENUE = "4001"  # فروش کالا
SALES_RETURNS = "4002"  # برگشت فروش
SALES_DISCOUNT = "4003"  # تخفیف فروش
SHIPPING_REVENUE = "4004"  # درآمد حمل
SHIPPING_EXPENSE = "5001"  # هزینه حمل
GATEWAY_FEE_EXPENSE = "5002"  # کارمزد درگاه پرداخت
BANK_FEE_EXPENSE = "5003"  # کارمزد بانکی
# Customer-credit schemes. These are contra-revenue: the platform gives money
# back to the customer, so the expense sits against sales rather than being
# netted silently into the revenue line. Splitting them by scheme matters
# because each is budgeted and measured separately.
CASHBACK_EXPENSE = "5004"  # هزینه کش‌بک
LOYALTY_EXPENSE = "5005"  # هزینه باشگاه مشتریان (امتیاز)
REFERRAL_EXPENSE = "5006"  # هزینه معرفی دوستان


@dataclass(frozen=True)
class AccountSpec:
    code: str
    name_fa: str
    type: AccountType
    parent_code: str | None = None
    description: str | None = None


# Minimal Iranian-standard skeleton: five groups + the leaf accounts the
# posting rules need. Group rows (is_group=True by code shape) exist so the
# admin tree view has structure; only leaves receive journal lines.
ACCOUNT_SKELETON: tuple[AccountSpec, ...] = (
    # گروه داراییها
    AccountSpec("1", "داراییهای جاری", AccountType.ASSET, None, "گروه حسابهای دارایی"),
    AccountSpec(CASH, "صندوق", AccountType.ASSET, "1", "موجودی نقد صندوق"),
    AccountSpec(BANK, "بانک", AccountType.ASSET, "1", "موجودی حسابهای بانکی"),
    AccountSpec(
        RECEIVABLE,
        "حسابهای دریافتنی تجاری",
        AccountType.ASSET,
        "1",
        "مطالبات از مشتریان بابت فروش",
    ),
    AccountSpec(INVENTORY, "موجودی کالا", AccountType.ASSET, "1", "موجودی انبار به بهای تمامشده"),
    AccountSpec(
        PSP_CLEARING,
        "حساب واسط درگاه پرداخت",
        AccountType.ASSET,
        "1",
        "مبالغ در جریان وصول از درگاه پرداخت",
    ),
    # گروه بدهیها
    AccountSpec("2", "بدهیهای جاری", AccountType.LIABILITY, None, "گروه حسابهای بدهی"),
    AccountSpec(
        PAYABLE,
        "حسابهای پرداختنی تجاری",
        AccountType.LIABILITY,
        "2",
        "بدهی به تامینکنندگان بابت خرید",
    ),
    AccountSpec(
        VAT_PAYABLE,
        "مالیات بر ارزش افزوده پرداختنی",
        AccountType.LIABILITY,
        "2",
        "مالیات ارزش افزوده فروش قابل پرداخت به سازمان امور مالیاتی",
    ),
    AccountSpec(
        WALLET_LIABILITY,
        "کیف پول کاربران",
        AccountType.LIABILITY,
        "2",
        "مانده کیف پول کاربران (بدهی به کاربران)",
    ),
    AccountSpec(
        VENDOR_PAYABLE,
        "بدهی به فروشندگان",
        AccountType.LIABILITY,
        "2",
        "مبالغ قابل پرداخت به فروشندگان پس از کسر کارمزد",
    ),
    # گروه حقوق صاحبان سهام
    AccountSpec("3", "حقوق صاحبان سهام", AccountType.EQUITY, None, "گروه حسابهای سرمایه"),
    AccountSpec(EQUITY_CAPITAL, "سرمایه", AccountType.EQUITY, "3", "سرمایه اولیه و افزایش سرمایه"),
    # گروه درآمدها
    AccountSpec("4", "درآمدها", AccountType.REVENUE, None, "گروه حسابهای درآمد"),
    AccountSpec(SALES_REVENUE, "فروش کالا", AccountType.REVENUE, "4", "درآمد فروش کالا و خدمات"),
    AccountSpec(
        SALES_RETURNS,
        "برگشت فروش",
        AccountType.REVENUE,
        "4",
        "برگشت از فروش (حساب کاهنده درآمد)",
    ),
    AccountSpec(
        SALES_DISCOUNT,
        "تخفیف فروش",
        AccountType.REVENUE,
        "4",
        "تخفیفهای اعطایی به مشتریان (حساب کاهنده درآمد)",
    ),
    AccountSpec(SHIPPING_REVENUE, "درآمد حمل", AccountType.REVENUE, "4", "هزینه حمل دریافتشده از مشتری"),
    # گروه هزینهها
    AccountSpec("5", "هزینهها", AccountType.EXPENSE, None, "گروه حسابهای هزینه"),
    AccountSpec(SHIPPING_EXPENSE, "هزینه حمل", AccountType.EXPENSE, "5", "هزینه حمل پرداختشده به پیک"),
    AccountSpec(
        GATEWAY_FEE_EXPENSE,
        "کارمزد درگاه پرداخت",
        AccountType.EXPENSE,
        "5",
        "کارمزد دریافتی شرکتهای PSP",
    ),
    AccountSpec(BANK_FEE_EXPENSE, "کارمزد بانکی", AccountType.EXPENSE, "5", "کارمزد خدمات بانکی"),
    AccountSpec(
        CASHBACK_EXPENSE,
        "هزینه کش‌بک",
        AccountType.EXPENSE,
        "5",
        "مبالغ کش‌بک واریزشده به کیف پول مشتریان",
    ),
    AccountSpec(
        LOYALTY_EXPENSE,
        "هزینه باشگاه مشتریان",
        AccountType.EXPENSE,
        "5",
        "ارزش امتیازهای باشگاه مشتریان که به کیف پول واریز شده",
    ),
    AccountSpec(
        REFERRAL_EXPENSE,
        "هزینه معرفی دوستان",
        AccountType.EXPENSE,
        "5",
        "کمیسیون معرفی پرداخت‌شده به کیف پول معرف",
    ),
)

# Codes referenced by the posting rules — asserted at import time so a typo in
# the skeleton fails loudly instead of silently orphaning the feed.
REQUIRED_CODES: frozenset[str] = frozenset(
    {
        BANK,
        RECEIVABLE,
        PSP_CLEARING,
        PAYABLE,
        VAT_PAYABLE,
        WALLET_LIABILITY,
        SALES_REVENUE,
        SALES_RETURNS,
        GATEWAY_FEE_EXPENSE,
        CASHBACK_EXPENSE,
        LOYALTY_EXPENSE,
        REFERRAL_EXPENSE,
    }
)


@dataclass
class SeedStats:
    created: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    total: int = 0


async def seed_accounts(db: "AsyncSession") -> SeedStats:
    """Upsert the chart-of-accounts skeleton by code.

    Caller owns the transaction boundary: flushes but never commits, so it
    composes with both the startup lifespan and the admin API.
    """
    existing = list((await db.execute(select(Account))).scalars().all())
    by_code = {acc.code: acc for acc in existing}

    created: list[str] = []
    skipped: list[str] = []

    for spec in ACCOUNT_SKELETON:
        if spec.code in by_code:
            skipped.append(spec.code)
            continue
        account = Account(
            code=spec.code,
            name_fa=spec.name_fa,
            type=spec.type,
            is_active=True,
            description=spec.description,
        )
        db.add(account)
        by_code[spec.code] = account
        created.append(spec.code)

    await db.flush()  # assign PKs

    # Second pass: wire parent_id now that every row has its id.
    for spec in ACCOUNT_SKELETON:
        if spec.parent_code is None:
            continue
        child = by_code[spec.code]
        parent = by_code.get(spec.parent_code)
        if parent is not None and child.parent_id is None:
            child.parent_id = parent.id

    await db.flush()

    await logger.ainfo(
        "account_seed_completed",
        accounts_created=len(created),
        accounts_skipped=len(skipped),
        total_skeleton=len(ACCOUNT_SKELETON),
    )
    return SeedStats(created=created, skipped=skipped, total=len(ACCOUNT_SKELETON))
