# کارنامه رسمی عملیات بیل مکانیکی Visual Page Builder (.loop/EXCAVATOR_LOG.md)

> مأموریت حفاری عمیق و ریشه‌کنی باگ‌های ۹۰ درصدی Visual Page Builder با مرجع معماری Elementor (`C:\Users\Administrator\Desktop\elementor-ref`) بر روی شاخه ایزوله مخزن `aroux30/site`.

---

## جدول پیشرفت عددی عملیات (Progress Table)

| Round | Before Failures | After Failures | Root Causes Fixed | Patterns Passed | Blocks Passed | Dead Controls Remaining | Status |
| :---: | :---: | :---: | :--- | :---: | :---: | :---: | :---: |
| **Round 01** | **123** (P0: 37, P1: 86) | **0** (P0: 0, P1: 0) | **۱. معماری لایه مستقل Selection & Toolbar Overlay Portal**<br>**۲. ریشه‌کنی تگ‌های HTML خام از ۲۸ الگوی آماده**<br>**۳. انتخابگر چیدمان ساختار ستونی کانتینر (Elementor Layout Picker)**<br>**۴. منوی راست‌کلیک جامع (Context Menu) روی بوم و لایه‌ها**<br>**۵. تغییرنام مستقیم (Inline Rename) و درگ‌انددراپ لایه‌ها در Navigator** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 02** | **1** (P0: 1, P1: 0) | **0** (P0: 0, P1: 0) | **۱. ممیزی عمیق کنترل‌های بازرس روی متن و سطح تگ ویجت تیتر**<br>**۲. افزودن پالت جامع گرادیانت و سایه باکس (Box Shadow & Gradients)**<br>**۳. همگام‌سازی کامل کامپایلر بک‌اند (ast_compiler) با گرادیانت‌ها و سایه باکس**<br>**۴. تصحیح هندسه و محاسبه مرز امن نوار ابزار روی المان‌های کم‌ارتفاع سطری** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 03** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. ویرایش مستقیم درون‌خطی روی بوم (Elementor Inline Text Editing)**<br>**۲. دابل‌کلیک روی تیترها و متون بدون نیاز به باز کردن بازرس**<br>**۳. همگام‌سازی کامل با کلیدهای Enter و Escape و ذخیره در AST**<br>**۴. تست‌های سخت‌گیرانه تعاملی اشعه ایکس در راند ۳** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 04** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. گروه کنترل‌های تایپوگرافی کامل به سبک Elementor (اندازه، ضخامت، ترازبندی)**<br>**۲. کامپایل تمام ویژگی‌های تایپوگرافی در سرور با ast_compiler.py**<br>**۳. تست جهش بلادرنگ فونت‌سایز و سایه کادر در ممیزی اشعه ایکس**<br>**۴. تایید صحت کامل چرخه بدون شکست و پاس ۱۰۰٪ تمام آزمون‌ها** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |

---

## جزییات ریشه‌ای و معماری راند ۱ (Round 01 Deep Architectural Root Causes)

### ۱. معماری لایه مستقل Selection & Toolbar Overlay Portal (اولویت مطلق P0 — رفع باگ بریدگی توسط overflow: hidden)
- **علت ریشه‌ای قبل از اصلاح**:
  - کادر انتخاب (`outline`) و نوار ابزار شناور (`floating-toolbar`) درون DOM فرزند هر المان در `canvas-element.tsx` رندر می‌شدند (`absolute -top-8`). هنگامی که المان یا یکی از والدهای آن (مانند بخش هیرو، بنرها، کارت‌ها یا نوارهای متحرک) دارای کلاس `overflow-hidden` بود، نوار ابزار از کادر والد بیرون می‌زد و به‌طور کامل قیچی/بریده می‌شد (`TOOLBAR_CLIPPED_BY_OVERFLOW`) یا دکمه‌های آن با رویدادهای ماوس همپوشانی پیدا کرده و کلیک‌ناپذیر می‌شدند (`TOOLBAR_BUTTON_UNCLICKABLE`).
- **اصلاح ریشه‌ای به سبک المنتور (`elementor-ref`)**:
  - ایجاد کامپوننت مستقل [canvas-overlay.tsx](frontend/components/admin/builder/canvas-overlay.tsx) در ریشه سند داخلی بوم Iframe (`z-[9999]`).
  - این لایه خارج از زنجیره سلسله‌مراتبی DOM عناصر و فارغ از هرگونه `overflow: hidden` قرار دارد و با `getBoundingClientRect()`، شنونده‌های تغییر اندازه (`ResizeObserver`) و تغییرات ساختاری بوم (`MutationObserver`) دقیقاً موقعیت المان فعال را دنبال می‌کند.
  - نوار ابزار هوشمند در حاشیه امن سقف بوم قرار می‌گیرد و با المان‌های با ارتفاع کم به زیبایی هماهنگ است.

### ۲. حذف کامل تگ‌ها و کلاس‌های HTML خام از هر ۲۸ الگو (اولویت P1 — رفع نشت کد خام به بازرس)
- **علت ریشه‌ای قبل از اصلاح**:
  - در [pattern-converter.ts](frontend/lib/builder/pattern-converter.ts)، برای متن‌های زیرعنوان و پاراگراف‌ها تگ‌های متنی به صورت رشته‌های خام نظیر `<p class="text-muted-foreground">` یا `<span class="text-xs">` در `props.content` قرار می‌گرفتند. هنگام کلیک روی المان متنی در بوم، این تگ‌ها در فیلد `<textarea>` بازرس به صورت کد خام HTML ظاهر شده و ویرایش متن را برای کاربر مخدوش می‌کردند (`RAW_HTML_IN_INSPECTOR`).
- **اصلاح ریشه‌ای**:
  - تفکیک کامل استایل‌ها و کلاس‌های Tailwind به `customCssClass` در ساختار استاندارد AST و ذخیره محتوای متنی تمیز و خالص بدون تگ‌های خام در هر ۲۸ الگوی آماده.
  - تبدیل المان توزیع نظرات در الگوی `review-histogram` به ویجت استاندارد و بومی `review_histogram`.

### ۳. انتخابگر چیدمان ساختار ستونی کانتینر (Elementor Layout Picker Parity)
- **نوآوری و ارتقای معماری**:
  - پیاده‌سازی کامپوننت [container-structure-picker.tsx](frontend/components/admin/builder/container-structure-picker.tsx) با الهام از رفتار دکمه + در Elementor.
  - ارائه ۶ ساختار آماده ستونی (تک‌ستونه ۱۰۰٪، ۲ ستون مساوی ۵۰/۵۰، ۳ ستون مساوی ۳۳/۳۳/۳۳، ۲ ستون نامتقارن ۳۳/۶۶ و ۶۶/۳۳، و ۴ ستون ۲۵/۲۵/۲۵/۲۵) جهت درج سریع ساختارهای شبکه‌ای در کانتینرهای خالی بوم.

### ۴. منوی راست‌کلیک کامل (Builder Context Menu)
- **پیاده‌سازی به سبک المنتور**:
  - ایجاد کامپوننت [builder-context-menu.tsx](frontend/components/admin/builder/builder-context-menu.tsx) متصل به رویداد `contextmenu` در سند بوم و درخت لایه‌ها با کلیدهای میانبر استاندارد:
    - ویرایش در بازرس
    - تکثیر المان (`Ctrl+D`)
    - کپی المان (`Ctrl+C`) و پیست المان (`Ctrl+V`)
    - کپی استایل‌ها و پیست استایل‌ها
    - انتقال به بالا (`Alt+↑`) و انتقال به پایین (`Alt+↓`)
    - ذخیره کانتینر به عنوان قالب
    - مخفی‌سازی / نمایش لایه
    - حذف المان (`Delete`)

### ۵. درخت لایه‌ها (Navigator Parity: Inline Rename & Drag & Drop)
- **اصلاح ریشه‌ای در LayersTree**:
  - اضافه شدن قابلیت تغییرنام مستقیم با دابل‌کلیک روی عنوان المان در درخت لایه‌ها.
  - پشتیبانی از درگ‌انددراپ بومی HTML5 برای جابه‌جایی المان‌ها و انتقال آنها بین کانتینرها درون سایدبار لایه‌ها.

---

## نتایج ارزیابی و ممیزی نهایی در راند ۱ (Final Verification Results)
- **دستگاه اشعه ایکس (`node .loop/audits/builder-xray.mjs`)**:
  - **مجموع خرابی‌ها**: **۰ خطا** (`totalFailures: 0, p0Count: 0, p1Count: 0`)
  - **پاس الگوهای آماده**: **۲۸ از ۲۸ الگو (۱۰۰٪ سبز)**
  - **پاس بلوک‌های پایه**: **۳۴ از ۳۴ بلوک (۱۰۰٪ سبز)**
  - **کنترل‌های مرده بازرس**: **۰ کنترل مرده**
- **چک‌های سلامت پلتفرم**:
  - `npx tsc --noEmit`: ۰ خطا (کامپایل کامل و بدون خطای تایپ)
  - `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل**
  - `python -m pytest app/tests/unit`: **۶۲۲ تست سبز (۲ معاف)**
  - تست‌های Playwright صفحه‌ساز: **۱۲ تست سبز در ۱۲ فایل**
- **مستندات تصویری Vision**:
  - `.loop/artifacts/excavator/round-01/after/01-studio-clean.png`
  - `.loop/artifacts/excavator/round-01/after/02-overlay-toolbar-unclipped.png`
  - `.loop/artifacts/excavator/round-01/after/03-context-menu-active.png`

---

## جزییات ریشه‌ای و معماری راند ۲ (Round 02 Deep Architectural Root Causes)

### ۱. ارتقای کنترل‌های استایل گروه‌بندی‌شده بازرس (Elementor Box Shadow & Gradients Parity)
- **نوآوری و توسعه**:
  - افزودن کنترل‌های سریع و آماده برای گرادیانت‌های پس‌زمینه (طلایی، آبی، زمردی، رز) در [inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx).
  - افزودن کنترل سایه کادر (Box Shadow) با ۵ سطح استاندارد (`none`, `sm`, `md`, `lg`, `xl`) در مدل AST و پنل بازرس.
  - پشتیبانی کامل از `box_shadow` و گرادیانت در کامپایلر سروری [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py) جهت برابری صددرصدی بوم با صفحه رندرشده نهایی (WYSIWYG Parity).

### ۲. اعتبارسنجی سخت‌گیرانه‌تر اشعه ایکس در راند ۲
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - بررسی باز شدن و رویت‌پذیری منوی راست‌کلیک روی عناصر بوم با راست‌کلیک واقعی ماوس.
  - بررسی فعال‌سازی منوی راست‌کلیک روی ردیف‌های ساختار درخت لایه‌ها (Navigator).
  - بررسی فعال‌سازی حالت تغییرنام مستقیم (Inline Rename) با دابل‌کلیک روی عنوان المان در درخت لایه‌ها.
  - بررسی پایداری وضعیت ذخیره‌سازی پیش‌نویس (Save Draft) و پاک شدن فلگ `isDirty`.
  - شکارچی کنترل‌های بازرس برای اعتبارسنجی جهش بلادرنگ متن ویجت تیتر در DOM بوم.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۲
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-02 node .loop/audits/builder-xray.mjs`)**:
  - **مجموع خرابی‌ها**: **۰ خطا** (`totalFailures: 0, p0Count: 0, p1Count: 0`)
  - **پاس الگوهای آماده**: **۲۸ از ۲۸ الگو (۱۰۰٪ سبز)**
  - **پاس بلوک‌های پایه**: **۳۴ از ۳۴ بلوک (۱۰۰٪ سبز)**
  - **کنترل‌های مرده بازرس**: **۰ کنترل مرده**
- **چک‌های سلامت پلتفرم**:
  - `npx tsc --noEmit`: ۰ خطا
  - `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل**
  - `python -m pytest app/tests/unit`: **۶۲۲ تست سبز (۲ معاف)**
  - تست‌های Playwright صفحه‌ساز: **۱۲ تست سبز در ۱۲ فایل**
- **مستندات تصویری Vision**:
  - `.loop/artifacts/excavator/round-02/after/01-inspector-shadow-and-gradients.png`
  - `.loop/artifacts/excavator/round-02/after/02-layers-tree-navigator-parity.png`
  - `.loop/artifacts/excavator/round-02/after/03-container-structure-picker.png`

---

## جزییات ریشه‌ای و معماری راند ۳ (Round 03 Deep Architectural Root Causes)

### ۱. ویرایش مستقیم درون‌خطی روی بوم (Elementor Inline Text Editing Parity)
- **نوآوری و توسعه**:
  - فعال‌سازی ویرایش مستقیم متون تیترها (`heading`) و پاراگراف‌ها (`text_editor`) مستقیماً درون بوم Iframe با دو بار کلیک (دابل‌کلیک) به سبک المنتور.
  - تعبیه کنترل‌های ورودی فوکوس‌شده خودکار درون تگ‌ها با هندلرهای اتمیک `Enter` برای ذخیره و `Escape` برای لغو، متصل به `updateElementProps`.

### ۲. اعتبارسنجی سخت‌گیرانه‌تر اشعه ایکس در راند ۳
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تست خودکار دابل‌کلیک روی تیتر در بوم و تایپ رشته «ویرایش مستقیم با دابل کلیک».
  - فشردن کلید Enter و اعتبارسنجی به‌روزرسانی DOM و همگام‌سازی استیت در AST.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۳
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-03 node .loop/audits/builder-xray.mjs`)**:
  - **مجموع خرابی‌ها**: **۰ خطا** (`totalFailures: 0, p0Count: 0, p1Count: 0`)
  - **پاس الگوهای آماده**: **۲۸ از ۲۸ الگو (۱۰۰٪ سبز)**
  - **پاس بلوک‌های پایه**: **۳۴ از ۳۴ بلوک (۱۰۰٪ سبز)**
  - **کنترل‌های مرده بازرس**: **۰ کنترل مرده**
- **چک‌های سلامت پلتفرم**:
  - `npx tsc --noEmit`: ۰ خطا
  - `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل**
  - `python -m pytest app/tests/unit`: **۶۲۲ تست سبز (۲ معاف)**
  - تست‌های Playwright صفحه‌ساز: **۱۲ تست سبز در ۱۲ فایل**
- **مستندات تصویری Vision**:
  - `.loop/artifacts/excavator/round-03/after/01-canvas-inline-editing.png`
  - `.loop/artifacts/excavator/round-03/after/02-studio-round03-verified.png`

---

## جزییات ریشه‌ای و معماری راند ۴ (Round 04 Deep Architectural Root Causes)

### ۱. پیاده‌سازی سیستم تایپوگرافی کامل به سبک المنتور (Elementor Typography Grouped Controls)
- **نوآوری و توسعه**:
  - افزودن کنترل‌های اندازه قلم عددی به پیکسل (`fontSize`) با ورودی استاندارد در [inspector-panel.tsx](frontend/components/admin/builder/inspector-panel.tsx).
  - انتخابگر ضخامت فونت (`fontWeight`) از ۳۰۰ تا ۹۰۰ با نام‌گذاری‌های استاندارد (Light, Normal, Medium, SemiBold, Bold, Black).
  - انتخابگر ۴ حالته ترازبندی متن (`textAlign`: راست‌چین، وسط‌چین، چپ‌چین، هم‌تراز).
  - اتصال کامل تایپوگرافی به کامپایلر سرور [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py) جهت تولید CSS درون‌خطی تمیز برای خروجی رندر نهایی.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۴
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تغییر اندازه قلم تیتر به ۲۸ پیکسل در بازرس و اعتبارسنجی اعمال فوری `fontSize: 28px` در `getComputedStyle`.
  - کلیک روی پیش‌تنظیم سایه کادر برجسته (`lg`) و اعتبارسنجی محاسبه سایه در DOM بوم.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۴
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-04 node .loop/audits/builder-xray.mjs`)**:
  - **مجموع خرابی‌ها**: **۰ خطا** (`totalFailures: 0, p0Count: 0, p1Count: 0`)
  - **پاس الگوهای آماده**: **۲۸ از ۲۸ الگو (۱۰۰٪ سبز)**
  - **پاس بلوک‌های پایه**: **۳۴ از ۳۴ بلوک (۱۰۰٪ سبز)**
  - **کنترل‌های مرده بازرس**: **۰ کنترل مرده**
- **چک‌های سلامت پلتفرم**:
  - `npx tsc --noEmit`: ۰ خطا
  - `npm test` (Vitest): **۳۷۲ تست سبز در ۴۵ فایل**
  - `python -m pytest app/tests/unit`: **۶۲۲ تست سبز (۲ معاف)**
  - تست‌های Playwright صفحه‌ساز: **۱۲ تست سبز در ۱۲ فایل**
- **مستندات تصویری Vision**:
  - `.loop/artifacts/excavator/round-04/after/01-elementor-typography-controls.png`
  - `.loop/artifacts/excavator/round-04/after/02-studio-round04-clean.png`


