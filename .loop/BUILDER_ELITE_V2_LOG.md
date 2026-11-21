# دفترچه ثبت و کارنامه جامع مهندسی صفحه‌ساز بصری (.loop/BUILDER_ELITE_V2_LOG.md)

## ۱. اطلاعات چرخه و شاخه
- **مأموریت**: پورت کامل، ممیزی و ارتقای ۳۶۰ درجه صفحه‌ساز بصری بر پایه معماری مدرن المنتور و المنتور پرو (BUILDER ELITE V2).
- **شاخه گیت فعال**: `claude/goofy-bohr-48c74a`
- **تاریخ شروع فاز صفر**: ۲۱ نوامبر ۲۰۲۶ (2026-11-21)
- **وضعیت راند صفر و ۱**: ✅ ۱۰۰٪ کامل و مستند

---

## ۲. مدارک و ساختارهای ایجادشده در فاز صفر (Phase 0 Deliverables)
1. **اسکریپت اسکنر سیم‌کشی استاتیک بیلدر ([scripts/loop/builder-wiring-audit.mjs](scripts/loop/builder-wiring-audit.mjs))**:
   - تحلیل عمیق کدهای فرانت‌اند (`inspector-panel.tsx`, `builder-toolbar.tsx`, `layers-tree.tsx`, `blocks-palette.tsx`, `builder-store.ts`, `canvas-element.tsx`, `types/builder.ts`) و بک‌اند پایتون (`builder_ast.py`, `ast_compiler.py`).
   - خروجی قطعی ذخیره‌شده در **[.loop/builder_wiring_gaps.json](.loop/builder_wiring_gaps.json)** با پوشش دسته‌های ۴ گانه:
     - `HARDCODED_OR_EMPTY_UI`: ۰ مورد (فاقد هندلر خالی یا آلرت بومی)
     - `UNREAD_IN_CANVAS`: ۰ مورد
     - `UNCOMPILED_IN_SSR`: ۲ مورد شناسایی‌شده (`backdropBlur` و `filterBlur`) برای اصلاح در کامپایلر پایتون
     - `WIDGET_CONTROL_BLIND_SPOTS`: ۰ مورد (تمام ۳۵ ویجت دارای هندلرهای متناظر در بازرس هستند)

2. **ماتریس قطعی ۳۶۰ درجه کنترل‌های بیلدر ([.loop/builder_control_matrix.json](.loop/builder_control_matrix.json))**:
   - ثبت ساختار کامل ۳۵ ویجت پایه، فرم و فروشگاهی.
   - ثبت ساختار ۲۸ الگوی آماده سکشن و لندینگ پیج.
   - ثبت ۶ سطح محیط استودیو (نوار ابزار، درخت لایه‌ها، دیالوگ‌های سراسری، ذخیره قالب و میانبرها).
   - تعریف وضعیت تک‌تک تب‌های `content`، `style` و `advanced` با سنجش‌های ۵ سیگنالی (`state`, `dom`, `style`, `pixels`, `ssr`).

3. **فهرست زنده مرجع المنتور و المنتور پرو ([.loop/elementor_parity_backlog.json](.loop/elementor_parity_backlog.json))**:
   - اسکن کامل و بازگشتی مخزن محلی مرجع `C:\Users\Administrator\Desktop\elementor`.
   - استخراج و ثبت ۱۵۱ قابلیت و مدخل مشخص در قالب امواج سه‌گانه:
     - **موج ۱ (Wave 1)**: گروه‌های کنترل حرفه‌ای (`control_group`)، کانتینر شبکه (`grid-container`)، جداکننده‌های شکلی SVG (`shape_divider`) و ارتقای درخت لایه‌ها (`navigator`).
     - **موج ۲ (Wave 2)**: ویجت‌های هسته و حرفه‌ای المنتور (`widget_core` و `pro_module`) شامل پاپ‌آپ، مگامنو، کشو، نقاط تعاملی، اسلایدرها و آکاردئون‌های تودرتو.
     - **موج ۳ (Wave 3)**: سایت‌کیت سراسری، تم‌بیلدر و لوپ‌بیلدر (`site_kit`, `theme_builder`, `loop_builder`).

4. **اسکریپت پروب ۵-سیگنالی سنجش علّی ([scripts/loop/builder-5signal-probe.mjs](scripts/loop/builder-5signal-probe.mjs))**:
   - اجرای آزمون جهش فعال روی المان و کنترل‌های بازرس.
   - اندازه‌گیری و راستی‌آزمایی هر ۵ سیگنال قطعی (`S1: State`, `S2: DOM`, `S3: ComputedStyle`, `S4: Pixel Diff`, `S5: Persistence + SSR Parity`).
   - ثبت تصاویر مقایسه‌ای در `.loop/artifacts/builder-v2/round-01/before/`, `after/` و `diff/`.
   - آزمون ویجت نمونه `heading` با موفقیت کامل و پاس ۱۰۰٪ هر ۵ سیگنال اجرا شد.

---

## ۳. نتایج ممیزی و تاییدیه‌های کیفی (Quality Gates)
- **TypeScript Typecheck**: `./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json` با **۰ خطا**.
- **Vitest Unit Suite**: **۳۷۲ تست سبز در ۴۵ فایل** (`372 passed`).
- **Pytest Unit Suite**: **۶۲۲ تست سبز، ۲ اسکیپ** (`622 passed, 2 skipped`).
- **Playwright Gym R01**: **۳ تست سبز** (`3 passed in 10.6s`).
- **Deterministic Audit**: **پاس ۱۰۰٪ هر ۷ چک** با ثبت گزارش و تصاویر Set-of-Mark.

---

## ۴. برنامه راند بعدی (Next Round Focus - Wave 1 / Weight 1 & 2)
- بستن ۲ شکاف شناسایی‌شده در `ast_compiler.py` (`backdropBlur` و `filterBlur`).
- اجرای دسته‌بندی‌شده پروب ۵-سیگنالی روی ۵ ویجت اول پایه (`container`, `section`, `columns`, `heading`, `text_editor`).
- آغاز پیاده‌سازی جداکننده‌های شکلی (Shape Dividers) بر مبنای SVGهای مرجع المنتور در کانتینرها.
