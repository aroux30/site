# حذف ماژول خبرنامه — ۲۰۲۶-۱۰-۰۶

دستور مالک: «هرچیزی مربوط به این ماژول هست میخوام پاک کنی کامل پاک کن از کد
هیچ اثری نمیخوام ازشون باشه برای سایت فروشگاهی کارایی ندارن!»

مایگریشن: `rmnews1` (down_revision=`rmtelegram1` — زنجیرهٔ خطی با موج‌های موازی همان روز).
آرشیو: `_archived/newsletter-removal-2026-10-06/`.

## چه چیزی حذف شد

### بک‌اند
- **کل ماژول `backend/app/modules/newsletter/`** — ۱۲ فایل:
  - `domain/models.py` — سه مدل: `NewsletterSubscriber`، `NewsletterCampaign`، `NewsletterCampaignRecipient` + سه enum
  - `api/routes.py` — ۱۷ روت (۳ عمومی: subscribe/confirm/unsubscribe + ۱۴ ادمین: مشترکان، CSV export، کمپین‌ها، پیش‌نمایش، ارسال، زمان‌بندی، تست، گیرنده‌ها)
  - `application/` — چهار سرویس: `newsletter_service.py` (عضویت دوعاملی + HMAC token)، `campaign_service.py` (چرخهٔ ارسال)، `admin_queries.py`، `tasks.py` (دو تسک Celery)
  - `schemas/newsletter.py` — ۱۴ اسکیمای Pydantic
- **`backend/app/main.py`** — رجیستری روتر (`app.modules.newsletter.api`).
- **`backend/app/worker/celery_app.py`** — سه جا: لیست include تسک‌ها، لیست autodiscover، و beat entry `dispatch-due-newsletter-campaigns` (کرون هر ۱ دقیقه).
- **`backend/app/modules/rbac/application/permission_catalog.py`** — دو پرمیشن `newsletter:read` / `newsletter:write`.
- **`backend/app/modules/content/domain/block_patterns.py`** — الگوی بلوک `newsletter-signup`.
- **`backend/app/shared/content/widgets.py`** — نوع ویجت `newsletter` + اسکیمای کانفیگش.
- **کامنت‌های اشاره‌کننده** در `email_service.py`، `default_options.py`، `site_options_service.py` به‌روز شدند.

### فرانت‌اند
- **صفحات**: `(store)/newsletter/confirm`، `(store)/newsletter/unsubscribe`، `admin/newsletter`
- **کامپوننت‌ها**: `admin/newsletter/campaigns-tab.tsx`، `shared/newsletter-token-action.tsx`، `NewsletterWidget` داخل `widget-area.tsx`
- **کلاینت‌های API**: `lib/api/newsletter.ts`، `lib/api/newsletter-campaigns.ts`
- **`admin/layout.tsx`** — آیتم منو «خبرنامه»
- **`lib/permalinks.ts` + `admin-bar.tsx`** — ریشهٔ رزرو `newsletter` (طبق کنوانسیون موج payship که ریشهٔ ماژول حذف‌شده از لیست می‌رود)

### دیتابیس (مایگریشن `rmnews1`)
- سه جدول: `newsletter_campaign_recipients` (۰ ردیف) → `newsletter_campaigns` (۰ ردیف) → `newsletter_subscribers` (۱ ردیف fixture پاریتی: `test-check@example.com`، PENDING، هرگز تأیید نشده)
- دو پرمیشن `newsletter:%` + دو گرنت `role_permissions` (هر دو به نقش سیستمی admin — با FK CASCADE رفتند)
- صفر `user_permission_overrides`، صفر ردیف audit/outbox مرتبط

## چرا حذف بی‌اتلاف بود (پروب زنده قبل از drop)

| جدول | ردیف | محتوا |
|---|---|---|
| `newsletter_subscribers` | ۱ | fixture تست `test-check@example.com`، PENDING (هرگز تأیید نشد) |
| `newsletter_campaigns` | ۰ | — |
| `newsletter_campaign_recipients` | ۰ | — |
| گرنت‌های پرمیشن | ۲ | فقط نقش admin سیستمی |
| `user_permission_overrides` | ۰ | — |

snapshot کامل (ستون‌ها، constraint ها، index ها، ردیف‌ها، id/timestamp دقیق پرمیشن‌ها) در
`_archived/newsletter-removal-2026-10-06/db_snapshot_before.json`.

## برگشت‌پذیری

`downgrade()` هر سه جدول را بایت‌به‌بایت بازسازی می‌کند — از جمله:
- enum ها با `native_enum=False` و ذخیرهٔ member NAME (قرارداد enum پروژه)
- server default های uppercase که `x5y6z7a8b9c0` ساخته بود (`'DRAFT'`، `'PENDING'`)
- default عجیب اما واقعی `'''footer'''::character varying` روی `source` (همان چیزی که مایگریشن سازنده تولید کرده بود)
- ردیف مشترک + دو پرمیشن + دو گرنت با id/timestamp دقیق از snapshot

تست انجام‌شده: `downgrade rmtelegram1` → راستی‌آزمایی (۳ جدول، ۱ ردیف، ۲ پرمیشن، ۲ گرنت، default ها) → `upgrade head` → جدول‌ها دوباره صفر. ✅

## راستی‌آزمایی نهایی (همه سبز)

- grep سراسری live code: صفر ارجاع newsletter (بک + فرانت + اسکریپت‌ها)
- openapi: ۵۶۲ مسیر، صفر newsletter
- DB: صفر جدول، صفر پرمیشن
- celery: صفر تسک، صفر beat entry
- pytest: ۲۰۸/۲۰۸
- گیت‌ها: ۲/۲ (ORM-schema sync شامل حذف جدول‌ها)
- tsc: صفر خطای سورس
- :3000/:3100/:3300 همه ۲۰۰ · `/newsletter/confirm` → ۴۰۴ · `/admin/newsletter` → ۳۰۷ (auth مثل هر مسیر ناموجود دیگر)
