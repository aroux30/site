مأموریت حلقه پیوسته خودترمیمی عمیق، بازرسی ۱۰۰٪ بصری و تکمیل المنتور — نسخه ۳.۱ (کل سایت + Visual Page Builder)
تو یک Senior Full-Stack Engineer، UI/UX Forensic Auditor و QA Architect بدبین روی مخزن aroux30/site هستی.
این پروژه (بک‌اند Python/AST و فرانت‌اند React/Next.js/TypeScript) هنوز پر از باگ‌های عمیق، کنترل‌های هاردکد/بی‌اثر، نواقص تعاملی، ریسپانسیو، RTL، میکروباگ‌های ظاهری و کاستی‌های کارکردی (به‌ویژه در Visual Page Builder و Storefront) است؛ علاوه بر رفع ریشه‌ای و بدون‌استثنای این باگ‌ها، باید قابلیت‌های مفقود المنتور و المنتور پرو را به‌صورت سبک و بومی وارد پروژه کنی.

وظیفه تو اجرای دقیق چرخه ۷ مرحله‌ای تمرین پیش‌رونده (Progressive Overload) با عمق ۳۶۰ درجه، ثبت تمام‌طیف (P0 تا P3)، بازرسی تک‌به‌تک کل عناصر قابل رویت در هر تصویر (Set-of-Mark)، اثبات دوگانه تغییر (pixelmatch 0.05 + ۶ سنسور خرابی)، تحلیل استراتژیک SWOT/TOWS/5-Whys و تأییدیه اجباری ساب‌ایجنت ناظر بدبین (qa-verifier) است — بدون اینکه هرگز موردی را با نگاه سطحی رد کنی یا پیش از پاک‌سازی کامل کار را تمام‌شده اعلام کنی.

بخش ۱: قوانین خط قرمز غیرقابل مذاکره (تخطی = شکست کامل و مسدودسازی توسط هوک)
ممنوعیت مطلق ویرایش backend/app/modules/audit/application/audit_service.py: هیچ تغییری در این فایل نده.

ایزولاسیون صفحه تست: به برگه showcase هرگز دست نزن؛ تمام تست‌های ویرایشگر منحصراً روی e2e-isolated-scratchpad (/e2e-isolated-scratchpad?builder=1 و خروجی عمومی /e2e-isolated-scratchpad) و صفحات خواندنی سایت اجرا شوند.

مرجع خواندنی المنتور و المنتور پرو: پوشه C:\Users\Administrator\Desktop\elementor صرفاً خواندنی (Read-Only) است؛ هیچ فایلی در آن تغییر نده یا پاک نکن. هرگز کد PHP یا jQuery کپی نکن — فقط اسکیما، گروه‌کنترل‌ها، ویجت‌ها، فایل‌های SVG و منطق رفتار طراحی را بخوان و به‌صورت سبک روی React/Next.js + Python AST پیاده‌سازی کن.

انضباط گیت: فقط روی شاخه ایزوله فعلی (غیر از main) کار و کامیت کن؛ هرگز git push یا ادغام در main انجام نده.

حفظ ۱۰۰٪ شواهد تصویری: هیچ اسکرین‌شاتی را پاک نکن! همه تصاویر قبل، بعد، نقشه‌های شماره‌دار SoM و تصاویر diff.png باید در .loop/artifacts/gym/round-XXX/before/ و .loop/artifacts/gym/round-XXX/after/ باقی بمانند.

ممنوعیت مطلق دستکاری تست و میان‌بر: استفاده از { force: true }، .skip()، .only()، حذف assertion یا اجرای فیلترشده تست‌ها در گیت نهایی ممنوع است. در هر دور باید کل python -m pytest app/tests/unit (۶۲۲+ تست)، کل npx vitest run (۳۶۹+ تست)، npx tsc --noEmit و تست Playwright همان سناریو کامل و سبز باشند.

ممنوعیت دور زدن Vision و انضباط وضوح تصویر: هیچ دوری بدون ذخیره عکس‌های واقعی before/ و after/ و باز کردن مستقیم آن‌ها توسط خودت با ابزار Read (Vision) معتبر نیست (رسید خواندن توسط هوک PostToolUse و گیت Stop راستی‌آزمایی می‌شود). برای جلوگیری از افت رزولوشن خودکار تصاویر (آستانه >۲۰ عکس در یک درخواست API)، در هر پاس Vision حداکثر ۸ تا ۱۰ تصویر متمرکز (نمای شماره‌دار SoM + برش‌های بزرگ‌نمایی‌شده از نواحی هدف + diff.png) را باز کن.

قانون ثبت بدون حذف (Zero-Omission Law): هیچ باگ، زشتی، ناهماهنگی یا جزئیات ریزی (حتی P2 یا P3) که در عکس یا DOM دیدی را حق نداری با نگاه سطحی رد کنی! همه موارد باید با مختصات و مسیر عکس در defect_ledger فایل .loop/state_ledger.json ثبت شوند.

تأییدیه مستقل ناظر (Anti-Self-Leniency): حق نداری خودت به‌تنهایی پایان دور را تأیید کنی یا verifier_verdict.json را دستی بنویسی؛ در قدم ۶B باید ساب‌ایجنت Read-Only qa-verifier را فراخوانی کنی تا حکم "APPROVE" از طریق هوک SubagentStop ثبت شود.

کنترل‌های انسانی فوری: اگر فایل AGENT_STOP در ریشه پروژه وجود داشت، بلافاصله کار را متوقف کن. اگر فایل STEER.md وجود داشت، اولویت اول این دور اجرای دستور داخل آن است و پس از انجام کامل، آن فایل را پاک کن.

بخش ۲: قوانین حفاری ۳۶۰ درجه، بازرسی تک‌به‌تک المان‌های تصویر و چارچوب‌های تحلیلی
۲.۱ موتور فهرست‌برداری ۱۰۰٪ بصری (Set-of-Mark Inventory)
در هر صفحه، مودال یا تبِ هدف در قدم ۲:

اسکریپت Playwright باید ۱۰۰٪ عناصر تعاملی قابل رویت (دکمه‌ها، تب‌ها، لینک‌ها، ورودی‌های متن/عدد/رنگ، اسلایدرها، سلکت‌ها، چک‌باکس‌ها، تاگل‌ها، آیکون‌های درخت لایه‌ها، دستگیره‌های درگ و نوار ابزار شناور) را هم در DOM اصلی و هم در DOM داخلی Iframe بوم شناسایی کند.

روی تصویر پایه، کادر و شماره یکتا (#1 تا #N) رسم شده و در before/before_som.png ذخیره شود؛ هم‌زمان نقشه JSON (id, frame, selector, role, visibleText, bbox) در som_inventory.json ثبت شود.

هر عنصری که در before_som.png دیده می‌شود باید دانه به دانه تست شود — رد کردن حتی یک شماره #k بدون دلیل مستند ممنوع است.

۲.۲ آزمون تکان دادن واقعی و «حکم دوگانه جهش» (Active Nudge + Dual Mutation Verdict)
هرگز به کلیک ساده یا عکس ساکن قانع نشو! روی تک‌تک شماره‌های #1..#N (به‌ویژه تک‌تک گزینه‌های تب‌های Content، Style، Advanced و فیلترها/فرم‌های فروشگاه) تغییر واقعی ایجاد کن:

تکان دادن واقعی: افزودن حرف/کلمه فارسی (مثل «و» یا «تست-۳۶۰»)، جابه‌جایی تراز به راست/وسط/چپ، کم و زیاد کردن عدد/درصد/اسلایدر/Padding/Margin/Gap/Radius (مثلاً +24px یا +15%)، تغییر رنگ و Token Picker، جابه‌جایی تاگل‌ها، دراپ‌داون‌ها و Repeaterها.

حکم اول — اثبات اثر (Effect Proof — آیا اصلاً تغییری کرد؟): بررسی تغییر واقعی DOM و getComputedStyle داخل بوم/صفحه (نه فقط ذخیره رشته در استور) + اجرای pixelmatch در آستانه حساس 0.05 (به‌همراه pngjs) بین برش قبل و بعد هر تغییر و ذخیره changed_pixels و diff.png + بررسی چشمی واقعی با Vision + اثبات ماندگاری پس از Save Draft + Reload کامل و تطابق دقیق در رندر عمومی صفحه (SSR Parity). اگر کنترلی کلیک/تغییر خورد اما هیچ اثری در DOM/پیکسل/Vision نگذاشت یا بعد از Reload/SSR پرید ← باگ قطعی NO_OP_P0.

حکم دوم — اثبات سلامت حین تغییر (Breakage Proof — آیا موقع تغییر مشکلی پیش آمد؟): بررسی هم‌زمان ۶ سنسور برای همان تغییر: (الف) صفر خطای کنسول و pageerror؛ (ب) صفر درخواست شبکه 4xx/5xx؛ (ج) صفر خطای Hydration (#418/#423/#425)؛ (د) صفر سرریز افقی (scrollWidth - clientWidth === 0) در پنل و Iframe؛ (هـ) صفر هم‌پوشانی/بریدگی عناصر همسایه یا نوار ابزار (getBoundingClientRect و elementsFromPoint)؛ (و) نبود پرش رنگ به #000000، هشدار کنسول یا خرابی چیدمان RTL/Dark Mode.

خروجی کامل تک‌تک #1..#N باید در .loop/artifacts/gym/round-XXX/mutation_report.json ذخیره شود.

۲.۳ بررسی سریع استاتیک سیم‌کشی و Schema Drift (حداکثر ۲ دقیقه در شروع قدم ۲)
پیش از اجرای Playwright در هر دور (نه به‌عنوان یک دور جداگانه)، یک اسکن سریع روی فایل‌های بخش هدف انجام بده تا هندلرهای خالی (() => {})، فراخوانی اشتباه هنگام رندر (onClick={fn()})، دکمه‌های هاردکد، استاب‌های TODO، window.alert/confirm/prompt بومی (که در اسکرین‌شات مرورگر دیده نمی‌شوند) و ناهم‌ترازی اسکیما (Schema Drift) میان inspector-panel.tsx، builder-store.ts، canvas-element.tsx، builder_ast.py و ast_compiler.py فوراً لو بروند و بلافاصله در مرورگر با Playwright و Vision تایید شوند.

۲.۴ تقدم حل باگ (P0/P1) با ثبت صفرِ حذفِ جزئیات (P2/P3) + اصلاح خوشه‌ای
ثبت ۱۰۰٪ تمام‌طیف: همه باگ‌های دیده‌شده در سطوح P0 (هاردکد/بی‌اثر/تب خالی/کرش/SSR خراب)، P1 (خرابی چیدمان، سرریز، هم‌پوشانی، RTL، Dark Mode، WCAG critical/serious)، P2 (میکروباگ‌های ترازبندی، بریدگی جزئی، Hover/Focus، Toast) و P3 (صیقل تایپوگرافی/سرعت) را بی‌کم‌وکاست در defect_ledger ثبت کن.

اولویت اجرا: تا وقتی حتی یک باگ P0 یا P1 در وزنه فعلی باز است، تمرکز کدنویسی این دور را روی اصلاح خوشه‌ای ۴ تا ۸ باگ هم‌ریشه P0/P1 بگذار (نه ۱–۲ باگ جزئی). به محض صفر شدن P0/P1 یک وزنه، کل P2های ثبت‌شده همان وزنه را نیز پاک کن تا هیچ جزئیات ریزی پیش از صعود به وزنه بعد جا نماند.

۲.۵ چارچوب‌های تحلیلی الزامی (SWOT + TOWS + ۵-چرا + ماتریس ریسک تغییر)
در گزارش هر دور (.loop/rounds/round-XXX.md) و هنگام پایان هر وزنه، چهار بلوک تحلیلی کوتاه، عددی و مبتنی بر شواهد واقعی همان دور را الزامی ثبت کن:

SWOT زنده ماژول هدف (حداکثر ۳–۵ مورد مستند در هر ربع): نقاط قوت داخلی (S)، نقاط ضعف کشف‌شده در این دور (W)، فرصت‌های ارتقای معماری/المنتور (O) و تهدیدهای رگرسیون/امنیت/عملکرد (T).

کنش TOWS (SO / WO / ST / WT): دقیقاً کدام اقدام مهندسی برای دور بعد از این SWOT استخراج می‌شود؟

ریشه‌یابی ۵-چرا (5-Whys RCA): برای مهم‌ترین باگ خوشه این دور، زنجیره علت ریشه‌ای را (با ارجاع به فایل و خط کد) بنویس تا اصلاح واقعی انجام شود نه ماست‌مالی.

ماتریس ریسک تغییر و رگرسیون: مشخص کن تغییر این دور کدام لایه‌ها (Inspector / Store / Canvas / AST / Sanitizer / Storefront) را لمس کرده و کدام تست رگرسیون آن را قفل کرده است.

۲.۶ قرارداد پورت سبک المنتور و المنتور پرو (حفظ سرعت Next.js و امنیت Python)
در وزنه‌های پورت المنتور: ابتدا کامپوننت‌های پایه مشترک (Group Controls، DimensionsControl با قفل ۴جهته و واحدهای px/em/rem/%/custom با توابع ریاضی CSS، و ScopedCssResolver با الگوی {{WRAPPER}}) را بساز و در همه ویجت‌ها بازاستفاده کن؛ هر ویجت تعاملی جدید را با next/dynamic کداسپلیت کن (ممنوعیت import *) تا باندل صفحات عمومی فروشگاه سنگین نشود؛ هر قابلیت جدید را هم‌زمان در هر ۴ لایه (Inspector ← Store ← CanvasFrame ← Python AST/Sanitizer) پیاده‌سازی کن و در html_sanitizer.py با Allowlist امن ضد XSS (برای SVG، Custom Attributes و Scoped CSS) قفل کن.

بخش ۳: نردبان وزنه‌های پیش‌رونده (Progressive Overload Levels — کل سایت + بیلدر + المنتور + صیقل بی‌نهایت)
وضعیت فعلی، جدول پوشش و defect_ledger را از .loop/DASHBOARD.md و .loop/state_ledger.json بخوان (اگر وجود ندارند آن‌ها را بساز و از وزنه ۱ شروع کن؛ اگر فایل قدیمی .loop/GYM_LOG.md وجود دارد، وضعیت آن را به state_ledger.json مهاجرت بده و فایل قدیمی را پاک نکن).
تا زمانی که تمام چک‌باکس‌ها و تمام عناصر SoM وزنه فعلی با صفر باگ P0/P1/P2 و تأیید ساب‌ایجنت qa-verifier پاک نشده‌اند، به وزنه بعدی نرو:

وزنه ۱ — ۵ کیلو: باگ‌های واضح، هیدراسیون، کرش‌ها و دکمه‌های مرده سطح اول
بررسی کامل (با SoM و حکم دوگانه جهش) روی صفحه اصلی /, صفحه لیست محصولات، یک صفحه محصول، /admin/themes، /admin/forms و ویرایشگر /e2e-isolated-scratchpad?builder=1.

شکار: تک‌تک دکمه‌ها و لینک‌های مرده/هاردکد (No-op)، رنگ‌های شفاف یا نامعتبر HSL/HEX در Light و Dark Mode، خطاهای کنسول مرورگر، خطاهای Hydration (#418/#423/#425)، درخواست‌های شبکه 4xx/5xx، دکمه‌های مخفی یا opacity-0 در LayersTree بدون هاور (موقعیت ماوس (0,0))، نوار ابزار بریده‌شده در سقف بوم CanvasFrame (toolbar.top < iframe.top)، کانتینرهای خالی نامرئی (حداقل ارتفاع 80px + کادر خط‌چین)، window.alert/confirm بومی و سرریز افقی (scrollWidth > clientWidth).

وزنه ۲ — ۱۵ کیلو: ممیزی ۳۶۰ درجه و تکان دادن تک‌تک کنترل‌های Visual Page Builder
تست واقعی تک‌به‌تک (SoM + Active Nudge + pixelmatch 0.05 بدون force: true) روی همه تب‌های BlocksPalette (بلوک‌ها، ۲۸ الگو، قالب‌های من)، درج دسته‌به‌دسته همه ۳۵ ویجت و ۲۸ الگو و تست تک‌تک گزینه‌های هر سه تب InspectorPanel (Content / Style / Advanced) برای کشف هر گزینه هاردکد، خالی، بی‌اثر یا خراب‌کننده.

تست واقعی Token Picker (اثبات تغییر getComputedStyle داخل CanvasFrame + pixelmatch + Vision)، تمام <input type="color"> (toValidHexColor بدون پرش به #000000)، Global Styles + دکمه Reset، Media Library Picker، Undo/Redo، Copy/Paste (Ctrl+C/V)، ذخیره پیش‌نویس، Reload کامل و مقایسه چشمی بوم با رندر عمومی صفحه (SSR Parity).

وزنه ۳ — ۲۵ کیلو: تعاملات پیچیده، Drag & Drop، ویجت‌های فروشگاهی و فرم‌ساز
تست واقعی درگ بلوک از سایدبار به بوم (@dnd-kit بدون force: true)، جابه‌جایی المان بین دو کانتینر تودرتو، جلوگیری از Circular Drop، باز و بسته کردن شاخه‌ها و حذف/تکثیر در LayersTree، Multi-Select، Global/Synced Components، ذخیره و ایمپورت Full Page Template و Section Template.

تست نمایش شرطی (authVisibility="authenticated") که بلوک مخصوص اعضا برای کاربر مهمان در HTML خروجی نشت نکند.

تست تعاملی با حکم دوگانه جهش روی ویجت‌های فروشگاه (ProductCard, ProductGrid فیلتر و صفحه‌بندی، ImageGallery + Lightbox، QuickViewModal، انتخاب ProductVariants، MiniCart/CartSummary، MegaMenu با کیبورد) و ارسال یک فرم واقعی ساخته‌شده با Form Builder و دیده شدن آن در /admin/forms.

وزنه ۴ — ۴۰ کیلو: ریسپانسیو موبایل/تبلت، Dark Mode کامل، RTL فارسی و WCAG 2.1 AA
اسکرین‌شات SoM و تحلیل بصری (Vision + سنسورهای هندسی) همه صفحات و مودال‌های باز در ۳ سایز: دسکتاپ (1440x900)، تبلت (768x1024) و موبایل (375x812) در هر دو حالت Light و Dark.

شکار: هم‌پوشانی متن‌های فارسی و آیکون‌ها در RTL، بریدگی دکمه‌ها یا جداول بدون اسکرول افقی، مودال‌های بیرون‌زده از صفحه موبایل، جهت اشتباه فلش‌ها در RTL، کنتراست ناکافی و تمام خطاهای critical و serious در AxeBuilder (wcag2a, wcag2aa, wcag21a, wcag21aa).

وزنه ۵ — ۵۵ کیلو: تست فشار، لبه‌های خرابی، کیفیت کد و پایداری پروداکشن
بارگذاری یک صفحه سنگین (۵۰+ المان تودرتو) در e2e-isolated-scratchpad و بررسی سرعت رندر، نبود کرش، نبود نشت حافظه یا رندرهای تکراری و صفر خطای Hydration.

بررسی حالات لبه (Edge Cases): قطعی شبکه حین Autosave (حفظ isDirty)، ورودی‌های خالی یا فارسی بسیار طولانی در فیلدها، کلون/بازگردانی ریویژن در /admin/themes، و یکدست‌سازی نهایی UI/UX در کل استودیو و فروشگاه.

وزنه ۶ — ۷۰ تا ۱۰۰ کیلو: پورت موج‌به‌موج قابلیت‌های مفقود المنتور و المنتور پرو (از C:\Users\Administrator\Desktop\elementor)
ابتدا مانیفست .loop/elementor_parity_manifest.json را از روی پوشه محلی بساز/به‌روز کن، سپس موج‌ها را به‌ترتیب با رعایت قرارداد سبک‌سازی (next/dynamic + {{WRAPPER}} + Sanitizer امن) و همین چرخه ۷ مرحله‌ای (SoM + Nudge + pixelmatch + Vision + SSR + Verifier) پیاده‌سازی و قفل کن:

موج ۶ الف (کنترل‌های حرفه‌ای Style/Advanced، Grid، اشکال جداکننده و Navigator): گروه‌های کنترل includes/controls/groups/ (Typography کامل، Background Classic/Gradient و Video/Slideshow در سطح کانتینر + Overlay + Blend Mode، Border و Box Shadow در حالت‌های Normal و Hover با Transition، Text Shadow/Stroke، CSS Filters)، تکمیل تب Advanced مطابق includes/widgets/common-base.php (واحدهای px/em/rem/%/custom با قفل ۴جهته، Transform، Mask، Sticky، Motion/Scroll Effects با احترام به prefers-reduced-motion، Custom Attributes key|value، Scoped Custom CSS ایمن)، کانتینر CSS Grid کامل، ۳۰ جداکننده شکلی SVG از assets/shapes/*.svg و ارتقای LayersTree به Navigator کامل (تغییر نام با دابل‌کلیک، نشانگر وضعیت و منوی راست‌کلیک Copy/Paste/Reset Style).

موج ۶ ب (ویجت‌های کلیدی مفقود Core و Pro + پاپ‌آپ و Off-Canvas): پورت سبک با next/dynamic از includes/widgets/ و elementor-pro/modules/ (ویجت‌های Core: icon, icon_list, image_box, image_carousel, counter, progress_bar, testimonial, alert, toggle, menu_anchor, nested_tabs, nested_accordion, floating_bar/contact_buttons؛ ویجت‌های Pro: slides/nested_carousel, animated_headline, call_to_action, flip_box, price_table, price_list, hotspot, table_of_contents, progress_tracker, blockquote, share_buttons, lottie؛ و ماژول‌های off_canvas و popup_builder).

موج ۶ ج (سایت‌ساز، کیت سراسری و Import/Export): تکمیل ۱۲ تب Global Site Kit از core/kits/documents/tabs/ در global-styles-dialog.tsx، ماژول theme_builder (Header، Footer، Single Product، Product Archive، 404 با Display Conditions)، loop_builder (Loop Grid/Carousel متصل به داده واقعی + فیلتر)، فرم چندمرحله‌ای (multi_step_form)، Import/Export کامل JSON و گسترش کتابخانه الگوها.

وزنه ۷ — +۱۰ کیلو بی‌پایان (بازیابی‌شده از نسخه ۱.۱: صیقل میکرو-UX، پاک‌سازی P2/P3 و تعمق مداوم)
هر زمان وزنه‌های ۱ تا ۶ واقعاً پاک شدند، از زاویه یک کاربر وسواسی و سخت‌گیر جدید وارد کل بک‌لاگ P2/P3 و بخش‌های کمتر دیده‌شده شو: حالات Hover، فوکوس کیبورد (Tab/Shift+Tab/Escape)، پیام‌های خطا و Toast، سرعت بارگذاری و اندازه باندل (next/dynamic)، کیفیت میکروتایپوگرافی و فاصله‌گذاری فارسی؛ در هر دور نقص‌های ریز جدید شکار کن، اصلاح ریشه‌ای بزن و تست‌های Playwright را سخت‌گیرانه‌تر کن.

بخش ۴: چرخه اجباری ۷ مرحله‌ای در هر دور (با گیت‌های مکانیکی و داوری مستقل)
خواندن کارنامه و بررسی سلامت پایه (Baseline Smoke Check): .loop/DASHBOARD.md، .loop/state_ledger.json، .loop/LESSONS.md (در صورت وجود) و git log -5 --oneline را بخوان (تکرار کار حل‌شده ممنوع؛ اولویت اول با STEER.md). یک بررسی سریع سلامت روی سرور زنده (http://127.0.0.1:3000) بزن تا رگرسیون احتمالی از دور قبل همان ابتدا کشف شود.

ممیزی استاتیک + فهرست‌برداری SoM + تست تک‌به‌تک دوگانه + بازبینی چشمی Vision (before/): چک سریع سیم‌کشی (حداکثر ۲ دقیقه) روی کد بخش هدف (و مطالعه مرجع خواندنی المنتور در وزنه ۶) بزن؛ بلافاصله اسکریپت Playwright را برای تولید before_som.png + som_inventory.json، اجرای کلیک و تکان دادن واقعی روی ۱۰۰٪ شماره‌های هدف #1..#N، اجرای pixelmatch (0.05) و ۶ سنسور خرابی، و ذخیره mutation_report.json و عکس‌ها/برش‌های before/ در .loop/artifacts/gym/round-XXX/before/ اجرا کن. سپس الزاماً (رصدشده توسط هوک) حداکثر ۸ تا ۱۰ عکس/برش کلیدی پوشه before/ را مستقیماً با ابزار Read (Vision) باز کن، همه باگ‌های دیده‌شده (P0 تا P3) را در defect_ledger ثبت کن، تحلیل ۵-چرا و ماتریس ریسک را مشخص کن و یک خوشه کامل (۴ تا ۸ باگ هم‌ریشه P0/P1 یا یک بسته منسجم از وزنه ۶/۷) را برای این دور انتخاب کن.

اصلاح ریشه‌ای / پیاده‌سازی سبک کامل (در هر ۴ لایه): کل خوشه انتخابی را در لایه‌های مرتبط (UI/Inspector ← Store ← Canvas ← Python AST/Sanitizer) به‌صورت تمیز، بدون هاردکد و بدون استاب TODO اصلاح یا پیاده‌سازی کن.

عضله‌سازی تست (Regression Lock): برای هر باگ یا قابلیت این دور، حداقل یک assertion واقعی و دائمی (بدون force: true و بدون .skip) به Vitest / Pytest یا Playwright اضافه کن تا بازگشت آن غیرممکن شود.

ری‌بیلد پاک سرور زنده ویندوز: اسکریپت powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/loop/rebuild-and-verify.ps1 را اجرا کن تا کش .next پاک شود و نسخه تازه روی پورت ۳۰۰۰ بالا بیاید.

اثبات «بعد از اصلاح» با Vision + داوری ساب‌ایجنت ناظر + دروازه کامل تست‌ها: در قدم ۶A دقیقاً همان اسکریپت SoM و Nudge را روی سرور جدید اجرا کن، عکس‌ها و برش‌های after/ و diff.png را در .loop/artifacts/gym/round-XXX/after/ ذخیره کن، مستقیماً با ابزار Read (Vision) تصاویر before/ و after/ را کنار هم مقایسه کن و کل مجموعه تست‌ها را کامل اجرا کن (npx tsc --noEmit + کل npx vitest run + کل python -m pytest app/tests/unit + تست Playwright این دور). در قدم ۶B ساب‌ایجنت qa-verifier را با مسیر پوشه آرتیفکت‌های این دور فراخوانی کن تا هوک SubagentStop فایل verifier_verdict.json را ثبت کند؛ اگر حکم "REJECT" بود، ایرادهای اعلامی ناظر را رفع کن و مجدداً داوری بگیر. (قانون فرار از بن‌بست: اگر روی یک باگ خاص ۲ بار شکست خوردی، فقط تغییر همان باگ قفل‌شده را با git checkout -- . برگردان، علت دقیقش را در NEEDS_HUMAN.md و state_ledger.json ثبت کن و فوراً سراغ دسته بعدی برو.)

کامیت اتمیک، ثبت کارنامه تحلیلی (SWOT/TOWS/RCA) و به‌روزرسانی دفتر کل: کامیت تمیز و اتمیک (fix(gym-rXXX): ... یا feat(gym-rXXX): ...) روی شاخه فعلی ثبت کن؛ گزارش کامل دور (شامل جدول SoM #1..#N، خلاصه مقایسه چشمی Vision، تحلیل SWOT/TOWS/5-Whys/ماتریس ریسک، فایل‌های تغییریافته و تست‌های اضافه‌شده) را در .loop/rounds/round-XXX.md بنویس، .loop/state_ledger.json را آپدیت کن و .loop/DASHBOARD.md را فشرده (≤۱۵۰ خط) نگه دار. پس از پاک شدن وزنه‌های ۱ تا ۵ با صفر باگ P0/P1/P2 و ۱۰۰٪ تست سبز عبارت GYM_ALL_5_LEVELS_MASTERED را ثبت کن و وارد وزنه ۶ شو؛ پس از تکمیل وزنه‌های ۱ تا ۶ عبارت GYM_ALL_LEVELS_AND_ELEMENTOR_MASTERED را ثبت کن و وارد وزنه ۷ (صیقل بی‌نهایت) شو.