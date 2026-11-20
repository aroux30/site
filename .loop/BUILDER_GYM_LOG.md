# کارنامه رسمی تمرین پیش‌رونده Visual Page Builder (.loop/BUILDER_GYM_LOG.md)

> تمرکز ۱۰۰٪ روی محیط صفحه‌ساز بصری (`/e2e-isolated-scratchpad?builder=1`) — پیگیری دور به دور ۵ وزنه پیش‌رونده تا ثبت BUILDER_GYM_LEVELS_1_TO_5_CLEAN

---

## راهنمای نردبان وزنه‌ها
- **وزنه ۱ (۵ کیلو)**: اسکلت ۳ ستونه استودیو، نوار ابزار، درخت لایه‌ها و بوم Iframe
- **وزنه ۲ (۱۰ کیلو)**: پالت بلوک‌ها، اعتبارسنجی تک‌تک ۲۸ الگوی آماده (Block Patterns) و تمام ویجت‌های بومی
- **وزنه ۳ (۲۰ کیلو)**: کنترل‌های پنل بازرس (Inspector: Content, Style, Advanced) و دیالوگ Global Styles
- **وزنه ۴ (۳۵ کیلو)**: درگ‌انددراپ، کلیدهای میانبر، قالب‌های سکشن/صفحه، کامپوننت‌های سراسری و تطابق با خروجی رندرشده (WYSIWYG)
- **وزنه ۵ (۵۰ کیلو)**: ریسپانسیو ۳ ویوپورت (موبایل ۳۷۵px، تبلت ۷۶۸px، دسکتاپ)، دارک‌مود کامل استودیو، و تست فشار ۵۰+ المان تودرتو

---

## کارنامه راندها (Round History)

### 🏋️ راند ۱ (Round 01) — وزنه ۱: ۵ کیلو (اسکلت استودیو، نشت چت‌بات، سقف بوم و کلید ?builder=1)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `autofix/gym-loop`
- **وضعیت**: ✅ کامل و سبز (۳ باگ ریشه‌ای اصلاح و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و DOM
1. **عدم فعال‌سازی استودیو با پارامتر اختصاصی `?builder=1`**:
   - *مشاهده در Vision*: در تصویر `before/01-studio-fullscreen-layout.png`، ارسال پارامتر `?builder=1` منجر به لود صفحه عمومی و عدم فعال‌سازی محیط ویرایشگر شد، زیرا شرط روتینگ تنها `visual_editor=true` و `edit=true` را بررسی می‌کرد.
   - *اصلاح ریشه‌ای*: الحاق `builder === "1"` و `builder === "true"` در `frontend/app/(store)/[slug]/page.tsx` و `frontend/components/layout/admin-bar.tsx`.
2. **پوشانده شدن گوشه پایینی پالت بلوک‌ها و لایه‌ها توسط ویجت چت بادی (`Chat FAB Collision on Builder Studio`)**:
   - *مشاهده در Vision*: در تصویر `before/01-studio-fullscreen-layout.png`، آیکون گرد آبی چت شناور (`[💬]`) دقیقاً روی کارت‌های انتهای سایدبار راست استودیو سوار شده بود و کلیک‌پذیری کارت‌ها را مختل می‌کرد.
   - *علت ریشه‌ای*: `PluginWidgetLoader` تنها چک می‌کرد `!pathname.startsWith("/admin")` و حضور در صفحه سازنده داخل برگه CMS را تشخیص نمی‌داد.
   - *اصلاح ریشه‌ای*: اضافه شدن تشخیص وضعیت ویرایشگر در `plugin-widget-loader.tsx` و مخفی‌سازی کامل ریشه `#n8n-w` در زمان حضور در بیلدر.
3. **تداخل دوگانه در محاسبه فاصله سقف بوم و بریدگی نوار ابزار شناور (`Floating Toolbar Ceiling Conflict`)**:
   - *مشاهده*: دو هوک `useEffect` متناقض با آستانه‌های ۳۶px و ۲۸px روی المان فعال برای تعیین `isNearTop` وجود داشت که باعث پرش و بریدگی نوار ابزار می‌شد.
   - *اصلاح ریشه‌ای*: ادغام و یکپارچه‌سازی محاسبه حاشیه امن سقف به ۴۰px و حذف هوک تکراری در `canvas-element.tsx`.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-01/before/`
  - `01-studio-fullscreen-layout.png`
  - `02-layers-tree-visibility-indent.png`
  - `03-canvas-toolbar-clearance.png`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-01/after/`
  - `01-studio-fullscreen-layout.png` (حذف کامل دکمه مزاحم چت و لود بی‌نقص استودیو با ?builder=1)
  - `02-layers-tree-visibility-indent.png` (رویت‌پذیری دائمی تمام کلیدهای عملیاتی بدون هاور)
  - `03-canvas-toolbar-clearance.png` (فاصله استاندارد بالای نوار ابزار شناور)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r01.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۱
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright راند ۱: **۳ تست سبز (`3 passed in 12.1s`)**
- `node .loop/audits/deterministic-audit.mjs`: **پاس ۱۰۰٪ تمام چک‌ها (`passed: true`)**

---

### 🏋️ راند ۲ (Round 02) — وزنه ۲: ۱۰ کیلو (پالت بلوک‌ها، استایل دکمه‌های الگو و درک شناسه کانتینر والد)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `autofix/gym-loop`
- **وضعیت**: ✅ کامل و سبز (۳ نقص ریشه‌ای پالت و الگوها حل و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **عدم اعمال کلاس‌های رنگ و پس‌زمینه دکمه‌ها در رندر الگوها روی بوم (`Button Custom Classes Override`)**:
   - *مشاهده در Vision*: در تصویر `before/03-canvas-rendered-patterns.png`، دکمه هیرو با متن «همین حالا بخرید» دارای کلاس سفارشی `bg-primary-foreground text-primary` بود اما به صورت دکمه پیش‌فرض سبز با متن سفید رندر می‌شد و کنتراست لازم را نداشت.
   - *علت ریشه‌ای*: ویجت `button` در `canvas-element.tsx` پروپرتی‌های کلاس سفارشی را روی تگ رندر نهایی اعمال نمی‌کرد.
   - *اصلاح ریشه‌ای*: تزریق مستقیم `customCssClass` در `canvas-element.tsx` با استفاده از `cn()`.
2. **گم شدن کانتینر والد هنگام درج الگو در زمان انتخاب المان‌های تودرتو**:
   - *مشاهده*: تابع `getTargetContainerId` در پالت بلوک‌ها فقط به ریشه‌های مستقیم سطح اول دسترسی داشت و اگر یک کانتینر فرزند داخل درخت انتخاب شده بود، شناسه آن را پیدا نمی‌کرد و الگو در ریشه بوم ریخته می‌شد.
   - *اصلاح ریشه‌ای*: بهره‌گیری از پیمایش عمیق درخت با `findElementById` در `blocks-palette.tsx`.
3. **فقدان شناسه یکتا `data-pattern-slug` برای اعتبارسنجی و تعامل در کارت‌های الگو**:
   - *مشاهده*: کارت‌های ۲۸ الگوی آماده فاقد اتریبیوت تست بودند.
   - *اصلاح*: اضافه شدن اتریبیوت صریح `data-pattern-slug={pattern.slug}` به هر ۲۸ کارت پالت الگوها.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-02/before/`
  - `01-blocks-search-filtered.png`
  - `02-patterns-palette-list.png`
  - `03-canvas-rendered-patterns.png`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-02/after/`
  - `01-blocks-search-filtered.png` (فیلتر دقیق و بدون لگ بلوک‌ها)
  - `02-patterns-palette-list.png` (فهرست کامل و منظم ۲۸ الگو)
  - `03-canvas-rendered-patterns.png` (رندر بی‌نقص دکمه سفید پرکنتراست در بنر سبز هیرو)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r02.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۲
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright راند ۲: **۳ تست سبز (`3 passed in 12.1s`)**
- `node .loop/audits/deterministic-audit.mjs`: **پاس ۱۰۰٪ تمام چک‌ها (`passed: true`)**

---

### 🏋️ راند ۳ (Round 03) — وزنه ۳: ۲۰ کیلو (پنل بازرس، تب‌های استایل و لایه دیالوگ Global Styles)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `autofix/gym-loop`
- **وضعیت**: ✅ کامل و سبز (اصلاح عمق بصری z-index دیالوگ‌ها، ایزولاسیون پوینتر هدر و اتصال کامل توکن‌های بازرس)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **پنهان شدن یا تداخل لایه‌ای دیالوگ Global Styles پشت پوسته استودیو (`Dialog Z-Index Collision`)**:
   - *مشاهده در Vision*: استودیو صفحه‌ساز با کلاس `z-[100]` در بالاترین سطح صفحه رندر می‌شد، در حالی که دیالوگ‌های Radix (`DialogOverlay` و `DialogContent`) از `z-50` استفاده می‌کردند. در نتیجه دیالوگ‌ها و لایه اوورلی در زیر استودیو قرار می‌گرفتند.
   - *اصلاح ریشه‌ای*: ارتقای سطح `z-index` در `frontend/components/ui/dialog.tsx` به `z-[120]` برای تضمین تقدم مطلق تمام دیالوگ‌های استودیو (استایل سراسری، ذخیره قالب و ...).
2. **تداخل رویدادهای ماوس هدر استورفرانت با محیط استودیو (`Header Pointer Interception`)**:
   - *مشاهده*: کامپوننت `Header` در بالای صفحه با وضعیت sticky لود می‌شد و در تست‌های خودکار لایه زیرین را مسدود می‌کرد.
   - *اصلاح ریشه‌ای*: شرط `if (isVisualEditor) return null;` در `frontend/components/layout/header.tsx` برای حذف کامل هرگونه المان مزاحم در حالت بیلدر.
3. **اعمال آنی توکن‌های رنگ و استایل در Inspector بدون نیاز به رفرش**:
   - *مشاهده*: اعمال توکن‌های پس‌زمینه و تایپوگرافی در تب استایل بازرس بررسی شد و ثبات عملکرد برای دیوایس جاری تضمین گردید.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-03/before/`
  - `01-inspector-content-tab.png`
  - `02-inspector-style-tab.png`
  - `03-inspector-advanced-tab.png`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-03/after/`
  - `01-inspector-content-tab.png` (کنترل‌های غنی محتوا)
  - `02-inspector-style-tab.png` (تنظیم دقیق فاصله‌ها، پس‌زمینه و رنگ تایپوگرافی)
  - `03-inspector-advanced-tab.png` (تنظیمات رویت‌پذیری و انیمیشن)
  - `04-global-styles-dialog.png` (رویت‌پذیری کاملاً واضح و شفاف دیالوگ Design Tokens در لایه بالاتر از استودیو)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r03.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۳
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright راند ۳: **۳ تست سبز (`3 passed in 9.7s`)**
- `node .loop/audits/deterministic-audit.mjs`: **پاس ۱۰۰٪ تمام چک‌ها (`passed: true`)**

---


