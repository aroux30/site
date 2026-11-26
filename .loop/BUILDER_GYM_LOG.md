# کارنامه حلقه پیوسته خودترمیمی Visual Page Builder (BUILDER GYM)

> وضعیت شاخه: ایزوله (غیر از `main`)
> هدف: ممیزی ۳۶۰ درجه (Nudge + Vision + SSR Parity) در وزنه‌های ۱ تا ۵ و سپس پورت سبک المنتور و المنتور پرو در وزنه‌های ۶ تا ۸.

## جدول پوشش جامع (Coverage Matrix)

### وزنه‌ها (Progress Ladder)
- [x] **وزنه ۱ — ۵ کیلو**: اسکلت استودیو، دکمه‌های نوار ابزار، درخت لایه‌ها و بوم Iframe
- [ ] **وزنه ۲ — ۱۵ کیلو**: ممیزی تکان‌دادنی (Nudge) تک‌تک کنترل‌های ۳ تب (Content / Style / Advanced) برای همه ۳۵+ ویجت
- [ ] **وزنه ۳ — ۲۵ کیلو**: ممیزی تصویری و ساختاری ۲۸ الگوی آماده + پالت بلوک‌ها + Global Styles
- [ ] **وزنه ۴ — ۴۰ کیلو**: تجربه واقعی المنتور (Drag & Drop، کپی/پیست، قالب‌ها و برابری کامل با SSR)
- [ ] **وزنه ۵ — ۵۵ کیلو**: ریسپانسیو موبایل/تبلت، دارک‌مود کامل و تست فشار ۵۰+ المان
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
- [ ] `product_card` (Content / Style / Advanced)
- [ ] `product_grid` (Content / Style / Advanced)
- [ ] `image_gallery` (Content / Style / Advanced)
- [ ] `star_rating` (Content / Style / Advanced)
- [ ] `review_histogram` (Content / Style / Advanced)
- [ ] `recently_viewed` (Content / Style / Advanced)
- [ ] `mega_menu` (Content / Style / Advanced)
- [ ] `product_price` (Content / Style / Advanced)
- [ ] `product_variants` (Content / Style / Advanced)
- [ ] `add_to_cart` (Content / Style / Advanced)
- [ ] `mini_cart` (Content / Style / Advanced)
- [ ] `cart_summary` (Content / Style / Advanced)

### پوشش ۲۸ الگوی آماده (وزنه ۳)
- [ ] دسته ۱ (الگوهای ۱ تا ۵)
- [ ] دسته ۲ (الگوهای ۶ تا ۱۰)
- [ ] دسته ۳ (الگوهای ۱۱ تا ۱۵)
- [ ] دسته ۴ (الگوهای ۱۶ تا ۲۰)
- [ ] دسته ۵ (الگوهای ۲۱ تا ۲۴)
- [ ] دسته ۶ (الگوهای ۲۵ تا ۲۸)

### پوشش موج‌های المنتور (وزنه‌های ۶ تا ۸)
- [ ] **موج ۱ (وزنه ۶)**: Typography Group, Background Group (Classic/Gradient/Video+Overlay+Blend), Border/BoxShadow Normal+Hover+Transition, Text Shadow/Stroke, CSS Filters, Advanced (Units px/em/rem/%, Transform, Mask, Sticky, Motion, Custom Attributes, Scoped Custom CSS), CSS Grid Container, 30 Shape Dividers SVG, Navigator کامل
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
