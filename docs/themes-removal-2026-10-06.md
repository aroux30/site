# حذف ماژول «پوسته‌ها» (Switchable Themes) — ۲۰۲۶-۱۰-۰۶

## دستور

> «"پوسته‌ها" هرچیزی مربوط به این ماژول ها هست میخوام پاک کنی کامل پاک کن از کد هیچ اثری نمیخوام ازشون باشه برای سایت فروشگاه اینترنتی کارایی ندارن! و فقط دو تا تم برای روز و شب داشتیم دیفالت و پیش‌فرض از خیلی قبل همونا کافیه بنظرم!»

## ماژول چه بود

مجموعه‌ی «پوسته‌های قابل‌تعویض» (پاریتی با Appearance وردپرس): هر پوسته یک مجموعه‌ی نامدار از توکن‌های رنگ (۷ رنگ + شعاع گوشه) بود. فعال‌سازی، توکن‌ها را در single type «theme» کپی می‌کرد و `layout.tsx` آن‌ها را به‌صورت CSS variable روی `<html>` تزریق می‌کرد — بدون دیپلوی. چهار پوسته‌ی کارخانه (default/minimal-light/midnight/warm-safran) + امکان snapshot و حذف برای اپراتور.

## چرا حذف شد

- برای سایت فروشگاهی کاربردی نداشت — فقط دکمه‌ی روز/شب لازم است.
- دکمه‌ی روز/شب (`ThemeToggle`) کاملاً مستقل است: فقط `classList` + `localStorage` + `prefers-color-scheme`؛ هیچ وابستگی به توکن‌های پوسته ندارد.
- تزریق توکن روی `<html>` با `.dark` تداخل داشت (باگ کنتراست ۱.۰۳ در ۲۰۲۶-۱۰-۰۴) — حذف آن، رفتار حالت تاریک را به حالت درست برمی‌گرداند.
- `dark_mode_default` در هیچ کدی خوانده نمی‌شد (فیلد مرده).

## دامنهٔ حذف

### Backend

| مورد | محل |
|---|---|
| مدل `SiteTheme` (جدول `site_themes`) | `app/modules/settings/domain/models.py` — حذف شد |
| سرویس `theme_service.py` (کل فایل، ۲۴۱ خط) | `app/modules/settings/application/` — حذف شد |
| ۴ روت `/settings/admin/themes` (list/create/activate/delete) | `app/modules/settings/api/routes.py` — حذف شد |
| ایمپورت‌های بی‌استفاده (`uuid`, `get_current_user_id`) | `settings/api/routes.py` — حذف شد |
| single type «theme» (`_THEME_SCHEMA`/`_THEME_DEFAULT`/`_COLOR_RE` + registry entry) | `app/modules/content/application/single_type_service.py` — حذف شد |
| کامنت «palette پوسته» | `app/modules/settings/schemas/settings.py` — بازنویسی شد |

### Frontend

| مورد | محل |
|---|---|
| صفحه‌ی `/admin/themes` (کل پوشه) | `app/admin/themes/` — حذف شد |
| کلاینت `themesApi` + تایپ‌های `SiteTheme`/`ThemeTokens` | `lib/api/themes.ts` — حذف شد |
| لودر توکن (`fetchThemeTokens`/`themeStyleVars`/`hexToHsl`/`COLOR_TO_VAR`) | `lib/theme.ts` — حذف شد |
| پل پیش‌نمایش زنده (`ThemePreviewBridge`) | `components/shared/theme-preview-bridge.tsx` — حذف شد |
| تزریق `style={styleVars}` + `<ThemePreviewBridge />` + ایمپورت‌ها | `app/layout.tsx` — حذف شد |
| `ThemeEditor` (ویرایشگر رنگ در CMS) + `<ThemeEditor />` | `app/admin/cms/page.tsx` — حذف شد |
| `ThemeConfig` + `singleTypesApi.getTheme` | `lib/api/content.ts` — حذف شد |
| entry منو «پوسته‌ها» + ایمپورت `Palette` | `lib/admin-nav.ts` — حذف شد (سشن ۱ در بازسازی ناوبری هماهنگ کرد) |

### Database

- `site_themes` (جدول، ۲ index) — drop شد؛ ۴ ردیف قبل از drop در `_capture_theme.json` آرشیو شدند.
- `site_settings` ردیف `key='theme' AND "group"='cms'` — delete شد.
- `audit_logs` با `resource='site_theme'` (۲۰ ردیف) — طبق رویهٔ ثابت، دست‌نخورده ماند (تاریخچه است، نه state ماژول).

## دیتابیس — مایگریشن

- **مایگریشن:** `rmtheme1` (`2026_10_06_rmtheme1_remove_switchable_themes.py`)
- **زنجیره:** `rmnews1 → rmdms1 → auditct1 → rmtheme1 (head)` — خطی، تک‌سر.
  - نکته: `auditct1` (اصلاح enum سشن ۲) همزمان روی `rmdms1` نشسته بود؛ `rmtheme1` روی آن re-parent شد تا head موازی شکل نگیرد.
- **upgrade:** drop index ها → drop جدول → delete ردیف single type (با `"group"` کوتیشن‌دار چون کلمهٔ رزرو است).
- **downgrade:** بازسازی بایت‌به‌بایت جدول طبق DDL مایگریشن سازنده (`c4d81f52a9b7`) + درج ۴ پوسته و ردیف تنظیمات با UUID و timestamp مشاهدشده (`ON CONFLICT DO NOTHING`).
- **تست round-trip (اجرا شد):** upgrade → جدول و ردیف رفتند (head=rmtheme1) → downgrade → ۴ پوسته + ردیف برگشتند با همان UUIDها → upgrade → دوباره صفر. ✅

## پروب زنده (بعد از حذف)

| پروب | نتیجه |
|---|---|
| `GET /api/v1/content/single-types/theme` | **422** — «تایپ تکی theme شناخته‌شده نیست» |
| `GET /api/v1/settings/admin/themes` | **404** |
| `GET /api/v1/content/single-types` | 200 — فقط `homepage_config` و `header_menu` |
| `GET /api/v1/content/single-types/homepage_config` | 200 — سالم |
| `GET /` (فروشگاه) | 200 — `<html>` بدون استایل توکن inline |
| `/admin/themes` (فرانت) | صفحه‌ی پوسته‌ها دیگر رندر نمی‌شود |
| دکمه‌ی روز/شب | دست‌نخورده (`ThemeToggle` مستقل؛ فقط `globals.css` `:root`/`.dark`) |

## تست‌ها و گیت‌ها

| مورد | نتیجه |
|---|---|
| pytest بک‌اند | **۲۰۸ پاس** (بدون تغییر — هیچ تستی به theme وابسته نبود) |
| گیت‌های `run_gates.py` | **۲/۲ پاس** (ORM sync؛ setting shapes) |
| `tsc --noEmit` | تمیز |
| vitest فرانت (شامل reachability ناوبری جدید) | **۲۴ پاس** |
| sweep متن (back+front) | صفر ارجاع باقی‌مانده |

## ارجاع‌های عمداً باقی‌مانده

1. مایگریشن تاریخی `c4d81f52a9b7` — سابقهٔ ساخت جدول؛ دست‌نخورده.
2. `frontend/public/manifest.json` → `theme_color` و `offline.html` → `<meta name="theme-color">` — متادیتای PWA (رنگ نوار مرورگر)، نه پوستهٔ قابل‌تعویض.
3. `app/layout.tsx` → `viewport.themeColor` (روشن/تاریک) — متادیتای مرورگر.
4. کامنت‌های عمومی وردپرس («menu locations from the theme» / «theme code») در `content/api/routes.py` و `widgets.py` — دربارهٔ مفهوم وردپرس، بی‌ارتباط با این ماژول.
5. `docs/monitor-notes-2026-10-04.md` — تحلیل حادثهٔ کنتراست؛ سابقهٔ تاریخی.
6. artifact های بیلد (`.next*`, `tsconfig.tsbuildinfo`, `ui-sweep-report.json`) — بازتولیدشدنی. **توجه:** `.next-prod` (بیلد prod) در لحظهٔ حذف استال بود و هنوز `/admin/themes` را در manifest داشت؛ بازبینی ناظر (۱.۱) آن را پیدا کرد. هیچ سروری از آن سرو نمی‌کرد (هر سه پورت فعال 3000/3100/3200 dev server با turbopack؛ چانک اختصاصی `.next-prod` از 3100/3200 → 404)، ولی طبق توصیهٔ ناظر با `NEXT_DIST_DIR=.next-prod npx next build` تازه‌سازی شد: صفر فایل themes، manifest تمیز، BUILD_ID جدید. درس: **بعد از موج حذف، هر dist بیلد prod را هم rebuild کن** — نه فقط بیلد ایزولهٔ وریفای.
7. `audit_logs` (۲۰ ردیف `site_theme`) — تاریخچه.

## بازگردانی

```bash
cd backend
python -m alembic downgrade auditct1   # جداول + ۴ ردیف + ردیف تنظیمات برمی‌گردند
python -m alembic upgrade head         # دوباره حذف
```

کد: کپی فایل‌های `_archived/themes-removal-2026-10-06/` به مسیرهای اصلی + برگرداندن ۷ فایل `_modified/` + حذف خطوط حذف‌شده مطابق دیف. جزئیات در README آرشیو.

## درس‌ها

- `themeService` فقط یک importer داشت (routes) و جدول صفر FK — حذف تمیز بود؛ «راستی‌آزمایی قبل از ادعا» باز هم جواب داد.
- `dark_mode_default` سه جا در تایپ‌های فرانت تعریف شده بود و هیچ‌جا خوانده نمی‌شد — فیلد مرده با حذف ماژول خودبه‌خود رفت.
- تزریق inline توکن روی `<html>` برندهٔ `.dark` بود — یعنی ماژول پوسته از روز اول با حالت تاریک در تضاد بود؛ حذفش رفتار درست را برمی‌گرداند.
- `site_settings."group"` کلمهٔ رزرو SQL است — در DELETE مایگریشن باید کوتیشن‌دار باشد.
- هماهنگی با سشن ۱ (بازسازی ناوبری) از طریق پیام پیش از ویرایش انجام شد و entry منو در فایل جدید `lib/admin-nav.ts` توسط خودشان برداشته شد — تست reachability دوطرفه (route بدون entry و entry بدون route) سبز ماند.
- **ترتیب حذف مهم است:** فایل importشده اول پاک شد و importer (`app/layout.tsx`) کمی بعد ویرایش شد؛ در همان پنجرهٔ میانی، dev server (turbopack) خطای `Module not found` را کامپایل و کش کرد و سایت ~۱۰ دقیقه ۵۰۰ داد تا ری‌استارت شد. دیسک از ۰۲:۳۰ درست بود (کش کهنه بود)، ولی درس: **اول importer ها ویرایش، بعد فایل حذف** — و بعد از هر موجی که فایل importشده پاک می‌کند، dev server را فعالانه ری‌استارت کن. دربارهٔ prod در همان بازه: **ملاک سلامت، rebuild ایزولهٔ `.next-rmtheme1` بود که بعد از حذف گرفته شد** (سبز، `/admin/themes` غایب از manifest)؛ بیلد استال `.next-prod` (۲۱:۵۹، قبل از حذف) هنوز صفحهٔ themes را داشت تا در همین بازبینی تازه‌سازی شد (بند ۶ «ارجاع‌های عمداً باقی‌مانده»).
