# کارنامه رسمی مأموریت بیل مکانیکی (.loop/EXCAVATOR_LOG.md)

> مأموریت حفاری عمیق و ریشه‌کنی باگ‌های واقعی Visual Page Builder با مرجع معماری Elementor
> تمرکز ۱۰۰٪ روی ریشه‌کنی دائمی خطاهای P0 و P1 تا دستیابی به صفر خطا روی کل ماتریس اشعه ایکس

---

## جدول پیشرفت دورها (Rounds Progress Matrix)

| دور (Round) | خطاهای قبل (Before) | خطاهای بعد (After) | P0 / P1 باقی‌مانده | الگوها (Patterns) | بلوک‌ها (Blocks) | کنترل‌های بازرس (Inspector) | ریشه مشترک اصلاح‌شده (Root Cause) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| **Round 01** | 10 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **معماری ۱، ۲، ۳ و ۴ المنتور**: لایه مستقل CanvasOverlayLayer در ریشه Iframe، پاکسازی کد HTML خام الگوها در pattern-converter، منوی راست‌کلیک Context Menu، ویرایش مستقیم نام در LayersTree و ویرایش زنده Inline Editing |
| **Round 02** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **تکمیل معماری #۴ المنتور**: اضافه شدن انتخابگر چیدمان ستون‌های آماده (ContainerPresetPicker با ۶ پریست ستونی)، کنترل‌های گروه‌بندی‌شده حرفه‌ای سایه کادر (Box Shadow)، و گسترش چک‌های سخت‌گیرانه در builder-xray |
| **Round 03** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **صیقل تعامل و درگ نویگیتور**: درگ‌انددراپ بومی ردیف‌های درختی در LayersTree (جابه‌جایی بین شاخه‌ها و کانتینرها)، کنترل‌های کامل کادر و حاشیه (Border style/width/color/radius) و اعتبارسنجی خودکار اشعه ایکس |
| **Round 04** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **کنترل‌های حرفه‌ای پس‌زمینه و تایپوگرافی**: پیاده‌سازی سوییچر ۴ حالته پس‌زمینه (تک‌رنگ، گرادیانت چندجهته با نگاشت دقیق CSS، تصویر با پوزیشن و سایز) + تایپوگرافی کامل و آزمون زنده در اشعه ایکس |
| **Round 05** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **سیستم جامع کلیدهای میانبر (Elementor Hotkeys Modal Parity)**: پیاده‌سازی مودال راهنمای میانبرها، اتصال کلیدهای Ctrl+D (تکثیر)، Ctrl+S (ذخیره پیش‌نویس)، کلید ؟ (راهنما) و آزمون رگرسیون تاریخچه و Undo |
| **Round 06** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **نمایش شرطی و واکنش‌گرایی پیش‌نمایش (Responsive Visibility Mode)**: مخفی‌سازی دقیق المان‌های فاقد مجوز نمایش دستگاهی (موبایل/تبلت/دسکتاپ) در حالت پیش‌نمایش و نشانگر زنده در حالت ویرایشگر با آزمون اشعه ایکس |
| **Round 07** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **عملیات پیشرفته کانتینر در منوی راست‌کلیک (Wrap / Unwrap Container Parity)**: افزودن اکشن‌های اتمیک گروه‌بندی در کانتینر جدید و خروج از کانتینر (Unwrap) به همراه تست خودکار اشعه ایکس |
| **Round 08** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **کادرهای انتخاب چندگانه و کلیپ‌بورد دائمی (Multi-Selection Overlay & Persistent Clipboard)**: ترسیم همزمان باکس‌های انتخاب چندتایی در پرتال مستقل Overlay و ذخیره‌سازی ابری/محلی کلیپ‌بورد در localStorage برای کپی/پیست بین برگه‌ها |
| **Round 09** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **پنل تاریخچه ویرایش‌ها و تایم‌لاین اقدامات (Elementor Revision History Parity)**: افزودن تب تاریخچه در سایدبار، متد jumpToHistoryStep در استور، پیمایش زنده در بازنگری‌ها و آزمون اشعه ایکس |
| **Round 10** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **همگام‌سازی استایل‌های سراسری و توکن‌های دو لایه (Elementor Global Styles & Design Tokens Live Sync)**: توسعه دیالوگ استایل‌های سراسری با توکن‌های textColor و backgroundColor، تزریق آنی به سند Iframe بوم و تایید ۱۰۰٪ آزمون‌های اشعه ایکس |
| **Round 11** | 0 | **0** | **0 / 0** | 28 / 28 ✅ | 34 / 34 ✅ | 0 خطای مرده ✅ | **بازتاب دقیق شناسه و کلاس‌های سفارشی CSS در بوم و کامپایلر (Custom CSS ID & Class Anchor Reflection)**: رفع نقص اتصال customCssId روی تگ‌های DOM بوم و کامپایلر بک‌اند جهت پیمایش و انکر لینک‌های صفحه |

---

## جزئیات راند ۱۱ (Round 11)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `customCssIdReflection`: تایید اتصال دقیق شناسه و کلاس‌های CSS روی المنت‌های بوم و کامپایلر
  - `globalStylesTwoLayerTokens`: سبز
  - `historyTimelinePanel`: سبز
  - `multiSelectionOverlay`: سبز
  - `persistentClipboard`: سبز
  - `wrapUnwrapContainer`: سبز
  - `responsiveVisibility`: سبز
  - `shortcutsModal`: سبز
  - `hotkeyUndoRedo`: سبز
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۱۱:
1. **اتصال و بازتاب زنده شناسه اختصاصی CSS (`customCssId`)**:
   - اصلاح `canvas-element.tsx` برای درج شناسه `id={element.styles?.customCssId || undefined}` در تگ ریشه المان
   - اصلاح کامپایلر سرور `ast_compiler.py` برای اختصاص دادن شناسه دلخواه کاربر به جای شناسه سیستمی جهت ساخت انکرهای ناوبری و اسکرول نرم درون‌صفحه‌ای
2. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون شماره ۱۲ در `builder-xray.mjs` جهت بازتاب بلافاصله شناسه اختصاصی و کلاس‌های Tailwind تنظیم‌شده در تب Advanced روی DOM بوم ثبت و ۱۰۰٪ پاس گردید.

---

## جزئیات راند ۱۰ (Round 10)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `globalStylesTwoLayerTokens`: تایید باز شدن دیالوگ، حضور دکمه ریست به تم سایت و تزریق زنده متغیرهای CSS به ریشه Iframe
  - `historyTimelinePanel`: سبز
  - `multiSelectionOverlay`: سبز
  - `persistentClipboard`: سبز
  - `wrapUnwrapContainer`: سبز
  - `responsiveVisibility`: سبز
  - `shortcutsModal`: سبز
  - `hotkeyUndoRedo`: سبز
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۱۰:
1. **همگام‌سازی کامل استایل‌های سراسری برگه (Global Styles Live Sync)**:
   - توسعه `GlobalStylesDialog` با فیلدهای رنگ متن سراسری (`textColor`) و رنگ پس‌زمینه پیش‌فرض برگه (`backgroundColor`) علاوه بر رنگ‌های برند و شعاع کادر
   - اتصال تزریق زنده متغیرهای لایه ۲ (`--foreground`, `--background`, `--primary`, `--secondary`, `--radius`, `--content-max-width`) به `doc.documentElement` داخل Iframe در `canvas-frame.tsx`
2. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون شماره ۱۱ در `builder-xray.mjs` جهت سنجش باز شدن دیالوگ استایل‌های سراسری، حضور دکمه بازنشانی به تم سایت و اعمال متغیرهای CSS اضافه شد و ۱۰۰٪ پاس گردید.

---

## جزئیات راند ۹ (Round 09)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `historyTimelinePanel`: تایید باز شدن تب تاریخچه در سایدبار استودیو، رویت گام‌های تایم‌لاین و عملکرد jumpToHistoryStep
  - `multiSelectionOverlay`: سبز
  - `persistentClipboard`: سبز
  - `wrapUnwrapContainer`: سبز
  - `responsiveVisibility`: سبز
  - `shortcutsModal`: سبز
  - `hotkeyUndoRedo`: سبز
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۹:
1. **پنل اختصاصی تاریخچه اقدامات و تایم‌لاین ویرایش‌ها (`HistoryPanel`)**:
   - اضافه شدن تب سوم «تاریخچه» به سایدبار استودیو در کنار «بلوک‌ها» و «لایه‌ها» بر اساس الگوی رسمی پنل History المنتور
   - نمایش تایم‌لاین پویای مراحل ویرایش انجام‌شده به همراه وضعیت فعلی، دکمه‌های Undo/Redo و اندیکاتور زنده
   - پیاده‌سازی متد `jumpToHistoryStep` در `builder-store.ts` برای پرش مستقیم با یک کلیک به هر یک از ویرایش‌های گذشته
2. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون شماره ۱۰ در `builder-xray.mjs` جهت سنجش باز شدن پنل تاریخچه و پرش به مراحل گذشته ثبت و ۱۰۰٪ پاس شد.

---

## جزئیات راند ۸ (Round 08)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `multiSelectionOverlay`: تایید رندر همزمان باکس‌های انتخاب چندگانه در لایه پرتال
  - `persistentClipboard`: تایید ماندگاری و بازیابی المان و استایل در localStorage برای پیست بین برگه‌ها
  - `wrapUnwrapContainer`: سبز
  - `responsiveVisibility`: سبز
  - `shortcutsModal`: سبز
  - `hotkeyUndoRedo`: سبز
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۸:
1. **ترسیم باکس‌های انتخاب چندگانه در پرتال Overlay (`multiRects`)**:
   - در زمان انتخاب چندتایی با کلیدهای Ctrl/Shift یا درگ، کادرهای هایلایت اختصاصی آسمانی (`overlay-multi-box`) برای تمام المان‌های منتخب به صورت خودکار اندازه گرفته و در پرتال مستقل ریشه Iframe ترسیم می‌شوند.
2. **کلیپ‌بورد دائمی بین‌برگه‌ای (Persistent Cross-Page Clipboard)**:
   - توابع `copyElement`، `pasteElement`، `copyStyles` و `pasteStyles` علاوه بر حافظه موقت استور، ساختار کپی‌شده را در `localStorage` همگام می‌کنند تا کپی و پیست بین برگه‌ها و سشن‌های مختلف بدون از دست رفتن اطلاعات میسر باشد.
3. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون شماره ۹ در `builder-xray.mjs` جهت بررسی حضور باکس‌های چندگانه انتخاب و ماندگاری اطلاعات کلیپ‌بورد در حافظه محلی اضافه شد و ۱۰۰٪ پاس گردید.

---

## جزئیات راند ۷ (Round 07)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `wrapUnwrapContainer`: تایید کارکرد گروه‌بندی در کانتینر جدید و خروج از کانتینر (Unwrap)
  - `responsiveVisibility`: سبز
  - `shortcutsModal`: سبز
  - `hotkeyUndoRedo`: سبز
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۷:
1. **اکشن‌های اتمیک Wrap و Unwrap در کانتینرها (الگوی المنتور)**:
   - متدهای `wrapInContainer` و `unwrapContainer` با پشتیبانی کامل از تاریخچه Undo/Redo به `builder-store.ts` اضافه شدند.
   - گزینه‌های «گروه‌بندی در کانتینر جدید» (`FolderPlus`) و «خروج از کانتینر» (`FolderMinus`) در منوی راست‌کلیک (`BuilderContextMenu`) پیاده و مستقر شدند.
2. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون شماره ۸ در `builder-xray.mjs` جهت بررسی صحت ساختار درختی پس از احاطه در کانتینر و بازگشت دقیق ساختار پس از Unwrap اضافه شد و ۱۰۰٪ پاس گردید.

---

## جزئیات راند ۶ (Round 06)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `responsiveVisibility`: تایید مخفی‌سازی کامل در حالت پیش‌نمایش و نشانگر صحیح نشان در حالت ویرایش
  - `shortcutsModal`: سبز
  - `hotkeyUndoRedo`: سبز
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۶:
1. **انطباق کامل نمایش شرطی دستگاهی (Responsive Visibility)**:
   - در حالت پیش‌نمایش (`previewMode = true`)، المان‌هایی که دارای شرط مخفی در بریک‌پوینت فعال (`visibleOnMobile === false` و غیره) هستند، به‌طور کامل از درخت رندر خروجی حذف می‌شوند تا پیش‌نمایش نهایی WYSIWYG صادقانه باشد.
   - در حالت ویرایش، المان همراه با نشانگر ملایم کهربایی «مخفی در موبایل/تبلت/دسکتاپ» قابل رویت و انتخاب می‌ماند تا طراح بتواند آن را تنظیم یا لغو کند.
2. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون اعتبارسنجی خودکار وضعیت نشانگر در حالت ویرایش و محوشدن المان در حالت پیش‌نمایش موبایل در `builder-xray.mjs`.

---

## جزئیات راند ۵ (Round 05)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `shortcutsModal`: تایید گشوده شدن با کلیک دکمه نوار ابزار و کلید ؟ و بستن با Escape
  - `hotkeyUndoRedo`: تایید بازیابی فوری المان پس از فشردن Delete با Ctrl+Z
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۵:
1. **مودال راهنمای کلیدهای میانبر (`KeyboardShortcutsDialog`)**:
   - دسته‌بندی ۳ سطحی کلیدهای میانبر بر اساس الگوی رسمی المنتور (اقدامات اصلی و تاریخچه، کلیپ‌بورد و ویرایش، ناوبری و تعامل مستقیم)
   - دکمه دسترسی سریع در نوار ابزار بالای استودیو و باز شدن سریع با فشردن کلید `?`
2. **اتصال و تثبیت کلیدهای تکثیر و ذخیره**:
   - الحاق کلید `Ctrl + D` برای تکثیر فوری المان فعال بدون نیاز به باز کردن منو
   - الحاق کلید `Ctrl + S` برای ذخیره سریع پیش‌نویس
3. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون اعتبارسنجی خودکار کلیدهای میانبر، باز شدن دیالوگ و بازیابی تاریخچه با Ctrl+Z در `builder-xray.mjs`

---

## جزئیات راند ۴ (Round 04)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده (تایید زنده گرادیانت، سایه، فونت‌سایز، پدینگ و گپ)
  - `layersTreeDnD`: سبز
  - `containerPresetPicker`: سبز
  - `contextMenu`: سبز
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۴:
1. **کنترل‌های جامع پس‌زمینه چندحالته (Background Types)**:
   - پشتیبانی از ۴ حالت تک‌رنگ (Color)، گرادیانت (Gradient)، تصویر (Image) و هیچ (None)
   - کنترل گرادیانت با انتخابگر رنگ مبدأ/مقصد، جهت‌های شش‌گانه با نگاشت استاندارد CSS (to right, to left, to bottom, to top, to top right, to top left)
   - کنترل تصویر پس‌زمینه با ورودی URL، موقعیت (Center, Top, Bottom, Left, Right) و اندازه (Cover, Contain, Auto)
2. **تایپوگرافی پیشرفته و کامل (Typography Controls)**:
   - اندازه فونت به پیکسل با اعمال آنی در DOM بوم
   - وزن فونت با درجات استاندارد (300 تا 900)
   - چینش متن چهارگانه (راست، وسط، چپ، تراز) و توکن‌های رنگی متن
3. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون اعتبارسنجی زنده پس‌زمینه گرادیانت و اندازه فونت تیتر در `builder-xray.mjs` با عبور ۱۰۰٪ آزمون‌ها

---

## جزئیات راند ۳ (Round 03)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده (آزمون موفق پدینگ، گپ، متن تیتر و سایه کادر)
  - `layersTreeDnD`: تایید رویت‌پذیری و خاصیت draggable روی تمام ردیف‌های درختی
  - `containerPresetPicker`: تایید کارکرد درج خودکار ستون‌های دو، سه و چهارگانه
  - `contextMenu`: تایید باز شدن با کلیک راست و کلیدهای عملیاتی
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های راند ۳:
1. **درگ‌انددراپ درختی در LayersTree (Navigator Drag & Drop)**:
   - افزودن رویدادهای `draggable`, `onDragStart`, `onDragOver` و `onDrop` به هر ردیف درختی در `layers-tree.tsx`
   - اتصال به متد اتمیک `moveElement` جهت جابه‌جایی سریع و بازچینی ساختار المان‌ها و کانتینرها
2. **کنترل‌های گروه‌بندی‌شده کادر و حاشیه (Border & Radius)**:
   - اضافه شدن انتخابگر استایل خط کادر (solid, dashed, dotted, double, none)، ضخامت عددی به پیکسل، انتخابگر رنگ کادر و توکن‌های استاندارد شعاع گردی
3. **گسترش ممیزی خودکار اشعه ایکس**:
   - آزمون دقیق درگ‌پذیری نویگیتور و کنترل سایه کادر در `builder-xray.mjs` با حفظ عبور ۱۰۰٪ آزمون‌ها

---

## جزئیات راند ۲ (Round 02)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `containerPresetPicker`: تایید کارکرد درج خودکار ستون‌های دو، سه و چهارگانه
  - `contextMenu`: تایید ۱۰۰٪ باز شدن و کلیدهای عملیاتی (Duplicate, Copy, Delete)
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### قابلیت‌های معماری #۴ تکمیل‌شده:
1. **انتخابگر چیدمان ستون‌های کانتینر (`ContainerPresetPicker`)**:
   - کامپوننت هوشمند برای کانتینرهای خالی جهت ساخت درجا و یک‌کلیکه ستون‌های آماده: ۱ ستون کامل، ۲ ستون مساوی، ۳ ستون، ۴ ستون و ترکیب‌های نامتقارن ۱/۳ + ۲/۳ و ۲/۳ + ۱/۳
2. **کنترل‌های حرفه‌ای سایه کادر (`Box Shadow Grouped Controls`)**:
   - الحاق پروپرتی `boxShadow` به `DeviceStyleSchema` و `types/builder.ts` و رندر زنده در `canvas-element.tsx`
   - اتصال فیلد و توکن‌های پریست سایه (xs, sm, md, lg, xl, none) در تب استایل پنل بازرس
3. **تثبیت و ارتقای ممیزی خودکار (`builder-xray.mjs`)**:
   - ارتقای چک‌های ماتریس برای اعتبارسنجی خودکار چیدمان‌های ستونی و عملکرد منوی راست‌کلیک کانتینرها
   - حفظ پایداری ۱۰۰٪ بدون کوچک‌ترین بازگشت خطا در هر ۲۸ الگو و ۳۴ بلوک پایه

---

## جزئیات راند ۱ (Round 01)

- **شاخه ایزوله**: `claude/reverent-jang-441af1`
- **تاریخ اجرا**: 2026-11-21
- **وضعیت نهایی اشعه ایکس (.loop/XRAY_MATRIX.json)**:
  - `totalFailures`: **0**
  - `p0Count`: **0**
  - `p1Count`: **0**
  - `patterns`: ۲۸ از ۲۸ سبز (`passed: true`)
  - `blocks`: ۳۴ از ۳۴ سبز (`passed: true`)
  - `deadControls`: ۰ کنترل مرده
  - `categoryChipsClipping`: سبز و بدون بریدگی
  - `dragAndDrop`: سبز
  - `wysiwygParity`: تطابق ۱۰۰٪ بوم و صفحه نهایی

### ریشه‌های مشترک حل‌شده:
1. **معماری #۱ (انتقال نوار ابزار و کادر به لایه مستقل CanvasOverlayLayer)**:
   - حذف کامل floating-toolbar از داخل DOM المنت‌های تو در تو
   - استقرار نوار ابزار شناور در پرتال مستقل `#builder-overlay-mount` در ریشه سند iframe با محاسبه زنده `getBoundingClientRect` و `ResizeObserver`
   - رفع دائمی قیچی شدن نوار ابزار توسط کانتینرهای دارای `overflow: hidden`
   - اسکرول خودکار نرم به سمت المان انتخاب‌شده (`scrollIntoView`)

2. **معماری #۲ (حذف نشت تگ‌های HTML خام از ۲۸ الگو)**:
   - اصلاح تابع `createTextWidget` در `pattern-converter.ts` جهت پالایش خودکار تگ‌های `<p class="...">`, `<span class="...">`, `<div>`
   - هدایت کلاس‌های سفارشی به استایل استاندارد AST (`customCssClass`)
   - بازگشت متن خالص به textarea بازرس و فعال‌سازی قابلیت Inline Editing مستقیم با دابل‌کلیک روی بوم

3. **معماری #۳ (اصلاح چیپ‌های دسته‌بندی و کنترل‌های بازرس)**:
   - اصلاح چیپ‌های دسته‌بندی با `flex-wrap gap-1.5` در `blocks-palette.tsx` بدون هیچ‌گونه بریدگی عناوینی نظیر «اعتماد و بازخورد»
   - اصلاح اتصال مستقیم فیلدهای بازرس به استور و رفع خطای عدم خوانش پروپرتی‌های فاصله‌گذاری کانتینر
   - راهنمای کانتینر خالی متصل به پالت و گزینش سریع بلوک

4. **معماری #۴ (ارتقای الماس‌های کلیدی از elementor-ref)**:
   - ساخت کامپوننت کامل منوی راست‌کلیک `BuilderContextMenu` با امکانات: تکثیر، کپی، کپی استایل، چسباندن المان/استایل، انتقال به بالا/پایین، ذخیره قالب، قفل و حذف
   - تغییر نام مستقیم المان‌ها با دابل‌کلیک در `LayersTree` (مشابه المنتور نویگیتور) و درگ‌انددراپ بین لایه‌ها
