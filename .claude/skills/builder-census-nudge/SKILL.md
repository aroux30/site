name: builder-census-nudge
description: اجرای سرشماری کد-به-DOM کنترل‌ها (census.mjs)، ماتریس تکان‌دادن کنترل‌به‌کنترل (Active Nudge) و مقادیر مرزی/خصمانه فارسی در قدم ۲ چرخه GYM.
user-invocable: false
سرشماری کنترل‌ها و دستورالعمل تکان‌دادن واقعی (Active Nudge)
۱. قانون طلایی سرشماری (پیش از هر کلیک)
در scripts/loop/census.mjs دو فهرست را استخراج و تطبیق بده:
- S (کد/اسکیما): کل کنترل‌های تعریف‌شده برای واحد هدف در block-registry.ts و inspector-panel.tsx به‌همراه نگاشت storeKey، canvas-element.tsx و builder_ast.py/ast_compiler.py.
- D (DOM زنده): کل input, select, textarea, button, [role="combobox"], [role="switch"], [role="slider"], [role="tab"], [role="menuitem"] زیر پنل بازرس (حتی داخل آکاردئون‌های بسته یا خارج از ویوپورت).
- احکام خودکار در census.json:
  - inSchema && !inDom => MISSING_CONTROL_P0
  - inDom && !reachable (پس از scrollIntoViewIfNeeded و mouse.wheel) => SCROLL_TRAP_P0 یا CLIPPED_P1
  - نبود هندلر یا storeKey => DEAD_P0
  - ذخیره در استور بدون نگاشت بوم => STORE_ONLY_P0
  - نمایش در بوم بدون نگاشت SSR => CANVAS_ONLY_P0
۲. ماتریس تکان‌دادن و مقادیر مرزی (هر کنترل باید هر ۶ شرط D4 را پاس کند)
نوع کنترلتکان‌دادن اجباریمقادیر مرزی و خصمانهمتن / تیتر / Textareaافزودن «و» یا «تست-۳۶۰»خالی؛ ۵۰۰۰ نویسه فارسی بی‌فاصله؛ ترکیب فارسی+انگلیسی+عدد؛ نیم‌فاصله؛ <img src=x onerror=alert(1)>؛ {{WRAPPER}}عدد / اسلایدر+24px یا +15% و بازگشت0؛ منفی؛ 0.5؛ 99999؛ تایپ حروف؛ واحدهای px/em/rem/%/vw؛ calc(100% - 20px)ابعاد ۴جهتهقفل/بازکردن، تغییر هر ضلع، تغییر واحدمنطق RTL (start/end)؛ تغییر واحد مقدار را پاک نکندرنگ / Token Pickerکلیک چیپ‌ها، hex، HSL، شفافیتhex ۳/۶/۸ رقمی؛ رشته نامعتبر zzz؛ پاک‌کردن؛ صفر پرش به #000000؛ بدون هشدار کنسولSelect / Comboboxتست تک‌تک گزینه‌ها≥۲ گزینه غیرهاردکد؛ باز شدن بالای <iframe>سوییچ / Toggleروشن/خاموش/روشننمایش/پنهان شدن کنترل‌های شرطی وابستهترازبندیراست/وسط/چپ/justifyتغییر واقعی getBoundingClientRect در RTLRepeater (آکاردئون/تب/جدول/فرم)افزودن، ویرایش، جابه‌جایی، تکثیر، حذفحذف همه (حالت خالی)؛ ۵۰ آیتم؛ ID یکتارسانه / لینکانتخابگر کتابخانه، آدرس دستی، تب جدیدآدرس شکسته؛ javascript:alert(1)؛ آدرس نسبیآیکونانتخاب، جستجو، اندازه، چرخشاعمال روی <svg> واقعی؛ صفر اسلاگ خامتایپوگرافیفونت، سایز ریسپانسیو، وزن، line-heightletter-spacing غیرصفر روی فارسی = باگ (FA_TYPO) چون اتصال حروف را می‌شکندپس‌زمینه/گرادیان/سایه/فیلترNormal و Hover + Transitionترکیب چند افکت؛ احترام به prefers-reduced-motionریسپانسیوتغییر جدا در دسکتاپ/تبلت/موبایلصفر نشت موبایل به دسکتاپ (DESKTOP_LEAK)authVisibilityتنظیم روی authenticatedنبود کامل بلوک در HTML کاربر مهمانCSS/Attributes سفارشی`keyvalueو{{WRAPPER}}`
۳. کتابخانه کلاس‌های باگ برای جاروی هم‌خانواده (D6)
کلاس‌های پایه (هر باگ تازه را به این فهرست اضافه کن): SCROLL_TRAP · CLIPPED_X · TOOLBAR_OVERLAP · DEAD_MENU · RAW_ICON_SLUG · WRONG_DIR_TEXT · NO_OP · STORE_ONLY · CANVAS_ONLY · PERSIST_LOSS · SSR_MISMATCH · HARDCODED_OPTIONS · INVISIBLE_ACTIONS · INVALID_COLOR · ID_COLLISION · DESKTOP_LEAK · NATIVE_DIALOG · A11Y_NAME_FOCUS · FA_TYPO · ARROW_DIR · IFRAME_LEAK · STALE_CLOSURE.