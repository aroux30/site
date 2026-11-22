# گزارش ممیزی راند ۳۷ — پورت و برابری ۴ لایه ویجت‌های کارت پروفایل و وبلاگ (Link in Bio, Posts Grid)

- **شماره راند**: ۳۷ (Round 37)
- **سطح**: وزنه ۷ و ۸ (پورت المنتور — موج ۲ و ۳)
- **شاخه ایزوله**: `worktree-gym-r41`
- **پورت استودیو**: ۴۰۰۴ (`http://127.0.0.1:4004`)
- **تاریخ اجرا**: 2026-11-22
- **وضعیت کل تست‌ها**: ۳۷۹ تست Vitest فرانت‌اند ۱۰۰٪ سبز | ۶۴۶ تست پایتون بک‌اند ۱۰۰٪ سبز | تست‌های Playwright راند ۳۷ ۱۰۰٪ سبز (۲ از ۲) | کامپایل تایپ‌اسکریپت (`tsc --noEmit`) ۰ خطا

---

### ۱. باگ‌ها و شکاف‌های کشف‌شده در بررسی اولیه و ابزار Vision

1. **فقدان ماژول‌های کارت پروفایل و شبکه مقالات در پالت بلوک‌ها**:
   - *مشاهده در Vision*: در تصویر `before/01-studio-overview.png` و `before/02-palette-missing-r37-widgets.png`، با جستجوی عناوین «لینک بیو» و «گرید مقالات»، صفر نتیجه در پالت یافت می‌شد و این ابزارهای کلیدی المنتور پرو غایب بودند.
   - *اصلاح ریشه‌ای در لایه ۱ (Block Registry)*: ثبت رسمی ۲ ویجت در `frontend/lib/builder/block-registry.ts` با آیکون‌های لوسید متناسب (`Contact2`, `Newspaper`)، دسته‌بندی `basic`، توضیحات فارسی، متدهای `createDefaultElement` و مجموع ۷۶ بلوک رجیسترشده.

2. **رندر ساختارمند بوم ویرایشگر (`canvas-element.tsx`)**:
   - *اصلاح ریشه‌ای در لایه ۲*:
     - `link_in_bio`: کارت مدرن لندینگ بایو با آواتار گرد، نام برند، توضیحات بیو و استک عمودی دکمه‌های لینکدار همراه با نشان (Badge) برجسته.
     - `posts_grid`: گرید واکنش‌گرا (۱ تا ۳ ستونه) با تصاویر بندانگشتی، برچسب‌های رنگی دسته‌بندی، تاریخ، خلاصه متن و دکمه مطالعه مقاله.

3. **کنترل‌های محتوایی تب Content در پنل بازرس (`inspector-panel.tsx`)**:
   - *اصلاح ریشه‌ای در لایه ۳*:
     - لینک بیو: فیلدهای نام، بیو، آدرس آواتار و ریپیتر دکمه‌های لینکدار (عنوان، نشان، پیوند) با تست Nudge موفق.
     - گرید مقالات: انتخابگر تعداد ستون‌ها (۱، ۲، ۳ ستونه) و ویرایشگر زنده عناوین مقالات همراه با به‌روزرسانی آنی بوم.

4. **کامپایلر سرور SSR بک‌اند (`ast_compiler.py`)**:
   - *لایه ۴*: پیاده‌سازی شاخه‌های خروجی HTML سئوپسند و تمیز برای `link_in_bio` و `posts_grid` در پایتون با تست اختصاصی در `test_ast_compiler.py`.

---

### ۲. مستندات بصری قبل و بعد (Vision Artifacts)

- **تصاویر قبل از اصلاح**: `.loop/artifacts/builder-gym/round-37/before/`
  - `01-studio-overview.png`: نمای اولیه استودیو در ۱۹۲۰×۱۰۸۰.
  - `02-palette-missing-r37-widgets.png`: نتیجه صفر در جستجوی «گرید مقالات».

- **تصاویر بعد از اصلاح**: `.loop/artifacts/builder-gym/round-37/after/`
  - `01-studio-overview.png`: نمای ۳ ستونه بی‌نقص در ۱۹۲۰×۱۰۸۰، درج و رندر هر دو ویجت لینک بیو و گرید مقالات با داده‌های تکان‌داده‌شده و بازرس فعال.
  - `02-palette-new-widgets.png`: نمایش کل بلوک‌ها در پالت (۷۶ بلوک استاندارد).
  - `03-canvas-with-new-widgets.png`: رندر جزئیات دقیق کارت پروفایل و شبکه مقالات وبلاگ در بوم.
  - `04-inspector-nudge-active.png`: کنترل‌های بازرس فعال با تست Nudge آنی.

---

### ۳. فایل‌های تغییریافته

1. `frontend/lib/builder/block-registry.ts`: اضافه شدن ۲ ویجت جدید به رجیستری بلوک‌ها.
2. `frontend/components/admin/builder/canvas-element.tsx`: افزودن شاخه‌های رندر ۲ ویجت در `renderWidget()`.
3. `frontend/components/admin/builder/inspector-panel.tsx`: افزودن کنترل‌های محتوایی در `renderContentControls()`.
4. `backend/app/modules/content/application/ast_compiler.py`: پیاده‌سازی شاخه کامپایل سروری ویجت‌های راند ۳۷.
5. `backend/app/tests/unit/test_ast_compiler.py`: تست اختصاصی کامپایلر سرور برای `link_in_bio` و `posts_grid`.
6. `frontend/tests/native-widgets.test.ts`: تست انطباق اسکیما و رجیستری برای ۲ ویجت جدید.
7. `frontend/tests/e2e/builder-gym-r37.spec.ts`: تست Playwright شامل فیلتر پالت، درج ویجت‌ها و آزمون Nudge بازرس.
8. `.loop/STATE.json`: به‌روزرسانی متریگ‌ها و وضعیت پورت ۴۰۰۴.

---

### ۴. نتایج نهایی راستی‌آزمایی

- `npx tsc --noEmit`: **۰ خطا** (کامل و سبز)
- `npm test` (Vitest): **۳۷۹ تست سبز در ۴۵ فایل** (`379 passed`)
- `python -m pytest app/tests/unit`: **۶۴۶ تست سبز، ۲ اسکیپ** (`646 passed, 2 skipped`)
- `npx playwright test builder-gym-r37`: **۲ تست سبز در ۱۱.۳ ثانیه**
