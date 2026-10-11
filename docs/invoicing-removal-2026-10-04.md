# حذف ماژول اسناد مالی (invoicing) — ۲۰۲۶-۱۰-۰۴

> **وضعیت نهایی: ماژول حذف شد.** مالک پروژه پس از بررسی، تصمیم گرفت کل
> ماژول (کد، صفحات، جداول، permissionها) حذف شود — چون برای فروشگاه
> اینترنتی مصرفی کاربرد واقعی نداشت و هیچ جریان زنده‌ای از آن عبور
> نمی‌کرد. کد در `_archived/invoicing-module-2026-10-04/` آرشیو است؛
> حذف جداول با مایگریشن برگشت‌پذیر `rminvoice1` انجام شد (upgrade →
> downgrade → upgrade تست شد). این سند سابقهٔ تصمیم است.

## چرا حذف شد — شواهد (همه راستی‌آزمایی‌شده)

### ۱. جدول‌ها خالی بودند

خواندن مستقیم از دیتابیس زنده (پیش از حذف):

```
invoices: 0 rows
invoice_lines: 0 rows
invoice_sequences: 0 rows
```

سیستمی که کارش ثبت اسناد مالی است، صفر سند داشت.

### ۲. تنها مسیر خودکار، در پیش‌نویس می‌ماند

تنها تولیدکنندهٔ خودکار سند، listener برگشت وجه در
`automation/application/outbox_worker.py` بود (رویدادهای `ReturnRefunded`
و `RefundProcessed` → `handle_refund_event` → پیش‌نویس سند اعتباری).
مرحلهٔ «صدور» (`post_invoice`) فقط از مسیر ادمین و دستی قابل اجرا بود و
هیچ جریانی خودکار صدور نمی‌کرد. یعنی حتی آن پیش‌نویس‌ها هرگز سند رسمی
نمی‌شدند.

### ۳. مسیر ساخت سند از UI قابل دسترس نبود

- تسک backfill (`backfill_invoices_for_paid_orders` در
  `invoicing/application/tasks.py`) در `beat_schedule` نبود و صفر caller
  داشت (دو بار grep سراسری).
- endpoint ساخت پیش‌نویس (`POST /admin/invoices/orders/{id}/create-draft`)
  وجود داشت ولی هیچ دکمه‌ای در UI آن را صدا نمی‌زد؛ `createDraftForOrder`
  در کلاینت API صفر مصرف‌کننده داشت.
- نتیجه: صفحهٔ `/admin/invoices` فقط می‌توانست جدول خالی نشان دهد —
  همان «حس کنترل کاذب» که در حذف کارتابل (rmapprov1) هم دیدیم.

### ۴. برای فروشگاه، ابزار اشتباهی بود

فروشگاه کالای دیجیتال و اشتراک می‌فروشد (بازی، اشتراک سرویس). دفتر مالی
رسمی با شماره‌گذاری متوالی و هش زنجیره‌ای (الگوی Odoo) از روی چک‌لیست ERP
ساخته شده بود، نه از نیاز واقعی مشتری. فاکتور چاپی ماده ۱۶۹
(`orders/application/order_receipt_renderer.py`، مسیر `/orders/{id}/invoice`)
مسیر جداگانه و قدیمی‌تری است که **دست نخورد** — مشتری هر وقت فاکتور
بخواهد همان را می‌گیرد.

### ۵. سیستم موازی با حسابداری

ماژول حسابداری (journal با هش زنجیره‌ای، شماره‌گذاری JE، دوره‌های مالی)
رکورد پولی پلتفرم است و می‌ماند. همان رویدادهای برگشت وجه را می‌بیند و
هرگز از invoicing تغذیه نمی‌شد (تنها اشتراک فنی، تابع ۶ خطی
`fiscal_period_for` بود که به `accounting/application/numbering.py`
منتقل شد).

## چه چیزی حذف شد

| نقطه | جزئیات |
|---|---|
| ماژول بک‌اند | `backend/app/modules/invoicing/` (api، application، domain، schemas) |
| جداول | `invoices`، `invoice_lines`، `invoice_sequences` |
| Permissionها | `invoicing:read`، `invoicing:write` + grantهای نقش admin |
| روتر | mount در `main.py` (خط `app.modules.invoicing.api`) |
| اوت‌باکس | listener برگشت وجه (۲ نقطه) + هلپر `_invoice_attachment` (پیوست PDF در ایمیل تأیید) |
| Celery | دو ورودی در `celery_app.py` (TASK_MODULES و autodiscover) |
| Alembic | import مدل در `env.py` |
| RBAC | دو بلوک `_p(...)` در `permission_catalog.py` |
| Privacy | ثبت منبع `invoices` در `privacy_core_sources.py` + یادداشت نگهداری |
| صفحات ادمین | `/admin/invoices` و `/admin/invoices/[id]` + لینک منو |
| کلاینت API | `frontend/lib/api/invoicing.ts` |
| حساب مشتری | دکمهٔ «سند مالی رسمی» در داشبورد |
| تست‌ها | سه تست `_invoice_attachment` در `test_email_templates_and_attachments.py` |

## چه چیزی دست نخورد

- فاکتور چاپی/رسید (`/orders/{id}/invoice`، `order_receipt_renderer.py`).
- دفتر حسابداری و همهٔ رویدادهای مالی آن.
- ماژول DMS (بایگانی اسناد) — enumهای `invoice`/`credit_note` آن برای
  بایگانی دستی باقی می‌مانند؛ فقط تولیدکنندهٔ خودکارشان رفت.
- `direct_invoices` در fintech (فاکتور پرداخت مستقیم — فیچر جداگانه).
- قابلیت `attachments` در سرویس ایمیل (قابلیت عمومی؛ فعلاً مصرف‌کنندهٔ
  داخلی ندارد).

## بازگردانی

```bash
cd backend
alembic downgrade -1   # rminvoice1 → rmapprov1 : جداول + permissionها برمی‌گردند
```

سپس فایل‌های `_archived/invoicing-module-2026-10-04/` را به سر جای اصلی
برگردانید و ارجاع‌های لیست‌شده در جدول بالا را دستی برگردانید. مایگریشن
`downgrade()` هم permissionها را با id اصلی و grant ادمین بازمی‌سازد.
