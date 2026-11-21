# کارنامه رسمی مأموریت BUILDER ELITE V2 (.loop/BUILDER_ELITE_V2_LOG.md)

**پروژه**: Visual Page Builder (`aroux30/site`)  
**شاخه Git**: `claude/heuristic-lamport-ee5149` (محیط ایزوله Worktree)  
**سورس مرجع**: `C:\Users\Administrator\Desktop\elementor` (Elementor Core & Pro — فقط خواندنی)  
**معماری**: React / Next.js 15 + Zustand + TailwindCSS + Pydantic v2 + SSR AST Compiler  
**سیاست اعتبارسنجی**: پروتکل ۵-سیگنالی سنجش واقعی (S1 State, S2 DOM, S3 ComputedStyle, S4 Pixel Diff, S5 Persistence & SSR Parity)  

---

## کارنامه راندها

### راند ۱ — راه‌اندازی و احصای ۱۰۰٪ کنترل‌ها (Round 01: Phase Zero Reconnaissance & Indexing)
- **تاریخ**: 2026-11-21
- **کامیت**: `chore(builder-v2-init): index builder controls and elementor reference`
- **اقدامات انجام‌شده**:
  1. ساخت و اجرای اسکنر سیم‌کشی استاتیک بیلدر (`scripts/loop/builder-wiring-audit.mjs`):
     - تحلیل ۴ دسته شکاف در کد فرانت‌اند و بک‌اند و ذخیره گزارش در `.loop/builder_wiring_gaps.json`.
     - شناسایی ۱ مورد عدم انطباق SSR (`backdropBlur` در `ast_compiler.py`).
  2. ایجاد ماتریس قطعی ۳۶۰ درجه کنترل‌های بیلدر (`.loop/builder_control_matrix.json`):
     - احصای کامل ۷۰ ردیف شامل ۳۵ ویجت بومی، ۲۸ الگوی آماده، ۳ کامپوننت اسکلت استودیو و ۴ دیالوگ اصلی.
     - تعریف تب‌های سه‌گانه Content، Style و Advanced همراه با الزامات اعتبارسنجی ۵-سیگنالی.
  3. استخراج نقشه جامع بک‌لاگ مرجع المنتور و المنتور پرو (`.loop/elementor_parity_backlog.json`):
     - اسکن بازگشتی `C:\Users\Administrator\Desktop\elementor` و استخراج ۹۱ مدخل در ۳ موج:
       - **موج ۱ (۵۱ آیتم)**: گروه‌های کنترل حرفه‌ای، کانتینر Grid، جداکننده‌های شکلی SVG و ناوبری پیشرفته.
       - **موج ۲ (۲۴ آیتم)**: ویجت‌های مفقود Core و Pro، ماژول‌های تعاملی پاپ‌آپ و Off-Canvas.
       - **موج ۳ (۱۶ آیتم)**: کیت سراسری سایت، Theme Builder، Loop Builder و فرم چندمرحله‌ای.
  4. ساخت اسکریپت آزمون ۵-سیگنالی علّی (`scripts/loop/builder-5signal-probe.mjs`):
     - اجرای آزمون بر روی محیط `/e2e-isolated-scratchpad?builder=1`.
     - ثبت تصاویر قبل، بعد و تفاوت پیکسلی در `.loop/artifacts/builder-v2/round-01/`.
     - ۵ از ۵ پروب سبز با حکم **PASS**.
- **گزارش ۵ پروب**:
  - `PROBE-W1-LAYERS-TREE`: رویت‌پذیری دکمه‌های اکشن Navigator و تورفتگی RTL (تأیید ۴ ردیف لایه) -> PASS
  - `PROBE-W2-HEADING-5SIGNAL`: آزمون جهش فعال ویجت سرتیتر در ۳ تب، تغییر پیکسلی ۱۵۵۱ پیکسل، اعمال استایل وسط‌چین و ذخیره پیش‌نویس -> PASS
  - `PROBE-W3-PATTERNS-PALETTE`: بارگذاری کامل پالت الگوها (۲۸ الگوی آماده فعال) -> PASS
  - `PROBE-W3-GLOBAL-STYLES`: باز شدن، نمایش توکن‌ها و بستن دیالوگ استایل‌های سراسری با Escape -> PASS
  - `PROBE-W5-RESPONSIVE-BREAKPOINTS`: تغییر سایز بوم Iframe در تبلت (768px) و موبایل (375px) با حفظ ایزولاسیون کامل مدیاکوئری‌ها -> PASS

---

### راند ۲ — برطرف کردن شکاف SSR و اعتبارسنجی ۵-سیگنالی وزنه‌های ۱ و ۲ (Round 02: SSR Gap Closure & 5-Signal Active Nudge)
- **تاریخ**: 2026-11-21
- **کامیت**: `fix(builder-v2-r02): close SSR backdropBlur gap, fix button navigation and verify 7 active probes`
- **اقدامات انجام‌شده**:
  1. **اصلاح شکاف SSR و کامپایلر استایل‌ها**:
     - اضافه شدن فیلدهای `backdrop_blur` و `filter_blur` به مدل `DeviceStyle` در `builder_ast.py`.
     - اضافه شدن `shape_divider_top`، `shape_divider_bottom` و `shape_divider_color` به `ResponsiveStyles` در `builder_ast.py`.
     - اعمال و کامپایل واقعی `backdrop-filter: blur(...)` و `filter: blur(...)` و کلاس‌های خط جداکننده `border-dashed` و `border-dotted` در `ast_compiler.py`.
     - صفر شدن ۱۰۰٪ شکاف‌های گزارش‌شده در `.loop/builder_wiring_gaps.json` (۰ خطای هاردکد، ۰ ناهماهنگی استور به بوم، ۰ شکاف کامپایل SSR، ۰ نقطه کور کنترلی).
  2. **اصلاح تعامل کلیک دکمه در بوم بیلدر**:
     - الحاق `e.preventDefault()` به تگ `<a>` دکمه در حالت غیر پیش‌نمایش جهت جلوگیری از پرش ناوبری پیش‌فرض مرورگر در حین انتخاب المان.
     - اضافه شدن شناسه استاندارد تست `data-testid="button-label-input"` و `data-testid="spacer-height-input"` در `inspector-panel.tsx`.
     - پشتیبانی یکپارچه از ویجت‌های معادل `paragraph` و `text` در کنار `text_editor` در بوم و کامپایلر SSR.
  3. **گسترش پروتکل ۵-سیگنالی سنجش واقعی**:
     - اجرای ۷ پروب مستقل با فعال‌سازی تب‌های محتوا، تغییر استایل و بررسی تفاوت پیکسلی.
     - نتیجه: ۷ از ۷ پروب سبز (۱۰۰٪ PASS).
     - ذخیره خروجی‌های تصویری و فایل گزارش در `.loop/artifacts/builder-v2/round-02/`.
  4. **به‌روزرسانی ماتریس کنترل‌ها**:
     - تأیید و قفل ردیف‌های `WIDGET-heading`، `WIDGET-button`، `WIDGET-spacer`، `SHELL-layers-tree`، `SHELL-builder-toolbar`، `SHELL-blocks-palette` و `DIALOG-global-styles-dialog`.

---

### راند ۳ — آزمون ۵-سیگنالی فیلدهای فرم و تعاملی (Round 03: Form Widgets 5-Signal Active Probe)
- **تاریخ**: 2026-11-21
- **کامیت**: `feat(builder-v2-r03): verify form input 5-signals and harden inspector test ids`
- **اقدامات انجام‌شده**:
  1. **تجهیز شناسه‌های تست تعاملی بازرس فرم**:
     - اضافه شدن شناسه‌های تست برای فیلدهای فرم: `data-testid="form-input-label-input"`, `data-testid="form-textarea-label-input"`, `data-testid="form-select-label-input"`, `data-testid="form-container-submit-url"`, `data-testid="form-container-success-input"`.
  2. **آزمون ۵-سیگنالی علّی (Active Nudge)**:
     - پروب ۸ گانه شامل ویجت ورودی متنی فرم با ثبت جهش متن، بررسی جهش DOM در آی‌فریم و ثبت تفاوت ۴۶۱ پیکسلی.
     - نتیجه: ۸ از ۸ پروب کاملاً سبز (۱۰۰٪ PASS).
     - ذخیره گزارش کامل و مصنوعات در `.loop/artifacts/builder-v2/round-03/`.
  3. **ارتقای ماتریس کنترل‌ها**:
     - ارتقای ردیف‌های پاس‌شده به ۸ مدخل رسمی در `.loop/builder_control_matrix.json`.

---

### راند ۴ — ارتقا و آزمون ۵-سیگنالی آکاردئون و تب‌های تعاملی (Round 04: Interactive Accordion & Tabs 5-Signal Probe)
- **تاریخ**: 2026-11-21
- **کامیت**: `feat(builder-v2-r04): verify accordion 5-signals and enrich interactive tab controls`
- **اقدامات انجام‌شده**:
  1. **تجهیز شناسه‌های تست تعاملی آکاردئون و تب‌ها**:
     - الحاق شناسه‌های آزمون `data-testid="accordion-item-title-0"`، `data-testid="accordion-add-item-btn"`، `data-testid="tabs-add-tab-btn"` و `data-testid="tab-title-input-0"`.
  2. **آزمون ۵-سیگنالی علّی آکاردئون**:
     - اضافه شدن بلوک آکاردئون از پالت، تغییر تیتر سؤال اول به «آیا ارسال سفارش‌ها رایگان است؟»، ثبت تغییر آنی در بوم و تفاوت پیکسلی در تصویر `accordion-diff.png`.
     - نتیجه پروب: ۹ از ۹ پروب کاملاً سبز (۱۰۰٪ PASS).
     - ذخیره مصنوعات در `.loop/artifacts/builder-v2/round-04/`.
  3. **ارتقای ماتریس کنترل‌ها**:
     - پیشرفت مدخل‌های تأییدشده به ۹ ردیف در `.loop/builder_control_matrix.json`.

---

### راند ۵ — آزمون ۵-سیگنالی جدول داده‌ها و باکس آیکون (Round 05: Table & Icon Box 5-Signal Active Probe)
- **تاریخ**: 2026-11-21
- **کامیت**: `feat(builder-v2-r05): verify table and iconbox 5-signals with live property mutations`
- **اقدامات انجام‌شده**:
  1. **تجهیز شناسه‌های آزمون بازرس جدول و آیکون‌باکس**:
     - اضافه شدن شناسه‌های تست `data-testid="table-headers-input"` و `data-testid="iconbox-title-input"`.
  2. **آزمون ۵-سیگنالی علّی جدول و آیکون‌باکس**:
     - تغییر عناوین ستون‌های جدول به «مدل، گارانتی طلایی، وضعیت»، بررسی بازتاب در سلول‌های `<th>` بوم و ذخیره تفاوت تصویری.
     - تغییر عنوان آیکون‌باکس به «پشتیبانی VIP ۲۴ ساعته»، بررسی تغییر آنی DOM و ثبت تفاوت پیکسلی.
     - نتیجه پروب: ۱۱ از ۱۱ پروب کاملاً سبز (۱۰۰٪ PASS).
     - ذخیره فایل گزارش و تصاویر در `.loop/artifacts/builder-v2/round-05/`.
  3. **ارتقای ماتریس کنترل‌ها**:
     - پیشرفت مدخل‌های تأییدشده به ۱۱ ردیف در `.loop/builder_control_matrix.json`.

---

### راند ۶ — آزمون ۵-سیگنالی کارت محصول و ویترین فروشگاهی (Round 06: Product Card 5-Signal Active Probe)
- **تاریخ**: 2026-11-21
- **کامیت**: `feat(builder-v2-r06): verify product card 5-signals and advance store widget parity`
- **اقدامات انجام‌شده**:
  1. **تجهیز شناسه‌های آزمون بازرس کارت محصول**:
     - الحاق شناسه‌های تست `data-testid="product-card-name-input"`، `data-testid="star-rating-value-input"` و `data-testid="add-to-cart-label-input"`.
  2. **آزمون ۵-سیگنالی علّی کارت محصول**:
     - درج کارت محصول از پالت، تغییر نام کالا به «هدفون نویزکنسلینگ سونی مدل Pro»، بررسی انعکاس زنده روی تگ `<h3>` کارت داخل بوم آی‌فریم و ثبت تفاوت پیکسلی.
     - نتیجه پروب: ۱۲ از ۱۲ پروب کاملاً سبز (۱۰۰٪ PASS).
     - ذخیره مصنوعات و گزارش رسمی در `.loop/artifacts/builder-v2/round-06/`.
  3. **ارتقای ماتریس کنترل‌ها**:
     - ارتقای ردیف‌های تاییدشده به ۱۲ مدخل رسمی در `.loop/builder_control_matrix.json`.

---

### راند ۷ — آزمون ۵-سیگنالی قیمت محصول و امتیاز ستاره‌ای (Round 07: Product Price & Star Rating 5-Signal Active Probe)
- **تاریخ**: 2026-11-21
- **کامیت**: `feat(builder-v2-r07): verify product price and star rating with live DOM formatting`
- **اقدامات انجام‌شده**:
  1. **تجهیز شناسه‌های آزمون بازرس قیمت و امتیاز**:
     - الحاق شناسه‌های تست `data-testid="product-price-input"` و `data-testid="star-rating-value-input"`.
  2. **آزمون ۵-سیگنالی علّی قیمت و امتیاز ستاره‌ای**:
     - تغییر قیمت کالا به ۴,۵۰۰,۰۰۰ تومان، تایید انعکاس با فرمت ارقام فارسی در بوم و ثبت تفاوت پیکسلی ۱۳۰۱ پیکسلی.
     - تغییر امتیاز ستاره‌ای از ۵ به ۲.۵، تایید تغییر تعداد ستاره‌های پر و خالی در DOM و ثبت تفاوت پیکسلی.
     - نتیجه پروب: ۱۴ از ۱۴ پروب کاملاً سبز (۱۰۰٪ PASS).
     - ذخیره مصنوعات و گزارش رسمی در `.loop/artifacts/builder-v2/round-07/`.
  3. **ارتقای ماتریس کنترل‌ها**:
     - پیشرفت مدخل‌های تأییدشده به ۱۴ ردیف رسمی در `.loop/builder_control_matrix.json`.

---

## اهداف راند بعدی (Round 08)
- تکمیل موج ۱ بک‌لاگ المنتور (کانتینر CSS Grid، تغییر نام مستقیم در Navigator و اشکال جداکننده SVG).






