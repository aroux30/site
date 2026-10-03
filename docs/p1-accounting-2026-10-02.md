# حسابداری واقعی ۱۰۸ آیتم P1 — ۲۰۲۶-۱۰-۰۲

این جدول **با شمردن** ساخته شده. برای هر آیتم، شاهدی که در درخت زنده پیدا شد.
«شاهد» یعنی grep یک فایل برگرداند — نه اینکه کسی ادعا کرده باشد.

| # | مالک | آیتم | شاهد |
| --- | --- | --- | --- |
| 1 | p1 | ناقص] ادیتور و بلاک: نوار ابزار ادیتور — فقط bold/italic/H2/ul/ol/link/oEmbed؛ نقل‌قو | ✅ frontend/components/admin/RichBodyEditor.tsx |
| 2 | p1 | ناقص] ادیتور و بلاک: درج تصویر/رسانه از کتابخانه در بدنه — `MediaPicker` فقط برای تصو | ✅ frontend/components/admin/RichBodyEditor.tsx |
| 3 | p1 | ناقص] ادیتور و بلاک: شورت‌کدها — ۶ شورت‌کد (`gallery/youtube/aparat/button/alert/embe | — |
| 4 | p1 | ناقص] نوشته: تغییر نویسنده — `author_id` فقط در `BlogPostCreate` هست و در `BlogPostUp | ✅ backend/app/modules/blog/schemas/blog.py |
| 5 | p1 | ناقص] نوشته: پیش‌نمایش پیش‌نویس — دکمه «پیش‌نمایش در سایت» به URL عمومی لینک می‌دهد ک | ✅ frontend/lib/api/blog.ts |
| 6 | p1 | ناقص] نوشته: پیش‌نمایش برگه — دکمه‌ی پیش‌نمایش به JSON خام API باز می‌شود نه صفحه‌ی ر | ✅ frontend/app/admin/pages/page.tsx |
| 7 | p1 | ناقص] نوشته: مقایسه‌ی ریویژن‌ها (Diff) — route دیف کلمه‌به‌کلمه در بک‌اند هست ولی UI  | ✅ frontend/app/admin/blog/page.tsx |
| 8 | p1 | ناقص] نوشته: سقف و هرس ریویژن (`WP_POST_REVISIONS`) — هیچ تنظیم تعداد یا حذف ریویژن ق | ✅ backend/app/modules/blog/application/blog_servic |
| 9 | p1 | ناقص] نوشته: فیلترهای فهرست نوشته‌ها — فیلتر نویسنده و بازه‌ی زمانی (dropdown ماه/سال | ✅ backend/app/modules/blog/api/routes.py |
| 10 | p1 | ناقص] نوشته: ویرایش گروهی فیلدها (Bulk Edit) — اکشن‌های گروهی فقط publish/draft/archi | ✅ backend/app/modules/blog/application/blog_servic |
| 11 | p1 | ناقص] نوشته: ویرایش سریع ناقص — Quick Edit دارد ولی نویسنده، فرمت و وضعیت «دیدگاه‌ها  | ✅ backend/app/modules/blog/application/quick_edit_ |
| 12 | p1 | ناقص] نوشته: تاریخ انتشار گذشته — `published_at` در schema به‌روزرسانی هست ولی هیچ فی | ✅ frontend/app/admin/blog/page.tsx |
| 13 | p1 | ناقص] نوشته: نوشته‌ی ویژه (sticky) — سنجاق در فرم و ترتیب «ویژه اول» اعمال می‌شود ولی | — |
| 14 | p1 | ناقص] نوشته: ریدایرکت نامک قدیمی (`wp_old_slug_redirect`) — تاریخچه ثبت می‌شود ولی `r | ✅ backend/app/modules/blog/api/routes.py:0
backend |
| 15 | p1 | ناقص] نوشته: تعداد دسته برای یک نوشته — مدل فقط یک `category_id` دارد در حالی که وردپ | — |
| 16 | p1 | ناقص] نوشته: ذخیره‌ی خودکار و قفل ویرایش فقط برای نوشته — برای صفحات CMS و ورودی‌های  | — |
| 17 | p1 | ناقص] نوشته: تصاحب قفل ویرایش (take over) — هشدار «کاربر دیگر در حال ویرایش» هست ولی  | ✅ frontend/lib/api/blog.ts |
| 18 | p1 | ناقص] نوشته: شمارش دیدگاه در فهرست ادمین — ستون «دیدگاه‌ها» همیشه صفر است چون `commen | ✅ backend/app/modules/blog/application/comment_ser |
| 19 | p1 | نداریم] انواع پست سفارشی: آرشیو و تک‌صفحه‌ی عمومی CPT — مسیر `GET /content-types/{slu | ✅ frontend/app/admin/blog/page.tsx |
| 20 | p1 | ناقص] انواع پست سفارشی: پرچم‌های `supports_categories`/`supports_comments` بی‌اثر — ف | ✅ backend/app/modules/blog/application/comment_ser |
| 21 | p1 | ناقص] انواع پست سفارشی: فیلدهای دلخواه به‌صورت فرم — صفحه‌ی `content-types` فرم پویا  | ✅ frontend/components/admin/blog/content-types-tab |
| 22 | p1 | ناقص] انواع پست سفارشی: ریویژن و زمان‌بندی انتشار — `CustomPostEntry` نه revision دار | ✅ backend/app/modules/blog/domain/custom_post_type |
| 23 | p1 | ناقص] انواع پست سفارشی: سطل زماله و بازیابی — ورودی‌های CPT فقط status دارند و مسیر t | ✅ backend/app/modules/content/application/entry_re |
| 24 | p1 | ناقص] انواع پست سفارشی: دیدگاه روی ورودی — `COMMENT_RESOURCE_TYPES` فقط `blog_post` و | ✅ backend/app/modules/blog/domain/models.py |
| 25 | p1 | ناقص] برگه‌ها: سلسله‌مراتب و ترتیب — `parent_id` و `menu_order` در مدل و schema هستند | ✅ frontend/app/admin/pages/page.tsx |
| 26 | p1 | ناقص] برگه‌ها: چرخه‌ی وضعیت و دید — صفحه حالت «در انتظار بررسی»، خصوصی و رمزدار ندارد | ✅ backend/app/modules/content/domain/models.py |
| 27 | p1 | ناقص] برگه‌ها: کلید `allow_comments` و حریم خصوصی — برگه‌ها هیچ‌کدام را ندارند، پس دی | ✅ backend/app/modules/content/domain/models.py |
| 28 | p1 | ناقص] برگه‌ها: تصویر شاخص — مدل `CmsPage` هیچ ستون کاور/featured ندارد در حالی که مدل | ✅ backend/app/modules/content/domain/models.py |
| 29 | p1 | ناقص] برگه‌ها: اعتبارسنجی زنده‌ی نامک — تداخل نامک فقط سمت سرور یکتا می‌شود و UI خطای | ✅ frontend/app/admin/pages/page.tsx |
| 30 | p1 | ناقص] تاکسونومی: انتساب ترم به نوشته از UI — `attachToPost` در کلاینت تعریف شده ولی ه | ✅ frontend/app/admin/media/page.tsx |
| 31 | p1 | ناقص] تاکسونومی: آرشیو عمومی ترم سفارشی — مسیر `GET /blog/taxonomies/{slug}/terms` هس | ✅ frontend/app/admin/blog/page.tsx |
| 32 | p1 | ناقص] تاکسونومی: ویرایش ترم/دسته از UI — فرم فقط `name` را می‌فرستد و فیلدهای `slug`، | ✅ frontend/components/admin/blog/taxonomies-tab.ts |
| 33 | p1 | ناقص] تاکسونومی: حذف ترم و ویرایش/حذف خود تاکسونومی — `updateTerm`/`removeTerm` و API | ✅ frontend/components/admin/blog/taxonomies-tab.ts |
| 34 | p1 | ناقص] تاکسونومی: نمایش سلسله‌مراتب ترم در UI — مدل و API `hierarchical` + `parent_id` | ✅ frontend/components/admin/admin-telemetry-badge. |
| 35 | p1 | ناقص] تاکسونومی: جست‌وجوی ترم در انتخابگر — فهرست ترم بدون پارامتر `search` برگردانده | ✅ backend/app/modules/blog/api/wp_parity_routes.py |
| 36 | p1 | ناقص] تاکسونومی: مقید کردن تاکسونومی به انواع محتوا (`object_types`) — چنین اتصالی در | ✅ backend/app/modules/blog/domain/taxonomy_models. |
| 37 | p1 | نداریم] کامنت: ویرایش متن کامنت از پنل — route `PATCH /admin/blog/comments/{id}` و کل | ✅ frontend/components/admin/blog/comments-moderati |
| 38 | p1 | ناقص] کامنت: لغو تأیید (unapprove) و ویرایش فیلدهای نویسنده — API ویرایش فقط `content | ✅ frontend/components/admin/blog/comments-moderati |
| 39 | p1 | ناقص] کامنت: سطل زباله — وضعیت `CommentStatus.TRASH` در enum هست ولی هیچ کدی آن را نم | ✅ backend/app/modules/blog/application/comment_ser |
| 40 | p1 | ناقص] کامنت: نمایش IP و URL نویسنده در پنل — `author_ip` ذخیره می‌شود ولی در پاسخ ادم | ✅ frontend/components/admin/blog/comments-moderati |
| 41 | p1 | ناقص] کامنت: عملیات گروهی — تأیید/اسپم/حذف فقط تک‌ردیفی است و انتخاب چندتایی وجود ندا | ✅ frontend/components/admin/blog/comments-moderati |
| 42 | p1 | ناقص] کامنت: جست‌وجوی متنی در دیدگاه‌ها — نه پارامتر `search` در پاسخ ادمین هست نه جس | ✅ backend/app/modules/blog/application/comment_ser |
| 43 | p1 | ناقص] کامنت: صفحه‌بندی فهرست مدیریت — فقط ۵۰ مورد اول نمایش داده می‌شود و pager ندارد | ✅ frontend/components/admin/blog/comments-moderati |
| 44 | p1 | ناقص] کامنت: لیست کلیدواژه‌های تعدیل و کنترل سیل — بک‌اند `moderation_keys`/`disallow | ✅ frontend/components/admin/content-settings-card. |
| 45 | p1 | ناقص] کامنت: گزینه‌های اعلان — تنظیم `comments_notify`/`moderation_notify` وجود ندارد | ✅ backend/app/modules/blog/application/comment_ser |
| 46 | p1 | ناقص] کامنت: لینک تأیید/رد یک‌کلیکی در ایمیل مدیر — اعلان کامنت فقط رویداد outbox می‌ | ✅ backend/app/modules/blog/api/routes.py |
| 47 | p1 | ناقص] کامنت: پاسخ‌دهی با ایمیل — ایمیل اعلان دیدگاه هدر `Reply-To` ندارد — شاهد: جست‌ | ✅ backend/app/modules/notifications/application/em |
| 48 | p1 | ناقص] کامنت: محدودیت نرخ دیدگاه — فقط flood ۱۵ ثانیه‌ای هست و سقف «چند دیدگاه در دقیق | ✅ backend/app/modules/blog/application/comment_ser |
| 49 | p1 | ناقص] کامنت: سرویس اسپم بیرونی (Akismet) — فقط امتیازدهی heuristic داخلی هست و اتصال  | — |
| 50 | p1 | نداریم] کامنت: بستن خودکار دیدگاه‌های قدیمی (`close_comments_for_old_posts`) — جست‌وج | ✅ backend/app/modules/blog/application/comment_ser |
| 51 | p1 | نداریم] کامنت: الزام نام/ایمیل برای دیدگاه مهمان (`require_name_email`) — کامنت بدون  | ✅ backend/app/modules/blog/application/comment_ser |
| 52 | p1 | نداریم] کامنت: تأیید خودکار دیدگاه‌دهنده‌ی قبلاً تأییدشده (`comment_previously_approv | ✅ backend/app/modules/blog/application/comment_ser |
| 53 | p1 | نداریم] کامنت: لیست سفید کامنت‌های قبلی — کامنت دوم به‌طور خودکار تأیید نمی‌شود — شاه | ✅ backend/app/modules/blog/application/comment_ser |
| 54 | p1 | نداریم] کامنت: ترتیب و صفحه‌بندی قابل تنظیم (`comment_order`/`default_comments_page`) | ✅ backend/app/modules/blog/application/comment_ser |
| 55 | p1 | نداریم] کامنت: شمارنده‌ی دیدگاه‌های در انتظار در منوی ادمین — بَدج تعداد در انتظار (ح | ✅ frontend/app/admin/layout.tsx |
| 56 | p1 | نداریم] کامنت: میانبرهای صفحه‌کلید مدیریت دیدگاه (approve/unapprove/spam/trash/delete | ✅ frontend/components/admin/blog/comments-moderati |
| 57 | p1-help/2 | نداریم] مدیا: جایگزینی فایل با حفظ URL (Replace Media) — جست‌وجوی `replace_media/repl | ✅ backend/app/modules/media/api/routes.py |
| 58 | p1-help/2 | نداریم] مدیا: سایدلود تصویر از URL در UI — route `POST /media/sideload` با گارد SSRF  | ✅ frontend/app/admin/media/page.tsx |
| 59 | p1-help/2 | نداریم] مدیا: فیلد Title رسانه — فقط alt/caption/description هست و نه فیلد عنوان در م | — |
| 60 | p1-help/2 | نداریم] مدیا: فیلتر «پیوست‌نشده» (Unattached) — پارامترهای `list_media` فقط mime/fold | ✅ backend/app/modules/media/api/routes.py |
| 61 | p1-help/2 | نداریم] مدیا: پیش‌نمایش PDF — برای PDF تصویر پیش‌نمایش ساخته نمی‌شود و فقط فایل ذخیره | — |
| 62 | p1-help/2 | نداریم] مدیا: آستانه‌ی تصویر بزرگ (Big Image Threshold) — تصاویر بالای ۲۵۶۰px هنگام آ | ✅ backend/app/modules/media/application/media_serv |
| 63 | p1-help/2 | ناقص] مدیا: اتصال به نوشته — ستون `post_id` روی مدل هست ولی هیچ کدی آن را نمی‌نویسد و | ✅ backend/app/modules/media/application/media_serv |
| 64 | p1-help/2 | ناقص] مدیا: برش با نسبت آماده — crop هست ولی preset نسبت (thumbnail/medium/large) ندا | ✅ frontend/app/admin/media/page.tsx |
| 65 | p1-help/2 | ناقص] مدیا: نمای فهرستی و فیلتر تاریخ — کتابخانه فقط نمای شبکه با فیلتر mime/پوشه/جست | ✅ frontend/app/admin/media/page.tsx |
| 66 | p1-help/2 | ناقص] مدیا: ساخت پوشه از UI — انتقال گروهی با `prompt` مسیر مقصد انجام می‌شود و دکمه‌ | ✅ frontend/app/admin/media/page.tsx |
| 67 | p1-help/2 | ناقص] مدیا: واترمارک — سرویس و کلیدهای `media_watermark_*` در بک‌اند فعال‌اند ولی هیچ | ✅ frontend/components/admin/watermark-settings-car |
| 68 | p1-help/2 | ناقص] مدیا: اندازه‌های تصویر سفارشی (`add_image_size`) — فقط ۴ اندازه‌ی ثابت وجود دار | ✅ backend/app/modules/media/application/image_proc |
| 69 | p1-help/2 | ناقص] مدیا: فهرست کانال‌های oEmbed — فقط ۴ ارائه‌دهنده (YouTube/Aparat/Twitter/Instag | ✅ backend/app/modules/content/application/embed_se |
| 70 | p1-help/2 | نداریم] کاربران: حذف/بازگردانی کاربر از UI — مسیرهای soft-delete/restore و کلاینت `de | ✅ frontend/.next/cache/webpack/client-production/0 |
| 71 | p1-help/2 | نداریم] کاربران: نام نمایشی/نام مستعار (Display Name / Nickname) — فیلد یا UI وجود ند | — |
| 72 | p1-help/2 | نداریم] کاربران: عملیات گروهی (bulk) — لیست کاربران بدون multi-select است و تغییر نقش | ✅ frontend/app/admin/users/page.tsx |
| 73 | p1-help/2 | نداریم] کاربران: کنترل باز/بسته بودن ثبت‌نام و نقش پیش‌فرض — ثبت‌نام همیشه باز است و  | ✅ backend/app/modules/auth/application/auth_servic |
| 74 | p1-help/2 | نداریم] کاربران: نشانگر قدرت رمز — فقط نمایش/مخفی‌کردن رمز هست و سنجه‌ی زنده‌ی قدرت و | ✅ frontend/.next/cache/webpack/client-production/0 |
| 75 | p1-help/2 | نداریم] کاربران: تأیید حساب توسط مدیر — ثبت‌نام بلافاصله توکن می‌دهد و وضعیت «در انتظ | — |
| 76 | p1-help/2 | نداریم] کاربران: مدیریت نشست‌های دیگر کاربران از پنل — «خروج از همه دستگاه‌ها» فقط se | ✅ frontend/app/admin/users/page.tsx |
| 77 | p1-help/2 | نداریم] کاربران: تغییر ایمیل مدیریتی با تأییدیه و بازبینی دوره‌ای — جریان `new_admin_ | ✅ backend/app/modules/users/application/email_chan |
| 78 | p1-help/2 | نداریم] کاربران: ورود و ثبت‌نام با ایمیل — احراز هویت فقط با شماره‌ی موبایل است و `Re | ✅ backend/app/modules/auth/application/auth_servic |
| 79 | p1-help/2 | نداریم] کاربران: «مرا به خاطر بسپار» — هیچ چک‌باکس و منطق نشست بلندمدتی نیست و طول عم | — |
| 80 | p1-help/2 | ناقص] کاربران: آواتار سفارشی — فیلد `avatar_url` در مدل و `PATCH /auth/me` هست ولی هی | — |
| 81 | p1-help/2 | ناقص] کاربران: ساخت کاربر توسط ادمین — دیالوگ هست ولی فیلد نقش ندارد (نقش‌دهی جدا و ب | ✅ frontend/components/admin/users/user-dialog.tsx |
| 82 | p1-help/2 | ناقص] کاربران: فیلتر نقش در فهرست کاربران سمت سرور نیست و کلاینت‌ساید روی صفحه‌ی جاری | ✅ backend/app/modules/users/api/routes.py |
| 83 | p1-help/2 | ناقص] کاربران: تأیید ایمیل هنگام ثبت‌نام — ستون `is_verified` هست ولی هیچ ایمیل تأیید | ✅ backend/app/modules/auth/application/auth_servic |
| 84 | p1-help/2 | ناقص] کاربران: ساخت خودکار `author_slug` — فقط یک‌بار در migration پر شده و برای کارب | ✅ backend/app/modules/auth/application/auth_servic |
| 85 | p1-help/2 | ناقص] کاربران: پاسکی — route چالش تصادفی هست ولی verify و ذخیره‌ی اعتبارنامه ندارد و  | ✅ backend/app/modules/auth/api/routes.py |
| 86 | p1-help/2 | ناقص] ویجت: انواع ویجت — ۱۰ نوع داریم (text/recent_posts/categories/tags/search/menu/ | ✅ backend/app/shared/content/widgets.py |
| 87 | p1-help/2 | ناقص] ویجت: تنظیمات هر ویجت — فرم فقط `title`/`content` دارد و هیچ فرم اختصاصی برای ت | ✅ frontend/app/admin/widgets/page.tsx |
| 88 | p1-help/2 | ناقص] ویجت: نواحی و چیدمان — نواحی در کد ثابت‌اند (header_top/footer_1..3/sidebar)، ن | ✅ backend/app/modules/settings/api/routes.py |
| 89 | p1-help/2 | ناقص] منو: آیتم‌ها فقط لینک سفارشی — مدل فقط `title+url` دارد و انتخابگر صفحه/دسته/بر | ✅ backend/app/modules/content/api/routes.py |
| 90 | p1-help/2 | ناقص] منو: مکان‌های منو ثابت (۵ مقدار enum) — افزودن/حذف مکان و ساخت چند منو و تخصیص  | ✅ backend/app/modules/content/api/routes.py |
| 91 | p1-help/2 | نداریم] تنظیمات: گزینه‌های آواتار سراسری (`show_avatars`/`avatar_default`/`avatar_rat | ✅ backend/app/modules/blog/application/comment_ser |
| 92 | p1-help/2 | نداریم] تنظیمات: robots.txt مجازی با دستور قالب — robots ما فایل Next است ولی هیچ کنت | ✅ frontend/app/robots.txt/route.ts |
| 93 | p1-help/2 | ناقص] تنظیمات: ساختار پیوند یکتا — ۵ پریست و ورودی آزاد با اعتبارسنجی داریم ولی URLها | — |
| 94 | p1-help/2 | ناقص] تنظیمات: تب‌بندی تنظیمات — صفحه‌ی تنظیمات یک صفحه‌ی بلند بدون گروه‌بندی General | — |
| 95 | p1-help/2 | نداریم] ابزارها: ایمپورتر WXR (ورود از وردپرس با XML) — هیچ پارسر WXR/XML وجود ندارد  | — |
| 96 | p1-help/2 | ناقص] ابزارها: اکسپورت بلاگ ناقص — خروجی دیدگاه‌ها را شامل نمی‌شود (خود سرویس صریحاً  | — |
| 97 | p1-help/2 | ناقص] ابزارها: ایمپورت JSON رسانه را نمی‌آورد — فقط متن/متادیتا وارد می‌شود و فایل‌ها | ✅ backend/app/modules/blog/application/transfer_se |
| 98 | p1-help/2 | ناقص] ابزارها: حالت بازیابی — صفحه‌ی pause و ازسرگیری هست ولی ایمیل دعوت با لینک بازی | ✅ backend/app/core/exceptions/handlers.py |
| 99 | p1-help/2 | ناقص] ابزارها: کرون — Celery beat معادل wp-cron هست ولی صفحه‌ی «رویدادهای زمان‌بندی‌ش | ✅ frontend/app/admin/blog/page.tsx |
| 100 | p1-help/2 | ناقص] فید: دو مسیر موازی سایت‌مپ — Next.js `/sitemap.xml` و بک‌اند `/content/sitemap. | ✅ frontend/app/(store)/blog/category/[slug]/page.t |
| 101 | p1-help/2 | ناقص] فید: discovery کامل oEmbed — لینک `text/json+oembed` فقط در layout ریشه تزریق م | ✅ frontend/app/layout.tsx |
| 102 | p1-help/2 | ناقص] حریم خصوصی: خروجی داده کاربر — رجیستری ۴۵ منبع و route ادمین و self-service کار | ✅ backend/app/modules/settings/application/privacy |
| 103 | p1-help/2 | ناقص] حریم خصوصی: سیاست نگه‌داشت — صف پاکسازی و `purge-expired` هست ولی مدت نگه‌داشت  | ✅ backend/app/modules/settings/application/default |
| 104 | p1-help/2 | ناقص] حریم خصوصی: انتخابگر صفحه‌ی سیاست — به اسلاگ ثابت `privacy` وصل است و `wp_page_ | ✅ backend/app/modules/settings/application/default |
| 105 | p1-help/2 | ناقص] حریم خصوصی: جریان ایمیلی تأیید درخواست — درخواست‌ها فقط از داخل نشست کاربر ثبت  | ✅ backend/app/modules/settings/application/privacy |
| 106 | p1-help/2 | ناقص] Site Health: پوشش آزمون‌های هسته — ۱۱ تا ۱۳ بررسی داریم در برابر ده‌ها تست وردپ | ✅ 9 |
| 107 | p1-help/2 | ناقص] Site Health: چک «آیا سایت می‌تواند ایمیل بفرستد؟» — تست SMTP فقط در صفحه‌ی تنظی | ✅ backend/app/modules/settings/application/site_he |
| 108 | p1-help/2 | ناقص] دسترس‌پذیری: آزمون خودکار — `@axe-core/playwright` نصب است ولی هیچ فایل آزمونی  | ✅ frontend/node_modules/@axe-core/playwright/dist/ |
