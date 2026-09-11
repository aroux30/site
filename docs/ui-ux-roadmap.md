# رودمپ ارتقای UI/UX و Front-End — فروشگاه آنلاین

> تاریخ: 2026-09-11 | دامنه: `frontend/` (Next.js 15 + React 19 + Tailwind + Radix)
> روش ارزیابی: بازبینی کد کامل پایه طراحی (توکن‌ها، layout، هدر/فوتر)، صفحات کلیدی
> (خانه، لیست محصولات، جزئیات محصول، ورود)، لایه API و زیرساخت (i18n، RTL، SEO، a11y).

---

## ۱) کارنامه ارزیابی (0–100)

| # | محور | قبل | بعد از موج ۱ | توضیح |
|---|------|-----|--------------|-------|
| 1 | پایه Design System (توکن، تایپ، رنگ) | 70 | 82 | توکن‌های shadcn موجود بود؛ رنگ‌های معنایی success/warning/info اضافه شد، پلاگین انیمیشن فعال شد |
| 2 | کتابخانه کامپوننت | 78 | 82 | ۳۳ کامپوننت shadcn/Magic-UI-style؛ یکدست‌سازی سلکت‌ها (بومی → Radix) |
| 3 | RTL و فارسی | 85 | 85 | فونت وزیرمتن، ارقام فارسی، تاریخ جلالی — از قبل قوی؛ فونت mono اصلاح شدنی (موج ۲) |
| 4 | SEO و دیده‌شدن | 40 | 82 | بزرگ‌ترین شکاف: metadata داینامیک محصول + JSON-LD (Product/Breadcrumb/Organization/WebSite) + noindex صفحات تراکنشی |
| 5 | Performance | 55 | 72 | `<img>` خام → next/image با sizes درست؛ dynamic import سه‌بعدی از قبل درست بود |
| 6 | Accessibility | 62 | 75 | محافظ prefers-reduced-motion سراسری، aria-label روی کنترل‌های icon-only، رنگ‌های destructive توکن‌محور |
| 7 | یکدستی و Consistency | 65 | 78 | سلکت بومی حذف شد؛ رنگ‌های هاردکد emerald در کامپوننت‌های اشتراکی → توکن primary |
| 8 | صداقت داده / اعتماد | 60 | 75 | رنکینگ جعلی تکراری (۴.۶/۲۸ نظر روی همه کارت‌ها) حذف شد |
| 9 | معماری State/Data | 80 | 80 | react-query + zustand + fallback داده — از قبل خوب |
| 10 | تغییرات بصری سرگرم‌کننده (3D، Motion) | 88 | 88 | 3D hero، tilt cards، marquee، countdown — موجود و باکیفیت |

**نمره کلی: ≈ 65 → ≈ 78** (موج ۱ اجرا شد؛ پتانسیل موج ۲ و ۳: 90+)

### یافته‌های خطرناک موج ۱ (P0 که همین حالا رفع شد)
- **کلاس‌های انیمیشن مرده**: هدر از `animate-in fade-in-0 zoom-in-95` استفاده می‌کرد ولی پلاگین `tailwindcss-animate` نصب نبود → دراپ‌داون پیشنهاد جستجو بدون انیمیشن بود. نصب و ثبت شد.
- **SEO صفر روی صفحه محصول**: PDP کاملاً client و بدون metadata بود؛ مهم‌ترین صفحه برای گوگل.
- **رنکینگ جعلی**: همه کارت‌ها یک امتیاز ثابت «۴.۶ (۲۸ نظر)» داشتند.

---

## ۲) تصمیم کتابخانه‌ها بر اساس لیست Tier S

قانون تصمیم: **به معماری موجود (Tailwind + Radix + CVA = معماری shadcn) وفادار بمان**؛
نصب هر UI-Kit سنگین دیگر یعنی دو design system موازی، CSS تکراری و باگ RTL.

| از لیست شما | وضعیت | تصمیم |
|---|---|---|
| shadcn/ui (معماری) | ✅ از قبل برقرار | Radix + CVA + tailwind-merge + clix — پایه درست انتخاب شده |
| Radix UI | ✅ نصب (۱۲ پکیج) | ستون فقرات کامپوننت‌ها |
| Magic UI / Aceternity UI | ✅ معادل‌سازی شده | bento-grid، marquee، number-ticker، shimmer-button، spotlight-card، smooth-scroll همین الگوها هستند؛ copy-paste library هستند و npm package ندارند |
| Framer Motion | ✅ نصب | number-ticker و انیمیشن‌ها |
| GSAP + @gsap/react | ✅ نصب | gsap-reveal و صحنه‌های 3D |
| Lenis | ✅ نصب | SmoothScroll سراسری + رعایت reduced-motion |
| Three.js / R3F / drei | ✅ نصب | hero-scene، product-viewer-3d |
| Tremor | ✅ معادل | recharts نصب است (همان موتور Tremor) برای داشبورد ادمین |
| Embla / vaul / cmdk / input-otp | ✅ نصب | اکوسیستم کامل shadcn |
| **tailwindcss-animate** | 🆕 **نصب شد** | کلاس‌های animate-in که کد استفاده می‌کرد بدون آن بی‌اثر بودند |
| MUI، Ant Design، Chakra، HeroUI/NextUI، daisyUI، Headless UI | ❌ نصب نشد | تداخل/تکرار با Tailwind+Radix؛ دو موازی‌کاری design system و خطر RTL |
| React Spring، Auto Animate، Motion One | ❌ نصب نشد | Framer Motion تمام این نیازها را پوشش می‌دهد |
| Design System‌های مرجع (Polaris، Carbon، Fluent،…) | 📚 مرجع | برای الگوبرداری از مستندات، نه نصب |

---

## ۳) رودمپ اجرا

### ✅ موج ۱ — اجرا شد (همین PR)
**فoundation**
- `tailwindcss-animate` نصب و در `tailwind.config.ts` ثبت شد.
- توکن‌های معنایی `success` / `warning` / `info` در light و dark (`globals.css`).
- محافظ سراسری `prefers-reduced-motion` (خاموشی انیمیشن/ترنزیشن‌های تزئینی).

**SEO (بزرگ‌ترین جهش)**
- `app/(store)/products/[slug]/layout.tsx`: generateMetadata داینامیک (title/description/OG/canonical از API) + JSON-LD محصول وBreadcrumbList.
- JSON-LD سراسری `Organization` + `WebSite` با SearchAction در `app/layout.tsx`.
- metadata layout برای: products، cart، checkout، compare، login، register، favorites (همگی noindex تراکنشی)، rewards، blog، contact.
- `public/logo.svg` ساخته شد (مرجع JSON-LD و آیکون برند).

**صفحه لیست محصولات**
- next/image با sizes بهینه (کارت + quick-view).
- سلکت مرتب‌سازی بومی → Radix Select (یکدستی، RTL درست، کیبورد).
- صفحه‌بندی پنجره‌ای با ellipsis (قبلاً همه صفحات دکمه ساخته می‌شد).
- رفع باگ dark-mode دکمه حذف فیلترها (red-50 → توکن destructive).
- aria-label کنترل‌های icon-only؛ حذف رنکینگ جعلی.

**صفحه اصلی و کارت محصول**
- شمارنده‌های اعتماد با NumberTicker (Magic UI style) انیمیت شدند.
- کل تصویر کارت محصول کلیک‌پذیر شد؛ رنگ‌های هاردکد → توکن primary.

### 🔜 موج ۲ — پیشنهاد فوری بعدی (2 تا 3 هفته)
1. **تبدیل PDP و لیست محصولات به RSC جزئی**: fetch سرور داده در `page.tsx` (server component) و آب‌بخاری کلاینت فقط برای تعامل → FCP/LCP بهتر و SEO محکم‌تر.
2. **احراز هویت UI**: اسکلت صفحه ورود (بالا ۲۵٪ فایل) بازطراحی بصری با layout دو ستونه (تصویر/اعتماد + فرم).
3. **Checkout UX**: فرم ۱۶۴۵ خطی به گام‌های مستقل (آدرس ← ارسال ← پرداخت) با وضعیت ذخیره‌شده و ریویو نهایی.
4. **تصاویر همه صفحات**: باقی‌مانده‌های `<img>` (blog، account، …) → next/image؛ `priority` برای تصویر hero.
5. **فونت mono واقعی** برای اعداد/کد (موجود mono=وزیرمتن است) + `font-variant-numeric` مرتب.
6. **دکمه‌ها/Stateهای بارگذاری**: اسکلت‌های اختصاصی checkout و دکمه‌های pending یکدست.

### 🌅 موج ۳ — تمایز و رشد (1 تا 2 ماه)
1. **هویت تایپوگرافیک متمایز**: تیترهای display (وزیرمتن Black در مقیاس fluid با clamp) و جدول مقیاس مستند.
2. **صفحه دسته‌بندی/جستجوی حرفه‌ای**: فیلتر فاصله‌ای با URL-first state، chips قابل اشتراک‌گذاری، اینفینیتی اسکرول اختیاری.
3. **PWA و آفلاین**: manifest + service worker برای بازگشت کاربر موبایل (mobile-bottom-nav موجود است).
4. **تست‌های visual regression**: Playwright screenshot برای صفحات کلیدی + بودجه Lighthouse در CI.
5. **پنل ادمین**: یکدست‌سازی با توکن‌های مشترک + نمودارهای recharts تم‌دار.
6. **A/B پیام‌های CTA** و افزودن نشان‌های اعتماد واقعی (اینماد/ساماندهی) در فوتر.

---

## ۴) اصول طراحی این پروژه (لنگرگاه تصمیم‌ها)
1. **سبز = اعتماد و اصالت کالا**: primary برای اکشن خرید/تأیید؛ رنگ‌های معنایی فقط برای معنا (موفق/هشدار/خطا)، نه تزئین.
2. **فارسی اول**: RTL خالص، ارقام فارسی در UI، انگلیسی فقط برای برند/مدل.
3. **حرکت با دلیل**: انیمیشن فقط برای پاسخ به کاربر یا یک لحظه روایت (ورود آمار hero)؛ هیچ حرکت تزئینی بی‌پاسخ.
4. **صداقت داده**: هیچ عدد نمایشی جعلی؛ تا وقتی API رتبه/آمار ندهد نمایش نده.
5. **یک design system، یک منبع حقیقت**: توکن‌های CSS متغیر؛ هیچ هاردکد رنگ در کامپوننت اشتراکی.
