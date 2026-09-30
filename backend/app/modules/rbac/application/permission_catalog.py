"""Catalog of every permission codename the API enforces.

Each entry's ``codename`` is the exact string passed to
``RequirePermissions(...)`` in route dependencies and stored as
``Permission.slug`` — the JWT ``permissions`` claim is matched against it
verbatim. ``resource``/``action`` are the two slug segments (codenames like
``inventory:counts`` or ``payments:manage`` keep their literal action).

The completeness of this catalog is enforced by a unit test that scans the
backend source for every ``RequirePermissions(...)`` call and asserts each
codename appears here — adding a guarded route without a catalog entry fails
CI.
"""

from __future__ import annotations

from typing import TypedDict


class PermissionCatalogEntry(TypedDict):
    codename: str
    name_fa: str
    name_en: str
    description: str


def _p(codename: str, name_fa: str, name_en: str, description: str) -> PermissionCatalogEntry:
    return {
        "codename": codename,
        "name_fa": name_fa,
        "name_en": name_en,
        "description": description,
    }


# Sorted by codename; keep in sync with every RequirePermissions(...) call.
PERMISSION_CATALOG: list[PermissionCatalogEntry] = [
    _p(
        "admin:access",
        "دسترسی به پنل مدیریت",
        "Admin panel access",
        "دسترسی کلی به بخش‌های مدیریتی سیستم",
    ),
    _p(
        "accounting:read",
        "مشاهده اسناد حسابداری",
        "Read accounting",
        "مشاهده کدینگ حساب‌ها، اسناد دفتر روزنامه، دوره‌های مالی و خروجی‌های حسابداری",
    ),
    _p(
        "accounting:write",
        "مدیریت اسناد حسابداری",
        "Manage accounting",
        "ایجاد و ویرایش حساب‌ها، ثبت و برگشت اسناد دستی، و بستن دوره مالی",
    ),
    _p(
        "analytics:read",
        "مشاهده تحلیل‌ها و آمار",
        "Read analytics",
        "مشاهده گزارش‌های تحلیلی و داشبوردهای آماری",
    ),
    _p(
        "approvals:review",
        "بررسی درخواست‌های تایید",
        "Review approvals",
        "بررسی و تایید/رد درخواست‌های در صف تایید",
    ),
    _p(
        "audit:read",
        "مشاهده رویدادهای حسابرسی",
        "Read audit logs",
        "مشاهده گزارش رویدادها و سوابق حسابرسی سیستم",
    ),
    _p(
        "audit:write",
        "مدیریت حسابرسی",
        "Manage audit",
        "اجرای عملیات مدیریتی روی ماژول حسابرسی (بازبینی پوشش داده و موارد مشابه)",
    ),
    _p(
        "automation:read",
        "مشاهده قوانین اتوماسیون",
        "Read automation rules",
        "مشاهده قوانین خودکارسازی و رویدادهای راه‌اندازی آن‌ها",
    ),
    _p(
        "automation:write",
        "مدیریت قوانین اتوماسیون",
        "Manage automation rules",
        "ایجاد، ویرایش و آزمایش قوانین خودکارسازی (تریگرها و اقدام‌ها)",
    ),
    _p(
        "blog:write",
        "مدیریت وبلاگ",
        "Manage blog",
        "ایجاد و ویرایش پیش‌نویس نوشته‌های وبلاگ. انتشار جداگانه و با کدنامهٔ "
        "blog:publish کنترل می‌شود، درست مثل edit_posts در برابر publish_posts در وردپرس",
    ),
    _p(
        "blog:publish",
        "انتشار نوشته",
        "Publish posts",
        "انتشار عمومی نوشته‌ها. همکار بدون این کدنامه فقط پیش‌نویس می‌نویسد "
        "و سردبیر آن را منتشر می‌کند (همان publish_posts در وردپرس)",
    ),
    _p(
        "blog:write_others",
        "ویرایش نوشته‌های دیگران",
        "Edit others' blog posts",
        "ویرایش و حذف نوشته‌های متعلق به دیگران (همان edit_others_posts در وردپرس)",
    ),
    _p(
        "calendar:read",
        "مشاهده تقویم عملیاتی",
        "Read calendar",
        "مشاهده نمای تقویمی رویدادهای زمان‌بندی‌شده (انتشار محتوا، تخفیف‌ها، اعلان‌ها، کمپین‌ها، اشتراک‌ها)",
    ),
    _p(
        "cashback:read",
        "مشاهده کش‌بک",
        "Read cashback",
        "مشاهده قوانین و تراکنش‌های کش‌بک",
    ),
    _p(
        "cashback:write",
        "مدیریت کش‌بک",
        "Manage cashback",
        "ایجاد و ویرایش قوانین کش‌بک و مدیریت تراکنش‌های آن",
    ),
    _p(
        "catalog:write",
        "مدیریت کاتالوگ",
        "Manage catalog",
        "ایجاد و ویرایش محصولات، دسته‌بندی‌ها، برندها و ویژگی‌های کاتالوگ",
    ),
    _p(
        "crm:read",
        "مشاهده قیف فروش عمده",
        "Read CRM",
        "مشاهده درخواست‌های عمده‌فروشی و مراحل قیف فروش",
    ),
    _p(
        "crm:write",
        "مدیریت قیف فروش عمده",
        "Manage CRM",
        "ثبت، پیگیری و تبدیل درخواست‌های عمده‌فروشی به همکار تجاری",
    ),
    _p(
        "dataexchange:read",
        "مشاهده تبادل داده",
        "Read data exchange",
        "مشاهده خروجی‌ها، فیدها و گزارش‌های تبادل داده",
    ),
    _p(
        "dataexchange:write",
        "مدیریت تبادل داده",
        "Manage data exchange",
        "ایجاد و اجرای ورودی/خروجی داده، فیدهای محصول و همگام‌سازی خارجی",
    ),
    _p(
        "discounts:read",
        "مشاهده تخفیف‌ها",
        "Read discounts",
        "مشاهده کدهای تخفیف، کوپن‌ها و کمپین‌های تخفیفی",
    ),
    _p(
        "discounts:write",
        "مدیریت تخفیف‌ها",
        "Manage discounts",
        "ایجاد، ویرایش و غیرفعال‌سازی کدهای تخفیف و کمپین‌ها",
    ),
    _p(
        "gamification:read",
        "مشاهده گیمیفیکیشن",
        "Read gamification",
        "مشاهده نشان‌ها، چالش‌ها و وضعیت گیمیفیکیشن کاربران",
    ),
    _p(
        "gamification:write",
        "مدیریت گیمیفیکیشن",
        "Manage gamification",
        "ایجاد و ویرایش نشان‌ها، چالش‌ها، جوایز و قرعه‌کشی‌ها",
    ),
    _p(
        "inventory:counts",
        "شمارش انبار",
        "Inventory counts",
        "انجام عملیات شمارش فیزیکی موجودی، ثبت شمارش و تطبیق اختلاف‌ها",
    ),
    _p(
        "inventory:read",
        "مشاهده موجودی انبار",
        "Read inventory",
        "مشاهده موجودی، انبارها، رزروها و گردش‌های انبار",
    ),
    _p(
        "inventory:write",
        "مدیریت موجودی انبار",
        "Manage inventory",
        "ایجاد و ویرایش انبارها، تنظیم موجودی، رزرو و عملیات فیزیکی انبار",
    ),
    _p(
        "invoicing:read",
        "مشاهده فاکتورها",
        "Read invoices",
        "مشاهده فاکتورهای فروش و رسمی و اسناد مالی مرتبط",
    ),
    _p(
        "invoicing:write",
        "مدیریت فاکتورها",
        "Manage invoices",
        "صدور، ویرایش و ابطال فاکتورها و اسناد مالی",
    ),
    _p(
        "loyalty:write",
        "مدیریت باشگاه مشتریان",
        "Manage loyalty",
        "مدیریت سطوح، امتیازها و قوانین باشگاه مشتریان",
    ),
    _p(
        "media:read",
        "مشاهده رسانه‌ها",
        "Read media",
        "مشاهده فایل‌ها و کتابخانه رسانه",
    ),
    _p(
        "media:write",
        "مدیریت رسانه‌ها",
        "Manage media",
        "بارگذاری، ویرایش و حذف فایل‌های رسانه‌ای",
    ),
    _p(
        "messaging:read",
        "مشاهده پیام‌ها",
        "Read messaging",
        "مشاهده قالب‌ها و پیام‌های ارسالی به کاربران",
    ),
    _p(
        "newsletter:read",
        "مشاهده خبرنامه",
        "Read newsletter",
        "مشاهده فهرست مشترکان خبرنامه و وضعیت عضویت آن‌ها",
    ),
    _p(
        "newsletter:write",
        "مدیریت خبرنامه",
        "Manage newsletter",
        "حذف مشترکان و مدیریت لیست خبرنامه",
    ),
    _p(
        "messaging:write",
        "مدیریت پیام‌ها",
        "Manage messaging",
        "ایجاد و ارسال پیام و مدیریت قالب‌های پیام‌رسانی",
    ),
    _p(
        "notifications:read",
        "مشاهده اعلان‌ها",
        "Read notifications",
        "مشاهده اعلان‌ها، قالب‌ها و سوابق ارسال",
    ),
    _p(
        "notifications:write",
        "مدیریت اعلان‌ها",
        "Manage notifications",
        "ایجاد و ارسال اعلان و مدیریت قالب‌ها و تنظیمات اعلان‌رسانی",
    ),
    _p(
        "orders:read",
        "مشاهده سفارش‌ها",
        "Read orders",
        "مشاهده سفارش‌ها، جزئیات و وضعیت آن‌ها",
    ),
    _p(
        "orders:write",
        "مدیریت سفارش‌ها",
        "Manage orders",
        "تغییر وضعیت، لغو و انجام عملیات مدیریتی روی سفارش‌ها",
    ),
    _p(
        "payments:manage",
        "مدیریت پرداخت‌ها",
        "Manage payments",
        "مدیریت درگاه‌ها، تسویه‌ها و عملیات مالی پرداخت",
    ),
    _p(
        "payments:refund",
        "بازگشت وجه",
        "Refund payments",
        "ثبت و پردازش درخواست‌های بازگشت وجه به مشتری",
    ),
    _p(
        "payments:write",
        "عملیات پرداخت",
        "Write payments",
        "ایجاد و ویرایش تراکنش‌ها و تنظیمات پرداخت",
    ),
    _p(
        "procurement:read",
        "مشاهده خرید و تامین",
        "Read procurement",
        "مشاهده تامین‌کننده‌ها و سفارش‌های خرید و درخواست‌های تدارکات",
    ),
    _p(
        "procurement:write",
        "مدیریت خرید و تامین",
        "Manage procurement",
        "ایجاد و ویرایش تامین‌کننده‌ها و سفارش‌های خرید، ارسال و دریافت اقلام",
    ),
    _p(
        "pricing:read",
        "مشاهده قیمت‌گذاری",
        "Read pricing",
        "مشاهده قوانین قیمت‌گذاری، لیست‌های قیمت و افزایش قیمت",
    ),
    _p(
        "pricing:write",
        "مدیریت قیمت‌گذاری",
        "Manage pricing",
        "ایجاد و ویرایش قوانین قیمت‌گذاری و لیست‌های قیمت",
    ),
    _p(
        "rbac:read",
        "مشاهده نقش‌ها و دسترسی‌ها",
        "Read RBAC",
        "مشاهده نقش‌ها، مجوزها و تخصیص‌های دسترسی",
    ),
    _p(
        "rbac:write",
        "مدیریت نقش‌ها و دسترسی‌ها",
        "Manage RBAC",
        "ایجاد و ویرایش نقش‌ها و مجوزها و تخصیص آن‌ها به کاربران",
    ),
    _p(
        "blog:moderate_comments",
        "تعدیل دیدگاه‌ها",
        "Moderate comments",
        "تأیید، اسپم و حذف دیدگاه‌ها — جدا از مجوز نوشتن، تا همکار بتواند بنویسد بدون اینکه بتواند گفتگوهای دیگران را حذف کند",
    ),
    _p(
        "rbac:escalate_own",
        "تغییر دسترسی‌های شخصی خود",
        "Escalate own privileges",
        "اعطای نقش یا مجوز به حساب کاربری خود — بدون این مجوز، هر مدیر دسترسی می‌تواند خودش را مدیر کل کند",
    ),
    _p(
        "reports:read",
        "مشاهده گزارش‌ها",
        "Read reports",
        "مشاهده و اجرای گزارش‌ها و گزارش‌های ذخیره‌شده",
    ),
    _p(
        "reports:write",
        "مدیریت گزارش‌ها",
        "Manage reports",
        "ایجاد، ویرایش و زمان‌بندی گزارش‌ها و خروجی‌های تحلیلی",
    ),
    _p(
        "reviews:moderate",
        "مدیریت نظرات",
        "Moderate reviews",
        "تایید، رد و پاسخ به نظرات و امتیازهای کاربران",
    ),
    _p(
        "search:reindex",
        "بازنمایه‌سازی جستجو",
        "Reindex search",
        "اجرای بازنمایه‌سازی ایندکس‌های جستجو",
    ),
    _p(
        "documents:read",
        "مشاهده اسناد و پیوست‌ها",
        "Read documents",
        "مشاهده پیوست‌های پرونده‌ها و جست‌وجو در بایگانی اسناد مالی",
    ),
    _p(
        "documents:write",
        "مدیریت اسناد و پیوست‌ها",
        "Manage documents",
        "افزودن و حذف پیوست روی رکوردهای کسب‌وکار",
    ),
    _p(
        "subscriptions:read",
        "مشاهده اشتراک‌ها",
        "Read subscriptions",
        "مشاهده فهرست و جزئیات اشتراک‌های کاربران و تاریخچه صورتحساب دوره‌ها",
    ),
    _p(
        "subscriptions:write",
        "مدیریت اشتراک‌ها",
        "Manage subscriptions",
        "اجرای دستی دوره صورتحساب و عملیات مدیریتی اشتراک‌ها",
    ),
    _p(
        "seo:write",
        "مدیریت سئو",
        "Manage SEO",
        "مدیریت متادیتا، ریدایرکت‌ها، نقشه سایت و تنظیمات سئو",
    ),
    _p(
        "settings:read",
        "مشاهده تنظیمات",
        "Read settings",
        "مشاهده تنظیمات سیستم و فروشگاه",
    ),
    _p(
        "settings:write",
        "مدیریت تنظیمات",
        "Manage settings",
        "ویرایش تنظیمات سیستم، فروشگاه و یکپارچه‌سازی‌ها",
    ),
    _p(
        "settings:write_others",
        "ویرایش صفحات دیگران",
        "Edit others' pages",
        "ویرایش و حذف صفحات متعلق به دیگران (همان edit_others_pages در وردپرس)",
    ),
    _p(
        "shipping:write",
        "مدیریت ارسال",
        "Manage shipping",
        "مدیریت روش‌های ارسال، مناطق و تعرفه‌های حمل‌ونقل",
    ),
    _p(
        "support:read",
        "مشاهده تیکت‌های پشتیبانی",
        "Read support",
        "مشاهده تیکت‌ها و درخواست‌های پشتیبانی مشتریان",
    ),
    _p(
        "support:write",
        "مدیریت تیکت‌های پشتیبانی",
        "Manage support",
        "پاسخ، ارجاع و بستن تیکت‌های پشتیبانی",
    ),
    _p(
        "tax:read",
        "مشاهده مالیات",
        "Read tax",
        "مشاهده قوانین مالیاتی، نرخ‌ها و گزارش‌های مالیات بر ارزش افزوده",
    ),
    _p(
        "tax:write",
        "مدیریت مالیات",
        "Manage tax",
        "ایجاد و ویرایش قوانین مالیاتی، نرخ‌ها و پروفایل‌های مالیاتی",
    ),
    _p(
        "users:delete",
        "حذف کاربران",
        "Delete users",
        "حذف یا غیرفعال‌سازی دائمی حساب‌های کاربری",
    ),
    _p(
        "users:read",
        "مشاهده کاربران",
        "Read users",
        "مشاهده فهرست و جزئیات حساب‌های کاربری",
    ),
    _p(
        "users:write",
        "مدیریت کاربران",
        "Manage users",
        "ایجاد و ویرایش حساب‌های کاربری و مدیریت وضعیت آن‌ها",
    ),
    _p(
        "vendors:read",
        "مشاهده فروشندگان",
        "Read vendors",
        "مشاهده فروشندگان، غرفه‌ها و وضعیت آن‌ها",
    ),
    _p(
        "vendors:write",
        "مدیریت فروشندگان",
        "Manage vendors",
        "ایجاد، تایید و مدیریت فروشندگان و غرفه‌های آن‌ها",
    ),
]

CATALOG_CODENAMES: frozenset[str] = frozenset(e["codename"] for e in PERMISSION_CATALOG)


def split_codename(codename: str) -> tuple[str, str]:
    """Split ``resource:action`` into its two segments.

    Single-segment codenames (none today) fall back to action ``access``.
    """
    resource, sep, action = codename.partition(":")
    return resource, action if sep else "access"
