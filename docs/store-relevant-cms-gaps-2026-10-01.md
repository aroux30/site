# کمبودهای CMS که برای یک فروشگاه اینترنتی مهم‌اند

فیلترشده از `docs/wordpress-cms-gaps-2026-10-01.md` (264 آیتم). معیار: آیا این قابلیت روی فروش، تجربه‌ی مشتری، کار روزمره‌ی ادمین، SEO یا ریسک حقوقی فروشگاه اثر می‌گذارد.

| اولویت | تعداد | معنی |
| --- | --- | --- |
| **P0** | 28 | مشتری / درآمد / قانون / امنیت |
| **P1** | 108 | کار روزمره‌ی ادمین را متوقف می‌کند |
| **P2** | 25 | SEO، تبدیل کاربر، رشد |
| **بی‌ربط** | 103 | مخصوص CMS وردپرس یا خارج از دامنه — پیاده‌سازی نشود |

**جمع: 264 آیتم — 161 مرتبط، 103 بی‌ربط.**

## P0 — مشتری، درآمد، قانون یا امنیت (28)

کاری که همین الان روی فروش، اعتماد مشتری یا ریسک حقوقی اثر می‌گذارد.

### نوشته، گردش ویرایش و ریویژن
- [ناقص] نوشته: صفحه‌بندی فهرست نوشته‌های ادمین — فقط ۵۰ ردیف اول بارگذاری می‌شود و صفحه‌بندی DataTable فقط روی همان ۵۰ ردیف محلی است، پس نوشته‌های بعدی قابل مرور نیستند — شاهد: `frontend/app/admin/blog/page.tsx:180` (`page_size: 50` بدون پارامتر `page`)
- [ناقص] نوشته: نشت نوشته‌ی خصوصی از مسیر جزئیات — `get_post_by_slug` فقط `status` را فیلتر می‌کند نه `visibility`، پس بدنه‌ی کامل پست خصوصی با URL مستقیم به هر بازدیدکننده سرو می‌شود — شاهد: `backend/app/modules/blog/application/blog_service.py:1096-1113` در برابر فیلترهای `:1260`, `:1373`, `feed_service.py:150`
### کامنت‌ها
- [ناقص] کامنت: صفحه‌بندی دیدگاه در فروشگاه — API صفحه‌بندی کامل دارد ولی UI فقط صفحه‌ی اول را می‌خواند و دکمه‌ی «بیشتر» ندارد — شاهد: `frontend/components/blog/blog-comments.tsx:58-63` در برابر `frontend/lib/api/blog.ts:194-206`
- [ناقص] کامنت: دیدگاه روی صفحات CMS — بک‌اند کامنت پلی‌مورفیک برای صفحه را کامل پشتیبانی می‌کند ولی هیچ صفحه‌ای در فروشگاه کامنت رندر نمی‌کند و پاسخ ادمین برای دیدگاه صفحه خراب است — شاهد: `backend/app/modules/blog/application/comment_service.py:145-173`؛ `submitPostComment(replyTarget.post_id)` در `comments-moderation-tab.tsx`؛ جست‌وجوی `comment` در `frontend/components/cms/cms-page-shell.tsx` بی‌نتیجه
### مدیا و کتابخانه‌ی رسانه
- [نداریم] مدیا: سطل زباله — حذف مدیا مستقیم و دائمی است (رکورد و فایل‌ها با هم پاک می‌شوند) و ستون `deleted_at` در مدل نیست — شاهد: `backend/app/modules/media/application/media_service.py:867-892`؛ `backend/app/modules/media/domain/models.py`
- [نداریم] مدیا: تصاویر واکنش‌گرا (srcset) در محتوا — تصویر درج‌شده در بدنه با یک URL ثابت رندر می‌شود و srcset تولید نمی‌شود — شاهد: جست‌وجوی `srcset|srcSet` در `frontend/app` و `frontend/components` بی‌نتیجه (فقط next/image برای بخش‌های UI)
- [نداریم] مدیا: آپلود کشیدن‌ورهاکردن (Drag & Drop) — فقط انتخاب فایل از دیالوگ هست — شاهد: جست‌وجوی `onDrop|dropzone|drag` در `frontend/components` و `frontend/app/admin/media` بی‌نتیجه
- [ناقص] مدیا: حذف گروهی در کتابخانه — فقط «انتقال به پوشه» برای انتخاب‌شده‌ها هست — شاهد: `frontend/app/admin/media/page.tsx:246-261` (`moveSelected`)
- [ناقص] مدیا: هشدار استفاده پیش از حذف — شمارش «این تصویر در N نوشته/محصول استفاده شده» قبل از حذف بررسی نمی‌شود — شاهد: `backend/app/modules/media/api/routes.py:347`
### کاربران، نقش‌ها و کپابیلیتی‌ها
- [نداریم] کاربران: UI انتساب نقش به کاربر — route‌های `/rbac/admin/users/{id}/roles` و کلاینت `assignUserRoles` هست ولی هیچ صفحه‌ای آن را مصرف نمی‌کند و دیالوگ کاربر فیلد نقش ندارد — شاهد: `frontend/lib/api/rbac.ts:176-190` (بدون caller)؛ `frontend/components/admin/users/user-dialog.tsx:27-38`
- [نداریم] کاربران: ارسال لینک بازنشانی رمز توسط ادمین — `AdminUserUpdate` فیلد password ندارد و هیچ route رمز در ماژول users نیست — شاهد: `backend/app/modules/users/schemas/user.py:169`؛ جست‌وجوی `reset` در `backend/app/modules/users/api/routes.py` بی‌نتیجه — در WP: `wp-admin/user-edit.php:749`
- [نداریم] کاربران: حذف کاربر با واگذاری محتوا (Reassign) — حذف فقط نرم است و `author_id` با `SET NULL` بی‌مالک می‌ماند — شاهد: `backend/app/modules/users/application/user_service.py:335`؛ `backend/app/modules/blog/domain/models.py:145`؛ جست‌وجوی `reassign` در `backend/app/modules/users` بی‌نتیجه
- [نداریم] کاربران: ایمیل خوش‌آمد ثبت‌نام و اطلاع به مدیر — `register()` هیچ ایمیلی به کاربر یا مدیر نمی‌فرستد — شاهد: `backend/app/modules/auth/application/auth_service.py:192-300` (بدون `send_email`)
- [نداریم] کاربران: ایمیل اطلاع تغییر رمز عبور — فقط `log_action` ثبت می‌شود و ایمیلی ارسال نمی‌شود — شاهد: `backend/app/modules/auth/application/auth_service.py:905-925` — در WP: `wp_password_change_notification`
- [ناقص] کاربران: محافظت «آخرین ادمین» — guard خود/سوپریوزر هست ولی منطق اختصاصی آخرین ادمین ندارد — شاهد: `backend/app/modules/users/application/user_service.py:236-250`
### ویجت‌ها، منوها و داشبورد
- [ناقص] ویجت: رندر `custom_html` — به‌صورت متن ساده رندر می‌شود نه HTML — شاهد: `frontend/components/layout/widget-area.tsx:42-52` («Rendered as text, not markup»)
### تنظیمات
- [نداریم] تنظیمات: انتخاب صفحه‌ی نخست (`show_on_front`/`page_on_front`) — بک‌اند کامل پیاده شده و صفحه‌ی اصلی مصرفش می‌کند ولی هیچ فیلد UI برای انتخاب «نوشته‌ها یا برگه‌ی ثابت» نیست — شاهد: `backend/app/modules/settings/api/routes.py:1240-1275`؛ جست‌وجوی `show_on_front|page_on_front` در `frontend/app/admin` بی‌نتیجه
- [نداریم] تنظیمات: نام سایت، توضیح سایت و ایمیل ادمین از UI — `blogname`/`blogdescription`/`admin_email` seed شده و خوانده می‌شوند ولی هیچ فیلد ویرایشی ندارند — شاهد: `backend/app/modules/settings/application/default_options.py:24-41`؛ جست‌وجوی `blogname|admin_email` در `frontend/app/admin` بی‌نتیجه
- [نداریم] تنظیمات: نمایش/پنهان‌سازی سایت از موتورهای جست‌وجو — کلید `blog_public` خوانده می‌شود ولی کنترلی برای تغییرش در پنل نیست — شاهد: جست‌وجوی `blog_public` در `frontend/app/admin` بی‌نتیجه (فقط `robots.ts` و `permalinks.ts` آن را می‌خوانند)
- [ناقص] تنظیمات: مشخصات فروشگاه — فرم `store.identity/store.support` ذخیره می‌کند ولی هیچ مصرف‌کننده‌ای آن را نمی‌خواند، پس نام فروشگاه اعمال نمی‌شود در حالی که فید/سایت‌مپ `blogname` ثابت را می‌خوانند — شاهد: `frontend/app/admin/settings/page.tsx:125-131,487-500`؛ جست‌وجوی `store.identity|store_name` بیرون از همان صفحه بی‌نتیجه
### ابزارها، ایمپورت/اکسپورت و به‌روزرسانی
- [نداریم] ابزارها: حالت نگهداری (Maintenance Mode) — صفحه‌ی «چند لحظه دیگر برمی‌گردیم» و فایل `.maintenance` معادلی ندارد — شاهد: جست‌وجوی `maintenance mode|.maintenance` بی‌نتیجه — در WP: `wp-admin/includes/update-core.php:1306-1327`
### REST API، فید، سایت‌مپ و پروتکل‌ها
- [ناقص] فید: پوشش CPT و نویسنده در سایت‌مپ — سایت‌مپ Next.js فقط routes/posts/categories/tags/products/pages را می‌سازد و آرشیوهای نویسنده/تاریخ و محتوای CPT در آن نیست — شاهد: `frontend/app/sitemap.ts:81-190`؛ `backend/app/modules/content/application/sitemap_index_service.py:19`
- [ناقص] فید: نگاشت تصاویر و `lastmod` دقیق در سایت‌مپ — معادل `wp-sitemaps` وجود ندارد — شاهد: `backend/app/modules/content/application/sitemap_index_service.py:19`
### حریم خصوصی، GDPR و امنیت
- [نداریم] حریم خصوصی: حذف خودکار داده‌های منقضی — route `purge-expired` هست ولی هیچ تسک زمان‌بندی‌شده‌ای آن را صدا نمی‌زند — شاهد: جست‌وجوی `purge_expired` در `backend/app/worker/celery_app.py` بی‌نتیجه
- [ناقص] حریم خصوصی: پوشش دیدگاه‌های مهمان — خروجی/پاک‌سازی فقط `author_id` را می‌بیند و دیدگاه مهمان که فقط ایمیل دارد پوشش داده نمی‌شود — شاهد: `backend/app/modules/settings/application/privacy_service.py:111-128`
- [ناقص] حریم خصوصی: نگه‌داشت IP دیدگاه — IP ذخیره می‌شود ولی ماسک یا انقضای زمان‌بندی‌شده ندارد — شاهد: `author_ip` در `backend/app/modules/blog/domain/models.py:422`
- [ناقص] حریم خصوصی: اطلاع‌رسانی حریم خصوصی در فرم‌ها — متن رضایت‌نامه‌ی قابل ویرایش از تنظیمات به فرم ثبت‌نام/سفارش/دیدگاه تزریق نمی‌شود — شاهد: جست‌وجوی `privacy` در `frontend/app/(store)/register/page.tsx` و `frontend/components/blog/blog-comments.tsx` بی‌نتیجه
### ایمیل
- [ناقص] ایمیل: نام فروشگاه در ایمیل‌ها — قالب‌های پیش‌فرض «فروشگاه اینترنتی» را هاردکد پاس می‌دهند — شاهد: `backend/app/modules/notifications/application/email_service.py:447`

## P1 — کار روزمره‌ی ادمین را متوقف می‌کند (108)

بدون این‌ها ادمین نمی‌تواند محتوا، کامنت، رسانه یا کاربر را واقعاً مدیریت کند.

### ادیتور، بلاک و الگوها
- [ناقص] ادیتور و بلاک: نوار ابزار ادیتور — فقط bold/italic/H2/ul/ol/link/oEmbed؛ نقل‌قول، کد، جدول، خط جداکننده، ترازبندی، رنگ متن، undo/redo، شمارش کلمه و حالت تمام‌صفحه غایب است — شاهد: فهرست دکمه‌ها در `frontend/components/admin/RichBodyEditor.tsx:131-155`
- [ناقص] ادیتور و بلاک: درج تصویر/رسانه از کتابخانه در بدنه — `MediaPicker` فقط برای تصویر شاخص است و نوار ابزار دکمه‌ی درج ندارد؛ تصویر فقط با HTML دستی درج می‌شود — شاهد: `frontend/components/admin/RichBodyEditor.tsx`؛ `frontend/app/admin/blog/page.tsx:1077` (MediaPicker فقط برای کاور)
- [ناقص] ادیتور و بلاک: شورت‌کدها — ۶ شورت‌کد (`gallery/youtube/aparat/button/alert/embed`) داریم ولی `caption`، `audio`، `video` و `playlist` وردپرسی غایب‌اند و هیچ API ثبت شورت‌کد برای توسعه‌دهنده نیست — شاهد: `backend/app/shared/content/shortcodes.py:151-289`؛ در WP: `wp-includes/media.php:2597-4005`
### نوشته، گردش ویرایش و ریویژن
- [ناقص] نوشته: تغییر نویسنده — `author_id` فقط در `BlogPostCreate` هست و در `BlogPostUpdate` نیست و هیچ انتخابگر نویسنده‌ای در ویرایشگر یا ویرایش سریع وجود ندارد — شاهد: `backend/app/modules/blog/schemas/blog.py:131` در برابر `:165-189`؛ `frontend/components/admin/blog/quick-edit-dialog.tsx:44-53`
- [ناقص] نوشته: پیش‌نمایش پیش‌نویس — دکمه «پیش‌نمایش در سایت» به URL عمومی لینک می‌دهد که برای پیش‌نویس ۴۰۴ می‌شود و route `previewPost` هیچ مصرف‌کننده‌ای ندارد — شاهد: `frontend/app/admin/blog/page.tsx:1014-1020`؛ `frontend/lib/api/blog.ts:334` (بدون caller)
- [ناقص] نوشته: پیش‌نمایش برگه — دکمه‌ی پیش‌نمایش به JSON خام API باز می‌شود نه صفحه‌ی رندرشده — شاهد: `frontend/app/admin/pages/page.tsx:380-388`
- [ناقص] نوشته: مقایسه‌ی ریویژن‌ها (Diff) — route دیف کلمه‌به‌کلمه در بک‌اند هست ولی UI فقط فهرست و بازگردانی نشان می‌دهد — شاهد: `backend/app/modules/blog/application/revision_diff_service.py`؛ `backend/app/modules/blog/api/routes.py:1429`؛ جست‌وجوی `diff` در `frontend/lib/api/blog.ts` و `frontend/app/admin/blog/page.tsx` بی‌نتیجه
- [ناقص] نوشته: سقف و هرس ریویژن (`WP_POST_REVISIONS`) — هیچ تنظیم تعداد یا حذف ریویژن قدیمی نیست و شماره فقط افزایشی است — شاهد: جست‌وجوی `MAX_REVISIONS|revision_limit|prune.*revision` در `backend/app` بی‌نتیجه؛ `backend/app/modules/blog/application/blog_service.py:407-465`
- [ناقص] نوشته: فیلترهای فهرست نوشته‌ها — فیلتر نویسنده و بازه‌ی زمانی (dropdown ماه/سال) نه در UI هست نه در پارامترهای API — شاهد: `frontend/app/admin/blog/page.tsx:97-175`؛ `backend/app/modules/blog/api/routes.py:826-850` (فقط category/status/search/sort)
- [ناقص] نوشته: ویرایش گروهی فیلدها (Bulk Edit) — اکشن‌های گروهی فقط publish/draft/archive/trash/restore است و تغییر گروهی دسته/برچ标签/نویسنده/فرمت/تاریخ وجود ندارد — شاهد: `backend/app/modules/blog/application/blog_service.py:1554`؛ `backend/app/modules/blog/api/routes.py:1930`
- [ناقص] نوشته: ویرایش سریع ناقص — Quick Edit دارد ولی نویسنده، فرمت و وضعیت «دیدگاه‌ها باز» در آن نیست و برای برگه‌های CMS هیچ معادلی ندارد — شاهد: `frontend/components/admin/blog/quick-edit-dialog.tsx:44-53`؛ نبود quick edit در `frontend/app/admin/pages/page.tsx`
- [ناقص] نوشته: تاریخ انتشار گذشته — `published_at` در schema به‌روزرسانی هست ولی هیچ فیلد UI آن را نمی‌فرستد و فقط زمان‌بندی آینده دارد — شاهد: `backend/app/modules/blog/schemas/blog.py:177`؛ جست‌وجوی `published_at` در `frontend/app/admin/blog/page.tsx` بی‌نتیجه
- [ناقص] نوشته: نوشته‌ی ویژه (sticky) — سنجاق در فرم و ترتیب «ویژه اول» اعمال می‌شود ولی toggle سریع در فهرست، فیلتر «فقط ویژه‌ها» و اکشن گروهی نیست — شاهد: `backend/app/modules/blog/application/blog_service.py:1291`؛ `frontend/app/admin/blog/page.tsx:654`
- [ناقص] نوشته: ریدایرکت نامک قدیمی (`wp_old_slug_redirect`) — تاریخچه ثبت می‌شود ولی `resolve_slug_redirect` هیچ فراخوانی در کل پروژه ندارد، پس آدرس قبلی ۴۰۴ می‌دهد — شاهد: `backend/app/modules/blog/application/slug_history_service.py:95` (جست‌وجوی تابع فقط همان فایل) و `record_slug_change` در `blog_service.py:956`
- [ناقص] نوشته: تعداد دسته برای یک نوشته — مدل فقط یک `category_id` دارد در حالی که وردپرس چند دسته‌ی همزمان می‌پذیرد — شاهد: `backend/app/modules/blog/domain/models.py:178-182`
- [ناقص] نوشته: ذخیره‌ی خودکار و قفل ویرایش فقط برای نوشته — برای صفحات CMS و ورودی‌های CPT هیچ autosave یا قفلی نیست — شاهد: `backend/app/modules/blog/application/autosave_service.py` و `post_lock_service.py` در برابر جست‌وجوی `autosave|lock` در `backend/app/modules/content` که بی‌نتیجه
- [ناقص] نوشته: تصاحب قفل ویرایش (take over) — هشدار «کاربر دیگر در حال ویرایش» هست ولی زمانسنج قفل و دکمه‌ی تصاحب در فهرست نیست — شاهد: `frontend/app/admin/blog/page.tsx:241,1024-1030`؛ `backend/app/modules/blog/application/post_lock_service.py`
- [ناقص] نوشته: شمارش دیدگاه در فهرست ادمین — ستون «دیدگاه‌ها» همیشه صفر است چون `comment_count=0` هاردکد شده و `get_comment_count` هیچ فراخوانی ندارد — شاهد: `backend/app/modules/blog/application/blog_service.py:274`؛ `comment_service.py:841`؛ `frontend/app/admin/blog/page.tsx:698`
### برگه‌ها (CMS Pages) و انواع پست سفارشی
- [نداریم] انواع پست سفارشی: آرشیو و تک‌صفحه‌ی عمومی CPT — مسیر `GET /content-types/{slug}/entries` در بک‌اند هست ولی هیچ صفحه‌ای در فرانت آن را مصرف نمی‌کند، پس ورودی منتشرشده در سایت قابل نمایش نیست — شاهد: `backend/app/modules/blog/api/wp_parity_routes.py:466-501`؛ جست‌وجوی `content-types` در `frontend/app/(store)` بی‌نتیجه
- [ناقص] انواع پست سفارشی: پرچم‌های `supports_categories`/`supports_comments` بی‌اثر — فقط ذخیره و serialize می‌شوند و هیچ منطقی آن‌ها را اعمال نمی‌کند — شاهد: `backend/app/modules/blog/domain/custom_post_types.py:66-70`؛ `backend/app/modules/blog/application/taxonomy_service.py:221-233`
- [ناقص] انواع پست سفارشی: فیلدهای دلخواه به‌صورت فرم — صفحه‌ی `content-types` فرم پویا دارد ولی در بلاگ فیلدها صرفاً JSON خام در textarea ذخیره می‌شوند — شاهد: `frontend/app/admin/content-types/page.tsx:100-114` در برابر `frontend/components/admin/blog/content-types-tab.tsx:260`
- [ناقص] انواع پست سفارشی: ریویژن و زمان‌بندی انتشار — `CustomPostEntry` نه revision دارد نه scheduled publish (در برابر ماژول content که هر دو را دارد) — شاهد: `backend/app/modules/blog/domain/custom_post_types.py:91-120`؛ جست‌وجوی `CustomPostEntry.*revision` بی‌نتیجه
- [ناقص] انواع پست سفارشی: سطل زماله و بازیابی — ورودی‌های CPT فقط status دارند و مسیر trash/restore در `wp_parity_routes` برایشان نیست — شاهد: `backend/app/modules/blog/api/wp_parity_routes.py:397-457` (فقط update/delete)
- [ناقص] انواع پست سفارشی: دیدگاه روی ورودی — `COMMENT_RESOURCE_TYPES` فقط `blog_post` و `cms_page` را می‌پذیرد، پس حتی با `supports_comments` هدف ثبت دیدگاه نیست — شاهد: `backend/app/modules/blog/domain/models.py:68-70`؛ `backend/app/modules/blog/schemas/blog.py:365`
- [ناقص] برگه‌ها: سلسله‌مراتب و ترتیب — `parent_id` و `menu_order` در مدل و schema هستند ولی فرم ادمین انتخابگر والد ندارد و مسیر عمومی `by-path` هیچ مصرف‌کننده‌ای ندارد — شاهد: `backend/app/modules/content/schemas/content.py:132,148,190`؛ `frontend/app/admin/pages/page.tsx:145-156`؛ جست‌وجوی `by-path|menu_order` در `frontend` بی‌نتیجه
- [ناقص] برگه‌ها: چرخه‌ی وضعیت و دید — صفحه حالت «در انتظار بررسی»، خصوصی و رمزدار ندارد (فقط draft/published/archived) — شاهد: `backend/app/modules/content/domain/models.py:142-145` در برابر `backend/app/modules/blog/domain/models.py:35,38`
- [ناقص] برگه‌ها: کلید `allow_comments` و حریم خصوصی — برگه‌ها هیچ‌کدام را ندارند، پس دیدگاه روی همه‌ی برگه‌های منتشرشده باز است — شاهد: `backend/app/modules/content/domain/models.py` (بدون این ستون‌ها) و `_ensure_page_accepts_comments` در `backend/app/modules/blog/application/comment_service.py`
- [ناقص] برگه‌ها: تصویر شاخص — مدل `CmsPage` هیچ ستون کاور/featured ندارد در حالی که مدل نوشته دارد — شاهد: کلاس `CmsPage` در `backend/app/modules/content/domain/models.py`
- [ناقص] برگه‌ها: اعتبارسنجی زنده‌ی نامک — تداخل نامک فقط سمت سرور یکتا می‌شود و UI خطای «نامک تکراری» را پیش از ارسال نشان نمی‌دهد — شاهد: `_ensure_unique_slug` در `backend/app/modules/content/application/cms_page_service.py:174`
### تاکسونومی، متا و فیلدهای دلخواه
- [ناقص] تاکسونومی: انتساب ترم به نوشته از UI — `attachToPost` در کلاینت تعریف شده ولی هیچ کامپوننتی آن را صدا نمی‌زند — شاهد: `frontend/lib/api/wp-parity.ts:128`؛ جست‌وجوی `attachToPost` در `frontend/app` و `frontend/components` بی‌نتیجه
- [ناقص] تاکسونومی: آرشیو عمومی ترم سفارشی — مسیر `GET /blog/taxonomies/{slug}/terms` هست ولی هیچ صفحه‌ی آرشیو یا نمایش ترمی در فرنت آن را مصرف نمی‌کند — شاهد: `backend/app/modules/blog/api/wp_parity_routes.py:504-536`؛ جست‌وجوی `taxonomies` در `frontend/app/(store)` بی‌نتیجه
- [ناقص] تاکسونومی: ویرایش ترم/دسته از UI — فرم فقط `name` را می‌فرستد و فیلدهای `slug`، توضیح و ترتیب را نمی‌فرستد، و `POST /categories/reorder` مصرف‌کننده ندارد — شاهد: `frontend/components/admin/blog/taxonomy-manager-tab.tsx:97-103` در برابر `backend/app/modules/blog/schemas/blog.py:520-546`
- [ناقص] تاکسونومی: حذف ترم و ویرایش/حذف خود تاکسونومی — `updateTerm`/`removeTerm` و API ویرایش تاکسونومی هست ولی تب ادمین فقط ساخت ترم را صدا می‌زند — شاهد: `frontend/lib/api/wp-parity.ts:99,117`؛ `frontend/components/admin/blog/taxonomies-tab.tsx`؛ `wp_parity_routes.py:212-263`
- [ناقص] تاکسونومی: نمایش سلسله‌مراتب ترم در UI — مدل و API `hierarchical` + `parent_id` دارند ولی فهرست ترم‌ها تخت است و فقط والد در فرم است — شاهد: `frontend/components/admin/blog/taxonomies-tab.tsx`؛ `backend/app/modules/blog/domain/taxonomy_models.py`
- [ناقص] تاکسونومی: جست‌وجوی ترم در انتخابگر — فهرست ترم بدون پارامتر `search` برگردانده می‌شود — شاهد: `GET /taxonomies/{taxonomy_id}/terms` در `backend/app/modules/blog/api/wp_parity_routes.py`
- [ناقص] تاکسونومی: مقید کردن تاکسونومی به انواع محتوا (`object_types`) — چنین اتصالی در مدل و UI نیست — شاهد: `backend/app/modules/blog/domain/taxonomy_models.py`؛ `frontend/components/admin/blog/taxonomies-tab.tsx`
### کامنت‌ها
- [نداریم] کامنت: ویرایش متن کامنت از پنل — route `PATCH /admin/blog/comments/{id}` و کلاینت `updateComment` هست ولی هیچ UI آن را صدا نمی‌زند — شاهد: `frontend/lib/api/blog.ts:385` (بدون caller)؛ `frontend/components/admin/blog/comments-moderation-tab.tsx`
- [ناقص] کامنت: لغو تأیید (unapprove) و ویرایش فیلدهای نویسنده — API ویرایش فقط `content` و `status` را می‌پذیرد (بدون نام/ایمیل/URL/تاریخ) و دکمه‌ی لغو تأیید در UI نیست — شاهد: `BlogCommentUpdate` در `backend/app/modules/blog/schemas/blog.py:383`
- [ناقص] کامنت: سطل زباله — وضعیت `CommentStatus.TRASH` در enum هست ولی هیچ کدی آن را نمی‌نویسد و خود UI صریحاً می‌گوید فیلترش حذف شده چون همیشه خالی می‌شد؛ حذف مستقیم و دائمی است — شاهد: `frontend/components/admin/blog/comments-moderation-tab.tsx:270-275`؛ `backend/app/modules/blog/application/comment_service.py:597-605`
- [ناقص] کامنت: نمایش IP و URL نویسنده در پنل — `author_ip` ذخیره می‌شود ولی در پاسخ ادمین برگردانده نمی‌شود و ستونی در جدول مدیریت ندارد — شاهد: `backend/app/modules/blog/domain/models.py:422`؛ `BlogCommentAdminResponse` در `backend/app/modules/blog/schemas/blog.py`؛ `comments-moderation-tab.tsx:139-250`
- [ناقص] کامنت: عملیات گروهی — تأیید/اسپم/حذف فقط تک‌ردیفی است و انتخاب چندتایی وجود ندارد — شاهد: `frontend/components/admin/blog/comments-moderation-tab.tsx:203-247`؛ جست‌وجوی `bulk` در ماژول کامنت بی‌نتیجه
- [ناقص] کامنت: جست‌وجوی متنی در دیدگاه‌ها — نه پارامتر `search` در پاسخ ادمین هست نه جست‌وجوی متن/نویسنده/ایمیل در UI — شاهد: `backend/app/modules/blog/api/routes.py:984`؛ `comments-moderation-tab.tsx`
- [ناقص] کامنت: صفحه‌بندی فهرست مدیریت — فقط ۵۰ مورد اول نمایش داده می‌شود و pager ندارد — شاهد: `frontend/components/admin/blog/comments-moderation-tab.tsx:65-66` (`page_size: 50`)
- [ناقص] کامنت: لیست کلیدواژه‌های تعدیل و کنترل سیل — بک‌اند `moderation_keys`/`disallowed_keys` و `comment_flood_seconds` را اعمال می‌کند ولی هیچ فیلد UI برای ویرایششان نیست — شاهد: `backend/app/modules/blog/application/comment_service.py:239,364-391`؛ `frontend/components/admin/content-settings-card.tsx:21-140`
- [ناقص] کامنت: گزینه‌های اعلان — تنظیم `comments_notify`/`moderation_notify` وجود ندارد و سیاست ارسال ثابت است — شاهد: `backend/app/modules/blog/application/notification_service.py:60-100`؛ جست‌وجوی `comments_notify|moderation_notify` بی‌نتیجه
- [ناقص] کامنت: لینک تأیید/رد یک‌کلیکی در ایمیل مدیر — اعلان کامنت فقط رویداد outbox می‌فرستد و لینک Approve/Spam/Trash ندارد — شاهد: `backend/app/modules/blog/application/notification_service.py`؛ جست‌وجوی `comment.php/approve-link` در `backend/app` بی‌نتیجه
- [ناقص] کامنت: پاسخ‌دهی با ایمیل — ایمیل اعلان دیدگاه هدر `Reply-To` ندارد — شاهد: جست‌وجوی `reply_to|Reply-To` در `backend/app/modules/notifications/application/email_service.py` بی‌نتیجه
- [ناقص] کامنت: محدودیت نرخ دیدگاه — فقط flood ۱۵ ثانیه‌ای هست و سقف «چند دیدگاه در دقیقه/روز» به‌ازای IP وجود ندارد — شاهد: `backend/app/modules/blog/application/comment_service.py:220-249`
- [ناقص] کامنت: سرویس اسپم بیرونی (Akismet) — فقط امتیازدهی heuristic داخلی هست و اتصال به سرویس اسپم و بازخورد «اسپم واقعی/غیر» نیست — شاهد: `backend/app/modules/blog/application/spam_filter.py`
- [نداریم] کامنت: بستن خودکار دیدگاه‌های قدیمی (`close_comments_for_old_posts`) — جست‌وجوی `close_comments` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-admin/options-discussion.php:81`
- [نداریم] کامنت: الزام نام/ایمیل برای دیدگاه مهمان (`require_name_email`) — کامنت بدون نام هم ثبت می‌شود — شاهد: `backend/app/modules/blog/schemas/blog.py:383-389`؛ جست‌وجوی `require_name_email` بی‌نتیجه
- [نداریم] کامنت: تأیید خودکار دیدگاه‌دهنده‌ی قبلاً تأییدشده (`comment_previously_approved`) — جست‌وجوی `previously_approved` در `backend/app` بی‌نتیجه
- [نداریم] کامنت: لیست سفید کامنت‌های قبلی — کامنت دوم به‌طور خودکار تأیید نمی‌شود — شاهد: جست‌وجوی `whitelist|previous.*comment` در `backend/app/modules/blog/application/comment_service.py` بی‌نتیجه
- [نداریم] کامنت: ترتیب و صفحه‌بندی قابل تنظیم (`comment_order`/`default_comments_page`) — ترتیب همیشه صعودی است و این کلیدها وجود ندارند — شاهد: `backend/app/modules/blog/application/comment_service.py:716,824`؛ جست‌وجوی `comment_order` در `backend/app` بی‌نتیجه
- [نداریم] کامنت: شمارنده‌ی دیدگاه‌های در انتظار در منوی ادمین — بَدج تعداد در انتظار (حباب `awaiting-mod` وردپرس) وجود ندارد — شاهد: `frontend/app/admin/layout.tsx` (لینک‌های بدون بَدج)
- [نداریم] کامنت: میانبرهای صفحه‌کلید مدیریت دیدگاه (approve/unapprove/spam/trash/delete) — جست‌وجوی `keydown|shortcut|hotkey` در `frontend/components/admin/blog/comments-moderation-tab.tsx` بی‌نتیجه — در WP: `wp-admin/js/edit-comments.js`
### مدیا و کتابخانه‌ی رسانه
- [نداریم] مدیا: جایگزینی فایل با حفظ URL (Replace Media) — جست‌وجوی `replace_media|replace.*file` در `backend/app/modules/media` بی‌نتیجه
- [نداریم] مدیا: سایدلود تصویر از URL در UI — route `POST /media/sideload` با گارد SSRF هست ولی هیچ مصرف‌کننده‌ای در فرنت ندارد — شاهد: `backend/app/modules/media/api/routes.py:56-88`؛ جست‌وجوی `sideload` در `frontend` بی‌نتیجه
- [نداریم] مدیا: فیلد Title رسانه — فقط alt/caption/description هست و نه فیلد عنوان در مدل و نه در `MediaAssetUpdateRequest` — شاهد: `backend/app/modules/media/domain/models.py`؛ `backend/app/modules/media/schemas/media.py:50`
- [نداریم] مدیا: فیلتر «پیوست‌نشده» (Unattached) — پارامترهای `list_media` فقط mime/folder/search هستند — شاهد: جست‌وجوی `unattached` در `backend/app/modules/media` و `frontend/app/admin/media` بی‌نتیجه
- [نداریم] مدیا: پیش‌نمایش PDF — برای PDF تصویر پیش‌نمایش ساخته نمی‌شود و فقط فایل ذخیره می‌شود — شاهد: جست‌وجوی `pdf` در `backend/app/modules/media/application/image_processor.py` بی‌نتیجه
- [نداریم] مدیا: آستانه‌ی تصویر بزرگ (Big Image Threshold) — تصاویر بالای ۲۵۶۰px هنگام آپلود کوچک نمی‌شوند، فقط بهینه‌ساز دستی هست — شاهد: `backend/app/modules/media/application/image_optimizer.py:32`؛ جست‌وجوی `big_image` بی‌نتیجه
- [ناقص] مدیا: اتصال به نوشته — ستون `post_id` روی مدل هست ولی هیچ کدی آن را نمی‌نویسد و نه فیلتر/پارامتر `post_id` در فهرست هست نه اکشن attach در UI — شاهد: `backend/app/modules/media/domain/models.py:44-49`؛ `MediaAssetUpdateRequest` در `backend/app/modules/media/schemas/media.py:50-56`
- [ناقص] مدیا: برش با نسبت آماده — crop هست ولی preset نسبت (thumbnail/medium/large) ندارد — شاهد: جست‌وجوی `aspect|ratio` در `frontend/app/admin/media/page.tsx` بی‌نتیجه
- [ناقص] مدیا: نمای فهرستی و فیلتر تاریخ — کتابخانه فقط نمای شبکه با فیلتر mime/پوشه/جست‌وجو دارد — شاهد: `frontend/app/admin/media/page.tsx`؛ پارامترهای `list_assets` در `backend/app/modules/media/application/media_service.py:630-640`
- [ناقص] مدیا: ساخت پوشه از UI — انتقال گروهی با `prompt` مسیر مقصد انجام می‌شود و دکمه‌ی ساخت پوشه نیست — شاهد: `frontend/app/admin/media/page.tsx:247`
- [ناقص] مدیا: واترمارک — سرویس و کلیدهای `media_watermark_*` در بک‌اند فعال‌اند ولی هیچ UI برای فعال‌سازی/تنظیم موقعیت و شفافیت نیست — شاهد: `backend/app/modules/media/application/watermark_service.py`؛ `default_options.py:99-102`؛ جست‌وجوی `watermark` در `frontend` بی‌نتیجه
- [ناقص] مدیا: اندازه‌های تصویر سفارشی (`add_image_size`) — فقط ۴ اندازه‌ی ثابت وجود دارد و ثبت اندازه‌ی دلخواه نیست — شاهد: `backend/app/modules/media/application/image_processor.py:28`؛ `frontend/components/admin/image-size-settings-card.tsx:22-27`
- [ناقص] مدیا: فهرست کانال‌های oEmbed — فقط ۴ ارائه‌دهنده (YouTube/Aparat/Twitter/Instagram) به‌علاوه‌ی fallback از OG در برابر ده‌ها الگوی وردپرس، و کش/allowlist قابل تنظیم نیست — شاهد: `backend/app/modules/content/application/embed_service.py:30-60`
### کاربران، نقش‌ها و کپابیلیتی‌ها
- [نداریم] کاربران: حذف/بازگردانی کاربر از UI — مسیرهای soft-delete/restore و کلاینت `deleteUser`/`restoreUser` هست ولی صفحه‌ی کاربران فقط block/unblock دارد — شاهد: `frontend/lib/api/users.ts:214-219`؛ جست‌وجوی آن در `frontend/app` و `frontend/components` بی‌نتیجه
- [نداریم] کاربران: نام نمایشی/نام مستعار (Display Name / Nickname) — فیلد یا UI وجود ندارد و نام از first/last ساخته می‌شود — شاهد: جست‌وجوی `nickname|display_name` در `backend/app/modules/users` و `frontend` بی‌نتیجه
- [نداریم] کاربران: عملیات گروهی (bulk) — لیست کاربران بدون multi-select است و تغییر نقش/حذف گروهی وجود ندارد — شاهد: جست‌وجوی `bulk` در `frontend/app/admin/users/page.tsx` بی‌نتیجه — در WP: `wp-admin/users.php:58-111`
- [نداریم] کاربران: کنترل باز/بسته بودن ثبت‌نام و نقش پیش‌فرض — ثبت‌نام همیشه باز است و نقش همیشه `customer` — شاهد: جست‌وجوی `users_can_register|default_role` در کل پروژه بی‌نتیجه؛ `backend/app/modules/auth/application/auth_service.py:209-241`
- [نداریم] کاربران: نشانگر قدرت رمز — فقط نمایش/مخفی‌کردن رمز هست و سنجه‌ی زنده‌ی قدرت وجود ندارد — شاهد: `frontend/app/(store)/register/page.tsx:128-134,343-362` — در WP: `pass-strength-result` در `wp-admin/user-new.php:604`
- [نداریم] کاربران: تأیید حساب توسط مدیر — ثبت‌نام بلافاصله توکن می‌دهد و وضعیت «در انتظار تأیید مدیر» وجود ندارد — شاهد: `backend/app/modules/auth/application/auth_service.py` (بازگشت فوری توکن)
- [نداریم] کاربران: مدیریت نشست‌های دیگر کاربران از پنل — «خروج از همه دستگاه‌ها» فقط self-service است و ادمین نشست کاربر دیگر را نمی‌بیند — شاهد: `frontend/components/account/sessions-card.tsx`
- [نداریم] کاربران: تغییر ایمیل مدیریتی با تأییدیه و بازبینی دوره‌ای — جریان `new_admin_email` وجود ندارد و صفحه‌ی «آیا این ایمیل هنوز درست است؟» وجود ندارد — شاهد: جست‌وجوی `new_admin_email|admin_email_verification` در پروژه بی‌نتیجه — در WP: `wp-admin/options-general.php:265`
- [نداریم] کاربران: ورود و ثبت‌نام با ایمیل — احراز هویت فقط با شماره‌ی موبایل است و `RegisterRequest` هم فقط phone/password می‌گیرد — شاهد: `backend/app/modules/auth/application/auth_service.py:312` (فقط `phone`)
- [نداریم] کاربران: «مرا به خاطر بسپار» — هیچ چک‌باکس و منطق نشست بلندمدتی نیست و طول عمر نشست فقط از env می‌آید — شاهد: جست‌وجوی `remember` در `frontend/app/(store)/login/page.tsx` بی‌نتیجه
- [ناقص] کاربران: آواتار سفارشی — فیلد `avatar_url` در مدل و `PATCH /auth/me` هست ولی هیچ UI آپلود/انتخاب از کتابخانه‌ی مدیا در حساب کاربری نیست — شاهد: `backend/app/modules/auth/schemas/auth.py:254-261`؛ جست‌وجوی `avatar` در `frontend/components/account` بی‌نتیجه
- [ناقص] کاربران: ساخت کاربر توسط ادمین — دیالوگ هست ولی فیلد نقش ندارد (نقش‌دهی جدا و بدون UI مانده) و رمز را ادمین دستی می‌دهد — شاهد: `frontend/components/admin/users/user-dialog.tsx:27-33` (FormState بدون role)
- [ناقص] کاربران: فیلتر نقش در فهرست کاربران سمت سرور نیست و کلاینت‌ساید روی صفحه‌ی جاری اجرا می‌شود — شاهد: `frontend/app/admin/users/page.tsx:119-129` («the API has no role parameter»)؛ `list_users` در `backend/app/modules/users/api/routes.py:159-165`
- [ناقص] کاربران: تأیید ایمیل هنگام ثبت‌نام — ستون `is_verified` هست ولی هیچ ایمیل تأییدی فرستاده نمی‌شود و فقط OTP شماره تأیید می‌کند — شاهد: `backend/app/modules/auth/application/auth_service.py:222,555`
- [ناقص] کاربران: ساخت خودکار `author_slug` — فقط یک‌بار در migration پر شده و برای کاربران جدید ساخته نمی‌شود، پس آرشیو نویسنده‌ی تازه ۴۰۴ است — شاهد: `backend/alembic/versions/2026_09_28_1805-q7r8s9t0u1v2_user_author_slug.py`؛ جست‌وجوی `author_slug` در ماژول‌های auth/users بی‌نتیجه
- [ناقص] کاربران: پاسکی — route چالش تصادفی هست ولی verify و ذخیره‌ی اعتبارنامه ندارد و `use-passkey` هیچ مصرف‌کننده‌ای ندارد — شاهد: `backend/app/modules/auth/api/routes.py:699-703`؛ `frontend/hooks/use-passkey.ts`
### ویجت‌ها، منوها و داشبورد
- [ناقص] ویجت: انواع ویجت — ۱۰ نوع داریم (text/recent_posts/categories/tags/search/menu/image/social_links/newsletter/custom_html) در برابر ۱۹ ویجت هسته؛ `archives`، `calendar`، `recent_comments`، `pages`، `meta`، `rss`، `links` و ویجت‌های رسانه غایب‌اند — شاهد: `WIDGET_TYPES` در `backend/app/shared/content/widgets.py:40-51` در برابر ۱۹ فایل `wp-includes/widgets/`
- [ناقص] ویجت: تنظیمات هر ویجت — فرم فقط `title`/`content` دارد و هیچ فرم اختصاصی برای تعداد پست، دسته‌بندی هدف یا فیلترها نیست — شاهد: `frontend/app/admin/widgets/page.tsx:62-77`
- [ناقص] ویجت: نواحی و چیدمان — نواحی در کد ثابت‌اند (header_top/footer_1..3/sidebar)، ناحیه‌ی جدید از پنل ساخته نمی‌شود و چیدمان فقط با دکمه‌ی بالا/پایین است نه drag & drop — شاهد: `WIDGET_AREAS` در `backend/app/shared/content/widgets.py`؛ `frontend/app/admin/widgets/page.tsx:82-90`؛ `frontend/components/layout/header.tsx:299` (`area="header_top"` ثابت)
- [ناقص] منو: آیتم‌ها فقط لینک سفارشی — مدل فقط `title+url` دارد و انتخابگر صفحه/دسته/برچسب/پست، افزودن خودکار صفحات، کلاس CSS، `target`، `title attribute` و آیکون در UI نیست — شاهد: `backend/app/modules/content/domain/models.py:78-107`؛ `backend/app/modules/content/schemas/content.py:48-55`؛ `MenuBuilderCard` در `frontend/app/admin/cms/page.tsx:706-930`
- [ناقص] منو: مکان‌های منو ثابت (۵ مقدار enum) — افزودن/حذف مکان و ساخت چند منو و تخصیص آزاد به ناحیه در UI نیست — شاهد: `MenuLocation` در `backend/app/modules/content/domain/models.py:43-48`
### تنظیمات
- [نداریم] تنظیمات: گزینه‌های آواتار سراسری (`show_avatars`/`avatar_default`/`avatar_rating`) — گراواتار همیشه فعال است و این کلیدها وجود ندارند — شاهد: `backend/app/shared/content/gravatar.py`؛ جست‌وجوی `show_avatars|avatar_rating` بی‌نتیجه
- [نداریم] تنظیمات: robots.txt مجازی با دستور قالب — robots ما فایل Next است ولی هیچ کنترل پنلی برای افزودن خط به آن نیست — شاهد: `frontend/app/robots.ts`
- [ناقص] تنظیمات: ساختار پیوند یکتا — ۵ پریست و ورودی آزاد با اعتبارسنجی داریم ولی URLهای ساخته‌شده با ساختار قبلی ریدایرکت خودکار نمی‌شوند — شاهد: `frontend/components/admin/content-settings-card.tsx:217-221`؛ `backend/app/modules/settings/api/routes.py:137-139`
- [ناقص] تنظیمات: تب‌بندی تنظیمات — صفحه‌ی تنظیمات یک صفحه‌ی بلند بدون گروه‌بندی General/Writing/Reading/Discussion/Media/Permalinks/Privacy است — شاهد: `frontend/app/admin/settings/page.tsx`
### ابزارها، ایمپورت/اکسپورت و به‌روزرسانی
- [نداریم] ابزارها: ایمپورتر WXR (ورود از وردپرس با XML) — هیچ پارسر WXR/XML وجود ندارد و خود سرویس این را «شکاف باز» اعلام کرده — شاهد: `backend/app/modules/blog/application/transfer_service.py:6-9` («no WXR parser exists in this project… an open gap»)
- [ناقص] ابزارها: اکسپورت بلاگ ناقص — خروجی دیدگاه‌ها را شامل نمی‌شود (خود سرویس صریحاً می‌گوید) و منوها/فیلدهای سفارشی/نسخه‌ها هم صادر نمی‌شوند — شاهد: `backend/app/modules/blog/application/transfer_service.py:3-4`
- [ناقص] ابزارها: ایمپورت JSON رسانه را نمی‌آورد — فقط متن/متادیتا وارد می‌شود و فایل‌ها و remap آدرس تصاویر وارد نمی‌شوند — شاهد: `BlogTransferService.import_json` در `backend/app/modules/blog/application/transfer_service.py`
- [ناقص] ابزارها: حالت بازیابی — صفحه‌ی pause و ازسرگیری هست ولی ایمیل دعوت با لینک بازیابی و کلید ورود موقت وجود ندارد — شاهد: `backend/app/core/exceptions/recovery_mode.py` (جست‌وجوی `email|mail` در آن بی‌نتیجه)
- [ناقص] ابزارها: کرون — Celery beat معادل wp-cron هست ولی صفحه‌ی «رویدادهای زمان‌بندی‌شده» و اجرای دستی از ادمین نیست — شاهد: `beat_schedule` در `backend/app/worker/celery_app.py`
### REST API، فید، سایت‌مپ و پروتکل‌ها
- [ناقص] فید: دو مسیر موازی سایت‌مپ — Next.js `/sitemap.xml` و بک‌اند `/content/sitemap.xml` با index پنج‌providerی که هیچ مصرف‌کننده‌ای در فرانت ندارد — شاهد: `backend/app/modules/content/application/sitemap_index_service.py:19,126-131`
- [ناقص] فید: discovery کامل oEmbed — لینک `text/json+oembed` فقط در layout ریشه تزریق می‌شود و صفحات پست/صفحه لینک discovery مخصوص خود را ندارند — شاهد: `frontend/app/layout.tsx:86-87`
### حریم خصوصی، GDPR و امنیت
- [ناقص] حریم خصوصی: خروجی داده کاربر — رجیستری ۴۵ منبع و route ادمین و self-service کار می‌کند ولی خروجی فقط JSON خام است و نه ZIP ساخت‌یافته با index.html و نه لینک ایمیلی منقضی‌شونده — شاهد: `backend/app/modules/settings/application/privacy_sources.py:123-178`؛ `backend/app/modules/settings/api/routes.py:818-843`
- [ناقص] حریم خصوصی: سیاست نگه‌داشت — صف پاکسازی و `purge-expired` هست ولی مدت نگه‌داشت قابل تنظیم نیست — شاهد: `purge-expired` در `backend/app/modules/settings/api/routes.py`
- [ناقص] حریم خصوصی: انتخابگر صفحه‌ی سیاست — به اسلاگ ثابت `privacy` وصل است و `wp_page_for_privacy_policy` و متن راهنمای قابل ویرایش وجود ندارد — شاهد: `frontend/app/(store)/privacy/page.tsx`؛ `frontend/app/(store)/privacy/guide/page.tsx:13-15`؛ جست‌وجوی `privacy_policy|wp_page_for_privacy` بی‌نتیجه
- [ناقص] حریم خصوصی: جریان ایمیلی تأیید درخواست — درخواست‌ها فقط از داخل نشست کاربر ثبت می‌شوند و جریان ایمیل به موضوع و تأیید با لینک وجود ندارد — شاهد: `PrivacyRequestService.submit` در `backend/app/modules/settings/application/privacy_request_service.py` — در WP: `wp_send_user_request`
### Site Health، i18n و دسترس‌پذیری
- [ناقص] Site Health: پوشش آزمون‌های هسته — ۱۱ تا ۱۳ بررسی داریم در برابر ده‌ها تست وردپرس؛ loopback HTTP، دسترس‌پذیری REST، utf8mb4/autoload، کش صفحه، وضعیت دیباگ، نشست‌ها، پوشه‌ی بک‌آپ، فضای دیسک، opcode cache و افزونه‌های PHP معادل ندارند — شاهد: `backend/app/modules/settings/application/site_health_service.py:39-440` و `content_health_service.py:42-334` در برابر `get_tests()` در `wp-admin/includes/class-wp-site-health.php:2850`
- [ناقص] Site Health: چک «آیا سایت می‌تواند ایمیل بفرستد؟» — تست SMTP فقط در صفحه‌ی تنظیمات است — شاهد: تست در `frontend/app/admin/settings/page.tsx:1039`؛ `site_health_service.py` بدون چک ایمیل
- [ناقص] دسترس‌پذیری: آزمون خودکار — `@axe-core/playwright` نصب است ولی هیچ فایل آزمونی آن را به‌کار نمی‌برد — شاهد: `frontend/package.json` و نبود هر فایل حاوی `AxeBuilder` در `frontend`

## P2 — رشد، بهینه‌سازی و راحتی (25)

کار را نمی‌ندازد؛ فقط کیفیت، سرعت یا راحتی را بهتر می‌کند.

### نوشته، گردش ویرایش و ریویژن
- [ناقص] نوشته: قالب‌بندی خودکار متن (wpautop/wptexturize) — تبدیل خودکار پاراگراف فقط سمت کلاینت و صرفاً در صفحه‌ی تکی وبلاگ انجام می‌شود و نوع‌نگاری/ایموجی وجود ندارد — شاهد: `backend/app/shared/content/render.py` (فقط reusable + shortcode)؛ جست‌وجوی `wpautop|texturize|smilies` در `backend/app` بی‌نتیجه
### تاکسونومی، متا و فیلدهای دلخواه
- [ناقص] متا: متای نوشته فقط در دیالوگ ویرایش دیده می‌شود و در Quick Edit و بازگردانی ریویژن نیست — شاهد: `frontend/app/admin/blog/page.tsx:1240-1290`
### کامنت‌ها
- [ناقص] کامنت: فیلد وب‌سایت دیدگاه‌دهنده — ستون `author_url` و ارسال در API هست ولی فرم عمومی آن را نمی‌گیرد و رندر نمی‌کند — شاهد: `backend/app/modules/blog/domain/models.py:422`؛ `frontend/components/blog/blog-comments.tsx:75-80`
- [ناقص] کامنت: بادداشت خصوصی روی نوشته (`comment_type note`) — یادداشت‌گذاری خصوصی تیم وجود ندارد — شاهد: جست‌وجوی `wp_notes|comment_type` در `backend/app` و `frontend` بی‌نتیجه
### مدیا و کتابخانه‌ی رسانه
- [ناقص] مدیا: بازیابی نسخه اصلی پس از ویرایش تصویر — ویرایش‌ها غیرمخرب‌اند ولی دکمه «بازگردانی به اصل» و فهرست نسخه‌های مشتق نیست — شاهد: `backend/app/modules/media/application/image_editor.py:1-5`؛ جست‌وجوی `restore` در ماژول مدیا بی‌نتیجه
- [ناقص] مدیا: تاریخچه‌ی ویرایش تصویر (Undo/Redo) — crop/rotate/flip/resize هست ولی undo/redo، مقایسه با اصل و «ذخیره به‌عنوان کپی جدید» نیست — شاهد: `frontend/app/admin/media/page.tsx:324-471,896-935`؛ جست‌وجوی `undo|redo` بی‌نتیجه
- [ناقص] مدیا: ویرایش تصویر از داخل ادیتور محتوا — ابزارها فقط در صفحه‌ی مدیا هستند و از داخل ویرایشگر در دسترس نیستند — شاهد: `frontend/app/admin/media/page.tsx:324-471`
- [ناقص] مدیا: هشدار متن جایگزین — متد `needs_alt_text` آماده است ولی هیچ مصرف‌کننده‌ای ندارد و در فهرست مدیا هشدار داده نمی‌شود — شاهد: `backend/app/modules/media/schemas/media.py:36`
- [ناقص] مدیا: سقف آپلود ثابت — ۱۰MB برای تصویر/PDF و ۱۰۰MB برای صوت/ویدیو در کد ثابت است و از تنظیمات قابل تغییر نیست — شاهد: `MAX_FILE_SIZE_BYTES`/`MAX_MEDIA_FILE_SIZE_BYTES` در `backend/app/modules/media/application/media_service.py:100-115`
### ویجت‌ها، منوها و داشبورد
- [نداریم] داشبورد: نوار مدیریت در فرانت (Admin Bar) — نوار بالای سایت برای کاربر واردشده با لینک «ویرایش/افزودن» وجود ندارد — شاهد: جست‌وجوی `admin-bar|admin_bar|AdminBar` در `frontend/app` و `frontend/components` بی‌نتیجه — در WP: `wp-includes/admin-bar.php`
- [نداریم] داشبورد: اعلان‌های ماندگار قابل‌بستن (Admin Notices) — فقط توست گذرا وجود دارد — شاهد: `frontend/components/ui/use-toast.tsx`؛ جست‌وجوی `notice-dismiss|dismissible` در `frontend/components/admin` بی‌نتیجه
### تنظیمات
- [نداریم] تنظیمات: قالب تاریخ/زمان و منطقه‌ی زمانی — `date_format`/`time_format`/`timezone_string` seed می‌شوند ولی هیچ کدی آن‌ها را نمی‌خواند و فیلد ویرایش ندارند — شاهد: `backend/app/modules/settings/application/default_options.py:39-42`؛ جست‌وجوی مصرف بیرون از فایل seed بی‌نتیجه
- [نداریم] تنظیمات: دسته‌ی پیش‌فرض و فرمت پیش‌فرض نوشته و `ping_sites` — نوشته‌ی جدید بدون هیچ پیش‌فرضی ساخته نمی‌شود — شاهد: جست‌وجوی `default_category|default_post_format|ping_sites` در کل پروژه بی‌نتیجه — در WP: `wp-admin/options-writing.php`
- [ناقص] تنظیمات: زبان‌های محتوا — `enabled_locales`/`default_locale` در بک‌اند هستند ولی هیچ UI ویرایشی ندارند و برنامه‌ی ترجمه فهرست ثابت `["fa","en","ar"]` دارد — شاهد: `backend/app/modules/settings/application/default_options.py:69-70`؛ `backend/app/modules/settings/application/i18n_service.py:38`
### ابزارها، ایمپورت/اکسپورت و به‌روزرسانی
- [نداریم] ابزارها: ایمپورت از پلتفرم‌های دیگر (Movable Type، Tumblr، Blogger، RSS) — جست‌وجوی `importer|blogger|tumblr` در `backend/app` بی‌نتیجه — شاهد WP: `wp-admin/import.php`
### REST API، فید، سایت‌مپ و پروتکل‌ها
- [ناقص] REST: مدیریت Application Password کاربر دیگر — ادمین نمی‌تواند app password کاربر را از صفحه‌ی مدیریت کاربران ببیند یا لغو کند — شاهد: `backend/app/modules/auth/application/application_password_service.py:63-211`؛ جست‌وجوی `application_password` در `backend/app/modules/users` و `rbac` بی‌نتیجه
- [ناقص] REST: احراز Basic با Application Password — رمزهای اپلیکیشن فقط به‌صورت Bearer پذیرفته می‌شوند — شاهد: `backend/app/core/security/dependencies.py:62`
- [ناقص] فید: بدون کش نتیجه‌ی oEmbed و پروکسی عمومی برای هر نشانی — فقط ۴ ارائه‌دهنده و fallback OG هست — شاهد: `backend/app/modules/content/application/embed_service.py:30-60`؛ `backend/app/modules/content/application/oembed_provider.py`
### حریم خصوصی، GDPR و امنیت
- [ناقص] امنیت: همگام‌سازی allowlist سمت سرور و کلاینت — دو نسخه‌ی جدا هستند و HTML نهایی روی خواندن دوباره sanitize نمی‌شود — شاهد: `backend/app/shared/content/html_sanitizer.py` و `frontend/lib/editor/allowlist.ts`؛ پاریتی در `scripts/wp-parity/check_editor_allowlists.py`
### Site Health، i18n و دسترس‌پذیری
- [ناقص] Site Health: آزمون‌های زمان‌بندی‌شده و نمای رویدادها — اجرای دوبار-در-روز و فهرست اجراهای پیش‌رو با اجرای دستی وجود ندارد — شاهد: `beat_schedule` در `backend/app/worker/celery_app.py`؛ `content_health_service.py:264`
- [ناقص] Site Health: تب Info ناقص — فقط server/database/storage را پوشش می‌دهد و گزینه‌های autoload و نسخه‌ی افزونه‌ها و رویدادهای زمان‌بندی‌شده را ندارد — شاهد: `frontend/app/admin/system-health/page.tsx`
- [ناقص] i18n: کاتالوگ رشته‌های رابط — سرویس و اندپوینت کاتالوگ با CRUD ادمین و `GET /settings/public/i18n` هست ولی هیچ صفحه‌ی ادمین و هیچ مصرف‌کننده‌ی فرانتی ندارد و رشته‌ها هاردکد فارسی‌اند — شاهد: `backend/app/modules/settings/api/routes.py:1384-1490`؛ `frontend/lib/i18n.ts:78-93`؛ جست‌وجوی `admin/i18n|public/i18n` در `frontend` بی‌نتیجه
### پلاگین، هوک و توسعه‌پذیری
- [ناقص] پلاگین: پوشش هوک‌ها — فقط ۴ نقطه‌ی dispatch در کل کد هست (`cms.page.before_save`, `cms.page.after_publish`, `cms.page.body_render`, `seo.metadata`) و نوشته‌ی وبلاگ هیچ هوکی ندارد، در برابر ۴۴۰ فیلتر پیش‌فرض وردپرس — شاهد: `backend/app/shared/plugins/registry.py:176-179`؛ `default_filter_hooks: 440` در `scripts/wp-parity/wp_inventory.json`
### ایمیل
- [ناقص] ایمیل: قالب قابل ویرایش از پنل — ایمیل‌های تراکنشی قالب HTML هاردکد دارند و ویرایشگر ندارند — شاهد: `backend/app/modules/notifications/application/email_service.py:418-447`؛ جست‌وجوی `email_template` بدون ویرایشگر
- [ناقص] ایمیل: پیوست فایل — سرویس ایمیل پشتیبانی از پیوست پشتیبانی نمی‌کند — شاهد: `backend/app/modules/notifications/application/email_service.py`

---

## بی‌ربط به فروشگاه (103) — چرا کنار گذاشته شدند

گروه‌های بزرگ این‌ها هستند:

- **ادیتور بلاکی و سایت‌ادیتر** (32 مورد): ساخت گutenberg با ۱۱۵ بلاک، Theme JSON، قالب‌های بلاکی و child theme. فروشگاه ما یک ادیتور متنی قابل قبول دارد؛ ساخت سیستم بلاک ماه‌ها کار می‌برد و مشتریِ فروشگاه آن را نمی‌بیند.
- **چندسایته و APIهای پلتفرمی وردپرس ۷** (8 مورد): Multisite، Abilities API، AI Client، Speculation Rules، View Transitions، Interactivity API، HTML API. یک فروشگاه تک‌سایتی به اینها نیاز ندارد.
- **پلاگین و به‌روزرسانی هسته** (6 مورد): نصب/به‌روزرسانی پلاگین و کور وردپرس، بسته‌ی زبان، رجیستری افزونه. ما کد خودمان را دیپلوی می‌کنیم، نه وردپرس را.
- **سازگاری با ابزارهای وردپرسی** (16 مورد): XML-RPC، RSD، pingback/trackback، Post by Email، Press This، ایندکس REST، پارامترهای `_fields`/`_embed`، فیدهای RDF/Atom/۰.۹۲.
- **قابلیت‌های کتابخانه‌ی رسانه** (7 مورد): صفحه‌ی پیوست، تاکسونومی رسانه، پوشه‌ی سال/ماه، پلی‌لیست صوتی، متادیتای ID3، Openverse، آپلود zip/docx.

موارد بی‌ربط دیگر تک‌تک با همان فرمت در انتهای همین سند آمده‌اند؛ این پنج گروه فقط بزرگ‌ترین خوشه‌ها را نشان می‌دهند، نه همه‌ی 103 مورد را.

### همه‌ی 103 مورد بی‌ربط، به ترتیب سند مبدأ

- [نداریم] ادیتور و بلاک: ادیتور بلاکی (Gutenberg) و کتابخانه‌ی ۱۱۵ بلاک هسته — ادیتور ما یک `contentEditable` ساده با ۷ دکمه است، نه سیستم بلاک ساخت‌یافته — شاهد: `frontend/components/admin/RichBodyEditor.tsx` (فقط `document.execCommand`)؛ جست‌وجوی `parse_blocks|register_block_type|serialize_block|<!-- wp:` در `backend/app` و `frontend` بی‌نتیجه
- [نداریم] ادیتور و بلاک: رجیستری بلاک با `block.json` و attributes/variations/styles — هیچ نوع بلاکی در پروژه ثبت نمی‌شود — شاهد: جست‌وجوی `registerBlockType|register_block_type|block.json` در کل پروژه صفر نتیجه؛ در WP: `wp-includes/blocks.php` و ۱۱۵ فایل `block.json`
- [نداریم] ادیتور و بلاک: Block Bindings API (اتصال اتریبیوت بلاک به فیلد/متا) — جست‌وجوی `block_binding|block-binding|blockBindings` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-includes/block-bindings/`
- [نداریم] ادیتور و بلاک: Block Supports (رنگ/تایپوگرافی/فاصله/سایه/duotone در سطح هر بلاک) — هیچ لایه‌ی استایل بلاکی وجود ندارد — شاهد: جست‌وجوی `duotone|block_style|style_variation` در `frontend/` بی‌نتیجه؛ فهرست ۲۳ موردی `block_supports` در `scripts/wp-parity/wp_inventory.json`
- [نداریم] ادیتور و بلاک: Block Locking و block visibility (قفل/پنهان‌سازی بلاک در محتوا) — جست‌وجوی `block_lock|block-locking|blockVisibility` در کل پروژه صفر نتیجه
- [نداریم] ادیتور و بلاک: Block Directory و Pattern Directory (نصب بلاک/الگو از مخزن وردپرس) — جست‌وجوی `block-directory|blockDirectory|pattern-directory|patternDirectory` در کل پروژه بی‌نتیجه — شاهد WP: `class-wp-rest-block-directory-controller.php`
- [نداریم] ادیتور و بلاک: Stylebook و Style Variations و Block Styles (نسخه‌های جایگزین استایل) — جست‌وجوی `stylebook|style variation|blockVariation` در کل پروژه بی‌نتیجه
- [نداریم] ادیتور و بلاک: بلاک Query Loop (فهرست پویای پست/محصول با فیلتر در ویرایشگر) — جست‌وجوی `query_loop|query-loop` در `backend/app` و `frontend` بی‌نتیجه
- [نداریم] ادیتور و بلاک: بلاک پانویس (Footnotes) — جست‌وجوی `footnote` در `backend/app` و `frontend` فقط یک کامنت در `settings/application/site_health_service.py` دارد
- [نداریم] ادیتور و بلاک: Block Widgets (قرار دادن بلاک در نواحی ویجت) — ویجت‌های ما ۱۰ نوع JSON-محور ثابت‌اند — شاهد: `WIDGET_TYPES` در `backend/app/shared/content/widgets.py:40-51` در مقابل `class-wp-widget-block.php`
- [نداریم] ادیتور و بلاک: تگ More (`<!--more-->`) و صفحه‌بندی محتوا (`<!--nextpage-->`) — جست‌وجوی `<!--more|nextpage` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-includes/post-template.php`
- [نداریم] ادیتور و بلاک: ویرایشگر فایل قالب/پلاگین از پنل (theme-editor.php/plugin-editor.php) — جست‌وجوی `theme-editor|plugin-editor` در `frontend/app/admin` و `backend/app` بی‌نتیجه
- [ناقص] ادیتور و بلاک: الگوهای بلاک (Block Patterns) — ۸ الگوی کد-ثبت‌شده با انتخابگر داریم ولی ساخت/ویرایش الگو، دسته‌بندی قابل‌مدیریت و پیش‌نمایش تصویری نیست و دسته‌ها برچسب فارسی هاردکد دارند — شاهد: `backend/app/modules/content/domain/block_patterns.py`؛ `frontend/components/admin/block-pattern-picker.tsx`
- [ناقص] ادیتور و بلاک: درج الگو یا بلوک قابل استفاده‌ی مجدد از داخل ادیتور — کاربر باید توکن `[block slug="…"]` را دستی کپی کند — شاهد: کامنت خود کد در `frontend/components/admin/reusable-blocks-card.tsx` («there is nothing to insert through the editor»)
- [ناقص] ادیتور و بلاک: بلوک‌های قابل استفاده‌ی مجدد (Reusable Blocks) — زنجیره کامل است ولی شمارش ارجاع پیش از حذف، الگوی غیرهمگام (unsynced) و بازگردانی نسخه‌ی قبلی ندارد — شاهد: `backend/app/modules/content/application/reusable_block_service.py` (بدون usage count)
- [ناقص] ادیتور و بلاک: درج خودکار رسانه (autoembed) — URL فقط با دکمه‌ی دستی oEmbed جاسازی می‌شود و در رندر خودکار امبد نمی‌شود — شاهد: `backend/app/shared/content/render.py` (فقط reusable + shortcode)
- [ناقص] ادیتور و بلاک: View Config و ذخیره‌ی سمت‌سرور Screen Options — ستون‌های قابل نمایش فقط در `localStorage` همان مرورگر ذخیره می‌شوند و ذخیره‌ی سمت‌سرور تنظیمات نمایش هر کاربر وجود ندارد — شاهد: `frontend/components/admin/list-engine.tsx:313-343`؛ `frontend/components/admin/data-table.tsx:69` (`columnVisibilityKey`)
- [نداریم] سایت‌ادیتر و تمپلیت: سایت‌ادیتر و قالب‌های بلاکی (`wp_template`/`wp_template_part`) — سلسله‌مراتب تمپلیت و ویرایش چیدمان کل سایت وجود ندارد؛ قالب سایت همان فایل‌های ثابت Next.js است — شاهد: جست‌وجوی `wp_template|template_part|site_editor` در `backend/app` و `frontend/app` بی‌نتیجه؛ در WP: `wp-admin/site-editor.php`
- [ناقص] سایت‌ادیتر و تمپلیت: Global Styles و `theme.json` — فقط ۷ توکن رنگ به‌علاوه‌ی شعاع/حالت تاریک هست و تایپوگرافی، فاصله‌گذاری، چیدمان، استایل per-block و ریویژن استایل سراسری غایب است — شاهد: `backend/app/modules/content/application/single_type_service.py:99-148` (که خودش را «theme.json parity» می‌نامد) و `_THEME_SCHEMA`
- [ناقص] سایت‌ادیتر و تمپلیت: سیستم تم — تم‌ها فقط «مجموعه توکن رنگ/رادیوس» با فعال‌سازی/ساخت/حذف‌اند و تمپلیت، پوسته‌ی فرزند (child theme)، style variation و ریویژن ندارند — شاهد: `backend/app/modules/settings/application/theme_service.py` («A theme here is a named token set»)؛ `frontend/app/admin/themes/page.tsx`
- [نداریم] سایت‌ادیتر و تمپلیت: نصب/آپلود تم از ZIP یا از مخزن — جست‌وجوی `install_theme|theme-install|child_theme` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-admin/theme-install.php`
- [ناقص] سایت‌ادیتر و تمپلیت: ویرایش توکن تم — `radius` اعمال می‌شود ولی فیلد UI ندارد و `typography` در فرانت هیچ مصرف‌کننده‌ای ندارد — شاهد: `frontend/app/admin/cms/page.tsx:467-570` (فقط `COLOR_KEYS`)؛ `frontend/lib/theme.ts`
- [ناقص] سایت‌ادیتر و تمپلیت: پیش‌نمایش تم غیرفعال پیش از فعال‌سازی — صفحه‌ی پوسته فقط بعد از تغییر reload می‌کند و پیش‌نمایش تم فعال‌نشده وجود ندارد — شاهد: `frontend/app/admin/themes/page.tsx:19-22`
- [نداریم] سایت‌ادیتر و تمپلیت: سلسله‌مراتب قالب (template hierarchy) و انتخاب قالب برای هر صفحه/نوع محتوا — چیدمان‌ها ثابت Next.js هستند — شاهد: جست‌وجوی `template hierarchy|get_template_part|template-part` در `backend/app` و `frontend` بی‌نتیجه
- [ناقص] سایت‌ادیتر و تمپلیت: قالب برگه (page_template) — ستون فقط در مدل و آداپتور dataexchange است؛ نه فیلد اسکیمای API، نه route، نه UI انتخاب و نه رندرکننده‌ای که آن را بخواند — شاهد: `backend/app/modules/content/domain/models.py:217`؛ `backend/app/modules/dataexchange/application/cms_page_adapter.py:136`؛ جست‌وجوی `page_template` در `frontend` بی‌نتیجه
- [نداریم] سایت‌ادیتر و تمپلیت: Font Library (نصب Font Family/Font Face و آپلود فونت) — فقط یک فیلد متنی `font_family` در توکن تایپوگرافی هست که در فرانت مصرف نمی‌شود — شاهد: جست‌وجوی `font_library|font_face|fontFaces` بی‌نتیجه؛ `single_type_service.py:148`؛ در WP: `wp-admin/font-library.php` و `wp-includes/fonts/`
- [نداریم] سایت‌ادیتر و تمپلیت: Custom Logo (لوگوی قابل تغییر از پنل) — فقط `site_icon` (فاوآیکون) خوانده می‌شود و هدر فروشگاه عنوان/کاراکتر ثابت دارد — شاهد: `frontend/components/layout/header.tsx:364-375`؛ جست‌وجوی `custom_logo|logo_url` در `backend/app` بی‌نتیجه
- [ناقص] سایت‌ادیتر و تمپلیت: سایت‌ایکون — به‌عنوان favicon اعمال می‌شود ولی برش/پیش‌نمایش مربع و تولید اندازه‌های اپل/اندروید ندارد — شاهد: `frontend/app/layout.tsx:22-38`
- [نداریم] سایت‌ادیتر و تمپلیت: Custom Header و Custom Background (تصویر سربرگ با برش و پس‌زمینه) — جست‌وجوی `custom-header|custom-background|header_image|background_image` در `backend/app` و `frontend` بی‌نتیجه
- [ناقص] سایت‌ادیتر و تمپلیت: Customizer — فقط ویرایش ۷ کلید رنگ با پیش‌نمایش زنده‌ی iframe؛ کنترل‌های هدر/پس‌زمینه/لوگو/ویجت/منو و changeset وجود ندارد — شاهد: `frontend/components/shared/theme-preview-bridge.tsx:12-21`؛ `frontend/app/admin/cms/page.tsx:467`
- [نداریم] سایت‌ادیتر و تمپلیت: CSS سفارشی سراسری (Additional CSS) — راهی برای افزودن CSS دلخواه بدون دیپلوی نیست — شاهد: جست‌وجوی `custom_css|additional_css` در کل پروژه بی‌نتیجه
- [نداریم] سایت‌ادیتر و تمپلیت: Icons API (کالکشن‌های آیکون ثبت‌شدنی و انتخابگر آیکون، وردپرس ۷.۱) — `SiteMenu.icon` فقط رشته‌ی متنی است — شاهد: جست‌وجوی `icon_collection|icons-registry|icon_picker` در `backend/app` و `frontend` بی‌نتیجه؛ در WP: `wp-includes/icons.php`
- [ناقص] نوشته: آرشیو روزانه — فقط `/archive/{year}` و `/archive/{year}/{month}` سرو می‌شود و preset «روز، ماه و نام» در UI ۴۰۴ می‌دهد — شاهد: `backend/app/modules/blog/api/routes.py:1849-1850`؛ `frontend/components/admin/content-settings-card.tsx:217-221`
- [ناقص] نوشته: وضعیت‌های نوشته — ۱۲ وضعیت وردپرس با ۴ وضعیت + فیلدهای جدا پوشش داده شده و `auto-draft` و `inherit` معادل ندارند — شاهد: `backend/app/modules/blog/domain/models.py:29-36`
- [نداریم] نوشته: وضعیت سفارشی نوشته (`register_post_status`) — وضعیت‌ها enum ثابت‌اند و تعریف وضعیت جدید ممکن نیست — شاهد: جست‌وجوی `register_post_status|custom_post_status` در `backend/app` بی‌نتیجه
- [ناقص] نوشته: پیوند کوتاه (Get Shortlink) — هیچ مسیر یا دکمه‌ی shortlink برای نوشته نیست — شاهد: جست‌وجوی `shortlink` در `backend/app` و `frontend` بی‌نتیجه
- [ناقص] نوشته: روابط نوشته و پیوند ترجمه — API روابط نوشته و API ترجمه‌ی صفحه‌ها هست ولی هیچ UI برای اتصال/قطع آن‌ها وجود ندارد — شاهد: `relationshipsApi` در `frontend/lib/api/wp-parity.ts:379`؛ `POST /admin/pages/{page_id}/translations`؛ جست‌وجوی `translation` در `frontend/app/admin/pages/page.tsx` بی‌نتیجه
- [نداریم] نوشته: پینگ‌بک/ترک‌بک (ارسال و دریافت) — جست‌وجوی `pingback|trackback` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-trackback.php` و `xmlrpc.php`
- [نداریم] نوشته: انتشار با ایمیل (Post by Email) — جست‌وجوی `post_by_email|wp-mail|imap|pop3` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-admin/wp-mail.php`
- [نداریم] نوشته: Press This (بوکمارکلت انتشار سریع) — جست‌وجوی `press-this|press_this|bookmarklet` در کل پروژه بی‌نتیجه — شاهد WP: `wp-admin/press-this.php`
- [نداریم] تاکسونومی: توضیحات برچسب — `BlogTag` فقط `name/slug` دارد در حالی که دسته‌بندی ستون `description` دارد — شاهد: `backend/app/modules/blog/domain/models.py:254-261`
- [ناقص] تاکسونومی: مبدل دسته↔برچسب (Categories and Tags Converter) — ابزار تبدیل گروهی دسته به برچسب وجود ندارد — شاهد: جست‌وجوی `converter|cat2tag` در `backend/app/modules/blog` و `frontend/app/admin` بی‌نتیجه — در WP: `wp-admin/tools.php`
- [ناقص] متا: متای صفحه CMS — سه route CRUD دارد ولی هیچ UI در `frontend/app/admin/pages/page.tsx` آن را مصرف نمی‌کند — شاهد: `backend/app/modules/content/api/routes.py:1453-1489`؛ جست‌وجوی `pageMeta|pages/.*/meta` در `frontend` بی‌نتیجه
- [ناقص] متا: متای کامنت و متای ترم — هر دو CRUD کامل در بک‌اند دارند ولی هیچ مصرف‌کننده‌ای در فرنت ندارند — شاهد: `backend/app/modules/blog/api/routes.py:1590,1626,1644`؛ جست‌وجوی `CommentMeta|TermMeta` در `frontend` بی‌نتیجه
- [ناقص] متا: متای کاربر (User Meta) — جدول `user_meta` فقط در سرویس حریم خصوصی خوانده/پاک می‌شود و هیچ route یا UI برای CRUD ندارد — شاهد: `backend/app/modules/blog/domain/wp_parity_models.py:47`؛ تنها مصرف‌کننده `backend/app/modules/settings/application/privacy_service.py:134`
- [ناقص] متا: متای نوشته در Quick Edit — سفارشی‌کردن فیلدها فقط در فرم اصلی ویرایش ممکن است و نه در ویرایش سریع — شاهد: `frontend/components/admin/blog/quick-edit-dialog.tsx`؛ `QUICK_EDIT_FIELDS` در `backend/app/modules/blog/application/quick_edit_service.py:28-31`
- [ناقص] کامنت: لنگر/پیوند دائمی دیدگاه (`#comment-…`) — هیچ لینک یکتای قابل اشتراک برای هر دیدگاه تولید نمی‌شود — شاهد: جست‌وجوی `#comment` در `frontend/components/blog/blog-comments.tsx` بی‌نتیجه (فقط در فید: `backend/app/modules/blog/application/feed_service.py:518`)
- [ناقص] کامنت: کوکی هویت دیدگاه‌دهنده و رضایت کوکی — نام/ایمیل مهمان بین دیدگاه‌ها ذخیره و بازیابی نمی‌شود و چک‌باکس رضایت کوکی نیست — شاهد: نبود `localStorage|cookie` در `frontend/components/blog/blog-comments.tsx`؛ جست‌وجوی `comment_cookie|cookies_opt_in` بی‌نتیجه
- [ناقص] کامنت: کلید `thread_comments` بی‌مصرف — تنظیم روشن/خاموش تودرتویی seed شده ولی هیچ کدی آن را نمی‌خواند؛ فقط عمق دیدگاه مصرف می‌شود — شاهد: `backend/app/modules/settings/application/default_options.py:77`؛ `backend/app/modules/blog/application/comment_service.py:191-196`
- [ناقص] کامنت: فیلد چک‌باکس «اطلاع از دیدگاه‌های بعدی» — فرم دیدگاه هیچ گزینه‌ی اشتراک اعلان پاسخ ندارد — شاهد: جست‌وجوی `notify|subscribe` در `frontend/components/blog/blog-comments.tsx` بی‌نتیجه
- [نداریم] کامنت: گزینه‌های آواتار دیدگاه (`show_avatars`/`avatar_default`/`avatar_rating`) — پارامترهای گراواتار ثابت `d=mp, r=g` هستند — شاهد: `backend/app/shared/content/gravatar.py:20-43`؛ جست‌وجوی `show_avatars|avatar_rating` بی‌نتیجه
- [نداریم] مدیا: صفحه‌ی پیوست (Attachment page) — هر فایل فقط URL مستقیم دارد و هیچ صفحه‌ی عمومی با متادیتا/دیدگاه وجود ندارد — شاهد: جست‌وجوی `attachment` در `frontend/app/(store)` بی‌نتیجه
- [نداریم] مدیا: تاکسونومی پیوست (دسته/برچسب رسانه) — جست‌وجوی تاکسونومی برای رسانه بی‌نتیجه (قابلیت `attachable-types` فقط برای ماژول اسناد است)
- [نداریم] مدیا: دسته‌بندی فایل در پوشه‌ی سال/ماه — گزینه‌ی `uploads_use_yearmonth_folders` seed می‌شود ولی هیچ کدی آن را نمی‌خواند و ذخیره تخت است — شاهد: `backend/app/modules/settings/application/default_options.py:93`؛ `backend/app/modules/media/application/storage_paths.py`
- [نداریم] مدیا: تصاویر استوک (Openverse) — جست‌وجو و درج تصویر آزاد وجود ندارد — شاهد: جست‌وجوی `openverse` در `backend/app` و `frontend` بی‌نتیجه
- [نداریم] مدیا: پلی‌لیست صوتی/تصویری و پخش‌کننده — جست‌وجوی `playlist|mediaelement` در کل پروژه صفر نتیجه
- [نداریم] مدیا: متادیتای ID3 صوت — فقط بایت جادویی برای تشخیص نوع خوانده می‌شود و عنوان/هنرمند/مدت خوانده نمی‌شود — شاهد: `backend/app/modules/media/application/media_service.py:128`؛ جست‌وجوی `mutagen|id3` بی‌نتیجه
- [نداریم] مدیا: آپلود فایل‌های دیگر (`unfiltered_upload`) — فقط image/pdf/audio/video مجاز است و zip/docx و… آپلود نمی‌شود — شاهد: `ALLOWED_MIME_TYPES` در `backend/app/modules/media/application/media_service.py:60-78`
- [ناقص] مدیا: دیدگاه روی پیوست — دیدگاه چندریختی فقط `blog_post` و `cms_page` را پشتیبانی می‌کند — شاهد: `COMMENT_RESOURCE_TYPES` در `backend/app/modules/blog/domain/models.py:68-70`
- [نداریم] کاربران: بیوگرافی و وب‌سایت کاربر — `UserProfile` هیچ ستون `bio`/`website` ندارد و `author_service.py` با `getattr(profile,"bio")` همیشه None می‌خواند، پس صفحه‌ی نویسنده همیشه بدون بیو است — شاهد: `backend/app/modules/users/domain/models.py:80-108`؛ `backend/app/modules/blog/application/author_service.py:142`
- [نداریم] کاربران: زبان پنل و گزینه‌های شخصی هر کاربر — ستون `locale` در مدل کاربر نیست و ادمین فارسی ثابت است — شاهد: جست‌وجوی `locale` در `backend/app/modules/users` و `frontend/app/admin` بی‌نتیجه
- [نداریم] کاربران: طرح رنگی ادمین (Admin Color Schemes) — فقط روشن/تیره سراسری داریم و ۹ اسکیم رنگی وردپرس معادلی ندارد — شاهد: `frontend/components/layout/theme-toggle.tsx`؛ جست‌وجوی `admin_color|color_scheme` بی‌نتیجه — در WP: `wp-admin/css/colors/`
- [نداریم] داشبورد: ابزارک‌های محتوایی داشبورد — «نگاهی کلی»، Quick Draft، «فعالیت‌های اخیر» و Site Health Status و چیدمان ویجت‌ها نیست؛ داشبورد فقط KPI فروشگاهی دارد — شاهد: `frontend/app/admin/dashboard/page.tsx`؛ جست‌وجوی `quick.?draft` بی‌نتیجه — در WP: `wp-admin/includes/dashboard.php:68-92`
- [نداریم] داشبورد: لینک‌های پرش (Skip links) — «پرش به محتوا» در پوسته‌ی ادمین نیست — شاهد: جست‌وجوی `skip.*link|skip-to` در `frontend/app/admin/layout.tsx` و `frontend/components` بی‌نتیجه — در WP: `wp-admin/includes/menu-header.php:294`
- [نداریم] تنظیمات: صفحه‌ی نوشته‌ها (`page_for_posts`) — نمی‌توان صفحه‌ای را به‌عنوان «صفحه‌ی نوشته‌ها» تعیین کرد — شاهد: `backend/app/modules/settings/application/default_options.py:52-55`؛ جست‌وجوی `page_for_posts` بی‌نتیجه
- [ناقص] تنظیمات: محتوای فید (متن کامل/خلاصه) — کلید `rss_use_excerpt` خوانده می‌شود ولی نه seed شده و نه UI دارد — شاهد: `backend/app/modules/blog/api/routes.py:439-440`؛ `frontend/components/admin/content-settings-card.tsx`
- [نداریم] ابزارها: به‌روزرسانی نرم‌افزار از پنل (Core/Plugin/Theme/Language) — هیچ بررسی نسخه، نصب، بازگشت یا auto-update وجود ندارد — شاهد: جست‌وجوی `update_core|update-core|check_for_updates|auto_update` در `backend/app` و `frontend/app/admin` بی‌نتیجه — در WP: `wp-admin/update-core.php`
- [نداریم] ابزارها: نصب/حذف پلاگین از مخزن — جست‌وجوی `install_plugin|plugin-install` در `backend/app` و `frontend` بی‌نتیجه — شاهد WP: `wp-admin/plugin-install.php`
- [نداریم] ابزارها: نصب بسته‌ی زبان (Language Pack) — مدیریت ترجمه‌ی ما فقط رشته‌های UI داخلی است، نه نصب زبان — شاهد: جست‌وجوی `language_pack|install_language|gettext` در `backend/app` بی‌نتیجه — در WP: `wp-admin/options-general.php`
- [نداریم] ابزارها: مهاجرت HTTPS — فقط تشخیص در Site Health هست و ابزار مهاجرت/اجبار SSL نیست — شاهد: جست‌وجوی `force_ssl|https_migration` بی‌نتیجه؛ `backend/app/modules/settings/application/content_health_service.py:219`
- [نداریم] ابزارها: صفحات About / Credits / Freedoms — هیچ معادلی در پنل نیست — شاهد: جست‌وجوی `credits|freedoms|about.php` در `frontend/app/admin` بی‌نتیجه
- [ناقص] ابزارها: فیلترهای خروجی — صادرات فیلتر نویسنده/بازه‌ی زمانی/نوع ندارد — شاهد: `export_all` در `backend/app/modules/blog/application/transfer_service.py`
- [ناقص] ابزارها: خالی‌کردن سطل زباله — نه دکمه‌ی «خالی‌کردن زباله‌دان» در فهرست هست و نه تسک زمان‌بندی‌شده‌ی `EMPTY_TRASH_DAYS`؛ فقط هشدار سلامت محتوا هست — شاهد: `backend/app/modules/settings/application/content_health_service.py:80-92`؛ جست‌وجوی `EMPTY_TRASH|purge_trash|trash_days` صفر نتیجه
- [ناقص] ابزارها: تعمیر دیتابیس — فقط ANALYZE اجرا می‌شود و معادل «تعمیر دیتابیس» وردپرس نیست — شاهد: `backend/app/modules/settings/api/routes.py:628` — در WP: `wp-admin/maint/repair.php`
- [نداریم] REST: endpoint دسته‌ای (`/batch/v1`) — ارسال چند درخواست در یک HTTP وجود ندارد — شاهد: جست‌وجوی `/batch/v1` در `backend/app` بی‌نتیجه (فقط `/cards/batch` و `/upload/batch` دامنه‌ای) — در WP: `wp-includes/rest-api/class-wp-rest-server.php:157`
- [نداریم] REST: پارامترهای `_fields`/`_embed` و هدر `X-WP-Total` — جست‌وجوی `_fields|_embed|X-WP-Total` در `backend/app` صفر نتیجه
- [نداریم] REST: API ایندکس کشف مسیرها — هیچ `GET /` سبک wp-json با فهرست routeها و namespaceهای عمومی نیست — شاهد: جست‌وجوی `wp-json|rest_index` در `backend/app` بی‌نتیجه
- [نداریم] REST: نقطه‌ی ثبت route توسط افزونه/ماژول ثالث (`register_rest_route`) — فهرست routerها در `backend/app/main.py` ثابت است — شاهد: `_include_routers` در `backend/app/main.py`
- [نداریم] REST: XML-RPC — کاملاً غایب است، پس هیچ ابزار یا اپ قدیمی وردپرسی وصل نمی‌شود — شاهد: جست‌وجوی `xmlrpc|xml-rpc|metaweblog` در `backend/app` و `frontend` بی‌نتیجه
- [نداریم] REST: RSD و هدرهای کشف سرویس (EditURI، `X-Pingback`) — وجود ندارند — شاهد: جست‌وجوی `rsd|EditURI|X-Pingback|wlwmanifest` در `frontend/app/layout.tsx` و `backend/app` بی‌نتیجه
- [ناقص] REST: جریان authorize-application و صفحه‌ی رضایت اپ — Application Passwords کامل است ولی صفحه‌ی تأیید درخواست اپ خارجی با `success_url` وجود ندارد و فقط Bearer پذیرفته می‌شود — شاهد: `backend/app/modules/auth/api/routes.py:728-816`؛ `backend/app/core/security/dependencies.py:62`
- [نداریم] فید: فید نویسنده — هیچ مسیر `/author/{slug}/feed` وجود ندارد — شاهد: فهرست مسیرهای `/feed` در `backend/app/modules/blog/api/routes.py:447-641` — در WP: `wp-includes/link-template.php:876`
- [نداریم] فید: فید جست‌وجو (Search feed) — جست‌وجوی `search` در `backend/app/modules/blog/application/feed_service.py` بی‌نتیجه
- [نداریم] فید: فید برای انواع پست سفارشی — فید فقط برای posts/categories/tags است — شاهد: جست‌وجوی `CustomPostEntry|content-types` در `backend/app/modules/blog/application/feed_service.py` بی‌نتیجه
- [ناقص] فید: فید RDF — ساختار درست است ولی `dc:date` با قالب RFC 822 تولید می‌شود در حالی که RSS 1.0 وردپرس ISO 8601 می‌فرستد و `dc:creator` همیشه خالی است — شاهد: `backend/app/modules/blog/application/feed_service.py:36-40,628-644` در برابر `wp-includes/feed-rdf.php:79`
- [ناقص] فید: فید Atom دیدگاه‌ها و RSS 0.92 — فید فقط RSS دیدگاه‌ها را دارد — شاهد: `build_rss_xml`/`build_atom_xml`/`build_comments_rss_xml` در `backend/app/modules/blog/application/feed_service.py`؛ جست‌وجوی `0.92` بی‌نتیجه
- [ناقص] فید: فید Atom دسته/برچسب — بک‌اند `/feed/atom/{slug}` دارد ولی مسیر فروشگاهی فقط RSS ترم است — شاهد: `backend/app/modules/blog/api/routes.py:641`؛ `frontend/app/blog/feed/rss/category/[slug]/route.ts`
- [ناقص] فید: فید دیدگاه هر نوشته — مسیر بک‌اند هست ولی هیچ لینک یا route فرانتی ندارد — شاهد: `backend/app/modules/blog/api/routes.py:590`؛ `frontend/app/feed/comments/rss/route.ts`
- [نداریم] چندسایته: Multisite / Network Admin — ادمین شبکه، ساخت/حذف سایت و کاربران شبکه وجود ندارد — شاهد: جست‌وجوی `multisite|network_admin|wp_blogs` در `backend/app` و `frontend` بی‌نتیجه — در WP: `wp-admin/network.php` و `ms-*.php`
- [نداریم] چندسایته: Abilities API — رجیستری قابلیت‌های نام‌دار با دسته‌بندی و endpoint اجرا وجود ندارد — شاهد: جست‌وجوی `register_ability|abilities-api|abilitiesV1` در `backend/app` بی‌نتیجه (تنها hit نامرتبط `core/security/object_capabilities.py`) — در WP: `wp-includes/abilities-api/`
- [نداریم] چندسایته: AI Client و Connectors API — هیچ کلاینت LLM یا رجیستری کانکتور AI و صفحه‌ی `options-connectors` وجود ندارد — شاهد: جست‌وجوی `ai_client|ai-client|openai|anthropic|llm` در `backend/app` و `frontend/lib` بی‌نتیجه — در WP: `wp-includes/ai-client/` و `wp-admin/options-connectors.php`
- [نداریم] چندسایته: Speculation Rules API (prefetch/prerender) — جست‌وجوی `speculation` در `frontend/app`, `frontend/components`, `frontend/lib` و `next.config.ts` بی‌نتیجه — در WP: `wp-includes/class-wp-speculation-rules.php`
- [نداریم] چندسایته: View Transitions — جست‌وجوی `viewTransition|view-transition` در `frontend/` بی‌نتیجه — در WP: `wp-includes/view-transitions.php`
- [نداریم] چندسایته: Interactivity API (وضعیت کلاینتی بلاک‌ها) — معادل عملکردی React هست ولی هیچ API عمومی برای بلاک‌های تعاملی نیست — شاهد: جست‌وجوی `interactivity|data-wp-` در `frontend/` بی‌نتیجه — در WP: `wp-includes/interactivity-api/`
- [نداریم] چندسایته: HTML API سمت سرور (Tag Processor) — هیچ پردازنده‌ی ساختاری HTML برای دستکاری مطمئن مارک‌آپ نیست و فقط پاک‌سازی allowlist با bleach داریم — شاهد: `backend/app/shared/content/html_sanitizer.py`؛ جست‌وجوی `TagProcessor|html-api` صفر نتیجه
- [نداریم] چندسایته: پرچم `wp_supports_ai` و بلوک‌های هوش مصنوعی — وجود ندارد — شاهد: جست‌وجوی `wp_supports_ai` در پروژه بی‌نتیجه
- [ناقص] حریم خصوصی: رجیستری افزودنی eraser/exporter — فهرست منابع ثابت است و نقطه‌ی ثبت بیرونی وجود ندارد — شاهد: `backend/app/modules/settings/application/privacy_core_sources.py`
- [ناقص] امنیت: کپابیلیتی `unfiltered_html` — هیچ نقشی (حتی مدیر) نمی‌تواند HTML خام ذخیره کند چون sanitizer برای همه یکسان اجرا می‌شود — شاهد: `backend/app/shared/content/html_sanitizer.py`؛ جست‌وجوی `unfiltered_html` در پروژه بی‌نتیجه
- [ناقص] i18n: تاریخچه‌ی رشته‌ها — هرچند سرویس ترجمه‌ی گروهی دارد، بدون مصرف‌کننده در UI است — شاهد: `backend/app/modules/settings/application/i18n_service.py:87-310`؛ جست‌وجوی `translate(` در `frontend` بی‌نتیجه
- [ناقص] پلاگین: رجیستری پلاگین — فقط هوک و toggle داریم و هیچ پلاگینی ثبت نشده است، پس UI همیشه خالی خواهد بود تا کد پلاگین نوشته شود — شاهد: `backend/app/shared/plugins/registry.py:69-140`؛ جست‌وجوی `register_plugin(` در `backend/app` بدون فراخوان
- [ناقص] پلاگین: وابستگی و توقف خودکار افزونه‌های خراب (paused extensions) — سرآیند «Requires Plugins» و `resume_plugin` وجود ندارد — شاهد: جست‌وجوی `resume_plugin|plugin.dependencies` بی‌نتیجه
- [ناقص] پلاگین: صفحه‌ی پلاگین‌ها فقط رجیستری درون‌کدی را نشان می‌دهد و نصب/آپلود/حذف/به‌روزرسانی از مخزن و ویرایشگر فایل افزونه نیست — شاهد: `frontend/app/admin/plugins/page.tsx:30-34` («introspection»)؛ `backend/app/modules/content/api/routes.py:1059-1097` (فقط list/toggle)
- [ناقص] ایمیل: «ایمیل تأیید ادمین» و جریان `new_admin_email` — وجود ندارد — شاهد: جست‌وجوی `admin_email_verification|new_admin_email` بی‌نتیجه

