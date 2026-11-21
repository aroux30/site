# کارنامه مهندسی سیستم صفحه‌ساز بصری حرفه‌ای (BUILDER ELITE V2 LOG)

**تاریخ شروع فاز**: ۲۱ نوامبر ۲۰۲۶  
**شاخه Git**: `claude/inspiring-curie-e15fb1` (در محیط ایزوله Git Worktree)  
**مرجع مقایسه**: `C:\Users\Administrator\Desktop\elementor` (شامل هسته المنتور و المنتور پرو)

---

## فاز صفر: احصای ۱۰۰٪ کنترل‌های فعلی + اسکن زنده سورس المنتور

### ۱. اسکنر استاتیک سیم‌کشی بیلدر (`scripts/loop/builder-wiring-audit.mjs`)
- تحلیل کامل ۱۰ فایل مرجع فرانت‌اند و بک‌اند:
  - `frontend/components/admin/builder/inspector-panel.tsx`
  - `frontend/components/admin/builder/builder-toolbar.tsx`
  - `frontend/components/admin/builder/layers-tree.tsx`
  - `frontend/components/admin/builder/blocks-palette.tsx`
  - `frontend/stores/builder-store.ts`
  - `frontend/components/admin/builder/canvas-element.tsx`
  - `frontend/types/builder.ts`
  - `frontend/lib/builder/block-registry.ts`
  - `backend/app/modules/content/domain/builder_ast.py`
  - `backend/app/modules/content/application/ast_compiler.py`
- نتایج ذخیره‌شده در `.loop/builder_wiring_gaps.json`:
  - **HARDCODED_OR_EMPTY_UI**: ۰ خطا (هیچ هندلر خالی یا `alert/confirm` نیتیو یافت نشد).
  - **UNREAD_IN_CANVAS**: ۶ کلید نیازمند غنی‌سازی (شامل اتصال کامل کنترل‌های Shape Divider و برخی تنظیمات لایه رویی).
  - **UNCOMPILED_IN_SSR**: ۴ مورد (ثبت جزئیات رندر سروری شکل جداکننده).
  - **WIDGET_CONTROL_BLIND_SPOTS**: ۰ خطا (تمام ۳۵ ویجت دارای پنل تنظیمات مشخص هستند).

---

### ۲. ماتریس قطعی ۳۶۰ درجه کنترل‌های بیلدر (`.loop/builder_control_matrix.json`)
- ثبت تک‌تک ۶۹ ردیف عملیاتی شامل:
  - **۳۵ ویجت بومی**:
    - ۱۰ پایه (`container, section, columns, heading, paragraph, text, image, button, spacer, divider`)
    - ۱۳ تعاملی و فرم (`table, form_container, form_input, form_textarea, form_select, form_checkbox, form_radio, accordion, tabs, countdown, video, icon_box, social_links`)
    - ۱۲ فروشگاهی (`product_card, product_grid, image_gallery, star_rating, review_histogram, recently_viewed, mega_menu, product_price, product_variants, add_to_cart, mini_cart, cart_summary`)
  - **۲۸ الگوی آماده بلاک** با ردیابی تب‌های Content, Style, Advanced
  - **۶ سطح و دیالوگ استودیو**: نوار ابزار، درخت لایه‌ها، لایه شناور اوورلی، استایل‌های سراسری، ذخیره قالب سکشن، ذخیره قالب برگه

---

### ۳. فهرست زنده مرجع المنتور و المنتور پرو (`.loop/elementor_parity_backlog.json`)
- اسکن بازگشتی مسیر `C:\Users\Administrator\Desktop\elementor`:
  - ۶۰ فایل کنترل پایه در `elementor/includes/controls/`
  - ۱۲ فایل گروه کنترل در `elementor/includes/controls/groups/`
  - ۳۶ فایل ویجت در `elementor/includes/widgets/`
  - ۲۹ فایل SVG تقسیم‌کننده در `elementor/assets/shapes/`
  - ۱۳ فایل تنظیمات کیت سراسری در `elementor/core/kits/documents/tabs/`
  - ۵۸۹ فایل ماژول و کامپوننت حرفه‌ای در `elementor-pro/modules/`
- تعریف ۱۶ مدخل استاندارد تسک در ۳ موج توسعه:
  - **موج ۱ (۷ مورد)**: تایپوگرافی کامل، پس‌زمینه و اوورلی پیشرفته، کادر و سایه هاور، ترانسفورم سه‌بعدی و انیمیشن، ۲۹ شکل جداکننده SVG، کانتینر CSS Grid، ناویگیتور پیشرفته.
  - **موج ۲ (۵ مورد)**: ویجت‌های Counter, Progress Bar, Testimonial Carousel, Table of Contents, Popup Builder & Off-Canvas.
  - **موج ۳ (۴ مورد)**: تنظیمات ۱۲ تب Site Kit، Theme Builder، Loop Builder، و فرم چندمرحله‌ای.

---

### ۴. پروتکل پروب ۵-سیگنالی (`scripts/loop/builder-5signal-probe.mjs`)
- سنجش آزمایشی موفق روی بوم و استودیو:
  - **S1 (State)**: بررسی تغییر و فعال‌سازی `isDirty`.
  - **S2 (DOM)**: ثبت تغییرات توسط ناظر دُم درون بوم Iframe.
  - **S3 (ComputedStyle)**: اعتبارسنجی تغییر مقادیر محاسباتی استایل المان هدف.
  - **S4 (Pixel Diff)**: ثبت تصاویر `before/` و `after/` و مقایسه تفاوت بصری در `.loop/artifacts/builder-v2/round-01/`.
  - **S5 (Persistence & SSR Parity)**: تایید عدم پس‌روی در ذخیره‌سازی و پایداری لایه‌ها.
- **حکم نهایی**: `PASS` (گزارش در `.loop/artifacts/builder-v2/round-01/5signal-probe-report.json`).

---

### ۵. نتایج دروازه‌های کیفیت و آزمون‌های رگرسیون
- **TypeScript**: `0 errors` (پاس کامل `npx tsc --noEmit`)
- **Vitest**: ۳۷۲ تست سبز در ۴۵ فایل تست (`372 passed`)
- **Pytest**: ۶۲۲ تست سبز، ۲ تست صرف‌نظرشده در بک‌اند (`622 passed, 2 skipped`)
- **Playwright E2E**: ۶ تست سبز در راندهای ۱ و ۲ (`6 passed`)
- **Deterministic Audit**: ۱۰۰٪ پاس و صفر خطای WCAG 2.1 AA
