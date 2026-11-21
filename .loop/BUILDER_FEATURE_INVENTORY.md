# موجودی جامع قابلیت‌های صفحه‌ساز بصری (.loop/BUILDER_FEATURE_INVENTORY.md)
**وضعیت اعتبارسنجی**: مبتنی بر ممیزی دقیق سورس‌کد، کامپایلر سرور، استور، و آزمون‌های خودکار Playwright / Vitest  

---

## ۱. ویجت‌های بومی (Basic Widgets Inventory — ۳۴ مورد)

| ردیف | نام ویجت (Widget Type) | دسته‌بندی | کنترل‌های بازرس (Inspector) | رندر در بوم (Canvas) | کامپایلر سرور (AST Compiler) | وضعیت | شواهد تست |
|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|
| ۱ | `container` | Layout | چیدمان Flex/Grid، فاصله، Boxed Width | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r15.spec.ts` |
| ۲ | `section` | Layout | پدینگ پیش‌فرض، چیدمان ستونی | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r10.spec.ts` |
| ۳ | `columns` | Layout | گرید ۲ ستونه، ستون‌های مستقل | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۴ | `form_container` | Layout | آدرس ارسال، پیام‌های موفقیت و خطا | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r09.spec.ts` |
| ۵ | `heading` | Basic | متن، تگ H1-H6، سایز، رنگ | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r06.spec.ts` |
| ۶ | `text_editor` | Basic | ویرایش پاراگراف، ویرایش مستقیم (Inline) | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r06.spec.ts` |
| ۷ | `image` | Basic | آدرس عکس، متن جایگزین Alt، کلاس سفارشی | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r06.spec.ts` |
| ۸ | `button` | Basic | برچسب دکمه، لینک مقصد، تب جدید، عرض کامل | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r02.spec.ts` |
| ۹ | `spacer` | Basic | ارتفاع قابل تنظیم به پیکسل | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۱۰ | `divider` | Basic | ضخامت، نوع خط، استایل مارجین | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r15.spec.ts` |
| ۱۱ | `table` | Basic | سرستون‌ها، ردیف‌ها، کادربندی، هایلایت ستون | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r09.spec.ts` |
| ۱۲ | `form_input` | Basic | برچسب، نام فیلد، نوع ورودی، پلیس‌هولدر | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r09.spec.ts` |
| ۱۳ | `form_textarea` | Basic | برچسب، تعداد سطرهای پیام، نام فیلد | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۱۴ | `form_select` | Basic | برچسب، گزینه‌های کشویی | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۱۵ | `product_card` | Basic | نام کالا، قیمت حداقل/حداکثر، تصویر، امتیاز | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۱۶ | `product_grid` | Basic | دسته‌بندی، فیلتر پیش‌فرض، تعداد نمایش، صفحه‌بندی | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r18.spec.ts` |
| ۱۷ | `product_variants` | Basic | عنوان بخش، افزودن/حذف/ویرایش تنوع‌ها و قیمت | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r19.spec.ts` |
| ۱۸ | `product_price` | Basic | قیمت فروش، قیمت قبل تخفیف، واحد تومان | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۱۹ | `add_to_cart` | Basic | برچسب دکمه خرید، کنترل شمارنده تعداد | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۲۰ | `mini_cart` | Basic | برچسب سبد خرید، نشانگر شمارنده آیتم‌ها | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۲۱ | `cart_summary` | Basic | عنوان خلاصه، متن دکمه تسویه حساب | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r19.spec.ts` |
| ۲۲ | `form_checkbox` | Basic | برچسب قوانین، وضعیت پیش‌فرض، نام فیلد | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۲۳ | `form_radio` | Basic | برچسب گروه، لیست گزینه‌های رادیویی | ✅ کامل | ✅ کامل | **PASS** | `builder-xray.mjs` |
| ۲۴ | `accordion` | Basic | افزودن، ویرایش و حذف آیتم‌ها، پیش‌فرض باز | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r17.spec.ts` |
| ۲۵ | `tabs` | Basic | مدیریت تب‌ها، عناوین و محتوای تفکیک‌شده | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r15.spec.ts` |
| ۲۶ | `countdown` | Basic | تاریخ هدف، محاسبه روز/ساعت/دقیقه به فارسی | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r18.spec.ts` |
| ۲۷ | `video` | Basic | آدرس آپارات/یوتیوب/فایل مستقیم، پوستر | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r18.spec.ts` |
| ۲۸ | `icon_box` | Basic | آیکون، عنوان ویژگی، متن توضیحی | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r08.spec.ts` |
| ۲۹ | `social_links` | Basic | لیست پلتفرم‌ها (اینستاگرام، تلگرام و...) و لینک‌ها | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r15.spec.ts` |
| ۳۰ | `image_gallery` | Basic | مدیریت چند تصویر، متن Alt و لینک‌ها | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r15.spec.ts` |
| ۳۱ | `star_rating` | Basic | مقدار امتیاز، تعداد نظرات، نمایش عدد | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r19.spec.ts` |
| ۳۲ | `review_histogram` | Basic | میانگین، تعداد کل نظرات، توزیع ۵ ستاره | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r07.spec.ts` |
| ۳۳ | `recently_viewed` | Basic | عنوان بخش، سقف تعداد نمایش کالاهای اخیر | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r20.spec.ts` |
| ۳۴ | `mega_menu` | Basic | برچسب دکمه ناوبری، دسته‌بندی‌های چندستونه | ✅ کامل | ✅ کامل | **PASS** | `builder-gym-r20.spec.ts` |

---

## ۲. الگوهای آماده بلاک (Block Patterns Inventory — ۲۸ مورد)

| ردیف | نامک الگو (Pattern Slug) | عنوان الگو | دسته‌بندی | وضعیت رندر بوم | وضعیت خروجی نهایی | وضعیت | شواهد تست |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---|
| ۱ | `hero-banner` | بنر اصلی (هیرو) | بنر و هیرو | ✅ | ✅ | **PASS** | `builder-gym-r02.spec.ts` |
| ۲ | `text-marquee` | متن چرخشی تبلیغاتی | بنر و هیرو | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۳ | `feature-grid` | شبکه ویژگی‌ها | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۴ | `image-text` | تصویر و متن | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۵ | `stats-counter` | شمارنده آمار | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۶ | `icon-box-grid` | جعبه‌های مزایا و خدمات | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۷ | `author-bio` | کارت معرفی کارشناس / نویسنده | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۸ | `pull-quote` | نقل‌قول و پیام برجسته | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r08.spec.ts` |
| ۹ | `process-steps` | مراحل گام‌به‌گام خرید و تحویل | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r09.spec.ts` |
| ۱۰ | `product-showcase-cta` | معرفی محصولات با دکمه | محصولات | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۱۱ | `star-rating-display` | نمایش امتیاز ستاره‌ای | محصولات | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۱۲ | `review-histogram` | نمودار توزیع امتیاز | محصولات | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۱۳ | `product-card-grid` | ویترین ۳ تایی محصولات پرفروش | محصولات | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۱۴ | `image-gallery-showcase` | گالری ۴ تایی تصاویر محصول | محصولات | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۱۵ | `product-highlights` | ویژگی‌های برجسته کالا | محصولات | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۱۶ | `testimonials` | نظرات مشتریان | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۱۷ | `brand-logo-carousel` | گرید برندها و شرکای تجاری | بازاریابی | ✅ | ✅ | **PASS** | `builder-gym-r09.spec.ts` |
| ۱۸ | `faq-accordion` | سوالات متداول با آکاردئون | پشتیبانی | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۱۹ | `countdown-offer` | فروش ویژه با شمارنده معکوس | فروش و تخفیف | ✅ | ✅ | **PASS** | `builder-gym-r06.spec.ts` |
| ۲۰ | `discount-badge-banner` | نوار تخفیف با بَج درصد | فروش و تخفیف | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۲۱ | `alert-banner` | نوار اعلان فوری و جشنواره | بنر و هیرو | ✅ | ✅ | **PASS** | `builder-gym-r07.spec.ts` |
| ۲۲ | `mega-menu-categories` | دسته‌بندی محصولات مگامنو | ناوبری | ✅ | ✅ | **PASS** | `builder-gym-r08.spec.ts` |
| ۲۳ | `pricing-table` | جدول ۳ تایی قیمت‌گذاری | قیمت‌گذاری | ✅ | ✅ | **PASS** | `builder-gym-r08.spec.ts` |
| ۲۴ | `price-list` | لیست قیمت خطی خدمات | قیمت‌گذاری | ✅ | ✅ | **PASS** | `builder-gym-r08.spec.ts` |
| ۲۵ | `comparison-table` | جدول مقایسه مشخصات فنی | محتوا | ✅ | ✅ | **PASS** | `builder-gym-r09.spec.ts` |
| ۲۶ | `support-callout` | کادر تماس و مشاوره قبل از خرید | پشتیبانی | ✅ | ✅ | **PASS** | `builder-gym-r08.spec.ts` |
| ۲۷ | `lead-capture-form` | فرم جذب سرنخ و مشاوره | فرم‌ها | ✅ | ✅ | **PASS** | `builder-gym-r09.spec.ts` |
| ۲۸ | `floating-contact-bar` | نوار ارتباطی چندکاناله | پشتیبانی | ✅ | ✅ | **PASS** | `builder-gym-r09.spec.ts` |

---

## ۳. کنترل‌های بازرس (Inspector Controls Matrix)

### ۳.۱. زبانه محتوا (Content Tab)
- ویرایشگر متن و تیترها: **PASS**
- انتخابگر آیکون و فایل رسانه: **PASS**
- فرم‌های داینامیک جدول و ستون‌ها: **PASS**
- تنظیمات شمارنده معکوس و تاریخ هدف: **PASS**
- مدیریت تنوع‌ها و قیمت‌های کالا: **PASS**

### ۳.۲. زبانه استایل (Style Tab)
- ابعاد، عرض سفارشی و چیپ‌های ریسپانسیو: **PASS**
- پس‌زمینه ۳ حالته (رنگ، گرادیانت چندجهته، تصویر): **PASS**
- فاصله‌گذاری خارجی و داخلی (Padding / Margin) با کلید لینک: **PASS**
- کادر، ضخامت، رنگ و گردی گوشه‌ها (Border Radius): **PASS**
- سایه کادر (Box Shadow) با پریست‌های آماده: **PASS**
- فیلترهای گرافیکی CSS (Blur, Grayscale, Contrast, Sepia): **PASS**
- لایه رویی پس‌زمینه کانتینر (Background Overlay): **PASS**

### ۳.۳. زبانه پیشرفته (Advanced Tab)
- انیمیشن‌های ورود (Fade In, Slide Up, Zoom In): **PASS**
- نمایش شرطی دستگاهی (Desktop, Tablet, Mobile): **PASS**
- نمایش شرطی احراز هویت (همه، کاربران واردشده، مهمان): **PASS**
- شناسه و کلاس سفارشی CSS (Anchor & Custom CSS): **PASS**
- کامپوننت سراسری و تفکیک (Global Component Sync & Detach): **PASS**
