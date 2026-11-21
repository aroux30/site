# ممیزی شناسایی اولیه پروژه (Stage 0: Reconnaissance & Initial Audit)

**تاریخ ممیزی**: ۲۱ نوامبر ۲۰۲۶ (2026-11-21)  
**محیط اجرا**: ویندوز ۱۰ پرو (Windows 10 Pro 10.0.19045)  
**شاخه گیت فعال**: `claude/goofy-bohr-48c74a` در ورک‌تری ایزوله `C:\Users\Administrator\Desktop\site\.claude\worktrees\goofy-bohr-48c74a`  
**مخزن مرجع المنتور**: `C:\Users\Administrator\Desktop\elementor` (شامل دو پکیج کامل `elementor` و `elementor-pro`)  

---

## ۱. ساختار پروژه و وضعیت گیت (Git & Working Tree Status)
- **وضعیت شاخه**: تمیز (Working tree clean) بدون هیچ تغییر کامیت‌نشده ناخواسته.
- **شاخه اصلی**: `main`
- **کامیت‌های اخیر**:
  - `b849aff` Merge branch 'claude/hungry-ardinghelli-71d423'
  - `c98e045` merge: resolve conflicts between main and excavator branch, unifying Elementor parity features
  - `101eb63` Merge branch 'main' of https://github.com/aroux30/site into claude/nice-roentgen-94fdac
  - `bf822d0` fix(excavator-r11): implement toolbar direct page title inline editing and Ctrl+D / Ctrl+Shift+V shortcuts
  - `c41a746` fix(excavator-r18): implement Elementor CSS filters controls and server compiler parity
- **وضعیت سشن‌ها و ورک‌تری‌ها**:
  - سشن‌های فعال موازی در ورک‌تری‌های اختصاصی خود در حال اجرا هستند. پورت‌های ۳۱۰۰ و ۳۲۰۰ توسط سشن‌های دیگر استفاده می‌شوند.
  - پورت ۳۰۰۰ به صورت مستقل با بیلد پروداکشن Next.js استاندارد (`next start -p 3000`) بالا آمده و اندپوینت `/api/health` سلامت کامل سرور و اتصال بک‌اند (HTTP 200) را با شناسه بیلد معتبر گزارش می‌کند.

---

## ۲. پشته فناوری و ابزارهای پروژه (Tech Stack & Tooling)
- **فرانت‌اند**: Next.js 15.5.25 (App Router)، React 18، TypeScript 5، Tailwind CSS، Radix UI، Lucide React، Zustand (`builder-store.ts`)
- **بک‌اند**: FastAPI / Python 3.14، SQLAlchemy (Async)، PostgreSQL 16 در Docker، Redis در Docker، Pydantic v2
- **تست‌ها**:
  - فرانت‌اند یونیت/کامپوننت: Vitest v5.0.1 (۳۷۲ تست سبز در ۴۵ فایل)
  - تایپ‌چک فرانت‌اند: `npx tsc --noEmit` (۰ خطا)
  - تست‌های ای۲ای/مرورگر: Playwright v1.48+، Axe Core Playwright (WCAG 2.1 AA)
  - بک‌اند: Pytest v9.1.1 (۶۲۲ تست سبز، ۲ اسکیپ)

---

## ۳. معماری Visual Page Builder پروژه
صفحه‌ساز بصری اختصاصی بر مبنای چرخه داده‌ای زیر پیاده‌سازی شده است:

```
ورودی کاربر (Drag & Drop / Inspector / Palette / Shortcuts)
       ↓
Builder Store (Zustand: builder-store.ts با مدیریت History past/future و پایش تغییرات)
       ↓
Page AST (درخت استاندارد JSON شامل rootElements, globalStyles, schemaVersion)
       ↓
Zod AST Validation (اعتبارسنجی فرانت‌اند با PageASTSchema)
       ↓
CanvasFrame (Iframe ایزوله برای ارزیابی صادقانه کوئری‌های مدیا و تزریق دو لایه توکن تم)
       ↓
CanvasOverlayLayer (لایه پرتال مستقل روی Iframe برای ترسیم کادرهای هاور، سلکشن و نوار ابزار شناور)
       ↓
Backend API (/api/v1/content/admin/pages/)
       ↓
PostgreSQL & Redis (ذخیره پیش‌نویس و اسنپ‌شات‌های بازیابی آنی کرش)
       ↓
AST Compiler (ast_compiler.py در بک‌اند برای کامپایل سروری به HTML امن و استاندارد)
       ↓
Storefront Renderer (رندر تمام‌عرض صفحات CMS با dangerouslySetInnerHTML و cleanHtml)
```

---

## ۴. اجزای کلیدی صفحه‌ساز
۱. **BuilderStudio (`frontend/components/admin/builder/builder-studio.tsx`)**:
   - محیط تمام‌صفحه با لایه‌بندی ۳ ستونه (پالت و درخت لایه‌ها در سمت راست، بوم آی‌فریم در مرکز، پنل بازرس در سمت چپ در RTL).
   - نوار ابزار بالا با سوییچ ۳ ویوپورت (دسکتاپ، تبلت ۷۶۸px، موبایل ۳۷۵px)، دکمه‌های بازگشت/انجام مجدد (Undo/Redo)، استایل سراسری، کلیدهای میانبر، پیش‌نمایش و دکمه‌های ذخیره پیش‌نویس و انتشار.

۲. **CanvasFrame & CanvasOverlayLayer (`canvas-frame.tsx`, `canvas-overlay-layer.tsx`)**:
   - سند داخلی آی‌فریم با استایل‌های پایه سایت و تزریق ۲ لایه توکن‌های طراحی (لایه ۱ تم فعال سایت + لایه ۲ استایل‌های سراسری برگه).
   - رندر عناصر داخل آی‌فریم با درک ریسپانسیو واقعی.
   - لایه پرتال شناور مستقل در ریشه آی‌فریم بدون ایجاد شکست در رندر فلکس/گرید فرزندان.

۳. **BlocksPalette (`blocks-palette.tsx`)**:
   - ۳ زبانه: بلوک‌های پایه (۳۴ بلوک)، الگوهای آماده (۲۸ الگوی کامل)، قالب‌های ذخیره‌شده من (قالب‌های برگه و کانتینر).
   - فیلتر و جستجوی بلادرنگ.

۴. **LayersTree (`layers-tree.tsx`)**:
   - درخت کامل سلسله‌مراتبی المان‌ها با تورفتگی RTL به ازای هر عمق (`depth * 24px`) و خط راهنمای عمودی.
   - دکمه‌های عملیاتی دائمی و بدون مخفی‌سازی (`opacity-80 hover:opacity-100`) برای مخفی‌سازی، تکثیر و حذف (`text-destructive`).
   - درگ‌انددراپ ردیف‌های درختی، جستجوی زنده در لایه‌ها، دکمه‌های باز و بسته کردن سراسری، و دابل‌کلیک برای تغییر نام درجا.

۵. **InspectorPanel (`inspector-panel.tsx`)**:
   - ۳ تب مجزا: محتوا (Content)، استایل (Style)، و پیشرفته (Advanced).
   - کنترل‌های غنی برای تایپوگرافی، پس‌زمینه (رنگ، گرادیانت، تصویر)، فیلترهای گرافیکی CSS، لایه رویی پس‌زمینه (Background Overlay)، سایه‌ها، کادر، انیمیشن‌ها، و نمایش شرطی بر اساس دستگاه و وضعیت احراز هویت.

۶. **Block Registry & Pattern Converter (`block-registry.ts`, `pattern-converter.ts`)**:
   - ثبت ۳۴ بلوک و ویجت واقعی فرانت‌اند.
   - تبدیل عمیق ۲۸ الگوی آماده به نودهای استاندارد AST بدون نشت تگ‌های خام HTML.

---

## ۵. ارزیابی اولیه نواقص P0 و قوانین حفاظتی
- **دکمه‌های LayersTree**: کلاس `opacity-0` به طور کامل حذف شده و تمامی دکمه‌ها با ماوس در مختصات (0, 0) قابل مشاهده و تعامل هستند.
- **تورفتگی لایه‌ها**: تورفتگی راست به صورت دقیق `depth * 24px` با خط راهنمای عمودی `border-r-2 border-primary/40` تثبیت شده است.
- **Empty Container Guide**: کادر خط‌چین با حداقل ارتفاع `80px` و دکمه راهنمای مشخص «افزودن بلوک به این بخش» برقرار است.
- **ایزولاسیون کامل `audit_service.py` و `showcase`**: هیچ تغییری در این فایل‌ها داده نمی‌شود.
- **ایزولاسیون تست‌ها**: تمام تست‌های خودکار روی برگه ایزوله `/e2e-isolated-scratchpad?builder=1` اجرا می‌شوند و صفحات عمومی فروشگاه دستکاری نمی‌شوند.
