# کارنامه حلقه پیوسته خودترمیمی Visual Page Builder (BUILDER GYM)

> وضعیت شاخه: ایزوله (غیر از `main`)
> هدف: ممیزی ۳۶۰ درجه (Nudge + Vision + SSR Parity) در وزنه‌های ۱ تا ۵ و سپس پورت سبک المنتور و المنتور پرو در وزنه‌های ۶ تا ۸.

## جدول پوشش جامع (Coverage Matrix)

### وزنه‌ها (Progress Ladder)
- [x] **وزنه ۱ — ۵ کیلو**: اسکلت استودیو، دکمه‌های نوار ابزار، درخت لایه‌ها و بوم Iframe
- [x] **وزنه ۲ — ۱۵ کیلو**: ممیزی تکان‌دادنی (Nudge) تک‌تک کنترل‌های ۳ تب (Content / Style / Advanced) برای همه ۳۵+ ویجت
- [x] **وزنه ۳ — ۲۵ کیلو**: ممیزی تصویری و ساختاری ۲۸ الگوی آماده + پالت بلوک‌ها + Global Styles
- [x] **وزنه ۴ — ۴۰ کیلو**: تجربه واقعی المنتور (Drag & Drop، کپی/پیست، قالب‌ها و برابری کامل با SSR)
- [x] **وزنه ۵ — ۵۵ کیلو**: ریسپانسیو موبایل/تبلت، دارک‌مود کامل و تست فشار ۵۰+ المان
- [ ] **وزنه ۶ — ۷۰ کیلو**: پورت المنتور موج ۱ (گروه‌های کنترل Style، تکمیل Advanced، کانتینر Grid، اشکال جداکننده SVG، Navigator کامل)
- [ ] **وزنه ۷ — ۸۵ کیلو**: پورت المنتور موج ۲ (ویجت‌های Core مفقود، ویجت‌های Pro، Off-Canvas و Popup Builder)
- [ ] **وزنه ۸ — ۱۰۰ کیلو**: پورت المنتور موج ۳ (۱۲ تب Global Site Kit، Theme Builder، Loop Builder، فرم چندمرحله‌ای، Import/Export JSON)

### پوشش ۳۵ ویجت اصلی (وزنه ۲)
#### ۱۰ ویجت پایه
- [x] `container` (Content / Style / Advanced)
- [x] `section` (Content / Style / Advanced)
- [x] `columns` (Content / Style / Advanced)
- [x] `heading` (Content / Style / Advanced)
- [x] `paragraph` (Content / Style / Advanced)
- [x] `text` / `text_editor` (Content / Style / Advanced)
- [x] `image` (Content / Style / Advanced)
- [x] `button` (Content / Style / Advanced)
- [x] `spacer` (Content / Style / Advanced)
- [x] `divider` (Content / Style / Advanced)

#### ۱۳ ویجت تعاملی و فرم
- [x] `table` (Content / Style / Advanced)
- [x] `form_container` (Content / Style / Advanced)
- [x] `form_input` (Content / Style / Advanced)
- [x] `form_textarea` (Content / Style / Advanced)
- [x] `form_select` (Content / Style / Advanced)
- [x] `form_checkbox` (Content / Style / Advanced)
- [x] `form_radio` (Content / Style / Advanced)
- [x] `accordion` (Content / Style / Advanced)
- [x] `tabs` (Content / Style / Advanced)
- [x] `countdown` (Content / Style / Advanced)
- [x] `video` (Content / Style / Advanced)
- [x] `icon_box` (Content / Style / Advanced)
- [x] `social_links` (Content / Style / Advanced)

#### ۱۲ ویجت فروشگاهی
- [x] `product_card` (Content / Style / Advanced)
- [x] `product_grid` (Content / Style / Advanced)
- [x] `image_gallery` (Content / Style / Advanced)
- [x] `star_rating` (Content / Style / Advanced)
- [x] `review_histogram` (Content / Style / Advanced)
- [x] `recently_viewed` (Content / Style / Advanced)
- [x] `mega_menu` (Content / Style / Advanced)
- [x] `product_price` (Content / Style / Advanced)
- [x] `product_variants` (Content / Style / Advanced)
- [x] `add_to_cart` (Content / Style / Advanced)
- [x] `mini_cart` (Content / Style / Advanced)
- [x] `cart_summary` (Content / Style / Advanced)

#### ۵ ویجت تکمیلی (Extra-5)
- [x] `product_title` (Content / Style / Advanced)
- [x] `code_highlight` (Content / Style / Advanced)
- [x] `breadcrumbs` (Content / Style / Advanced)
- [x] `search_bar` (Content / Style / Advanced)
- [x] `nav_menu` (Content / Style / Advanced)

### پوشش ۲۸ الگوی آماده (وزنه ۳)
- [x] دسته ۱ (الگوهای ۱ تا ۵)
- [x] دسته ۲ (الگوهای ۶ تا ۱۰)
- [x] دسته ۳ (الگوهای ۱۱ تا ۱۵)
- [x] دسته ۴ (الگوهای ۱۶ تا ۲۰)
- [x] دسته ۵ (الگوهای ۲۱ تا ۲۴)
- [x] دسته ۶ (الگوهای ۲۵ تا ۲۸)

### پوشش موج‌های المنتور (وزنه‌های ۶ تا ۸)
- [x] **موج ۱ (وزنه ۶)**: Typography Group, Background Group (Classic/Gradient/Video+Overlay+Blend), Border/BoxShadow Normal+Hover+Transition, Text Shadow/Stroke, CSS Filters, Advanced (Units px/em/rem/%, Transform, Mask, Sticky, Motion, Custom Attributes, Scoped Custom CSS), CSS Grid Container, 30 Shape Dividers SVG, Navigator کامل
- [ ] **موج ۲ (وزنه ۷)**: Core (`icon`, `icon_list`, `image_box`, `image_carousel`, `counter`, `progress_bar`, `testimonial`, `alert`, `toggle`, `menu_anchor`, `nested_tabs`, `nested_accordion`, `floating_bar`), Pro (`slides`/`nested_carousel`, `animated_headline`, `call_to_action`, `flip_box`, `price_table`, `price_list`, `hotspot`, `table_of_contents`, `progress_tracker`, `blockquote`, `share_buttons`, `lottie`), `off_canvas`, `popup_builder`
- [ ] **موج ۳ (وزنه ۸)**: 12 Site Kit Tabs, `theme_builder` (Header/Footer/Single Product/Product Archive/404 + Display Conditions), `loop_builder` (`loop_grid`/`loop_carousel`), `multi_step_form`, `import_export` JSON

---

## گزارش دورها (Rounds Log)

### دور ۱ (Round 01 — وزنه ۱: اسکلت استودیو، درخت لایه‌ها و بوم Iframe)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-01/before/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision: تورفتگی ترکیبی درخت لایه‌ها در عمق ۲ باعث فشردگی شدید برچسب‌ها تا عرض ۰ و شکسته شدن خطوط راهنما شده بود؛ واحدهای `px` روی برچسب عددی `Gap` و `Boxed Width` در جهت RTL روی عدد می‌افتاد؛ برچسب‌های `ContainerPresetPicker` بریده می‌شد؛ نوار ابزار موبایل ۳۷۵px سرریز داشت؛ کوتاه‌مدار کردن `e2e-isolated-scratchpad` مانع ثبت پیش‌نویس/انتشار واقعی و همگام‌سازی SSR می‌شد.
  - `after/`: `.loop/artifacts/builder-gym/round-01/after/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision: `toolbarTop: 8px` بدون بریدگی بالای بوم (`firstElTop: 48px`)، موبایل بدون سرریز افقی (`toolbarOverflow: false`)، درخت لایه‌ها در عمق‌های ۰/۱/۲ با عرض برچسب خوانا (`85/101/71px`) و آیکون‌های عملیاتی همیشه‌نمایان، جهت `ltr` تمیز روی ورودی‌های عددی `Gap` و `Boxed Width`، و رندر واقعی وضعیت پیش‌نویس/انتشار در DB و خروجی SSR.
- **فایل‌های اصلاح‌شده**:
  - `frontend/components/admin/builder/layers-tree.tsx` (تورفتگی RTL ۲۴px غیرترکیبی، تک‌خط راهنما، حذف بریدگی ردیف بیرونی)
  - `frontend/components/admin/builder/inspector-panel.tsx` (اعمال `dir="ltr"` روی رپر `Gap` و `Boxed Width`)
  - `frontend/components/admin/builder/canvas-frame.tsx` (فضای بالای بوم `48px` برای نوار ابزار شناور)
  - `frontend/components/admin/builder/canvas-overlay-layer.tsx` (چیدمان فشرده موبایل `< 460px` و مهار عرض/موقعیت نوار ابزار شناور)
  - `frontend/components/admin/builder/container-preset-picker.tsx` (تغییر گرید از ۳/۶ ستون به ۲/۳ ستون برای خوانایی برچسب‌ها)
  - `frontend/components/admin/builder/builder-studio.tsx` (`min-h-0` سایدبار و همگام‌سازی زنده `livePageStatus`)
  - `frontend/components/admin/builder/builder-toolbar.tsx` (افزودن `data-testid="page-status-badge"`)
  - `frontend/components/admin/builder/save-page-template-dialog.tsx` (ذخیره `templateMeta` در `builder_data`)
  - `frontend/app/(store)/[slug]/page.tsx` (حذف کوتاه‌مدار ثابت `e2e-isolated-scratchpad` و محدود کردن fallback فقط به خطای شبکه/API)
  - `frontend/tests/e2e/builder-gym-r01.spec.ts` (تکمیل تست‌های رگرسیون `1` تا `6` شامل موبایل ۳۷۵px، عمق ۲ درخت لایه‌ها، ذخیره پیش‌نویس/انتشار و SSR Parity)
  - `scripts/loop/rebuild-and-verify.ps1` (تطبیق پورت بک‌اند `:8000`)
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `67 passed (67)` — `452 passed (452)`
  - `python -m pytest app/tests/unit -q`: پاس (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts --reporter=list`: `7 passed (7)`

### دور ۲ (Round 02 — وزنه ۲ دسته ۱: ۱۰ ویجت پایه + کنترل‌های مشترک Style/Advanced و برابری SSR)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-02/before/` (۴ تصویر اولیه‌ با باگ Radix portal در `03` + `report.json` و ۶ تصویر کامل در اجرای تمیز: `01..06` + `report.json`) — مشاهده‌شده با Vision و تله‌متری Nudge:
    - خروجی SSR `/e2e-isolated-scratchpad` تحت `cleanHtml(page.body_html)` تقریباً تمامی استایل‌های رندرشده توسط `ASTCompiler` (`height` برای Spacer، `font-size`/`text-align`/`opacity`/`transform`/`filter`/`border-radius`، `hsl(var(--...))`، ویژگی‌های `data-*`، `button`/`svg`/`form`) را حذف می‌کرد.
    - `ASTCompiler` فقط `styles.mobile` را کامپایل می‌کرد و تمامی تغییرات `desktop`/`tablet` (از جمله حالت پیش‌فرض دسکتاپ استودیو) و ستون‌های `grid` را نادیده می‌گرفت، یا به دلیل inline `style` روی `mobile` مانع اعمال `@media (min-width: 1024px)` می‌شد.
    - در `canvas-element.tsx`: گرید دو ستونه (`columns`) درون Iframe باریک استودیو به جای `gridColumns` تکی ۱ ستونه (`622px`) رندر می‌شد؛ رنگ/وزن سرتیتر به دلیل `text-foreground`/`font-bold` به ارث نمی‌رسید؛ استایل سطح دکمه به جای `<a>` روی رپر بیرونی می‌رفت و `target="_blank"` تنظیم نمی‌شد؛ `.prose p` رنگ سفارشی را نادیده می‌گرفت.
    - `BorderStyleSchema` و `builder_ast.py` فیلد `radiusToken` را در Save Draft حذف می‌کردند؛ `divider` فاقد کنترل‌های ضخامت/عرض/رنگ/تراز در بازرس و فاقد اعمال استایل در SSR بود (`border-top-style` توسط allowlist بک‌اند حذف می‌شد).
  - `after/`: `.loop/artifacts/builder-gym/round-02/after/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision: بنر قرمز چرخان با شعاع گردی `16px`، `fontSize: 36px`، تراز `left` و `data-gym` در SSR، پاراگراف آبی `rgb(37, 99, 235)`، دکمه با `target="_blank"` و رنگ زرد `rgb(254, 240, 138)`، خط جداکننده نقطه‌چین `dashed` ۳px راست‌چین، فاصله‌ساز `96px` و گرید ۲ ستونه `colGridColsSsr: 2` با `0` خطای کنسول و شبکه.
- **فایل‌های اصلاح‌شده**:
  - `frontend/types/builder.ts`, `frontend/lib/builder/schema.ts`, `backend/app/modules/content/domain/builder_ast.py` (افزودن `radiusToken` / `radius_token` و حذف فیلد تکراری `box_shadow`)
  - `frontend/lib/sanitize-html.ts`, `frontend/app/(store)/[slug]/page.tsx` (افزودن `cleanBuilderHtml` ویژه خروجی `ASTCompiler` با حفظ کامل `cleanHtml` قبلی برای متون وبلاگ/CMS)
  - `frontend/components/admin/builder/inspector-panel.tsx` (تکمیل کنترل‌های `Divider` شامل سبک/ضخامت/عرض/رنگ/تراز، افزودن `data-testid` و رفع coercion ناخواسته `border.style: "solid"` هنگام تغییر `radiusToken`)
  - `frontend/components/admin/builder/canvas-element.tsx` (گرید ریسپانسیو درون بوم، وراثت تایپوگرافی `heading`/`text_editor`، تفکیک استایل سطح دکمه روی `<a>` + `target="_blank"`، رندر کامل `divider`)
  - `backend/app/modules/content/application/ast_compiler.py` (کامپایل `@media` برای `tablet`/`desktop`/`grid`/`hover` و انتقال `mobile` به CSS پایه هنگام وجود override واکنش‌گرا، پشتیبانی `newTab` دکمه، ترکیب سبک‌های `divider`/`spacer` با allowlist بک‌اند و اصلاح `dir_map` گرادیانت)
  - تست‌های رگرسیون: `backend/app/tests/unit/test_ast_compiler.py` (+۲ تست)، `frontend/tests/builder-gym-r02-unit.test.ts` (+۲ تست)، `frontend/tests/e2e/builder-gym-r02.spec.ts`
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `68 passed (68)` — `454 passed (454)`
  - `python -m pytest app/tests/unit`: `661 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts tests/e2e/builder-gym-r02.spec.ts --workers=1 --reporter=list`: `8 passed (8)`

### دور ۳ (Round 03 — وزنه ۲ دسته ۲: ۱۳ ویجت تعاملی و فرم + رانتایم تعاملی SSR)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-03/before/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision و Nudge:
    - ویجت `video` هنگام درج پیش‌فرض آدرس `dummy` آپارات را صدا می‌زد و خطای HTTP 404 تولید می‌کرد؛ همچنین لینک‌های عادی YouTube (`watch?v=...` / `youtu.be/`) و Aparat (`/v/...`) به `/embed/` تبدیل نمی‌شدند و در بوم خطای `X-Frame-Options` و در SSR حذف کامل توسط `_EMBED_HOSTS` رخ می‌داد.
    - ویجت `tabs` و `nested_tabs` در خروجی SSR فاقد هرگونه منطق جاوااسکریپت برای تعویض تب بودند (`ssrTab2Switched: false`).
    - ویجت `form_container` فاقد دکمه `type="submit"` در SSR و فاقد پیش‌نمایش دکمه ارسال و رانتایم AJAX برای ارسال بدون ریلود صفحه بود؛ `form_checkbox`/`form_radio` در SSR نشانگر الزامی (`*`) نداشتند و `form_radio` گزینه‌های جداشده با کاما (`،` / `,`) را تجزیه نمی‌کرد.
    - ویجت `icon_box` در بوم آیکون `<Sparkles>` را هاردکد کرده و انتخاب کاربر را نادیده می‌گرفت و در SSR ایموجی ثابت رندر می‌کرد؛ `accordion` در SSR علامت `"▾"` به جای آیکون SVG داشت؛ `social_links` در SSR فاقد آیکون SVG بود و `countdown` به دلیل `datetime` بدون timezone وارد `except` شده و استاتیک می‌ماند و `table` خطوط سلولی را با toggle تغییر نمی‌داد.
  - `after/`: `.loop/artifacts/builder-gym/round-03/after/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision: صفر خطای کنسول و شبکه، درج `video` بدون درخواست 404 و تبدیل خودکار YouTube `watch?v=...` به `embed/` در بوم و SSR، تغییر واقعی آیکون `icon_box` به آیکون SVG کامیون (`truck`)، رندر آیکون SVG برای `social_links` و `accordion`، شمارنده زنده فارسی `countdown`، تعویض فعال تب ۲ در خروجی SSR (`نقد راند۳`)، جداسازی ۳ گزینه رادیویی با کاما + نمایش ستاره قرمز اجباری `*`، و ارسال واقعی فرم با نمایش بنر سبز تأییدیه («پیام شما در راند۳ ثبت شد!»).
- **فایل‌های اصلاح‌شده**:
  - `frontend/lib/builder/video-utils.ts` (تابع `normalizeVideoEmbedUrl` برای تبدیل لینک‌های YouTube و Aparat)
  - `frontend/lib/builder/block-registry.ts` (حذف URL ساختگی آپارات در `video` و افزودن `submit_label` / `show_submit` به `form_container`)
  - `frontend/components/admin/builder/inspector-panel.tsx` (کنترل‌های `submit_label`/`show_submit` فرم، `expired_text` شمارنده، تجزیه کاما و سویچ `required` رادیو، برچسب‌های مجزا برای شبکه/آدرس `social_links` و `data-testid`های ممیزی)
  - `frontend/components/admin/builder/canvas-element.tsx` (استفاده از `BuilderIconSvg` به جای `Sparkles`، نرمال‌سازی ویدئو، دکمه پیش‌نمایش فرم، ستاره `*` برای چک‌باکس/رادیو، خطوط واقعی `bordered`/`striped` جدول و شمارنده زنده)
  - `frontend/components/admin/builder/builder-interactive-runtime.tsx` و `frontend/app/(store)/[slug]/page.tsx` (رانتایم تعاملی کلاینت روی صفحات بیلدر SSR برای تب‌ها، شمارنده معکوس زنده فارسی و ارسال AJAX فرم به `/api/v1/content/forms/submit`)
  - `backend/app/modules/content/application/ast_compiler.py` و `backend/app/shared/content/html_sanitizer.py` (دکمه ارسال فرم، نرمال‌سازی YouTube/Aparat، SVG برای `icon_box`/`accordion`/`social_links`، رفع باگ timezone در `countdown`، صفت‌های تب/شمارنده و مجوزدهی امن آن‌ها)
  - تست‌های رگرسیون: `backend/app/tests/unit/test_ast_compiler.py` (+۱ تست)، `frontend/tests/builder-gym-r03-unit.test.ts` (+۴ تست)، `frontend/tests/e2e/builder-gym-r03.spec.ts`
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `69 passed (69)` — `458 passed (458)`
  - `python -m pytest app/tests/unit`: `662 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts tests/e2e/builder-gym-r02.spec.ts tests/e2e/builder-gym-r03.spec.ts --workers=1 --reporter=list`: `9 passed (9)`

### دور ۴ (Round 04 — وزنه ۲ دسته ۳: ۱۲ ویجت فروشگاهی + دارایی‌های تصویر و تعامل‌پذیری SSR)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-04/before/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision و Nudge:
    - فایل ناموجود `/placeholder.svg` در پیش‌فرض `image_gallery`، `mega_menu` و `image_carousel` منجر به ۴ خطای همزمان HTTP 404 و مربع‌های سفید خراب می‌شد.
    - در خروجی SSR، ویجت‌های `product_card` و `image_gallery` فاقد محدودیت عرض (`max-w-sm` / `max-w-md`) بودند و در نمای ۱۴۴۰px به شکل مربع عظیم تمام‌عرض کش می‌آمدند؛ همچنین خط فرار نقل‌قول در کانتینر نشانک‌های `product_card` باعث به‌هم‌ریختگی رندر شده بود.
    - ویجت‌های `mini_cart` (نادیده‌گرفتن `label`، سویچ `show_badge` و نبود آیکون SVG سبد)، `cart_summary` (نادیده‌گرفتن `title`، `button_label`، `checkout_url` و `show_discount` در SSR و نمایش همیشگی ردیف تخفیف در بوم)، `recently_viewed` (نادیده‌گرفتن `title` و رندرنکردن کارت‌ها در SSR)، `star_rating` (نمایش تنها ۱ ستاره به جای ۵ ستاره و بی‌توجهی به `showValue=false` و باگ مقدار `0`)، `product_price` (عدم اثر `show_discount=false` و باگ مقدار `0` در بوم)، `add_to_cart` (نبود انتخابگر تعداد و آیکون در SSR)، `mega_menu` (دکمه مرده بدون منو و آیکون)، `review_histogram` (تک‌نوار ثابت به جای توزیع ۵ ستاره و نبود `verifiedCount`) و `product_grid` (ناهمگامی انتخابگر فیلتر بازرس با بوم) اصلاح ریشه‌ای شدند.
  - `after/`: `.loop/artifacts/builder-gym/round-04/after/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision: صفر خطای کنسول و ۴۰۴، کارت محصول و گالری تصویر متناسب (`max-w-sm`/`max-w-md`) با پشته نشانک‌ها و تعویض زنده تصویر بندانگشتی گالری در SSR، ۵ ستاره رتبه‌بندی و مخفی‌سازی صحیح امتیاز در حالت `showValue=false`، نمودار توزیع ۵ ردیفی با خریدهای تأییدشده، بازشدن پنل دسته‌های `mega_menu`، همگام‌سازی انتخاب تنوع با دکمه خرید و افزایش زنده بج `mini_cart` در خروجی SSR.
- **فایل‌های اصلاح‌شده**:
  - `frontend/lib/builder/block-registry.ts`, `frontend/lib/builder/pattern-converter.ts` (حذف `/placeholder.svg` و تنظیم عنوان پیش‌فرض `recently_viewed`)
  - `frontend/components/admin/builder/inspector-panel.tsx` (افزودن `data-testid`های ممیزی، ورودی `verifiedCount`، رفع صفرشدن قیمت/امتیاز و اصلاح URL گالری)
  - `frontend/components/admin/builder/canvas-element.tsx` (همگام‌سازی فیلتر `product_grid` با بازرس، رندر شرطی ردیف تخفیف `cart_summary`، رفع مقدار `0` در `star_rating`/`product_price` و حذف `/placeholder.svg`)
  - `frontend/components/admin/builder/builder-interactive-runtime.tsx` (تعامل زنده SSR برای `image_gallery`، `mega_menu`، `product_grid`، `product_variants` و `add_to_cart` + `mini_cart`)
  - `backend/app/modules/content/application/ast_compiler.py` و `backend/app/shared/content/html_sanitizer.py` (بازنویسی رندر ۱۲ ویجت فروشگاهی، فرمت عددی فارسی، رفع خط فرار نشانک‌های `product_card` و مجوزدهی صفت‌های تعاملی)
  - تست‌های رگرسیون: `backend/app/tests/unit/test_ast_compiler.py` (+۱ تست)، `frontend/tests/builder-gym-r04-unit.test.ts` (+۲ تست)، `frontend/tests/e2e/builder-gym-r03.spec.ts` (تضمین صفر خطای خالص اپلیکیشن)، `frontend/tests/e2e/builder-gym-r04.spec.ts`
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `70 passed (70)` — `460 passed (460)`
  - `python -m pytest app/tests/unit`: `663 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts tests/e2e/builder-gym-r02.spec.ts tests/e2e/builder-gym-r03.spec.ts tests/e2e/builder-gym-r04.spec.ts --workers=1 --reporter=list`: `10 passed (10)`

### دور ۵ (Round 05 — وزنه ۲ Extra-5 + وزنه ۳: ۲۸ الگو، پالت بلوک‌ها، Global Styles و برابری H1 در SSR)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-05/before/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision و Nudge:
    - در `hero-banner` دکمه CTA سفید-روی-سفید (`bg-primary`) و هدینگ `h1` فاقد کنتراست صحیح پس‌زمینه بود؛ در `author-bio` فایل ناموجود `/placeholder-avatar.svg` تصویر آواتار را می‌شکست؛ در `review-histogram` فقط تک‌نوار ثابت تولید می‌شد و `mega-menu-categories` برش متن داشت.
    - دیالوگ `GlobalStylesDialog` بیرون از محدوده ارتفاع ویوپورت و بدون ذخیره CSS متغیرهای واقعی (`--primary-hex`, `--background-hex`, `--radius`) در خروجی کامپایلر AST بود.
    - در خروجی SSR، ویجت `code_highlight` کاراکترها را دوبار-escape می‌کرد (`&#x27;`) و دکمه کپی `.code-copy-btn` فاقد رانتایم کلیک بود؛ ویجت `nav_menu` چیدمان عمودی `flex-col` را اعمال نمی‌کرد؛ و `render_body` به‌صورت پیش‌فرض تمام `h1`های بیلدر (`product_title` و `hero-banner`) را به `h2` تنزل می‌داد.
  - `after/`: `.loop/artifacts/builder-gym/round-05/after/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision: تمام ۲۸ الگوی آماده با کنتراست صحیح (`text-primary-foreground`, `bg-primary-foreground text-primary`)، جایگزینی `/placeholder-about.svg` و ۵ ویجت `progress_bar` رندر شدند؛ `GlobalStylesDialog` در ویوپورت جا گرفت و `--primary-hex`/`--background-hex`/`backgroundColor` در `.builder-document` SSR اعمال شد؛ `code_highlight` بدون double-escape و با دکمه کپی زنده، `nav_menu` با `flex-col` و `<h1>` در `product_title` و `hero-banner` در SSR حفظ شد.
- **فایل‌های اصلاح‌شده**:
  - `frontend/components/admin/builder/global-styles-dialog.tsx`, `frontend/components/admin/builder/builder-studio.tsx`, `frontend/stores/builder-store.ts` (رفع ارتفاع و `z-[125]` دیالوگ استایل‌های سراسری، پاکسازی توکن‌های خالی و `revalidatePage` پیش از بستن ذخیره/انتشار)
  - `frontend/components/admin/builder/blocks-palette.tsx`, `frontend/lib/builder/block-registry.ts`, `frontend/lib/builder/pattern-converter.ts`, `backend/app/modules/content/domain/block_patterns.py` (`data-testid` جستجو، ثبت `product_title`، تصویر `/placeholder-about.svg`، هیستوگرام ۵ ردیفه، بسته‌بندی متنی `mega-menu-categories` و کنتراست `hero-banner`)
  - `frontend/components/admin/builder/canvas-element.tsx`, `frontend/components/admin/builder/inspector-panel.tsx`, `frontend/components/admin/builder/builder-interactive-runtime.tsx` (چیدمان عمودی `nav_menu`، حفظ رنگ سفارشی روی هدینگ/دکمه، `data-testid`های Extra-5 و `.code-copy-btn`)
  - `backend/app/modules/content/application/ast_compiler.py`, `backend/app/shared/content/html_sanitizer.py`, `backend/app/shared/content/render.py`, `backend/app/modules/content/api/routes.py` (کامپایل `globalStyles` به متغیرهای CSS، حفظ رنگ سفارشی در کامپایلر، ماسک `<pre>`/`<code>` در `Linker`، افزودن `data-widget="product_title"` و حفظ `<h1>` با `demote_h1=not has_builder_data`)
  - تست‌های رگرسیون: `backend/app/tests/unit/test_ast_compiler.py`, `frontend/tests/builder-gym-r05-unit.test.ts`, `frontend/tests/e2e/builder-gym-r05.spec.ts`
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `71 passed (71)` — `463 passed (463)`
  - `python -m pytest app/tests/unit`: `665 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts tests/e2e/builder-gym-r02.spec.ts tests/e2e/builder-gym-r03.spec.ts tests/e2e/builder-gym-r04.spec.ts tests/e2e/builder-gym-r05.spec.ts --workers=1 --reporter=list`: `11 passed (11)`

### دور ۶ (Round 06 — وزنه ۴: تجربه واقعی المنتور، Drag & Drop، قالب‌ها، کامپوننت سراسری و برابری authVisibility در SSR)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-06/before/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision و Nudge:
    - در `builder-context-menu.tsx`، کلیک روی «ذخیره به عنوان قالب...» تابع `closeMenu()` را صدا می‌زد که با `pos = null` باعث می‌شد `if (!pos || !activeElement) return null;` کل کامپوننت از جمله `SaveTemplateDialog` را فوراً unmount کند و هیچ دیالوگی باز نشود (`saveSecDialogVisible: false`).
    - در `layers-tree.tsx`، کلیک با کلید `Ctrl+Click` چندانتخابی انجام نمی‌داد (`multiSelectedIdsInLayers: ["el_e2etext1"]`) و منوی راست‌کلیک آن فاقد گزینه ذخیره قالب بخش بود.
    - در `canvas-overlay-layer.tsx`، خطای شرط `selectedRect.top` به جای `viewportTop` هنگام اسکرول بوم نوار ابزار شناور را از بالای کادر خارج می‌کرد و عرض زیاد نوار ابزار در میانه افقی مانع کلیک مستقیم روی المان هم‌جوار می‌شد.
    - در بک‌اند (`cms_page_service.py`)، متدهای `create_template`، `update_template` و `delete_template` فقط `db.flush()` می‌زدند و در پایان درخواست به‌خاطر شرط `session.new or session.dirty or session.deleted` در `get_db()` بی‌سروصدا rollback می‌شدند و هیچ قالب بخش یا برگه‌ای در دیتابیس باقی نمی‌ماند.
    - در خروجی عمومی SSR (`routes.py` و `frontend/app/(store)/[slug]/page.tsx`)، صفحات فقط یک بار با `is_authenticated=False` کامپایل می‌شدند و کاربران عضو واردشده نیز بلوک‌های `authenticated` را نمی‌دیدند و بلوک‌های `guest` به اشتباه برایشان نمایش داده می‌شد.
  - `after/`: `.loop/artifacts/builder-gym/round-06/after/` (۷ تصویر + `report.json`) — مشاهده‌شده با Vision:
    - Drag & Drop از پالت به بوم و جابه‌جایی در `LayersTree` بدون `force: true`، کپی/پیست استایل (`#dbeafe` پس‌زمینه)، چندانتخابی `Ctrl+Click`، بازشدن شفاف و کامل `SaveTemplateDialog` (`z-[125]`) از منوی راست‌کلیک بوم و `LayersTree`، ثبت پایدار قالب بخش و قالب برگه در PostgreSQL و نمایش در «قالب‌های من»، همگام‌سازی زنده و Detach کامپوننت سراسری و پنهان‌سازی/نمایش دقیق SSR برای مهمان (`06`) در برابر عضو واردشده (`07`) تأیید شد.
- **فایل‌های اصلاح‌شده**:
  - `frontend/components/admin/builder/builder-context-menu.tsx`, `frontend/components/admin/builder/save-template-dialog.tsx`, `frontend/components/admin/builder/save-page-template-dialog.tsx`, `frontend/components/admin/builder/blocks-palette.tsx` (جداکردن وضعیت `saveTemplateElement`، `z-[125]` و `builder:templates-updated`)
  - `frontend/components/admin/builder/layers-tree.tsx` (`Ctrl+Click` چندانتخابی و گزینه ذخیره قالب در منوی درخت لایه‌ها)
  - `frontend/components/admin/builder/canvas-overlay-layer.tsx`, `frontend/components/admin/builder/inspector-panel.tsx` (تثبیت موقعیت `viewportTop` و فشرده‌سازی عرض نوار ابزار شناور بوم و افزودن `data-testid="style-bg-color-input"`)
  - `backend/app/modules/content/application/cms_page_service.py` (`db.commit()` و `db.refresh()` واقعی در CRUD قالب‌ها)
  - `backend/app/modules/content/api/routes.py`, `frontend/app/(store)/[slug]/page.tsx` (`get_current_user_optional` و کامپایل زنده `is_authenticated=True` با fallback امن مهمان روی 401)
  - تست‌های رگرسیون: `frontend/tests/builder-gym-r06-unit.test.ts` (+۳ تست)، `backend/app/tests/unit/test_ast_compiler.py` (+۱ تست)، `backend/app/tests/unit/test_cms_page_builder_db.py` (+۱ تست)، `frontend/tests/e2e/builder-gym-r06.spec.ts`
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `72 passed (72)` — `466 passed (466)`
  - `python -m pytest app/tests/unit`: `667 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts tests/e2e/builder-gym-r02.spec.ts tests/e2e/builder-gym-r03.spec.ts tests/e2e/builder-gym-r04.spec.ts tests/e2e/builder-gym-r05.spec.ts tests/e2e/builder-gym-r06.spec.ts --workers=1 --reporter=list`: `12 passed (12)`

### دور ۷ (Round 07 — وزنه ۵: ریسپانسیو تبلت ۷۶۸ و موبایل ۳۷۵، دارک‌مود کامل، تست فشار ۶۰ المان تودرتو و حفظ isDirty روی خطای ۵۰۰)
- **وضعیت نردبان پایه**: `BUILDER_GYM_LEVELS_1_TO_5_CLEAN` — وزنه‌های ۱ تا ۵ همگی پاک و سبز شدند.
- **شاخه**: `fix/builder-gym-360`
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-07/before/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision و Nudge:
    - در `canvas-frame.tsx`، متغیرهای تم روشن لایه ۱ (`--background`, `--foreground`, `--card`, `--muted`, `--border`) با inline style روی `<html style>` داخل iframe نوشته می‌شدند و در حالت دارک‌مود قوانین `.dark` را خنثی می‌کردند؛ همچنین `MutationObserver` تنها کلاس و style والد را کپی می‌کرد بدون `syncStyles(doc)` (در نتیجه در دارک‌مود بوم Iframe کاملاً سفید `#ffffff` با متن سیاه می‌ماند: `03`).
    - در `ast_compiler.py`، مخفی‌سازی شرطی بر اساس دستگاه (`visible_on_mobile=False`, `visible_on_tablet=False`) صرفاً به کلاس‌های `max-md:hidden` و `md:max-lg:hidden` متکی بود که در Tailwind باندل فرانت‌اند تولید نشده بودند؛ در نتیجه المان مخفی در موبایل همچنان با `display: block` در SSR `375px` دیده می‌شد (`05`).
    - در `builder-studio.tsx`، خطای سرور `500` هنگام ذخیره پیش‌نویس یا انتشار پیام نادرست «اعتبارسنجی ساختار صفحه با خطا مواجه شد» را نشان می‌داد (`06`).
  - `after/`: `.loop/artifacts/builder-gym/round-07/after/` (۶ تصویر + `report.json`) — مشاهده‌شده با Vision:
    - در دارک‌مود استودیو (`03`) و دیالوگ (`04`) و خروجی SSR موبایل ۳۷۵px (`05`)، بوم Iframe اکنون هماهنگ با استودیو پس‌زمینه تیره (`rgb(11, 14, 13)`) و متن روشن (`rgb(242, 243, 242)`) دارد، ویجت مخفی در موبایل در خروجی SSR ۳۷۵px کاملاً حذف بصری می‌شود (`textDisplay: "none"`)، تغییرات breakpoint تبلت ۷۶۸px (`24px`, `#fef9c3`) و موبایل ۳۷۵px (`16px`, `#fee2e2`) در بوم و SSR برابرند، ۶۰ المان ۳-سطحی تودرتو بدون خطا و سرریز رندر و ذخیره می‌شوند، و روی خطای `500` سرور پیام صادقانه نمایش داده شده و `isDirty: true` حفظ می‌شود (`06`).
- **فایل‌های اصلاح‌شده**:
  - `frontend/components/admin/builder/canvas-frame.tsx` (حذف بازنویسی سطوح روشن هنگام فعال‌بودن `.dark` و فراخوانی `syncStyles(doc)` در `MutationObserver`)
  - `backend/app/modules/content/application/ast_compiler.py` (تولید صریح `@media ... { #id { display: none !important; } }` برای `visible_on_mobile`/`tablet`/`desktop` در `_collect_responsive_rules`)
  - `frontend/components/admin/builder/builder-studio.tsx` (تفکیک پیام خطای `ZodError` از خطای شبکه/سرور همراه با حفظ ویرایش‌ها)
  - تست‌های رگرسیون: `backend/app/tests/unit/test_ast_compiler.py` (+۱ تست)، `frontend/tests/builder-gym-r07-unit.test.ts` (+۱ تست)، `frontend/tests/e2e/builder-gym-r07.spec.ts`
- **نتایج راستی‌آزمایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `73 passed (73)` — `467 passed (467)`
  - `python -m pytest app/tests/unit`: `668 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts tests/e2e/builder-gym-r02.spec.ts tests/e2e/builder-gym-r03.spec.ts tests/e2e/builder-gym-r04.spec.ts tests/e2e/builder-gym-r05.spec.ts tests/e2e/builder-gym-r06.spec.ts tests/e2e/builder-gym-r07.spec.ts --workers=1 --reporter=list`: `13 passed (13)`

### دور ۸ (Round 08 — وزنه ۶: موج ۱ المنتور و المنتور پرو — تایپوگرافی، پس‌زمینه، هاور، فیلتر، استیکی، موشن، CSS اختصاصی، ۳۰ جداکننده SVG و ناویگیتور)
- **شاخه**: `fix/builder-gym-360`
- **مقایسه مرجع ↔ پیاده‌سازی (Elementor Wave 1)**:
  - **Typography Group (`typography.php`, `text-shadow.php`, `text-stroke.php`)**: کنترل‌های `fontFamily`، `fontSize` (با واحدهای `px/em/rem/vw`)، `fontStyle` (`normal/italic/oblique`)، `textTransform`، `textDecoration` (`none/underline/overline/line-through`)، `lineHeight`، `letterSpacing`، `wordSpacing`، اسلایدر/ورودی‌های ۴گانه `textShadow` (`H/V/Blur/Color`) و `textStroke` + `textStrokeColor` به بازرس، بوم و `ASTCompiler` (SSR) اضافه شدند.
  - **Background Group (`background.php`, `container.php`)**: حالت پس‌زمینه `video` (پشتیبانی MP4/WebM و YouTube/Aparat)، گرادیانت `linear`/`radial` + زاویه (`angle`)، تصویر `repeat`/`attachment`، `blendMode` در پس‌زمینه/روپوش/المان (`mix-blend-mode`) پیاده‌سازی شد. همچنین باگ ریشه‌ای حذف `background-image: linear-gradient(...)` در `html_sanitizer.py` (`ALLOWED_CSS_PROPERTIES`) ریشه‌کن شد.
  - **Border & Box Shadow Normal + Hover + Transition**: تب‌های عادی/هاور برای `border` و `boxShadow`، ورودی‌های ساخت‌یافته `H/V/Blur/Spread/Color` + `Outline/Inset`، کنترل‌های `hoverBackground` و `hoverFilter`، و رفع باگ `isHovered` در dependency array بوم (`canvas-element.tsx`) و کامپایل `@media/:hover` در `ast_compiler.py`. *(اسلایدشو گالری چندتصویری `background.php` و timestamp ویدئو عمداً به موج ۲/ویجت کاروسل سپرده شده تا بار روی هر کانتینر سبک بماند).*
  - **CSS Filters (`css-filter.php`)**: اسلایدرهای ۵گانه `blur`/`brightness`/`contrast`/`saturate`/`hue` با همگام‌سازی دوطرفه با `filter`.
  - **Advanced (Units, Sticky, Motion, Custom CSS)**: انتخابگر واحد `px/em/rem/%/vw/vh` روی Padding، Margin، Width، MinHeight، Typography، Gap و مختصات `Top/Bottom/Left/Right`؛ کنترل‌های `stickyMode`/`stickyOffset`/`stickyOn` (کامپایل‌شده به `@media` CSS در SSR)؛ `motionEffects` (`scrollParallax`/`scrollScale`/`scrollOpacity`/`mouseTrack`) با رانتایم مشترک (`motion-runtime.ts`) در بوم و SSR؛ و ویرایشگر `customCss` ایزوله (`selector` و `{{WRAPPER}}`) در تب پیشرفته و کامپایل ایمن در `<style data-builder-responsive="1">`.
  - **CSS Grid Container (`grid-container.php`)**: افزودن `gridRows`، `justifyItems`، `alignContent` در کنار `gridColumns`، `gridAutoFlow` و `Gap` چندواحدی.
  - **30 Shape Dividers SVG (`shapes.php`, `assets/shapes/*.svg`)**: استخراج ۲۹ شکل SVG المنتور + حالت `none` (۳۰ گزینه کامل) در منبع واحد فرانت‌اند (`shape-dividers.ts`) و بک‌اند (`shape_dividers.py`) با رندر inline `<svg><path fill=.../></svg>` قابل رنگ‌آمیزی، ارتفاع/عرض/قرینه‌سازی برای بالا و پایین و حذف بلاک تکراری از تب پیشرفته و جایگزینی کامل `<img src="/shapes/...">` سیاه‌رنگ.
  - **Navigator (`layers-tree.tsx`)**: برچسب‌های وضعیت زنده `S` (Sticky)، `M` (Motion) و `CSS` در ردیف درخت در کنار `expand-all-layers-btn` / `collapse-all-layers-btn`، فیلتر جست‌وجو، تغییرنام دابل‌کلیک، جابه‌جایی و منوی راست‌کلیک.
- **مقایسه چشمی (Vision)**:
  - `before/`: `.loop/artifacts/builder-gym/round-08/before/` (۴ تصویر + `report.json`) — مشاهده‌شده با Vision و Nudge: `shapeOptionCount: 5`؛ اشکال `clouds`/`zigzag` در بوم رندر نمی‌شدند (`canvasShapeEls: 0`) و در SSR با `<img src="/shapes/...">` به‌صورت کاملاً سیاه رندر می‌شدند و `shapeDividerColor` را نادیده می‌گرفتند (`imgBroken: 2, svgCount: 0`)؛ `html_sanitizer.py` گرادیانت پس‌زمینه را حذف می‌کرد (`04-ssr-before-parity.png` کاملاً سفید با تیتر محوشده)؛ کنترل‌های `fontStyle`/`wordSpacing`/`textStroke`، اسلایدرهای `CSS Filter`، تب `Hover`، `Sticky`، `Motion` و `Custom CSS` (`selector`) در UI/SSR غایب بودند.
  - `after/`: `.loop/artifacts/builder-gym/round-08/after/` (۵ تصویر + `report.json`) — مشاهده‌شده با Vision: `shapeOptionCount: 30`؛ نمایش دقیق جداکننده‌های `clouds` زمردی (`#10b981`) و `zigzag` کهربایی (`#f59e0b`) با inline `<svg>` (`ssrImgCount: 0, ssrSvgCount: 2`)؛ تیتر ایتالیک زیرخط‌دار با فاصله‌کلمات `4px` و دورخط سبز (`1px`)؛ اسلایدرهای فیلتر گرافیکی، تب هاور، کنترل‌های Sticky/Motion/Scoped CSS با حاشیه کهربایی `3px` در بوم و `05-ssr-after-parity.png` با گرادیانت کامل `135deg`، `position: sticky; top: 16px` و صفر خطای کنسول و شبکه.
- **فایل‌های ایجاد و اصلاح‌شده**:
  - `frontend/lib/builder/shape-dividers.ts`, `backend/app/modules/content/application/shape_dividers.py` (رجیستری یکپارچه ۲۹ SVG المنتور)
  - `frontend/lib/builder/motion-runtime.ts` (رانتایم مشترک اسکرول/ماوس موشن و پارسر/سازنده فیلتر CSS)
  - `frontend/components/admin/builder/wave1-controls.tsx`, `inspector-panel.tsx`, `canvas-element.tsx`, `layers-tree.tsx`, `builder-interactive-runtime.tsx`
  - `frontend/lib/builder/scoped-css.ts`, `frontend/types/builder.ts`, `frontend/lib/builder/schema.ts`, `frontend/lib/sanitize-html.ts`
  - `backend/app/modules/content/domain/builder_ast.py`, `builder_validation.py`, `application/ast_compiler.py`, `app/shared/content/html_sanitizer.py`
  - تست‌های رگرسیون: `frontend/tests/builder-gym-r08-unit.test.ts` (+۵ تست)، `backend/app/tests/unit/test_ast_compiler.py` (+۱ تست)، `frontend/tests/e2e/builder-gym-r08.spec.ts`
- **نتایج راستی‌آزمایی نهایی**:
  - `npx tsc --noEmit`: پاس (`exit 0`)
  - `npx vitest run`: `74 passed (74)` — `472 passed (472)`
  - `python -m pytest app/tests/unit`: `669 passed, 2 skipped` (`exit 0`)
  - `npx playwright test tests/e2e/builder-gym-r01.spec.ts ... builder-gym-r08.spec.ts --workers=1 --reporter=list`: `14 passed (14)`
