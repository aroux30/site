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

### 🏋️ راند ۴ (Round 04) — وزنه ۴: ۳۵ کیلو (کلیدهای میانبر درون بوم، درج هوشمند پیست، همگام‌سازی کامپوننت‌های سراسری و قالب‌ها)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `autofix/gym-loop`
- **وضعیت**: ✅ کامل و سبز (۴ نقص ریشه‌ای در بهره‌وری و میانبرها، همگام‌سازی و اعمال قالب‌ها برطرف شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **از کار افتادن کلیدهای میانبر درون بوم Iframe (`Canvas Iframe Shortcut Event Swallowing`)**:
   - *مشاهده در Vision*: در تصویر `before/01-canvas-shortcuts-paste.png`، کلیک و انتخاب المان درون Iframe بوم باعث انتقال فوکوس به سند داخلی می‌شد و در نتیجه فشردن `Ctrl+C` و `Ctrl+V` یا `Ctrl+Z` به پنجره اصلی (`window`) نمی‌رسید و هیچ عملیاتی صورت نمی‌گرفت (`report.json: passed: false`).
   - *اصلاح ریشه‌ای*: ثبت شنونده `keydown` در سند داخلی `CanvasFrame` در `frontend/components/admin/builder/canvas-frame.tsx` و فوروارد رویدادهای کیبورد به پنجره والد.
2. **تخریب ساختار AST هنگام پیست روی المان‌های غیرکانتینر (`Paste Into Non-Container AST Corruption`)**:
   - *مشاهده*: در صورت انتخاب یک المان متنی یا دکمه و زدن پیست، تابع `pasteElement` المان کپی‌شده را به عنوان فرزند آن المان درج می‌کرد که ساختار درختی را نامعتبر می‌ساخت.
   - *اصلاح ریشه‌ای*: ارتقای منطق `pasteElement` در `frontend/stores/builder-store.ts` به گونه‌ای که با پیمایش درخت والد، در صورت انتخاب یک المان غیرکانتینر، المان کپی‌شده به عنوان برادر مجاور (`sibling`) با `index + 1` درج می‌شود.
3. **عدم همگام‌سازی خودکار ویرایش کامپوننت‌های سراسری روی سایر نمونه‌ها (`Global Components Out of Sync`)**:
   - *مشاهده*: ویرایش پروپ‌ها و استایل‌های یک کامپوننت علامت‌گذاری‌شده به عنوان سراسری (`globalComponentId`) فقط روی نمونه فعلی اثر می‌کرد و سایر نمونه‌های همگام به‌روزرسانی نمی‌شدند.
   - *اصلاح ریشه‌ای*: بازنویسی `updateElementProps`، `updateElementStyles` و `updateDeviceStyles` در `builder-store.ts` برای به‌روزرسانی تمام نودهای دارای همان `globalComponentId` در سراسر درخت AST.
4. **عدم ثبت تاریخچه Undo در زمان اعمال قالب کامل برگه (`Page Template Apply Undo Loss`)**:
   - *مشاهده*: در `blocks-palette.tsx`، تابع `handleApplyPageTemplate` مستقیماً استیت را بدون ثبت در `history.past` تغییر می‌داد و امکان بازگشت با `Ctrl+Z` وجود نداشت.
   - *اصلاح ریشه‌ای*: ایجاد متد اختصاصی `replacePageAST` در `builder-store.ts` با حفظ تاریخچه `past` و مدیریت صحیح `mutationVersion`.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-04/before/`
  - `01-canvas-shortcuts-paste.png`
  - `02-palette-templates-tab.png`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-04/after/`
  - `01-canvas-shortcuts-paste.png` (درج موفق المان کپی‌شده «متن دوم (کپی)» دقیقاً در مجاورت المان فعال)
  - `02-palette-templates-tab.png` (نمایش تمیز و بی‌نقص زبانه قالب‌های من با امکان درگ، کپی و حذف)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r04.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۴
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright راند ۴: **۳ تست سبز (`3 passed in 13.2s`)**
- `node .loop/audits/deterministic-audit.mjs`: **پاس ۱۰۰٪ تمام چک‌ها (`passed: true`)**

---

### 🏋️ راند ۵ (Round 05) — وزنه ۵: ۵۰ کیلو (ریسپانسیو ویوپورت‌ها، دارک‌مود همگام و تست استرس بوم)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `autofix/gym-loop`
- **وضعیت**: ✅ کامل و سبز (همگام‌سازی بی‌درنگ حالت تاریک به iframe، تطابق دقیق ویوپورت‌های تبلت ۷۶۸px و موبایل ۳۷۵px، و حذف نقص دسترس‌پذیری دراور موبایل)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **عدم انطباق بلادرنگ تم تاریک (Dark Mode) با بوم ایزوله Iframe (`CanvasFrame Dark Mode Sync Delay`)**:
   - *مشاهده در Vision*: در سوییچ پوسته استودیو به حالت شب، سند داخلی `CanvasFrame` به دلیل عدم شنود رویداد تغییر کلاس روی ریشه والد، در تم قبلی باقی می‌ماند.
   - *اصلاح ریشه‌ای*: ثبت `MutationObserver` روی اتریبیوت‌های `class` و `style` در `document.documentElement` داخل `canvas-frame.tsx` برای انتقال آنی تم شب/روز به سند بوم.
2. **نقص دسترسی‌پذیری عنصر پنهان با فرزندان قابل فوکوس در استورفرانت (`aria-hidden-focus in Mobile Navigation Drawer`)**:
   - *مشاهده*: اسکن استاندارد AxeBuilder وجود یک خطای جدی `aria-hidden-focus` را در منوی موبایل گزارش کرد که در وضعیت بسته دارای عناصر فوکوس‌پذیر داخل کانتینر با `aria-hidden="true"` بود.
   - *اصلاح ریشه‌ای*: آن‌مانت کامل منوی دراور در زمان بسته بودن (`mobileMenuOpen && (...)`) در `frontend/components/layout/header.tsx` و تنظیم `role="dialog"` و `aria-modal="true"` در حالت باز.
3. **پایداری فرآیند سرور پروداکشن در rebuild-and-verify.ps1 بدون نشت استاتیک**:
   - *اصلاح*: استانداردسازی اجرای سرور در اسکریپت ری‌بیلد ویندوز برای اطمینان از سرو کامل فایل‌های CSS و JS بیلد پروداکشن بدون خطای ۴۰۰.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-05/before/`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-05/after/`
  - `01-viewport-desktop.png` (بوم تمام‌عرض استاندارد)
  - `02-viewport-tablet-768.png` (تنظیم دقیق عرض تبلت با حاشیه امن)
  - `03-viewport-mobile-375.png` (بوم استاندارد ۳۷۵px موبایل بدون سرریز افقی)
  - `04-builder-dark-mode-sync.png` (هماهنگی کامل دارک‌مود استودیو، پنل‌ها، بازرس و بوم داخلی با کنتراست عالی)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r05.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۵
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۵): **۱۵ تست سبز در ۱۵ فایل (`15 passed in 48.7s`)**
- `node .loop/audits/deterministic-audit.mjs`: **پاس ۱۰۰٪ تمام چک‌ها (`passed: true`) شامل ۰ خطای WCAG 2.1 AA**

---

### 🏋️ راند ۶ (Round 06) — وزنه ۲: ۱۰ کیلو (ممیزی عمیق بصری الگوها، رفع افت کلاس‌های سفارشی ویجت‌ها و بهینه‌سازی تستک توست‌ها)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (۳ نقص ریشه‌ای در رندر ویجت‌های الگوها، تصاویر و اعلان‌ها کشف، اصلاح و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **افت کلاس‌های سفارشی تایپوگرافی در ویجت‌های heading و text_editor بوم (`Canvas Heading & Text customCssClass Drop`)**:
   - *مشاهده در Vision*: در تصاویر `before/02-pattern-hero-and-features.png` و `before/04-pattern-faq-image-countdown.png` و گزارش `report.json`، عناوین تولیدشده توسط الگوها (نظیر سایز `text-3xl md:text-5xl` در هیرو و رنگ و فونت `font-mono text-primary text-lg` در شمارش معکوس) به دلیل عدم الحاق `customCssClass` در رندر نهایی کامپوننت `canvas-element.tsx`، نادیده گرفته شده و با سایز پیش‌فرض ساده رندر می‌شدند.
   - *اصلاح ریشه‌ای*: الحاق صریح `customCssClass` (از پروپ‌ها یا استایل‌های المان) با متد `cn()` به تگ‌های `Tag` در ویجت `heading` و `div` در ویجت `text_editor` درون `canvas-element.tsx`.
2. **افت استایل‌ها و ابعاد تصویر در ویجت image (`Canvas Image customCssClass Drop`)**:
   - *مشاهده در Vision*: در الگوهایی نظیر بیوگرافی نویسنده (`author-bio`)، گالری و هیرو، ابعاد و استایل‌های مرز و گردی عکس نظیر `w-24 h-24 rounded-full border-2` به تگ `img` یا کانتینر آن اعمال نمی‌شد و عکس با کلاس ثابت پیش‌فرض رندر می‌شد.
   - *اصلاح ریشه‌ای*: تزریق `customClass` به کانتینر و تگ `img` در `canvas-element.tsx`.
3. **انباشتگی و اشغال بوم توسط پشته توست‌های ماندگار ۵ ثانیه‌ای در زمان درج الگوها (`Toast Stack Canvas Obstruction`)**:
   - *مشاهده در Vision*: در تصاویر `before/02` و `before/03` و `before/04`، هنگام درج پیاپی الگوها، ۳ تا ۴ کادر توست اعلان موفقیت به مدت ۵ ثانیه روی گوشه چپ بوم انباشته شده و محتوای بوم و کارت‌ها را می‌پوشاندند.
   - *اصلاح ریشه‌ای*: تنظیم مدت زمان معقول ۲ ثانیه‌ای (`duration: 2000`) برای اعلان‌های افزودن الگو و قالب در `blocks-palette.tsx` به منظور محو سریع‌تر و عدم ایجاد مزاحمت بصری در بوم طراحی.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-06/before/`
  - `01-patterns-palette-list.png`
  - `02-pattern-hero-and-features.png`
  - `03-pattern-product-showcase-testimonials.png`
  - `04-pattern-faq-image-countdown.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-06/after/`
  - `01-patterns-palette-list.png` (فهرست غنی و کامل ۲۸ الگوی آماده)
  - `02-pattern-hero-and-features.png` (اعمال موفق کلاس‌های سایز ۳xl و ۵xl و هدینگ‌های سفارشی هیرو)
  - `03-pattern-product-showcase-testimonials.png` (رندر پایدار و استاندارد الگوهای معرفی کالا و نظرات مشتریان)
  - `04-pattern-faq-image-countdown.png` (نمایش دقیق استایل مونو و رنگ primary در شمارش معکوس)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r06.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۶
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۶): **۱۸ تست سبز در ۱۸ فایل (`18 passed in 55.6s`)**

---

### 🏋️ راند ۷ (Round 07) — وزنه ۲: ۱۰ کیلو (ممیزی الگوهای ۸ تا ۱۴: فروشگاهی، امتیازدهی، آمار و درج ریشه‌ای الگوها)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (۳ باگ ریشه‌ای در تودرتوشدن الگوها، کلاس‌های ویجت‌های فرم و دکمه‌های تمام‌عرض حل شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **تودرتو شدن ناخواسته الگوهای بخش در زمان درج پیاپی (`Accidental Pattern Nesting`)**:
   - *مشاهده در Vision*: در تصاویر `before/01` و `before/02`، الگوهای بخش‌های کامل پس از درج اولیه به دلیل فعال ماندن `selectedElementId` درون کانتینر الگوی قبلی درج می‌شدند و ساختار درختی بوم تخریب می‌شد.
   - *اصلاح ریشه‌ای*: در `blocks-palette.tsx`، تابع `handleInsertPattern` و `handleInsertTemplate` اصلاح شدند تا الگوهای آماده سکشن همواره به عنوان سکشن‌های مستقل سطح اول (`rootElements`) به ریشه سند بوم اضافه شوند.
2. **افت کلاس‌های سفارشی در ویجت‌های فرم (`Form Widgets customCssClass Drop`)**:
   - *مشاهده در Vision*: ویجت‌های `form_input`, `form_textarea` و `form_select` کلاس‌های سفارشی استایل را روی کانتینر دربرگیرنده اعمال نمی‌کردند.
   - *اصلاح ریشه‌ای*: الحاق `customClass` با `cn()` به ریشه ویجت‌های فرم در `canvas-element.tsx`.
3. **عدم انطباق عرض دکمه‌های با کلاس `w-full` در کانتینرهای flex (`Full-Width Button Wrapper Shrink`)**:
   - *مشاهده*: دکمه‌هایی که دارای کلاس `w-full` بودند درون کانتینر پیش‌فرض `inline-block` جمع می‌شدند.
   - *اصلاح ریشه‌ای*: تشخیص کلاس `w-full` در ویجت دکمه و تنظیم کانتینر والد به صورت `w-full block`.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-07/before/`
  - `01-pattern-star-rating-histogram.png`
  - `02-pattern-products-grid-marquee.png`
  - `03-pattern-stats-gallery-discount.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-07/after/`
  - `01-pattern-star-rating-histogram.png` (تفکیک ریشه‌ای کانتینر امتیاز و نمودار هیستوگرام با ستاره‌های کهربایی)
  - `02-pattern-products-grid-marquee.png` (سکشن مستقل ویترین کارت‌های کالا و نوار متحرک)
  - `03-pattern-stats-gallery-discount.png` (کادر تخفیف پرکنتراست و دکمه‌های متناسب)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r07.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۷
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۷): **۲۱ تست سبز در ۲۱ فایل (`21 passed in 60s`)**

---

### 🏋️ راند ۸ (Round 08) — وزنه ۲: ۱۰ کیلو (ممیزی الگوهای ۱۵ تا ۲۱: پلن‌های قیمت‌گذاری، دسته‌بندی مگامنو، بیوگرافی و نقل‌قول)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (۳ نقص در رندر توضیحات پلن‌های دارای برچسب، دکمه‌های ناوبری مگامنو و نقل‌قول اصلاح و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **حذف اشتباه توضیحات پلن دوم در جدول تعرفه به دلیل وجود نشان برچسب (`Pricing Table Badge Description Drop`)**:
   - *مشاهده در Vision*: در `before/01-pattern-megamenu-pricing.png` و `report.json`، در صورت وجود `badge` برای پلن‌های جدول تعرفه (نظیر پلن حرفه‌ای با برچسب «محبوب‌ترین»)، عبارت شرطی نادرست باعث می‌شد متن توضیح زیر عنوان پلن (`p.desc`) کلاً رندر نشود.
   - *اصلاح ریشه‌ای*: در `pattern-converter.ts` در الگوی `pricing-table`، استخراج نشان و متن توضیح به دو عنصر مجزا تفکیک شدند تا هر دو همزمان و با فاصله‌گذاری استاندارد رندر شوند.
2. **عدم انطباق عرض دکمه‌های دسته‌بندی مگامنو با ستون‌های گرید (`MegaMenu Category Buttons Full-Width`)**:
   - *مشاهده*: دکمه‌های ناوبری دسته‌بندی در الگوی `mega-menu-categories` فاقد کلاس صریح `w-full` بودند و در عرض ستون‌های گرید ۴ تایی نامتقارن رندر می‌شدند.
   - *اصلاح ریشه‌ای*: الحاق کلاس `w-full` به دکمه‌های `createButtonWidget` در `pattern-converter.ts`.
3. **افت هماهنگی تایپوگرافی در نقل‌قول و کادر تماس پشتیبانی**:
   - *اصلاح*: تطابق کامل استایل خط حاشیه آغازین (`border-s-4`) و کادرهای خط‌چین در بوم و کامپایلر AST.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-08/before/`
  - `01-pattern-megamenu-pricing.png`
  - `02-pattern-pricelist-iconbox.png`
  - `03-pattern-bio-quote-support.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-08/after/`
  - `01-pattern-megamenu-pricing.png` (رندر دقیق عنوان، برچسب و توضیحات کامل پلن ۲ در کنار دکمه‌های منظم دسته‌بندی)
  - `02-pattern-pricelist-iconbox.png` (لیست قیمت منظم با خطوط جداکننده تمیز)
  - `03-pattern-bio-quote-support.png` (رندر بی‌نقص کادر نقل‌قول و کادر تماس با آیکون پیام)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r08.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۸
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۸): **۲۴ تست سبز در ۲۴ فایل (`24 passed in 78s`)**

---

### 🏋️ راند ۹ (Round 09) — وزنه ۲: ۱۰ کیلو (ممیزی الگوهای ۲۲ تا ۲۸: جدول مقایسه، مراحل خرید، فرم جذب سرنخ و برندها — پوشش ۱۰۰٪ هر ۲۸ الگو)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (تکمیل موفق ممیزی بصری تمامی ۲۸ الگوی آماده صفحه‌ساز با حفظ برابری WYSIWYG)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **عدم اعمال هایلایت ستون جدول در کامپایلر AST سمت سرور (`Comparison Table highlightCol Disparity`)**:
   - *مشاهده*: در ویجت `table` در `canvas-element.tsx` پروپرتی `highlightCol` به ستون مدل پرو رنگ و حاشیه متمایز (`bg-primary/10 text-primary border-x`) اعمال می‌کرد اما در `ast_compiler.py` کلاس‌های متناظر درج نمی‌شدند و جدول خروجی نهایی بدون هایلایت رندر می‌شد.
   - *اصلاح ریشه‌ای*: الحاق بررسی `highlightCol` در بخش thead و tbody در `ast_compiler.py` جهت برابری صددرصدی بوم با صفحه نهایی.
2. **پشتیبانی کامل از تمامی ورودی‌های فرم مشاوره و برچسب پاسخگویی (`Lead Capture Form Complete Slots`)**:
   - *اصلاح*: اطمینان از قرارگیری برچسب «پاسخگویی در کمتر از ۱۵ دقیقه» و ورودی موضوع در فرم جذب سرنخ.
3. **پوشش ۱۰۰٪ تصویری هر ۲۸ الگوی آماده**:
   - الگوهای ۲۲ تا ۲۸ (جدول مقایسه، مراحل ۴ گانه خرید، فرم سرنخ، نوار اعلان تخفیف، نوار ارتباطی سریع، گرید برندها و ویژگی‌های برجسته کالا) با اسکریپت ممیزی در بوم رندر، عکسبرداری و با ابزار Vision بررسی شدند.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-09/before/`
  - `01-pattern-comparison-steps.png`
  - `02-pattern-leadform-alert.png`
  - `03-pattern-contact-brand-highlights.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-09/after/`
  - `01-pattern-comparison-steps.png` (جدول مقایسه ۳ ستونه با هایلایت ستون پرو و مراحل گام‌به‌گام خرید)
  - `02-pattern-leadform-alert.png` (فرم شکیل جذب سرنخ و نوار اعلان پاییزه)
  - `03-pattern-contact-brand-highlights.png` (راه‌های ارتباطی، برندهای رسمی و کارت‌های ۳ گانه ارزش خرید)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r09.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۹
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۹): **۲۷ تست سبز در ۲۷ فایل (`27 passed in 84s`)**

---

### 🏋️ راند ۱۰ (Round 10) — وزنه ۶: بی‌نهایت (طراحی لندینگ کامل از صفر در بوم و صیقل درخت لایه‌ها)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (۳ باگ در سرریز دکمه‌های درخت لایه‌ها، تورفتگی عمق‌های ۲ و ۳ و مخفی‌سازی نوار ابزار در پیش‌نمایش اصلاح و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **سرریز و بریدگی دکمه‌های عملیاتی ردیف‌های درختی در عمق‌های ۲ و ۳ (`LayersTree Row Action Buttons Overflow Clipping`)**:
   - *مشاهده در Vision*: در تصویر `before/04-layers-tree-landing-sections.png`، المان‌های دارای عمق تودرتو به دلیل تورفتگی زیاد (`depth * 24px`) از عرض سایدبار ۳۲۰px فراتر رفته و دکمه‌های کپی، حذف و مخفی‌سازی از کادر ردیف به بیرون نشت کرده و بریده می‌شدند.
   - *اصلاح ریشه‌ای*: در `layers-tree.tsx`، تورفتگی راست به `Math.min(depth * 16, 48)px` محدود شد و کانتینر عنوان با `min-w-0 flex-1 truncate` تنظیم گردید تا دکمه‌های عملیاتی هرگز از کادر ردیف بیرون نزنند.
2. **ساخت موفق لندینگ پیج کامل ۶ بخشی در بوم**:
   - ۶ بخش هیرو، ویژگی‌ها، جدول مقایسه، فرم جذب سرنخ، سوالات متداول و تماس پشتیبانی از صفر روی بوم اضافه و در نمای کلی و پیش‌نمایش WYSIWYG اعتبارسنجی شدند.
3. **تثبیت حالت پیش‌نمایش (Preview Mode)**:
   - در حالت پیش‌نمایش کادرهای راهنمای انتخاب و نوار ابزار شناور پنهان و صفحه دقیقاً مشابه خروجی رندرشده نهایی نمایش داده می‌شود.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-10/before/`
  - `01-landing-hero-features.png`
  - `02-landing-comparison-leadform.png`
  - `03-landing-faq-support-cta.png`
  - `04-layers-tree-landing-sections.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-10/after/`
  - `01-landing-hero-features.png`
  - `02-landing-comparison-leadform.png`
  - `03-landing-faq-support-cta.png`
  - `04-layers-tree-landing-sections.png` (چینش تمیز و بدون سرریز ردیف‌های درختی با رویت‌پذیری کامل دکمه‌ها در تمام عمق‌ها)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r10.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۱۰
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۱۰): **۳۰ تست سبز در ۳۰ فایل (`30 passed in 80s`)**

---

### 🏋️ راند ۱۱ (Round 11) — وزنه ۶: بی‌نهایت (عمق چیدمان کانتینرها در بازرس، ثبت تاریخچه Undo و ایزولاسیون سبد خرید)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (۳ باگ در اعمال عمیق تنظیمات چیدمان بازرس، ثبت تاریخچه و حذف نشت سبد خرید شناور حل شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **عدم اعمال تنظیمات چیدمان روی کانتینرهای تودرتو و دور زدن تاریخچه (`Inspector Layout Shallow Map & Undo Bypass`)**:
   - *مشاهده*: در `inspector-panel.tsx`، کنترل‌های جهت چینش (direction)، تعداد ستون‌ها (gridColumns) و فاصله (gap) از `ast.rootElements.map(...)` سطح اول استفاده می‌کردند که روی کانتینرهای تودرتو بی‌اثر بود و از همه مهم‌تر از `useBuilderStore.setState(...)` مستقیم بدون ثبت در `history.past` استفاده می‌کرد که قابلیت Undo با Ctrl+Z را از کار می‌انداخت.
   - *اصلاح ریشه‌ای*: تعریف متد اختصاصی `updateElementLayout` و `updateElementName` در `builder-store.ts` با استفاده از پیمایش عمیق درختی `updateElementInTree` و ثبت منظم در تاریخچه `past`.
2. **نشت ویجت سبد خرید شناور استورفرانت به محیط استودیوی صفحه‌ساز (`FloatingCartBar Leak into Builder Studio`)**:
   - *مشاهده*: کامپوننت `FloatingCartBar` در زمان حضور در صفحه صفحه‌ساز (`builder=1`) به عنوان یک عنصر `<aside>` شناور روی صفحه رندر می‌شد و با سایدبار بازرس تداخل داشت.
   - *اصلاح ریشه‌ای*: شرط ایزولاسیون صریح `isBuilder` در `floating-cart-bar.tsx` جهت جلوگیری قطعی از رندر سبد شناور در محیط استودیو، و اضافه شدن نشانگر صریح `data-builder-inspector` به سایدبار بازرس در `builder-studio.tsx`.
3. **تفکیک ایمن و بازگشت‌پذیر کامپوننت همگام سراسری (`Global Component Detach`)**:
   - *اصلاح ریشه‌ای*: تعریف اکشن `unlinkGlobalComponent` در استور با ثبت تاریخچه و پیمایش عمیق درختی بدون ایجاد ناپایداری در استیت.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-11/before/`
  - `01-inspector-content-layout.png`
  - `02-inspector-style-spacing.png`
  - `03-inspector-advanced-global-sync.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-11/after/`
  - `01-inspector-content-layout.png` (کنترل‌های دقیق چیدمان محتوا در بازرس ایزوله)
  - `02-inspector-style-spacing.png` (تنظیمات فاصله‌گذاری و تایپوگرافی)
  - `03-inspector-advanced-global-sync.png` (کنترل‌های پیشرفته کامپوننت سراسری و نمایش شرطی)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r11.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۱۱
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۱۱): **۳۳ تست سبز در ۳۳ فایل (`33 passed in 84s`)**

---

### 🏋️ راند ۱۲ (Round 12) — وزنه ۶: بی‌نهایت (جابه‌جایی اتمیک المان‌ها در نوار ابزار با دکمه‌های بالا/پایین و همگام‌سازی کلیدهای جهت‌نما)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (۳ باگ در فقدان اکشن‌های جابه‌جایی المان بدون درگ، محاسبه تاچ در سقف و ثبت پشته Undo اصلاح شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **فقدان دکمه‌های انتقال مستقیم (Move Up / Move Down) در نوار ابزار شناور (`Floating Toolbar Reorder Arrows Missing`)**:
   - *مشاهده در Vision*: در تصویر `01-floating-toolbar-reorder-buttons.png`، برای جابه‌جایی المان‌ها و بخش‌ها کاربر ناچار به درگ بود که روی نمایشگرهای لمسی و لپ‌تاپ دقت پایینی داشت.
   - *اصلاح ریشه‌ای*: الحاق دکمه‌های Move Up و Move Down (`ArrowUp`, `ArrowDown`) به نوار ابزار شناور المان در `canvas-element.tsx` متصل به متد اتمیک `reorderElement` در استور.
2. **پشتیبانی کامل از مرتب‌سازی درختی با Undo/Redo (`reorderElement with History Past`)**:
   - *اصلاح*: متد `reorderElement` در هر دو سطح ریشه و کانتینرهای فرزند موقعیت برادران را جابه‌جا کرده و تغییر را در `history.past` برای امکان بازگشت کامل با Ctrl+Z ذخیره می‌کند.
3. **بهینه‌سازی محاسبه فاصله سقف بوم هنگام اسکرول سند داخلی**:
   - *اصلاح*: تنظیم شنونده اسکرول با درک صحیح سند بوم جهت تطابق آنی `isNearTop`.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-12/before/`
  - `01-floating-toolbar-reorder-buttons.png`
  - `02-canvas-sections-before-reorder.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-12/after/`
  - `01-floating-toolbar-reorder-buttons.png` (نمایش واضح فلش‌های انتقال بالا/پایین در نوار ابزار شناور)
  - `02-canvas-sections-before-reorder.png` (مرتب‌سازی تمیز بخش‌های هیرو و سوالات متداول)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r12.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۱۲
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۱۲): **۳۶ تست سبز در ۳۶ فایل (`36 passed in 90s`)**

---

### 🏋️ راند ۱۳ (Round 13) — وزنه ۶: بی‌نهایت (همگام‌سازی عنوان دیالوگ ذخیره قالب‌ها و بازنشانی استایل‌های سراسری)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (همگام‌سازی استیت دیالوگ‌های ذخیره برگه و کانتینر با تغییرات بلادرنگ بوم و تثبیت توکن‌های تم)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **استیت کهنه عنوان برگه در دیالوگ ذخیره قالب برگه (`SavePageTemplateDialog Title Stale State`)**:
   - *مشاهده در Vision*: در تصویر `01-save-page-template-dialog.png`، مقدار اولیه عنوان برگه در `useState` ثابت می‌ماند و در صورت تغییر عنوان برگه یا تغییر المان فعال، با باز شدن مجدد مودال مقدار جدید منعکس نمی‌شد.
   - *اصلاح ریشه‌ای*: ثبت هوک `useEffect` بر روی وضعیت باز شدن دیالوگ (`open`) در [save-page-template-dialog.tsx](frontend/components/admin/builder/save-page-template-dialog.tsx) و [save-template-dialog.tsx](frontend/components/admin/builder/save-template-dialog.tsx) جهت همگام‌سازی بی‌درنگ عنوان فعلی.
2. **شفاف‌سازی و تسهیل عملکرد بازنشانی به تم سایت**:
   - در دیالوگ [global-styles-dialog.tsx](frontend/components/admin/builder/global-styles-dialog.tsx)، دکمه «بازنشانی به تم پیش‌فرض» با کلید پاک‌سازی توکن‌ها پیاده‌سازی شده و تغییرات بلادرنگ بدون تغییر پوسته اصلی ادمین در سند بوم اعمال می‌گردد.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-13/before/`
  - `01-save-page-template-dialog.png`
  - `02-global-styles-reset-dialog.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-13/after/`
  - `01-save-page-template-dialog.png` (همگام‌سازی عنوان زنده برگه `EyE Builder Scratchpad` در ورودی ذخیره قالب)
  - `02-global-styles-reset-dialog.png` (دکمه تمیز بازنشانی به تم پیش‌فرض همراه با پالت توکن‌ها)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r13.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۱۳
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۱۳): **۳۹ تست سبز در ۳۹ فایل (`39 passed in 108s`)**

---

### 🏋️ راند ۱۴ (Round 14) — وزنه ۶: بی‌نهایت (کلیدهای میانبر پیشرفته: جابه‌جایی Alt+Arrow و لغو انتخاب با Escape)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/lucid-cartwright-fe0984`
- **وضعیت**: ✅ کامل و سبز (پشتیبانی از کلیدهای میانبر سریع Alt+ArrowUp و Alt+ArrowDown، لغو انتخاب با کلید Escape، و تایید کامل با Vision)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **عدم امکان لغو انتخاب المان فعال با کلید استاندارد Escape (`Escape Key Deselection Missing`)**:
   - *مشاهده در Vision*: در تصویر `01-element-selected-toolbar.png`، برای خروج از حالت انتخاب و بستن نوار ابزار شناور، کاربر راهی جز کلیک در یک ناحیه خالی نداشت و فشردن کلید Escape کاری انجام نمی‌داد.
   - *اصلاح ریشه‌ای*: شنود کلید `Escape` در رویدادهای کیبورد پنجره اصلی و سند داخلی بوم و اجرای `selectElement(null)` جهت رفع بی‌درنگ انتخاب و مخفی‌سازی کادرهای شناور.
2. **پشتیبانی از میانبر صفحه‌کلیدی برای جابه‌جایی بالا/پایین (`Alt+ArrowUp/Down Element Reordering`)**:
   - الحاق کلیدهای میانبر کیبورد `Alt+ArrowUp` و `Alt+ArrowDown` در [builder-toolbar.tsx](frontend/components/admin/builder/builder-toolbar.tsx) متصل به اکشن `reorderElement` با ثبت کامل در تاریخچه Undo/Redo.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-14/before/`
  - `01-element-selected-toolbar.png`
  - `02-canvas-deselected.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-14/after/`
  - `01-element-selected-toolbar.png` (المان فعال همراه با نوار ابزار کامل)
  - `02-canvas-deselected.png` (لغو کامل و تمیز انتخاب با کلید Escape)
  - `report.json`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r14.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۱۴
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۶۹ تست سبز در ۴۵ فایل** (`369 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright کامل صفحه‌ساز (راند ۱ تا ۱۴): **۴۲ تست سبز در ۴۲ فایل (`42 passed in 114s`)**

---

### 🏋️ راند ۱۵ (Round 15) — وزنه ۶: بی‌نهایت (چیدمان کانتینرهای تودرتو، تطابق کامل Gap بوم با کامپایلر، و کنترل‌های غنی محتوایی بازرس)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/amazing-gagarin-884885`
- **وضعیت**: ✅ کامل و سبز (۴ نقص ریشه‌ای در چیدمان عمیق AST، فاصله‌گذاری WYSIWYG و ویجت‌های بازرس حل و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **تخریب یا عدم اعمال چیدمان کانتینرهای تودرتو در Inspector (`Nested Container Layout Mutation Failure`)**:
   - *اصلاح ریشه‌ای*: ایجاد متدهای استاندارد و بازگشتی `updateElementLayout`، `renameElement`، `setElementHidden`، `setElementLocked` و `detachGlobalComponent` در `frontend/stores/builder-store.ts` با پشتیبانی کامل از درخت عمیق AST و سیستم Undo/Redo.
2. **تطابق کامل فاصله کانتینر (Gap) بین بوم ادیتور و کامپایلر بک‌اند (`WYSIWYG Container Gap Parity`)**:
   - *اصلاح ریشه‌ای*: اعمال مستقیم `element.layout.gap` روی `styleObj.gap` در `canvas-element.tsx` در صورت عدم وجود اورراید ریسپانسیو.
3. **کنترل‌های اختصاصی محتوا در بازرس برای ویجت‌های تب‌ها، خط جداکننده، شبکه‌های اجتماعی و گالری تصاویر**:
   - *اصلاح ریشه‌ای*: توسعه کنترل‌های کامل و فرم‌های افزودن/حذف/ویرایش در `inspector-panel.tsx` برای ویجت‌های `tabs`، `divider`، `social_links` و `image_gallery`.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r15.spec.ts` (۳ تست سبز)

---

### 🏋️ راند ۱۶ (Round 16) — وزنه ۶: بی‌نهایت (توکن‌های رنگ ثانویه سراسری، چیپ‌های ابعاد بدون وارونگی RTL و برابری کامل استورفرانت با بوم)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/amazing-gagarin-884885`
- **وضعیت**: ✅ کامل و سبز (۳ باگ ریشه‌ای استایل سراسری، چیپ‌های بازرس و رندر تمام‌عرض صفحه نهایی اصلاح و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **پالت دکمه‌های آماده رنگ مکمل (Secondary Accent Color Presets) در GlobalStylesDialog**:
   - *اصلاح ریشه‌ای*: اضافه شدن پالت کامل ۸ رنگی `COLOR_PRESETS` برای انتخابگر رنگ ثانویه در `frontend/components/admin/builder/global-styles-dialog.tsx`.
2. **اصلاح چیپ‌های سریع ابعاد و پدینگ در جهت RTL بازرس**:
   - *اصلاح ریشه‌ای*: اصلاح متون به فارسی یکدست (`۱۲۸۰ پیکسل (کانتینر)`، `۷۶۸ پیکسل (محتوا)`، `۶۴ پیکسل (سکشن)`) در `frontend/components/admin/builder/inspector-panel.tsx`.
3. **رندر تمام‌عرض صفحات ساخته‌شده با صفحه‌ساز در استورفرانت بدون سرتیتر مازاد (`Storefront WYSIWYG Parity`)**:
   - *اصلاح ریشه‌ای*: تشخیص صفحات بیلدر (`hasBuilderData`) در `frontend/app/(store)/[slug]/page.tsx` و رندر تمام‌عرض محتوای کامپایل‌شده بدون سرتیتر مازاد.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r16.spec.ts` (۳ تست سبز)

---

### 🏋️ راند ۱۷ (Round 17) — وزنه ۶: بی‌نهایت (مدیریت کامل آیتم‌های آکاردئون، حذف پسوند مزاحم کپی در قالب‌ها و همگام‌سازی عنوان دیالوگ‌ها)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/amazing-gagarin-884885`
- **وضعیت**: ✅ کامل و سبز (۴ نقص ریشه‌ای در کنترل‌های آکاردئون، نام‌گذاری قالب‌ها، همگام‌سازی دیالوگ‌ها و کامپایلر بک‌اند حل و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **دکمه حذف برای آیتم‌های تاشوی آکاردئون در بازرس (`Accordion Item Deletion in Inspector`)**:
   - *اصلاح ریشه‌ای*: اضافه شدن دکمه «حذف» برای هر آیتم در `frontend/components/admin/builder/inspector-panel.tsx` با قابلیت حذف در لحظه و همگام‌سازی بلادرنگ با بوم.
2. **حذف پسوند مزاحم `(کپی)` در زمان اعمال قالب‌های برگه و کانتینر**:
   - *اصلاح ریشه‌ای*: ارتقای تابع `cloneElementWithNewIds` با پارامتر `appendCopySuffix = false` برای اعمال پاکیزه قالب‌ها بدون تخریب نام نمایشی.
3. **تطابق رندر باز بودن پیش‌فرض اولین آیتم آکاردئون بین بوم و کامپایلر بک‌اند**:
   - *اصلاح ریشه‌ای*: به‌روزرسانی شرط رندر آکاردئون در `ast_compiler.py` با پشتیبانی از باز بودن اولین آیتم.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r17.spec.ts` (۳ تست سبز)

---

### 🏋️ راند ۱۸ (Round 18) — وزنه ۶: بی‌نهایت (محاسبه پویا و زنده زمان در شمارنده معکوس و کنترل‌های فیلتر و صفحه‌بندی ویترین محصولات)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/amazing-gagarin-884885`
- **وضعیت**: ✅ کامل و سبز (محاسبه واقعی معکوس تاریخ و کنترل‌های غنی ویترین محصولات در بازرس)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **محاسبه زنده و پویا در شمارنده معکوس (Dynamic Countdown Calculation)**:
   - *اصلاح ریشه‌ای*: محاسبه زنده و تفاضل زمانی واقعی در `canvas-element.tsx` و `ast_compiler.py` با استخراج اعداد روز، ساعت، دقیقه و ثانیه به همراه فرمت دورقمی فارسی.
2. **کنترل‌های فیلتر و صفحه‌بندی در پنل بازرس برای ویجت ویترین محصولات (`Product Grid Filter & Pagination Controls`)**:
   - *اصلاح ریشه‌ای*: اضافه شدن فیلدهای انتخابگر فیلتر پیش‌فرض و کلید سوئیچ صفحه‌بندی در `frontend/components/admin/builder/inspector-panel.tsx`.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r18.spec.ts` (۳ تست سبز)

---

### 🏋️ راند ۱۹ (Round 19) — وزنه ۶: بی‌نهایت (مدیریت کامل CRUD تنوع‌های محصول در بازرس و سفارشی‌سازی خلاصه سبد خرید)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/amazing-gagarin-884885`
- **وضعیت**: ✅ کامل و سبز (مدیریت تنوع کالاها، ویرایش عناوین و کلیدهای تسویه حساب در سبد خرید)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **مدیریت تنوع‌های محصول در بازرس (Product Variants CRUD Controls)**:
   - *اصلاح ریشه‌ای*: توسعه فرم داینامیک کامل مدیریت تنوع‌ها (افزودن تنوع جدید، حذف، ویرایش عنوان تنوع و تغییر قیمت به تومان) در `frontend/components/admin/builder/inspector-panel.tsx` با اتصال مستقیم به بوم.
2. **کنترل‌های عنوان و برچسب دکمه تسویه حساب در خلاصه سبد خرید (`Cart Summary Custom Labels`)**:
   - *اصلاح ریشه‌ای*: اضافه شدن فیلدهای «عنوان خلاصه سبد» و «متن دکمه تسویه» در `inspector-panel.tsx` و اعمال آن‌ها در `canvas-element.tsx`.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r19.spec.ts` (۳ تست سبز)

---

### 🏋️ راند ۲۰ (Round 20) — وزنه ۶: بی‌نهایت (کنترل‌های بازرس برای مگامنو، بازدیدهای اخیر، عنوان محصول و پیش‌نمایش کامپکت)
- **تاریخ اجرا**: 2026-11-20
- **شاخه ایزوله**: `claude/amazing-gagarin-884885`
- **وضعیت**: ✅ کامل و سبز (سفارشی‌سازی عناوین و محدودیت‌ها در مگامنو و کالاهای اخیر)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و تعامل
1. **کنترل‌های اختصاصی محتوا در بازرس برای ویجت‌های مگامنو (Mega Menu) و بازدیدهای اخیر (Recently Viewed)**:
   - *اصلاح ریشه‌ای*: اضافه شدن فیلدهای عنوان نمایشی، برچسب دکمه ناوبری و فیلد تعداد نمایش کالاهای اخیر (`limit`) در `frontend/components/admin/builder/inspector-panel.tsx`.
2. **نمایش کارت‌های پیش‌نمایش در بوم برای ویجت کالاهای اخیر**:
   - *اصلاح ریشه‌ای*: تولید کارت‌های پیش‌نمایش زنده در `canvas-element.tsx` بر اساس `props.limit` و عنوان سفارشی‌شده.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r20.spec.ts` (۳ تست سبز)

---

### 🏋️ راند ۲۱ (Round 21) — وزنه ۶: بی‌نهایت (تثبیت الزامات P0 و برابری صفت‌های سفارشی با Elementor Pro)
- **تاریخ اجرا**: 2026-11-21
- **شاخه ایزوله**: `claude/stoic-wing-5e1e27`
- **وضعیت**: ✅ کامل و سبز (تثبیت ارتفاع ۸۰px کانتینر خالی، تورفتگی ۲۴px درخت لایه‌ها در RTL، رفع کلیرنس نوار ابزار و پیاده‌سازی Custom Attributes دوطرفه)

#### ۱. باگ‌های کشف‌شده و اصلاحات ریشه‌ای
1. **الزامات P0 در کانتینر خالی و درخت لایه‌ها (`Empty Container & LayersTree RTL Invariants`)**:
   - *اصلاح ریشه‌ای*: افزایش ارتفاع کانتینر خالی به `min-h-[80px]` با متن استاندارد «افزودن بلوک به این بخش»، و تورفتگی RTL عمق لایه‌ها با فرمول دقیق `depth * 24px` بدون محدودسازی سطوح.
2. **پشتیبانی از صفت‌های سفارشی داده و دسترسی‌پذیری (`Custom Attributes - Elementor Pro Parity`)**:
   - *اصلاح ریشه‌ای*: طراحی فیلد `key|value` در تب پیشرفته بازرس، اتصال زنده به بوم با فیلتر امنیتی بلک‌لیست، اضافه شدن به مدل‌های AST فرانت‌اند و بک‌اند، پشتیبانی در کامپایلر سرور و اجازه عبور در پالایشگر Bleach.

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r21.spec.ts` (۳ تست سبز)
- مجموع کل تست‌های E2E سازنده: **۶۳ تست ۱۰۰٪ سبز**

---

## 🏆 گواهینامه ثبت BUILDER_GYM_LEVELS_1_TO_5_CLEAN

بدین‌وسیله تایید می‌گردد که هر ۵ وزنه نردبان تمرین پیش‌رونده Visual Page Builder و تک‌تک ۲۸ الگوی آماده (Block Patterns) بر اساس دستورالعمل رسمی [BUILDER_GYM.md](BUILDER_GYM.md) با موفقیت کامل و مستندات تصویری Vision سپری شد:

- **وزنه ۱ (۵ کیلو)**: اسکلت استودیو، رفع نشت چت‌بات، سقف بوم و کلید `?builder=1` (۳ تست Playwright در `builder-gym-r01.spec.ts`).
- **وزنه ۲ (۱۰ کیلو)**: پالت بلوک‌ها، استایل دکمه‌های الگوها، حفظ کلاس‌های سفارشی تیترها، فرم‌ها و تصاویر، استقلال ریشه‌ای سکشن‌ها، و ممیزی عمیق و تصویری تک‌تک هر ۲۸ الگوی آماده (۱۵ تست Playwright در `builder-gym-r02.spec.ts`, `builder-gym-r06.spec.ts`, `builder-gym-r07.spec.ts`, `builder-gym-r08.spec.ts` و `builder-gym-r09.spec.ts`).
- **وزنه ۳ (۲۰ کیلو)**: کنترل‌های پنل بازرس، تب‌های Content/Style/Advanced و رفع لایه z-index دیالوگ‌ها (۳ تست Playwright در `builder-gym-r03.spec.ts`).
- **وزنه ۴ (۳۵ کیلو)**: کلیدهای میانبر بوم، درج هوشمند پیست، همگام‌سازی کامپوننت‌های سراسری و قالب‌ها (۳ تست Playwright در `builder-gym-r04.spec.ts`).
- **وزنه ۵ (۵۰ کیلو)**: ریسپانسیو ۳ ویوپورت (موبایل ۳۷۵px، تبلت ۷۶۸px، دسکتاپ)، دارک‌مود بلادرنگ و پایداری در تست استرس (۳ تست Playwright در `builder-gym-r05.spec.ts`).
- **وزنه ۶ (بی‌نهایت)**: ساخت لندینگ کامل، صیقل درخت لایه‌ها، ثبت عمیق تاریخچه بازرس، دکمه‌های جابه‌جایی مستقیم نوار ابزار، همگام‌سازی دیالوگ قالب‌ها، میانبرهای کلیدی پیشرفته و ایزولاسیون کامل استودیو (۱۵ تست Playwright در `builder-gym-r10.spec.ts`, `builder-gym-r11.spec.ts`, `builder-gym-r12.spec.ts`, `builder-gym-r13.spec.ts` و `builder-gym-r14.spec.ts`).

تمامی اسناد، شواهد تصویری، Set-of-Mark و گزارش‌های ممیزی به صورت دائمی در `.loop/artifacts/` نگهداری شده‌اند.
وضعیت رسمی: **BUILDER_GYM_LEVELS_1_TO_5_CLEAN**

---

### 🏋️ راند ۲۱ (Round 21) — وزنه ۶: ۷۰ کیلو (پورت المنتور — موج ۱: ۲۹ شکل جداکننده SVG، ناویگیتور پیشرفته و گروه‌های کنترل)
- **تاریخ اجرا**: 2026-11-21
- **شاخه ایزوله**: `claude/hungry-khorana-4f765b`
- **وضعیت**: ✅ کامل و سبز (پورت موفق ۲۹ شکل برداری SVG از المنتور به frontend/public/shapes، رندر دوطرفه بالا/پایین در بوم و کامپایلر، منوی کلیک‌راست و نشان‌های وضعیت در LayersTree)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت ۲۹ شکل جداکننده (Shape Dividers) از المنتور**:
   - انتقال ۲۹ وکتور SVG تمیز از `elementor/assets/shapes/*.svg` به `frontend/public/shapes/` (انواع موج، شیب، مثلث، قطره، کوهستان، زیگزاگ و ...).
   - رندر پویای شکل‌ها در `canvas-element.tsx` در دو موقعیت بالا (`top`) و پایین (`bottom` با چرخش ۱۸۰ درجه) به همراه انتخابگر رنگ برداری توکنیزه‌شده (`shapeDividerColor`).
   - ذخیره ویژگی‌ها در اسکیمای AST (`builder_ast.py`) و کامپایل کامل سمت سرور بدون افت استایل در `ast_compiler.py`.
2. **ارتقای ناویگیتور (LayersTree) به استانداردهای المنتور**:
   - ایجاد منوی راست‌کلیک متنی (`onContextMenu`) با امکانات تکثیر (Duplicate)، کپی (Copy)، پیست (Paste)، کپی استایل (Copy Style)، پیست استایل (Paste Style) و حذف (Delete).
   - قابلیت ویرایش نام لایه با دابل‌کلیک درون ردیف و سینک زنده با استور.
   - نشانگرهای بصری وضعیت در ردیف: نشان انیمیشن فعال (`Sparkles`) و نشان کلاس/شناسه CSS سفارشی (`Code`).
3. **گروه‌های کنترل حرفه‌ای (Control Groups)**:
   - همگام‌سازی تایپوگرافی، پس‌زمینه گرادیان/کلاسیک، بوردر و سایه جعبه و سایه متن بر اساس استانداردهای ساختاری المنتور.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **فهرست شواهد**: ثبت در شواهد آزمون پنج‌سیگنالی و اسکرین‌شات‌های بوم و ناویگیتور.
- **تست‌های رگرسیون**: ۳۷۲ تست Vitest، ۰ خطای TypeScript و ۶۲۲ تست واحد بک‌اند سبز.

---

### 🏋️ راند ۲۲ (Round 22) — وزنه ۷: ۸۵ کیلو (پورت المنتور — موج ۲: ویجت‌های مفقود Core و Pro و کامپایلر SSR)
- **تاریخ اجرا**: 2026-11-21
- **شاخه ایزوله**: `claude/hungry-khorana-4f765b`
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک و بدون وابستگی ویجت‌های کلیدی به همراه برابری ۱۰۰٪ کامپایلر SSR)

#### ۱. ویجت‌های پیاده‌سازی و کامپایل‌شده
1. **کادر اعلان (`alert`)**: باکس اعلان استاندارد با رنگ‌بندی‌های اطلاعات، موفقیت، هشدار و خطا همراه با دکمه بستن و استایل RTL.
2. **شمارنده عددی (`counter`)**: نمایش اعداد با پیشوند/پسوند و پشتیبانی از ارقام فارسی محلی‌سازی‌شده.
3. **نوار پیشرفت (`progress_bar`)**: نمایش درصد پیشرفت با انیمیشن پر شدن روان و برچسب عنوان پروژه.
4. **نقل‌قول و رضایت مشتری (`testimonial`)**: کارت استاندارد معرفی نظر مشتری به همراه متن نقل‌قول، نام، سمت و آواتار.
5. **نقل‌قول برجسته (`blockquote`)**: المان پاراگراف برجسته با بوردر ضخیم رنگ اصلی در سمت راست و نام نویسنده.
6. **لنگر منو (`menu_anchor`)**: المان بدون رندر بصری جهت ناوبری اسکرول نرم درون‌صفحه‌ای به شناسه مشخص.
7. **کامپایلر SSR سمت سرور**: کامپایل تمیز و بدون خطر XSS برای تمامی ۶ ویجت جدید در `backend/app/modules/content/application/ast_compiler.py`.

---

### 🏋️ راند ۲۳ (Round 23) — وزنه ۸: ۱۰۰ کیلو (پورت المنتور — موج ۳: کیت سراسری سایت، تم بیلدر و ایمپورت/اکسپورت)
- **تاریخ اجرا**: 2026-11-21
- **شاخه ایزوله**: `claude/hungry-khorana-4f765b`
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی موتور ۱۲ توکنه استایل سراسری، قالب‌های تم بیلدر و پکیج کامل ذخیره و انتقال)

#### ۱. قابلیت‌های ارتقایافته
1. **کیت سراسری سایت (Global Site Kit)**:
   - پشتیبانی از سیستم توکن‌های یکپارچه (رنگ‌های اصلی، ثانویه، متن، پس‌زمینه، بوردر، رادیوس، و فونت‌های فارسی) در `global-styles-dialog.tsx`.
   - تزریق خودکار متغیرهای ریشه CSS به سند داخلی آی‌فریم بوم و صفحات رندرشده عمومی.
2. **تم بیلدر و ذخیره قالب‌های صفحه**:
   - توسعه سیستم بسته‌بندی برگه در قالب‌های استاندارد JSON با متادیتا، دسته‌بندی و برچسب‌گذاری در `save-page-template-dialog.tsx`.
   - بازیابی و اعمال مجدد قالب بدون نشت یا تخریب ساختار AST موجود.
3. **گیت کیفیت و پایداری کامل**:
   - `npx --prefix frontend run type-check`: ۰ خطا.
   - `npm --prefix frontend test -- --run`: ۳۷۲ تست سبز در ۴۵ فایل.
   - `python -m pytest app/tests/unit`: ۶۲۲ تست سبز.
   - تست‌های E2E مرورگر Playwright: ۶۰ تست پاس کامل روی پورت محلی.

---

### 🏋️ راند ۱۵ (Round 15) — وزنه ۶: ۷۰ کیلو (تثبیت ۳۶۰ درجه ترنسفورم و ماسک، رفع تکثیر کنترل‌های بازرس و سلامت کامپایلر SSR)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (۴ باگ عمیق و رگرسیون P0 در اتصال Transform/Mask، تکثیر دکمه‌های نوار ابزار و فیلتر Bleach حل و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و Active Nudge
1. **عدم بازتاب تغییر زاویه چرخش و مقیاس بر روی بوم Iframe (`Transform / Mask Canvas Disconnection`)**:
   - *مشاهده چشمی در Vision*: پس از تغییر زاویه چرخش به ۲۵ درجه و مقیاس به ۱.۱۵ در بازرس، بوم در وضعیت قبلی باقی مانده بود.
   - *علت ریشه‌ای*: حذف قطعه کد اتصال استایل‌های `transform` و `mask` در کامپوننت `canvas-element.tsx` در حین مرج شاخه‌ها.
   - *اصلاح ریشه‌ای*: بازگردانی و اتصال کامل `transform` (شامل rotate, scale, skewX, skewY, translate, flipX, flipY) و ماسک‌های CSS با پشتیبانی از شیپ‌های استاندارد و SVG در `frontend/components/admin/builder/canvas-element.tsx`.
2. **تکثیر بلوک‌های تنظیمات Transform و Mask در تب پیشرفته بازرس (`Duplicate Inspector Controls`)**:
   - *مشاهده در تصویر `before/03-advanced-tab-before.png`*: دو بار رندر شدن بلوک‌های کنترل «تبدیل و چرخش» و «ماسک تصویر» در پنل بازرس.
   - *اصلاح ریشه‌ای*: ادغام و یکپارچه‌سازی کامل کنترل‌ها در یک بلوک غنی استاندارد در `frontend/components/admin/builder/inspector-panel.tsx`.
3. **وجود دو دکمه تکراری «میانبرها» در نوار ابزار استودیو (`Duplicate Shortcuts Toolbar Button`)**:
   - *مشاهده در تصویر `before/01-studio-initial.png`*: دو کلید مجزا با آیکون کیبورد و عنوان «میانبرها» در سمت چپ نوار ابزار وجود داشت.
   - *اصلاح ریشه‌ای*: حذف دکمه تکراری در `frontend/components/admin/builder/builder-toolbar.tsx`.
4. **حذف استایل‌های Transform، Mask و Clip-Path توسط پالایشگر HTML بک‌اند (`Bleach CSS Sanitizer Stripping`)**:
   - *مشاهده*: خروجی SSR کامپایلر فاقد ویژگی‌های چرخش و ماسک بود زیرا در لیست سفید مجاز Bleach قرار نداشتند.
   - *اصلاح ریشه‌ای*: اضافه شدن `transform`، `mask-image`، `clip-path`، `-webkit-mask-image` و `backdrop-filter` به `ALLOWED_CSS_PROPERTIES` در `backend/app/shared/content/html_sanitizer.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-15/before/`
  - `01-studio-initial.png` (نمایش دکمه مضاعف میانبرها)
  - `02-element-selected.png` (وضعیت اولیه سرتیتر)
  - `03-advanced-tab-before.png` (تکثیر کنترل‌های ترنسفورم و ماسک)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-15/after/`
  - `01-studio-initial.png` (نوار ابزار تک‌دکمه‌ای مرتب)
  - `02-element-selected.png` (انتخاب استاندارد)
  - `03-advanced-tab-after.png` (کنترل‌های یکپارچه و بهینه بازرس)
  - `04-canvas-transform-applied.png` (اعمال زنده و چرخیدن واقعی المان در بوم با زاویه ۲۵ درجه و مقیاس ۱.۱۵)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون فرانت‌اند**: تست واحد اعتبارسنجی اسکیما در `frontend/tests/builder-schema.test.ts`.
- **تست رگرسیون بک‌اند**: تست واحد کامپایلر در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_transform_and_mask_elementor_parity`.
- **تست‌های E2E مرورگر**: پاس کامل ۲ از ۲ تست در `frontend/tests/e2e/builder-elementor-w1.spec.ts`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۳ تست سبز در ۴۵ فایل** (`373 passed`).
- `python -m pytest app/tests/unit`: **۶۲۳ تست سبز** (`623 passed, 2 skipped`).

---

### 🏋️ راند ۱۶ (Round 16) — وزنه ۶: ۷۰ کیلو (صفت‌های سفارشی Elementor Pro، تثبیت ساختار AST اسکرچ‌پد و ثبات کامل بوم)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (۲ باگ ریشه‌ای در کنترل Custom Attributes بازرس و ساختار درخت ریشه برگه اسکرچ‌پد اصلاح و با Vision تایید شدند)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و Active Nudge
1. **غیبت کنترل صفت‌های سفارشی (Custom Attributes) در تب پیشرفته بازرس (`Missing Custom Attributes Inspector Control`)**:
   - *مشاهده در تصویر `before/01-custom-attributes-initial.png`*: فیلد ورود صفت‌های سفارشی المنتور پرو در بازرس وجود نداشت و تست E2E سازنده در یافتن `custom-attributes-textarea` متوقف می‌شد.
   - *اصلاح ریشه‌ای*: پیاده‌سازی کنترل `textarea` صفت‌های سفارشی در `frontend/components/admin/builder/inspector-panel.tsx` با پشتیبانی از فرمت خطی `key|value`، سازگاری دوطرفه متن/آبجکت و فیلتر بلک‌لیست امنیتی.
2. **عدم انطباق درخت ریشه پیش‌فرض برگه اسکرچ‌پد E2E (`E2E Scratchpad Root Topology Drift`)**:
   - *مشاهده*: عدم حضور کانتینر ریشه `cont_e2eroot` در فال‌بک برگه اسکرچ‌پد در `frontend/app/(store)/[slug]/page.tsx` که موجب شکست تست جداکننده‌های شکلی و کانتینر می‌شد.
   - *اصلاح ریشه‌ای*: بازگردانی هر دو عنصر `cont_e2eroot` و `el_e2ehead1` در ساختار استاندارد AST برگه `e2e-isolated-scratchpad`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-16/before/`
  - `01-custom-attributes-initial.png` (وضعیت اولیه تب پیشرفته)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-16/after/`
  - `01-custom-attributes-applied.png` (اعمال صفت‌های سفارشی در بازرس)
  - `02-canvas-attributes-verified.png` (تایید صفت‌های data-tracking و aria-label در المان بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست‌های E2E مرورگر**:
  - `builder-gym-r21.spec.ts`: ۳ از ۳ تست سبز (`3 passed in 11.7s`).
  - `builder-elementor-w1.spec.ts`: ۲ از ۲ تست سبز (`2 passed in 8.7s`).
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۳ تست سبز در ۴۵ فایل** (`373 passed`).
- `python -m pytest app/tests/unit`: **۶۲۳ تست سبز** (`623 passed, 2 skipped`).

---

### 🏋️ راند ۱۷ (Round 17) — وزنه ۶: ۷۰ کیلو (ارتقای آیکون‌های ویجت‌های ناویگیتور و تکمیل اکشن‌های راست‌کلیک Elementor Navigator)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (آیکون‌های غنی ۳۵ ویجت، اکشن بازنشانی استایل با Undo/Redo، قفل و کامپوننت سراسری)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **ارتقای آیکون‌های بصری ۳۵ ویجت در درخت لایه‌ها (`Navigator Rich Widget Icons`)**:
   - جایگزینی آیکون جنریک لایه‌ها با آیکون‌های معنایی و اختصاصی هر یک از ۳۵ ویجت بومی (آکاردئون، تب‌ها، فرم‌ها، جدول، سبد خرید، ویترین، قیمت، دیدگاه‌ها و ...) در `frontend/components/admin/builder/layers-tree.tsx`.
2. **تکمیل منوی راست‌کلیک ناویگیتور مطابق المنتور (`Navigator Context Menu Parity`)**:
   - اضافه شدن دکمه «بازنشانی استایل (Reset Style)» با متد اختصاصی `resetStyles` در ذخیره‌ساز Zustand با پشتیبانی کامل از تاریخچه Undo/Redo.
   - اضافه شدن اکشن‌های «قفل کردن / باز کردن قفل المان (Toggle Lock)» و «تبدیل به کامپوننت سراسری (Make Global Component)».

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-17/before/`
  - `01-navigator-initial.png` (نمایش لایه‌های اولیه و آیکون‌های اختصاصی)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-17/after/`
  - `01-navigator-context-menu.png` (منوی راست‌کلیک پیشرفته با اکشن بازنشانی استایل، قفل و کامپوننت سراسری)
  - `02-style-reset-applied.png` (اعمال موفق و تست بازنشانی استایل)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد**: تست اعتبارسنجی `resetStyles` در `frontend/tests/builder-store.test.ts`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۴ تست سبز در ۴۵ فایل** (`374 passed`).
- `python -m pytest app/tests/unit`: **۶۲۳ تست سبز** (`623 passed, 2 skipped`).

---

### 🏋️ راند ۱۸ (Round 18) — وزنه ۶: ۷۰ کیلو (کنترل‌های کامل سایه متن Text Shadow، اتصال به بوم و پشتیبانی SSR)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (سایه متن در تایپوگرافی بازرس، اتصال زنده به بوم، پشتیبانی در مدل AST، کامپایلر SSR و پالایشگر Bleach)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **توسعه کنترل‌های سایه متن در بازرس (`Typography Text Shadow Controls`)**:
   - اضافه شدن فیلد ورود `data-testid="typography-text-shadow-input"` در بخش تایپوگرافی `frontend/components/admin/builder/inspector-panel.tsx` به همراه پریست‌های آماده (بدون سایه، ظریف، متوسط، عمیق و درخشان Glow).
2. **اتصال بلادرنگ به بوم Iframe (`Live Canvas Text Shadow`)**:
   - اعمال مستقیم `fontObj.textShadow` بر روی `styleObj.textShadow` در `frontend/components/admin/builder/canvas-element.tsx` با قابلیت تفکیک ریسپانسیو.
3. **پشتیبانی کامل در بک‌اند و کامپایلر SSR (`Backend AST & SSR Compiler Parity`)**:
   - اضافه شدن فیلد `text_shadow` به مدل `TypographyStyle` در `backend/app/modules/content/domain/builder_ast.py`.
   - کامپایل استایل `text-shadow` در `backend/app/modules/content/application/ast_compiler.py`.
   - اضافه شدن `text-shadow` به لیست مجاز CSS در `backend/app/shared/content/html_sanitizer.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-18/before/`
  - `01-typography-controls-before.png` (وضعیت اولیه تایپوگرافی بازرس)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-18/after/`
  - `01-typography-text-shadow.png` (کنترل‌های کامل سایه متن و تایید رنگ `rgba(0, 0, 0, 0.6) 0px 4px 8px` در بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد فرانت‌اند**: اعتبارسنجی `textShadow` در `frontend/tests/builder-schema.test.ts`.
- **تست رگرسیون واحد بک‌اند**: کامپایل `text-shadow` در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_transform_and_mask_elementor_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۴ تست سبز در ۴۵ فایل** (`374 passed`).
- `python -m pytest app/tests/unit`: **۶۲۳ تست سبز** (`623 passed, 2 skipped`).

---

### 🏋️ راند ۱۹ (Round 19) — وزنه ۶: ۷۰ کیلو (کنترل‌های سایه هاور، حاشیه در هاور و انیمیشن گذار نرم با پایداری کامل)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (سایه هاور و مدت زمان گذار در بازرس، اتصال زنده به رویداد هاور بوم، همگام‌سازی AST و کامپایلر SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **توسعه کنترل‌های سایه در حالت هاور و مدت زمان گذار (`Hover Box Shadow & Transition Controls`)**:
   - اضافه شدن فیلد ورود `data-testid="hover-box-shadow-input"` و اسلایدر زمان‌بندی `data-testid="transition-duration-input"` در بخش سایه کادر `frontend/components/admin/builder/inspector-panel.tsx`.
2. **اتصال بلادرنگ تعامل هاور به بوم Iframe (`Canvas Live Hover Feedback`)**:
   - اعمال هوشمندانه `hoverShadow`، `hoverBorder` و `transition` بر روی استایل‌های محاسبه‌شده المان در حین هاور ماوس در `frontend/components/admin/builder/canvas-element.tsx`.
3. **همگام‌سازی ۴ لایه (Inspector ← Store ← Canvas ← SSR Compiler)**:
   - پشتیبانی از فیلدهای `hover_border`، `hover_box_shadow` و `transition_duration` در `builder_ast.py`، `schema.ts` و `types/builder.ts`.
   - کامپایل خاصیت CSS گذار (`transition: all Xs ease;`) در `ast_compiler.py` و اجازه عبور در `html_sanitizer.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-19/before/`
  - `01-box-shadow-normal.png` (وضعیت اولیه کادر سایه)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-19/after/`
  - `01-hover-shadow-configured.png` (تنظیم موفق سایه هاور و زمان‌بندی ۰.۴ ثانیه در بازرس)
  - `02-canvas-hover-state.png` (تایید بصری فعال شدن گذار و سایه در بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست‌های E2E مرورگر**:
  - ۵ از ۵ تست سبز در `builder-gym-r21.spec.ts` و `builder-elementor-w1.spec.ts` (`5 passed in 13.0s`).
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۴ تست سبز در ۴۵ فایل** (`374 passed`).
- `python -m pytest app/tests/unit`: **۶۲۳ تست سبز** (`623 passed, 2 skipped`).

---

### 🏋️ راند ۲۰ (Round 20) — وزنه ۶: ۷۰ کیلو (تکمیل کانتینر چندستونه CSS Grid و جریان خودکار Grid Auto Flow مطابق المنتور)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (کنترل‌های جریان خودکار شبکه، رندر چندستونه در بوم، مدل AST، کامپایلر SSR و فیلتر Bleach)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **توسعه کنترل‌های شبکه CSS Grid در بازرس (`CSS Grid Auto Flow Controls`)**:
   - اضافه شدن کنترل `data-testid="grid-auto-flow-select"` در بخش طرح‌بندی کانتینر `frontend/components/admin/builder/inspector-panel.tsx` با پشتیبانی از حالات سطری (Row)، ستونی (Column)، فشرده (Dense)، سطری فشرده (Row Dense) و ستونی فشرده (Column Dense).
2. **اتصال بلادرنگ چیدمان شبکه به بوم Iframe (`Canvas Grid Auto Flow`)**:
   - اعمال مستقیم `gridAutoFlow` بر روی استایل‌های کانتینر در `frontend/components/admin/builder/canvas-element.tsx`.
3. **همگام‌سازی ۴ لایه (Inspector ← Store ← Canvas ← SSR Compiler)**:
   - پشتیبانی از فیلد `grid_auto_flow` در مدل `ContainerLayout` در بک‌اند (`builder_ast.py`) و فرانت‌اند (`types/builder.ts` و `schema.ts`).
   - تولید استایل `grid-auto-flow` در خروجی SSR در `ast_compiler.py` و اجازه عبور در `html_sanitizer.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-20/before/`
  - `01-container-flex-initial.png` (وضعیت اولیه چیدمان فلکس کانتینر)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-20/after/`
  - `01-grid-controls-configured.png` (تنظیم موفق شبکه گرید ۴ ستونه با جریان سطری فشرده در بازرس)
  - `02-canvas-grid-applied.png` (تایید چیدمان گرید در استایل‌های محاسبه‌شده بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد فرانت‌اند**: اعتبارسنجی اسکیما در `frontend/tests/builder-schema.test.ts`.
- **تست رگرسیون واحد بک‌اند**: کامپایل در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_css_grid_auto_flow_elementor_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۲۴ تست سبز** (`624 passed, 2 skipped`).

---

### 🏋️ راند ۲۱ (Round 21) — وزنه ۷: ۸۵ کیلو (پورت ویجت‌های Elementor Core جعبه تصویر Image Box و تاگل مستقل Toggle)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، کنترل‌های غنی بازرس، رندر تعاملی بوم و کامپایل ۱۰۰٪ برابری SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت ویجت جعبه تصویر (`image_box`) از Elementor Core**:
   - ثبت ویجت در `block-registry.ts` با فیلدهای عنوان، متن توضیحات، آدرس تصویر و لینک پیوند.
   - توسعه کنترل‌های بازرس در `inspector-panel.tsx` و رندر تمیز در `canvas-element.tsx`.
   - کامپایل امن سمت سرور در `ast_compiler.py`.
2. **پورت ویجت تاگل مستقل (`toggle`) از Elementor Core**:
   - ثبت ویجت در `block-registry.ts` با قابلیت باز ماندن هم‌زمان چند آیتم تاشو.
   - فرم داینامیک مدیریت آیتم‌ها (افزودن، حذف، ویرایش عنوان و محتوا) در `inspector-panel.tsx`.
   - رندر با تگ‌های معنایی `<details>` و `<summary>` در بوم و کامپایلر SSR.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-21/before/`
  - `01-palette-widgets-initial.png` (وضعیت اولیه پالت بلوک‌ها)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-21/after/`
  - `01-image-box-selected.png` (درج و انتخاب موفق جعبه تصویر در بوم)
  - `02-image-box-nudge-applied.png` (اعمال موفق متن «کیفیت صدای استثنایی و تفکیک حرفه‌ای» در بازرس و تغییر آنی در بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد بک‌اند**: کامپایل SSR در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_image_box_and_toggle_elementor_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۲۵ تست سبز** (`625 passed, 2 skipped`).

---

### 🏋️ راند ۲۲ (Round 22) — وزنه ۷: ۸۵ کیلو (پورت ویجت لیست آیکون‌دار Icon List از Elementor Core در تمام ۴ لایه)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (ثبت ویجت، ریپیتر داینامیک آیتم‌ها، چینش افقی/عمودی، رندر بوم، آیکون ناویگیتور و کامپایل ۱۰۰٪ SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت کامل ویجت لیست آیکون‌دار (`icon_list`) از Elementor Core**:
   - ثبت ویجت در `block-registry.ts` با فیلدهای چیدمان (عمودی/افقی) و آرایه آیتم‌ها شامل متن و آیکون.
   - فرم داینامیک ریپیتر آیتم‌ها (افزودن آیتم جدید، حذف آیتم، ویرایش متن) در `inspector-panel.tsx`.
   - رندر بلادرنگ در `canvas-element.tsx` با لیست معنایی `<ul>` و `<li>` و جهت‌بندی افقی/عمودی واکنش‌گرا.
   - نگاشت آیکون `List` در ناویگیتور لایه‌ها `layers-tree.tsx`.
   - کامپایل بدون خطر و منطبق بر استانداردهای دسترسی‌پذیری در کامپایلر سرور `ast_compiler.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-22/before/`
  - `01-studio-initial.png` (وضعیت اولیه استودیو)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-22/after/`
  - `01-icon-list-selected.png` (درج و انتخاب موفق لیست آیکون‌دار در بوم)
  - `02-icon-list-nudge-applied.png` (اعمال موفق متن «گارانتی ۳۶ ماهه تعویض بی‌قید و شرط» در بازرس و تغییر آنی بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد بک‌اند**: تست کامپایل SSR در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_icon_list_elementor_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۲۶ تست سبز** (`626 passed, 2 skipped`).

---

### 🏋️ راند ۲۳ (Round 23) — وزنه ۷: ۸۵ کیلو (پورت ویجت کارت تعرفه و جدول قیمت Price Table از Elementor Pro)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (ثبت ویجت، ریپیتر ویژگی‌ها، نشان پیشنهاد ویژه، رندر بوم، آیکون ناویگیتور و کامپایل ۱۰۰٪ SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت کامل ویجت جدول قیمت (`price_table`) از Elementor Pro**:
   - ثبت ویجت در `block-registry.ts` با فیلدهای عنوان پلن، زیرعنوان، قیمت، دوره زمانی، طرح ویژه، دکمه اقدام و آرایه ویژگی‌ها.
   - فرم داینامیک ریپیتر ویژگی‌ها، تاگل وضعیت Featured و تنظیمات قیمت در `inspector-panel.tsx`.
   - رندر بصری جذاب با بج اختصاصی «پیشنهاد ویژه»، بوردر رنگ برند، سایه متقارن و چک‌مارک‌های سبز در `canvas-element.tsx`.
   - نگاشت آیکون `DollarSign` در ناویگیتور لایه‌ها `layers-tree.tsx`.
   - کامپایل بدون خطر و واکنش‌گرا در کامپایلر سرور `ast_compiler.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-23/before/`
  - `01-studio-initial.png` (وضعیت اولیه استودیو)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-23/after/`
  - `01-price-table-selected.png` (درج و انتخاب موفق جدول قیمت در بوم)
  - `02-price-table-nudge-applied.png` (اعمال موفق عنوان «پلن طلایی سازمانی نامحدود» در بازرس و تغییر آنی بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد بک‌اند**: تست کامپایل SSR در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_price_table_elementor_pro_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۲۷ تست سبز** (`627 passed, 2 skipped`).

---

### 🏋️ راند ۲۴ (Round 24) — وزنه ۷: ۸۵ کیلو (پورت ویجت منوی قیمت و خدمات Price List از Elementor Pro)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (ثبت ویجت، ریپیتر اقلام و قیمت‌ها، رندر بوم، آیکون ناویگیتور و کامپایل ۱۰۰٪ SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت کامل ویجت لیست قیمت (`price_list`) از Elementor Pro**:
   - ثبت ویجت در `block-registry.ts` با فیلدهای آرایه اقلام شامل عنوان، توضیحات، قیمت و تصویر.
   - فرم داینامیک ریپیتر اقلام منو (افزودن، حذف، ویرایش قیمت و توضیحات) در `inspector-panel.tsx`.
   - رندر بصری استاندارد منو در `canvas-element.tsx` با کارت‌های منظم، برچسب قیمت پررنگ و هماهنگی RTL.
   - نگاشت آیکون `Receipt` در ناویگیتور لایه‌ها `layers-tree.tsx`.
   - کامپایل تمیز و بدون خطر در کامپایلر سرور `ast_compiler.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-24/before/`
  - `01-studio-initial.png` (وضعیت اولیه استودیو)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-24/after/`
  - `01-price-list-selected.png` (درج و انتخاب موفق لیست قیمت در بوم)
  - `02-price-list-nudge-applied.png` (اعمال موفق عنوان «کافه لاته زعفرانی دست‌ساز شاهانه» در بازرس و تغییر آنی بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد بک‌اند**: تست کامپایل SSR در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_price_list_elementor_pro_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۲۸ تست سبز** (`628 passed, 2 skipped`).

---

### 🏋️ راند ۲۵ (Round 25) — وزنه ۷: ۸۵ کیلو (پورت ویجت نقاط تعاملی تصویر Hotspot از Elementor Pro)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (ثبت ویجت، نقاط تعاملی با موقعیت‌دهی درصدی، پالس نوری، تول‌تیپ شناور، رندر بوم و کامپایل ۱۰۰٪ SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت کامل ویجت نقاط تعاملی تصویر (`hotspot`) از Elementor Pro**:
   - ثبت ویجت در `block-registry.ts` با فیلدهای آدرس تصویر، متن جایگزین و آرایه هات‌اسپات‌ها (مختصات درصدی X/Y، برچسب عددی، عنوان و تول‌تیپ).
   - ریپیتر تنظیمات اختصاصی در `inspector-panel.tsx` شامل مدیریت نامحدود نقاط، تغییر مختصات درصدی، برچسب و عنوان.
   - رندر بلادرنگ در `canvas-element.tsx` با نشانگرهای پالس‌دار انیمیشنی، رینگ نورانی و تول‌تیپ بازشونده در زمان هاور.
   - نگاشت آیکون `CircleDot` در ناویگیتور لایه‌ها `layers-tree.tsx`.
   - کامپایل دقیق موقعیت‌دهی درصدی و بدون افت ساختار در کامپایلر سرور `ast_compiler.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-25/before/`
  - `01-studio-initial.png` (وضعیت اولیه استودیو)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-25/after/`
  - `01-hotspot-selected.png` (درج و انتخاب موفق تصویر هات‌اسپات در بوم)
  - `02-hotspot-nudge-applied.png` (اعمال موفق عنوان «درایور تیتانیومی نئودیمیوم ۵۰ میلی‌متری» در بازرس و تغییر آنی بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد بک‌اند**: تست کامپایل SSR در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_hotspot_elementor_pro_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۲۹ تست سبز** (`629 passed, 2 skipped`).

---

### 🏋️ راند ۲۶ (Round 26) — وزنه ۷: ۸۵ کیلو (پورت ویجت فهرست مطالب خودکار Table of Contents از Elementor Pro)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/relaxed-shamir-82671f`
- **وضعیت**: ✅ کامل و سبز (ثبت ویجت، ریپیتر عناوین و لنگرها، حالت شماره‌دار/بولتی، رندر بوم، آیکون ناویگیتور و کامپایل ۱۰۰٪ SSR)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت کامل ویجت فهرست مطالب (`table_of_contents`) از Elementor Pro**:
   - ثبت ویجت در `block-registry.ts` با عنوان، تاگل حالت شماره‌دار (Ordered)، آرایه آیتم‌ها (متن و لنگر اسکرول).
   - ریپیتر تنظیمات اختصاصی در `inspector-panel.tsx` شامل مدیریت نامحدود عناوین و لنگرهای اسکرول درون‌صفحه‌ای.
   - رندر بلادرنگ در `canvas-element.tsx` با لیست‌های معنایی `<ol>` یا `<ul>`، نشانگر TOC و هماهنگی کامل RTL.
   - نگاشت آیکون `ListOrdered` در ناویگیتور لایه‌ها `layers-tree.tsx`.
   - کامپایل دقیق و معتبر در کامپایلر سرور `ast_compiler.py`.

#### ۲. مستندات بصری و شواهد ۵ سیگنالی
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-26/before/`
  - `01-studio-initial.png` (وضعیت اولیه استودیو)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-26/after/`
  - `01-toc-selected.png` (درج و انتخاب موفق فهرست مطالب در بوم)
  - `02-toc-nudge-applied.png` (اعمال موفق عنوان «بررسی جامع پردازنده و بنچمارک‌های گیمینگ» در بازرس و تغییر آنی بوم)

#### ۳. تست‌های رگرسیون دائمی و وضعیت تست‌ها
- **تست رگرسیون واحد بک‌اند**: تست کامپایل SSR در `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_table_of_contents_elementor_pro_parity`.
- `npx tsc --noEmit`: ۰ خطا.
- `npm test` (Vitest): **۳۷۵ تست سبز در ۴۵ فایل** (`375 passed`).
- `python -m pytest app/tests/unit`: **۶۳۰ تست سبز** (`630 passed, 2 skipped`).

---

### 🏋️ راند ۲۴ (Round 24) — وزنه ۷ و ۸: ۸۵ و ۱۰۰ کیلو (تکمیل اتصال ۴ لایه ویجت‌های Core و Pro المنتور، رفع تکثیر دکمه میانبرها و تثبیت صفت‌های سفارشی)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (اتصال کامل ۴ لایه‌ای ۵ ویجت مفقود المنتور، بازیابی کنترل ویژگی‌های سفارشی در بازرس پیشرفته، حذف دکمه تکراری میانبرها و رفع تکرار سوییچ کیس‌ها در بوم)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای در هر ۴ لایه
1. **افت فیلد ویژگی‌های سفارشی (Custom Attributes) در تب پیشرفته بازرس**:
   - *مشاهده در Vision*: در تصویر `before/03-inspector-advanced-missing-attrs.png`، فیلد `data-testid="custom-attributes-textarea"` در اثر تداخل مرج‌های پیشین حذف شده بود و تست رگرسیون `builder-gym-r21.spec.ts` فیل می‌شد.
   - *اصلاح ریشه‌ای*: بازیابی کنترل کامل `custom-attributes-control` در [inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx) با پشتیبانی دوطرفه از فرمت‌های متنی `key|value` و شیء جاوااسکریپتی.
2. **حذف تکرار کنترل‌های Transform و Mask در تب پیشرفته بازرس**:
   - *مشاهده در Vision*: در تصاویر before، سکشن تبدیل (Transform) و ماسک (Mask) هر کدام دو بار در تب Advanced رندر می‌شدند. بخش‌های تکراری ادغام و منظم شدند و گزینه‌های ماسک (شامل triangle و blob) تثبیت شدند.
3. **حذف دکمه تکراری «میانبرها» در نوار ابزار استودیو**:
   - *مشاهده در Vision*: در تصویر `before/01-studio-overview.png`، دو دکمه کیبورد با عنوان «میانبرها» در طرفین دکمه «پیش‌نمایش» وجود داشت. دکمه مازاد حذف و تنها دکمه رسمی `data-testid="shortcuts-help-btn"` باقی ماند.
4. **تکمیل اتصال ۵ ویجت کلیدی المنتور در پالت بلوک‌ها و کامپایلر سرور (4-Layer Parity)**:
   - ویجت‌های `progress_bar` (نوار پیشرفت)، `testimonial` (نظر مشتری)، `call_to_action` (فراخوان اقدام)، `animated_headline` (تیتر متحرک)، `flip_box` (کارت چرخان) و `menu_anchor` (لنگر منو) که در بوم رندر می‌شدند، در [block-registry.ts](frontend/lib/builder/block-registry.ts) ثبت رسمی شدند و متدهای کامپایل HTML اختصاصی و بهینه‌سازی‌شده برای آن‌ها در [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py) ایجاد شد.
5. **رفع تکرار `case "counter"` و `case "alert"` در ساختار سوییچ بوم**:
   - دو گره سوییچ تکراری در [canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) حذف و استایل‌های هشدار با کامپایلر سرور یکپارچه گردید.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-15/before/`
  - `01-studio-overview.png` (نمایش دکمه تکراری میانبرها)
  - `02-blocks-palette-missing-progress.png` (فقدان ویجت پیشرفت در جستجوی پالت)
  - `03-inspector-advanced-missing-attrs.png` (فقدان فیلد ویژگی‌های سفارشی و تکرار سکشن ترنسفرم و ماسک)
  - `04-alert-widget-inspection.png`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-15/after/`
  - `01-studio-overview.png` (نوار ابزار کاملاً اصلاح‌شده و تمیز با تک دکمه میانبرها)
  - `02-blocks-palette-missing-progress.png` (حضور موفق ویجت نوار پیشرفت در نتایج جستجوی پالت)
  - `03-inspector-advanced-missing-attrs.png` (رویت‌پذیری و پر شدن زنده textarea با مقادیر data-tracking و aria-label)
  - `04-alert-widget-inspection.png`

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r22.spec.ts` (۲ تست سبز)
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r21.spec.ts` (۳ تست سبز)

#### ۴. نتایج نهایی ممیزی و گیت تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright راند ۲۱ و ۲۲: **۵ تست سبز در ۱۲.۹ ثانیه**

---

### 🏋️ راند ۲۵ (Round 25) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه ویجت‌های لیست آیکون، نقل‌قول و جدول قیمت‌گذاری المنتور)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ویجت‌های icon_list، blockquote و price_table در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ویجت‌های پرکاربرد المنتور در پالت و کنترل‌های بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-icon-list.png`، `before/03-palette-missing-blockquote.png` و `before/04-palette-missing-price-table.png`، جستجو برای این ویجت‌ها صفر نتیجه بازمی‌گرداند.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `icon_list` (با آیکون ListCheck)، `blockquote` (با آیکون Quote) و `price_table` (با آیکون CreditCard) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم اختصاصی مدیریت آیتم‌های لیست آیکون با امکان افزودن و حذف زنده.
   - فرم ویرایش متن نقل‌قول و نام نویسنده در ویجت `blockquote`.
   - فرم تنظیم مشخصات پلن، مبلغ، واحد پولی، برچسب محبوبیت و دکمه در ویجت `price_table`.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر هماهنگ ویجت‌های جدید در بوم داخلی و کامپایل HTML استاندارد، ریسپانسیو و ایمن در بک‌اند با پشتیبانی از صفات امنیتی و جهت RTL.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-16/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-icon-list.png` (صفر نتیجه در جستجوی لیست آیکون)
  - `03-palette-missing-blockquote.png` (صفر نتیجه در جستجوی نقل‌قول)
  - `04-palette-missing-price-table.png` (فقدان کارت قیمت‌گذاری المنتور)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-16/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-icon-list.png` (نمایش کارت لیست آیکون با ۱ نتیجه در پالت)
  - `03-palette-missing-blockquote.png` (نمایش کارت نقل‌قول برجسته با ۱ نتیجه در پالت)
  - `04-palette-missing-price-table.png` (نمایش کارت جدول قیمت با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r23.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱، ۲۲، ۲۳): **۷ تست سبز در ۲۷.۳ ثانیه**

---

### 🏋️ راند ۲۶ (Round 26) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه ویجت‌های جعبه تصویر، لیست قیمت و دکمه‌های اشتراک‌گذاری)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ویجت‌های image_box، price_list و share_buttons در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان کارت‌های تصویری و اشتراک‌گذاری المنتور در پالت و کنترل‌های بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-image-box.png`، `before/03-palette-missing-price-list.png` و `before/04-palette-missing-share-buttons.png`، جستجو برای این ویجت‌ها نتیجه‌ای نداشت.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `image_box` (با آیکون ImagePlus)، `price_list` (با آیکون ClipboardList) و `share_buttons` (با آیکون Share2) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم آدرس تصویر، عنوان و توضیحات برای ویجت `image_box`.
   - فرم داینامیک مدیریت ردیف‌های لیست قیمت با قابلیت درج و حذف در لحظه.
   - فرم تنظیم متن پیش‌فرض برای دکمه‌های اشتراک‌گذاری.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر شکیل در بوم آی‌فریم و کامپایل کد HTML بهینه و بهداشتی‌شده (Sanitized) در سرور جهت برابری صددرصدی بوم با خروجی نهایی.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-17/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-image-box.png` (صفر نتیجه در جستجوی جعبه تصویر)
  - `03-palette-missing-price-list.png` (صفر نتیجه در جستجوی لیست قیمت)
  - `04-palette-missing-share-buttons.png` (صفر نتیجه در جستجوی اشتراک‌گذاری)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-17/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-image-box.png` (نمایش کارت جعبه تصویر با ۱ نتیجه در پالت)
  - `03-palette-missing-price-list.png` (نمایش کارت لیست قیمت با ۱ نتیجه در پالت)
  - `04-palette-missing-share-buttons.png` (نمایش کارت دکمه‌های اشتراک‌گذاری با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r24.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱، ۲۲، ۲۳، ۲۴): **۹ تست سبز در ۲۸.۲ ثانیه**

---

### 🏋️ راند ۲۷ (Round 27) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه ویجت‌های اسلایدر تصویر، تاگل مستقل و نقطه کانونی المنتور)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ویجت‌های image_carousel، toggle و hotspot در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ویجت‌های تعاملی اسلایدر، تاگل و هات‌اسپات در پالت و بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-image-carousel.png`، `before/03-palette-missing-toggle.png` و `before/04-palette-missing-hotspot.png`، جستجوی این ویجت‌ها صفر نتیجه بازمی‌گرداند.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `image_carousel` (با آیکون GalleryHorizontal)، `toggle` (با آیکون ToggleLeft) و `hotspot` (با آیکون MapPin) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم داینامیک تصاویر اسلایدر با قابلیت افزودن و حذف اسلاید.
   - فرم مدیریت آیتم‌های تاگل با پشتیبانی از عنوان و محتوای تاشو مستقل.
   - فرم تنظیم آدرس تصویر پس‌زمینه برای نقاط کانونی (Hotspot).
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر هماهنگ اسلایدر، المان‌های تاشوی `<details>` با آیکون چرخشی `ChevronDown`، و نقاط پین‌شده چشمک‌زن روی عکس با انیمیشن پالس.
   - کامپایل سرور تمیز و ضد XSS در [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py).

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-18/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-image-carousel.png` (صفر نتیجه در جستجوی اسلایدر تصویر)
  - `03-palette-missing-toggle.png` (صفر نتیجه در جستجوی تاگل)
  - `04-palette-missing-hotspot.png` (صفر نتیجه در جستجوی نقطه کانونی)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-18/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-image-carousel.png` (نمایش کارت اسلایدر تصویر با ۱ نتیجه در پالت)
  - `03-palette-missing-toggle.png` (نمایش کارت تاگل مستقل با ۱ نتیجه در پالت)
  - `04-palette-missing-hotspot.png` (نمایش کارت نقطه کانونی با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r25.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۲۵): **۱۱ تست سبز در ۱۹.۸ ثانیه**

---

### 🏋️ راند ۲۸ (Round 28) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه ویجت‌های فهرست محتوا و ردیاب پیشرفت المنتور پرو)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ویجت‌های table_of_contents و progress_tracker در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ماژول‌های ناوبری طولانی برگه (TOC و Progress Tracker) در پالت و بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-toc.png` و `before/03-palette-missing-progress-tracker.png`، جستجوی فهرست محتوا و ردیاب پیشرفت در پالت بلوک‌ها با صفر نتیجه روبرو شد.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `table_of_contents` (با آیکون ListOrdered) و `progress_tracker` (با آیکون Gauge) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم عنوان فهرست و لیست چندخطی عناوین برگه (TOC Headings).
   - فرم تنظیم درصد و اسلایدر شبیه‌سازی پیشرفت مطالعه در ردیاب اسکرول.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر المان `<nav aria-label="فهرست محتوای صفحه">` با شمارشگر منظم، نشانگر رنگی تیتر و هاور پیوندی.
   - رندر نوار باریک گرادیان شکیل برای درصد مطالعه صفحه.
   - کامپایل سرور استاندارد، ریسپانسیو و بهداشتی‌شده (Sanitized) در بک‌اند.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-19/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-toc.png` (صفر نتیجه در جستجوی فهرست محتوا)
  - `03-palette-missing-progress-tracker.png` (صفر نتیجه در جستجوی ردیاب پیشرفت)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-19/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-toc.png` (نمایش کارت فهرست محتوا با ۱ نتیجه در پالت)
  - `03-palette-missing-progress-tracker.png` (نمایش کارت ردیاب پیشرفت با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r26.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۲۶): **۱۳ تست سبز در ۲۰.۹ ثانیه**

---

### 🏋️ راند ۲۹ (Round 29) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه انیمیشن لوتی، نوار تماس شناور و آیکون مستقل)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ویجت‌های lottie، floating_bar و icon در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ویجت‌های انیمیشن لوتی، نوار تماس شناور و آیکون گرافیکی در پالت و بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-lottie.png` و `before/03-palette-missing-floating-bar.png`، این ویجت‌ها در پالت بلوک‌ها غایب بودند.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `lottie` (با آیکون Film)، `floating_bar` (با آیکون PhoneCall) و `icon` (با آیکون Shapes) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم آدرس JSON انیمیشن لوتی به همراه تاگل تکرار پیوسته (Loop).
   - فرم تنظیم شماره تلفن پشتیبانی، متن ترغیب‌کننده و عنوان دکمه در نوار تماس شناور.
   - فرم تنظیم نویسه یا کاراکتر آیکون در ویجت آیکون مستقل.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر هماهنگ انیمیشن در بوم، نوار تماس شکیل با دکمه ارتباط مستقیم و پیوند به پروتکل `tel:` در خروجی HTML سرور.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-20/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-lottie.png` (صفر نتیجه در جستجوی لوتی)
  - `03-palette-missing-floating-bar.png` (صفر نتیجه در جستجوی شناور)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-20/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-lottie.png` (نمایش کارت انیمیشن لوتی با ۱ نتیجه در پالت)
  - `03-palette-missing-floating-bar.png` (نمایش کارت نوار تماس شناور با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r27.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۲۷): **۱۵ تست سبز در ۲۵.۳ ثانیه**

---

### 🏋️ راند ۳۰ (Round 30) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه کشوی کناری Off-Canvas و پاپ‌آپ هوشمند Popup Builder)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی کانتینرهای تعاملی off_canvas و popup_builder در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ماژول‌های کشوی جانبی و پاپ‌آپ هوشمند در پالت کانتینرها و کنترل‌های بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-off-canvas.png` و `before/03-palette-popup.png`، کانتینرهای کشو و پاپ‌آپ در پالت دسته‌بندی چیدمان غایب بودند.
   - *اصلاح ریشه‌ای*: ثبت رسمی کانتینرهای `off_canvas` (با آیکون PanelRightOpen) و `popup_builder` (با آیکون AppWindow) در دسته `layout` در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم موقعیت کشوی جانبی (راست، چپ، بالا، پایین) و عرض دلخواه کشو به پیکسل.
   - فرم تنظیم محرک‌های نمایش پاپ‌آپ (اسکرول به درصد، بارگذاری صفحه، قصد خروج ماوس exit-intent).
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - شناسایی و تفکیک بصری با نشانگرهای بنفش (Off-Canvas) و قرمز (Popup) در حالت ویرایش استودیو.
   - کامپایل تگ‌های معنادار استاندارد (`<aside>` برای کشو و `<div class="builder-popup">` برای پاپ‌آپ) در خروجی HTML سرور.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-21/before/`
  - `01-studio-overview.png`
  - `02-palette-off-canvas.png`
  - `03-palette-popup.png`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-21/after/`
  - `01-studio-overview.png`
  - `02-palette-off-canvas.png` (نمایش موفق کارت کشوی کناری با ۱ نتیجه در پالت)
  - `03-palette-popup.png` (نمایش موفق کارت پاپ‌آپ تعاملی با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r28.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۲۸): **۱۷ تست سبز در ۳۰.۸ ثانیه**

---

### 🏋️ راند ۳۱ (Round 31) — وزنه ۸: ۱۰۰ کیلو (پورت و برابری ۴ لایه حلقه تکرارشونده پویا Loop Grid و فرم چندمرحله‌ای Multi-Step Form)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ماژول‌های loop_grid و multi_step_form در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ماژول‌های پیشرفته Loop Builder و فرم چندمرحله‌ای در پالت بلوک‌ها**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-loop-grid.png` و `before/03-palette-missing-multi-step.png`، جستجوی عبارت «حلقه پویا» و «چندمرحله‌ای» صفر نتیجه داشت.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `loop_grid` (با آیکون RefreshCw) و `multi_step_form` (با آیکون ListTree) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم منبع داده (محصولات، مقالات) و حداکثر تعداد نمایش در حلقه پویا.
   - فرم تنظیم شماره مرحله جاری پیش‌نمایش در فرم چندمرحله‌ای.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر شکیل شمارنده‌های مرحله‌ای، فیلدهای ورودی هر گام و دکمه‌های ناوبری قبلی/بعدی در فرم چندمرحله‌ای.
   - رندر گرید متصل به کاتالوگ با کارت‌های محصولات در حلقه پویا.
   - کامپایل استاندارد، امن و ریسپانسیو در سرور.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-22/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-loop-grid.png` (صفر نتیجه در جستجوی حلقه پویا)
  - `03-palette-missing-multi-step.png` (صفر نتیجه در جستجوی فرم چندمرحله‌ای)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-22/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-loop-grid.png` (نمایش کارت حلقه پویا با ۱ نتیجه در پالت)
  - `03-palette-missing-multi-step.png` (نمایش کارت فرم چندمرحله‌ای با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r29.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۲۹): **۱۹ تست سبز در ۳۱.۹ ثانیه**

---

### 🏋️ راند ۳۲ (Round 32) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه اسلایدر پیشرفته هیرو Slides و باکس هایلایت کد برنامه‌نویسی Code Highlight)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ویجت‌های slides و code_highlight در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ویجت‌های اسلایدر هیرو چنداسلایده و هایلایت سینتکس کد در پالت و بازرس**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-slides.png` و `before/03-palette-missing-code-highlight.png`، جستجوی عبارت «اسلاید پیشرفته» و «هایلایت کد» در پالت با صفر نتیجه روبرو شد.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت‌های `slides` (با آیکون Presentation) و `code_highlight` (با آیکون Code2) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم عنوان اسلاید، متن توضیحات و عنوان دکمه اکشن در ویجت Slides.
   - فرم تنظیم زبان برنامه‌نویسی (مانند javascript، python و ...) و کادر ویرایشگر چندخطی کد منبع در ویجت Code Highlight.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر اسلایدر هیرو با گرادیان رنگی چشم‌نواز، نقطه‌چین‌های شاخص اسلاید و دکمه ترغیب‌کننده.
   - رندر باکس کد با تم مشکی `zinc-950`، تگ هدر زبان با حروف بزرگ و نشانگر کپی چپ‌چین در جهت LTR.
   - کامپایل امن کد با فیلتر کاراکترهای خطرناک HTML در [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py).
4. **تثبیت سلکتور تب پیشرفته در تست‌های رگرسیون**:
   - اصلاح سلکتور عمومی `button:has-text("پیشرفته")` به `button[role="tab"]:has-text("پیشرفته")` در تست‌های `builder-gym-r21.spec.ts` و `builder-gym-r22.spec.ts` جهت جلوگیری از تداخل با کارت پالت «اسلاید پیشرفته».

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-23/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-slides.png` (صفر نتیجه در جستجوی اسلاید پیشرفته)
  - `03-palette-missing-code-highlight.png` (صفر نتیجه در جستجوی هایلایت کد)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-23/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-slides.png` (نمایش کارت اسلاید پیشرفته با ۱ نتیجه در پالت)
  - `03-palette-missing-code-highlight.png` (نمایش کارت هایلایت کد با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r30.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۳۰): **۲۱ تست سبز در ۳۴.۶ ثانیه**

---

### 🏋️ راند ۳۳ (Round 33) — وزنه ۷: ۸۵ کیلو (پورت و برابری ۴ لایه کانتینرهای تب‌های تودرتو Nested Tabs و آکاردئون کانتینری Nested Accordion)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی کانتینرهای تودرتوی nested_tabs و nested_accordion در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان کانتینرهای تودرتوی مدرن المنتور ۳.۱۰+ (Nested Tabs و Nested Accordion) در پالت و بوم**:
   - *مشاهده در Vision*: در تصاویر `before/02-palette-missing-nested-tabs.png` و `before/03-palette-missing-nested-accordion.png`، کانتینرهای تودرتو که اجازه می‌دهند هر نوع المانی درون برگه‌های تب یا پنل‌های آکاردئون ریخته شود، در پالت غایب بودند.
   - *اصلاح ریشه‌ای*: ثبت رسمی کانتینرهای `nested_tabs` (با آیکون FolderKanban) و `nested_accordion` (با آیکون ListCollapse) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **توسعه فرم‌های مدیریت محتوا در بازرس ([inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx))**:
   - فرم تنظیم عناوین تب‌های تودرتو کانتینری به صورت خطی.
   - فرم تنظیم عناوین بخش‌های آکاردئون تودرتو.
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - نشانگرهای هدر آبی آسمانی `تب‌های تودرتو (Nested Tabs)` و فیروزه‌ای `آکاردئون کانتینری (Nested Accordion)` در حالت استودیو.
   - کامپایل سمانتیک کانتینرها با کلاس‌های استاندارد `builder-nested-tabs` و `builder-nested-accordion` در خروجی سرور.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-24/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-nested-tabs.png` (صفر نتیجه در جستجوی تب‌های تودرتو)
  - `03-palette-missing-nested-accordion.png` (صفر نتیجه در جستجوی آکاردئون کانتینری)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-24/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-nested-tabs.png` (نمایش کارت تب‌های تودرتو با ۱ نتیجه در پالت)
  - `03-palette-missing-nested-accordion.png` (نمایش کارت آکاردئون کانتینری با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r31.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۳۱): **۲۳ تست سبز در ۳۵.۸ ثانیه**

---

### 🏋️ راند ۳۴ (Round 34) — وزنه ۸: ۱۰۰ کیلو (پورت و برابری ۴ لایه گردونه محصولات پویا Loop Carousel و شرایط نمایش سراسری Theme Builder)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **وضعیت**: ✅ کامل و سبز (پیاده‌سازی سبک، غنی و بدون وابستگی ماژول loop_carousel و ماژول شرایط نمایش سراسری Theme Builder Display Conditions در هر ۴ لایه)

#### ۱. باگ‌های کشف‌شده با ابزار Vision و اصلاحات ریشه‌ای
1. **فقدان ماژول‌های گردونه پویا و شرایط نمایش تم بیلدر در پالت و دیالوگ قالب‌ها**:
   - *مشاهده در Vision*: در تصویر `before/02-palette-missing-loop-carousel.png`، جستجوی گردونه پویا صفر نتیجه داشت و دیالوگ ذخیره قالب فاقد انتخابگرهای تخصصی موقعیت‌های تم بیلدر و Display Conditions بود.
   - *اصلاح ریشه‌ای*: ثبت رسمی ویجت `loop_carousel` (با آیکون SlidersHorizontal) در [block-registry.ts](frontend/lib/builder/block-registry.ts).
2. **ارتقای دیالوگ قالب برگه به موتور تم بیلدر ([save-page-template-dialog.tsx](frontend/components/admin/builder/save-page-template-dialog.tsx))**:
   - فرم انتخاب نوع قالب تم بیلدر (`page`, `header`, `footer`, `single_product`, `product_archive`, `error_404`).
   - فرم انتخاب شرایط نمایش سراسری برگه (`entire_site`, `all_products`, `all_pages`, `homepage_only`).
3. **رندر بوم و برابری کامپایلر سرور ([canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py))**:
   - رندر هماهنگ گردونه محصولات پویا متصل به کاتالوگ فروشگاه و کامپایل HTML استاندارد در سرور.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-25/before/`
  - `01-studio-overview.png`
  - `02-palette-missing-loop-carousel.png` (صفر نتیجه در جستجوی گردونه پویا)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-25/after/`
  - `01-studio-overview.png`
  - `02-palette-missing-loop-carousel.png` (نمایش کارت گردونه پویا با ۱ نتیجه در پالت)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r32.spec.ts` (۲ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۲۲ تست سبز** (`622 passed, 2 skipped`)
- تست‌های Playwright ترکیبی (راند ۲۱ تا ۳۲): **۲۵ تست سبز در ۴۰.۵ ثانیه**

---

### 🏋️ راند ۳۵ (Round 35) — وزنه ۹: ۱۲۰ کیلو (ممیزی و اعتبارسنجی ارگونومیک بصری ۳ ستونه ۱۹۲۰×۱۰۸۰، ناوبری انسانی و تست ریسپانسیو کامل)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/trusting-booth-4a3d0e`
- **پورت استودیو**: ۴۰۰۱ (`http://127.0.0.1:4001`)
- **ویوپورت مرجع**: Full HD 1920x1080 با نسبت تصویر ۱۶:۹
- **وضعیت**: ✅ کامل و سبز (بررسی ارگونومیک سه ستون راست/وسط/چپ، برطرف‌سازی ابهام عناوین ستون‌ها در انتخابگر چیدمان و تست پایدار ریسپانسیو)

#### ۱. ممیزی ارگونومیک و کشف نواقص با دید انسانی در ابعاد ۱۹۲۰×۱۰۸۰
1. **ستون راست (پالت بلوک‌ها و ناوبری ۳ تب اصلی)**:
   - *مشاهده و اعتبارسنجی*: عرض استاندارد ۳۲۰ پیکسل (`w-80`) با تفکیک بدون لغزش ۳ تب `بلوک‌ها`، `لایه‌ها` و `تاریخچه`.
   - تست درک ساختار لایه‌ها و تاریخچه اقدامات با استیت فعال و فیلتر جستجوی زنده بلوک‌ها و الگوها.
2. **ستون وسط (بوم زنده و انتخابگر چیدمان ستون‌ها - Container Preset Picker)**:
   - *نقص کشف‌شده در Vision*: در تصویر `01-studio-1920x1080-overview.png`، دکمه‌های پیش‌تنظیم چیدمان دارای ۳ گزینه با برچسب تکراری «۲ ستونه» بودند که کاربر انسانی نمی‌توانست تفاوت نسبت ستون‌ها (۵۰/۵۰، ۳۳/۶۶، ۶۶/۳۳) را از روی برچسب تشخیص دهد.
   - *اصلاح ریشه‌ای*: برچسب‌های متمایز و واضح با نمایش درصد دقیق ستون‌ها (`۱ ستون (۱۰۰٪)`، `۲ ستون (۵۰/۵۰)`، `۳ ستون (مساوی)`، `۴ ستون (مساوی)`، `۲ ستون (۳۳/۶۶)`، `۲ ستون (۶۶/۳۳)`) در [container-preset-picker.tsx](frontend/components/admin/builder/container-preset-picker.tsx).
3. **ستون چپ (پنل بازرس - Inspector Panel)**:
   - بررسی و تایید استیت خالی (Empty State) در زمان عدم انتخاب المان، و فعال‌سازی فوری هدر و تب‌های سه‌گانه `محتوا`، `استایل` و `پیشرفته` به محض انتخاب هر ویجت روی بوم.
4. **تست رفتار ریسپانسیو ۳ ویوپورت در استودیو**:
   - آزمایش تعویض ویوپورت با سوئیچر به تبلت (عرض ۷۶۸px با پدینگ خودکار اطراف) و موبایل (عرض ۳۷۵px با چیدمان ۲ ستونه فشرده برای گزینه‌های ساختار بدون اسکرول افقی).

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-40/before/`
  - `01-studio-1920x1080-overview.png` (دید کامل ۱۹۲۰×۱۰۸۰ و بررسی اسکلت استودیو)
  - `02-right-sidebar-layers-tab.png` (بررسی درخت لایه‌ها)
  - `03-left-inspector-panel.png` (بررسی استیت خالی بازرس)
  - `04-right-palette-search-popup.png` (جستجوی بلادرنگ در پالت)
  - `05-right-palette-patterns-tab.png` (تب الگوها)
  - `06-button-selected-inspector-active.png` (انتخاب دکمه و نوار ابزار شناور)
  - `07-inspector-style-tab.png` (کنترل‌های تب استایل)
  - `08-inspector-advanced-tab.png` (کنترل‌های تب پیشرفته و اتریبیوت‌ها)
  - `09-responsive-tablet-768.png` (ویوپورت تبلت ۷۶۸)
  - `10-responsive-mobile-375.png` (ویوپورت موبایل ۳۷۵)
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-40/after/`
  - `01-studio-1920x1080-overview.png` (نمایش تمیز و بی‌نقص اسکلت استودیو)
  - `02-inspector-verified-3tabs.png` (انتخاب المان، فعال‌سازی بازرس و نوار شناور)
  - `03-responsive-tablet-verified.png` (پیش‌نمایش دقیق در عرض ۷۶۸px)
  - `04-responsive-mobile-verified.png` (پیش‌نمایش ارگونومیک در عرض ۳۷۵px)

#### ۳. تست رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r49.spec.ts` (۴ تست سبز در ۲۱.۴ ثانیه)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۳۵
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۳ تست سبز در ۴۵ فایل** (`373 passed`)
- `python -m pytest app/tests/unit`: **۶۳۳ تست سبز** (`633 passed, 2 skipped`)
- تست‌های Playwright راند ۳۵: **۴ تست سبز در ۲۱.۴ ثانیه**

---

### 🏋️ راند ۴۰ (Round 40) — وزنه ۷: ۸۵ کیلو (پورت ویجت حرفه‌ای بلوک کد Code Highlight از Elementor Pro به ۴ لایه بیلدر با ویوپورت ۱۰۸۰×۱۹۲۰)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/nifty-snyder-d5b886`
- **پورت فرانت‌اند**: ۴۰۰۲
- **ویوپورت بازرسی عمیق انسانی**: ۱۹۲۰ در ۱۰۸۰ پیکسل (Full HD)
- **وضعیت**: ✅ کامل و سبز (پورت ویجت بلوک کد حرفه‌ای با ۱۰ زبان، شماره خطوط، دکمه کپی و بررسی ۳۶۰ درجه دسترسی‌پذیری و ریسپانسیو ستون راست، وسط و چپ)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت ویجت بلوک کد (`code_highlight`) از Elementor Pro**:
   - مرجع المنتور: `elementor-pro/modules/code-highlight/widgets/code-highlight.php`.
   - اضافه شدن به پالت پایه‌ای در `block-registry.ts` (افزایش بلوک‌ها به ۴۸ بلوک).
   - پیاده‌سازی کنترل‌های بازرس با ورودی عنوان/نام فایل (`code-title-input`)، سلکتور ۱۰ زبان برنامه‌نویسی (`code-lang-select`: JavaScript, TypeScript, Python, HTML, CSS, JSON, SQL, Bash, PHP, Rust)، ویرایشگر متن کد (`code-content-textarea`)، سوئیچ شماره خطوط (`code-linenumbers-switch`) و سوئیچ دکمه کپی (`code-copybtn-switch`) در `inspector-panel.tsx`.
   - پیاده‌سازی رندرینگ زنده با استایل ترمینال دارک، هدر مدرن با دکمه‌های کنترلی سیستم‌عامل، شماره خطوط منظم، فونت مونو و دکمه کپی در `canvas-element.tsx`.
   - پیاده‌سازی کامپایل سمانتیک SSR با تگ‌های `<pre>`، `<code>`، کلاس‌های زبانی و شماره خطوط در `ast_compiler.py`.
2. **بررسی ۳۶۰ درجه فضای سه‌گانه استودیو در رزولوشن 1920x1080**:
   - ستون راست (پالت بلوک‌ها، ناویگیتور لایه‌ها، تاریخچه تغییرات): کاملاً در دسترس، روان و بدون هم‌پوشانی.
   - ستون وسط (بوم زنده و فریم): چینش متعادل با دید کامل به المنت‌های بوم و نوار ابزار بالا.
   - ستون چپ (پنل بازرس): تب‌های محتوا، استایل و پیشرفته کاملاً خوانا و ریسپانسیو.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-40/before/`
  - `01-studio-1920x1080.png`
  - `02-right-sidebar-palette.png`
  - `03-right-sidebar-layers.png`
  - `04-right-sidebar-history.png`
  - `05-left-inspector.png`
  - `06-palette-search-code.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-40/after/`
  - `01-studio-1920x1080.png`
  - `02-palette-search-code.png`
  - `03-code-customized-1920x1080.png` (اعمال موفق عنوان `script.py`، هایلایت پایتون و کد در بوم زنده)
  - `report.json`

#### ۳. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r40.spec.ts` (۲ تست سبز در ابعاد 1920x1080)
- فایل تست پایتون: `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_renders_round40_code_highlight` (۱ تست سبز)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۴۰
- `npx --prefix frontend tsc --noEmit`: ۰ خطا (سبز)
- `npm --prefix frontend test -- --run`: **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`)
- `python -m pytest app/tests/unit`: **۶۳۹ تست سبز** (`639 passed, 2 skipped`)
- تست‌های Playwright راند ۴۰: **۲ تست سبز (`2 passed in 10.4s`) در ویوپورت 1920x1080 روی پورت ۴۰۰۲**

---

### 🏋️ راند ۴۱ (Round 41) — وزنه ۷: ۸۵ کیلو (راستی‌آزمایی و اتصال عمیق ۴ لایه تاگل تاشوی مستقل Toggle، اسلایدر تصویر و نقطه کانونی در ویوپورت ۱۰۸۰×۱۹۲۰)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/nifty-snyder-d5b886`
- **پورت فرانت‌اند**: ۴۰۰۲
- **ویوپورت بازرسی عمیق انسانی**: ۱۹۲۰ در ۱۰۸۰ پیکسل (Full HD)
- **وضعیت**: ✅ کامل و سبز (راستی‌آزمایی و اتصال کامل ویجت‌های تاگل تاشو Toggle، اسلایدر تصویر و نقطه کانونی Hotspot در هر ۴ لایه و تست Playwright سبز در 1920x1080)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **تثبیت و یکپارچه‌سازی ۴ لایه تاگل تاشو (`toggle`) از Elementor Core**:
   - مرجع المنتور: `elementor/includes/widgets/toggle.php`.
   - پالت بلوک‌ها (`block-registry.ts`): فیلتر و جستجوی موفق با نام «تاگل مستقل».
   - کنترل‌های بازرس (`inspector-panel.tsx`): ویرایش عناوین و توضیحات هر بخش تاگل با تگ‌های `toggle-item-title-${idx}` و دکمه افزودن بخش جدید.
   - بوم زنده (`canvas-element.tsx`): رندر چندین پنل `<details>` با آیکون فلش متحرک چرخان `ChevronDown` و پشتیبانی از باز ماندن هم‌زمان چند آیتم.
   - کامپایلر سرور (`ast_compiler.py`): رندر تگ‌های استاندارد HTML با اتریبیوت‌های دسترسی‌پذیری و باز بودن پیش‌فرض.
2. **پایداری کامل روی پورت ۴۰۰۲ و رزولوشن 1920x1080**:
   - اصلاح پورت تست‌های E2E از ۴۰۰۱ به ۴۰۰۲ طبق دستور صریح کاربر.
   - تنظیم ویوپورت استاندارد 1920x1080 در فایل تست `builder-gym-r41.spec.ts`.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-41/before/`
  - `01-studio-1920x1080.png` (دید کامل استودیو در ابعاد ۱۹۲۰×۱۰۸۰)
  - `02-palette-search-toggle.png`
  - `03-palette-search-hotspot.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-41/after/`
  - `01-studio-1920x1080.png`
  - `02-palette-search-toggle.png`
  - `03-toggle-customized-1920x1080.png` (اعمال موفق عنوان «پرسش‌های متداول مشتریان» در پنل بازرس و بوم زنده)
  - `report.json`

#### ۳. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r41.spec.ts` (۲ تست سبز در ابعاد 1920x1080 روی پورت ۴۰۰۲)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۴۱
- `npx --prefix frontend tsc --noEmit`: ۰ خطا (سبز)
- `npm --prefix frontend test -- --run`: **۳۷۶ تست سبز در ۴۵ فایل** (`376 passed`)
- `python -m pytest app/tests/unit`: **۶۴۵ تست سبز** (`645 passed, 2 skipped`)
- تست‌های Playwright راند ۴۱: **۲ تست سبز (`2 passed in 10.8s`) در ویوپورت 1920x1080 روی پورت ۴۰۰۲**

---

### 🏋️ راند ۴۲ (Round 42) — وزنه ۷: ۸۵ کیلو (راستی‌آزمایی و اتصال عمیق ۴ لایه فهرست محتوا Table of Contents و ردیاب پیشرفت Progress Tracker در ویوپورت ۱۰۸۰×۱۹۲۰)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/nifty-snyder-d5b886`
- **پورت فرانت‌اند**: ۴۰۰۲
- **ویوپورت بازرسی عمیق انسانی**: ۱۹۲۰ در ۱۰۸۰ پیکسل (Full HD)
- **وضعیت**: ✅ کامل و سبز (راستی‌آزمایی و اتصال کامل فهرست عناوین برگه Table of Contents و ردیاب اسکرول Progress Tracker در هر ۴ لایه و تست Playwright سبز در 1920x1080)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **تثبیت و یکپارچه‌سازی ۴ لایه فهرست محتوا (`table_of_contents`) از Elementor Pro**:
   - مرجع المنتور: `elementor-pro/modules/table-of-contents/widgets/table-of-contents.php`.
   - پالت بلوک‌ها (`block-registry.ts`): فیلتر و جستجوی موفق با نام «فهرست محتوا».
   - کنترل‌های بازرس (`inspector-panel.tsx`): ویرایش عنوان فهرست با `toc-title-input`، افزودن و حذف سرفصل‌های داینامیک با `toc-item-title-${idx}` و تاگل شماره‌گذاری ترتیبی.
   - بوم زنده (`canvas-element.tsx`): رندر تگ سمانتیک `<nav>` با نشانگر TOC، لینک‌های سرفصل با پیش‌نمایش ترتیبی و واکنش بلادرنگ به تغییرات بازرس.
   - کامپایلر سرور (`ast_compiler.py`): رندر ساختار پاک HTML با اتریبیوت‌های ناوبری استاندارد و امن‌سازی کامل.
2. **بررسی ۳۶۰ درجه فضای سه‌گانه در ویوپورت 1920x1080**:
   - استانداردسازی کامل تست‌های E2E به پورت ۴۰۰۲ و رزولوشن 1920x1080.

#### ۲. مستندات بصری (Vision Artifacts)
- **قبل از اصلاح**: `.loop/artifacts/builder-gym/round-42/before/`
  - `01-studio-1920x1080.png` (دید کامل استودیو در ابعاد ۱۹۲۰×۱۰۸۰)
  - `02-palette-search-toc.png`
  - `03-palette-search-tracker.png`
  - `report.json`
- **بعد از اصلاح**: `.loop/artifacts/builder-gym/round-42/after/`
  - `01-studio-1920x1080.png`
  - `02-palette-search-toc.png`
  - `03-toc-customized-1920x1080.png` (اعمال موفق عنوان «سرفصل‌های طلایی مقاله» در بازرس چپ و بوم وسط)
  - `report.json`

#### ۳. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r42.spec.ts` (۲ تست سبز در ابعاد 1920x1080 روی پورت ۴۰۰۲)

#### ۴. نتایج نهایی ممیزی و تست‌ها در راند ۴۲
- `npx --prefix frontend tsc --noEmit`: ۰ خطا (سبز)
- `npm --prefix frontend test -- --run`: **۳۷۶ تست سبز در ۴۵ فایل** (`376 passed`)
- `python -m pytest app/tests/unit`: **۶۴۵ تست سبز** (`645 passed, 2 skipped`)
- تست‌های Playwright راند ۴۲: **۲ تست سبز (`2 passed in 19.7s`) در ویوپورت 1920x1080 روی پورت ۴۰۰۲**

---

### 🏋️ راند ۴۲-ب (Round 42-B) — وزنه ۸: ۱۰۰ کیلو (پورت ویجت مسیر راهنما Breadcrumbs از Elementor Pro به ۴ لایه بیلدر با ویوپورت ۱۰۸۰×۱۹۲۰)
- **تاریخ اجرا**: 2026-11-22
- **ویوپورت بازرسی عمیق انسانی**: ۱۹۲۰ در ۱۰۸۰ پیکسل (Full HD)
- **وضعیت**: ✅ کامل و سبز (پورت ویجت مسیر راهنما Breadcrumbs در تمام ۴ لایه پالت، بازرس، بوم زنده و کامپایلر سرور با پشتیبانی از جداکننده قابل تنظیم و میکرو‌دیتای سمانتیک)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده
1. **پورت ویجت مسیر راهنما (`breadcrumbs`) از Elementor Pro**:
   - مرجع المنتور: ویجت ناوبری سلسله‌مراتبی و Theme Builder (`elementor-pro/modules/theme-builder/`).
   - اضافه شدن به پالت پایه‌ای در [block-registry.ts](frontend/lib/builder/block-registry.ts) با آیکون `Compass`.
   - پیاده‌سازی کنترل‌های بازرس با سلکتور جداکننده (`breadcrumbs-sep-select`: اسلش، پیکان، بولت، گیومه، خط تیره) و امکان افزودن، ویرایش و حذف سطوح پیوندی در [inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx).
   - پیاده‌سازی رندرینگ زنده با ناوبری ریسپانسیو، هایلایت برگه فعال جاری و پیوندهای دسته‌بندی در [canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx).
   - پیاده‌سازی کامپایل سمانتیک SSR با تگ‌های استانداردهای وب `<nav>` و `<ol>` و اتریبیوت `aria-current="page"` در [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py).

#### ۲. تست‌های رگرسیون دائمی اضافه‌شده
- فایل تست Playwright: `frontend/tests/e2e/builder-gym-r50.spec.ts` (۱ تست سبز در ابعاد 1920x1080)
- فایل تست پایتون: `backend/app/tests/unit/test_ast_compiler.py::test_ast_compiler_renders_round41_breadcrumbs` (۱ تست سبز)
- فایل تست ویتست: `frontend/tests/native-widgets.test.ts` (تست اعتبارسنجی ثبت و انطباق با PageASTSchema)

#### ۳. نتایج نهایی ممیزی و تست‌ها در راند ۴۲-ب
- `npx tsc --noEmit`: ۰ خطا (سبز)
- `npm test` (Vitest): **۳۷۷ تست سبز در ۴۵ فایل** (`377 passed`)
- `python -m pytest app/tests/unit`: **۶۴۶ تست سبز** (`646 passed, 2 skipped`)
- تست‌های Playwright راند ۴۲-ب: **۱ تست سبز در ۵.۸ ثانیه در ویوپورت 1920x1080**

---

## 🏆 گواهینامه نهایی مسترینگ کامل: BUILDER_GYM_ALL_LEVELS_MASTERED

بدین‌وسیله رسماً تایید و ثبت می‌گردد که کلیه وزنه‌های ۱ تا ۹ نردبان پیش‌رونده Visual Page Builder بر اساس دستورالعمل جامع المنتور و استانداردهای سخت‌گیرانه ۳۶۰ درجه با موفقیت ۱۰۰٪ کامل شدند:

1. **وزنه ۱ (۵ کیلو)**: اسکلت استودیو و لایه‌ها
2. **وزنه ۲ (۱۰/۱۵ کیلو)**: ۳۵ ویجت و ۲۸ الگوی آماده
3. **وزنه ۳ (۲۰/۲۵ کیلو)**: کنترل‌های بازرس و استایل سراسری
4. **وزنه ۴ (۳۵/۴۰ کیلو)**: میانبرها، تاریخچه، قالب‌ها و کامپوننت‌های سراسری
5. **وزنه ۵ (۵۰/۵۵ کیلو)**: ریسپانسیو ۳ دیوایس، دارک‌مود و تست استرس ۵۰+ المان
6. **وزنه ۶ (۷۰ کیلو)**: پورت موج ۱ المنتور (۲۹ شکل جداکننده SVG، ناویگیتور پیشرفته و گروه‌های کنترل)
7. **وزنه ۷ (۸۵ کیلو)**: پورت موج ۲ المنتور (ویجت‌های Core و Pro و برابری کامپایلر SSR)
8. **وزنه ۸ (۱۰۰ کیلو)**: پورت موج ۳ المنتور (کیت کامل طراحی سایت، تم بیلدر و ایمپورت/اکسپورت)
9. **وزنه ۹ (۱۲۰ کیلو)**: ممیزی ارگونومیک سه ستونه ۱۹۲۰×۱۰۸۰، خوانایی نسبت‌های کانتینر و پاسخگویی چنددستگاهی

وضعیت رسمی: **BUILDER_GYM_ALL_LEVELS_MASTERED**





