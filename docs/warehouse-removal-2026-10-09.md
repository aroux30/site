# حذف کامل انبارها — ۲۰۲۶-۱۰-۰۹

این سند با اصول ASD-STE100 نوشته شده است: جمله‌های کوتاه، صدای فعال، یک واژه برای یک مفهوم.

---

## ۱. دستور مالک

مالک در پنل مدیریت، صفحهٔ «انبارها» را دید. مالک گفت:

> «این بخش رو کامل حذف کن چون ما موجودی فیزیکی نداریم فعالا و فروشگاهمون مربوط به اشتراک و ردیم کد ووچر هست که اینترنتی هست و فیزیکی نیست و این هم ناقصه پس حذف کن بعدا خواستی کامل و جامع اضافه میکنیم»

معنی دستور:

1. بخش انبارها باید کامل حذف شود.
2. فروشگاه فقط کالای دیجیتال می‌فروشد: اشتراک، کد، ووچر.
3. موجودی فیزیکی وجود ندارد. پس انبار فیزیکی لازم نیست.
4. صفحهٔ فعلی ناقص بود. حذف می‌شود. اگر لازم شد، بعداً کامل ساخته می‌شود.

مالک در پاسخ به پرسش دامنه، «حذف کامل دامنه + دیتابیس» را انتخاب کرد. یعنی صفحه، اندپوینت‌ها، سرویس، جدول، و ستون‌های دیتابیس — همه حذف شوند.

---

## ۲. چرا حذف بی‌خطر بود؟

بررسی زندهٔ دیتابیس قبل از حذف، این نتیجه‌ها را داد:

| جدول یا ستون | ردیف | محتوا |
|---|---|---|
| `warehouses` | ۱ | فقط ردیف سنتینل «انبار مرکزی» (`CENTRAL`) |
| `inventory_items.warehouse_id` | ۱۳۶۹ | همه یک مقدار متمایز داشتند (سنتینل) |
| `inventory_reservations.warehouse_id` | ۱۲۵۳ | همه یک مقدار متمایز داشتند (سنتینل) |
| `inventory_transactions.warehouse_id` | ۲۲۰۱ | همه یک مقدار متمایز داشتند (سنتینل) |
| `inventory_reorder_rules` | ۰ | جدول خالی |
| `saved_reports` | ۰ | جدول خالی؛ هیچ فیلتر warehouse ذخیره نشده بود |
| `inventory_items` ردیف تکراری variant | ۰ | هیچ variant در دو انبار نبود |

نتیجه: حذف ستون `warehouse_id` هیچ اطلاعاتی را از دست نمی‌دهد. همهٔ ردیف‌ها در یک انبار بودند. ledger موجودی سالم می‌ماند.

---

## ۳. چه چیزی حذف شد

### ۳.۱ سطح ادمین

| مورد | مسیر یا نام |
|---|---|
| صفحهٔ انبارها | `/admin/warehouses` |
| آیتم منوی سایدبار | گروه «فروشگاه» → «انبارها» |
| کلاینت API | `frontend/lib/api/warehouses.ts` |
| ۸ اندپوینت ادمین | `GET/POST /admin/inventory/warehouses`, `GET/PATCH /warehouses/{id}`, `GET /warehouses/default`, `GET /warehouses/stock`, `POST /warehouses/{id}/deactivate`, `POST /warehouses/{id}/reactivate` |
| سرویس بک‌اند | `warehouse_service.py` (کل فایل) |
| قراردادهای Pydantic | `schemas/warehouse.py` (کل فایل) |
| روتر ادمین خالی‌شده | `admin_router` در ماژول inventory |
| بوت‌استرپ startup | بلوک `ensure_default_warehouse` در `main.py` |

### ۳.۲ دیتابیس (migration `rmwarehouse1`)

| مورد | تغییر |
|---|---|
| جدول `warehouses` | حذف کامل (۱ ردیف سنتینل) |
| `inventory_items.warehouse_id` | حذف ستون + ایندکس |
| `inventory_reservations.warehouse_id` | حذف ستون + ایندکس |
| `inventory_transactions.warehouse_id` | حذف ستون + ایندکس |
| `inventory_reorder_rules.warehouse_id` | حذف ستون + ایندکس + unique ترکیبی |
| `uq_inventory_items_variant_warehouse` | جایگزین با `uq_inventory_items_variant_id` (تک‌ستونی) |
| `uq_reorder_variant_warehouse` | جایگزین با `uq_reorder_variant` (تک‌ستونی) |

### ۳.۳ گزارش‌ها و BI

| مورد | تغییر |
|---|---|
| `group_by="warehouse"` در گزارش موجودی | حذف از بک‌اند و فرانت‌اند |
| فیلتر `warehouse_id` در گزارش و CSV | حذف از اندپوینت‌ها |
| فیلتر `warehouse_id` در گزارش‌های ذخیره‌شده | حذف از `_FILTER_KEYS` و پارس |
| `warehouse_id` در مقایسهٔ BI | حذف از پارامترها |
| گزینهٔ «انبار» در UI گزارش‌ها | حذف |

### ۳.۴ داده‌های ورود/خروج (dataexchange)

| مورد | تغییر |
|---|---|
| `DEFAULT_WAREHOUSE_ID` در import موجودی | حذف |
| `DEFAULT_WAREHOUSE_ID` در export موجودی | حذف |

### ۳.۵ کد مرده

| مورد | توضیح |
|---|---|
| `transfer_stock` | انتقال بین دو انبار. صفر فراخوان داشت. حذف شد. |
| `admin_router` خالی | فقط روتر انبار را include می‌کرد. حذف شد. |

---

## ۴. چه چیزی عمداً نگه داشته شد

| مورد | دلیل |
|---|---|
| ledger موجودی (`inventory_items`، `inventory_reservations`، `inventory_transactions`) | فروشگاه روی همین ledger می‌فروزد. فقط ستون انبار حذف شد. |
| `/admin/inventory` | لیست موجودی، تنظیم، قوانین سفارش مجدد، تراکنش‌ها — سطح زندهٔ فروشگاه |
| `/admin/digital-inventory` | انبار کدهای دیجیتال — قابلیت زنده و پرکاربرد فروشگاه دیجیتال |
| کدنامه‌های `inventory:read` / `inventory:write` | روترهای زندهٔ inventory و digital از همین‌ها استفاده می‌کنند. هیچ کدنامهٔ اختصاصی انبار وجود نداشت. |
| قوانین سفارش مجدد (`ReorderRule`) | قابلیت مستقل است. فقط کلیدش از (variant, warehouse) به variant تنها تغییر کرد. |
| متن‌های عادی «انبار» در UI | کپی‌رایتینگ‌اند (مثل «موجودی انبار»). فیچر انبارداری نیستند. |

---

## ۵. مایگریشن

فایل: `backend/alembic/versions/2026_10_09_rmwarehouse1_remove_warehouse_dimension.py`

- شناسه: `rmwarehouse1`
- والد: `seom1` (زنجیرهٔ سشن سئو)
- `upgrade()`: جدول و ستون‌ها و ایندکس‌ها را حذف می‌کند.
- `downgrade()`: همه را دقیقاً با نام‌های اصلی بازمی‌سازد. ردیف سنتینل را هم برمی‌گرداند.

چرخهٔ `downgrade → upgrade` تست شد و تمیز گذشت.

---

## ۶. بازگردانی

1. دستور `alembic downgrade seom1` را اجرا کنید. اسکیما برمی‌گردد.
2. فایل‌های پوشهٔ `_archived/warehouse-removal-2026-10-09/` را به مسیر اصلی کپی کنید.
3. فایل‌های `_modified/` را به مسیرهای اصلی کپی کنید.
4. سرور dev را ری‌استارت کنید.

---

## ۷. راستی‌آزمایی در زمان حذف

| بررسی | نتیجه |
|---|---|
| `alembic_version` | `rmwarehouse1` → بعد از merge سشن سئو: `seom3` |
| ستون `warehouse_id` در دیتابیس | صفر |
| جدول `warehouses` | حذف شد |
| ردیف‌های ledger | ۱۳۶۹ / ۱۲۵۳ / ۲۲۰۱ — سالم |
| کنستِرینت‌ها | `uq_inventory_items_variant_id` و `uq_reorder_variant` برقرار |
| OpenAPI زنده | صفر مسیر warehouse؛ ۷۲۸ مسیر کل |
| پروب زنده | `/admin/inventory/warehouses` → 404 |
| پروب زنده | `/inventory` و `/inventory/reorder-rules` → 401 (سالم) |
| pytest بک‌اند | ۱۹۵ تست سبز |
| vitest فرانت‌اند | ۵۲ تست سبز (شامل گارد ناوبری) |
| `tsc --noEmit` | تمیز |
| گیت‌های کیفیت | ۹/۹ سبز |
| چرخهٔ downgrade → upgrade | تمیز |
| تست سرویس زنده (reserve + rollback) | موفق؛ دادهٔ زنده دست‌نخورده |

---

## ۸. نکتهٔ خارج از دامنه

گیت `check_model_schema_sync` در میانهٔ این موج قرمز شد. علت جدول `seo_404_logs` بود (از migration `seom1`، سشن همکار). مدل `Seo404Log` از `BaseModel` ارث می‌برد. ولی جدول ستون‌های `created_at` و `updated_at` را نداشت. به سشن سئو گزارش شد. آن سشن با migration `seom2` مشکل را رفع کرد. الان گیت سبز است.
