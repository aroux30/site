# حذف ماژول «مرکز عملیات و حسابرسی» — ۲۰۲۶-۱۰-۰۵

> **وضعیت نهایی: ماژول حذف شد.** مالک (۲۰۲۶-۱۰-۰۵، اسکرین‌شات صفحهٔ `/admin/exceptions` + پیام)
> دستور داد: «هرچیزی مربوط به این ماژول‌ها هست می‌خوام پاک کنی کامل پاک کن از کد هیچ اثری
> نمی‌خوام ازشون باشه برای سایت فروشگاه اینترنتی کارایی ندارن!». کد در
> `_archived/ops-center-2026-10-05/` آرشیو است؛ جدول با مایگریشن برگشت‌پذیر `rmopscenter1`
> حذف شد.

## چرا حذف شد — شواهد (راستی‌آزمایی‌شده ۲۰۲۶-۱۰-۰۵)

### ۱. نیمهٔ «Exception Center» مرده بود (کد بدون مصرف‌کننده)
- `record_exception()` — تنها نویسندهٔ رجیستری — **صفر فراخوان در کل پروژه** (grep سراسری backend).
- رجیستری **in-memory** بود (`self._registry = {}`) — با هر ری‌استارت پاک می‌شد و جدول DB نداشت.
- نتیجه: زبانهٔ «خطاهای عملیاتی» **همیشه خالی** بود؛ سه endpoint نوشتنش (assign/resolve/dismiss)
  روی رکوردهایی کار می‌کردند که هرگز وجود نداشتند. همان الگوی «زیرسیستم کامل بدون producer»
  (مثل plugins/hooks).

### ۲. نیمهٔ «اسکنر reconciliation» واقعی بود ولی غیرضروری
- اسکنر فقط-خواندنی هر ۳۰ دقیقه اجرا می‌شد و ۵۴ یافتهٔ derived تولید کرده بود.
- تصمیم مالک: فروشگاه به سطح reconciliation خودکار نیاز ندارد؛ حقیقت پرداخت/سفارش در جداول
  orders/payments و runbook دستی `docs/runbooks/payment-reconciliation.md` می‌ماند.

## چه چیزی حذف شد

### بک‌اند (در `backend/app/modules/audit/` — آرشیو verbatim)
| مورد | جزئیات |
|---|---|
| `application/exception_center_service.py` | رجیستری in-memory، صفر نویسنده |
| `application/reconciliation_service.py` | اسکنر پرداخت/refund/webhook |
| `application/lifecycle_auditor.py` | بازرس چرخهٔ سفارش |
| `application/tasks.py` | فقط دو تسک reconcile_payments و audit_order_lifecycle |
| `domain/operational_exceptions.py`، `domain/reconciliation.py`، `schemas/reconciliation.py` | مدل‌ها و schemaها |
| `api/routes.py` | ۹ endpoint: `GET /admin/exceptions`، سه PATCH استثناها، `GET /admin/reconciliation/findings\|summary`، `POST /admin/reconciliation/run\|audit-lifecycle`، دو PATCH یافته‌ها |
| `schemas/audit.py` | `OperationalExceptionResponse`، `ExceptionAssignRequest`، `ExceptionResolveRequest` (+ import بی‌استفادهٔ Field) |
| `worker/celery_app.py` | TASK_MODULES entry + دو Beat entry (`reconcile-payments` هر ۳۰ دقیقه، `audit-order-lifecycle` هر ۲ ساعت) |
| `alembic/env.py` | import مدل `domain.reconciliation` |

### فرانت‌اند (آرشیو verbatim)
- `app/admin/exceptions/page.tsx` (صفحهٔ دو زبانه)
- `components/admin/reconciliation-findings.tsx`، `finding-action-dialog.tsx`، `service-health-banner.tsx`
- `lib/ops-exceptions.ts`، `lib/api/reconciliation.ts`
- `lib/api/audit.ts`: نوع `OperationalException` + `normalizeException` + چهار متد `auditApi`
- `app/admin/layout.tsx`: ورودی سایدبار «مرکز عملیات و حسابرسی»

### دیتابیس
- `reconciliation_findings` (۵۴ ردیف derived در لحظهٔ حذف) — drop شد.

## چه چیزی عمداً حفظ شد

- **گزارش رویدادها** (audit log): جدول `audit_logs`، `GET /admin/audit-logs`، صفحهٔ `/admin/audit`.
- **change log سطح فیلد**: جدول `entity_change_log`، چهار endpoint `/admin/audit/...`.
- permissionهای `audit:read`/`audit:write` — همچنان نگهبان audit-log و change-log هستند.
- `components/admin/async-state.tsx` — ۸+ مصرف‌کنندهٔ دیگر دارد.
- مایگریشن‌های `b7d3e5f9a1c4`/`c8e1f4a7b2d6` (تاریخ) و runbook دستی `payment-reconciliation.md`.
- تسک شبانهٔ `reconcile-wallet-balances` (متفاوت از اسکنر؛ سالم و ثبت‌شده در celery_app.py:407).

## مایگریشن

`rmopscenter1` (down_revision=`rmaccount1`) — drop جدول + ۵ ایندکس. `downgrade()` جدول را دقیقاً
مطابق `b7d3e5f9a1c4` + `c8e1f4a7b2d6` (finding_type VARCHAR(64)) بازسازی می‌کند. ۵۴ ردیف یافته
بازنمی‌گردند (derived بودند؛ تولیدکننده‌شان حذف شده).

**زنجیره:** `rmpayship2 → rmaccount1 → rmopscenter1 → rmi18n1 → …`

## راستی‌آزمایی (شواهد زنده)

| چک | نتیجه |
|---|---|
| روت‌های ops-center (زنده) | ۴۰۴ |
| `/admin/audit` با auth | ۲۰۰ (محفوظ) |
| beat entries | صفر برای reconcile-payments/audit-order-lifecycle |
| بوت بک‌اند | ۸۰۳ مسیر، صفر روت exception/reconciliation |
| تست‌ها | ۲۱۰/۲۱۰ بک‌اند · ۲۰/۲۰ فرانت · گیت‌ها ۲/۲ · tsc سبز |
| برگشت‌پذیری | upgrade→downgrade→upgrade روی DB خالی سبز |
| UI sweep با auth | ۵۰/۵۰ · `/admin/exceptions` با auth = ۴۰۴ |
| nav reachability | ۴۸/۴۸ پوشه |
| آرشیو | `_archived/ops-center-2026-10-05/` (۱۸ فایل + README) |

راستی‌آزمایی متقابل: سشن ۱ (verify مستقل، همه سبز) + ناظر ۱.۱ (کشف two-head در موج i18n و
نظارت زنجیرهٔ migration).
