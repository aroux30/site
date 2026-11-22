---

## پرامپت نهایی ارتقایافته ۳.۲: منحصراً Visual Page Builder (المنتور پروژه)

متن زیر را به‌طور کامل و بدون تغییر در فایل `BUILDER_GYM_LOOP_V3.md` در ریشه پروژه ذخیره کنید. این پرامپت **۱۰۰ درصد بندهای `1.2.md` و `2.2.md`** (از جمله قفل مطلق محدوده بیلدر، تفکیک ۳۵ ویجت، ۲۸ الگو و موج‌های ۱ تا ۳ المنتور در وزنه‌های ۶، ۷ و ۸) را حفظ کرده، **وزنه ۹ تست فشار ساخت لندینگ کامل از صفر نسخه ۱.۲** را بازیابی کرده و کل معماری ۵ لایه نسخه ۳ را بر آن حاکم کرده است [cite: 2, 5, 6, 8, 9, 13, 14, 15].

```markdown
# مأموریت حلقه پیوسته خودترمیمی عمیق، بازرسی ۱۰۰٪ بصری و تکمیل Visual Page Builder (المنتور پروژه) — نسخه ۳.۲

تو **Senior UI/UX Engineer، Full-Stack Architect و QA بدبین** روی مخزن `aroux30/site` هستی.
مالک پروژه نباید مجبور باشد ده‌ها کنترل هاردکد، تب خالی، میکروباگ ظاهری و نواقص کارکردی محیط صفحه‌ساز (Visual Page Builder) را دانه به دانه پیدا کند و به تو بگوید.
وظیفه تو اجرای دقیق **چرخه ۷ مرحله‌ای تمرین پیش‌رونده (Progressive Overload)** با عمق ۳۶۰ درجه و قفل مطلق روی صفحه‌ساز بصری است: در هر دور وارد `/e2e-isolated-scratchpad?builder=1` شو، از کل عناصر قابل رویت استودیو و Iframe نقشه شماره‌دار SoM بساز، تک‌تک گزینه‌های Content، Style، Advanced و نوار ابزار را دانه به دانه کلیک و تکان بده، با `pixelmatch 0.05` و ۶ سنسور خرابی حکم دوگانه جهش صادر کن، عکس‌های `before/` را با Vision ببین، همه باگ‌های P0 تا P3 را بدون حذف ثبت کن، کل یک دسته هم‌ریشه را در هر ۴ لایه اصلاح کن، تست رگرسیون اضافه کن، ری‌بیلد پاک بزن، عکس‌های `after/` را با Vision و ساب‌ایجنت ناظر بدبین (`qa-verifier`) مقایسه و تایید کن — و پس از سالم‌سازی ۱۰۰٪ امکانات فعلی، قابلیت‌های مفقود المنتور و المنتور پرو را به‌صورت سبک از پوشه محلی وارد بیلدر کن.

---

## بخش ۱: قفل مطلق محدوده (SCOPE LOCK — فقط Visual Page Builder)

تمرکز ۱۰۰٪ روی صفحه‌ساز بصری است (و توسط متغیر `GYM_SCOPE=builder` در هوک `PreToolUse` مکانیکی قفل می‌شود):
- **آدرس‌های مجاز مرورگر:** منحصراً Visual Page Builder Studio در `/e2e-isolated-scratchpad?builder=1` و خروجی رندرشده عمومی `/e2e-isolated-scratchpad` (فقط برای اثبات WYSIWYG / SSR Parity و عدم نشت `authVisibility`).
- **فرانت‌اند مجاز:** `frontend/components/admin/builder/**` (`builder-studio.tsx`, `builder-toolbar.tsx`, `blocks-palette.tsx`, `layers-tree.tsx`, `canvas-frame.tsx`, `canvas-element.tsx`, `inspector-panel.tsx`, `global-styles-dialog.tsx`, `save-template-dialog.tsx`, `save-page-template-dialog.tsx` و زیرکامپوننت‌های کنترل‌ها و ویجت‌های جدید)، `frontend/stores/builder-store.ts`، `frontend/lib/builder/**` (`block-registry.ts`, `pattern-converter.ts`, `theme-schema.ts`, `schema.ts`, `color-utils.ts`) و `frontend/types/builder.ts`.
- **بک‌اند مجاز (فقط برای اسکیما/ولیدیشن/کامپایل SSR/قالب/فرم/پاپ‌آپ بیلدر):** `backend/app/modules/content/domain/builder_ast.py`, `builder_validation.py`, `application/ast_compiler.py`, `html_sanitizer.py`, `cms_page_service.py`, `form_submission_service.py`.
- **مرجع خواندنی المنتور و المنتور پرو:** `C:\Users\Administrator\Desktop\elementor` (صرفاً Read-Only — هیچ تغییری نده و هرگز PHP/jQuery کپی نکن!).
- **ممنوعیت خروج از محدوده:** دست زدن به صفحات عمومی فروشگاه (صفحه اصلی، لیست محصولات، صفحه محصول، سبد خرید، وبلاگ، `/admin/themes`) ممنوع است!

---

## بخش ۲: خط قرمزهای غیرقابل مذاکره (قفل‌شده توسط هوک‌های Node.js)

1. هیچ تغییری در `backend/app/modules/audit/application/audit_service.py` نده.
2. به برگه `showcase` هرگز دست نزن؛ تمام تست‌ها و تغییرات منحصراً روی `e2e-isolated-scratchpad` اجرا شوند.
3. فقط روی شاخه ایزوله فعلی (غیر از `main`) کامیت کن؛ هرگز `git push` یا ادغام در `main` انجام نده.
4. پاک کردن اسکرین‌شات‌ها مطلقاً ممنوع است! همه عکس‌ها، نقشه‌های SoM و `diff.png` باید در `.loop/artifacts/builder-gym/round-XXX/before/` و `.loop/artifacts/builder-gym/round-XXX/after/` باقی بمانند.
5. استفاده از `{ force: true }`، `.skip()`، `.only()` یا فیلتر کردن تست‌ها در گیت نهایی ممنوع است. هر بار راستی‌آزمایی باید کل `npx tsc --noEmit`، کل `npx vitest run` (۳۶۹+ تست)، کل `python -m pytest app/tests/unit` (۶۲۲+ تست) و تست Playwright بیلدر کامل و سبز باشند.
6. **ممنوعیت دور زدن Vision و سقف وضوح:** هیچ دوری بدون باز کردن مستقیم PNGهای `before/` و `after/` با ابزار `Read` معتبر نیست (رصد توسط هوک `PostToolUse` و گیت `Stop`). در هر پاس Vision حداکثر **۸ تا ۱۰ تصویر/برش متمرکز** باز کن تا از افت رزولوشن بیش از ۲۰ تصویر API جلوگیری شود.
7. **قانون ثبت بدون حذف (Zero-Omission Law):** تک‌تک جزئیات ریز (P2/P3) و باگ‌های عمده (P0/P1) دیده‌شده در تصویر یا DOM باید در `defect_ledger` فایل `.loop/state_ledger.json` ثبت شوند؛ هیچ موردی با نگاه سطحی رد نشود.
8. **داوری مستقل و غیرقابل‌جعل:** در قدم ۶B هر دور، فراخوانی ساب‌ایجنت Read-Only `qa-verifier` الزامی است تا هوک `SubagentStop` فایل `verifier_verdict.json` را با حکم `"APPROVE"` ثبت کند (نوشتن دستی این فایل توسط هوک مسدود است).
9. اگر فایل `AGENT_STOP` در ریشه پروژه وجود داشت فوراً متوقف شو. اگر فایل `STEER.md` وجود داشت، اولویت اول این دور اجرای دستور داخل آن است و بعد فایل را پاک کن.

---

## بخش ۳: قوانین حفاری ۳۶۰ درجه، بازرسی تک‌به‌تک SoM و چارچوب‌های تحلیلی

### ۳.۱ بازرسی تک‌به‌تک ۱۰۰٪ عناصر تصویر (Set-of-Mark روی استودیو + Iframe)
- اسکریپت Playwright پیش از هر اصلاحی، تمام دکمه‌ها، تب‌ها، ورودی‌ها، سلکت‌ها، رنگ‌انتخاب‌کن‌ها، اسلایدرها، تاگل‌ها، گره‌های درخت لایه‌ها و ابزارک‌های شناور داخل استودیو و داخل `CanvasFrame` Iframe را شماره‌گذاری (`#1..#N`) کرده، `before_som.png` و `som_inventory.json` می‌سازد.
- تک‌تک شماره‌های `#1..#N` مربوط به بخش هدف این دور باید **یک‌به‌یک** کلیک و تست شوند.

### ۳.۲ آزمون تکان دادن واقعی و «حکم دوگانه جهش» (Effect Proof + Breakage Proof)
برای هر کنترل در تب‌های Content، Style، Advanced و نوار ابزار استودیو:
- **تکان دادن واقعی:** متن/تیتر ← افزودن حرف فارسی («و» یا «تست-۳۶۰»)؛ ترازبندی/چیدمان ← راست/وسط/چپ؛ اسلایدر/عدد/درصد/Padding/Margin/Gap/Radius ← افزایش و کاهش (`+24px` یا `+15%`)؛ رنگ/Token Picker ← تغییر رنگ متن/پس‌زمینه/حاشیه (بدون پرش به `#000000` و بدون هشدار کنسول)؛ تاگل‌ها/سلکت‌ها/Repeaterها (آکاردئون/تب/جدول/فرم) و تب Advanced (انیمیشن، `z-index`, `position`, کلاس دلخواه، `authVisibility`, قفل، مخفی) ← تغییر وضعیت واقعی.
- **اثبات اثر (آیا تغییری کرد؟):** بررسی تغییر `getComputedStyle` و `textContent`/`getBoundingClientRect` داخل Iframe + اختلاف پیکسلی **`pixelmatch` با آستانه `0.05`** (`changed_pixels > 0` + ذخیره `diff.png`) + تایید چشمی Vision + پایداری پس از `Save Draft + Reload` و تطابق با `/e2e-isolated-scratchpad` (SSR). هر کنترل بی‌اثر = **باگ قطعی `NO_OP_P0`**.
- **اثبات سلامت حین تغییر (آیا چیزی خراب شد؟):** صفر خطای کنسول/`pageerror`، صفر خطای شبکه `4xx/5xx`، صفر خطای Hydration (`#418/#423/#425`)، صفر سرریز افقی (`scrollWidth - clientWidth === 0`) در سایدبار، بازرس و Iframe، صفر هم‌پوشانی/بریدگی عناصر همسایه (`elementsFromPoint`) و حفظ سلامت RTL و Dark Mode.
- خروجی کامل تک‌تک `#1..#N` باید در `.loop/artifacts/builder-gym/round-XXX/mutation_report.json` ذخیره شود.

### ۳.۳ اسکن استاتیک سیم‌کشی + ثبت تمام‌طیف P0–P3 + اصلاح خوشه‌ای
- در ۲ دقیقه اول قدم ۲، سیم‌کشی `inspector-panel.tsx`، `builder-store.ts`، `canvas-element.tsx`، `builder_ast.py` و `ast_compiler.py` را سریع بررسی کن تا هندلرهای خالی (`() => {}`)، `onClick={fn()}`، استاب‌ها، `window.alert/confirm` و Schema Drift لو بروند.
- تمام یافته‌های P0، P1، P2 و P3 را بدون حذف در `defect_ledger` ثبت کن؛ اولویت اصلاح در هر دور یک خوشه کامل (۴ تا ۸ باگ هم‌ریشه P0/P1 در یک تب یا دسته ۵تایی ویجت) است و پس از صفر شدن P0/P1 آن وزنه، کل P2های ثبت‌شده همان وزنه پاک‌سازی می‌شوند.

### ۳.۴ تحلیل اجباری SWOT، TOWS، ۵-چرا و ماتریس ریسک در هر دور
در گزارش `.loop/rounds/builder-round-XXX.md` برای هر دور الزامی بنویس:
1. **SWOT مستند بخش هدف بیلدر** (حداکثر ۳–۵ مورد عینی در هر ربع S/W/O/T).
2. **تبدیل به کنش TOWS** (SO / WO / ST / WT) برای اولویت‌بندی دور بعد و پورت المنتور.
3. **ریشه‌یابی ۵-چرا (5-Whys RCA)** برای باگ محوری خوشه با ارجاع دقیق به فایل و خط.
4. **ماتریس ریسک تغییر و رگرسیون** (لایه‌های لمس‌شده + تست قفل‌کننده + وضعیت باندل/امنیت).

### ۳.۵ قرارداد فنی پورت سبک المنتور
- ساخت کامپوننت‌های مشترک (Group Controls + `DimensionsControl` ۴جهته با قفل و واحدهای `px/em/rem/%/custom` + `ScopedCssResolver` با `{{WRAPPER}}`) پیش از تکثیر در ویجت‌ها.
- کداسپلیتینگ اجباری ویجت‌های تعاملی جدید با **`next/dynamic`** (ممنوعیت `import *`).
- پیاده‌سازی هم‌زمان هر ۴ لایه (`Inspector ← Store ← CanvasFrame ← Python AST/Sanitizer`) و تست ضد XSS در `html_sanitizer.py` برای ۳۰ شکل SVG، Custom Attributes و Scoped CSS.

---

## بخش ۴: نردبان وزنه‌های پیش‌رونده (فقط Visual Page Builder — وزنه‌های ۱ تا ۹)

ابتدا `.loop/DASHBOARD.md` و `.loop/state_ledger.json` را بخوان (اگر وجود ندارند بساز و اگر `.loop/BUILDER_GYM_LOG.md` قدیمی هست وضعیتش را بدون حذف به JSON مهاجرت بده). تا کل چک‌باکس‌ها و شماره‌های SoM وزنه فعلی با صفر باگ P0/P1/P2 و حکم `"APPROVE"` ناظر پاک نشده‌اند، به وزنه بعدی نرو:

### وزنه ۱ — ۵ کیلو: اسکلت استودیو، دکمه‌های مرده سطح استودیو، درخت لایه‌ها و بوم Iframe
- نمای ۳ ستونه استودیو (`builder-studio.tsx` & `builder-toolbar.tsx`): تمام‌صفحه بودن واقعی بدون نشت هدر سایت، تست SoM و Nudge تک‌تک دکمه‌های نوار ابزار (صفر دکمه هاردکد/بی‌اثر)، نبود سرریز افقی (`scrollWidth <= clientWidth`) در سایدبار راست و بازرس چپ، متقارن بودن تب‌های سایدبار (افزودن بلوک | لایه‌ها) و نبود بریدگی متن.
- درخت لایه‌ها (`layers-tree.tsx`): رویت‌پذیری دائمی دکمه‌های حذف/تکثیر/مخفی بدون نیاز به هاور (موقعیت ماوس `(0,0)`، بدون `opacity-0`)، خوانایی کامل روی ردیف انتخاب‌شده (`bg-primary`)، تورفتگی واضح RTL (`depth * 24px` در بیرون کادر سبز انتخاب)، خط راهنمای عمودی درختی، دکمه باز/بست واقعی (`ChevronDown/ChevronLeft`)، دستگیره درگ (`GripVertical`) و آیکون وضعیت (`EyeOff/Lock`).
- بوم ایزوله (`canvas-frame.tsx` & `canvas-element.tsx`): عدم بریدگی نوار ابزار شناور بالای اولین المان (`toolbar.top >= iframe.top`)، کانتینر خالی با کادر خط‌چین واضح با حداقل ارتفاع `80px` و دکمه راهنمای افزودن بلوک، سلامت هم‌زمان متغیرهای کانال HSL (`--primary` و...) و `--theme-*` بدون CSS نامعتبر `hsl(#...)` یا `background-color: 160 84% 39%`.

### وزنه ۲ — ۱۵ کیلو: ممیزی تکان‌دادنی (SoM + Nudge) تک‌تک کنترل‌های تب‌های Content / Style / Advanced برای همه ۳۵ ویجت
در دسته‌های ۵تایی تا پوشش ۱۰۰٪ همه ۳۵ ویجت (۱۰۵ سلول ویجت × تب در `state_ledger.json`):
- **۱۰ ویجت پایه:** `container, section, columns, heading, paragraph, text, image, button, spacer, divider`.
- **۱۳ ویجت تعاملی و فرم:** `table, form_container, form_input, form_textarea, form_select, form_checkbox, form_radio, accordion, tabs, countdown, video, icon_box, social_links`.
- **۱۲ ویجت فروشگاهی:** `product_card, product_grid, image_gallery, star_rating, review_histogram, recently_viewed, mega_menu, product_price, product_variants, add_to_cart, mini_cart, cart_summary`.
برای هر ویجت: باز کردن هر سه تب Content، Style و Advanced، شماره‌گذاری SoM و تکان دادن یک‌به‌یک همه گزینه‌ها شامل `Token Picker`، `<input type="color">` (`toValidHexColor`)، `Media Library Picker`، هدر/سلول جدول، گزینه‌های فرم/آکاردئون/تب‌ها، `Padding/Margin` چهارجهته، Flexbox/Grid/Position/Z-Index/Overflow، انیمیشن، نمایش شرطی (`authVisibility`)، Global Component، قفل و مخفی‌سازی؛ ثبت `pixelmatch 0.05` + حکم دوگانه + Vision + Reload + SSR Parity.

### وزنه ۳ — ۲۵ کیلو: ممیزی تصویری و ساختاری هر ۲۸ الگوی آماده + پالت بلوک‌ها + Global Styles
- پالت بلوک‌ها (`blocks-palette.tsx`): جستجوی واقعی، تب‌های «بلوک‌ها»، «الگوها (۲۸)» و «قالب‌های من»، وضوح آیکون، عنوان و دکمه درج فوری.
- درج همه ۲۸ الگو (`pattern-converter.ts`) در دسته‌های ۴ تا ۵ تایی تا پوشش ۱۰۰٪: عکس `before` در بوم و در `/e2e-isolated-scratchpad` (SSR)، بازبینی چشمی دقیق با Vision (چیدمان RTL، کنتراست دکمه‌ها، `comparison-table`، `lead-capture-form`، کارت‌ها، قیمت‌ها، ستون‌ها و نبود تداخل `var(--primary)` در استایل خطی) و اصلاح ریشه‌ای الگوهای شکسته یا زشت.
- دیالوگ Global Styles (`global-styles-dialog.tsx`): تست یک‌به‌یک تغییر رنگ برند، فونت و شعاع، تزریق فوری به Iframe بدون نشت به پنل ادمین، پایداری پس از Reload و کارکرد واقعی دکمه «بازنشانی به تم سایت».

### وزنه ۴ — ۴۰ کیلو: تجربه واقعی المنتور (Drag & Drop، کپی/پیست، قالب‌ها و برابری کامل با صفحه نهایی)
- درگ‌انددراپ واقعی (`@dnd-kit` بدون `force: true`): از پالت به بوم، جابه‌جایی در Root، انداختن داخل کانتینر تودرتو، انتقال بین دو کانتینر، بازگشت به Root، جلوگیری از Circular Drop و نمایش واضح Drop Indicator.
- میانبرها و بهره‌وری (`builder-store.ts` & `builder-toolbar.tsx`): `Undo/Redo` (`Ctrl+Z/Y`)، `Copy/Paste` (`Ctrl+C/V` با شناسه یکتا)، `Copy/Paste Styles`، `Multi-Select` + حذف گروهی، دکمه‌های تکثیر و حذف روی بوم و در `LayersTree`.
- قالب‌های بخش و کل صفحه (`save-template-dialog.tsx` & `save-page-template-dialog.tsx`): ذخیره، پیش‌نمایش درختی، تغییر نام/دسته‌بندی، کلون، حذف، درج مجدد و Import کل صفحه با بازتولید ID یکتا.
- کامپوننت‌های همگام (`Global Components`)، `Autosave` و `Save Draft` + Reload + حالت Preview + مقایسه تصویری WYSIWYG Parity بین بوم و `ast_compiler.py` + تایید عدم نشت بلوک `authVisibility="authenticated"` برای کاربر مهمان.

### وزنه ۵ — ۵۵ کیلو: ریسپانسیو موبایل/تبلت، دارک‌مود کامل، WCAG و تست فشار ۵۰+ المان
- ریسپانسیو داخل بیلدر: تغییر Viewport به تبلت (`768px`) و موبایل (`375px`)، ثبت استایل اختصاصی موبایل بدون تخریب دسکتاپ (`resolveResponsiveValue`)؛ بازبینی Vision الگوها و کانتینرها در تبلت و موبایل.
- دارک‌مود کامل بیلدر و Iframe + اسکن `AxeBuilder` (`wcag2a, wcag2aa, wcag21a, wcag21aa`) برای حذف تمام خطاهای `critical` و `serious`.
- تست فشار و لبه‌های خرابی: بارگذاری ۵۰+ المان تودرتو در `e2e-isolated-scratchpad` بدون لگ یا Hydration (`#418/#423/#425`)، حفظ `isDirty` در خطای شبکه حین Autosave و تست ورودی‌های خالی یا فارسی بسیار طولانی.

### وزنه ۶ — ۷۰ کیلو (پورت المنتور — موج ۱): تکمیل حرفه‌ای تب‌های Style و Advanced، کانتینر Grid، اشکال جداکننده و Navigator
ابتدا مانیفست `.loop/elementor_parity_manifest.json` را از `C:\Users\Administrator\Desktop\elementor` بساز و با تست SoM/Nudge/Pixelmatch/Vision/SSR پیاده‌سازی کن:
- گروه‌های کنترل `includes/controls/groups/`: تایپوگرافی کامل (فونت، سایز ریسپانسیو، وزن، Line-Height، Letter-Spacing، Decoration)، پس‌زمینه کامل (Classic، Gradient خطی/شعاعی با زاویه و مکان، Video/Slideshow در سطح کانتینر + Overlay + Blend Mode)، Border و Box Shadow مستقل در Normal و Hover با Transition، Text Shadow/Stroke و CSS Filters.
- تکمیل تب Advanced مطابق `includes/widgets/common-base.php`: واحدهای `px/em/rem/%/custom` (شامل توابع ریاضی CSS) با قفل ۴جهته، Transform (Rotate/Scale/Offset/Skew/Flip در Normal/Hover)، Mask (Circle/Flower/Sketch/Triangle/Blob/Hexagon/Custom SVG)، Sticky، Motion/Scroll Effects (با احترام به `prefers-reduced-motion`)، Custom Attributes (`key|value`) و Scoped Custom CSS ایمن (`{{WRAPPER}}`).
- کانتینر CSS Grid کامل (سطر/ستون `fr/px/custom`، خطوط راهنما، Autoflow) + پورت ۳۰ شکل SVG جداکننده از `assets/shapes/*.svg` (Top/Bottom، رنگ، عرض، ارتفاع، Flip، Bring to Front با پاک‌سازی امن در `html_sanitizer.py`).
- ارتقای `LayersTree` به Navigator کامل: تغییر نام با دابل‌کلیک، نشانگر وضعیت (Hidden/Locked/Motion/CustomCSS) و منوی راست‌کلیک (Duplicate، Copy/Paste، Copy/Paste/Reset Style، Save as Template/Global، Delete).

### وزنه ۷ — ۸۵ کیلو (پورت المنتور — موج ۲): ویجت‌های کلیدی مفقود Core و Pro + پاپ‌آپ و Off-Canvas
خواندن مشخصات از `C:\Users\Administrator\Desktop\elementor` (`includes/widgets/` و `elementor-pro/modules/`) و پورت سبک با **`next/dynamic`** و اتصال ۴ لایه + SoM + Vision + SSR:
- **ویجت‌های Core مفقود:** `icon`, `icon_list`, `image_box`, `image_carousel`, `counter`, `progress_bar`, `testimonial`, `alert`, `toggle`, `menu_anchor`, `nested_tabs`, `nested_accordion`, `floating_bar/contact_buttons`.
- **ویجت‌های Pro پرکاربرد:** `slides/nested_carousel`, `animated_headline`, `call_to_action`, `flip_box`, `price_table`, `price_list`, `hotspot`, `table_of_contents`, `progress_tracker`, `blockquote`, `share_buttons`, `lottie`.
- **ماژول‌های تعاملی:** `off_canvas` (کشوی منو/فیلتر تودرتو) و `popup_builder` (طراحی پاپ‌آپ در همین بیلدر + تریگرهای بارگذاری/اسکرول/کلیک/قصد خروج).

### وزنه ۸ — ۱۰۰ کیلو (پورت المنتور — موج ۳): Global Site Kit، Theme Builder، Loop Builder، فرم چندمرحله‌ای و Import/Export
- تکمیل ۱۲ تب تنظیمات سراسری طبق `core/kits/documents/tabs/` در `global-styles-dialog.tsx`.
- ماژول `theme_builder` (قالب‌های Header، Footer، Single Product، Product Archive و 404 با Display Conditions)، ماژول `loop_builder` (کارت تکرارشونده + `loop_grid` و `loop_carousel` متصل به داده واقعی)، فرم‌ساز چندمرحله‌ای (`multi_step_form`) و `import_export` کامل JSON برای صفحات/قالب‌ها/کیت‌ها + گسترش کتابخانه الگوها.

### وزنه ۹ — بی‌نهایت (+۱۰ کیلو در هر دور — بازیابی‌شده از نسخه ۱.۲: ساخت لندینگ کامل از صفر + پاک‌سازی کامل P2/P3)
هر زمان وزنه‌های ۱ تا ۸ واقعاً پاک شدند، نقش یک طراح صفحه سخت‌گیر را بازی کن: یک لندینگ کامل را از صفر داخل بیلدر بساز (Hero + ویژگی‌ها + جدول مقایسه + فرم چندمرحله‌ای + FAQ + پاپ‌آپ + CTA)، تک‌تک بخش‌ها را ویرایش، درگ، رنگ‌آمیزی، کپی، ذخیره و در موبایل/تبلت/دسکتاپ و Light/Dark پیش‌نمایش کن؛ کل بک‌لاگ میکروباگ‌های `P2/P3` را از `defect_ledger` ببند، از هر مرحله عکس بگیر، کوچک‌ترین نقص UX، زشتی، ناهماهنگی ترازبندی یا باگ میکرو را شکار و اصلاح ریشه‌ای کن و تست رگرسیونش را دائمی کن.

---

## بخش ۵: چرخه اجباری ۷ مرحله‌ای در هر دور (Round)

1. **بررسی کارنامه و سلامت پایه:** `.loop/DASHBOARD.md`، `.loop/state_ledger.json`، `.loop/LESSONS.md` و `git log -5 --oneline` را بخوان (تکرار ممنوع؛ اولویت اول با `STEER.md`). یک اسموک‌تست سریع روی `/e2e-isolated-scratchpad?builder=1` بزن.
2. **اسکن سیم‌کشی + فهرست‌برداری SoM + تست تک‌به‌تک دوگانه + بازبینی مستقیم Vision (`before/`):** ۲ دقیقه سیم‌کشی فایل‌های بخش هدف (و فایل مرجع المنتور در وزنه‌های ۶ تا ۸) را بررسی کن؛ بلافاصله اسکریپت Playwright روی `http://127.0.0.1:3000/e2e-isolated-scratchpad?builder=1` را اجرا کن تا `before_som.png` + `som_inventory.json` بسازد، کل شماره‌های هدف `#1..#N` را یک‌به‌یک کلیک و تکان بدهد، `pixelmatch` (`0.05`) + ۶ سنسور خرابی + تست SSR را اجرا کرده و `mutation_report.json` و عکس‌های `before/` را در `.loop/artifacts/builder-gym/round-XXX/before/` ذخیره کند. سپس **الزاماً (رصد توسط هوک)** حداکثر ۸ تا ۱۰ تصویر/برش کلیدی `before/` را مستقیماً با ابزار `Read` (Vision) باز کن، کل باگ‌های P0 تا P3 را در `defect_ledger` ثبت کن و یک خوشه هم‌ریشه کامل (۴ تا ۸ باگ P0/P1 یا یک بسته منسجم از وزنه‌های ۶ تا ۹) را انتخاب کن.
3. **اصلاح ریشه‌ای / پیاده‌سازی سبک در هر ۴ لایه بیلدر:** کد آن خوشه را در `Inspector ← Store ← Canvas ← Backend AST/Sanitizer` تمیز، سبک و کامل پیاده‌سازی کن (بدون هاردکد، بدون `TODO` و بدون خروج از Scope Lock).
4. **عضله‌سازی تست (Regression Lock):** برای هر باگ یا قابلیت این دور، assertion واقعی (بدون `force: true` و `.skip`) به Vitest / Pytest یا Playwright بیلدر اضافه کن.
5. **ری‌بیلد پاک سرور زنده ویندوز:** اسکریپت `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/loop/rebuild-and-verify.ps1` را اجرا کن تا کش `.next` پاک شود و نسخه تازه روی پورت ۳۰۰۰ بالا بیاید.
6. **اثبات بصری «بعد از اصلاح» + داوری ساب‌ایجنت ناظر + دروازه کامل تست‌ها:** در قدم ۶A دقیقاً همان تست SoM/Nudge/Pixelmatch را روی سرور جدید اجرا کن، عکس‌های `after/` و `diff.png` را در `.loop/artifacts/builder-gym/round-XXX/after/` ذخیره کن، تصاویر `before/` و `after/` را با ابزار `Read` (Vision) مقایسه کن و کل مجموعه تست‌ها را کامل اجرا کن (`npx tsc --noEmit` + کل `npx vitest run` + کل `python -m pytest app/tests/unit` + تست Playwright بیلدر). در قدم ۶B ساب‌ایجنت مستقل `qa-verifier` را فراخوانی کن تا هوک `SubagentStop` فایل `verifier_verdict.json` را ثبت کند؛ در صورت `"REJECT"`، ایرادهای اعلامی ناظر را رفع و مجدداً داوری بگیر. (قانون فرار از بن‌بست: پس از ۲ شکست روی یک باگ خاص، فقط تغییر همان باگ قفل‌شده را با `git checkout -- .` برگردان، علت را در `NEEDS_HUMAN.md` و `state_ledger.json` ثبت کن و فوراً سراغ دسته بعدی برو.)
7. **کامیت اتمیک، ثبت کارنامه تحلیلی (SWOT/TOWS/RCA) و به‌روزرسانی دفتر کل:** کامیت تمیز (`fix(builder-gym-rXXX): ...` یا `feat(builder-gym-rXXX): ...`) روی شاخه فعلی ثبت کن؛ گزارش کامل دور (جدول SoM `#1..#N`، شرح دقیق مقایسه چشمی Vision با مسیر عکس‌ها، تحلیل SWOT/TOWS/5-Whys/ماتریس ریسک، مسیر مرجع المنتور در صورت پورت، فایل‌های تغییریافته و تست‌های اضافه‌شده) را در `.loop/rounds/builder-round-XXX.md` ذخیره کن و `state_ledger.json` و `DASHBOARD.md` (≤۱۵۰ خط) را آپدیت کن. پس از پاک شدن وزنه‌های ۱ تا ۵ با صفر باگ P0/P1/P2 و ۱۰۰٪ تست سبز عبارت `BUILDER_GYM_LEVELS_1_TO_5_CLEAN` را ثبت کن و وارد وزنه ۶ شو؛ پس از تکمیل وزنه‌های ۱ تا ۸ عبارت `BUILDER_GYM_ALL_LEVELS_MASTERED` را ثبت کن و وارد وزنه ۹ (تست لندینگ از صفر و صیقل بی‌نهایت) شو.
