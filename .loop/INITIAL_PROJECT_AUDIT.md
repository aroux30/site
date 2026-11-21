# گزارش شناسایی اولیه و ممیزی معماری صفحه‌ساز بصری (.loop/INITIAL_PROJECT_AUDIT.md)

**تاریخ ممیزی**: 2026-11-21  
**شاخه جاری مخزن Git**: `claude/intelligent-bhabha-e2ac6c` (ایزوله در Git Worktree)  
**محیط اجرا**: ویندوز ۱۰ پرو (Node.js v26.1.0, npm 11.13.0, Python 3.14.5)  
**سورس مرجع المنتور**: `C:\Users\Administrator\Desktop\elementor` (شامل `elementor` و `elementor-pro`)  
**پروژه اصلی**: `C:\Users\Administrator\Desktop\site`  
**وضعیت سرور ایزوله**: پورت ۳۳۰۰ (پوسته Webpack با متغیر `NEXT_DIST_DIR=.next-preview-3300` جهت ایزولاسیون کامل از سرورهای هم‌زمان)  

---

## ۱. نقشه ساختار و معماری صفحه‌ساز (Architecture Map)

محیط Visual Page Builder یک سیستم ۳ ستونه مدرن است که بر بستر React 18 / Next.js 15 و پایگاه داده PostgreSQL توسعه داده شده است:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             BuilderToolbar                                  │
│ [عنوان برگه] [ذخیره پیش‌نویس] [انتشار] [استایل سراسری] [قالب برگه] [ویوپورت]    │
├────────────────────┬───────────────────────────────────┬────────────────────┤
│   Left Sidebar     │           Center Canvas           │   Right Sidebar    │
│  (BlocksPalette /  │    (CanvasFrame -> Iframe Sandbox │  (InspectorPanel)  │
│   LayersTree /     │     + CanvasOverlayLayer Portal   │  [Content]         │
│   HistoryPanel)    │     + CanvasElement Tree)         │  [Style]           │
│                    │                                   │  [Advanced]        │
└────────────────────┴───────────────────────────────────┴────────────────────┘
```

### چرخه کامل تبدیل داده (Data & Rendering Lifecycle)
```text
تعامل کاربر در استودیو (Palette / Drag & Drop / Shortcuts / Inspector)
       ↓
استور مرکزی زاستند (useBuilderStore در frontend/stores/builder-store.ts)
       ↓
اعتبارسنجی ساختار درختی انتزاعی (Zod Schema: PageASTSchema در frontend/lib/builder/schema.ts)
       ↓
سریال‌سازی JSON و ذخیره در پایگاه داده (PostgreSQL via cmsPagesAdminApi / Redis Snapshot)
       ↓
کامپایلر سرور بک‌اند (FastAPI / ast_compiler.py / builder_ast.py)
       ↓
رندر امن و استریلیزه (cleanHtml / HTML Sanitizer در استورفرانت)
```

---

## ۲. نقشه وابستگی فایل‌های کلیدی (Dependency Map)

| حوزه | فایل‌های اصلی | مسئولیت فنی |
| :--- | :--- | :--- |
| **Studio Shell** | `frontend/components/admin/builder/builder-studio.tsx` | اسکلت ۳ ستونه، قفل هم‌زمانی ویرایش (`usePageEditingLock`)، مدیریت روتینگ و تب‌ها |
| **Toolbar** | `frontend/components/admin/builder/builder-toolbar.tsx` | نوار ابزار اصلی، ذخیره پیش‌نویس، انتشار، پیش‌نمایش، کلیدهای میانبر، سوییچر ویوپورت |
| **Blocks Palette** | `frontend/components/admin/builder/blocks-palette.tsx` | پالت ۳ زبانه (۳۴ بلوک پایه، ۲۸ الگوی آماده و قالب‌های من)، جستجو، فیلتر دسته‌بندی |
| **Layers Tree** | `frontend/components/admin/builder/layers-tree.tsx` | درخت لایه‌ها (Navigator)، تورفتگی دقیق RTL با عمق ۲۴px، دکمه‌های عملیاتی همیشه روشن، درگ‌انددراپ، فیلتر زنده |
| **Canvas Frame** | `frontend/components/admin/builder/canvas-frame.tsx` | بوم ایزوله Iframe، پورتال رندر React، همگام‌سازی بلادرنگ دارک‌مود و متغیرهای HSL تم |
| **Canvas Element** | `frontend/components/admin/builder/canvas-element.tsx` | رندر زنده تک‌تک ۳۴ ویجت، نوار ابزار شناور المان، لایه اوورلی پس‌زمینه، کادر خط‌چین کانتینر خالی |
| **Overlay Portal** | `frontend/components/admin/builder/canvas-overlay-layer.tsx` | کادرهای انتخاب چندگانه و منوی راست‌کلیک مستقل در پرتال بوم |
| **Inspector Panel** | `frontend/components/admin/builder/inspector-panel.tsx` | پنل تنظیمات ۳ زبانه: محتوا (Content)، استایل (Style: پس‌زمینه، سایه، مرز، فیلتر CSS)، پیشرفته (Advanced: انیمیشن، نمایش شرطی دستگاه، رویت‌پذیری احراز هویت، کامپوننت سراسری) |
| **Presets & Dialogs**| `container-preset-picker.tsx`, `global-styles-dialog.tsx`, `keyboard-shortcuts-dialog.tsx`, `save-page-template-dialog.tsx` | پریست‌های ستونی کانتینر، توکن‌های سراسری، راهنمای میانبرها و ذخیره قالب برگه |
| **State Store** | `frontend/stores/builder-store.ts` | استور مرکزی Zustand: درخت عمیق AST، تاریخچه Undo/Redo تا ۳۰ مرحله، کلیپ‌بورد پایدار، همگام‌سازی کامپوننت‌های سراسری |
| **Block Registry** | `frontend/lib/builder/block-registry.ts` | ثبت رسمی ۳۴ بلوک و ویجت اختصاصی همراه با متدهای `createDefaultElement()` |
| **Backend Compiler**| `backend/app/modules/content/application/ast_compiler.py` | کامپایلر پایتون برای تبدیل درخت AST به خروجی HTML استاندارد منطبق بر تیل‌ویند و استایل‌های بوم |

---

## ۳. ثبت ریسک‌های فنی (Technical Risk Register)

1. **تداخل پورت‌ها در سشن‌های چندگانه (Multi-Session Port Collision)**:
   - *ریسک*: در صورت اجرای چند سشن هم‌زمان، سرور پیش‌فرض پورت ۳۰۰۰ ممکن است توسط سشن دیگری اشغال شده باشد.
   - *کنترل*: فعال‌سازی لانچرهای ایزوله نظیر `:3300` با دایرکتوری بیلد مجزا (`.next-preview-3300`) که از تداخل کش‌های `.next` جلوگیری می‌کند.
2. **قفل شدن فایل‌ها در ویندوز (Windows File Lock on Rebuild)**:
   - *ریسک*: پروسه‌های باز جاوااسکریپت مانع حذف کش و ری‌بیلد تمیز می‌گردند.
   - *کنترل*: اسکریپت `rebuild-and-verify.ps1` و بستن پروسه‌های معلق پورت‌های بلااستفاده پیش از بیلد.
3. **تطابق WYSIWYG میان بوم و خروجی نهایی**:
   - *ریسک*: استایل‌های اعمال‌شده در بوم (مانند پس‌زمینه لایه رویی یا فیلترهای CSS) ممکن است در کامپایلر پایتون منعکس نشوند.
   - *کنترل*: آزمون‌های خودکار اشعه ایکس (`builder-xray.mjs`) که تطابق ۱۰۰٪ خروجی کامپایلر بک‌اند با استایل‌های بوم را می‌سنجد.
4. **محافظت از فایل‌های هسته‌ای**:
   - فایل‌های `backend/app/modules/audit/application/audit_service.py` و مسیرهای مربوط به Showcase طبق قوانین پایه پروژه ایزوله و قفل هستند.
