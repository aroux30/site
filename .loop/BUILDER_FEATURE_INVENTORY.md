# موجودی جامع قابلیت‌های صفحه‌ساز بصری (.loop/BUILDER_FEATURE_INVENTORY.md)
**وضعیت اعتبارسنجی**: مبتنی بر سورس واقعی کد و تست‌های فعال E2E  
**آخرین بروزرسانی**: 2026-11-21  

---

## ۱. فهرست بلوک‌های پایه (Basic Blocks Registry - ۳۴ بلوک)

| ردیف | نام بلوک (Type) | دسته‌بندی | وضعیت | مسیر فایل | توضیحات و کنترل‌های اختصاصی |
|---|---|---|---|---|---|
| ۱ | `container` | layout | PASS | `frontend/lib/builder/block-registry.ts` | کانتینر فلکس/گرید، چیدمان ستونی، پریست‌های ۱ تا ۴ ستونه، حداقل ارتفاع |
| ۲ | `section` | layout | PASS | `frontend/lib/builder/block-registry.ts` | سکشن سرتاسری برای پس‌زمینه و گروه‌بندی با پدینگ پیش‌فرض |
| ۳ | `columns` | layout | PASS | `frontend/lib/builder/block-registry.ts` | چیدمان دو ستونه مساوی با کانتینرهای فرزند مستقل |
| ۴ | `heading` | basic | PASS | `frontend/lib/builder/block-registry.ts` | تیترهای H1 تا H6 با ویرایش مستقیم متن در بوم (Inline Editing) |
| ۵ | `text_editor` | basic | PASS | `frontend/lib/builder/block-registry.ts` | پاراگراف متن با پشتیبانی از استایل غنی، ویرایش مستقیم در بوم |
| ۶ | `image` | basic | PASS | `frontend/lib/builder/block-registry.ts` | تصویر با کتابخانه رسانه، نسبت تصویر، فیت، و متن جایگزین (Alt) |
| ۷ | `button` | basic | PASS | `frontend/lib/builder/block-registry.ts` | دکمه اقدام، انواع رنگ سازمانی، آیکون، عرض کامل و پیوند |
| ۸ | `spacer` | basic | PASS | `frontend/lib/builder/block-registry.ts` | فاصله‌ساز عمودی قابل تنظیم با اسلایدر ارتفاع |
| ۹ | `divider` | basic | PASS | `frontend/lib/builder/block-registry.ts` | خط جداکننده افقی ظریف با رنگ و استایل حاشیه |
| ۱۰ | `table` | basic | PASS | `frontend/lib/builder/block-registry.ts` | جدول داده با سطرهای متغیر، حالت راه‌راه و هایلایت ستون |
| ۱۱ | `form_container` | basic | PASS | `frontend/lib/builder/block-registry.ts` | نگه‌دارنده فرم متصل به بک‌اند با پشتیبانی از فیلدهای فرزند |
| ۱۲ | `form_input` | basic | PASS | `frontend/lib/builder/block-registry.ts` | فیلد ورودی متن فرم با برچسب و متن راهنما |
| ۱۳ | `form_textarea` | basic | PASS | `frontend/lib/builder/block-registry.ts` | متن چندخطی با تعداد سطرهای قابل تنظیم |
| ۱۴ | `form_select` | basic | PASS | `frontend/lib/builder/block-registry.ts` | منوی کشویی انتخاب گزینه‌ها |
| ۱۵ | `form_checkbox` | basic | PASS | `frontend/lib/builder/block-registry.ts` | چک‌باکس تایید قوانین با پیوند شرایط |
| ۱۶ | `form_radio` | basic | PASS | `frontend/lib/builder/block-registry.ts` | دکمه‌های رادیویی تک‌انتخابی |
| ۱۷ | `accordion` | basic | PASS | `frontend/lib/builder/block-registry.ts` | آکاردئون پرسش‌وپاسخ با باز/بسته شدن متحرک |
| ۱۸ | `tabs` | basic | PASS | `frontend/lib/builder/block-registry.ts` | تب‌های محتوایی افقی با پنل‌های اختصاصی |
| ۱۹ | `countdown` | basic | PASS | `frontend/lib/builder/block-registry.ts` | شمارنده معکوس پویا با تفاضل زمانی زنده و ارقام فارسی |
| ۲۰ | `video` | basic | PASS | `frontend/lib/builder/block-registry.ts` | پخش‌کننده ویدیو آپارات و MP4 مستقیم با کاور پوستر |
| ۲۱ | `icon_box` | basic | PASS | `frontend/lib/builder/block-registry.ts` | جعبه آیکون و عنوان با پس‌زمینه کارت و متن توصیفی |
| ۲۲ | `social_links` | basic | PASS | `frontend/lib/builder/block-registry.ts` | دکمه‌های شبکه‌های اجتماعی با آیکون‌های استاندارد |
| ۲۳ | `product_card` | basic | PASS | `frontend/lib/builder/block-registry.ts` | کارت هوشمند کالا با تصویر، عنوان، قیمت، امتیاز و افزودن به سبد |
| ۲۴ | `product_grid` | basic | PASS | `frontend/lib/builder/block-registry.ts` | شبکه محصولات فروشگاهی متصل به API با فیلتر دسته‌بندی و صفحه‌بندی |
| ۲۵ | `image_gallery` | basic | PASS | `frontend/lib/builder/block-registry.ts` | گالری چندتصویره شبکه‌ای با لایت‌باکس |
| ۲۶ | `star_rating` | basic | PASS | `frontend/lib/builder/block-registry.ts` | نمایش امتیاز ستاره‌ای ۵ ستاره با قابلیت سوئیچ نمایش عدد |
| ۲۷ | `review_histogram` | basic | PASS | `frontend/lib/builder/block-registry.ts` | نمودار میله‌ای توزیع امتیازهای خریداران |
| ۲۸ | `recently_viewed` | basic | PASS | `frontend/lib/builder/block-registry.ts` | ویجت کالاهای اخیراً مشاهده‌شده با فیلد سفارشی عنوان و تعداد نمایش |
| ۲۹ | `mega_menu` | basic | PASS | `frontend/lib/builder/block-registry.ts` | مگامنو ناوبری محصولات با کنترل عنوان کاتالوگ در بازرس |
| ۳۰ | `product_price` | basic | PASS | `frontend/lib/builder/block-registry.ts` | قیمت کالا با تخفیف، قیمت خط‌خورده و برچسب تومان |
| ۳۱ | `product_variants` | basic | PASS | `frontend/lib/builder/block-registry.ts` | مدیریت کامل افزودن و حذف تنوع‌های رنگ/سایز با قیمت‌های متفاوت |
| ۳۲ | `add_to_cart` | basic | PASS | `frontend/lib/builder/block-registry.ts` | دکمه مستقیم اتصال به سبد خرید با اکشن استور |
| ۳۳ | `mini_cart` | basic | PASS | `frontend/lib/builder/block-registry.ts` | خلاصه شناور سبد خرید با شمارنده نشانگر کالاها |
| ۳۴ | `cart_summary` | basic | PASS | `frontend/lib/builder/block-registry.ts` | خلاصه فاکتور و سبد خرید با ویرایشگر عنوان و دکمه پرداخت |

---

## ۲. فهرست الگوهای آماده (Block Patterns - ۲۸ الگو)
تمام ۲۸ الگوی آماده در `frontend/lib/builder/pattern-converter.ts` ثبت، به استایل‌های سازگار با AST ترجمه شده و در تست‌های X-Ray دارای `passed: true` هستند:
۱. `hero-banner` (بنر اصلی)
۲. `text-marquee` (متن چرخشی تبلیغاتی)
۳. `feature-grid` (شبکه ویژگی‌ها)
۴. `image-text` (تصویر و متن ترکیبی)
۵. `stats-counter` (شمارنده آمار و ارقام)
۶. `icon-box-grid` (جعبه مزایا و خدمات)
۷. `author-bio` (کارت معرفی نویسنده)
۸. `pull-quote` (نقل‌قول برجسته)
۹. `process-steps` (مراحل گام‌به‌گام خرید)
۱۰. `product-showcase-cta` (معرفی محصولات با دکمه)
۱۱. `star-rating-display` (نمایش امتیاز ستاره‌ای)
۱۲. `review-histogram` (نمودار توزیع رضایت)
۱۳. `recently-viewed-shelf` (ویترین کالاهای اخیر)
۱۴. `brand-marquee` (اسلایدر برندها)
۱۵. `faq-accordion` (سوالات متداول)
۱۶. `countdown-urgency` (شمارنده تخفیف ویژه)
۱۷. `lead-form-horizontal` (فرم تک‌خطی عضویت)
۱۸. `lead-form-card` (کارت فرم تماس)
۱۹. `pricing-comparison-table` (جدول مقایسه)
۲۰. `customer-testimonials-carousel` (نظرات مشتریان)
۲۱. `cta-fullwidth` (فراخوان تمام‌عرض)
۲۲. `newsletter-subscribe` (خبرنامه ایمیلی)
۲۳. `timeline-roadmap` (نقشه راه)
۲۴. `team-members-grid` (اعضای تیم)
۲۵. `video-testimonial` (ویدیوی معرفی)
۲۶. `trust-badges-row` (نشان‌های اعتماد الکترونیکی)
۲۷. `category-grid` (دسته‌بندی‌های کالا)
۲۸. `footer-sitemap` (نقشه پیوندهای فوتر)

---

## ۳. کنترل‌های بازرس (Inspector Controls)
- **محتوا (Content)**: ورودی متن، انتخاب تگ تیتر H1-H6، نوع دکمه، درج رسانه، فیلدهای فرم، گزینه‌های سلکت، آیتم‌های آکاردئون و تب‌ها.
- **استایل (Style)**:
  - پدینگ و مارجین ۴ جهته تفکیک‌شده و متصل با قفل پیوند.
  - رنگ پس‌زمینه، گرادیان‌های ۲ رنگ در جهات مختلف، تصویر پس‌زمینه با اندازه و موقعیت.
  - حاشیه (Border)، ضخامت، استایل‌های Solid/Dashed/Dotted، شعاع گوشه‌ها (Border Radius) با توکن‌ها و ورودی‌های پیکسلی.
  - سایه کادر (Box Shadow) با پریست‌های xs تا xl و حالت سفارشی.
  - تایپوگرافی کامل: فونت، اندازه با واحد px/rem، وزن فونت ۱۰۰ تا ۹۰۰، فاصله خطوط و تراز متن.
  - فیلترهای بصری CSS: Blur, Brightness, Contrast, Grayscale, Invert.
  - استایل Overlay پس‌زمینه (Background Overlay) با ماتریال Glassmorphism و تاری پشت‌زمینه (Backdrop Blur).
  - جداکننده‌های شکل بوم (Shape Dividers) بالا و پایین: Waves, Curve, Triangle, Tilt با انتخاب رنگ زنده.
- **پیشرفته (Advanced)**:
  - انیمیشن‌های ورود (Fade In, Slide Up, Zoom In).
  - کنترل‌های دید دستگاهی (مخفی‌سازی انتخابی در دسکتاپ، تبلت و موبایل با نشانگر زنده در بوم).
  - کامپوننت‌های همگام سراسری (Global Components).
  - کلاس‌های سفارشی CSS و شناسه اختصاصی المان.
