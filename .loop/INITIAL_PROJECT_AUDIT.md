# ممیزی شناسایی اولیه پروژه (Reconnaissance Audit)
**تاریخ ممیزی**: ۲۱ نوامبر ۲۰۲۶  
**شاخه Git**: `claude/inspiring-curie-e15fb1` (در محیط ایزوله Git Worktree)  
**مسیر پروژه اصلی**: `C:\Users\Administrator\Desktop\site`  
**مسیر سورس مرجع المنتور**: `C:\Users\Administrator\Desktop\elementor` (شامل `elementor` و `elementor-pro`)  

---

## ۱. وضعیت زیرساخت و سیستم اجرایی
- **سیستم‌عامل**: Windows 10 Pro (x64)
- **دیتابیس و سرویس‌ها**: Docker Desktop (PostgreSQL 16, Redis 7, Elasticsearch 8.15.0 فعال و سالم)
- **فرانت‌اند**: Next.js 15.5.25 (React 18, Tailwind CSS, Lucide Icons, Radix UI, Zustand 4.5.5)
- **بک‌اند**: FastAPI, Python 3.12, SQLAlchemy (Async), Uvicorn, Celery
- **محیط تست**: Vitest (Unit), Pytest (Backend Unit), Playwright Chromium (E2E & Accessibility)

---

## ۲. وضعیت سلامت ابزارها و تست‌های موجود
1. **تایپ‌چک فرانت‌اند**:
   - دستور: `npx tsc --noEmit`
   - نتیجه: **۰ خطا (کامپایل کامل و موفق)**
2. **تست‌های واحد فرانت‌اند**:
   - دستور: `npx vitest run`
   - نتیجه: **۳۷۲ تست سبز در ۴۵ فایل تست (`372 passed`)**
3. **تست‌های واحد بک‌اند**:
   - دستور: `python -m pytest app/tests/unit`
   - نتیجه: **۶۲۲ تست سبز، ۲ تست صرف‌نظرشده (`622 passed, 2 skipped`)**
4. **تست‌های رگرسیون پیش‌رونده Visual Builder (راند ۱ تا ۲۰)**:
   - دستور: `npx playwright test tests/e2e/builder-gym-r*.spec.ts --workers=1`
   - نتیجه: **۶۰ تست سبز از ۶۰ تست (`60 passed in 3.2m`)**
5. **ممیزی دترمینیستیک هسته استودیو**:
   - اسکریپت: `node .loop/audits/deterministic-audit.mjs`
   - نتیجه: **۱۰۰٪ سبز (`passed: true`)** شامل:
     - تطابق HSL Channels (بدون کاما)
     - استاندارد WCAG 2.1 AA (صفر خطا در اسکن AxeBuilder)
     - رویت‌پذیری دائمی کلیدهای عملیاتی درخت لایه‌ها
     - تورفتگی RTL به ازای هر عمق (`depth * 24px`)
     - ارتفاع و راهنمای کانتینر خالی (`min-h-[80px]`)
     - موقعیت نوار ابزار شناور المان در بوم بدون بریدگی در سقف
     - بررسی خطاهای هیدریشن ری‌اکت (۰ خطای هیدریشن)

---

## ۳. نقشه معماری صفحه‌ساز (Visual Page Builder Architecture Map)

### ۳.۱. لایه Frontend & Store
- **فریم بوم (Canvas Frame)**: `frontend/components/admin/builder/canvas-frame.tsx`
  - رندر ایزوله با `createPortal` در آی‌فریم اختصاصی
  - تزریق دو لایه توکن‌های طراحی (تم سراسری + توکن‌های سفارشی برگه)
  - فوروارد رویدادهای کیبورد (Ctrl+Z, Ctrl+Y, Ctrl+C, Ctrl+V, Delete, Alt+Arrows, Escape) به پنجره والد
- **لایه مستقل اوورلی (Independent Selection & Action Overlay)**: `frontend/components/admin/builder/canvas-overlay-layer.tsx`
  - ترسیم کادرهای شناور انتخاب تکی و چندگانه بدون تاثیر از `overflow: hidden` المان‌های والد
  - نوار ابزار شناور هوشمند با فلیپ عمودی خودکار در نزدیکی سقف بوم
- **مدیریت استیت (Zustand Store)**: `frontend/stores/builder-store.ts`
  - درخت AST کامل صفحه با تفکیک `rootElements`
  - مدیریت تاریخچه Undo/Redo (`history.past` و `history.future`)
  - کلیپ‌بورد درونی و localStorage پایدار
  - همگام‌سازی بلادرنگ کامپوننت‌های سراسری (`globalComponentId`)
- **پالت بلوک‌ها و الگوها (Palette)**: `frontend/components/admin/builder/blocks-palette.tsx`
  - ۳۴ بلوک پایه بومی ثبت‌شده در `BASIC_BLOCK_DEFINITIONS`
  - ۲۸ الگوی آماده ثبت‌شده در بک‌اند با پشتیبانی از درگ و کلیک فوری
  - زبانه قالب‌های ذخیره‌شده (Page & Section Templates)
- **درخت ساختار لایه‌ها (Navigator / Layers Tree)**: `frontend/components/admin/builder/layers-tree.tsx`
  - درگ‌انددراپ بومی برای جابه‌جایی المان‌ها و کانتینرها
  - جستجو و فیلتر زنده لایه‌ها و کنترل باز/بسته کردن سراسری
  - رویت‌پذیری دائمی کلیدهای حذف، تکثیر و مخفی‌سازی بدون نیاز به هاور
- **پنل بازرس (Inspector Panel)**: `frontend/components/admin/builder/inspector-panel.tsx`
  - تب محتوا (Content): فرم‌های اختصاصی محتوایی برای تمام ۳۴ ویجت
  - تب استایل (Style): ابعاد و توکن‌های ریسپانسیو، فاصله‌گذاری، پس‌زمینه (رنگ/گرادیانت/عکس)، کادر و گوشه‌ها، سایه، فیلترهای گرافیکی CSS، و لایه رویی پس‌زمینه (Background Overlay)
  - تب پیشرفته (Advanced): انیمیشن‌ها، نمایش شرطی دستگاهی (Desktop/Tablet/Mobile)، نمایش شرطی احراز هویت، و شناسه/کلاس‌های سفارشی CSS

### ۳.۲. لایه Backend & Compiler
- **اسکیمای اعتبارسنجی AST**: `backend/app/modules/content/domain/builder_ast.py` و `builder_validation.py`
- **کامپایلر استاتیک**: `backend/app/modules/content/application/ast_compiler.py`
  - کامپایل بدون افت AST به HTML بهینه‌شده سئو
  - پشتیبانی از تمام ویجت‌ها، استایل‌های دستگاهی، هایلایت جداول، فیلترهای CSS، شمارنده زمان و لایه رویی پس‌زمینه
- **مخزن الگوها**: `backend/app/modules/content/domain/block_patterns.py` (۲۸ الگوی آماده شرکتی و فروشگاهی)
