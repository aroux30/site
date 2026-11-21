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

## اهداف راند بعدی (Round 02)
- آغاز مسیر A وزنه ۱ و ۲:
  - برطرف کردن شکاف SSR شناسایی‌شده (`backdropBlur` در `ast_compiler.py`).
  - آغاز ممیزی ۵-سیگنالی دسته‌های ۵‌تایی ویجت‌ها در `.loop/builder_control_matrix.json`.
