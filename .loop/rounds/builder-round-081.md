# گزارش تحلیلی، ممیزی سنسورها و مستندات راند ۸۱ (Weight 3 — Global Styles SSR Injection & Clean Theme Reset)

- **شماره راند**: ۸۱ (Progressive Overload Round 81 — Weight 3 Global Styles SSR Injection & Canvas Reset)
- **وزنه تمرینی**: وزنه ۳ (۲۵ کیلو: استایل‌های سراسری، توکن‌های طراحی، تزریق به ریشه و برابری بوم با SSR)
- **پورت اختصاصی فرانت‌اند**: ۳۰۰۰ (`http://127.0.0.1:3000`)
- **تاریخ اجرا**: ۲۰۲۶-۱۱-۲۶
- **شاخه کاری ایزوله**: `claude/optimistic-gates-09b249`
- **وضعیت کل تست‌ها**:
  - کامپایل تایپ‌اسکریپت (`tsc --noEmit`): ۰ خطا (۱۰۰٪ سبز)
  - آزمون‌های واحد فرانت‌اند (`vitest run`): ۶۷ فایل، ۴۳۸ تست سبز کامل (`438 passed`)
  - آزمون‌های واحد بک‌اند پایتون (`pytest app/tests/unit`): ۶۵۹ تست سبز و ۲ تست نادیده‌گرفته‌شده مجاز (`659 passed, 2 skipped`)
  - سنسورهای کالیبره‌شده: ۱۰۰٪ پاس روی فیکسچرهای RED/GREEN
- **حکم ناظر کیفی مستقل (`qa-verifier`)**: `APPROVE`
- **مهر مسترینگ نهایی**: **BUILDER_GYM_ALL_LEVELS_MASTERED**

---

## ۱. خلاصه‌ی اصلاحات مهندسی راند ۸۱

1. **تزریق استایل سراسری برگه به ریشه سند در کامپایلر بک‌اند (`DEFECT-W3-02`)**:
   - در `ast_compiler.py`، هنگام کامپایل سند به HTML، ویژگی‌های استایل سراسری (`backgroundColor`، `textColor`، `fontFamily`، `borderRadius`) نادیده گرفته می‌شدند و تگ ریشه `.builder-document` استایل‌های اعمال‌شده در استودیو را در خروجی SSR منعکس نمی‌کرد.
   - با خواندن دیکشنری `ast.global_styles` و تزریق امن خصوصیات مجاز CSS (`background-color`، `color`، `font-family`، `border-radius`)، تطابق ۱۰۰٪ بین محیط بوم و خروجی عمومی SSR برقرار گردید.
2. **پاکسازی دقیق متغیرهای CSS در بازنشانی تم آی‌فریم (`DEFECT-W3-03`)**:
   - در `canvas-frame.tsx`، متغیرهای سفارشی `--theme-primary`، `--primary-hex`، `--radius` و متغیرهای رنگ زمینه و متن در صورت حذف یا بازنشانی استایل‌های سراسری از روی ریشه داکیومنت آی‌فریم پاک نمی‌شدند. با افزودن شاخه `else` و فراخوانی `removeProperty`، بازنشانی به تم سایت به صورت کاملاً تمیز و بی‌نقص انجام می‌شود.
3. **آزمون واحد رگرسیون بک‌اند و قفل قراردادی**:
   - آزمون `test_ast_compiler_applies_global_styles_to_root_document` در پایتون با موفقیت اضافه شد.
   - تگ قراردادی `@unit:global_styles @col:ssr_injection` در `controls.contract.spec.ts` ثبت گردید.

---

## ۲. خلاصه ۴ سنسور قطعی زمان اجرا (Round 81)

| سنسور | وضعیت کالیبراسیون | وضعیت راند |
|:---|:---:|:---:|
| **Sensor 1: Scroll & Overflow Audit (SCROLL_TRAP)** | کالیبره (RED/GREEN) | ✅ PASS |
| **Sensor 2: Clipped Elements Audit (CLIPPED_X)** | کالیبره (RED/GREEN) | ✅ PASS |
| **Sensor 3: Semantic Icon Audit (RAW_ICON_SLUG)** | کالیبره (RED/GREEN) | ✅ PASS |
| **Sensor 4: Actions & Color Audit (INVISIBLE_ACTIONS / INVALID_COLOR)** | کالیبره (RED/GREEN) | ✅ PASS |

---

## ۳. تحلیل مستند ≤۱۲ خطی (قالب استاندارد)

- **SWOT (۴ خط)**:
  - S: همگام‌سازی کامل استایل‌های سراسری برگه با کامپایلر SSR بک‌اند و پاکسازی تمیز متغیرها در بوم.
  - W: محدودیت‌های امنیتی Bleach در فیلتر کردن متغیرهای سفارشی CSS که با نگاشت به خصوصیات استاندارد مهار شد.
  - O: یکپارچگی ظاهری کامل میان پیش‌نمایش ادمین و صفحات عمومی منتشرشده در فروشگاه.
  - T: ریسک بازنویسی متغیرهای سراسری توسط استایل‌های محلی المان‌ها که با اولویت آبشاری CSS مهار شده است.
- **TOWS (۲ خط)**:
  - SO: بهره‌گیری از هماهنگی بوم و SSR برای ایجاد صفحات با هویت بصری یکپارچه و سرعت لود بالا.
  - WT: حفظ سادگی توکن‌های طراحی در اسکیما جهت جلوگیری از نشت مقادیر نامعتبر به استایل‌های ریشه.
- **۵-چرا (۳ خط)**:
  - چرا در خروجی SSR رنگ زمینه یا فونت انتخابی در استایل سراسری اعمال نمی‌شد؟ چون متد `compile` در `ast_compiler.py:129` تگ `.builder-document` را بدون بررسی `ast.global_styles` رندر می‌کرد. با اضافه شدن استخراج خصوصیات استاندارد CSS، این نقص کاملاً رفع گردید.
- **ماتریس ریسک (۳ خط)**:
  - لایه‌های لمس‌شده: `backend/app/modules/content/application/ast_compiler.py`, `frontend/components/admin/builder/canvas-frame.tsx`, تست‌های رگرسیون.
  - تست‌های قفل‌کننده: `test_ast_compiler_applies_global_styles_to_root_document` (بک‌اند) و `controls.contract.spec.ts`.
  - اثر بر باندل/امنیت: بدون تغییر در حجم باندل، بدون کاهش امنیت sanitization.

