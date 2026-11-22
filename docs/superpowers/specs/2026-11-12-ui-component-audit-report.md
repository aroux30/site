# گزارش بررسی کامپوننت‌های رابط کاربری — ۱۲ آبان ۱۴۰۵

> **وضعیت:** فقط‌خواندنی — هیچ فایلی تغییر نکرده. منتظر تأیید برای پیاده‌سازی.

---

## بخش ۱: خلاصه‌ی وضعیت فرانت‌اند فعلی

| شاخص | مقدار |
|---|---|
| صفحات | ~۱۰۰ (۲۷ فروشگاه + ۱۲ حساب + ۵۰+ ادمین) |
| کامپوننت UI پایه | ۳۴ فایل (`components/ui/`) |
| کامپوننت ادمین | ~۷۰ فایل |
| هوک | ۱۰ |
| استور (Zustand) | ۳ (auth, cart, compare) |
| فایل API client | ۵۶ |
| فریم‌ورک | Next.js 15 App Router |
| زبان | TypeScript |
| استایل | Tailwind CSS 3 + shadcn/ui + Radix UI |
| فونت | Vazirmatn (فارسی) |
| رنگ اصلی | سبز زمردی (emerald ۱۶۰°) |
| انیمیشن | Framer Motion (کم‌استفاده)، Three.js/R3F (هیرو + ویوئر ۳D) |
| وابستگی مرده | GSAP (نصب شده، هیچ‌جا import نشده) |

---

## بخش ۲: خلأهای شناسایی‌شده در فرانت‌اند

### 🔴 بحرانی (تأثیر مستقیم روی تجربه کاربر)

| # | خلأ | توضیح |
|---|---|---|
| G1 | **loading.tsx تقریباً وجود نداره** | فقط ۳ از ~۱۰۰ صفحه `loading.tsx` دارن. کاربر موقع ناوبری هیچ فیدبکی نمی‌بینه. |
| G2 | **error.tsx فقط ۱ عدد کلی** | خطا در هر بخش کل سایت رو می‌زنه. ایزوله‌سازی خطا وجود نداره. |
| G3 | **گالری عکس / لایت‌باکس نداریم** | صفحه‌ی محصول زوم، فول‌اسکرین و اسوایپ نداره. برای فروشگاه حیاتیه. |
| G4 | **کارت محصول قابل‌استفاده مجدد نداریم** | هر صفحه (خانه، لیست، جستجو) کارت رو از اول ساخته. |

### 🟡 مهم (بهبود قابل‌توجه تجربه)

| # | خلأ | توضیح |
|---|---|---|
| G5 | **هیستوگرام امتیاز نداریم** | نقد و بررسی بدون نمودار "۴ ستاره: ۴۵٪" |
| G6 | **کامپوننت Rating مستقل نداریم** | ستاره‌ها inline توی PDP ساخته شدن |
| G7 | **مشاهده سریع (Quick View) نداریم** | از لیست محصولات باید وارد صفحه بشی |
| G8 | **محصولات اخیراً دیده‌شده نداریم** | |
| G9 | **Empty State یکپارچه ضعیفه** | `PageLoader`/`EmptyState`/`ErrorState` وجود داره ولی اکثر صفحات ازش استفاده نمی‌کنن |
| G10 | **فقط ۳ نوع toast** | `info` و `warning` نداریم با اینکه توکن رنگی‌شون هست |

### 🟢 بهبود تدریجی (polish)

| # | خلأ | توضیح |
|---|---|---|
| G11 | **Mega Menu دسته‌بندی نداریم** | هدر فقط لیست ساده‌ی لینک‌ها داره |
| G12 | **انیمیشن میکرو ضعیفه** | add-to-cart و wishlist بدون فیدبک بصری جذاب |
| G13 | **متن چرخشی تبلیغاتی نداریم** | "ارسال رایگان • ضمانت بازگشت • …" |
| G14 | **GSAP وابستگی مرده** | نصبه ولی هیچ‌جا استفاده نشده — باید حذف بشه |

---

## بخش ۳: بررسی ۱۰ مخزن

### ماتریس سازگاری

| کتابخانه | لایسنس | React 18 | RTL | نصب | کیفیت | ارزش برای فروشگاه |
|---|---|---|---|---|---|---|
| **shadcn/ui** | MIT ✅ | ✅ | ✅ بومی | CLI copy | ⭐⭐⭐⭐⭐ | بالا — پایه‌ی فعلی |
| **Flowbite** | MIT ✅ | ✅ | ✅✅✅ بومی | npm | ⭐⭐⭐⭐ | بالا — بهترین RTL |
| **Magic UI** | MIT ✅ | ✅ | ❌ | CLI copy | ⭐⭐⭐⭐ | متوسط — تزئینی |
| **Motion Primitives** | MIT ✅ | ✅ | ❌ | CLI copy | ⭐⭐⭐⭐ | متوسط — انیمیشن |
| **React Bits** | MIT+CC ✅ | ✅ | ❌ | CLI copy | ⭐⭐⭐⭐ | متوسط — میکرو |
| **Aceternity UI** | اختصاصی ✅ | ✅ | ❌ | CLI copy | ⭐⭐⭐⭐ | متوسط — بصری |
| **Preline** | MIT ✅ | ⚠️ HTML | ⚠️ جزئی | npm | ⭐⭐⭐⭐ | مرجع طراحی |
| **TailGrids** | MIT ✅ | ✅ | ❌ | CLI copy | ⭐⭐⭐⭐ | مرجع طراحی |
| **HyperUI** | MIT ✅ | ⚠️ HTML | ⚠️ جزئی | copy | ⭐⭐⭐ | مرجع طراحی |
| **Commerce UI** | MIT ✅ | ❌ React 19 | ❌ | CLI | ⭐⭐⭐ | ❌ فقط مطالعه |

---

## بخش ۴: فهرست پیشنهادی اولویت‌بندی‌شده

### 🏆 اولویت ۱ — نصب مستقیم از shadcn/ui (بدون اصطکاک، RTL بومی)

| # | کامپوننت | منبع | خلأ رفع‌شده | کاربرد | پیچیدگی |
|---|---|---|---|---|---|
| P1 | **Breadcrumb** | shadcn/ui | — | ناوبری همه‌ی صفحات | ساده |
| P2 | **Carousel** | shadcn/ui (Embla) | G3 جزئی | گالری محصول، اسلایدر تبلیغات | ساده |
| P3 | **Command** (⌘K) | shadcn/ui (cmdk) | — | جستجوی سریع ادمین | ساده |
| P4 | **Drawer** | shadcn/ui (vaul) | — | فیلتر موبایل، منوی موبایل | ساده |
| P5 | **Tooltip** | shadcn/ui (Radix) | — | راهنمای آیکون‌ها | ساده |
| P6 | **Pagination** | shadcn/ui | — | لیست محصولات، بلاگ، ادمین | ساده |
| P7 | **Progress** | shadcn/ui | — | آپلود فایل، فرایند خرید | ساده |
| P8 | **Scroll Area** | shadcn/ui (Radix) | — | لیست‌های بلند ادمین | ساده |
| P9 | **Hover Card** | shadcn/ui (Radix) | — | پیش‌نمایش محصول در لینک | ساده |
| P10 | **Toggle Group** | shadcn/ui (Radix) | — | تغییر نمای grid/list | ساده |

**تخمین زمانی:** مجموعاً ~۲ ساعت (هر کدوم `npx shadcn@latest add` و تمام)

---

### 🥈 اولویت ۲ — ساخت کامپوننت‌های حیاتی فروشگاه (ترکیب منابع)

| # | کامپوننت | منبع الهام | خلأ رفع‌شده | کاربرد | پیچیدگی |
|---|---|---|---|---|---|
| P11 | **ProductCard (قابل‌استفاده مجدد)** | TailGrids + Commerce UI (مطالعه) | G4 | خانه، لیست، جستجو، دسته‌بندی، پیشنهادات | متوسط |
| P12 | **ImageGallery + Lightbox** | Motion Primitives carousel + ساخت اختصاصی | G3 | صفحه‌ی محصول — زوم، فول‌اسکرین، اسوایپ | متوسط |
| P13 | **StarRating (نمایش + ورودی)** | Flowbite Rating (RTL بومی) | G5, G6 | PDP، لیست، فرم نقد | ساده |
| P14 | **ReviewHistogram** | Commerce UI (مطالعه) + ساخت اختصاصی | G5 | PDP — نمودار توزیع ستاره‌ها | ساده |
| P15 | **QuickViewModal** | Aceternity Animated Modal + TailGrids Quick View | G7 | لیست محصولات — پیش‌نمایش سریع | متوسط |
| P16 | **RecentlyViewed** | ساخت اختصاصی (localStorage + استور) | G8 | فوتر PDP، صفحه‌ی اصلی | ساده |
| P17 | **MegaMenu** | Flowbite Mega Menu (RTL بومی) | G11 | هدر — ناوبری دسته‌بندی چندستونه | متوسط |

**تخمین زمانی:** مجموعاً ~۱۲-۱۵ ساعت

---

### 🥉 اولویت ۳ — بهبود تجربه‌ی کاربری (انیمیشن و فیدبک)

| # | کامپوننت | منبع | خلأ رفع‌شده | کاربرد | پیچیدگی |
|---|---|---|---|---|---|
| P18 | **ClickSpark** | React Bits | G12 | فیدبک add-to-cart | ساده |
| P19 | **PulseHeart** | React Bits | G12 | انیمیشن دکمه‌ی علاقه‌مندی | ساده |
| P20 | **TextLoop** | Motion Primitives | G13 | متن چرخشی تبلیغاتی هدر | ساده |
| P21 | **AnimatedNumber** | Motion Primitives | — | تعداد سبد، قیمت، آمار | ساده |
| P22 | **Toast variants (info + warning)** | ساخت اختصاصی (توکن‌ها موجوده) | G10 | اعلان‌های سیستمی | ساده |

**تخمین زمانی:** مجموعاً ~۴ ساعت

---

### 🔧 اولویت ۴ — زیرساخت و بهداشت کد

| # | کار | خلأ رفع‌شده | پیچیدگی |
|---|---|---|---|
| P23 | **اضافه کردن `loading.tsx` به route groupها** | G1 | ساده (۴ فایل: store, account, admin, blog) |
| P24 | **اضافه کردن `error.tsx` به route groupها** | G2 | ساده (۴ فایل) |
| P25 | **حذف GSAP** | G14 | ساده (`npm uninstall gsap @gsap/react`) |

**تخمین زمانی:** ~۱ ساعت

---

## بخش ۵: موارد رد‌شده

| کامپوننت / کتابخانه | منبع | دلیل رد |
|---|---|---|
| **Commerce UI (کل کتابخانه)** | stackzero-labs | ❌ نیاز به React 19 + Tailwind v4 — ناسازگار با پروژه |
| **Flowbite (نصب کامل npm)** | flowbite-react | ❌ نسخه‌ی React هنوز pre-release (v0.12). فقط cherry-pick سورس Rating و MegaMenu. |
| **Preline (نصب کامل)** | preline | ❌ HTML خالص + JS plugin — نیاز به تبدیل به JSX. فقط مرجع طراحی. |
| **HyperUI (نصب)** | hyperui | ❌ HTML خالص — فقط مرجع طراحی |
| **Apple Cards Carousel** | Aceternity | ❌ جذابه ولی در طول سال حداکثر ۲-۳ بار استفاده می‌شه |
| **Bento Grid** | Magic UI / Aceternity | ❌ قبلاً `bento-grid.tsx` داریم |
| **Marquee** | Magic UI | ❌ قبلاً `marquee.tsx` داریم |
| **Number Ticker** | Magic UI | ❌ قبلاً `number-ticker.tsx` داریم |
| **Shimmer Button** | Magic UI | ❌ قبلاً `shimmer-button.tsx` داریم |
| **Confetti** | Magic UI | ❌ قبلاً `confetti.tsx` داریم |
| **Smooth Scroll (Lenis)** | — | ❌ قبلاً `smooth-scroll.tsx` داریم |
| **Sidebar** | shadcn/ui | ❌ پنل ادمین فعلی ناوبری خودش رو داره و ۵۰+ صفحه باهاش کار می‌کنه. بازنویسی نمی‌ارزه. |
| **Chart System** | shadcn/ui | ❌ `recharts` قبلاً نصبه و توی BI/reports استفاده می‌شه. wrapper اضافی ارزش نداره. |
| **Chat Components** | shadcn/ui | ❌ ماژول چت فعلی (SSE + n8n) با معماری خودش کار می‌کنه. جایگزینی هزینه‌بر و بی‌ارزشه. |
| **Timeline** | Aceternity | ❌ `shipment-stepper.tsx` رو داریم و کار می‌کنه |
| **Dock** | React Bits | ❌ `floating-bottom-dock.tsx` رو داریم |
| **Stepper** | React Bits | ❌ `shipment-stepper.tsx` رو داریم |
| **3D Tilt / Glare** | React Bits | ❌ `tilt-card-3d.tsx` رو داریم |
| **Floating Navbar** | Aceternity | ❌ هدر فعلی sticky هست و کار می‌کنه |
| **Datepicker** | Flowbite | ❌ `jalali-datepicker.tsx` رو داریم (تقویم شمسی) |
| **Bottom Navigation** | Flowbite | ❌ `mobile-bottom-nav.tsx` رو داریم |
| **Kanban** | Preline | ❌ `orders-board.tsx` + `tickets-board.tsx` با dnd-kit داریم |
| **OTP Input** | — | ❌ `input-otp.tsx` رو داریم |
| **Masonry Grid** | React Bits | ❌ کاربرد محدود در فروشگاه؛ grid معمولی کافیه |
| **Image Comparison (قبل/بعد)** | Motion Primitives | ❌ فروشگاه لباس/لوازم آرایشی نیست — حداکثر ۱ بار استفاده |
| **Scroll Progress** | Motion Primitives | ❌ صفحات به اندازه‌ای بلند نیستن |
| **Flip Card** | React Bits | ❌ gimmick — کاربرد واقعی نداره |
| **Silk backgrounds** | React Bits | ❌ صرفاً تزئینی |
| **Morphing Dialog** | Motion Primitives | ❌ پیچیدگی بالا، ارزش کم |
| **Multi Step Loader** | Aceternity | ❌ `top-progress-bar.tsx` رو داریم |
| **Speed Dial (FAB)** | Flowbite | ❌ الگوی Material Design — با دیزاین سیستم فعلی ناسازگار |

---

## بخش ۶: برنامه‌ی پیاده‌سازی پیشنهادی

### فاز ۱ — زیرساخت (۱ ساعت)
- [ ] حذف GSAP (`npm uninstall gsap @gsap/react`)
- [ ] اضافه کردن `loading.tsx` به `(store)/`، `(account)/`، `admin/` (اگه نداره)، `blog/`
- [ ] اضافه کردن `error.tsx` به `(store)/`، `(account)/`، `blog/`

### فاز ۲ — کامپوننت‌های shadcn/ui (۲ ساعت)
- [ ] نصب: Breadcrumb, Carousel, Command, Drawer, Tooltip, Pagination, Progress, Scroll Area, Hover Card, Toggle Group

### فاز ۳ — کامپوننت‌های حیاتی فروشگاه (۱۲-۱۵ ساعت)
- [ ] ساخت `ProductCard` قابل‌استفاده مجدد
- [ ] ساخت `ImageGallery` + `Lightbox` (با Embla carousel)
- [ ] cherry-pick سورس `StarRating` از Flowbite + RTL
- [ ] ساخت `ReviewHistogram`
- [ ] ساخت `QuickViewModal`
- [ ] ساخت `RecentlyViewed` (localStorage + Zustand)
- [ ] cherry-pick سورس `MegaMenu` از Flowbite + RTL

### فاز ۴ — انیمیشن و فیدبک (۴ ساعت)
- [ ] copy-paste `ClickSpark` از React Bits + RTL patch
- [ ] copy-paste `PulseHeart` از React Bits
- [ ] copy-paste `TextLoop` از Motion Primitives + RTL patch
- [ ] copy-paste `AnimatedNumber` از Motion Primitives
- [ ] اضافه کردن variant‌های `info` و `warning` به toast

### فاز ۵ — تست و بررسی (۲ ساعت)
- [ ] تست واکنش‌گرایی موبایل
- [ ] تست RTL همه‌ی کامپوننت‌های جدید
- [ ] تست عدم تداخل با کامپوننت‌های فعلی
- [ ] بررسی bundle size قبل و بعد

---

**مجموع تخمین:** ~۲۱-۲۴ ساعت کاری در ۵ فاز
