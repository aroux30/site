# گزارش ممیزی راند ۳۶ — پورت و برابری ۴ لایه ویجت‌های تعاملی رسانه و کد (Video Playlist, Image Comparison, Custom HTML)

- **شماره راند**: ۳۶ (Round 36)
- **سطح**: وزنه ۷ و ۸ (پورت المنتور — موج ۲ و ۳)
- **شاخه ایزوله**: `worktree-gym-r41`
- **پورت استودیو**: ۴۰۰۴ (`http://127.0.0.1:4004`)
- **تاریخ اجرا**: 2026-11-22
- **وضعیت کل تست‌ها**: ۳۷۸ تست Vitest فرانت‌اند ۱۰۰٪ سبز | ۶۴۵ تست پایتون بک‌اند ۱۰۰٪ سبز | تست‌های Playwright راند ۳۶ ۱۰۰٪ سبز (۲ از ۲) | کامپایل تایپ‌اسکریپت (`tsc --noEmit`) ۰ خطا

---

### ۱. باگ‌ها و شکاف‌های کشف‌شده در بررسی اولیه و ابزار Vision

1. **فقدان ماژول‌های لیست پخش ویدیو، اسلایدر مقایسه تصویر و کد سفارشی HTML در پالت بلوک‌ها**:
   - *مشاهده در Vision*: در تصویر `before/01-studio-overview.png` و `before/02-palette-missing-r36-widgets.png`، با جستجوی عناوین «لیست پخش»، «مقایسه تصویر» و «کد سفارشی»، صفر نتیجه در پالت یافت می‌شد.
   - *اصلاح ریشه‌ای در لایه ۱ (Block Registry)*: ثبت رسمی ۳ ویجت در `frontend/lib/builder/block-registry.ts` با آیکون‌های لوسید متناسب (`PlaySquare`, `SplitSquareVertical`, `Code2`)، توضیحات فارسی روان، متدهای `createDefaultElement` و ساختار منسجم با کل سیستم.

2. **پیاده‌سازی رندرهای چندرسانه‌ای درون بوم (`canvas-element.tsx`)**:
   - *اصلاح ریشه‌ای در لایه ۲*:
     - `video_playlist`: نمایش دو بخشی (پخش‌کننده ویدیو + لیست دوره‌ای اپیزودها با زمان‌بندی و استایل المان فعال).
     - `image_comparison`: رندر مقایسه دو تصویر قبل و بعد همراه با برچسب‌های متنی و حاشیه جداکننده.
     - `html_custom`: رندر مستقیم و امن محتوای HTML سفارشی با مدیریت حالت خالی.

3. **کنترل‌های محتوایی تب Content در پنل بازرس (`inspector-panel.tsx`)**:
   - *اصلاح ریشه‌ای در لایه ۳*:
     - لیست پخش: ورودی عنوان دوره، ریپیتر ویدیوها شامل نام، زمان هر قسمت، دکمه افزودن و حذف قسمت‌ها.
     - مقایسه تصویر: نشانی تصویر قبل، تصویر بعد، برچسب قبل و برچسب بعد با تست Nudge آنی در بوم.
     - کد سفارشی: فیلد متنی کد HTML سفارشی با پیش‌نمایش در بوم.

4. **کامپایلر سرور SSR بک‌اند (`ast_compiler.py`)**:
   - *لایه ۴*: پیاده‌سازی شاخه‌های تولید کد HTML تمیز و سئوپسند برای `video_playlist` و `image_comparison` و تایید برابری ۱۰۰٪ بین خروجی بوم و سرور.

---

### ۲. مستندات بصری قبل و بعد (Vision Artifacts)

- **تصاویر قبل از اصلاح**: `.loop/artifacts/builder-gym/round-36/before/`
  - `01-studio-overview.png`: نمای اولیه استودیو در ۱۹۲۰×۱۰۸۰.
  - `02-palette-missing-r36-widgets.png`: نتیجه صفر جستجو برای کد سفارشی و غیبت ویجت‌ها در پالت.

- **تصاویر بعد از اصلاح**: `.loop/artifacts/builder-gym/round-36/after/`
  - `01-studio-overview.png`: نمای کامل ۳ ستونه ۱۹۲۰×۱۰۸۰، درج هر ۳ ویجت لیست پخش ویدیو، اسلایدر مقایسه تصاویر قبل و بعد، و کادر کد سفارشی HTML با رندر بی‌نقص.
  - `02-palette-new-widgets.png`: نمایش کل بلوک‌ها در پالت (۷۴ بلوک استاندارد).
  - `03-canvas-with-new-widgets.png`: رندر جزئیات دقیق مقایسه تصاویر و لیست پخش درون کادر اصلی.

---

### ۳. فایل‌های تغییریافته

1. `frontend/lib/builder/block-registry.ts`: اضافه شدن ۳ ویجت جدید به رجیستری بلوک‌ها.
2. `frontend/components/admin/builder/canvas-element.tsx`: افزودن شاخه‌های رندر ۳ ویجت در `renderWidget()`.
3. `frontend/components/admin/builder/inspector-panel.tsx`: افزودن کنترل‌های محتوایی در `renderContentControls()`.
4. `backend/app/modules/content/application/ast_compiler.py`: پیاده‌سازی شاخه کامپایل سروری ویجت‌های راند ۳۶.
5. `backend/app/tests/unit/test_ast_compiler.py`: تست اختصاصی کامپایلر سرور برای `video_playlist` و `image_comparison`.
6. `frontend/tests/native-widgets.test.ts`: تست انطباق اسکیما و رجیستری برای ۳ ویجت جدید.
7. `frontend/tests/e2e/builder-gym-r36.spec.ts`: تست Playwright شامل فیلتر پالت، درج ویجت‌ها و آزمون Nudge بازرس.
8. `.loop/STATE.json`: به‌روزرسانی متریگ‌ها و وضعیت پورت ۴۰۰۴.

---

### ۴. نتایج نهایی راستی‌آزمایی

- `npx tsc --noEmit`: **۰ خطا** (کامل و سبز)
- `npm test` (Vitest): **۳۷۸ تست سبز در ۴۵ فایل** (`378 passed`)
- `python -m pytest app/tests/unit`: **۶۴۵ تست سبز، ۲ اسکیپ** (`645 passed, 2 skipped`)
- `npx playwright test builder-gym-r36`: **۲ تست سبز در ۱۴.۱ ثانیه**
