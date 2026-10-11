# حذف ماژول اسناد و پیوست‌ها (DMS) — ۲۰۲۶-۱۰-۰۶

دستور مالک (۲۰۲۶-۱۰-۰۶، اسکرین‌شات `/admin/documents` و پیام): «هرچیزی مربوط
به این ماژول ها هست میخوام پاک کنی کامل پاک کن از کد هیچ اثری نمیخوام ازشون
باشه برای سایت فروشگاه اینترنتی کارایی ندارن». دهمین موج حذف پروژه (پس از
approvals، invoicing، inbound/journal/periods، pickup-scan، RMA/webhooks/
dead-letters، plugins/hooks، logistics، pay/ship/Zohal، accounting، i18n ×۲،
privacy/scheduled، ops-center، newsletter).

## ماژول چه بود

**`backend/app/modules/dms/`** — سیستم مدیریت اسناد (فیچر #۲۵ بنچمارک ERP، P2).
دو جدول، هفت اندپوینت ادمین:

- **`attachments`** — اسناد کاری چندریختی روی هر رکورد کسب‌وکار با
  `(entity_type, entity_id)`. اندپوینت‌ها: ایجاد، فهرست، شمارش per-kind، حذف،
  به‌علاوه رجیستری attachable-types.
- **`archived_documents`** — ایندکس بایگانی مالی تغییرناپذیر (اسنپ‌شات HTML
  فاکتور منجمدشده و مانند آن)، طبق طراحی فقط-خواندنی (بدون روت حذف).
  اندپوینت‌ها: جست‌وجو، خلاصه، دریافت یکی.

**فرانت‌اند:** `frontend/app/admin/documents/page.tsx` (۴۳۸ خط)،
`frontend/lib/api/dms.ts` (۱۱۸ خط)، یک ورودی سایدبار با `FolderOpen`.

## چرا حذف شد — شواهد

**نیمه‌ی نویسنده از قبل مرده بود.** بایگانی مالی را ماژول invoicing
می‌نوشت — که در ۲۰۲۶-۱۰-۰۴ (موج ۲) حذف شد. `ArchivedDocument` از آن زمان
**صفر نویسنده در کل کدبیس** داشته؛ گرپ `archived_document` / `ArchivedDocument`
بیرون ماژول چیزی برنمی‌گرداند. تب «بایگانی اسناد مالی» طبق ساختار خالی بود:
هیچ ماژولی دیگر سند رندرشده را منجمد نمی‌کند.

**نیمه‌ی پیوست هم مصرف‌کننده نداشت.** `create_attachment` / `list_attachments` /
`delete_attachment` فقط توسط روت‌های خود ماژول صدا زده می‌شدند؛ هیچ صفحه‌ی
سفارش/محصول/فروشنده‌ای هرگز UI «پیوست فایل» نداشت. `ATTACHABLE_ENTITY_TYPES`
شامل order/return/purchase_order/... بود — سفارش‌های خرید در حذف لجستیک مردند،
مرجوعی‌ها در حذف RMA، فاکتورها در حذف invoicing.

**هر دو جدول در لحظه‌ی حذف خالی بودند** (پروب زنده ۲۰۲۶-۱۰-۰۶):
`attachments` = ۰ ردیف، `archived_documents` = ۰ ردیف. حذفشان چیزی از دست نمی‌دهد.

## چه حذف شد

**بک‌اند** (آرشیو verbatim در `backend/modules/dms/`):
- کل پکیج `app/modules/dms/` — `api/routes.py` (۸ روت)،
  `application/document_service.py` (۳۷۲ خط)، `domain/models.py`
  (`Attachment`، `ArchivedDocument`، هر دو enum، `ATTACHABLE_ENTITY_TYPES`)،
  پکیج خالی `schemas/`
- `app/main.py`: اسپک روتر `("app.modules.dms.api", "/documents", ["documents"])`
- `alembic/env.py`: `import app.modules.dms.domain.models`
- `app/modules/rbac/application/permission_catalog.py`: دو ورودی `_p(...)`
  برای `documents:read` / `documents:write`
- `app/modules/media/application/usage_service.py`: پروب ستون
  `("attachments", "file_url")` و `"attachments"` از tuple در `_bucket_for`.
  خود bucket `documents` **می‌ماند** — `ticket_attachments` و
  `card_transfer_receipts` هنوز از آن استفاده می‌کنند.

**فرانت‌اند:**
- `app/admin/documents/page.tsx` (کل پوشه)
- `lib/api/dms.ts`
- `app/admin/layout.tsx`: ورودی سایدبار + ایمپورت بی‌استفاده‌ی `FolderOpen`

**دیتابیس** (مایگریشن `rmdms1`، زنجیره بعد از `rmnews1` سشن ۳ طبق ترتیب
ناظر): drop جدول `archived_documents` (۳ ایندکس + جدول) و `attachments`
(۳ ایندکس + جدول)، حذف دو ردیف مجوز `documents:*` (گرانت‌های `role_permissions`
کاسکید می‌شوند). `downgrade()` هر دو جدول را **دقیقاً مطابق تعریف
`b3d5f7a9c1e4_dms_v1`** بازمی‌سازد — همان ستون‌ها، تایپ‌ها، طول‌ها،
check constraintها، unique constraint، FK، ایندکس‌ها — و دو ردیف مجوز را با
UUIDهای مشاهده‌شده دوباره درج می‌کند (`_capture_dms_perms.json` در آرشیو)
به‌همراه گرانت‌های نقش admin.

## شواهد در لحظه‌ی حذف

- پروب DB زنده (۲۰۲۶-۱۰-۰۶): `attachments` = ۰، `archived_documents` = ۰،
  مجوزهای `documents:read` (id `91902960-...203ca4`) و `documents:write`
  (id `f9628304-...f7a365`)، ۲ گرانت، هر دو روی نقش `admin`
  (`51ab099d-...263f50`).
- اسکیمای جدول قبل از drop از `information_schema` ثبت شد؛ downgrade
  ستون‌به‌ستون آن را بازتولید می‌کند.
- روت‌ها قبل: ۷۸۵ کل، ۸ زیر `/documents`. بعد: ۷۴۹ کل، ۰ زیر `/documents`.

## راستی‌آزمایی

- زنجیره‌ی کامل روی DB اسکرچ از صفر: `upgrade head` تا `rmdms1` سبز.
- چرخه‌ی برگشت: `downgrade rmnews1` → هر دو جدول + ۲ مجوز با UUID دقیق
  برگشتند؛ با نقش admin موجود، ۲ گرانت هم برگشتند؛ سپس re-upgrade سبز.
- پروب زنده با احراز هویت: `/api/v1/documents/admin/attachable-types` → 404؛
  `/api/v1/media` → 200؛ `/healthz` → 200.
- سایدبار ادمین (HTML سرور-رندرشده با لاگین): «اسناد و پیوست‌ها» غایب،
  ورودی‌های اصلی (اشتراک‌های دوره‌ای، انبارها) حاضر.
- `check_model_schema_sync` PASS (۱۵۳ جدول)؛ `run_gates.py` سبز؛
  `verify_media_usage` و `verify_media_delete_guard` سبز؛ pytest ۲۰۸؛
  vitest ۱۲؛ tsc تمیز؛ `next build` سبز.
- پیت‌فال (تکرارشونده): بعد از حذف صفحه، `tsc` روی types قدیمی
  `.next/types` و `.next-prod/types` می‌شکند — فقط زیرشاخه‌ی `types` پاک شد
  (نه کل `.next` که سرور dev روی :3000 از آن استفاده می‌کند).

## هماهنگی

- ناظر (سشن «1.1») زنجیره را تعیین کرد:
  `rmprivacy1 → rmtelegram1 (سشن ۲) → rmnews1 (سشن ۳) → rmdms1 (این موج)`.
  فایل مایگریشن عمداً تا رسیدن `rmnews1` روی دیسک ننشست تا زنجیره dangle نشود.
- `main.py` و `frontend/app/admin/layout.tsx` با موج‌های موازی هم‌زمان
  ویرایش شدند (تلگرام/وب‌پوش سشن ۲، خبرنامه سشن ۳) — فقط با Edit خط‌محور،
  هرگز با بازنویسی کل فایل، تا ویرایش‌های موازی سالم merge شوند.
- آرشیو: `_archived/dms-documents-2026-10-06/` با README کامل.
