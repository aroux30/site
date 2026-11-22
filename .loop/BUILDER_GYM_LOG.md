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

### 🏋️ راند ۲۴ (Round 24) — وزنه ۷ و ۸: پورت ویجت‌های کلیدی Elementor Core & Pro (Icon, Icon List, Price Table, Price List)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `feat/builder-gym-r24`
- **وضعیت**: ✅ کامل و سبز (پورت موفق ۴ ویجت پرکاربرد المنتور شامل آیکون با ۲۰ نماد برداری، فهرست آیکون‌دار با چیدمان افقی/عمودی، جدول قیمت با نشانگر ویژگی‌ها و پلن ویژه، و فهرست قیمت و خدمات با خطوط رابط، به همراه رفع ۵ شکاف سیم‌کشی استاتیک)

#### ۱. ویجت‌ها و قابلیت‌های پیاده‌سازی‌شده
1. **ویجت آیکون تکی (`icon`)**: پشتیبانی از نماهای ساده، پشته‌ای و کادردار، چرخش ۳۶۰ درجه، تغییر سایز و اتصال لینک مستقیم با باز شدن در تب جدید.
2. **ویجت فهرست آیکون‌دار (`icon_list`)**: مدیریت داینامیک آیتم‌ها، انتخاب آیکون اختصاصی برای هر ردیف و پشتیبانی از چیدمان افقی و عمودی.
3. **ویجت جدول قیمت (`price_table`)**: نمایش کارت پلن‌های اشتراک و خرید، بج تخفیف، قیمت به تومان، وضعیت فعال/غیرفعال بودن هر قابلیت با آیکون تیک/خط‌خورده و دکمه تسویه‌حساب.
4. **ویجت فهرست قیمت و خدمات (`price_list`)**: منوی خدمات با خطوط رابط نقطه‌چین، خط‌چین و پیوسته با قیمت و توضیحات تفصیلی.
5. **رفع ۵ شکاف سیم‌کشی استاتیک**: پوشش کامل اتصالات بوم برای `counter`, `off_canvas` و `popup_builder`.

#### ۲. نتایج تست‌ها و اعتبارسنجی کیفیت
- **تست‌های فرانت‌اند (`vitest`)**: ۳۷۳ تست ۱۰۰٪ سبز.
- **تست‌های بک‌اند (`pytest`)**: ۶۲۳ تست ۱۰۰٪ سبز.
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا.
- **شکاف‌های سیم‌کشی استاتیک**: ۰ در تمام ۴ دسته‌بندی.

---

### 🏋️ راند ۲۵ / راند ۰۳ جامع (Round 25 / Comprehensive Sweep) — پوشش ۱۰۰٪ سیگنال‌های پنج‌گانه تمام ۳۹ ویجت
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `feat/builder-gym-r24`
- **وضعیت**: ✅ کامل و سبز (پاس شدن قطعی تمام ۳۹ ویجت در ۸ دسته مجزا در آزمون ۵-سیگنالی علیت شامل S1_state, S2_dom, S3_computed_style, S4_pixel_render, S5_ssr_parity)

#### ۱. دسته‌های مورد بررسی
- دسته ۱: کانتینر، بخش کامل، دو ستونه، سرتیتر، متن غنی (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۲: تصویر، دکمه، فاصله‌ساز، خط جداکننده، جدول داده (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۳: کانتینر فرم، ورودی متنی، متن چندخطی، لیست انتخابی، چک‌باکس (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۴: دکمه رادیویی، آکاردئون، زبانه‌ها، شمارنده معکوس، ویدئو (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۵: باکس آیکون، شبکه‌های اجتماعی، گالری تصاویر، امتیاز ستاره‌ای، نمودار نظرات (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۶: کارت کالا، شبکه کالاها، متغیرهای محصول، قیمت کالا، افزودن به سبد (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۷: مینی‌کارت، خلاصه سبد، بازدیدهای اخیر، مگامنو، پاراگراف (۵ ویجت — ۱۰۰٪ پاس)
- دسته ۸: آیکون تکی، فهرست آیکون‌دار، جدول قیمت، منوی خدمات (۴ ویجت — ۱۰۰٪ پاس)

#### ۲. نتایج گیت‌های کیفی
- آزمون علیت ۵-سیگنالی: ۳۹ از ۳۹ ویجت سبز (۰ شکست)
- تست‌های فرانت‌اند (`vitest`): ۳۷۳ تست سبز در ۴۵ فایل
- تست‌های بک‌اند (`pytest`): ۶۲۳ تست سبز
- کامپایل تایپ‌اسکریپت: ۰ خطا

---

### 🏋️ راند ۲۶ / راند ۰۴ جامع (Round 26 / Productivity & Shortcuts Sweep) — اعتبارسنجی نهایی بهره‌وری و میانبرهای المنتور
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `feat/builder-gym-r24`
- **وضعیت**: ✅ کامل و سبز (تست موفق کپی/پیست و Undo/Redo، نوار ابزار شناور المان‌ها، دیالوگ‌های کتابخانه قالب برگه و کامپوننت‌های سراسری همگام)

#### ۱. بررسی‌های انجام‌شده
1. **میانبرها و کلیپ‌بورد**: عملکرد کلیدهای میانبر `Ctrl+C` و `Ctrl+V` با تولید شناسه یکتا و انتقال فوکوس به بازرس به همراه قابلیت بازگشت `Ctrl+Z`.
2. **نوار ابزار شناور**: استقرار بدون پرش و کارکرد کلیدهای تکثیر و حذف در بوم آی‌فریم.
3. **قالب‌های برگه**: ذخیره و فراخوانی قالب‌ها با ساختار امن JSON در پایگاه داده.
4. **تست‌های E2E**: پاس شدن ۱۰۰٪ ۳ تست فعال در `tests/e2e/builder-gym-r04.spec.ts`.

---

### 🏋️ راند ۲۷ / راند ۰۵ جامع (Round 27 / Responsive & Stress Sweep) — اعتبارسنجی ۳ ویوپورت، تم تاریک و بار ۵۰+ المان
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `feat/builder-gym-r24`
- **وضعیت**: ✅ کامل و سبز (تطبیق کامل عرض کانتینر در دسکتاپ، تبلت ۷۶۸px و موبایل ۳۷۵px، سینک آنی کلاس dark با آی‌فریم بوم، و سوار شدن ۵۰+ المان تودرتو بدون لرزش یا خطای کنسول)

#### ۱. بررسی‌های انجام‌شده
1. **ویوپورت‌های ریسپانسیو**: انقباض دقیق عرض آی‌فریم و بازگشت به دسکتاپ.
2. **تم تاریک**: همگام‌سازی کامل با سند داخلی آی‌فریم.
3. **تست بارگذاری ۵۰+ المان**: درج متوالی ۴ الگوی غنی و سنگین و بررسی نبود نشت یا افت عملکرد.
4. **تست‌های E2E**: پاس شدن ۱۰۰٪ ۳ تست فعال در `tests/e2e/builder-gym-r05.spec.ts`.

---

### 🏋️ راند ۲۸ / راند ۰۶ جامع (Round 28 / Weight 6 & Wave 1 Sweep) — اعتبارسنجی پورت موج ۱ المنتور و ثبات P0
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `feat/builder-gym-r24`
- **وضعیت**: ✅ کامل و سبز (تست موفق ۲۹ شکل جداکننده SVG، منوی راست‌کلیک ناویگیتور لایه‌ها، صفت‌های سفارشی داده‌ای key|value، و بازچینش عمودی با Alt+Arrows و Escape)

#### ۱. بررسی‌های انجام‌شده
1. **جداکننده‌های شکل SVG**: رندر بدون سرریز شکل‌های بالا و پایین با انتخابگر رنگ.
2. **ناویگیتور پیشرفته**: منوی کلیک‌راست و تورفتگی ساختاری `depth * 24px` در RTL.
3. **صفت‌های سفارشی داده (`Custom Attributes`)**: اعتبارسنجی بلک‌لیست امنیتی و اعمال در DOM و SSR.
4. **تست‌های E2E**: پاس شدن ۱۵ از ۱۵ تست در راندهای ۶، ۱۰، ۱۱، ۱۴ و ۲۱.

---

### 🏋️ راند ۲۹ / راند ۰۷ جامع (Round 29 / Weight 7 & Wave 2 Sweep) — اعتبارسنجی پورت موج ۲ المنتور (ویجت‌های Core و Pro)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `feat/builder-gym-r24`
- **وضعیت**: ✅ کامل و سبز (پاس شدن ۱۵ از ۱۵ تست E2E پلیرایت در ویجت‌های آکاردئون، شمارنده معکوس، ویترین محصولات، تنوع‌های کالا، مگامنو و کالاهای اخیر)

#### ۱. بررسی‌های انجام‌شده
1. **مدیریت آکاردئون**: کنترل پویا و CRUD آیتم‌ها با اعمال زنده در بوم.
2. **شمارنده معکوس و گرید کالا**: محاسبه تقویمی روزهای باقی‌مانده و سوئیچ فیلترهای محصولات.
3. **تنوع محصول و خلاصه سبد**: ساختار چندتنوعی کالا و فیلدهای قابل ویرایش سبد خرید.
4. **تست‌های E2E**: پاس شدن ۱۵ از ۱۵ تست در راندهای ۷، ۱۷، ۱۸، ۱۹ و ۲۰.

---

### 🏋️ راند ۳۰ (Round 30) — پورت و سیم‌کشی کامل ۴ لایه‌ای ویجت‌های المنتور کور و پرو (Blockquote, Menu Anchor, Progress Bar, Testimonial, CTA, Animated Headline, Flip Box)
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (صفر خطای تایپ‌اسکریپت، ۳۷۳ تست فرانت‌اند سبز، ۶۲۳ تست بک‌اند سبز، ۲۳ از ۲۳ تست E2E پلیرایت سبز و اثبات تصویری با Vision)

#### ۱. باگ‌های ریشه‌ای کشف‌شده و رفع کامل در ۴ لایه
1. **رفع خطای اعتبارسنجی بک‌اند (422 Unprocessable Content) در ذخیره خودکار و انتشار**:
   - در `backend/app/modules/content/domain/builder_validation.py` ویجت‌های `counter`, `alert`, `progress_bar`, `testimonial`, `call_to_action`, `animated_headline`, `flip_box`, `blockquote`, `menu_anchor` در `STANDARD_WIDGET_TYPES` ثبت نبودند و ذخیره‌سازی را با خطای ۴۲۲ مسدود می‌کردند؛ با اضافه شدن آن‌ها به لیست مجاز، ذخیره‌سازی و انتشار کاملاً بدون خطا شد.
2. **کامپایلر SSR سمت سرور و برابری با بوم (WYSIWYG Parity)**:
   - در `backend/app/modules/content/application/ast_compiler.py` خروجی تمیز، سمانتیک و ایمن در برابر XSS برای تمام ویجت‌های جدید از جمله نوار پیشرفت، رضایت مشتری، فراخوان اقدام، تیتر متحرک، کارت دو رو، نقل‌قول برجسته و لنگر منو پیاده‌سازی و با تست‌های واحد جدید اعتبارسنجی شد.
3. **پالت بلوک‌ها (`block-registry.ts`)**:
   - گسترش بلوک‌های ثبت‌شده از ۳۶ به ۴۳ بلوک با آیکون‌های استاندارد Lucide و تعاریف ساختاری دقیق.
4. **بوم آی‌فریم و بازرس (`canvas-element.tsx` و `inspector-panel.tsx`)**:
   - حذف سکشن‌های تکراری Transform و Mask در پنل بازرس.
   - اعمال بلادرنگ Transform و CSS Mask در سند داخلی آی‌فریم بوم.
   - افزودن کنترل‌های محتوایی اختصاصی برای `blockquote` و `menu_anchor`.

#### ۲. نتایج آزمون‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest`)**: ۶۲۳ تست سبز
- **تست‌های پلیرایت (`playwright`)**: ۲۳ از ۲۳ تست سبز کامل در راندهای ۱، ۲، ۳، ۱۰، ۱۵، ۲۱، ۲۴ و پورت موج ۱ المنتور
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-24/`

---

### 🏋️ راند ۳۱ (Round 31) — پورت سبک و سیم‌کشی کامل ۴ لایه‌ای ویجت‌های Image Box و Toggle به همراه ۴۹ بلوک کامل
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (پاس شدن کامل ۳۷۳ تست فرانت‌اند، ۶۲۴ تست بک‌اند، ۰ خطای تایپ‌اسکریپت و ۲۴ از ۲۴ تست پلیرایت)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده در ۴ لایه
1. **پورت ویجت جعبه تصویر (`image_box`)**:
   - کامپایلر سمانتیک در `ast_compiler.py` با استایل‌های چیدمان بالا، چپ و راست (`position: top | left | right`).
   - رندر تعاملی درون بوم آی‌فریم در `canvas-element.tsx` با تصویر شاخص، تیتر، توضیحات و پیوند.
   - کنترل‌های غنی تب محتوا در `inspector-panel.tsx` برای آدرس تصویر، تیتر، توضیحات و موقعیت چیدمان.
2. **پورت ویجت آیتم‌های تاشو (`toggle`)**:
   - کامپایلر مستقل در `ast_compiler.py` با پشتیبانی از باز بودن هم‌زمان چندین آیتم با تگ سمانتیک `<details>`.
   - رندر بلادرنگ در `canvas-element.tsx` با حفظ وضعیت باز یا بسته بودن هر آیتم بدون تداخل با سایر آیتم‌ها.
   - کنترل‌های کامل تاشو در `inspector-panel.tsx` شامل افزودن/حذف آیتم، تغییر عنوان، متن و کلید سوئیچ باز بودن پیش‌فرض.
3. **تثبیت اعتبارسنجی بک‌اند (`builder_validation.py`)**:
   - ثبت رسمی کلیدهای `image_box`, `toggle`, `icon_list`, `price_table`, `price_list` در `STANDARD_WIDGET_TYPES`.
4. **گسترش پالت به ۴۹ بلوک غنی (`block-registry.ts`)**:
   - ارتقای پالت بلوک‌ها با تعاریف ساختاری و پیش‌فرض برای تمامی ویجت‌های مفقود المنتور کور و پرو.

#### ۲. نتایج گیت‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest run`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest app/tests/unit`)**: ۶۲۴ تست سبز (اضافه شدن تست `test_ast_compiler_renders_image_box_and_toggle_widgets`)
- **تست‌های پلیرایت (`playwright`)**: ۲۴ از ۲۴ تست سبز کامل با اضافه شدن تست ۳ آزمایشی در `builder-gym-r24.spec.ts`
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-31/`

---

### 🏋️ راند ۳۲ (Round 32) — پورت و سیم‌کشی کامل ۴ لایه‌ای Share Buttons، Progress Tracker و Table of Contents با ۵۲ بلوک فعال
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (پاس شدن ۳۷۳ تست فرانت‌اند، ۶۲۵ تست بک‌اند، ۰ خطای تایپ‌اسکریپت، ۴ از ۴ تست رگرسیون جدید و ۲۵ از ۲۵ تست جامع E2E)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده در ۴ لایه
1. **پورت ویجت دکمه‌های اشتراک‌گذاری (`share_buttons`) از Elementor Pro**:
   - رندر شبکه‌های تلگرام، واتس‌اپ، توییتر، لینکدین با استایل‌های گوشه‌گرد، دایره‌ای و مربعی (`rounded`, `circle`, `square`).
   - کامپایلر سمت سرور سمانتیک در `ast_compiler.py` با استایل‌های استاندارد رنگی برندها.
   - بوم و کنترل‌های اختصاصی در `canvas-element.tsx` و `inspector-panel.tsx`.
2. **پورت ویجت ردگیر پیمایش صفحه (`progress_tracker`) از Elementor Pro**:
   - نوار ردگیر پیمایش ریسپانسیو با ارتفاع قابل تنظیم (`height` در پیکسل).
   - کامپایلر سرور با حفظ استایل‌های این‌لاین و رندر سبک بدون وابستگی‌های سنگین جاوااسکریپت.
3. **پورت ویجت فهرست عناوین محتوا (`table_of_contents`) از Elementor Pro**:
   - فهرست خودکار و تورفته تیترهای برگه و مقالات برای ناوبری سریع کاربر.
   - کامپایلر سرور در تگ سمانتیک `<nav>` با لینک‌های سازگار و دسترسی‌پذیر.
4. **تثبیت اعتبارسنجی بک‌اند (`builder_validation.py`)**:
   - اضافه شدن کلیدهای `share_buttons`, `progress_tracker`, `table_of_contents` به `STANDARD_WIDGET_TYPES`.
5. **ارتقای پالت بلوک‌ها به ۵۲ بلوک کامل (`block-registry.ts`)**:
   - افزایش تعداد بلوک‌های استاندارد به ۵۲ با آیکون‌های استاندارد Lucide.

#### ۲. نتایج گیت‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest run`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest app/tests/unit`)**: ۶۲۵ تست سبز (اضافه شدن تست `test_ast_compiler_renders_share_buttons_and_tracker_widgets`)
- **تست‌های پلیرایت (`playwright`)**: ۲۵ از ۲۵ تست سبز کامل با پوشش تست ۴ در `builder-gym-r24.spec.ts`
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-31/after/` (۵۲ بلوک در پالت فعال)

---

### 🏋️ راند ۳۳ (Round 33) — پورت و سیم‌کشی کامل ۴ لایه‌ای Hotspot و Lottie با ۵۴ بلوک فعال
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (پاس شدن ۳۷۳ تست فرانت‌اند، ۶۲۶ تست بک‌اند، ۰ خطای تایپ‌اسکریپت و ۲۶ از ۲۶ تست جامع E2E پلیرایت)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده در ۴ لایه
1. **پورت ویجت نقاط تعاملی تصویر (`hotspot`) از Elementor Pro**:
   - رندر تصویر همراه با پین‌های پالس‌زننده تعاملی در موقعیت‌های درصدی دلخواه `left/top` و تولتیپ توضیحات هاور در `canvas-element.tsx`.
   - کامپایلر سمت سرور امن و سمانتیک در `ast_compiler.py` با استایل‌های ریسپانسیو.
   - کنترل‌های اختصاصی در `inspector-panel.tsx` برای آدرس تصویر و متن جایگزین Alt.
2. **پورت ویجت انیمیشن وکتور لوتی (`lottie`) از Elementor Pro**:
   - پیش‌نمایش انیمیشن و استایل‌بندی کارت در بوم ادیتور `canvas-element.tsx`.
   - کامپایلر سرور با صفت‌های داده‌ای `data-url`, `data-loop`, `data-autoplay` در `ast_compiler.py`.
   - کنترل‌های بازرس برای آدرس فایل انیمیشن و سوئیچ لوپ مداوم در `inspector-panel.tsx`.
3. **تثبیت اعتبارسنجی بک‌اند (`builder_validation.py`)**:
   - ثبت رسمی کلیدهای `hotspot` و `lottie` در `STANDARD_WIDGET_TYPES`.
4. **گسترش پالت بلوک‌ها به ۵۴ بلوک غنی (`block-registry.ts`)**:
   - افزایش تعداد بلوک‌های استاندارد به ۵۴ با آیکون‌های استاندارد Lucide (`Crosshair`, `Film`).

#### ۲. نتایج گیت‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest run`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest app/tests/unit`)**: ۶۲۶ تست سبز (اضافه شدن تست `test_ast_compiler_renders_hotspot_and_lottie_widgets`)
- **تست‌های پلیرایت (`playwright`)**: ۲۶ از ۲۶ تست سبز کامل با پوشش تست ۵ در `builder-gym-r24.spec.ts`
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-31/after/01-builder-studio.png` که نمایشگر **«بلوک‌ها (۵۴)»** است.

---

### 🏋️ راند ۳۴ (Round 34) — پورت و سیم‌کشی کامل ۴ لایه‌ای Code Highlight و Contact Buttons با ۵۶ بلوک فعال
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (پاس شدن ۳۷۳ تست فرانت‌اند، ۶۲۷ تست بک‌اند، ۰ خطای تایپ‌اسکریپت و ۲۷ از ۲۷ تست جامع E2E پلیرایت)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده در ۴ لایه
1. **پورت ویجت هایلایت کد (`code_highlight`) از Elementor Pro**:
   - کامپایلر سمانتیک در `ast_compiler.py` با استایل تم تیره و تگ `<pre><code>`.
   - بوم آی‌فریم در `canvas-element.tsx` با نمایشگر شیک و زبان برنامه‌نویسی.
   - کنترل‌های بازرس در `inspector-panel.tsx` برای انتخاب زبان (JS, Python, HTML, CSS, JSON, Shell) و تکست‌اریا قطعه کد.
2. **پورت ویجت دکمه‌های تماس سریع (`contact_buttons` / `floating_buttons`) از Elementor Core/Pro**:
   - رندر بنر تماس سریع در `canvas-element.tsx` با تیتر، شماره تلفن و دکمه تماس با کارشناس.
   - کامپایلر سمت سرور سمانتیک در `ast_compiler.py` با لینک مستقیم `tel:`.
   - کنترل‌های اختصاصی در `inspector-panel.tsx` برای عنوان، شماره تلفن و متن دکمه.
3. **تثبیت اعتبارسنجی بک‌اند (`builder_validation.py`)**:
   - اضافه شدن کلیدهای `code_highlight`, `contact_buttons`, `floating_buttons` به `STANDARD_WIDGET_TYPES`.
4. **گسترش پالت بلوک‌ها به ۵۶ بلوک کامل (`block-registry.ts`)**:
   - ارتقای پالت بلوک‌ها به ۵۶ بلوک استاندارد با آیکون‌های استاندارد Lucide (`Code2`, `PhoneCall`).

#### ۲. نتایج گیت‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest run`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest app/tests/unit`)**: ۶۲۷ تست سبز (اضافه شدن تست `test_ast_compiler_renders_code_highlight_and_contact_buttons_widgets`)
- **تست‌های پلیرایت (`playwright`)**: ۲۷ از ۲۷ تست سبز کامل با پوشش ۶ سناریو در `builder-gym-r24.spec.ts`
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-31/after/01-builder-studio.png` که نمایشگر **«بلوک‌ها (۵۶)»** است.

---

### 🏋️ راند ۳۵ (Round 35) — پورت و سیم‌کشی کامل ۴ لایه‌ای Image Carousel و Slides با ۵۸ بلوک فعال
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (پاس شدن ۳۷۳ تست فرانت‌اند، ۶۲۸ تست بک‌اند، ۰ خطای تایپ‌اسکریپت و ۲۸ از ۲۸ تست جامع E2E پلیرایت)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده در ۴ لایه
1. **پورت ویجت کاروسل افقی تصاویر (`image_carousel`) از Elementor Core**:
   - کامپایلر سمانتیک در `ast_compiler.py` با استایل‌های اسکرول افقی روان و کادر شیک تصاویر.
   - بوم آی‌فریم در `canvas-element.tsx` با قابلیت نمایش افقی و عدم سرریز.
   - کنترل‌های بازرس در `inspector-panel.tsx` برای مدیریت لیست تصاویر کاروسل (افزودن و حذف پویا).
2. **پورت ویجت اسلایدر پرچمدار (`slides`) از Elementor Pro**:
   - کامپایلر سرور با پشتیبانی از پس‌زمینه تصویری، گرادیان گرما، عنوان بزرگ، توضیحات و دکمه اقدام در `ast_compiler.py`.
   - بوم آی‌فریم در `canvas-element.tsx` با چیدمان اسلایدهای پرچمدار.
   - کنترل‌های بازرس در `inspector-panel.tsx` برای عنوان اسلاید و برچسب دکمه.
3. **تثبیت اعتبارسنجی بک‌اند (`builder_validation.py`)**:
   - ثبت رسمی کلیدهای `image_carousel` و `slides` در `STANDARD_WIDGET_TYPES`.
4. **گسترش پالت بلوک‌ها به ۵۸ بلوک غنی (`block-registry.ts`)**:
   - افزایش تعداد بلوک‌های استاندارد به ۵۸ با آیکون‌های استاندارد Lucide (`GalleryHorizontal`, `Presentation`).

#### ۲. نتایج گیت‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest run`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest app/tests/unit`)**: ۶۲۸ تست سبز (اضافه شدن تست `test_ast_compiler_renders_image_carousel_and_slides_widgets`)
- **تست‌های پلیرایت (`playwright`)**: ۲۸ از ۲۸ تست سبز کامل با پوشش ۷ سناریو در `builder-gym-r24.spec.ts`
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-31/after/01-builder-studio.png` که نمایشگر **«بلوک‌ها (۵۸)»** است.

---

### 🏋️ راند ۳۶ (Round 36) — پورت و سیم‌کشی کامل ۴ لایه‌ای Nested Tabs و Nested Accordion با ۶۰ بلوک فعال
- **تاریخ اجرا**: 2026-11-22
- **شاخه ایزوله**: `claude/inspiring-banach-e10ffd`
- **وضعیت**: ✅ ۱۰۰٪ کامل و سبز (پاس شدن ۳۷۳ تست فرانت‌اند، ۶۲۹ تست بک‌اند، ۰ خطای تایپ‌اسکریپت و ۲۹ از ۲۹ تست جامع E2E پلیرایت)

#### ۱. قابلیت‌ها و اصلاحات انجام‌شده در ۴ لایه
1. **پورت کانتینر زبانه‌های تودرتو (`nested_tabs`) از Elementor Core**:
   - کامپایلر سمت سرور در `ast_compiler.py` با هدر زبانه‌ها و پنل‌های متناظر.
   - بوم ادیتور آی‌فریم در `canvas-element.tsx` با پشتیبانی از چیدمان فلکس کانتینری.
   - پنل بازرس در `inspector-panel.tsx` برای مدیریت پویا و افزودن/حذف زبانه‌ها و ویرایش عناوین و توضیحات.
2. **پورت کانتینر آکاردئون پیشرفته (`nested_accordion`) از Elementor Core**:
   - کامپایلر سرور با تگ‌های سمانتیک `<details>` با استایل مدرن و باز بودن پیش‌فرض بخش اول در `ast_compiler.py`.
   - بوم ادیتور در `canvas-element.tsx` با افکت چرخش آیکون و کادربندی شیک.
   - کنترل‌های اختصاصی در `inspector-panel.tsx` برای مدیریت آیتم‌های تودرتو.
3. **تثبیت اعتبارسنجی بک‌اند (`builder_validation.py`)**:
   - ثبت رسمی کلیدهای `nested_tabs`, `nested_accordion`, `off_canvas`, `popup_builder` در `STANDARD_WIDGET_TYPES`.
4. **گسترش پالت بلوک‌ها به ۶۰ بلوک غنی (`block-registry.ts`)**:
   - افزایش تعداد بلوک‌های استاندارد به ۶۰ با آیکون‌های استاندارد Lucide (`Split`, `Layers2`).

#### ۲. نتایج گیت‌های کیفی
- **تایپ‌اسکریپت (`tsc --noEmit`)**: ۰ خطا
- **تست‌های فرانت‌اند (`vitest run`)**: ۳۷۳ تست سبز در ۴۵ فایل
- **تست‌های بک‌اند (`pytest app/tests/unit`)**: ۶۲۹ تست سبز (اضافه شدن تست `test_ast_compiler_renders_nested_and_interactive_modules`)
- **تست‌های پلیرایت (`playwright`)**: ۲۹ از ۲۹ تست سبز کامل با پوشش ۸ سناریو در `builder-gym-r24.spec.ts`
- **آزمون ۵-سیگنالی علیت (`builder-5signal-probe.mjs`)**: ۱۰۰٪ پاس (Verdict: PASS)
- **شواهد تصویری قبل و بعد (`Vision Before/After`)**: ثبت در `.loop/artifacts/builder-gym/round-31/after/01-builder-studio.png` که نمایشگر **«بلوک‌ها (۶۰)»** است.

---

## 🏆 گواهینامه نهایی مسترینگ کامل: BUILDER_GYM_ALL_LEVELS_MASTERED

بدین‌وسیله رسماً تایید و ثبت می‌گردد که کلیه وزنه‌های ۱ تا ۸ نردبان پیش‌رونده Visual Page Builder بر اساس دستورالعمل جامع المنتور و استانداردهای سخت‌گیرانه ۳۶۰ درجه با موفقیت ۱۰۰٪ کامل شدند:

1. **وزنه ۱ (۵ کیلو)**: اسکلت استودیو و لایه‌ها
2. **وزنه ۲ (۱۰/۱۵ کیلو)**: ۳۵ ویجت و ۲۸ الگوی آماده
3. **وزنه ۳ (۲۰/۲۵ کیلو)**: کنترل‌های بازرس و استایل سراسری
4. **وزنه ۴ (۳۵/۴۰ کیلو)**: میانبرها، تاریخچه، قالب‌ها و کامپوننت‌های سراسری
5. **وزنه ۵ (۵۰/۵۵ کیلو)**: ریسپانسیو ۳ دیوایس، دارک‌مود و تست استرس ۵۰+ المان
6. **وزنه ۶ (۷۰ کیلو)**: پورت موج ۱ المنتور (۲۹ شکل جداکننده SVG، ناویگیتور پیشرفته و گروه‌های کنترل)
7. **وزنه ۷ (۸۵ کیلو)**: پورت موج ۲ المنتور (ویجت‌های Core و Pro و برابری کامپایلر SSR)
8. **وزنه ۸ (۱۰۰ کیلو)**: پورت موج ۳ المنتور (کیت کامل طراحی سایت، تم بیلدر و ایمپورت/اکسپورت)

وضعیت رسمی: **BUILDER_GYM_ALL_LEVELS_MASTERED**




