# حذف کامل i18n — موج دوم: ستون‌های locale محتوا — ۲۰۲۶-۱۰-۰۵

> **وضعیت نهایی: هر اثر i18n/چندزبانگی از کد و اسکیمای زنده حذف شد.**
> موج اول (`rmi18n1`، سشن ۱) کاتالوگ رشته‌ها و لینک‌های ترجمهٔ محتوا را حذف
> کرد ولی ستون‌های `locale` را «بخشی از مدل محتوا» تشخیص داد و عمداً نگه
> داشت؛ `enabled_locales`/`default_locale` هم ماندند. مالک همان روز مستقیماً
> دستور داد: «بقیه‌اش رو هم پاک کن هیچ اثری نمونه» — این سند موج دوم را ثبت
> می‌کند که آن استثناها را باطل کرد. حذف با مایگریشن برگشت‌پذیر `rmi18n2`
> انجام شد (upgrade → downgrade → upgrade تست شد؛ بازسازی ستون‌ها
> بایت‌به‌بایت verify شد).

## چرا حذف شد — شواهد (پروب زندهٔ ۲۰۲۶-۱۰-۰۵)

### ۱. صفر دادهٔ کسب‌وکاری در ستون‌ها

خواندن مستقیم از دیتابیس زنده پیش از حذف:

```
blog_posts.locale:          17 rows — همه 'fa' (۱ مقدار متمایز)
cms_pages:                  0 rows
cms_content_entries:        0 rows
site_settings (enabled_locales/default_locale): 0 rows (فقط کد)
```

هر مقدار موجود دقیقاً همان `server_default='fa'` بود؛ هیچ ردیفی را اپراتور
با زبان دیگر نساخته بود. اسنپشات کامل در
`_archived/i18n-removal-2026-10-05/locale_columns_rows_before_drop.json`.

### ۲. سایت عملاً تک‌زبانه بود

- صفر کامپوننت `t()` را صدا می‌زد (موج اول).
- صفر محتوای غیرفارسی در DB (این موج).
- `enabled_locales`/`default_locale`: صفر read واقعی در runtime — فقط type
  declaration، فرم ادمین، seed و پاسخ `/public/routing`. همان الگوی
  «پیکربندی بدون مصرف‌کننده» (مثل plugins/hooks).

### ۳. فیلترهای locale هیچ خروجی متفاوتی تولید نمی‌کردند

هر فیلتر `locale=fa` روی داده‌ای که ۱۰۰٪ `fa` است، همان کل نتیجه را
برمی‌گرداند — یعنی کد مردهٔ واقعی، نه قابلیت.

## چه چیزی حذف شد

### بک‌اند (کد)

| نقطه | جزئیات |
|---|---|
| مدل‌ها | `blog_posts.locale`، `cms_pages.locale`، `cms_content_entries.locale` + ایندکس‌ها (models + builder) |
| اسکیماها | `BlogPostCreate/Update/Response`، `CmsPageCreate/Update/Response`، `PublicPageSummary`، `ContentEntryWriteRequest`، `ContentSearchResult` |
| سرویس‌ها | `cms_page_service` (فیلتر list + create + copy)، `builder_service` (create + list)، `entry_revision_service`، `blog_service` (create/duplicate/response)، `feed_service` (پارامتر locale همهٔ فیدها)، `transfer_service` (export/import) |
| روت‌ها | Query paramهای locale در content admin/public، search `/content`، `ContentEntryWriteRequest` |
| search | ES mapping، doc builders، `_build_query`، fallback ILIKE، admin search extra |
| dataexchange | ستون «زبان» import/export + `_validate_locale` |
| settings | `enabled_locales`/`default_locale` از `default_options.py` و `/public/routing` |
| http_cache | Accept-Language از cache key |
| relationship_models | کامنت «translation (multi-language link)» + summary روت unlink |

### فرانت‌اند

| نقطه | جزئیات |
|---|---|
| lib | `permalinks.ts` (`enabled_locales`/`default_locale` از `RoutingConfig` + defaults)، `routing.ts` (docstring)، `api/blog.ts`، `api/cms-admin.ts`، `api/content.ts`، `api/services.ts`، `sitemap.ts` |
| صفحات ادمین | فیلتر زبان + سلکت زبان + ستون زبان در `pages`؛ state/payload/badge در `blog`؛ state/سلکت/payload در `content-types` |
| تنظیمات | دو فیلد «زبان‌های فعال محتوا»/«زبان پیش‌فرض» از `content-settings-card` |

### دیتابیس

- مایگریشن `rmi18n2` (down=`rmi18n1`): drop ستون‌های `locale` سه جدول +
  دو ایندکس. `downgrade()` ستون‌ها را دقیقاً با تعریف مایگریشن‌های سازنده
  (`String(10)`, NOT NULL, `server_default 'fa'`) و ایندکس‌ها بازسازی می‌کند.

### مستندات

- ردیف گیت i18n از `quality-gates.md` (اسکریپت و workflow وجود نداشتند).
- `messages/fa.json`/`en.json` از درخت `frontend.md` (دایرکتوری وجود نداشت).

## چه چیزی عمداً ماند (i18n نیست)

- `<html lang="fa" dir="rtl">` و `openGraph.locale: "fa_IR"` — اعلان زبان
  سند فارسی، نه سیستم چندزبانه.
- `<language>fa</language>` در RSS — فیلد استاندارد فید برای سایت فارسی.
- `toLocaleDateString("fa-IR")` / `Intl.NumberFormat` — قالب‌بندی نمایش،
  نه ترجمه.
- `toLocaleLowerCase()` در جستجو — متد استاندارد رشته.

## راستی‌آزمایی

| چک | نتیجه |
|---|---|
| grep سراسری (`locale`/`i18n`) در بک‌اند + فرانت | صفر ارجاع غیرِ فرمت‌بندی |
| `alembic heads` | تک‌سر: `rmi18n2` |
| DB: ستون locale در کل اسکیما | صفر جدول |
| upgrade → downgrade → upgrade | ستون‌ها/ایندکس‌ها بایت‌به‌بایت؛ ۱۷ ردیف `fa` بازسازی |
| pytest بک‌اند | ۲۰۹/۲۰۹ سبز |
| `tsc --noEmit` فرانت | سبز |
| `next build` (dist جدا، بدون آسیب به سرور زنده) | سبز؛ صفر صفحهٔ i18n/translations |
| openapi | ۶۱۰ مسیر، صفر مسیر i18n/alternates/translations |
| `/public/routing` زنده | ۵ کلید (بدون localeها) |
| سرورهای زندهٔ :3000/:3100 بعد از همه‌چیز | ۲۰۰ |
