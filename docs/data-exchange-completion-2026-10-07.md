# تکمیل «ورود و خروج داده» — WXR + ۴ موجودیت جدید (2026-10-07)

## شکایت کاربر (شاهد: اسکرین‌شات صفحه)

> «از سایتم خروجی گرفتم بیارم اینجا اینپورت کنم اصلا اون فرمت xml رو نداره نمیشه بارگذاری کرد
> یک سری موارد هم انگار ناقصه فقط وبلاگ و محصولات و برگه‌های سایت رو داره خیلی ناقصه!»

دو شکاف واقعی تأیید شد:

1. **XML وردپرس (WXR) در این صفحه نبود.** یک parser و روت WXR وجود داشت
   (`blog/application/wxr_parser.py` + `/admin/blog/import/wxr`) ولی فقط زیر
   `/admin/blog` → تب «انتقال محتوا» — جای اشتباهی برای کسی که به «ورود و خروج داده» می‌رود.
2. **فقط ۳ موجودیت داشت** (محصول/مطلب/برگه).

## یافته‌های حین کار (همه با شاهد)

### الف) فایل خروجی خود کاربر خالی است
`arouxshop.WordPress.2026-10-06.xml` (2.9KB) پارس شد: **۰ نوشته، ۰ برگه،
۰ دسته، ۰ برچسب** — فقط ۲ نویسنده و متادیتای سایت. هنگام Export در وردپرس،
«همهٔ محتوا» انتخاب نشده. (راهنما در UI اضافه شد.)

### ب) مسیر فید RSS/Atom در همین صفحه خراب بود (پیدا شد، رفع شد)
فرانت به `/admin/import-feed/preview` صدا می‌زد؛ بک‌اند `/admin/import/feed/preview`
را سرو می‌کند. پروب زنده: مسیر فرانت **404**، مسیر درست **401 (موجود)**.
یعنی دکمهٔ فید از قبل کار نمی‌کرد. مسیر فرانت اصلاح شد.

### ج) پارسر WXR چهار باگ داشت که ایمپورت را ناقص می‌کرد
1. `category_slugs` (جمع، همهٔ دسته‌های دیده‌شده) تولید می‌کرد ولی importer
   `category_slug` (مفرد) می‌خواند → **هیچ مطلبی با دسته/برچسب لینک نمی‌شد**
   (ردیف‌های دسته ساخته می‌شدند، ولی اتصال هیچ‌وقت).
2. `excerpt:encoded` پارس نمی‌شد (`content:encoded` و `excerpt:encoded` هر دو
   local name یکسان `encoded` دارند؛ lookup قدیمی اولین را برمی‌گرداند).
3. صفحات (`post_type=page`) کلاً رد می‌شدند (`_CONTENT_TYPES = {"post"}`).
4. کامنت‌ها پارس می‌شدند ولی importer هیچ‌وقت نمی‌خواندشان (silently dropped).

### د) باگ ۵۰۰ زنده: stdlib logger با structlog kwargs
`wxr_parser.py` از `logging.getLogger` استفاده می‌کند ولی
`logger.info("wxr_parsed", posts=n, ...)` صدا می‌زد →
`TypeError: Logger._log() got an unexpected keyword argument 'posts'`
در سرور پیکربندی‌شده (تست واحد سبز می‌ماند چون INFO در تست‌ها خاموش است و
صدا زده نمی‌شود). **هر ایمپورت WXR در محیط واقعی ۵۰۰ می‌داد.** در همان کلاس
۳ نقطهٔ دیگر هم پیدا و رفع شد (`feed_parser.py` ×۲، `comment_email_service.py` ×۱).
اسکن AST دائمی ساخته شد: `scripts/check_stdlib_logger_kwargs.py` (گیت ششم،
negative-tested).

## تغییرات

### بک‌اند
- **`blog/application/wxr_parser.py`** — بازنویسی: دسته/برچسب per-item (لیست‌های
  `category_slugs`/`tag_slugs`)، excerpt درست (`_encoded_text` با تفکیک namespace)،
  صفحات با `parent_slug` (resolved از `wp:post_parent` → slug)، کامنت‌ها با
  `wxr_comment_id` + `post_slug` برای اتصال، فیکس logger kwargs. نسخه ۱.۱.
  سخت‌سازی: سقف حجم `MAX_WXR_BYTES` = ۵۰MB + پارس با **defusedxml**
  (XML bomb / entity expansion رد می‌شود — فایل WXR ورودی غیرقابل‌اعتماد است).
- **`blog/application/transfer_service.py`** — `import_json` مقاوم‌سازی:
  هر دو املاى `category_slug`/`category_slugs` و `tag_slugs` را می‌خواند،
  کامنت‌ها را ایمپورت می‌کند (fingerprint = author+content[:300] برای skip در
  re-import؛ threading با `wxr_comment_id_map`)، `skip_existing=False` دیگر
  duplicate نمی‌سازد (update درجا). `allow_comments` از meta خوانده می‌شود.
- **`blog/application/wxr_import.py`** (جدید) — orchestrator مشترک:
  صفحات → `import_content` (content module, upsert by slug + parent hierarchy)،
  بقیه → `import_json`. صفحات اول (flush)، blog آخر (commit داخلی) — یک تراکنش،
  یا همه یا هیچ. بچ‌بندی ۴۰۰تایی برای سقف ۵۰۰ صفحهٔ `import_content`.
- **`dataexchange/api/routes.py`** — دو روت جدید:
  `POST /admin/import/wxr/preview` (فقط شمارش، هیچ نوشتنی) و
  `POST /admin/import/wxr` (ایمپورت کامل با پیام خطای واضح برای فایل خالی).
- **`blog/api/wp_parity_routes.py`** — روت قدیمی `/admin/blog/import/wxr` هم به
  همان orchestrator وصل شد (یک مسیر ایمپورت، نه دو مسیر که drift کنند).
- **آداپتورهای جدید** (هر کدام یک فایل + register در `adapters.py`):
  - `product_category_adapter.py` — دسته‌بندی محصولات (slug؛ parent + path/depth
    recompute مثل `CategoryService`؛ پیش‌نیاز ایمپورت محصول جدید)
  - `blog_taxonomy_adapter.py` — دسته‌های وبلاگ (parent) + برچسب‌های وبلاگ
  - `faq_adapter.py` — پرسش متداول (کلید ترکیبی `(question, category)`)
- **`scripts/check_stdlib_logger_kwargs.py`** + `negative_test_stdlib_logger_kwargs.py`
  + ثبت در `run_gates.py` (گیت ششم).

### فرانت‌اند
- **`frontend/lib/api/data-exchange.ts`** — فیکس مسیر فید (`/admin/import/feed*`)،
  متدهای `previewWxr`/`importWxr`، تایپ‌های `WxrPreview`/`WxrImportStats`.
- **`frontend/app/admin/data-exchange/page.tsx`** — کارت «ایمپورت از خروجی وردپرس
  (XML / WXR)» به سبک کارت فید: پیش‌نمایش (شمارش نوشته/برگه/دسته/برچسب/دیدگاه +
  نمونه‌ها) → دکمهٔ ایمپورت. هشدار صریح وقتی فایل خالی است. دکمهٔ ایمپورت وقتی
  نوشته و برگه صفرند غیرفعال است.
- **`frontend/lib/api/wp-parity.ts`** + **`components/admin/blog/transfer-tab.tsx`** —
  تایپ و پیام نتیجه به‌روز شد (شمارش برگه‌ها).

## تأیید (همه اجرا شد، شاهد دارد)

| چک | نتیجه |
|---|---|
| پارسر روی fixture کامل (۲ نوشته، ۲ برگه، ۲ کامنت، سلسله‌مراتب) | ✅ |
| ایمپورت E2E دیتابیس (rollback-verified) | ✅ پست+دسته+برچسب+کامنت+برگه با parent |
| ایمپورت زنده HTTP (login واقعی → preview → import) | ✅ counts کامل |
| Idempotency (ایمپورت دوم) | ✅ ۲ پست + ۲ کامنت skip |
| چرخهٔ کامل آداپتور جدید (CSV→job→mapping→validate→execute) | ✅ ۳ دسته با path درست (`electronics/phones`) |
| entities API زنده | ✅ ۷ موجودیت |
| مرورگر: کارت WXR + سلکت ۷ گزینه، صفر خطای کنسول | ✅ (اسکرین‌شات) |
| ۲۲۶ تست واحد | ✅ |
| ۶/۶ گیت (شامل گیت جدید stdlib-logger) | ✅ |
| گیت جدید negative-tested (۳ sabotage + ۳ clean case) | ✅ |
| دیتای تست پاک‌شده | ✅ (۶ جدول صفر) |
| XML bomb (DOCTYPE/entity) رد می‌شود | ✅ `EntitiesForbidden` → پیام فارسی |
| سقف ۵۰MB | ✅ oversize رد شد |
| ruff روی همهٔ فایل‌های app تغییریافته | ✅ تمیز (حتی F841 قبلی هم حذف شد) |

## نکات برای بعد

- **فایل WXR کاربر خالی بود** — باید از وردپرس دوباره Export بگیرد و در
  مرحلهٔ انتخاب محتوا، «همهٔ محتوا» را بزند. راهنما در کارت UI هست.
- کامنت‌های صفحات (comments روی `post_type=page`) شمارش می‌شوند ولی ایمپورت
  نمی‌شوند (`comments_on_pages_skipped` در counts) — صفحه‌کامنت سطح
  مدیریت جداگانه‌ای دارد.
- Media/attachment ها در WXR پارس نمی‌شوند (نیاز به fetch-by-URL دارد؛
  سرویس جداگانه است، نه آداپتور).
- در dev ورکر Celery نیست؛ دکمهٔ «اجرای import» job را در `ready` نگه
  می‌دارد (طبیعی — طبق `outbox-dev-backlog-no-worker.md`). در prod worker
  هست. برای تست dev، تسک را دستی اجرا کنید:
  `execute_import_job_task('<job_id>', None)`.

## تکمله — تست با فایل واقعی کاربر (۳۷.۹MB) و سه فیکس دیگر (2026-10-07 ~۰۳:۰۰)

کاربر چهار فایل XML داد؛ فقط فایل «(3)» محتوا داشت (۳۷.۹MB: ۱۸ برگه، ۱ نوشته،
۳۲ دسته، ۱۵ دیدگاه). تست زنده سه مشکل دیگر را آشکار کرد:

### ۱) انتخاب XML از کارت اول → خودکار هدایت شود
کاربر فایل XML را از کارت «شروع import جدید» (CSV/XLSX) انتخاب می‌کرد → 422.
فیکس:  اگر فایل XML باشد، محتوا را می‌خواند؛ اگر نشانهٔ WXR
( / ) داشت به کارت WXR هدایت و صفحه
اسکرول می‌شود؛ وگرنه به مسیر فید.  کارت اول هم 
گرفت. پیام خطای بک‌اند () هم راهنمای کارت درست را می‌دهد.

### ۲) صفحهٔ رزروشده (cart) کل ایمپورت را متوقف می‌کرد → per-page savepoint
خطای اصلی کاربر:  (صفحهٔ
ووکامرس در فایل). قبلاً یک صفحهٔ ردشده کل ایمپورت ۱۸-برگه‌ای را می‌ترکاند.
فیکس: در  هر صفحه داخل ؛ صفحهٔ ردشده
 می‌شود با log و بقیه ادامه می‌دهند.  به
نتیجهٔ orchestrator و پیام UI اضافه شد.
**شاهد زنده:** ایمپورت فایل واقعی → 
(بقیهٔ محتوا کامل لند شد).

### ۳) نامک فارسی percent-encoded → decode
وردپرس  فارسی را انکودشده ذخیره می‌کند
( = «یوسی»). فیکس:  با
 (escape خراب = دست‌نخورده، بدون exception).
صفحهٔ خرابِ ایمپورت‌شده هم در DB اصلاح شد ().

### شاهد نهایی (زنده، همان فایل واقعی)
| چک | نتیجه |
|---|---|
| ایمپورت اول | ۱۴ برگه + ۳۲ دسته + ۱ برچسب + ۱ نوشته + ۱۵ دیدگاه؛ ۴ برگه رزروشده skip |
| ایمپورت دوم (idempotency) | posts=0, comments=0, skipped=1, comments_skipped=15, pages_updated=14 |
| pytest / gates / tsc / vitest | ۲۲۶ / ۶-از-۶ / تمیز / ۲۴ ✅ |
