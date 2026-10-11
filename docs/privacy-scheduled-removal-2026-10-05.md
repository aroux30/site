# حذف ماژول‌های «حریم خصوصی و GDPR» و «رویدادهای زمان‌بندی‌شده» — ۲۰۲۶-۱۰-۰۵

دستور مالک: «هرچیزی مربوط به این ۲ ماژول هست میخوام پاک کنی کامل پاک کن از کد
هیچ اثری نمیخوام ازشون باشه برای سایت فروشگاه اینترنتی کارایی ندارن!»

دامنه با پرسش تأییدی مشخص شد:
- **privacy**: «همه — حذف کامل» (هم صف GDPR و هم صفحهٔ سیاست حریم خصوصی فروشگاه).
- **scheduled-jobs**: «فقط صفحه و ابزارش» — خود Celery beat و ۲۵+ کار فروشگاه
  (انقضای سبد، پاکسازی رسانه، reindex و…) دست‌نخورده ماند.

مایگریشن: **`rmprivacy1`** — `down_revision = "rmi18n2"` (زنجیره خطی حفظ شد).

## چه چیزی رفت — بک‌اند

| جزء | جزئیات |
|---|---|
| سرویس‌های privacy | `privacy_service.py`, `privacy_request_service.py`, `privacy_sources.py`, `privacy_core_sources.py` (۴۵ منبع ثبت‌شده), `privacy_policy_service.py` |
| ماسک IP دیدگاه‌ها | `comment_ip_retention_service.py` + دو تسک در `settings/application/tasks.py` (`purge_expired_privacy_results`, `mask_expired_comment_ips`) |
| API | `settings/api/privacy_confirm_routes.py` + کل بلوک GDPR در `settings/api/routes.py` (۱۳ endpoint) + `/settings/public/privacy-policy` |
| اسکیما/مدل | `schemas/privacy.py`، `PrivacyPolicyResponse`، مدل `PrivacyRequest` + دو enum، و ۳ option پیش‌فرض (`privacy.*`) |
| scheduled-jobs | `automation/application/scheduler_service.py` + دو endpoint `/admin/scheduled-jobs*` + بخش `scheduled_jobs` در `site_health_service.debug_info` |
| beat | دو entry حذف شد (`purge-expired-privacy-results`, `mask-expired-comment-ips`)؛ ۲۵+ entry دیگر دست‌نخورده |
| `ip_anonymize.py` | `ip_is_masked` و `has_ipv6_socket_support` حذف؛ **`anonymize_ip` ماند** (ثبت‌نام از آن استفاده می‌کند) + docstring به‌روز شد |
| اسکریپت‌ها | ۷ اسکریپت verify/negative حذف شد |
| تست | `test_the_info_tab_lists_the_scheduled_jobs` حذف شد (۲۰۹→۲۰۸ تست) |

## چه چیزی رفت — فرانت

| جزء | جزئیات |
|---|---|
| صفحات | `/admin/privacy`, `/admin/scheduled-jobs`, `/account/privacy`, `/(store)/privacy`, `/(store)/privacy/guide` |
| کامپوننت‌ها | `privacy-policy-card.tsx`, `privacy-policy-notice.tsx` (و پوشهٔ `components/privacy/`) |
| API client | `lib/api/privacy.ts`, `lib/api/privacy-admin.ts`, `privacyApi` در `wp-parity.ts`, `privacyPolicyApi` در `settings.ts`, `scheduledJobsApi` در `automation.ts` |
| منو | دو آیتم سایدبار + آیکن CalendarClock بی‌استفاده |
| حساب | لینک «حریم خصوصی و داده‌های من» در داشبورد |
| consent | `PrivacyClause` در ثبت‌نام، `PrivacyPolicyNotice` در دیدگاه‌ها |
| کاربران | دکمهٔ export GDPR و state/تابعش در `/admin/users` |
| Site Health | بخش `scheduled_jobs` در info tab |
| توکن | `privacy_confirm_token` در middleware و auth-guard |
| فوتر | دو لینک «حریم خصوصی» |
| sweep | `/admin/privacy` از QUICK_ROUTES |
| کامنت‌ها | به‌روزرسانی ارجاعات در robots.txt، cms-page-shell، newsletter (برچسب «حذف (GDPR)» → «حذف مشترک») |

## چه چیزی عمداً ماند

- **`RESERVED_ROOTS` (permalinks.ts) و `RESERVED` (admin-bar.tsx)**: واژهٔ `privacy`
  ماند چون این دو لیست guard روتینگ‌اند، نه بخشی از ماژول. اگر اپراتور صفحه‌ای با
  اسلاگ `privacy` در CMS بسازد، بدون این guard مسیرش به بلاگ rewrite می‌شود.
- **`anonymize_ip`** در `core/security/ip_anonymize.py` — مصرف‌کنندهٔ زندهٔ auth دارد.
- **Celery beat و همهٔ کارهای فروشگاه** — فقط صفحهٔ نمایش/اجرای دستی رفت.
- **`blog_public` / robots** — تنظیم مستقل visibility، بی‌ارتباط با ماژول privacy.

## ریسک بررسی‌شده: ماسک IP دیدگاه‌ها

ناظر (سشن ۲) هشدار داد: حذف `mask_expired_comment_ips` یعنی IP کامل دیگر
خودکار ماسک نمی‌شود. **پروب زنده قبل از حذف: `blog_comments` = ۳ ردیف، صفر ردیف
با `author_ip` غیرNULL، صفر ردیف قدیمی‌تر از ۳۰ روز.** پس حذف این کنترل هیچ
دادهٔ واقعی‌ای را بدون پوشش نمی‌گذارد. این تصمیم (حذف ماسک طبق دامنهٔ «هیچ اثری»)
اینجا صریح ثبت می‌شود: **اگر روزی کامنت مهمان با IP فعال شد، دیگر ماسک خودکاری
وجود ندارد و باید آگاهانه بازگردانده شود.**

## دیتابیس (مایگریشن `rmprivacy1`)

- `DROP TABLE privacy_requests` (+ دو ایندکس). اسنپ‌شات قبل: ۲ ردیف fixture
  (هر دو EXPORT؛ یکی PARTIAL یکی COMPLETED؛ صفر payload؛ کاربران email=NULL)،
  صفر FK از بیرون. ردیف‌ها بازنمی‌گردند (fixture بودند و queue حذف‌شده تنها
  نویسندهٔ آن‌ها بود).
- `DELETE FROM site_options WHERE option_key LIKE 'privacy.%'` — دو ردیف زنده
  (`privacy.export_retention_hours`, `privacy.policy_page`) با id/timestamp دقیق
  در `downgrade()` بازمی‌گردند (CAST صریح uuid/timestamptz — درس rmi18n1).
- `downgrade()` جدول را دقیقاً با اسکیمای زنده (p9r1v2w3x4y5 + prvmail1)
  بازمی‌سازد.

## راستی‌آزمایی (همه سبز)

| بررسی | نتیجه |
|---|---|
| `alembic upgrade head` (rmi18n2→rmprivacy1) | ✅ |
| downgrade → snapshot diff (columns/constraints/indexes/options) | ✅ IDENTICAL |
| re-upgrade + head=rmprivacy1 | ✅ |
| تست‌های بک‌اند | ۲۰۸/۲۰۸ |
| گیت‌ها (run_gates.py) | ۲/۲ |
| `tsc --noEmit` | ✅ |
| بیلد پروداکشن (dist مجزا) | ۹۷/۹۷ صفحه |
| تست‌های فرانت | ۱۲/۱۲ |
| UI sweep (۱۲ مسیر ادمین) | ۱۲/۱۲ |
| OpenAPI زنده | ۵۹۳ مسیر، صفر privacy/scheduled |
| prob مسیرهای حذف‌شده | admin→307 (login), API→404, /privacy→catch-all not-found |
| grep نهایی privacy/gdpr | فقط ۲ RESERVED عمدی |

## آرشیو

`_archived/privacy-scheduled-removal-2026-10-05/` — ۵۹ فایل:
- فایل‌های حذف‌شده (verbatim) + `_modified/` (نسخهٔ اصلی فایل‌های ویرایشی)
- `db_snapshot_before.json` / `db_snapshot_after_downgrade.json`
