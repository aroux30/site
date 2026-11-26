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
- [ ] `container` (Content / Style / Advanced)
- [ ] `section` (Content / Style / Advanced)
- [ ] `columns` (Content / Style / Advanced)
- [ ] `heading` (Content / Style / Advanced)
- [ ] `paragraph` (Content / Style / Advanced)
- [ ] `text` / `text_editor` (Content / Style / Advanced)
- [ ] `image` (Content / Style / Advanced)
- [ ] `button` (Content / Style / Advanced)
- [ ] `spacer` (Content / Style / Advanced)
- [ ] `divider` (Content / Style / Advanced)

#### ۱۳ ویجت تعاملی و فرم
- [ ] `table` (Content / Style / Advanced)
- [ ] `form_container` (Content / Style / Advanced)
- [ ] `form_input` (Content / Style / Advanced)
- [ ] `form_textarea` (Content / Style / Advanced)
- [ ] `form_select` (Content / Style / Advanced)
- [ ] `form_checkbox` (Content / Style / Advanced)
- [ ] `form_radio` (Content / Style / Advanced)
- [ ] `accordion` (Content / Style / Advanced)
- [ ] `tabs` (Content / Style / Advanced)
- [ ] `countdown` (Content / Style / Advanced)
- [ ] `video` (Content / Style / Advanced)
- [ ] `icon_box` (Content / Style / Advanced)
- [ ] `social_links` (Content / Style / Advanced)

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
