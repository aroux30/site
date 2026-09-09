# 🛒 پرامپت مگا برای ساخت پلتفرم فروشگاهی کلاس جهانی

> این پرامپت را کامل کپی کن و به ChatGPT بده. خروجی: آرکیتکچر کامل + رودمپ اجرایی فاز‌بندی‌شده

---

## پرامپت شروع می‌شود 👇

---

تو یک Senior Solution Architect با بیش از ۱۵ سال تجربه در طراحی پلتفرم‌های e-commerce مقیاس‌پذیر هستی. من می‌خوام یک **پلتفرم فروشگاهی آنلاین حرفه‌ای و کلاس جهانی** بسازم که از نظر معماری، امنیت، مقیاس‌پذیری، UX/UI و قابلیت‌ها در سطح پلتفرم‌هایی مثل Shopify، Saleor، Medusa و دیجی‌کالا باشد.

---

## 🔧 مشخصات فنی پروژه (غیرقابل تغییر)

| آیتم | تکنولوژی |
|------|----------|
| **بک‌اند** | Python (FastAPI یا Django REST Framework — بهترین را انتخاب و دلیلش را بگو) |
| **فرانت‌اند** | Next.js 15 (App Router) + TypeScript + React 19 |
| **دیتابیس اصلی** | PostgreSQL 16 |
| **کش و صف** | Redis 7 (کش + Celery broker + session store) |
| **جستجو** | Elasticsearch یا Meilisearch (بهترین را انتخاب و دلیلش را بگو) |
| **فایل استوریج** | MinIO (S3-compatible) یا Local با CDN |
| **تسک‌های پس‌زمینه** | Celery + Redis |
| **دیپلوی** | سرور اوبونتو ۲۲/۲۴ + Docker Compose + Nginx + SSL (Let's Encrypt) |
| **CI/CD** | GitHub Actions |
| **مانیتورینگ** | Sentry + Prometheus + Grafana |

---

## 🏗️ بخش ۱: معماری سیستم (System Architecture)

لطفاً یک معماری کامل و جامع ارائه بده که شامل موارد زیر باشد:

### ۱.۱ — الگوی معماری کلان
- **Headless Commerce** architecture: فرانت‌اند و بک‌اند کاملاً مجزا با ارتباط از طریق REST API و/یا GraphQL
- توضیح بده چرا Headless بهتر از Monolithic است برای این پروژه
- دیاگرام متنی (ASCII/Mermaid) از معماری کلی سیستم بکش

### ۱.۲ — ساختار لایه‌ای بک‌اند
- **API Layer**: روتینگ، ولیدیشن ورودی، سریالایز خروجی
- **Service Layer**: تمام بیزینس لاجیک (هرگز در API مستقیم نباشد)
- **Repository Layer**: دسترسی به دیتابیس با الگوی Repository Pattern
- **Model Layer**: مدل‌های ORM (SQLAlchemy 2.0 async)
- **Schema Layer**: Pydantic v2 برای request/response validation
- **Core Layer**: احراز هویت، مجوزها، رمزنگاری، rate limiting، خطاها
- **Integration Layer**: اتصال به سرویس‌های خارجی (درگاه پرداخت، پیامک، ایمیل، CDN)
- **Worker Layer**: تسک‌های Celery پس‌زمینه

### ۱.۳ — ساختار لایه‌ای فرانت‌اند
- **App Router** ساختار Next.js 15 با Server Components و Client Components
- **Feature-based folder structure** (نه page-based)
- **State management**: Zustand یا React Context (بهترین را انتخاب کن)
- **API client layer**: با interceptor برای JWT refresh، retry، error handling
- **UI component library**: مبتنی بر shadcn/ui + Radix UI + Tailwind CSS
- **Animation layer**: Framer Motion برای micro-interactions و page transitions
- **Internationalization**: next-intl با پشتیبانی کامل RTL فارسی
- **SEO layer**: متاتگ‌ها، Structured Data (JSON-LD)، سایت‌مپ، robots.txt

### ۱.۴ — ساختار دیتابیس
- **ERD کامل** (Entity Relationship Diagram) به‌صورت متنی یا Mermaid
- ایندکس‌گذاری مناسب روی فیلدهای پرکاربرد
- استفاده از JSONB برای فیلدهای انعطاف‌پذیر (مثل attributes محصول)
- Soft delete برای همه موجودیت‌های تجاری
- Audit trail (created_at, updated_at, created_by)
- UUID v4 به‌عنوان primary key

---

## 🛍️ بخش ۲: فیچرهای فروشگاهی هسته‌ای (Core E-Commerce)

هر فیچر را با جزئیات کامل طراحی کن: مدل دیتابیس، API endpoints، بیزینس لاجیک، و ملاحظات فنی.

### ۲.۱ — مدیریت محصولات (Product Management)
- محصولات ساده و متغیر (با Variants: سایز، رنگ، مدل)
- SKU و بارکد یکتا
- دسته‌بندی درختی (Category Tree) با materialized path یا nested set
- برچسب‌ها (Tags) و ویژگی‌های فیلتر‌پذیر (Filterable Attributes)
- گالری تصاویر با crop، resize، WebP auto-conversion، lazy loading
- ویدیو محصول
- وضعیت انتشار: draft, published, archived, out_of_stock
- محصولات مرتبط و Cross-sell / Upsell
- مقایسه محصولات
- SEO metadata در سطح محصول (title, description, slug, canonical)
- بررسی و امتیازدهی (Reviews & Ratings) با moderation queue

### ۲.۲ — مدیریت موجودی (Inventory Management)
- موجودی در سطح Variant
- هشدار کمبود موجودی (Low Stock Alert) با threshold قابل تنظیم
- رزرو موجودی هنگام افزودن به سبد خرید (Stock Reservation با TTL)
- Track موجودی: backorder allowed, out of stock behavior
- تاریخچه تغییرات موجودی (Inventory Log)

### ۲.۳ — سبد خرید (Shopping Cart)
- سبد خرید برای کاربران لاگین‌شده (server-side) و مهمان (localStorage + merge on login)
- اعتبارسنجی real-time قیمت و موجودی
- TTL برای سبدهای رها‌شده (Abandoned Cart)
- ذخیره‌سازی در Redis برای سرعت + PostgreSQL برای دوام

### ۲.۴ — فرآیند خرید (Checkout Flow)
- Multi-step checkout: اطلاعات ارسال → روش ارسال → روش پرداخت → بررسی نهایی → تأیید
- Guest checkout (بدون نیاز به ثبت‌نام)
- محاسبه خودکار: مالیات، هزینه ارسال، تخفیف
- اعمال کد تخفیف با اعتبارسنجی real-time
- Idempotency key برای جلوگیری از پرداخت دوبله

### ۲.۵ — مدیریت سفارشات (Order Management)
- ماشین حالت سفارش (Order State Machine): pending → confirmed → processing → shipped → delivered → completed
- حالت‌های اضافی: canceled, refunded, partially_refunded, on_hold, returned
- Order timeline: لاگ هر تغییر وضعیت با timestamp و actor
- فاکتور PDF خودکار
- ارسال نوتیفیکیشن در هر مرحله (ایمیل + پیامک + push notification)
- Split orders (تقسیم سفارش بر اساس انبار یا فروشنده)

### ۲.۶ — سیستم پرداخت (Payment System)
- **درگاه‌های ایرانی**: زرین‌پال، آی‌دی‌پی، نکست‌پی (با الگوی Strategy Pattern — یک interface واحد، چندین provider)
- **کیف پول داخلی** (Wallet) با واریز، برداشت، و row-level locking برای جلوگیری از race condition
- **پرداخت ارز دیجیتال**: Plisio یا NowPayments (USDT, BTC) — با نرخ لحظه‌ای از صرافی (مثل Nobitex)
- **کارت به کارت**: آپلود رسید + تأیید ادمین
- تراکنش‌ها با audit trail کامل
- Refund flow: خودکار به کیف پول یا دستی به حساب بانکی

### ۲.۷ — سیستم تخفیف و کوپن (Discount & Coupon Engine)
- کد تخفیف درصدی و مبلغ ثابت
- محدودیت: حداکثر استفاده کل، حداکثر استفاده هر کاربر، تاریخ انقضا
- محدوده اعمال: کل سبد، دسته‌بندی خاص، محصول خاص، اولین خرید
- تخفیف خودکار (بدون کد): تخفیف روی قیمت محصول، فلش سیل، تخفیف تعدادی
- حداقل مبلغ سفارش برای اعمال تخفیف
- ترکیب‌پذیری تخفیف‌ها (stackable vs exclusive)

### ۲.۸ — سیستم ارسال (Shipping System)
- روش‌های ارسال: پست پیشتاز، پست سفارشی، اسنپ‌باکس، تیپاکس، ارسال اختصاصی
- محاسبه هزینه ارسال بر اساس: وزن، حجم، مقصد، روش ارسال
- ارسال رایگان با حداقل مبلغ خرید
- کد رهگیری مرسوله
- تخمین زمان تحویل

### ۲.۹ — جستجو و فیلتر (Search & Filter)
- Full-text search فارسی با stem و synonym
- Faceted search: فیلتر بر اساس قیمت، دسته‌بندی، برند، رنگ، سایز، امتیاز
- Auto-suggest / Autocomplete
- جستجوی هوشمند با NLP (تبدیل متن طبیعی فارسی به فیلترهای ساختاریافته)
- Search analytics: ثبت و تحلیل عبارات جستجو‌شده
- اولویت‌بندی نتایج: relevance, price, newest, bestseller, rating

### ۲.۱۰ — لیست علاقه‌مندی‌ها (Wishlist)
- اضافه/حذف محصول به لیست علاقه‌مندی
- نوتیفیکیشن هنگام تخفیف خوردن محصول wishlist
- اشتراک‌گذاری wishlist

---

## 👥 بخش ۳: سیستم کاربران و احراز هویت

### ۳.۱ — احراز هویت (Authentication)
- JWT access token (کوتاه‌مدت) + refresh token (بلندمدت با چرخش)
- ثبت‌نام با ایمیل/شماره‌موبایل + تأیید OTP
- لاگین با رمز عبور یا OTP (passwordless)
- Rate limiting روی endpoint‌های حساس
- brute-force protection با lockout
- ذخیره refresh token در HttpOnly cookie

### ۳.۲ — پروفایل کاربر
- اطلاعات شخصی، آواتار
- دفترچه آدرس (چند آدرس با انتخاب پیش‌فرض)
- تاریخچه سفارشات
- مدیریت کیف پول
- مدیریت wishlist
- تیکت‌های پشتیبانی
- نوتیفیکیشن‌ها

### ۳.۳ — سیستم نقش‌ها و مجوزها (RBAC)
- نقش‌ها: super_admin, admin, manager, editor, customer_support, accountant, customer
- مجوزهای گرانولار برای هر عملیات CRUD
- Dependency injection برای authorization

---

## 📈 بخش ۴: فیچرهای مارکتینگ و رشد (الهام از پروژه‌های موجود)

> این فیچرها از تجربه پروژه‌های VPN SaaS، پلتفرم SEO و CRM املاک استخراج شده‌اند و برای فروشگاه آنلاین آداپت شده‌اند.

### ۴.۱ — سیستم رفرال دو لایه (Two-Tier Referral System)
**الهام از پروژه VPN:**
- لایه ۱: کاربر معرف → پاداش ثابت هنگام ثبت‌نام + درصد کمیسیون از هر خرید کاربر معرفی‌شده
- لایه ۲: معرف معرف → پاداش ثابت + درصد کمیسیون (MLM یک‌سطحی)
- لینک رفرال یکتا برای هر کاربر
- داشبورد رفرال: تعداد دعوت‌ها، درآمد کمیسیون، نمودار رشد
- تنظیمات کامل: درصدها، مبالغ، فعال/غیرفعال — توسط ادمین

### ۴.۲ — سیستم کشبک (Cashback System)
**الهام از پروژه VPN:**
- درصد کشبک قابل تنظیم روی خریدها
- انتخاب حالت پاداش: واریز به کیف پول، هدیه محصول، یا ترکیبی
- کشبک متفاوت بر اساس روش پرداخت
- بونوس شارژ کیف پول (مثلاً ۱۰٪ اضافه هنگام شارژ)

### ۴.۳ — هدیه خوشامدگویی (Welcome Gift)
**الهام از پروژه VPN:**
- اعتبار هدیه به کیف پول هنگام اولین ثبت‌نام
- مبلغ قابل تنظیم توسط ادمین
- اعمال خودکار در اولین خرید

### ۴.۴ — گیمیفیکیشن (Gamification)
**الهام از پروژه VPN:**
- چرخ شانس / بازی تاس روزانه با جوایز: اعتبار کیف پول، کد تخفیف، ارسال رایگان
- محدودیت روزانه قابل تنظیم
- سطح‌بندی جوایز (Tier system)
- امتیاز وفاداری (Loyalty Points): کسب امتیاز از خرید، ریویو، رفرال → تبدیل به تخفیف

### ۴.۵ — پیام‌رسانی انبوه هدفمند (Broadcast Messaging)
**الهام از پروژه VPN:**
- ارسال ایمیل/پیامک/نوتیفیکیشن push به segmentهای مختلف:
  - همه کاربران
  - خریداران فعال
  - کاربران غیرفعال
  - سبدهای رها‌شده (Abandoned Cart Recovery)
  - کاربران wishlist محصول تخفیف‌خورده
- زمان‌بندی ارسال (Scheduled)
- A/B testing عنوان و محتوا

### ۴.۶ — سیستم SEO یکپارچه
**الهام از پروژه SEO OS:**
- SEO Score خودکار برای هر محصول و صفحه (مشابه Rank Math)
  - بررسی: کلمه کلیدی در عنوان، meta description، URL، تراکم کلمه کلیدی، هدینگ‌ها، لینک‌ها، مدیا، تعداد کلمات
  - نمره ۰ تا ۱۰۰ با راهنمای بهبود
- تولید خودکار meta title, description با AI
- سایت‌مپ XML خودکار
- Structured Data (JSON-LD) برای Product, BreadcrumbList, Organization, FAQ
- کنترل canonical URL
- آنالیز فرصت‌های SEO: محصولات با impression بالا ولی CTR پایین
- لینک‌سازی داخلی هوشمند بین محصولات مرتبط

### ۴.۷ — سیستم هشدار و مانیتورینگ هوشمند
**الهام از پروژه SEO OS:**
- هشدار افت ترافیک، افت رتبه، افت نرخ تبدیل
- هشدار کمبود موجودی
- هشدار سفارشات ناموفق
- مانیتورینگ uptime سایت
- نوتیفیکیشن چند‌کاناله: داشبورد + تلگرام + ایمیل

### ۴.۸ — داشبورد آنالیتیکس حرفه‌ای
**الهام از پروژه Real-Estate و SEO OS:**
- KPI ریل‌تایم: فروش امروز/هفته/ماه، تعداد سفارشات، نرخ تبدیل، میانگین ارزش سفارش
- نمودار روند فروش (ساعتی/روزانه/ماهانه)
- توزیع فروش بر اساس: دسته‌بندی، محصول، منطقه، روش پرداخت
- فانل خرید: بازدید → سبد → چک‌اوت → پرداخت → تحویل
- مقایسه دوره‌ای (Period-over-period comparison)
- تحلیل عرضه و تقاضا (Supply-Demand Gap) مثل پروژه املاک
- پروفایل عملکرد محصولات: بازدید، نرخ تبدیل، ارزش فروش، برگشتی‌ها

### ۴.۹ — Kanban Board برای مدیریت سفارشات
**الهام از پروژه Real-Estate:**
- تخته کانبان بصری برای مدیریت سفارشات در مراحل مختلف
- ستون‌ها: سفارش جدید → در حال پردازش → بسته‌بندی → ارسال‌شده → تحویل‌شده
- کارت‌های سفارش با اولویت‌بندی (urgent, normal)
- هشدار سفارشات راکد (stale orders)
- یادداشت و لاگ فعالیت روی هر سفارش

### ۴.۱۰ — تطبیق هوشمند (Smart Matching)
**الهام از پروژه Real-Estate:**
- تطبیق هوشمند محصول-مشتری: وقتی محصول جدید اضافه شود، به مشتریانی که در wishlist یا جستجوهای اخیرشان مرتبط است نوتیفیکیشن بده
- الگوریتم scoring وزن‌دار: بودجه، دسته‌بندی، برند، تاریخچه خرید
- پیشنهادات شخصی‌سازی‌شده (Personalized Recommendations)

### ۴.۱۱ — سیستم Multi-Vendor / مارکت‌پلیس (اختیاری)
**الهام از پروژه VPN (Reseller System):**
- فروشندگان مستقل می‌توانند ثبت‌نام کنند و محصول بفروشند
- هر فروشنده: پنل مجزا، تنظیمات مجزا، برندینگ مجزا
- سیستم کمیسیون: درصد از هر فروش برای پلتفرم
- تسویه حساب دوره‌ای با فروشندگان
- فروشنده‌های سلسله‌مراتبی (مثل reseller tree در پروژه VPN)
- تنظیمات مجزا برای هر فروشنده (Feature Flags per tenant)

### ۴.۱۲ — n8n / Automation Workflows
**الهام از پروژه SEO OS و Real-Estate:**
- اتصال به n8n برای workflow‌های خودکار
- نمونه workflow‌ها:
  - سبد رها‌شده → ارسال ایمیل یادآوری بعد ۱ ساعت → ارسال کد تخفیف بعد ۲۴ ساعت
  - سفارش تکمیل‌شده → درخواست ریویو بعد ۷ روز
  - محصول جدید → تولید محتوای SEO با AI → انتشار در بلاگ
  - هشدار کمبود موجودی → نوتیفیکیشن تلگرام به ادمین

### ۴.۱۳ — سیستم Approval و تأیید انسانی
**الهام از پروژه SEO OS:**
- صف تأیید برای اقدامات حساس:
  - انتشار محصول جدید
  - تغییر قیمت بیش از X درصد
  - ریفاند بالای مبلغ مشخص
  - تأیید ریویوی کاربران
- سطح‌بندی ریسک: low (خودکار) → medium (تأیید ادمین) → high (تأیید مدیر)

### ۴.۱۴ — سیستم پشتیبانی تیکتی
**الهام از پروژه VPN:**
- ارسال تیکت توسط کاربر با دسته‌بندی (سفارش، پرداخت، محصول، فنی)
- پاسخ ادمین با وضعیت: open → answered → closed
- اتصال تیکت به سفارش خاص
- آپلود فایل ضمیمه
- SLA tracking: زمان پاسخ‌گویی، زمان حل

### ۴.۱۵ — بلاگ و محتوا
- سیستم بلاگ داخلی با ادیتور ریچ‌تکست
- دسته‌بندی و تگ مقالات
- SEO Score خودکار برای هر مقاله (مشابه بخش ۴.۶)
- تقویم محتوایی (Content Calendar) مشابه پروژه SEO OS
- لینک‌سازی داخلی هوشمند بین مقالات و محصولات

---

## 🎨 بخش ۵: UI/UX و فرانت‌اند Design System

### ۵.۱ — Design System
- مبتنی بر **shadcn/ui** + **Radix UI** + **Tailwind CSS**
- با الهام از بهترین Design Systemهای جهانی: Shopify Polaris, Ant Design, Adobe Spectrum
- کامپوننت‌های اتمیک: Button, Input, Select, Modal, Toast, Tooltip, Dropdown, Badge, Avatar, Card, Table, Pagination, Tabs, Accordion, Breadcrumb, Skeleton, Empty State
- تم‌بندی: Light/Dark mode با CSS variables
- فونت فارسی: Vazirmatn یا Estedad
- رنگ‌بندی: Primary, Secondary, Success, Warning, Error, Neutral — هر کدام با ۹ shade
- فاصله‌گذاری و تایپوگرافی استاندارد با scale سیستماتیک

### ۵.۲ — صفحات اصلی (با جزئیات layout)
برای هر صفحه، layout دقیق، کامپوننت‌ها، و تعاملات را توضیح بده:

1. **صفحه اصلی (Home)**
   - Hero section با slider یا ویدیو + CTA
   - دسته‌بندی‌های اصلی (grid یا carousel)
   - محصولات ویژه / پیشنهاد لحظه‌ای / تخفیف‌دار
   - بنرهای تبلیغاتی
   - محصولات پرفروش
   - برندهای محبوب
   - بلاگ پست‌های اخیر
   - شمارنده معکوس (Countdown) برای فلش سیل

2. **صفحه لیست محصولات (Product Listing Page — PLP)**
   - فیلتر sidebar (desktop) / bottom sheet (mobile) با faceted search
   - مرتب‌سازی: جدیدترین، ارزان‌ترین، گران‌ترین، پرفروش‌ترین، بیشترین تخفیف، بالاترین امتیاز
   - نمایش Grid/List toggle
   - Infinite scroll یا pagination
   - Quick view modal
   - اضافه‌کردن سریع به سبد
   - نمایش تخفیف، امتیاز، و badge (جدید، تخفیف، تمام‌شد)

3. **صفحه محصول (Product Detail Page — PDP)**
   - گالری تصاویر با zoom و lightbox
   - انتخاب variant (رنگ، سایز) با تغییر قیمت و تصویر
   - نمودار سایز (Size Guide)
   - تب‌ها: توضیحات، مشخصات فنی، نظرات، سؤالات
   - محصولات مرتبط / مشابه
   - اضافه به wishlist / مقایسه
   - Share button (لینک، تلگرام، واتساپ)
   - Breadcrumb
   - Sticky add-to-cart bar (mobile)

4. **سبد خرید (Cart)**
   - لیست آیتم‌ها با تصویر، نام، variant، قیمت، تعداد
   - تغییر تعداد inline
   - حذف آیتم با confirmation
   - کد تخفیف
   - خلاصه سفارش (جمع، تخفیف، مالیات، ارسال، مبلغ نهایی)
   - محصولات پیشنهادی (Cross-sell)
   - ادامه خرید / رفتن به چک‌اوت

5. **چک‌اوت (Checkout)**
   - Stepper visual (مرحله‌ای)
   - انتخاب/ویرایش آدرس
   - انتخاب روش ارسال با تخمین زمان و هزینه
   - انتخاب روش پرداخت
   - خلاصه نهایی
   - دکمه تأیید و پرداخت

6. **پنل کاربر (Dashboard)**
   - خلاصه حساب
   - سفارشات با فیلتر وضعیت + timeline هر سفارش
   - کیف پول با تاریخچه تراکنش‌ها
   - آدرس‌ها
   - wishlist
   - تیکت‌های پشتیبانی
   - داشبورد رفرال
   - تنظیمات (تغییر رمز، نوتیفیکیشن‌ها)

7. **پنل ادمین (Admin Dashboard)**
   - داشبورد KPI با نمودارها
   - مدیریت محصولات (CRUD + bulk actions)
   - مدیریت سفارشات (Kanban + لیست)
   - مدیریت کاربران
   - مدیریت تخفیف‌ها
   - مدیریت محتوا (بلاگ + بنرها + اسلایدر)
   - گزارشات مالی
   - تنظیمات سایت (عمومی، پرداخت، ارسال، SEO، ایمیل)
   - SEO Dashboard

### ۵.۳ — انیمیشن و Interaction
- **Framer Motion** برای:
  - Page transitions (fade, slide)
  - Micro-interactions: hover effects، button press، toggle
  - Skeleton loading
  - Scroll-triggered animations
  - Modal/drawer enter/exit
  - Cart badge bounce on add
  - Toast notifications slide-in
- **Lenis** برای smooth scrolling
- **Intersection Observer** برای lazy loading و scroll animations

### ۵.۴ — Responsive و RTL
- Mobile-first design
- Breakpoints: sm(640), md(768), lg(1024), xl(1280), 2xl(1536)
- RTL کامل: direction, text-align, margin/padding mirroring, icon direction
- فونت و عددنویسی فارسی (اعداد فارسی اختیاری)
- تقویم شمسی برای تاریخ‌ها

### ۵.۵ — Performance
- Core Web Vitals بهینه: LCP < 2.5s, FID < 100ms, CLS < 0.1
- Image optimization با next/image + WebP + srcSet
- Code splitting و dynamic imports
- Prefetch لینک‌های مهم
- Service Worker برای caching assets
- Server Components حداکثری + Client Components فقط برای interactive

---

## ⚙️ بخش ۶: امنیت و عملیات (Security & DevOps)

### ۶.۱ — امنیت
- HTTPS everywhere
- CORS whitelist
- CSRF protection
- SQL injection prevention (ORM + parameterized queries)
- XSS prevention (HTML sanitization + CSP headers)
- Rate limiting (per-endpoint، per-user)
- Input validation و sanitization همه‌جا
- Helmet.js / Security headers
- Encryption at rest (فیلدهای حساس با Fernet)
- Audit log همه عملیات حساس

### ۶.۲ — DevOps و دیپلوی
- **Docker Compose** با سرویس‌ها:
  - backend (FastAPI/Django + Uvicorn/Gunicorn)
  - frontend (Next.js standalone)
  - postgres
  - redis
  - celery-worker
  - celery-beat
  - nginx (reverse proxy + SSL)
  - meilisearch/elasticsearch
  - minio (اختیاری)
- **Nginx config** با: gzip, cache headers, rate limit, proxy pass
- **SSL/TLS** با Certbot auto-renew
- **Environment variables** مدیریت شده با .env files
- **Backup خودکار** PostgreSQL: pg_dump → فشرده‌سازی → ارسال به تلگرام/S3 (مشابه پروژه VPN)
- Health check endpoints

### ۶.۳ — CI/CD
- GitHub Actions:
  - Lint + Type check
  - Unit tests + Integration tests
  - Build + Push Docker images
  - Deploy to server via SSH
- تست‌ها: pytest (backend) + Jest/Vitest (frontend)

---

## 🗺️ بخش ۷: رودمپ اجرایی (Implementation Roadmap)

یک رودمپ فاز‌بندی‌شده دقیق بده با:
- شماره فاز
- نام فاز
- مدت زمان تقریبی (هفته)
- لیست دقیق کارها (Task breakdown)
- خروجی قابل تحویل هر فاز (Deliverables)
- وابستگی‌ها بین فازها

پیشنهاد من برای ترتیب فازها:
1. **فاز ۰**: راه‌اندازی زیرساخت (Docker, CI/CD, Project structure)
2. **فاز ۱**: احراز هویت + مدیریت کاربران + RBAC
3. **فاز ۲**: مدیریت محصولات + دسته‌بندی + موجودی
4. **فاز ۳**: سبد خرید + چک‌اوت + پرداخت
5. **فاز ۴**: سفارشات + ارسال
6. **فاز ۵**: جستجو + فیلتر
7. **فاز ۶**: UI/UX فرانت‌اند (Design System + صفحات اصلی)
8. **فاز ۷**: پنل ادمین
9. **فاز ۸**: مارکتینگ (رفرال، کشبک، گیمیفیکیشن، broadcast)
10. **فاز ۹**: SEO + بلاگ + محتوا
11. **فاز ۱۰**: آنالیتیکس + داشبورد
12. **فاز ۱۱**: تیکت پشتیبانی + هشدارها + نوتیفیکیشن
13. **فاز ۱۲**: Multi-vendor / مارکت‌پلیس (اختیاری)
14. **فاز ۱۳**: Automation + n8n + AI features
15. **فاز ۱۴**: تست نهایی + بهینه‌سازی + دیپلوی production

---

## 📋 بخش ۸: خروجی‌های مورد انتظار

لطفاً در پاسخت **تمام** موارد زیر را ارائه بده:

1. ✅ **انتخاب فریمورک بک‌اند** (FastAPI vs Django) با استدلال
2. ✅ **انتخاب موتور جستجو** (Elasticsearch vs Meilisearch) با استدلال
3. ✅ **دیاگرام معماری کلی** (ASCII یا Mermaid)
4. ✅ **ERD دیتابیس** (Mermaid) — تمام جداول با روابط
5. ✅ **ساختار فولدری بک‌اند** (tree view)
6. ✅ **ساختار فولدری فرانت‌اند** (tree view)
7. ✅ **لیست API endpoints** — گروه‌بندی شده با HTTP method و path
8. ✅ **docker-compose.yml** کامل
9. ✅ **رودمپ فاز‌بندی‌شده** با جزئیات Task breakdown
10. ✅ **لیست پکیج‌ها** (requirements.txt / pyproject.toml + package.json)

---

## ⚠️ قوانین و محدودیت‌ها

1. همه چیز به **زبان فارسی** توضیح بده
2. از **بهترین practice‌های ۲۰۲۵-۲۰۲۶** استفاده کن
3. کد نمونه ننویس — فقط **آرکیتکچر، طراحی، و رودمپ**
4. هر تصمیم طراحی را با **دلیل** توضیح بده
5. **مقیاس‌پذیری** را در ذهن داشته باش (از ۱۰۰ کاربر تا ۱۰۰,۰۰۰ کاربر)
6. ساختار **modular monolith** — نه microservices (مشابه پروژه SEO OS)
7. تمرکز روی **بازار ایران**: تومان، تقویم شمسی، شماره‌موبایل ایرانی، درگاه‌های پرداخت ایرانی، RTL
8. **هیچ محدودیتی در طول پاسخ نداری** — کامل و جامع بنویس حتی اگر بسیار طولانی شود

---

**الان شروع کن. ابتدا انتخاب‌های فنی و معماری کلی، سپس ERD، سپس ساختار فولدری، سپس API‌ها، سپس رودمپ.**
