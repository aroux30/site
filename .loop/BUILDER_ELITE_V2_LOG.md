# کارنامه و لاگ اجرایی BUILDER ELITE V2 (.loop/BUILDER_ELITE_V2_LOG.md)

**تاریخ شروع**: 2026-11-21  
**شاخه فعال Git**: `claude/intelligent-bhabha-e2ac6c` (ایزوله در Git Worktree)  
**معماری هدف**: React 19, Next.js 15, Zustand, Tailwind CSS, Python FastAPI, PostgreSQL  
**مرجع محلی المنتور**: `C:\Users\Administrator\Desktop\elementor` (Core + Pro Read-only)

---

## ۱. فاز صفر: احصای ۱۰۰٪ کنترل‌ها و اسکن زنده المنتور (Phase 0)

### ۱. اسکنر استاتیک سیم‌کشی بیلدر (`scripts/loop/builder-wiring-audit.mjs`)
- **خروجی**: `.loop/builder_wiring_gaps.json`
- **تحلیل فایل‌ها**:
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
  - `backend/app/shared/content/html_sanitizer.py`
- **آمار نتایج ۴ گانه**:
  - `HARDCODED_OR_EMPTY_UI`: ۰ مورد (فاقد هندلر خالی یا تله alert/confirm)
  - `UNREAD_IN_CANVAS`: ۶ پروپرتی تخصصی فرم/دکمه در بوم جهت رندرینگ تعاملی
  - `UNCOMPILED_IN_SSR`: ۰ مورد (تمام ۳۵ ویجت و کانتینرها در کامپایلر پایتون پوشش داده شده‌اند)
  - `WIDGET_CONTROL_BLIND_SPOTS`: ۰ مورد (تمامی ۳۵ ویجت دارای هندلرهای اختصاصی در پنل بازرس هستند)

### ۲. ماتریس قطعی ۳۶۰ درجه کنترل‌های بیلدر (`.loop/builder_control_matrix.json`)
- **تعداد کل ردیف‌ها**: ۷۰ ردیف کامل و غیرقابل حذف
- **تفکیک ردیف‌ها**:
  - ۳۵ ویجت پایه، فرم و فروشگاهی (۱۰ پایه + ۱۳ تعاملی/فرم + ۱۲ فروشگاهی)
  - ۲۸ الگوی آماده لندینگ (`pattern-converter.ts`)
  - ۷ کامپوننت هسته استودیو (نوار ابزار، درخت لایه‌ها، پالت، دیالوگ استایل سراسری، دیالوگ‌های قالب و میانبرها)
- **تب‌های تحت پوشش**: `Content`، `Style` و `Advanced` با معیارهای مشخص پذیرش ماشین‌محور

### ۳. فهرست زنده مرجع المنتور و المنتور پرو (`.loop/elementor_parity_backlog.json`)
- **اسکن پوشه‌های واقعی**:
  - `elementor/includes/controls/`
  - `elementor/includes/controls/groups/`
  - `elementor/includes/widgets/`
  - `elementor/includes/widgets/common-base.php`
  - `elementor/assets/shapes/*.svg` (۳۰ فایل برداری)
  - `elementor/core/kits/documents/tabs/` (۱۲ تب تنظیمات سراسری)
  - `elementor-pro/modules/` (۳۴ ماژول و ابزار حرفه‌ای)
- **موج‌های سه‌گانه بک‌لاگ**:
  - موج ۱: گروه‌های کنترل حرفه‌ای، کانتینر Grid، اشکال جداکننده و نویگیتور (۸ مدخل)
  - موج ۲: ویجت‌های کلیدی مفقود Core و Pro (۷ مدخل)
  - موج ۳: کیت سراسری سایت، تم بیلدر، لوپ بیلدر و فرم چندمرحله‌ای (۴ مدخل)

### ۴. پروتکل پروب ۵-سیگنالی (`scripts/loop/builder-5signal-probe.mjs`)
- پیاده‌سازی آزمون ۵ سیگنالی:
  - `S1 (State)`: فعال‌سازی `isDirty` و تغییرات استیت در Zustand
  - `S2 (DOM)`: ثبت تغییرات در آی‌فریم `CanvasFrame`
  - `S3 (ComputedStyle)`: محاسبه مقادیر دقیق CSS در بوم
  - `S4 (Visual Pixels)`: ذخیره تصاویر قبل و بعد و ارزیابی تغییرات بصری
  - `S5 (Persistence + SSR Parity)`: ذخیره پیش‌نویس، ریلود صفحه و بررسی یکسانی ساختار با خروجی عمومی SSR

---

## ۲. نتایج گیت‌های کیفی و تست‌ها
- **تایپ‌اسکریپت**: `npm --prefix frontend run type-check` -> ۰ خطا (کاملاً تمیز)
- **تست‌های واحد فرانت‌اند**: `npm --prefix frontend run test` -> ۳۷۲ تست سبز در ۴۵ فایل
- **تست‌های واحد بک‌اند**: `cd backend && python -m pytest app/tests/unit` -> ۶۲۲ تست سبز، ۲ اسکیپ

---

## ۳. ثبت کامیت
- کامیت اتمیک ۱: `chore(builder-v2-init): index builder controls and elementor reference`

---

## ۴. اجرای موفق مسیر A: وزنه‌های ۱ و ۲ (پاک‌سازی عمیق و پروب ۵-سیگنالی ۳۵ ویجت)

### ۱. اصلاح ریشه‌ای گپ‌های سیم‌کشی بوم (`canvas-element.tsx`)
- اصلاح و اتصال مشخصه‌های `newTab` در دکمه‌ها (`target="_blank" rel="noopener noreferrer"`).
- اتصال اتریبیوت `required` و برچسب ستاره سرخ الزامی در فیلدهای فرم (`form_input`, `form_textarea`, `form_select`).
- بازتاب صریح متادیتا و آدرس‌های `checkout_url`، `submit_url`، `success_message` و `error_message` در المان‌های فرم و سبد خرید.
- صفر شدن کامل شکاف‌های سیم‌کشی:
  - `HARDCODED_OR_EMPTY_UI`: ۰
  - `UNREAD_IN_CANVAS`: ۰
  - `UNCOMPILED_IN_SSR`: ۰
  - `WIDGET_CONTROL_BLIND_SPOTS`: ۰
  - **مجموع**: ۰ گپ

### ۲. اجرای پروب ۵-سیگنالی برای ۳۵ ویجت (۷ دسته ۵ تایی)
- **دسته ۱ (کانتینرها و تایپوگرافی)**: `container`, `section`, `columns`, `heading`, `text_editor` -> ۵ از ۵ پاس (۱۰۰٪)
- **دسته ۲ (المان‌های پایه)**: `text`, `image`, `button`, `spacer`, `divider` -> ۵ از ۵ پاس (۱۰۰٪)
- **دسته ۳ (فرم و جدول)**: `table`, `form_container`, `form_input`, `form_textarea`, `form_select` -> ۵ از ۵ پاس (۱۰۰٪)
- **دسته ۴ (کنترل‌های فرم و پنل‌ها)**: `form_checkbox`, `form_radio`, `accordion`, `tabs`, `countdown` -> ۵ از ۵ پاس (۱۰۰٪)
- **دسته ۵ (رسانه و کارت‌ها)**: `video`, `icon_box`, `social_links`, `product_card`, `product_grid` -> ۵ از ۵ پاس (۱۰۰٪)
- **دسته ۶ (کاتالوگ فروشگاهی)**: `image_gallery`, `star_rating`, `review_histogram`, `recently_viewed`, `mega_menu` -> ۵ از ۵ پاس (۱۰۰٪)
- **دسته ۷ (تجارت الکترونیک و سبد)**: `product_price`, `product_variants`, `add_to_cart`, `mini_cart`, `cart_summary` -> ۵ از ۵ پاس (۱۰۰٪)
- **نتیجه کلی وزنه‌های ۱ و ۲**: ۳۵ از ۳۵ ویجت در تمامی ۵ سیگنال (S1 تا S5) تایید شدند.

