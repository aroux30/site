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
| **Round 05** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. سیستم کامل کنترل‌های کادر و حاشیه به سبک Elementor (نوع خط، ضخامت، رنگ و شعاع گردی)**<br>**۲. پشتیبانی کامل کامپایلر بک‌اند از border-style، border-width و border-color**<br>**۳. اعتبارسنجی جهش بلادرنگ ضخامت کادر به ۴ پیکسل در تست‌های اشعه ایکس**<br>**۴. ثبات کامل ۱۰۰٪ پلتفرم و ثبت رکوردهای نهایی بدون نقص** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 06** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. اعتبارسنجی سوئیچ بی‌درنگ ویوپورت‌های ریسپانسیو (موبایل ۳۷۵، تبلت ۷۶۸، دسکتاپ ۱۴۴۰)**<br>**۲. ارزیابی انطباق لایه مستقل Overlay Portal در ابعاد گوناگون فریم بوم**<br>**۳. ثبت ۱۰۰٪ پایداری بدون رگرسیون در ۲۸ الگوی آماده و ۳۴ بلوک بومی**<br>**۴. پاس کامل تمام ۱۲ تست پلی‌رایت، ۳۷۲ تست ویتست و ۶۲۲ تست پای‌تست** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 07** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. تست تعاملی واقعی درگ‌انددراپ بومی HTML5 از پالت به بوم**<br>**۲. درج مستقیم و افزایش اتمیک تعداد عناصر AST پس از دراپ**<br>**۳. تایید عملکرد پلتفرم بدون خطاهای کراش یا هیدراسیون**<br>**۴. حفظ ۱۰۰٪ سبزی تمامی گیت‌های کیفیت مخزن** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 08** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. تست ری‌لود کامل صفحه و اعتبارسنجی ماندگاری المان‌ها در بوم**<br>**۲. برابری کامل خروجی عمومی استورفرانت با داخل بوم (WYSIWYG Parity)**<br>**۳. تایید صحت رندر کامپایلر سروری در مسیر عمومی /e2e-isolated-scratchpad**<br>**۴. پایداری ۱۰۰٪ با صفر خطای مطلق در اشعه ایکس و تمام گیت‌های آزمون** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 09** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. اعتبارسنجی اتمیک تاریخچه بازگشت و انجام مجدد (Undo/Redo History)**<br>**۲. تست کلیدهای میانبر استاندارد دسکتاپ (Ctrl+Z و Ctrl+Y)**<br>**۳. تایید پایداری کامل استیت در ۲۸ الگوی آماده و ۳۴ بلوک پایه**<br>**۴. پاس کامل ۱۰۰٪ تمام تست‌های پلتفرم و ثبت کارنامه سبز** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 10** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. تست فشار فوق سنگین ۷۹ المان تودرتو در ۶ سکشن و ۲۴ ستون**<br>**۲. رفع نقص ریشه‌ای کراش پدینگ/مارجین ناقص (TypeError on undefined.value)**<br>**۳. تثبیت کامل پایداری فریم بوم و حفظ صفر خطای اشعه ایکس**<br>**۴. فتح کامل قله و ثبت کارنامه پاک در هر ۱۰ راند عملیات بیل مکانیکی** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |
| **Round 11** | **0** (P0: 0, P1: 0) | **0** (P0: 0, P1: 0) | **۱. آزمون چرخه کامل سریال‌سازی و بازگردانی قالب‌های برگه (Template Export / Import)**<br>**۲. اعتبارسنجی یکپارچگی دیالوگ ذخیره قالب کل برگه در نوار ابزار**<br>**۳. تایید حفظ کامل ساختار درختی بدون افت عناصر یا استایل‌ها در راند ۱۱**<br>**۴. پایداری ۱۰۰٪ با صفر خطای مطلق در تمام ممیزی‌ها و تست‌ها** | **28/28** | **34/34** | **0** | ✅ کامل و سبز |

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

---

## جزییات ریشه‌ای و معماری راند ۵ (Round 05 Deep Architectural Root Causes)

### ۱. پیاده‌سازی سیستم کادر و حاشیه کامل به سبک المنتور (Elementor Border & Outline System)
- **نوآوری و توسعه**:
  - انتخابگر نوع خط حاشیه (`borderStyle`: solid, dashed, dotted, double, none).
  - کنترل ضخامت حاشیه عددی به پیکسل (`borderWidth`) با اعمال بلادرنگ در DOM بوم.
  - انتخابگر رنگ حاشیه با ورودی رنگ و پشتیبانی از متغیرهای HSL و توکن‌های سازمانی.
  - یکپارچه‌سازی کامل در کامپایلر سرور [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py) جهت تولید ویژگی‌های CSS استاندارد برای لندینگ‌ها.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۵
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تنظیم ضخامت کادر تیتر به ۴ پیکسل در بازرس و اعتبارسنجی بلادرنگ `borderTopWidth: 4px` در DOM بوم.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۵
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-05 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-05/after/01-elementor-border-controls.png`
  - `.loop/artifacts/excavator/round-05/after/02-studio-round05-clean.png`

---

## جزییات ریشه‌ای و معماری راند ۶ (Round 06 Deep Architectural Root Causes)

### ۱. اعتبارسنجی سوئیچ ویوپورت‌های ریسپانسیو و انطباق ابعاد لایه Overlay Portal
- **نوآوری و توسعه**:
  - اعتبارسنجی رفتار تعاملی ۳ ویوپورت (موبایل ۳۷۵px، تبلت ۷۶۸px، دسکتاپ ۱۴۴۰px) در [builder-toolbar.tsx](frontend/components/admin/builder/builder-toolbar.tsx) و فریم بوم [canvas-frame.tsx](frontend/components/admin/builder/canvas-frame.tsx).
  - تثبیت بازنشانی هوشمند ابعاد و موقعیت لایه [canvas-overlay.tsx](frontend/components/admin/builder/canvas-overlay.tsx) از طریق ResizeObserver در ابعاد گوناگون ویوپورت‌ها بدون تداخل یا پرش.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۶
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تست خودکار سوئیچ به تبلت و اعتبارسنجی `activeBreakpoint === "tablet"`.
  - تست خودکار سوئیچ به موبایل و اعتبارسنجی `activeBreakpoint === "mobile"`.
  - تست خودکار بازگشت به دسکتاپ و اعتبارسنجی `activeBreakpoint === "desktop"`.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۶
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-06 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-06/after/01-viewport-tablet-768.png`
  - `.loop/artifacts/excavator/round-06/after/02-viewport-mobile-375.png`
  - `.loop/artifacts/excavator/round-06/after/03-viewport-desktop-1440.png`

---

## جزییات ریشه‌ای و معماری راند ۷ (Round 07 Deep Architectural Root Causes)

### ۱. اعتبارسنجی درگ‌انددراپ بومی و درج المان‌ها
- **نوآوری و توسعه**:
  - اعتبارسنجی انتقال و دریافت داده‌های JSON در رویداد دراپ بومی HTML5 در ریشه بوم و کانتینرها.
  - اعتبارسنجی افزایش اتمیک تعداد عناصر AST و استقرار کامل ویجت‌ها پس از رهاسازی در کانتینر.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۷
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تست خودکار دراپ بلوک دکمه (`button`) از پالت به ریشه بوم (`builder-canvas-root`) با آبجکت `DataTransfer`.
  - اعتبارسنجی افزایش تعداد المان‌های بوم بدون پرش یا خطای کنسول.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۷
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-07 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-07/after/01-dnd-canvas-inserted.png`
  - `.loop/artifacts/excavator/round-07/after/02-studio-round07-clean.png`

---

## جزییات ریشه‌ای و معماری راند ۸ (Round 08 Deep Architectural Root Causes)

### ۱. اعتبارسنجی ری‌لود کامل صفحه و انطباق WYSIWYG خروجی استورفرانت
- **نوآوری و توسعه**:
  - اعتبارسنجی پایداری و بازیابی خودکار ساختار AST بوم پس از رفرش کامل مرورگر بدون افت المان‌ها.
  - اعتبارسنجی خروجی عمومی مسیر `/e2e-isolated-scratchpad` و تطابق رندر HTML کامپایلر سروری با داخل بوم استودیو.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۸
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تست خودکار رفرش کامل صفحه (`page.reload`) و اعتبارسنجی حضور تمام عناصر بوم.
  - تست باز کردن برگه در حالت عمومی (بدون پارامتر ویرایشگر) و بررسی رندر کامل ساختار در کانتینر `.builder-rendered-content`.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۸
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-08 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-08/after/01-studio-round08-verified.png`
  - `.loop/artifacts/excavator/round-08/after/02-public-storefront-wysiwyg.png`

---

## جزییات ریشه‌ای و معماری راند ۹ (Round 09 Deep Architectural Root Causes)

### ۱. اعتبارسنجی پشته تاریخچه بازگشت و انجام مجدد (Undo / Redo History Parity)
- **نوآوری و توسعه**:
  - اعتبارسنجی ذخیره‌سازی اتمیک درخت AST در پشته `history.past` با ظرفیت تا ۵۰ مرحله گذشته.
  - تست عملکرد دکمه‌های ناوبری Undo و Redo در نوار ابزار اصلی [builder-toolbar.tsx](frontend/components/admin/builder/builder-toolbar.tsx) و میانبرهای کیبورد `Ctrl+Z` و `Ctrl+Y`.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۹
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تست خودکار تکثیر المان و ثبت وضعیت اولیه.
  - فشردن دکمه Undo و اعتبارسنجی بازگشت دقیق تعداد المان‌ها به حالت پیش از تکثیر.
  - فشردن دکمه Redo و اعتبارسنجی اعمال مجدد تغییرات بدون کوچک‌ترین عدم تطابق در ساختار AST.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۹
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-09 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-09/after/01-studio-round09-clean.png`
  - `.loop/artifacts/excavator/round-09/after/02-history-undo-redo-state.png`

---

## جزییات ریشه‌ای و معماری راند ۱۰ (Round 10 Deep Architectural Root Causes)

### ۱. کشف و ریشه‌کنی خطای بحرانی عدم تحمل مقادیر حاشیه/پدینگ تک‌جهته (TypeError on undefined.value)
- **علت ریشه‌ای قبل از اصلاح**:
  - در [canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx)، توابع `resolvePadding` و `resolveMargin` به اشتباه فرض می‌کردند که در صورت وجود آبجکت `padding` یا `margin`، تمام ویژگی‌های چهارگانه `p.top`, `p.right`, `p.bottom`, `p.left` حتماً تعریف شده‌اند. در صورت تعریف شدن پدینگ به صورت خلاصه یا متصل (`isLinked: true` با تنها `top`)، دسترسی به `p.right.value` باعث پرتاب خطای جاوااسکریپتی `TypeError: Cannot read properties of undefined (reading 'value')` و کراش کردن کامل لایه رندر ری‌اکت در بوم می‌شد.
- **اصلاح ریشه‌ای**:
  - اعمال فال‌بک ایمن و پیشرفته در `resolvePadding`، `resolveMargin`، `border.width` و `border.radius` در [canvas-element.tsx](frontend/components/admin/builder/canvas-element.tsx) و کامپایلر سرور [ast_compiler.py](backend/app/modules/content/application/ast_compiler.py) به نحوی که مقادیر مفقود به صورت خودکار از `top` یا صفر به ارث برده شوند.

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۱۰
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - تست فشار سنگین تزریق بیش از ۵۰ المان تودرتو (۷۹ المان در ۶ سکشن و ۲۴ ستون فلکس و گرید).
  - اعتبارسنجی رندر کامل و بی‌درنگ تمام ۷۹ المان بدون هیچ‌گونه افت فریم یا خطای هیدراسیون.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۱۰
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-10 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-10/after/01-studio-round10-clean.png`
  - `.loop/artifacts/excavator/round-10/after/02-stress-50-elements-canvas.png`

---

## جزییات ریشه‌ای و معماری راند ۱۱ (Round 11 Deep Architectural Root Causes)

### ۱. اعتبارسنجی کامل چرخه سریال‌سازی و ایمپورت قالب‌های کل برگه (Template Export / Import Parity)
- **نوآوری و توسعه**:
  - اعتبارسنجی چرخه کامل JSON export / import بر روی استیت Zustand و اطمینان از حفظ دقیق تمام ۲۸ الگوی آماده و ساختارهای تودرتو بدون حذف یا تغییر شکل پروپرتی‌ها.
  - تست پایداری دیالوگ ذخیره قالب کل برگه در نوار ابزار اصلی [builder-toolbar.tsx](frontend/components/admin/builder/builder-toolbar.tsx).

### ۲. اعتبارسنجی ارتقایافته در ممیزی اشعه ایکس راند ۱۱
- **چک‌های جدید اضافه‌شده به builder-xray.mjs**:
  - استخراج زنده AST صفحه به رشته JSON استاندارد.
  - پارس مجدد و تزریق مستقیم به `replacePageAST`.
  - اعتبارسنجی برابری دقیق تعداد المان‌های ریشه و عدم ایجاد خطای هیدراسیون.

### ۳. نتایج ارزیابی و ممیزی نهایی در راند ۱۱
- **دستگاه اشعه ایکس (`EXCAVATOR_ROUND=round-11 node .loop/audits/builder-xray.mjs`)**:
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
  - `.loop/artifacts/excavator/round-11/after/01-studio-round11-verified.png`
  - `.loop/artifacts/excavator/round-11/after/02-save-page-template-dialog.png`









