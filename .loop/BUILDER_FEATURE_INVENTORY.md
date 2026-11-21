# Visual Page Builder — Feature Inventory

**Audit Date**: 2026-11-21  
**Total Blocks**: 34  
**Total Patterns**: 28  
**Total Inspector Controls**: 52+  
**Status Legend**:
- `PASS`: Verified working in UI, AST, and rendering.
- `PARTIAL`: Partially functional; minor gaps or edge cases exist.
- `FAIL`: Broken or produces reproducible error.
- `UNVERIFIED`: Not yet verified in real browser interaction.

---

## 1. Widget & Block Inventory (34 Blocks)

### 1.1 Layout Blocks
| # | Block Name | Type | Key Features | Status |
|---|------------|------|--------------|--------|
| 1 | كانتینر (Container) | `container` | Flex/Grid, Direction, Wrap, Gap, Padding, Boxed Width | **PASS** |
| 2 | بخش کامل (Section) | `section` | Full-width container with default padding | **PASS** |
| 3 | دو ستونه (2 Columns) | `columns` | Grid layout preset with 2 equal column containers | **PASS** |
| 4 | فرم سازنده (Form Container) | `form_container` | Dedicated form wrapper with submission endpoint | **PASS** |

### 1.2 Basic Content Blocks
| # | Block Name | Type | Key Features | Status |
|---|------------|------|--------------|--------|
| 5 | سرتیتر (Heading) | `heading` | H1–H6 tags, font size, weight, inline editing | **PASS** |
| 6 | پاراگراف متن (Paragraph) | `text_editor` | Rich HTML text, typography, color, inline editing | **PASS** |
| 7 | تصویر (Image) | `image` | URL, Alt, rounded border, object-fit, custom classes | **PASS** |
| 8 | دکمه اقدام (Button) | `button` | Label, URL, primary/secondary variants, full-width | **PASS** |
| 9 | فاصله خالی (Spacer) | `spacer` | Vertical space generator (height in px) | **PASS** |
| 10 | خط جداکننده (Divider) | `divider` | Style (solid/dashed/dotted), width, color, height | **PASS** |
| 11 | جدول داده (Table) | `table` | Header columns, rows, cell formatting, column highlight | **PASS** |

### 1.3 Interactive & Form Fields
| # | Block Name | Type | Key Features | Status |
|---|------------|------|--------------|--------|
| 12 | فیلد ورودی متن (Input) | `form_input` | Text/email/tel/number, placeholder, required flag | **PASS** |
| 13 | متن چندخطی (Textarea) | `form_textarea` | Rows, placeholder, required validation | **PASS** |
| 14 | منوی انتخابی (Select) | `form_select` | Dynamic options array, placeholder, value | **PASS** |
| 15 | چک‌باکس (Checkbox) | `form_checkbox` | Checkbox toggle, label, default checked | **PASS** |
| 16 | دکمه رادیویی (Radio) | `form_radio` | Group name, options array | **PASS** |
| 17 | آکاردئون (Accordion) | `accordion` | Collapsible items, default open, multi-expand | **PASS** |
| 18 | زبانه‌ها (Tabs) | `tabs` | Tab headers, tab panels, active state | **PASS** |
| 19 | شمارش معکوس (Countdown) | `countdown` | Target date/time, days/hours/minutes/seconds slots | **PASS** |
| 20 | پخش‌کننده ویدیو (Video) | `video` | Aparat / MP4 embed, aspect ratio, controls | **PASS** |
| 21 | جعبه آیکون (Icon Box) | `icon_box` | Icon picker, title, description, badge | **PASS** |
| 22 | پیوندهای اجتماعی (Social Links) | `social_links` | Telegram, Instagram, WhatsApp, Twitter, YouTube | **PASS** |
| 23 | گالری تصاویر (Image Gallery) | `image_gallery` | Multi-image grid, columns, lightbox preview | **PASS** |
| 24 | امتیاز ستاره‌ای (Star Rating) | `star_rating` | 1–5 stars, rating score display, review count | **PASS** |
| 25 | نمودار بازخوردها (Histogram) | `review_histogram` | 5-star distribution bars, percentages | **PASS** |
| 26 | دسته‌بندی مگامنو (Mega Menu) | `mega_menu` | Multi-level category hierarchy links | **PASS** |

### 1.4 E-commerce Native Blocks
| # | Block Name | Type | Key Features | Status |
|---|------------|------|--------------|--------|
| 27 | کارت محصول (Product Card) | `product_card` | Image, title, price, discount badge, buy button | **PASS** |
| 28 | شبکه محصولات (Product Grid) | `product_grid` | Query by category/tag, column count, pagination | **PASS** |
| 29 | متغیرهای محصول (Variants) | `product_variants` | Color & size selector, stock indicator | **PASS** |
| 30 | قیمت محصول (Product Price) | `product_price` | Regular price, sale price, Toman currency formatting | **PASS** |
| 31 | افزودن به سبد خرید (Add to Cart) | `add_to_cart` | Quantity stepper, animated cart button | **PASS** |
| 32 | پیش‌نمایش سبد خرید (Mini Cart) | `mini_cart` | Slide-over cart preview, item list, checkout CTA | **PASS** |
| 33 | خلاصه سفارش (Cart Summary) | `cart_summary` | Subtotal, discounts, shipping, final payable amount | **PASS** |
| 34 | محصولات اخیراً بازدیدشده | `recently_viewed` | LocalStorage tracking of viewed products | **PASS** |

---

## 2. Block Patterns Inventory (28 Patterns)

| # | Slug | Category | Title | Status |
|---|------|----------|-------|--------|
| 1 | `hero-banner` | بنر و هیرو | بنر اصلی فروشگاهی با دکمه اقدام و برچسب | **PASS** |
| 2 | `features-grid` | معرفی خدمات | گرید ۳ ستونه ویژگی‌ها و مزایای خرید | **PASS** |
| 3 | `product-showcase` | محصولات | معرفی محصول ویژه با عکس بزرگ و قیمت | **PASS** |
| 4 | `testimonials-carousel` | نظرات | کارت‌های رضایت مشتریان با آواتار و ستاره | **PASS** |
| 5 | `faq-accordion` | سوالات متداول | پرسش و پاسخ‌های متداول تاشو | **PASS** |
| 6 | `contact-form-card` | تماس | فرم تماس دو ستونه با نقشه و راه‌های ارتباطی | **PASS** |
| 7 | `countdown-sale` | تخفیف | بنر شمارش معکوس حراج شگفت‌انگیز | **PASS** |
| 8 | `stats-counter` | آمار | ارقام و دستاوردهای کلیدی فروشگاه | **PASS** |
| 9 | `gallery-masonry` | رسانه | گالری تصاویر شبکه با کادربندی منظم | **PASS** |
| 10 | `newsletter-box` | تعامل | باکس عضویت در خبرنامه با ایمیل و پیام تشکر | **PASS** |
| 11 | `pricing-table` | تعرفه | جدول ۳ ستونه تعرفه خدمات با برچسب محبوب‌ترین | **PASS** |
| 12 | `cta-banner` | فراخوان | بنر فوری اقدام به خرید با پس‌زمینه رنگی | **PASS** |
| 13 | `author-bio` | نویسنده | معرفی نویسنده یا مدیر با تصویر گرد و بیوگرافی | **PASS** |
| 14 | `steps-process` | راهنما | مراحل ۴ گانه فرآیند خرید تا تحویل | **PASS** |
| 15 | `comparison-table` | جدول | جدول مقایسه فنی ویژگی‌ها و پلن‌ها | **PASS** |
| 16 | `quote-box` | نقل قول | کادر نقل قول شاخص با خط حاشیه آغازین | **PASS** |
| 17 | `video-presentation` | ویدیو | معرفی ویدیویی با دکمه پخش و پوستر | **PASS** |
| 18 | `mega-menu-categories` | ناوبری | مگامنوی ناوبری دسته‌های اصلی با آیکون | **PASS** |
| 19 | `recently-viewed-shelf` | هوشمند | قفسه بازدیدهای اخیر کاربر | **PASS** |
| 20 | `lead-capture-form` | جذب سرنخ | فرم درخواست مشاوره رایگان با برچسب پاسخگویی | **PASS** |
| 21 | `support-contact-box` | پشتیبانی | کادر اطلاعات تماس فوری و ساعات پاسخگویی | **PASS** |
| 22 | `alert-notice-bar` | اعلان | نوار باریک هشدار جشنواره و اطلاعیه تخفیف | **PASS** |
| 23 | `social-proof-rating` | اعتماد | امتیاز کلی کاربران با هیستوگرام ستاره‌ها | **PASS** |
| 24 | `product-features-bullet` | محصول | مشخصات و مزایای برجسته کالا با تیک سبز | **PASS** |
| 25 | `partner-brands-grid` | برندها | لوگوی برندهای معتبر و همکاران تجاری | **PASS** |
| 26 | `store-quick-contact` | تماس | کارت ارتباط مستقیم با واتساپ و تلگرام | **PASS** |
| 27 | `products-grid-feed` | کالاها | ویترین ۴ ستونه جدیدترین محصولات | **PASS** |
| 28 | `discount-marquee` | تخفیف | نوار متحرک کدهای تخفیف جاری | **PASS** |

---

## 3. Inspector Controls Inventory

### 3.1 Content Tab
- Direct Text & Heading Tag (`h1`..`h6`)
- Links (`url`, `target="_blank"`)
- Image Picker & Dimensions (`width`, `height`, `alt`)
- Form Inputs (`placeholder`, `required`, `input_type`)
- Accordion & Tabs Item CRUD (Add, Rename, Delete, Reorder)
- Table Column & Row Editors

### 3.2 Style Tab
- Layout Direction (Row, Row-Reverse, Column, Column-Reverse)
- Alignment & Justification (Start, Center, End, Between, Stretch)
- Container Dimensions (Boxed vs Full Width, Custom Max-Width)
- Gaps (Grid / Flex gap with px/rem units)
- Backgrounds (Solid Color, Multi-Stop Gradient, Image)
- Background Overlay (Color, Opacity, Blend Mode)
- Typography (Font Family, Size, Weight, Line Height, Letter Spacing)
- Border & Border Radius (Linked / Unlinked 4 corners, Style, Color)
- Box Shadow (X, Y, Blur, Spread, Color, Inset)
- CSS Graphical Filters (Blur, Brightness, Contrast, Grayscale, Sepia)
- Opacity (0.0 to 1.0)
- Align-Self & Flex Order

### 3.3 Advanced Tab
- Responsive Device Visibility (`visibleOnDesktop`, `visibleOnTablet`, `visibleOnMobile`)
- Authentication Visibility (`all`, `authenticated`, `guest`)
- CSS Motion Effects & Animations (`fade-in`, `slide-up`, `zoom-in`, `duration`, `delay`)
- Global Component Sync (`globalComponentId`)
- Custom CSS ID (Anchor Navigation)
- Custom CSS Classes (`className` injection)
- Lock Element & Hide Element toggles
