# گزارش ممیزی راند ۳۵ — پورت و برابری ۴ لایه ویجت‌های کلیدی تکمیلی Elementor Core & Pro (Audio, Google Maps, Search Bar, Nav Menu, Read More, Rating)

- **شماره راند**: ۳۵ (Round 35)
- **سطح**: وزنه ۷ و ۸ (پورت المنتور — موج ۲ و ۳)
- **شاخه ایزوله**: `worktree-gym-r41`
- **پورت استودیو**: ۴۰۰۴ (`http://127.0.0.1:4004`)
- **تاریخ اجرا**: 2026-11-22
- **وضعیت کل تست‌ها**: ۳۷۷ تست Vitest فرانت‌اند ۱۰۰٪ سبز | ۶۴۴ تست پایتون بک‌اند ۱۰۰٪ سبز | تست‌های Playwright راند ۳۵ ۱۰۰٪ سبز (۲ از ۲) | کامپایل تایپ‌اسکریپت (`tsc --noEmit`) ۰ خطا

---

### ۱. باگ‌ها و شکاف‌های کشف‌شده در بررسی اولیه و ابزار Vision

1. **فقدان ۶ ویجت کلیدی المنتور در پالت و بوم فرانت‌اند**:
   - *مشاهده در Vision*: در تصویر `before/01-studio-overview.png` و `before/02-palette-missing-new-widgets.png`، با جستجوی «فرم جستجو»، «صوت» و «نقشه»، صفر نتیجه در پالت یافت می‌شد و این ویجت‌ها در فرانت‌اند ثبت نشده بودند در حالی که شاخه‌های کامپایلر بک‌اند در `ast_compiler.py` از قبل پیاده‌سازی شده بودند.
   - *اصلاح ریشه‌ای در لایه ۱ (Block Registry)*: ثبت کامل هر ۶ ویجت در `frontend/lib/builder/block-registry.ts` با دسته‌بندی `basic`، آیکون‌های لوسید متناسب (`Headphones`, `MapPin`, `Search`, `Navigation`, `ArrowLeft`, `Star`)، توضیحات فارسی دقیق و متدهای `createDefaultElement`.

2. **فقدان رندرهای زنده در بوم ویرایشگر (`canvas-element.tsx`)**:
   - *اصلاح ریشه‌ای در لایه ۲*: پیاده‌سازی کیس‌های `audio` (پخش‌کننده صوتی کامل)، `google_maps` (پیش‌نمایش نقشه با پین و آدرس سفارشی)، `read_more` (پیوند جهت‌دار)، `rating` (نشانگر ستاره‌ای و عددی)، `search_bar` (فرم تعاملی جستجو) و `nav_menu` (فهرست افقی لینک‌ها) در تابع `renderWidget`.

3. **نبود کنترل‌های محتوایی تب Content در پنل بازرس (`inspector-panel.tsx`)**:
   - *اصلاح ریشه‌ای در لایه ۳*: پیاده‌سازی کامل فرم‌های ویرایش مشخصات در تب محتوا برای هر ۶ ویجت با شناسه تست (`data-testid`) استاندارد و واکنش زنده به تغییر مقادیر (Nudge test) بدون افت وضعیت.

4. **تثبیت برابری با کامپایلر SSR بک‌اند (`ast_compiler.py`)**:
   - *لایه ۴*: بررسی و هماهنگ‌سازی کامل پراپ‌های `url`/`src`، `title`، `address`، `height`، `placeholder`، `action_url`، `button_text`، `items` و `rating_value`/`rating_scale` بین ذخیره‌ساز Zustand، کلاینت Next.js و خروجی HTML تولیدشده توسط پایتون.

---

### ۲. مستندات بصری قبل و بعد (Vision Artifacts)

- **تصاویر قبل از اصلاح**: `.loop/artifacts/builder-gym/round-35/before/`
  - `01-studio-overview.png`: نمای کامل ۱۲۸۰×۱۰۸۰ با سرریز و استایل اولیه.
  - `02-palette-missing-new-widgets.png`: نتیجه صفر در جستجوی «فرم جستجو» و غیبت ویجت‌ها در پالت.
  - `03-canvas-default.png`: بوم اولیه پیش از درج ویجت‌ها.

- **تصاویر بعد از اصلاح**: `.loop/artifacts/builder-gym/round-35/after/`
  - `01-studio-overview.png`: نمای ۳ ستونه بی‌نقص استودیو در ۱۹۲۰×۱۰۸۰، استایل تمیز هدر، حضور ویجت‌های صوتی، نقشه و جستجو در بوم با داده‌های تغییریافته و پنل بازرس فعال.
  - `02-palette-new-widgets.png`: نمایش کامل و فیلتر بی‌درنگ ویجت‌های جدید در پالت با تگ بلوک‌ها.
  - `03-canvas-with-new-widgets.png`: رندر دقیق اجزای تعاملی درون بوم Iframe.
  - `04-inspector-nudge-active.png`: تکان دادن موفق کنترل‌های بازرس و به‌روزرسانی آنی نام، آدرس و مشخصات در بوم.

---

### ۳. فایل‌های تغییریافته

1. `frontend/lib/builder/block-registry.ts`: اضافه شدن ۶ ویجت جدید به `BASIC_BLOCK_DEFINITIONS` و ایمپورت آیکون‌های `Headphones`, `Search`, `ArrowLeft`, `Navigation`.
2. `frontend/components/admin/builder/canvas-element.tsx`: افزودن شاخه‌های رندر ۶ ویجت در `renderWidget()`.
3. `frontend/components/admin/builder/inspector-panel.tsx`: افزودن کنترل‌های محتوایی ۶ ویجت در `renderContentControls()`.
4. `frontend/tests/native-widgets.test.ts`: افزودن تست انطباق اسکیما و رجیستری برای ۶ ویجت جدید.
5. `frontend/tests/e2e/builder-gym-r35.spec.ts`: تست End-to-End شامل فیلتر پالت، درج ویجت‌ها و آزمون Nudge بازرس.
6. `.loop/STATE.json`: به‌روزرسانی متریگ‌ها، تست‌ها و وضعیت پورت ۴۰۰۴.

---

### ۴. نتایج نهایی راستی‌آزمایی

- `npx tsc --noEmit`: **۰ خطا** (کامل و سبز)
- `npm test` (Vitest): **۳۷۷ تست سبز در ۴۵ فایل** (`377 passed`)
- `python -m pytest app/tests/unit`: **۶۴۴ تست سبز، ۲ اسکیپ** (`644 passed, 2 skipped`)
- `npx playwright test builder-gym-r35`: **۲ تست سبز در ۱۴.۱ ثانیه**
