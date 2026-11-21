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
- کامیت اتمیک: `chore(builder-v2-init): index builder controls and elementor reference`
