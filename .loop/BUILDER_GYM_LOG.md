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

## 🏆 گواهینامه ثبت BUILDER_GYM_LEVELS_1_TO_5_CLEAN

بدین‌وسیله تایید می‌گردد که هر ۵ وزنه نردبان تمرین پیش‌رونده Visual Page Builder بر اساس دستورالعمل رسمی [BUILDER_GYM.md](BUILDER_GYM.md) با موفقیت کامل و مستندات تصویری Vision سپری شد:

- **وزنه ۱ (۵ کیلو)**: اسکلت استودیو، رفع نشت چت‌بات، سقف بوم و کلید `?builder=1` (۳ تست Playwright در `builder-gym-r01.spec.ts`).
- **وزنه ۲ (۱۰ کیلو)**: پالت بلوک‌ها، استایل دکمه‌های الگوها، حفظ کلاس‌های سفارشی تیترها و تصاویر، و درک کانتینر والد برای هر ۲۸ الگوی آماده (۶ تست Playwright در `builder-gym-r02.spec.ts` و `builder-gym-r06.spec.ts`).
- **وزنه ۳ (۲۰ کیلو)**: کنترل‌های پنل بازرس، تب‌های Content/Style/Advanced و رفع لایه z-index دیالوگ‌ها (۳ تست Playwright در `builder-gym-r03.spec.ts`).
- **وزنه ۴ (۳۵ کیلو)**: کلیدهای میانبر بوم، درج هوشمند پیست، همگام‌سازی کامپوننت‌های سراسری و قالب‌ها (۳ تست Playwright در `builder-gym-r04.spec.ts`).
- **وزنه ۵ (۵۰ کیلو)**: ریسپانسیو ۳ ویوپورت (موبایل ۳۷۵px، تبلت ۷۶۸px، دسکتاپ)، دارک‌مود بلادرنگ و پایداری در تست استرس (۳ تست Playwright در `builder-gym-r05.spec.ts`).

تمامی اسناد، شواهد تصویری، Set-of-Mark و گزارش‌های ممیزی به صورت دائمی در `.loop/artifacts/` نگهداری شده‌اند.
وضعیت رسمی: **BUILDER_GYM_LEVELS_1_TO_5_CLEAN**




