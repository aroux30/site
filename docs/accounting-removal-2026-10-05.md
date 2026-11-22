# حذف ماژول حسابداری — کدینگ حساب‌ها — ۲۰۲۶-۱۰-۰۵

> **وضعیت نهایی: ماژول حذف شد.** مالک پروژه (۲۰۲۶-۱۰-۰۵) تصمیم گرفت آخرین
> بازماندهٔ حسابداری — «کدینگ حساب‌ها» — هم کامل حذف شود: کد، صفحه، جدول،
> permissionها. این تصمیم، ادامهٔ زنجیرهٔ `rmjournal1` است که دفتر روزنامه و
> بستن دوره را حذف کرده بود و کدینگ را «عمداً» نگه داشته بود؛ آن استثنا در
> همین سند باطل می‌شود. کد در `_archived/accounting-module-2026-10-05/`
> آرشیو است؛ حذف جدول با مایگریشن برگشت‌پذیر `rmaccount1` انجام شد
> (upgrade → downgrade → upgrade تست شد؛ دقت بازسازی بایت‌به‌بایت verify شد).

## چرا حذف شد — شواهد (همه راستی‌آزمایی‌شده در ۲۰۲۶-۱۰-۰۵)

### ۱. جدول فقط seed بود، صفر دادهٔ کسب‌وکاری

خواندن مستقیم از دیتابیس زنده پیش از حذف:

```
accounts: 22 rows — همه از seed استاندارد ایرانی (application/account_seed.py)
```

هر ۲۲ ردیف دقیقاً همان چارت استاندارد بود؛ هیچ ردیفی را اپراتور نساخته بود.
پس حذف، هیچ دادهٔ کسب‌وکاری را از بین نبرد.

### ۲. هیچ‌چیز به کدینگ ارجاع نمی‌داد

- تنها FK ای که به `accounts` اشاره داشت `journal_lines.account_id` بود که
  با `rmjournal1` (۲۰۲۶-۱۰-۰۴) از بین رفته بود — در لحظهٔ حذف هیچ جدولی
  به `accounts` ارجاع نداشت (پروب `pg_constraint`).
- صفر import زندهٔ `app.modules.accounting` در کل بک‌اند. آخرین دو مورد:
  spec روتر در `main.py` و import مدل در `alembic/env.py` — هر دو با همین
  حذف رفتند.
- فرانت‌اند: صفر مصرف‌کننده جز صفحهٔ `/admin/accounting` و آیتم سایدبار.

### ۳. رویداد outbox مرده هم با آن رفت

`cashback_service.py` رویداد `CashbackCredited` را در outbox منتشر می‌کرد
«تا listener حسابداری سند بزند». آن listener در `rmjournal1` حذف شده بود؛
یعنی این publish صفر consumer زنده داشت و فقط ردیف مرده تولید می‌کرد.
پروب: صفر ردیف `CashbackCredited` در `outbox_messages`. publish حذف شد.

### ۴. برای فروشگاه، ابزار اشتباهی بود

چارت حساب استاندارد ایرانی + دفتر دوطرفه، از روی چک‌لیست ERP ساخته شده
بود، نه از نیاز واقعی یک فروشگاه اینترنتی کالای دیجیتال. رکورد پول واقعی:
سفارش/پرداخت/کیف‌پول. فاکتور چاپی مشتری
(`orders/application/order_receipt_renderer.py`) مسیر جداگانه و مستقل است
و دست نخورد.

## چه چیزی حذف شد

| نقطه | جزئیات |
|---|---|
| ماژول بک‌اند | `backend/app/modules/accounting/` — کل (api، application، domain، schemas) |
| جدول | `accounts` — مایگریشن `rmaccount1` |
| Permissionها | `accounting:read`، `accounting:write` + grantهای نقش admin |
| روتر | spec `app.modules.accounting.api` در `main.py` |
| Alembic | import مدل در `env.py` |
| RBAC | دو بلوک `_p(...)` در `permission_catalog.py` |
| رویداد مرده | publish `CashbackCredited` در `cashback_service.py` |
| صفحات ادمین | `/admin/accounting` (page + layout) + آیتم سایدبار + آیکن BookOpen |
| کلاینت API | `frontend/lib/api/accounting.ts` |
| کامنت‌های کهنه | `main.py`، `tax_routes.py`، `subscription_service.py` (×۲)، `automation/tasks.py` |

## چه چیزی دست نخورد

- **مالیات** (`checkout/api/tax_routes.py`) — ماژول جدا و زنده؛ فقط کامنت
  «same as the accounting module» به متن بی‌ارجاع عوض شد.
- **اشتراک‌های دوره‌ای** — فقط دو کامنت «accounting journal entry» در
  docstring عوض شد؛ رفتار دست نخورد.
- **داشبورد مغایرت‌ها** (`/admin/exceptions`) — جدا از حسابداری، زنده.
- **سفارش/پرداخت/کیف‌پول/فاکتور چاپی** — دست نخورد.

## مایگریشن `rmaccount1` — برگشت‌پذیری تست‌شده

- `upgrade()`: drop سه ایندکس + جدول `accounts`؛ سپس DELETE دو permission
  (grantهای `role_permissions` با ON DELETE CASCADE می‌روند).
- `downgrade()`: بازسازی `accounts` دقیقاً مطابق `a9c1e3f5b7d9`
  (ستون‌ها، Enum، FK، قیدها، ایندکس‌ها) + درج هر ۲۲ ردیف با id و
  parent_id اصلی + بازگرداندن دو permission با id پین‌شده از DB زنده +
  grant نقش admin.
- **تست دقت:** اسنپ‌شات DDL+داده ← upgrade ← downgrade ← اسنپ‌شات مجدد ←
  مقایسه: `columns/constraints/indexes/perms/grants` + ۲۲ ردیف → **IDENTICAL**.
- **نکتهٔ زنجیره:** `rmaccount1` head جدید است (`down_revision = rmpayship2`).
  در downgrade زنجیره، اول همین برمی‌گردد؛ وقتی نوبت `rmjournal1` برسد،
  `accounts` وجود دارد و FK جدول `journal_lines` سالم می‌نشیند.

## راستی‌آزمایی بعد از حذف (همه سبز)

- بک‌اند بوت: `healthz` = 200؛ `/api/v1/admin/accounting/accounts` = 404.
- `alembic heads` = تک head `rmaccount1`؛ `alembic_version` = `rmaccount1`.
- grep سراسری زنده: صفر ارجاع `accounting` در `backend/app` و فرانت‌اند.
- تست‌های بک‌اند: ۲۰۹/۲۰۹ سبز. گیت‌ها: ۲/۲ pass. تست‌های فرانت: ۲۰/۲۰ سبز.
- `tsc --noEmit`: سبز.
- فرانت زنده (با احراز هویت): `/admin/accounting` = 404، `/admin/bi` = 200.
- سایدبار: آیتم «کدینگ حساب‌ها» حذف؛ صفر رفرنس به مسیر در سورس.
- UI sweep زنده: **۵۳/۵۳** روت ادمین سبز (شامل `/admin/reports` بعد از رفع زیر).

## یافتهٔ جانبی رفع‌شده: health-check ES به proxy ویندوز گوش می‌داد (main.py)

در sweep اول، `/admin/reports` خطای 503 از `/api/health/ready` گرفت. ریشه
(کشف ناظر سشن ۲، علت‌شناسی با شاهد قطعی نهایی‌شده): `httpx.AsyncClient`
پیش‌فرض (`trust_env=True`) درخواست probe به ES لوکال را از proxy رد می‌کرد →
ReadTimeout → گزارش «elasticsearch: unavailable» درحالی‌که کلاستر healthy
بود. repro: با `trust_env=True` → ReadTimeout؛ با `trust_env=False` → 200.

**منبع proxy: رجیستری ویندوز، نه env شل** (تصحیح ۲۰۲۶-۱۰-۰۵): پروسهٔ
uvicorn (parent و worker) صفر proxy env داشت (psutil: ۴۹ var، هیچ PROXY).
اما `HKCU\...\Internet Settings` → `ProxyEnable=1`،
`ProxyServer=127.0.0.1:10809`؛ و `urllib.request.getproxies()` در ویندوز
رجیستری را می‌خواند. لایهٔ عمیق‌تر: `getproxies_registry()` پایتون مقدار
`ProxyOverride` (لیست استثنای `localhost;127.*;...`) را **نادیده می‌گیرد**
(سورس ۳.۱۴) — پس env پاک بودن کافی نیست و باگ با هر ری‌استارت بدون فیکس
برمی‌گردد.

این باگ از ۲۰۲۶-۱۰-۰۳ در لاگ‌ها بود (نامرتبط به حذف حسابداری)، ولی رفع شد:

- `_check_es` (main.py:~499): `httpx.AsyncClient(timeout=1.5, trust_env=False)`
- `_diag_es` (main.py:~575): همان تغییر
- پیشینه: `site_health_service.py:475` همین الگو را از قبل دارد («an origin
  check must not inherit ambient proxy settings») — کنوانسیون پروژه.
- بعد از رفع: `readyz` = ok، `deep-health` = healthy (ES green، ~۲۰۷ms)،
  `/admin/reports` سبز در sweep.
- تست‌ها بعد از رفع: ۲۰۹/۲۰۹ بک‌اند، ۲۰/۲۰ فرانت، ۲/۲ گیت، tsc سبز.
