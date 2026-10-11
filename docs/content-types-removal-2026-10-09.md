# حذف ماژول‌های سازنده تایپ محتوا (2026-10-09)

## هدف و دستور مالک
مالک سیستم اعلام کرد این پلتفرم یک فروشگاه اینترنتی است و نیازی به ابزارهای ساخت تایپ محتوای سفارشی (فرم‌سازهای خبری یا تایپ‌های سفارشی مشابه Strapi و وردپرس) ندارد.  
برای نیازمندی‌های محتوایی سایت، بخش‌های استاندارد وبلاگ (پست‌ها، دسته‌ها، برچسب‌ها، تاکسونومی‌های سفارشی) و برگه‌های ثابت CMS کافی است.  
بنابراین، دو سیستم موازی سازنده تایپ محتوا به طور کامل از کد، دیتابیس، پنل مدیریت، روت‌های عمومی و تسک‌های پس‌زمینه حذف شدند.

---

## بخش‌های حذف‌شده

| بخش | نام سیستم | فایل‌ها و جداول حذف‌شده |
|---|---|---|
| **دیتابیس** | CMS Builder | جداول `cms_content_types`, `cms_content_entries`, `cms_content_entry_revisions` |
| **دیتابیس** | Blog CPT | جداول `custom_post_types`, `custom_post_entries`, `custom_post_entry_revisions` |
| **بک‌اند دامنه و سرویس** | CMS Builder | `content/domain/builder.py`, `content/domain/entry_extras.py`, `content/application/builder_service.py`, `content/application/entry_revision_service.py` |
| **بک‌اند دامنه و سرویس** | Blog CPT | `blog/domain/custom_post_types.py`, `blog/application/custom_post_revision_service.py`, `ContentTypeService` در `taxonomy_service.py` |
| **اندپوینت‌های API** | CMS Builder | ۱۲ اندپوینت در `/api/v1/content/admin/content-types*` و `/api/v1/content/content-types*` |
| **اندپوینت‌های API** | Blog CPT | ۱۱ اندپوینت در `/api/v1/admin/blog/content-types*` و `/api/v1/blog/content-types*` |
| **تسک‌های پس‌زمینه** | Celery Beat | تسک `publish-scheduled-cpt-entries` و انتشار زمان‌بندی‌شده ورودی‌ها در `content/tasks.py` |
| **پنل مدیریت** | CMS Builder | صفحه کامل `/admin/content-types` و منوی «سازنده تایپ محتوا» در گروه محتوا |
| **پنل مدیریت** | Blog CPT | تب «تایپ‌های محتوا» از صفحه مدیریت وبلاگ (`/admin/blog`) |
| **فروشگاه عمومی** | Storefront | صفحه عمومی رندر آرشیو `/content/[slug]` |
| **کلاینت‌های فرانت‌اند** | API Clients | کلاینت‌های `contentTypesApi` و `contentTypesPublicApi` از `cms-admin.ts` و `wp-parity.ts` |

---

## بخش‌هایی که عمداً حفظ شدند (دست‌نخورده)
* **نوشته‌های وبلاگ (`blog_posts`)**: سیستم کامل مقالات و وبلاگ، دسته‌بندی‌ها، برچسب‌ها و نظرات.
* **برگه‌های CMS (`cms_pages`)**: صفحات ثابت، منوهای سایت، سوالات متداول (FAQ)، و الگوهای تکرارپذیر (Reusable Blocks).
* **تاکسونومی‌های سفارشی (`custom_taxonomies`)**: برای نوشته‌ها و برگه‌ها همچنان فعال است (`OBJECT_TYPES = ("blog_post", "cms_page")`).
* **انتقال داده و واردکننده WXR**: ایمپورت و اکسپورت مقالات و برگه‌ها از طریق ماژول `dataexchange` بدون تغییر فعال است.

---

## مایگریشن دیتابیس (`rmcpt1`)
* شناسه مایگریشن: `rmcpt1`
* والد (down_revision): `seom3`
* این مایگریشن ۱۰۰٪ برگشت‌پذیر (Reversible) است و در صورت اجرای `downgrade -1` تمامی ۶ جدول با کلیدهای اصلی، ایندکس‌ها، قیود و پیش‌فرض‌ها مجدداً ایجاد می‌شوند.
* داده‌های قبل از حذف در `_archived/content-types-removal-2026-10-09/db_snapshot_before.json` نگهداری می‌شوند.
