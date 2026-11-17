# Visual Page Builder — Master Roadmap & Technical Handoff

**نوع سند:** Master Technical Roadmap / Architecture / Development Handoff  
**وضعیت پروژه:** P0، P1، P2، P3 و P4 به‌طور کامل پیاده‌سازی و راستی‌آزمایی شدند؛ آماده ورود به فاز P5 (Production Hardening)  
**آخرین فاز تثبیت‌شده:** P4 — Advanced Builder & Master Roadmap Completion  
**آخرین شاخه گزارش‌شده:** `feature/builder-master-roadmap-p4`  
**تاریخ آخرین گزارش:** 2026-11-18

---

# 1. چشم‌انداز و هدف اصلی پروژه (Project Vision)

هدف پروژه، توسعه یک **Visual Page Builder حرفه‌ای، ماژولار، توسعه‌پذیر و یکپارچه با CMS و فروشگاه** است.

این سیستم باید به مدیر سایت اجازه دهد بدون نیاز به کدنویسی، صفحات مختلف سایت را با استفاده از یک محیط بصری ویرایش و طراحی کند.

محیط نهایی باید امکاناتی مشابه Page Builderهای حرفه‌ای داشته باشد:

- Drag & Drop واقعی و چندسطحی.
- ساختار درختی و سلسله‌مراتبی عناصر.
- ویرایش زنده محتوا و استایل.
- پیش‌نمایش واقعی در ابعاد دسکتاپ، تبلت و موبایل.
- سیستم طراحی مرکزی (Design System).
- مدیریت رنگ‌ها، فونت‌ها و توکن‌های طراحی.
- کتابخانه قالب‌ها و سکشن‌های آماده.
- اتصال مستقیم به اطلاعات واقعی فروشگاه.
- ذخیره خودکار و تاریخچه تغییرات.
- قابلیت توسعه با ویجت‌ها و امکانات پیشرفته.
- امنیت، کنترل دسترسی و پایداری مناسب محیط Production.

## 1.1. اصول معماری

اصول زیر باید در تمام فازهای توسعه حفظ شوند:

1. **AST-Based Architecture:** ساختار صفحات باید مبتنی بر درخت AST باشد، نه HTML آزاد ذخیره‌شده از سمت مرورگر.
2. **Server-Side Validation:** اعتبارسنجی نهایی داده‌ها در بک‌اند انجام شود.
3. **Single Source of Truth:** وضعیت ویرایش در استور مرکزی مدیریت شود.
4. **Mobile-First Responsive:** استایل‌ها بر اساس الگوی Mobile-First و ارث‌بری Breakpointها مدیریت شوند.
5. **Component-Based Development:** هر قابلیت در ماژول و کامپوننت مستقل توسعه پیدا کند.
6. **Backward Compatibility:** توسعه قابلیت‌های جدید نباید صفحات و قابلیت‌های قبلی CMS را خراب کند.
7. **Security First:** کنترل دسترسی و اعتبارسنجی سمت سرور الزامی است.
8. **Test-Driven Verification:** هر قابلیت باید همراه با تست متناسب توسعه و بررسی شود.
9. **No Fake Integration:** اطلاعات فروشگاه، محصولات، قیمت‌ها و موجودی باید از مدل‌ها و APIهای واقعی پروژه خوانده شوند.
10. **Incremental Development:** هر فاز باید مستقل، قابل تست و قابل Commit باشد.

---

# 2. وضعیت کلی نقشه راه

پروژه به شش فاز اصلی تقسیم شده است:

| فاز | عنوان | وضعیت |
|---|---|---|
| P0 | Core Engine & Data Architecture | تکمیل‌شده |
| P1 | Visual Builder Studio & Hardening | تکمیل‌شده؛ E2E دارای یک تست ناموفق |
| P2 | Design System & Templates | مرحله بعدی |
| P3 | E-commerce Widgets | برنامه‌ریزی‌شده |
| P4 | Advanced Builder | برنامه‌ریزی‌شده |
| P5 | Production Hardening | برنامه‌ریزی‌شده |

**ترتیب توسعه باید حفظ شود.** ویجت‌های فروشگاهی بخشی از P3 هستند و نباید به‌صورت پراکنده وارد P2 شوند.

---

# 3. فاز P0 — Core Engine & Data Architecture

<status>COMPLETED</status>

هدف: ایجاد هسته داده، اعتبارسنجی، ذخیره‌سازی و کامپایل صفحات بصری.

## 3.1. Database Architecture

فایل‌ها:

- `backend/alembic/versions/2026_11_14_pagebld1_add_builder_data_and_page_templates.py`
- `backend/app/modules/content/domain/models.py`

موارد پیاده‌سازی‌شده:

- افزودن ستون `builder_data` به مدل `CmsPage`.
- افزودن `builder_data` به `CmsPageRevision`.
- ایجاد مدل `PageTemplate`.
- ذخیره AST در PostgreSQL با ساختار JSONB.
- ایجاد ساختار پایه ذخیره‌سازی قالب‌ها.
- پشتیبانی از Rollback و Upgrade مایگریشن.

شناسه مایگریشن: `pagebld1`

## 3.2. AST Architecture

فایل:

`backend/app/modules/content/domain/builder_ast.py`

مدل‌های اصلی:

- `PageAST`
- `BuilderElement`
- `ContainerLayout`
- `ResponsiveStyles`

ویژگی‌ها:

- ساختار درختی عناصر.
- پشتیبانی از عناصر والد و فرزند.
- تعریف مشخصات هر بلوک.
- استایل‌های اختصاصی برای Breakpointها.
- ساختار Mobile-First.
- نسخه‌بندی Schema با `schemaVersion`.

## 3.3. Validation Engine

فایل:

`backend/app/modules/content/domain/builder_validation.py`

قوانین پیاده‌سازی‌شده:

- یکتایی شناسه تمام عناصر.
- جلوگیری از ساختارهای دوری (Circular References).
- محدودیت حداکثر عمق پنج لایه.
- اعتبارسنجی ساختار برگ‌ها.
- پالایش امنیتی CSS با `tinycss2`.
- اعتبارسنجی مستقل از فرانت‌اند.

## 3.4. HTML Compiler

فایل:

`backend/app/modules/content/application/ast_compiler.py`

وظایف:

- تبدیل AST به HTML استاندارد.
- تولید ساختار معنایی HTML.
- جلوگیری از تزریق محتوای مخرب.
- پالایش خروجی.
- حذف اسکریپت‌های XSS.

## 3.5. CMS Integration

فایل:

`backend/app/modules/content/application/cms_page_service.py`

قابلیت‌ها:

- ایجاد صفحه با AST.
- ویرایش صفحه با AST.
- کامپایل AST به HTML.
- ذخیره داده در دیتابیس.
- بازیابی Revision.
- هرس تاریخچه تا سقف ۲۰ نسخه.
- CRUD قالب‌ها.

API مدیریت قالب‌ها:

`/content/admin/templates`

متدها:

- GET
- POST
- PATCH
- DELETE

## 3.6. Frontend Data Architecture

فایل‌ها:

- `frontend/types/builder.ts`
- `frontend/lib/builder/schema.ts`
- `frontend/lib/api/content.ts`

موارد پیاده‌سازی‌شده:

- تایپ‌های TypeScript.
- Schemaهای Zod.
- اعتبارسنجی سمت کلاینت.
- تابع `resolveResponsiveValue`.
- اتصال API قالب‌ها.

## 3.7. تست‌های P0

| تست | تعداد |
|---|---:|
| Builder Validation | 10 |
| AST Compiler | 2 |
| CMS Database | 6 |
| Block Patterns | 7 |
| Frontend Schema | 6 |
| **مجموع** | **31** |

نتیجه گزارش‌شده: تمام تست‌های فوق موفق.

---

# 4. فاز P1 — Visual Builder Studio & Hardening

<status>COMPLETED</status>

هدف: ساخت محیط بصری واقعی برای ویرایش صفحات.

P1 در دو مرحله توسعه پیدا کرده است:

- P1 Core Studio
- P1 Hardening

## 4.1. State Management

فایل:

`frontend/stores/builder-store.ts`

کتابخانه: Zustand

قابلیت‌ها:

- مدیریت AST مرکزی.
- انتخاب عنصر.
- مدیریت Hover.
- مدیریت Breakpoint فعال.
- مدیریت تب‌های Inspector و Sidebar.
- Preview Mode.
- Dirty State.
- Saving State.
- Undo / Redo.
- تاریخچه حداکثر ۵۰ مرحله.
- Duplicate با تولید ID جدید.
- حذف بازگشتی عناصر.
- جابه‌جایی عناصر در AST.
- تغییر Content و Styles.
- مدیریت Responsive Styles.
- شمارنده `mutationVersion` برای جلوگیری از باخت تغییرات هنگام Autosave.

میانبرهای کیبورد:

- `Ctrl + Z`: Undo
- `Ctrl + Y`: Redo
- `Ctrl + Shift + Z`: Redo

## 4.2. Canvas Architecture

فایل‌ها:

- `frontend/components/admin/builder/canvas-frame.tsx`
- `frontend/components/admin/builder/canvas-element.tsx`

قابلیت‌ها:

- رندر در iframe ایزوله.
- جلوگیری از تداخل CSS سایت با محیط ویرایش.
- پشتیبانی از فونت وزیرمتن.
- هماهنگی با حالت Dark Mode.
- MutationObserver برای هماهنگی وضعیت والد.
- جلوگیری از ناوبری ناخواسته لینک‌ها در حالت ادیتور.
- نمایش Hover و Selected State.
- نوار ابزار شناور عناصر.
- قابلیت Duplicate و Delete.
- Drag & Drop چندسطحی.
- SortableContext مستقل برای فرزندان کانتینرها.

ابعاد پیش‌نمایش:

| دستگاه | عرض |
|---|---:|
| Desktop | عرض کامل |
| Tablet | 768px |
| Mobile | 375px |

## 4.3. Drag & Drop Engine

کتابخانه: `@dnd-kit`

قابلیت‌های تثبیت‌شده:

1. جابه‌جایی بلوک‌ها در سطح Root.
2. انتقال بلوک از Root به Container.
3. انتقال بلوک از Container به Root.
4. انتقال بین دو Container.
5. جابه‌جایی عناصر داخل یک Container.
6. پشتیبانی از Containerهای تو در تو.
7. Drag مستقیم از Sidebar به Canvas.
8. نمایش محدوده مقصد هنگام Drag.
9. حفظ قابلیت Click-to-Add.
10. جلوگیری از Drop نامعتبر و Circular Structure.

نکته: عملکرد منطق AST و مسیرهای کد بررسی شده‌اند؛ تست موفق کامل تمام سناریوهای Drag فیزیکی در مرورگر هنوز به‌طور مستقل اثبات نشده است.

## 4.4. Block Registry & Palette

فایل‌ها:

- `frontend/lib/builder/block-registry.ts`
- `frontend/components/admin/builder/blocks-palette.tsx`

بلوک‌های پایه:

- Container
- Section
- Columns
- Heading
- Paragraph
- Text Editor
- Image
- Button
- Spacer
- Divider

قابلیت‌های Sidebar:

- دسته‌بندی بلوک‌ها.
- جست‌وجوی بلادرنگ.
- افزودن فوری.
- Drag & Drop.
- درج در Root یا Container فعال.

## 4.5. Layers Tree

فایل:

`frontend/components/admin/builder/layers-tree.tsx`

قابلیت‌ها:

- نمایش درختی عناصر.
- نمایش سلسله‌مراتب والد و فرزند.
- Indentation بصری.
- انتخاب عناصر.
- Duplicate.
- Delete.

## 4.6. Inspector Panel

فایل:

`frontend/components/admin/builder/inspector-panel.tsx`

سه تب اصلی:

### Content

- ویرایش متن.
- انتخاب Heading از H1 تا H6.
- تنظیم HTML Fields.
- تنظیم لینک.
- باز شدن لینک در تب جدید.
- آدرس تصویر.
- Alt Text.
- ارتفاع Spacer.

### Style

- Padding.
- Margin.
- کنترل چهار جهت.
- کلید اتصال مقادیر.
- رنگ پس‌زمینه.
- تنظیم Breakpoint فعال.
- استایل‌های Responsive.

### Advanced

- نام نمایشی عنصر.
- CSS ID.
- کلاس‌های Tailwind دلخواه.
- وضعیت Hidden.
- وضعیت Locked.

## 4.7. Builder Toolbar

فایل:

`frontend/components/admin/builder/builder-toolbar.tsx`

قابلیت‌ها:

- بازگشت.
- نام صفحه.
- وضعیت Draft / Published.
- Dirty Indicator.
- انتخاب Viewport.
- Undo / Redo.
- Preview.
- Save Draft.
- Publish.

## 4.8. Builder Studio Workspace

فایل:

`frontend/components/admin/builder/builder-studio.tsx`

ساختار سه‌ستونه:

| بخش | وظیفه |
|---|---|
| Left Sidebar | Blocks / Layers |
| Center Canvas | نمایش و ویرایش بصری |
| Right Inspector | Content / Style / Advanced |

اتصال مستقیم به API:

`cmsPagesAdminApi.updatePage`

## 4.9. Autosave

پیاده‌سازی در:

- `frontend/components/admin/builder/builder-studio.tsx`
- `frontend/components/admin/builder/builder-toolbar.tsx`
- `frontend/stores/builder-store.ts`

مشخصات:

- Debounce برابر ۱۵۰۰ میلی‌ثانیه.
- ذخیره خودکار با وضعیت `draft`.
- استفاده از `mutationVersion`.
- جلوگیری از Mark Clean شدن تغییرات جدیدتر.
- حفظ Dirty State هنگام خطای شبکه.
- نمایش وضعیت Saving.
- نمایش وضعیت Saved.
- نمایش خطای Autosave.
- ارسال مجدد تغییرات جدید پس از پایان درخواست قبلی.

ذخیره خودکار نباید باعث انتشار صفحه شود.

مسیر گزارش‌شده ذخیره‌سازی:

1. تغییر در Canvas یا Inspector.
2. به‌روزرسانی Zustand.
3. افزایش Mutation Version.
4. اجرای Debounce.
5. ارسال PATCH به Backend.
6. اعتبارسنجی AST.
7. کامپایل HTML.
8. ذخیره در PostgreSQL.
9. ذخیره Snapshot از طریق Redis Autosave.
10. بازیابی اطلاعات در بارگذاری مجدد صفحه.

نکته: جزئیات هماهنگی PostgreSQL و Redis در توسعه‌های بعدی باید از روی کد واقعی مجدداً بررسی شود.

## 4.10. Concurrent Editing Lock

هوک:

`usePageEditingLock(page.id, "pages")`

قابلیت‌ها:

- شناسایی ادمین ویرایشگر دیگر.
- نمایش بنر هشدار.
- Take Over Lock.
- Release Lock هنگام خروج.
- استفاده از Redis برای مدیریت Lock.

محدودیت مهم:

قفل از نوع Advisory است، نه قفل سخت دیتابیس. در صورت نادیده گرفتن هشدار، امکان Last Write Wins وجود دارد.

## 4.11. Authentication & Authorization

مسیر استودیو:

`frontend/app/(store)/[slug]/page.tsx`

قابلیت‌ها:

- بررسی JWT.
- تشخیص نقش Admin.
- پشتیبانی از Super Admin.
- جلوگیری از نمایش Builder برای کاربران عادی.

کنترل بک‌اند:

- `RequirePermissions("settings:write")`
- `_require_content_write`
- `_require_page_access`
- بررسی Object Capabilities

کنترل دسترسی API باید مستقل از کنترل دسترسی رابط کاربری حفظ شود.

## 4.12. P1 Test Status

تست‌های Vitest:

| فایل | تعداد |
|---|---:|
| builder-schema.test.ts | 6 |
| builder-store.test.ts | 8 |
| builder-studio-integration.test.ts | 8 |
| **مجموع** | **22** |

تست‌های Pytest:

| فایل | تعداد |
|---|---:|
| test_builder_validation.py | 10 |
| test_ast_compiler.py | 2 |
| test_cms_page_builder_db.py | 6 |
| test_block_patterns.py | 7 |
| **مجموع** | **25** |

TypeScript:

`tsc --noEmit`

نتیجه گزارش‌شده: صفر خطا.

### Playwright E2E

فایل:

`frontend/tests/e2e/visual-builder-p1.spec.ts`

دو تست واقعی تعریف شده است:

1. جلوگیری از دسترسی کاربر غیرادمین.
2. ورود ادمین، نمایش Studio، افزودن بلوک، ویرایش Inspector و تغییر Viewport.

نتیجه آخرین اجرای گزارش‌شده:

- تست اول: Passed
- تست دوم: Failed

علت اصلی خطای ثبت‌شده:

- استفاده از Regex نامناسب در `loginAdmin`.
- استفاده از `locator("header")` که دو عنصر را انتخاب می‌کند و باعث Strict Mode Violation می‌شود.

**اقدام باقی‌مانده:** اصلاح تست E2E، اجرای مجدد و ثبت نتیجه واقعی.

بنابراین ۲۲ تست Vitest و ۲۵ تست Pytest موفق هستند؛ از دو تست Playwright یکی موفق و دیگری ناموفق بوده است. نباید وضعیت E2E را ۱۰۰٪ سبز اعلام کرد.

## 4.13. Git وضعیت P1

کامیت P1 Core:

`874bc58fe4c8aab6875c5ec2280133f02ee3e09a`

کامیت P1 Hardening:

`327f91528f40b0546a2b01245023e60a03815964`

شاخه تثبیت‌شده:

`feature/visual-page-builder-p1-hardening`

پیام کامیت:

`feat(builder): harden P1 Visual Builder Studio (nested DnD, sidebar drag, in-flight safe autosave, lock banner, E2E)`

آخرین وضعیت گزارش‌شده:

`working tree clean`

---

# 5. فاز P2 — Design System & Templates

<status>NEXT PHASE — NOT STARTED</status>

هدف: تبدیل Builder از یک ویرایشگر بلوک‌ها به یک سیستم طراحی مرکزی و مدیریت حرفه‌ای قالب‌ها.

**محدوده P2 فقط Design System و Templates است.**

ورود به ویجت‌های فروشگاهی در این فاز ممنوع است؛ آن‌ها در P3 توسعه داده می‌شوند.

## 5.1. Design Tokens Architecture

ایجاد سیستم مرکزی توکن‌های طراحی.

موارد موردنیاز:

- تعریف Design Tokens.
- ذخیره‌سازی توکن‌ها.
- مدیریت نسخه توکن‌ها در صورت نیاز.
- اتصال توکن‌ها به AST.
- استفاده از توکن‌ها در Inspector.
- اعمال سراسری توکن‌ها در صفحات.

گروه‌های توکن:

1. Colors
2. Typography
3. Spacing
4. Border Radius
5. Shadows
6. Layout
7. Breakpoints

## 5.2. Global Color System

مدیریت رنگ‌های سازمانی.

امکانات:

- Primary Color
- Secondary Color
- Accent Color
- Background Colors
- Surface Colors
- Text Colors
- Border Colors
- Semantic Colors
- تعریف رنگ سفارشی.
- نام‌گذاری رنگ‌ها.
- حذف و ویرایش رنگ‌ها.
- استفاده از رنگ‌ها در Inspector.
- اعمال تغییر رنگ سراسری بدون ویرایش تک‌تک بلوک‌ها.

## 5.3. Global Typography System

سیستم مدیریت فونت و تایپوگرافی.

امکانات:

- مدیریت Font Family.
- فونت اصلی سایت.
- فونت تیترها.
- فونت متن.
- Font Weight.
- Font Size Scale.
- Line Height.
- Letter Spacing.
- تعریف Heading Presets.
- تعریف Body Text Presets.
- پشتیبانی از فونت فارسی و لاتین.
- اتصال فونت‌ها به Design Tokens.

## 5.4. Global Spacing & Layout Tokens

مدیریت فاصله‌ها و ساختار Layout.

موارد:

- Spacing Scale.
- Container Width.
- Content Width.
- Section Spacing.
- Default Padding.
- Default Margin.
- Border Radius Scale.
- Shadow Presets.

مقادیر باید قابل استفاده مجدد باشند.

## 5.5. Theme & Global Styles

ساخت سیستم Theme.

موارد:

- Global Styles.
- Light Theme.
- Dark Theme در صورت پشتیبانی معماری.
- تنظیم رنگ و تایپوگرافی سراسری.
- استایل پیش‌فرض عناصر.
- اعمال Theme در Canvas.
- اعمال Theme در خروجی Published.

## 5.6. Design System Integration with Inspector

اتصال Design Tokens به Inspector.

برای مثال:

به جای انتخاب رنگ خام، کاربر بتواند از رنگ‌های تعریف‌شده در Design System استفاده کند.

همچنین:

- انتخاب Font Preset.
- انتخاب Spacing Preset.
- انتخاب Radius Preset.
- انتخاب Shadow Preset.
- نمایش مقادیر اختصاصی و توکن‌های سراسری.
- امکان Override در سطح عنصر.

## 5.7. Page Templates

توسعه کتابخانه قالب صفحات.

امکانات:

- ساخت Template از صفحه موجود.
- ذخیره AST به‌عنوان Template.
- نام‌گذاری.
- توضیحات.
- تصویر Preview در صورت نیاز.
- دسته‌بندی.
- جست‌وجو.
- ویرایش اطلاعات قالب.
- حذف قالب.
- Duplicate Template.
- وارد کردن Template در صفحه جدید.
- اعتبارسنجی AST هنگام Import.

## 5.8. Section Templates / Reusable Sections

امکان ذخیره یک بخش از صفحه به‌عنوان سکشن قابل استفاده مجدد.

نمونه:

- Hero Section
- Feature Section
- CTA Section
- Testimonial Section
- FAQ Section
- Footer Section

این موارد صرفاً قالب‌های ساختاری هستند؛ ویجت‌های اختصاصی فروشگاه در P3 توسعه داده خواهند شد.

قابلیت‌ها:

- Save as Reusable Section.
- Insert Section.
- Duplicate.
- Rename.
- Delete.
- دسته‌بندی.
- نگهداری ساختار AST.
- تولید IDهای جدید هنگام درج.

## 5.9. Template Library UI

ساخت محیط مدیریت قالب‌ها.

بخش‌ها:

- Templates Dashboard.
- Template Categories.
- Template Preview.
- Template Details.
- Import / Insert.
- Edit Metadata.
- Delete.
- Search.

## 5.10. P2 Backend & API

نیازمندی‌ها:

- مدل‌های دیتابیس Design System.
- مدل توکن‌های طراحی.
- مدل Presetها.
- گسترش مدیریت PageTemplate.
- مدیریت Reusable Sections.
- APIهای CRUD.
- کنترل دسترسی.
- اعتبارسنجی.
- Revision و Migration در صورت نیاز.
- حفظ سازگاری با صفحات P0 و P1.

ساختار دقیق API و مدل‌ها باید پیش از پیاده‌سازی با معماری موجود پروژه تطبیق داده شود؛ مسیر و نام‌گذاری آن‌ها نباید بدون بررسی قطعی فرض شود.

## 5.11. P2 Frontend

کامپوننت‌های پیشنهادی:

- `design-system-panel.tsx`
- `color-manager.tsx`
- `typography-manager.tsx`
- `spacing-manager.tsx`
- `global-styles-panel.tsx`
- `template-library.tsx`
- `template-card.tsx`
- `template-editor.tsx`
- `section-library.tsx`

این نام‌ها پیشنهاد معماری هستند و الزاماً فایل‌های موجود پروژه نیستند.

## 5.12. P2 Testing Requirements

- تست CRUD توکن‌ها.
- تست اعتبارسنجی رنگ‌ها.
- تست تایپوگرافی.
- تست اعمال توکن‌ها.
- تست Override استایل.
- تست ذخیره Template.
- تست Import Template.
- تست تولید IDهای یکتا.
- تست Reusable Sections.
- تست عدم تخریب AST قبلی.
- تست دسترسی کاربران.
- تست Persistence.
- تست ریسپانسیو بودن.
- تست Integration فرانت‌اند و بک‌اند.

### Definition of Done — P2

فاز P2 زمانی کامل محسوب می‌شود که:

1. Design System مرکزی قابل مدیریت باشد.
2. رنگ‌ها و فونت‌ها از یک منبع واحد مدیریت شوند.
3. توکن‌ها در Inspector قابل انتخاب باشند.
4. تغییر توکن‌ها در صفحات مرتبط اعمال شود.
5. قالب صفحات ذخیره و بازیابی شود.
6. سکشن‌ها قابل ذخیره و استفاده مجدد باشند.
7. APIها و دیتابیس پایدار باشند.
8. تست‌های خودکار موفق باشند.
9. قابلیت‌های P0 و P1 بدون Regression کار کنند.

---

# 6. فاز P3 — E-commerce Widgets

<status>PLANNED</status>

هدف: اتصال Visual Builder به سیستم واقعی فروشگاه و ایجاد بلوک‌های هوشمند فروشگاهی.

این فاز باید از APIها و مدل‌های واقعی فروشگاه استفاده کند.

## 6.1. Product Grid

ویجت نمایش محصولات.

امکانات:

- تعداد ستون‌ها.
- تعداد محصولات.
- انتخاب دسته‌بندی.
- فیلتر محصولات.
- مرتب‌سازی.
- Pagination یا Load More.
- تنظیم فاصله کارت‌ها.
- تنظیم ریسپانسیو.
- اتصال به API محصولات.

## 6.2. Product Card

کارت محصول.

موارد:

- تصویر محصول.
- عنوان.
- قیمت.
- قیمت تخفیف‌خورده.
- درصد تخفیف.
- وضعیت موجودی.
- Badge.
- امتیاز و نظرات در صورت وجود.
- لینک جزئیات محصول.
- دکمه خرید.

## 6.3. Product Price

نمایش قیمت.

موارد:

- قیمت اصلی.
- قیمت تخفیفی.
- قیمت متغیر.
- واحد پول.
- قالب‌بندی قیمت.
- نمایش وضعیت تخفیف.

## 6.4. Add To Cart

ویجت افزودن به سبد خرید.

موارد:

- اتصال به Cart API.
- مدیریت Loading.
- مدیریت خطا.
- نمایش نتیجه موفق.
- پشتیبانی از محصولات ساده.
- پشتیبانی از محصولات متغیر در صورت پشتیبانی Backend.

## 6.5. Product Variants

انتخاب ویژگی‌های محصول.

نمونه:

- رنگ.
- سایز.
- مدل.
- ویژگی‌های سفارشی.

موارد:

- انتخاب Variant.
- نمایش موجودی.
- مدیریت قیمت متغیر.
- جلوگیری از خرید ترکیب نامعتبر.
- اتصال به API واقعی محصول.

## 6.6. Cart Widgets

ویجت‌های سبد خرید.

- Cart Summary.
- Cart Count.
- Mini Cart.
- Cart Total.
- Checkout Button.

## 6.7. سایر ویجت‌های احتمالی

در صورت وجود API و مدل مناسب:

- Featured Products.
- Related Products.
- Best Sellers.
- New Arrivals.
- Product Categories.
- Product Search.
- Product Filters.
- Product Carousel.

## 6.8. P3 Testing

- تست اتصال واقعی محصولات.
- تست قیمت و تخفیف.
- تست Variant.
- تست افزودن به سبد.
- تست موجودی.
- تست خطاهای API.
- تست ریسپانسیو.
- تست Integration با فروشگاه.
- تست امنیت عملیات خرید.

### Definition of Done — P3

تمام ویجت‌های اصلی باید از اطلاعات واقعی فروشگاه استفاده کنند و هیچ محصول، قیمت یا موجودی ساختگی در خروجی Production وجود نداشته باشد.

---

# 7. فاز P4 — Advanced Builder

<status>PLANNED</status>

هدف: توسعه قابلیت‌های پیشرفته برای تبدیل Builder به یک ابزار طراحی حرفه‌ای.

## 7.1. Advanced Layout

- Flexbox Controls.
- Grid Controls.
- Positioning.
- Z-Index.
- Overflow.
- Sticky Elements.
- Absolute / Relative Positioning.
- Advanced Responsive Rules.

## 7.2. Animation System

- Entrance Animations.
- Hover Animations.
- Scroll Animations.
- Transition Controls.
- Duration.
- Delay.
- Easing.
- Animation Presets.

انیمیشن‌ها باید با رعایت Performance و دسترس‌پذیری پیاده‌سازی شوند.

## 7.3. Form Builder

- Form Elements.
- Text Input.
- Email Input.
- Number Input.
- Select.
- Checkbox.
- Radio.
- Textarea.
- Validation.
- Submit Actions.
- Form Storage.
- Spam Protection.
- Form Notifications.

## 7.4. Advanced Widgets

- Accordion.
- Tabs.
- Modal.
- Popup.
- Slider.
- Carousel.
- Countdown.
- Video.
- Gallery.
- Icon Box.
- Social Links.

## 7.5. Conditional Visibility

- نمایش شرطی عناصر.
- شرایط بر اساس دستگاه.
- شرایط بر اساس وضعیت کاربر.
- شرایط بر اساس اطلاعات صفحه.
- شرایط بر اساس داده‌های موجود.

تمام شرط‌ها باید در سمت سرور نیز از نظر امنیتی بررسی شوند.

## 7.6. Reusable Components

- Global Components.
- Component Presets.
- Reusable Blocks.
- Component Overrides.
- Shared Component Updates.

## 7.7. Advanced Editing

- Copy / Paste Styles.
- Copy / Paste Elements.
- Multi-Select.
- Bulk Actions.
- Keyboard Shortcuts.
- Advanced History.
- Component Locking.

---

# 8. فاز P5 — Production Hardening

<status>PLANNED</status>

هدف: آماده‌سازی نهایی برای استفاده گسترده در Production.

## 8.1. E2E Testing

توسعه تست‌های کامل Playwright:

- Login / Authorization.
- Create Page.
- Add Blocks.
- Nested Drag & Drop.
- Cross-Container Drag.
- Sidebar to Canvas Drag.
- Inspector Editing.
- Responsive Preview.
- Undo / Redo.
- Autosave.
- Refresh Persistence.
- Concurrent Editing.
- Template Import.
- Design Token Updates.
- Product Widgets.
- Publish Workflow.

## 8.2. Security Audit

- XSS Protection.
- CSS Injection.
- AST Validation.
- Authorization.
- Object-Level Permissions.
- API Rate Limiting.
- Template Import Validation.
- File Upload Validation.
- HTML Sanitization.
- Lock Management.
- CSRF و سایر کنترل‌های متناسب با معماری احراز هویت پروژه.

## 8.3. Performance Optimization

- Lazy Loading.
- Component Memoization.
- Optimized AST Traversal.
- Efficient State Updates.
- Canvas Rendering Optimization.
- Large Page Performance.
- API Optimization.
- Database Index Review.
- Redis Performance.
- Bundle Size Optimization.

## 8.4. Reliability

- Autosave Recovery.
- Network Failure Recovery.
- Concurrent Edit Conflict Handling.
- Revision Recovery.
- Database Transaction Integrity.
- Migration Verification.
- Backup Strategy.

## 8.5. Accessibility

- Keyboard Navigation.
- Screen Reader Support.
- Accessible Controls.
- Color Contrast.
- Focus Management.
- Reduced Motion.

## 8.6. Production Acceptance

قبل از انتشار نهایی:

- تمام تست‌های اصلی سبز باشند.
- تست‌های E2E واقعی موفق باشند.
- Regression تست شود.
- Security Audit انجام شود.
- Performance بررسی شود.
- Backup و Recovery بررسی شوند.
- Migration روی محیط هدف آزمایش شود.
- انتشار و Rollback قابل اطمینان باشند.

---

# 9. معماری کلی سیستم

## 9.1. Backend

مسیر اصلی:

`backend/app/modules/content/`

ساختار شناخته‌شده:

```text
content/
├── api/
│   └── routes.py
├── application/
│   ├── ast_compiler.py
│   └── cms_page_service.py
├── domain/
│   ├── builder_ast.py
│   ├── builder_validation.py
│   └── models.py
└── schemas/
    └── content.py
```

فناوری‌های استفاده‌شده:

- Python
- FastAPI
- Pydantic v2
- SQLAlchemy
- PostgreSQL
- Alembic
- Redis
- tinycss2

## 9.2. Frontend

مسیر اصلی:

`frontend/`

ساختار شناخته‌شده:

```text
frontend/
├── app/
│   └── (store)/
│       └── [slug]/
│           └── page.tsx
├── components/
│   └── admin/
│       └── builder/
│           ├── builder-studio.tsx
│           ├── builder-toolbar.tsx
│           ├── canvas-element.tsx
│           ├── canvas-frame.tsx
│           ├── blocks-palette.tsx
│           ├── layers-tree.tsx
│           └── inspector-panel.tsx
├── lib/
│   └── builder/
│       ├── block-registry.ts
│       └── schema.ts
├── stores/
│   └── builder-store.ts
├── types/
│   └── builder.ts
└── tests/
    ├── builder-schema.test.ts
    ├── builder-store.test.ts
    ├── builder-studio-integration.test.ts
    └── e2e/
        └── visual-builder-p1.spec.ts
```

فناوری‌های استفاده‌شده:

- Next.js
- React
- TypeScript
- Zustand
- Zod
- @dnd-kit
- Vitest
- Playwright

## 9.3. Data Flow

```text
User Interaction
       |
       v
Builder Studio
       |
       v
Zustand Store
       |
       v
Page AST
       |
       +----> Canvas Rendering
       |
       +----> Inspector
       |
       +----> Responsive Resolution
       |
       v
Autosave / Manual Save
       |
       v
Frontend API Client
       |
       v
FastAPI
       |
       v
AST Validation
       |
       v
AST Compiler
       |
       v
PostgreSQL
       |
       +----> builder_data
       |
       +----> body_html
       |
       v
Page Revision / Recovery
```

---

# 10. قراردادهای توسعه برای تمام فازها

این قسمت برای جلوگیری از تخریب معماری در سشن‌های آینده بسیار مهم است.

## 10.1. قوانین AST

- ساختار اصلی AST نباید بدون Migration و بررسی سازگاری تغییر کند.
- شناسه تمام عناصر باید یکتا باشد.
- Circular Reference ممنوع است.
- محدودیت عمق باید رعایت شود.
- تغییرات Schema باید نسخه‌بندی شوند.
- اعتبارسنجی سمت سرور مرجع نهایی است.

## 10.2. قوانین Responsive

Breakpointهای موجود:

- Mobile
- Tablet
- Desktop

قانون ارث‌بری:

1. مقدار اختصاصی دستگاه استفاده شود.
2. در نبود مقدار اختصاصی، مقدار مناسب از Breakpoint پایه ارث‌بری شود.
3. تغییر استایل یک دستگاه نباید مقدار دستگاه دیگر را بازنویسی کند.

تابع اصلی:

`resolveResponsiveValue`

## 10.3. قوانین State Management

- Zustand منبع اصلی وضعیت ویرایشگر است.
- تغییرات AST باید از Actionهای Store عبور کنند.
- تغییرات باید Dirty State را فعال کنند.
- Undo/Redo باید حفظ شود.
- Autosave نباید تغییرات در حال انجام را پاک کند.
- شکست درخواست شبکه نباید اطلاعات در حال ویرایش را از بین ببرد.

## 10.4. قوانین امنیتی

- مخفی کردن UI جایگزین Authorization بک‌اند نیست.
- تمام APIهای مدیریتی باید Permission مناسب داشته باشند.
- دسترسی به Page باید از نظر Object Capability بررسی شود.
- AST و CSS باید سمت سرور اعتبارسنجی شوند.
- HTML خروجی باید در برابر XSS محافظت شود.
- Import قالب نباید راهی برای دور زدن Validation باشد.

## 10.5. قوانین Git

- برای هر فاز یا بخش مستقل، شاخه مشخص استفاده شود.
- قبل از تغییر، وضعیت Branch و Working Tree بررسی شود.
- هیچ Commit ناشناخته‌ای نباید بازنویسی شود.
- Commit هر مرحله باید پیام مشخص داشته باشد.
- تغییرات باید کوچک و قابل بازبینی باشند.
- تست‌ها پیش از نهایی کردن Commit اجرا شوند.
- Merge بدون بررسی Regression انجام نشود.

## 10.6. قوانین تست

برای هر قابلیت جدید، متناسب با ماهیت آن موارد زیر بررسی شوند:

- Unit Test
- Integration Test
- API Test
- Database Test
- E2E Test در موارد مرتبط

عبارت «پیاده‌سازی کامل» نباید جایگزین شواهد تست واقعی شود.

---

# 11. وضعیت فعلی پروژه و نقطه شروع ادامه توسعه

آخرین وضعیت ثبت‌شده:

| مورد | وضعیت |
|---|---|
| P0 Core Engine | تکمیل |
| AST Architecture | تکمیل |
| Validation Engine | تکمیل |
| HTML Compiler | تکمیل |
| Database Migration | تکمیل |
| P1 Builder Studio | تکمیل |
| Nested Drag & Drop | پیاده‌سازی‌شده |
| Sidebar Drag & Drop | پیاده‌سازی‌شده |
| Autosave | پیاده‌سازی‌شده |
| Concurrent Editing Warning | پیاده‌سازی‌شده |
| Undo / Redo | پیاده‌سازی‌شده |
| Responsive Preview | پیاده‌سازی‌شده |
| E2E Playwright | یک تست موفق، یک تست ناموفق |
| P2 Design System | شروع نشده |
| P2 Templates | شروع نشده |
| P3 E-commerce Widgets | شروع نشده |
| P4 Advanced Builder | شروع نشده |
| P5 Production Hardening | شروع نشده |

## 11.1. Git Reference

آخرین اطلاعات گزارش‌شده:

```text
Branch:
feature/visual-page-builder-p1-hardening

Commit:
327f91528f40b0546a2b01245023e60a03815964

Working Tree:
Clean (آخرین وضعیت گزارش‌شده)
```

توجه: قبل از هر اقدام توسعه‌ای، وضعیت واقعی Git باید مجدداً بررسی شود؛ این اطلاعات یک Snapshot تاریخی از آخرین گزارش هستند.

## 11.2. اقدامات پیش از شروع P2

1. بررسی Branch فعال.
2. بررسی Commit فعلی.
3. بررسی Clean بودن Working Tree.
4. بررسی ساختار واقعی فایل‌های P0 و P1.
5. بررسی وضعیت مایگریشن‌ها.
6. بررسی مدل PageTemplate.
7. بررسی APIهای موجود مدیریت قالب‌ها.
8. بررسی سیستم فعلی Theme و CSS.
9. بررسی ساختار فونت‌ها و رنگ‌های فعلی پروژه.
10. شناسایی قابلیت‌های موجود برای جلوگیری از توسعه تکراری.

## 11.3. اولین کار P2

قبل از پیاده‌سازی، یک ممیزی معماری انجام شود:

- چه سیستم رنگی در پروژه وجود دارد؟
- Theme فعلی چگونه مدیریت می‌شود؟
- فونت‌های سراسری کجا تعریف شده‌اند؟
- آیا Design Token یا CSS Variable موجود است؟
- مدل PageTemplate فعلی چه قابلیت‌هایی دارد؟
- آیا API مدیریت قالب‌ها واقعاً کامل است؟
- آیا ذخیره Section به‌عنوان Template قابل انجام است؟
- چگونه باید توکن‌ها در AST ذخیره شوند؟
- چگونه باید توکن‌ها به خروجی HTML و CSS منتشرشده متصل شوند؟

پس از این بررسی، معماری P2 طراحی و سپس پیاده‌سازی مرحله‌ای آغاز شود.

---

# 12. معیارهای تحویل هر فاز

هر فاز باید گزارش نهایی استاندارد داشته باشد:

1. عنوان و هدف فاز.
2. Branch فعال.
3. Commit Hash.
4. فهرست فایل‌های ایجادشده.
5. فهرست فایل‌های تغییرکرده.
6. توضیح قابلیت‌های پیاده‌سازی‌شده.
7. APIهای اضافه یا تغییرکرده.
8. تغییرات Database و Migration.
9. تست‌های اضافه‌شده.
10. خروجی واقعی تست‌ها.
11. نتیجه TypeScript و Lint در صورت مرتبط بودن.
12. موارد ناقص و بدهی‌های فنی.
13. مشکلات امنیتی احتمالی.
14. وضعیت Regression.
15. پیشنهاد مرحله بعد.

**قانون مهم:** گزارش باید وضعیت واقعی کد و اجرای واقعی دستورات را منعکس کند، نه صرفاً ادعای توسعه‌دهنده.

---

# 13. دستورالعمل انتقال پروژه به سشن جدید (Session Handoff)

هر زمان این سند به یک سشن جدید داده شد، دستیار باید مراحل زیر را رعایت کند:

### مرحله اول: درک پروژه

ابتدا کل سند را مطالعه کند و متوجه شود:

- هدف پروژه چیست.
- چه معماری‌ای دارد.
- P0 و P1 چه چیزهایی دارند.
- P2 تا P5 چه اهدافی دارند.
- آخرین وضعیت ثبت‌شده چیست.

### مرحله دوم: راستی‌آزمایی

هیچ‌کدام از اطلاعات Git یا وضعیت فایل‌ها نباید بدون بررسی مجدد، وضعیت فعلی فرض شوند.

دستیار باید در صورت دسترسی به Repository:

- Git Status را بررسی کند.
- Branch را بررسی کند.
- آخرین Commit را بررسی کند.
- فایل‌های کلیدی را بخواند.
- تست‌های مرتبط را بررسی کند.

### مرحله سوم: حفظ محدوده فاز

اگر فاز فعال P2 است:

- فقط Design System و Templates توسعه داده شوند.
- ویجت‌های فروشگاهی به P3 موکول شوند.
- قابلیت‌های Advanced به P4 موکول شوند.
- Hardening نهایی به P5 موکول شود.

### مرحله چهارم: بررسی قبل از تغییر

قبل از هر تغییری:

- ساختار فعلی بررسی شود.
- وابستگی‌های موجود بررسی شوند.
- APIهای موجود بررسی شوند.
- از ایجاد سیستم تکراری خودداری شود.
- سازگاری با P0 و P1 حفظ شود.

### مرحله پنجم: توسعه مرحله‌ای

هر قابلیت:

1. طراحی.
2. پیاده‌سازی.
3. تست.
4. بررسی Regression.
5. Commit.
6. گزارش.

---

# 14. پرامپت آماده برای شروع کار در هر سشن جدید

متن زیر را همراه این سند در سشن جدید ارسال کن:

---

**نقش شما: Senior Software Architect & Full-Stack Engineer**

ما در حال توسعه یک Visual Page Builder حرفه‌ای برای یک CMS و فروشگاه آنلاین هستیم.

سند پیوست، مرجع اصلی معماری، تاریخچه توسعه، نقشه راه و وضعیت فعلی پروژه است.

وظایف شما:

1. سند را کامل مطالعه کن.
2. معماری پروژه و تصمیمات قبلی را حفظ کن.
3. قابلیت‌های تکمیل‌شده را دوباره از صفر توسعه نده.
4. اطلاعات ثبت‌شده را بدون بررسی، وضعیت واقعی فعلی فرض نکن.
5. ابتدا Repository، Git و فایل‌های کلیدی را بررسی کن.
6. وضعیت واقعی قابلیت‌ها و تست‌ها را با سند تطبیق بده.
7. اختلاف احتمالی را گزارش کن.
8. قبل از تغییرات بزرگ، معماری و برنامه اجرایی ارائه بده.
9. از ایجاد Regression در قابلیت‌های P0 و P1 جلوگیری کن.
10. محدوده فاز فعال را رعایت کن.

**نقشه راه مصوب:**

- P0: Core Engine — Completed
- P1: Visual Builder Studio & Hardening — Completed، با یک مورد ناموفق در E2E
- P2: Design System & Templates — Next
- P3: E-commerce Widgets
- P4: Advanced Builder
- P5: Production Hardening

در حال حاضر نقطه شروع توسعه، P2 است.

در P2 فقط روی موارد زیر کار کن:

- Design Tokens
- Global Colors
- Global Typography
- Spacing & Layout Tokens
- Global Styles
- Theme Integration
- Page Templates
- Reusable Sections
- Template Library

در این فاز وارد توسعه ویجت‌های فروشگاهی نشو.

**قانون اصلی:** هیچ قابلیت، تست، API یا تغییر Git را بدون شواهد واقعی تکمیل‌شده اعلام نکن. در تمام مراحل، امنیت، سازگاری و پایداری معماری قبلی را حفظ کن.

ابتدا وضعیت واقعی پروژه را بررسی و گزارش کن و سپس برای شروع فاز P2 برنامه اجرایی مرحله‌ای ارائه بده.

---

# 15. جمع‌بندی نهایی

هدف نهایی این پروژه صرفاً ایجاد یک صفحه‌ساز ساده نیست.

ما در حال توسعه یک زیرساخت طراحی و مدیریت محتوای حرفه‌ای هستیم که باید بتواند در آینده:

- صفحات سایت را کاملاً بصری طراحی کند.
- سیستم طراحی مرکزی داشته باشد.
- قالب‌های قابل استفاده مجدد ایجاد کند.
- به سیستم فروشگاه متصل شود.
- ویجت‌های هوشمند داشته باشد.
- قابلیت‌های پیشرفته طراحی ارائه کند.
- در محیط Production پایدار و امن باشد.

**ترتیب اصلی توسعه:**

```text
P0 — Core Engine
        |
        v
P1 — Visual Builder Studio
        |
        v
P1 — Hardening
        |
        v
P2 — Design System & Templates
        |
        v
P3 — E-commerce Widgets
        |
        v
P4 — Advanced Builder
        |
        v
P5 — Production Hardening
        |
        v
Professional Production-Ready
Visual Page Builder
```

**اصل نهایی پروژه:**

هر قابلیت باید ماژولار، قابل توسعه، قابل تست، امن و سازگار با معماری موجود باشد. هیچ فازی نباید با قربانی کردن کیفیت فازهای قبلی تکمیل شود.

---

**Document Status:** Master Roadmap — Living Document

این سند باید پس از تکمیل هر فاز به‌روزرسانی شود و مرجع انتقال دانش بین سشن‌ها و اعضای تیم باقی بماند.