# حذف کانال‌های تلگرام و Web Push (VAPID) — ۲۰۲۶-۱۰-۰۶

## دستور

مالک: «هرچیزی مربوط به این ماژول‌ها هست میخوام پاک کنی کامل پاک کن از کد
هیچ اثری نمیخوام ازشون باشه برای سایت فروشگاه اینترنتی کارایی ندارن!»

سه رکورد فهرست قابلیت هدف بودند:
۱. Telegram bot delivery
۲. Internal Telegram acknowledgement (bot token not configured)
۳. Web push (VAPID)

## چرا این دو کانال حذف شدند

هر دو کانال برای فروشگاه اینترنتی ایرانی کاربرد عملی نداشتند:

- **تلگرام:** بدون توکن ربات فقط شبیه‌سازی بود؛ جریان اتصال حساب
  (کد ۸ کاراکتری + اتصال دستی اپراتور) نیمه‌کاره ماند — وب‌هوک ربات هرگز
  ساخته نشد و اتصال کاربر نهایی به اپراتور وابسته بود.
- **Web Push:** پکیج `pywebpush` هرگز نصب نشد؛ کل مسیر (subscribe،
  public-key، ارسال) در حالت MOCK بود. بدون آن حتی با کلیدهای VAPID هم
  ارسال واقعی ممکن نبود.

مشتری نهایی هیچ‌وقت این دو کانال را در عمل ندید. کانال‌های باقی‌مانده:
**ایمیل (SMTP)**، **پیامک (کاوهنگار + fallback)**، **اعلان درون‌برنامه‌ای**.

## دامنهٔ حذف

### Backend

| مورد | جزئیات |
|---|---|
| جداول | `telegram_delivery_logs` (۰ ردیف)، `push_subscriptions` (۰ ردیف) |
| ستون‌ها | `notification_preferences`: `telegram_chat_id`، `telegram_link_code`، `telegram_link_code_expires_at` (هر سه NULL روی تنها ردیف زنده) |
| سرویس‌ها | `telegram_service.py` (۴۱۹ خط)، `push_service.py` (۲۸۹ خط) |
| Providerها | `MockTelegramProvider`، `TelegramBotProvider`، `MockPushProvider`، `WebPushProvider` |
| روت‌ها | ۱۰ عدد: `/notifications/telegram/link-code`، `/telegram/link-status`، `/telegram/link` (DELETE)، `/admin/telegram/link`، `/notifications/push/public-key`، `/push/subscribe`، `/push/unsubscribe`، `/settings/admin/telegram-provider`، `/settings/admin/telegram-provider/test`، `/settings/admin/telegram-delivery-log` |
| تنظیمات | `TELEGRAM_BOT_TOKEN`، `TELEGRAM_BOT_USERNAME`، `TELEGRAM_API_BASE_URL`، `TELEGRAM_TIMEOUT_SECONDS`، `VAPID_PUBLIC_KEY`، `VAPID_PRIVATE_KEY`، `VAPID_SUBJECT`، `PUSH_TIMEOUT_SECONDS` |
| Enumها | `NotificationChannel.TELEGRAM/PUSH`، `CampaignChannel.PUSH` (بدون CHECK constraint — صفر ردیف) |
| رکوردهای registry | `messaging.telegram_bot`، `messaging.telegram_simulation`، `messaging.webpush_vapid` |

### Frontend

| مورد | جزئیات |
|---|---|
| کامپوننت‌ها | `browser-push-card.tsx` (حذف کامل)، `lib/pwa.ts` (حذف کامل) |
| صفحه حساب | کارت اعلان مرورگر + کارت اتصال تلگرام + دو کانال از ماتریس |
| صفحه ادمین | کارت «تنظیمات ربات تلگرام» + تست ارسال + جدول گزارش تحویل |
| Service Worker | رویدادهای `push`، `notificationclick`، `pushsubscriptionchange` |
| API client | تایپ کانال `push` از `messaging.ts` |

## دیتابیس

**probe قبل از حذف (۲۰۲۶-۱۰-۰۶):**

| جدول | ردیف | حکم |
|---|---|---|
| `notification_preferences` | ۱ | ستون‌های تلگرام همه NULL — بدون از دست رفتن داده |
| `telegram_delivery_logs` | ۰ | حذف امن |
| `push_subscriptions` | ۰ | حذف امن |
| `notification_templates.channel` | ۰ ردیف با TELEGRAM/PUSH | بدون نیاز به rewrite |
| `broadcast_campaigns.channel` | ۰ ردیف با PUSH | بدون نیاز به rewrite |

**مایگریشن:** `rmtelegram1` (down_revision=`rmprivacy1`)

- `upgrade()`: حذف ۳ ستون → حذف ۲ جدول (با indexها)
- `downgrade()`: بازسازی کامل هر دو جدول (ستون‌ها، indexها، FKها با نام
  دقیق از snapshot) + برگرداندن ۳ ستون
- **round-trip تست شد:** downgrade → upgrade، اسکیما مطابق snapshot

## تست‌ها و گیت‌ها

| بررسی | نتیجه |
|---|---|
| `check_model_schema_sync.py` | PASS — ۱۵۳ جدول، همه ستون‌های ORM در DB |
| `run_gates.py` | ۲/۲ pass |
| unit tests بکاند | همه pass |
| `tsc --noEmit` (سورس) | تمیز — بدون خطای جدید |
| `eslint` فایل‌های ویرایش‌شده | بدون خطای جدید (warnings از قبل موجود) |
| `ruff` فایل‌های ویرایش‌شده | شمارش خطا دقیقاً برابر نسخهٔ اصلی (بدون خطای جدید) |
| import کامل `app.main` | OK — ۷۴۹ روت، صفر روت telegram/push |
| sweep نهایی repo | صفر ارجاع زنده (به‌جز مایگریشن‌های تاریخی append-only و یک کامنت oEmbed) |

## ارجاع‌های عمداً باقی‌مانده

1. **مایگریشن‌های تاریخی** (`initial_schema`، `notification_channels_v1`) —
   مایگریشن append-only است؛ بازنویسی زنجیرهٔ ارتقا را می‌شکند. دیتابیس
   تازه: ساخت سپس حذف.
2. **کامنت oEmbed** در `(store)/[slug]/page.tsx` — دربارهٔ اشتراک‌گذاری
   لینک در کلاینت‌های چت (Telegram/Slack) است، نه این ماژول.

## بازگردانی

```bash
cd backend
alembic downgrade rmprivacy1   # بازسازی اسکیما (دقیقاً مطابق snapshot)
alembic upgrade head           # برگشت به سر
```

کد سرویس‌ها: `_archived/telegram-webpush-removal-2026-10-06/backend/`.
نسخه‌های اصلی فایل‌های ویرایش‌شده: همان پوشه، زیر `_modified/`.

## درس‌ها

- **enum با `native_enum=False` بدون CHECK constraint:** حذف عضو enum نیازی
  به migration ستونی ندارد — ولی قبل از حذف باید صفر بودن ردیف‌های استفاده‌کننده
  تأیید شود (اینجا: صفر).
- **حذف ستون روی جدولی که ردیف دارد:** اول محتوای ستون را probe کن. تنها
  ردیف `notification_preferences` همه ستون‌های تلگرامش NULL بود، پس حذف
  بدون از دست رفتن وضعیت انجام شد.
- **jفت‌های «واقعی + داخلی»:** حذف کانال واقعی، رکورد «Internal ...acknowledgement»
  را هم منسوخ می‌کند — هر دو با هم می‌روند.
