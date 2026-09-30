# معماری امنیتی، احراز هویت و کنترل دسترسی پلتفرم (Security Architecture Guide)

این سند نقشه راه و مرجع فنی پیاده‌سازی لایه‌های امنیت، احراز هویت (Authentication)، کنترل دسترسی بر اساس نقش (RBAC/ABAC)، محافظت از روت‌ها (Middleware & Auth Guard)، مقابله با حملات Brute Force و Bot Abuse، و مانیتورینگ امنیتی در پروژه فروشگاهی و پنل مدیریت است.

---

## ۱. نمای کلی معماری تفکیک‌شده لایه‌ها (Defense-in-Depth)

```
                    ┌──────────────────────────────┐
                    │      فرانت‌اند (Next.js)      │
                    │   پنل مدیریت و داشبورد کاربر │
                    │ SimpleWebAuthn + AuthGuard   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   لایه گارد و میدل‌ور (Edge) │
                    │   Next.js middleware.ts      │
                    │   بررسی کوکی و توکن JWT      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   Reverse Proxy & WAF (Nginx)│
                    │   Anti-Bot & Scanner Blocker │
                    │   Connection & Rate Limits   │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   احراز هویت و دفاع چندلایه  │
                    │   SlowAPI + Redis RateLimit  │
                    │   Brute Force Lockout & OTP  │
                    │   MFA / TOTP / Passkeys      │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │   کنترل دسترسی (RBAC / ABAC) │
                    │   FastAPI RequirePermissions │
                    │   Casbin Enforcer Engine     │
                    └──────────────┬───────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────┐
                    │        هسته بک‌اند و API     │
                    │   FastAPI Services & Models  │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
         PostgreSQL              Redis                MinIO
     داده‌ها و لاگ اودیت     نشست‌ها و Lockout     فایل‌ها و فیش‌ها
              │
              ▼
    ┌──────────────────────────────────┐
    │     داشبورد مانیتورینگ و امنیت   │
    │  CrowdSec / Fail2Ban / Grafana   │
    │  Prometheus (9090) / Sentry      │
    └──────────────────────────────────┘
```

---

## ۲. اسکیل‌های هوشمند نصب‌شده ورک‌اسپیس ZCode (`.zcode/skills/` و `.agents/skills/`)

تمامی اسکیل‌های امنیتی استاندارد و تخصصی در مسیرهای `.zcode/skills/` و `.agents/skills/` نصب و فعال شده‌اند:

1. **`bruteforce-defense`**:
   - دفاع چندکلیدی در برابر Brute Force، Credential Stuffing و Password Spraying.
   - مدیریت لایه‌های IP، نام کاربری/شماره موبایل، و اثرانگشت کلاینت.
   - اعمال تاخیر تصاعدی (Progressive Delay) و قفل موقت حساب (Account Lockout) پس از ۵ تلاش ناموفق.

2. **`waf-anti-bot`**:
   - مپینگ و بلاک خودکار اسکنرهای امنیتی و بات‌های مخرب (`sqlmap`، `nikto`، `dirbuster`، `nmap`، ...).
   - محدودسازی نرخ اتصال در ثانیه (`limit_conn_zone`) و نرخ درخواست (`limit_req_zone`).
   - مسدودسازی دسترسی به فایل‌های سیستمی و کانفیگ (`.env`، `.git`، `.aws`، کدهای PHP).
   - اتصال به Coraza WAF / ModSecurity و OWASP Core Rule Set (CRS).

3. **`mfa-passkeys`**:
   - پیاده‌سازی ورود بدون رمز و مقاوم در برابر فیشینگ با FIDO2 / WebAuthn Passkeys (`py_webauthn` و `@simplewebauthn/browser`).
   - احراز هویت دو مرحله‌ای مبتنی بر زمان (TOTP) با اپلیکیشن‌های Authenticator (Google / Microsoft Authenticator) از طریق `pyotp`.
   - تولید کدهای بازیابی اضطراری (Backup Codes).

4. **`security-monitoring`**:
   - مانیتورینگ امنیت و سامانه تشخیص نفوذ (IDS) با CrowdSec و Fail2Ban.
   - ثبت لاگ‌های اودیت ساخت‌یافته امنیتی (Security Audit Logs) برای تلاش‌های ورود و تغییرات دسترسی.
   - اشتراک‌گذاری خودکار لیست سیاه IPهای مخرب در لایه Bouncer.

5. **`api-gateway-policy`**:
   - سخت‌سازی ریورس‌پروکسی Nginx (مدیریت بافرها، هدرهای `X-Real-IP` و جلوگیری از Slowloris).
   - موتور پالیسی Casbin در FastAPI جهت ارزیابی ماتریس دسترسی‌های چندسطحی سازمانی.

6. **`auth-guard`**:
   - راهنمای پیاده‌سازی `middleware.ts` در Next.js.
   - محافظت از روت‌های پنل مدیریت (`/admin/*`) و حساب کاربری (`/account/*`).
   - ایزولاسیون کوکی‌های HttpOnly با `path="/"`.

7. **`rbac-authorization`**:
   - سلسله‌مراتب نقش‌ها (`super_admin`، `admin`، `vendor`، `support`، `customer`).
   - دکوراتورهای مجوزهای ریزدانه `resource:action`.
   - کامپوننت `PermissionGate` در فرانت‌اند.

8. **`security-hardening`**:
   - تنظیم هدرهای امنیتی (CSP, HSTS, X-Frame-Options, ...).
   - فیلتر و پاکسازی کدهای کاربر با `dompurify` جهت مقابله با XSS.

9. **`security-audit`**:
   - اسکن آسیب‌پذیری‌های استاتیک (SAST) با Semgrep و Trivy.
   - جلوگیری از نشت کلیدها و اسرار با Gitleaks.

---

## ۳. پکیج‌ها و کتابخانه‌های نصب‌شده در کد پروژه

### بک‌اند (`backend`):
- **`slowapi` (0.1.10) & `limits` (5.8.0)**: محدودسازی نرخ درخواست‌ها در سطح فریم‌ورک FastAPI.
- **`casbin` (1.43.0)**: موتور ارزیابی سیاست‌های دسترسی و RBAC/ABAC.
- **`pyotp` (2.10.0)**: تولید و تایید کدهای پویا و مخزن امن TOTP.
- **`py_webauthn` (0.0.6)**: موتور سروری پروتکل WebAuthn/Passkeys.
- **`argon2-cffi` (25.1.0) & `passlib` (1.7.4)**: هشینگ رمزنگاری‌شده مقاوم در برابر پردازش موازی GPU/FPGA.
- **`python-jose`**: تولید و راستی‌آزمایی توکن‌های استاندارد JWT.

### فرانت‌اند (`frontend`):
- **`@simplewebauthn/browser`**: تعامل مستقیم با رابط‌های WebAuthn / Passkeys مرورگر کاربر.
- **`dompurify` & `@types/dompurify`**: ضدعفونی‌سازی ورودی‌های غنی HTML در برابر XSS.
- **`jose`**: اعتبارسنجی سبک و بدون وابستگی توکن‌ها در لایه Edge Runtime میدل‌ور.

---

## ۴. پیاده‌سازی‌های انجام‌شده در سورس‌کد پروژه

### الف) دفاع Brute Force و SlowAPI (`backend/app/core/security/rate_limiter.py`)
- کلاس `BruteForceProtector`:
  - بررسی قفل موقت قبل از اجرای منطق احراز هویت.
  - ثبت خطاهای ناموفق در ردیس با پنجره لغزان (Sliding Window).
  - در صورت ۵ تلاش ناموفق برای یک شماره/شناسه، دسترسی به مدت ۱۵ دقیقه قفل می‌شود (`HTTP 429 Too Many Requests` با هدر `Retry-After`).
  - پاکسازی خودکار شمارنده خطا در صورت ورود موفقیت‌آمیز.
- اعمال دکوراتور `@limiter.limit` بر روی اندپوینت‌های حساس:
  - `/api/v1/auth/login`: حداکثر ۱۰ درخواست بر دقیقه بر اساس IP + قفل شماره تلفن.
  - `/api/v1/auth/otp/request`: حداکثر ۵ درخواست بر دقیقه بر اساس IP + کول‌داون ۱۲۰ ثانیه.
  - `/api/v1/auth/otp/verify`: حداکثر ۱۰ درخواست بر دقیقه بر اساس IP + حداکثر ۳ تلاش ناموفق کد.

### ب) دیواره آتش و مسدودساز ربات‌ها (`nginx/nginx.conf` و `nginx/nginx.prod.conf`)
- ایجاد جدول مپ `$bad_bot` برای مسدودسازی اسکنرهای خودکار با پاسخ `403 Forbidden`.
- محدودیت همزمانی اتصال `limit_conn addr_conn 30;` برای هر IP جهت مقابله با DoS.
- محدودیت نرخ درخواست روت‌های احراز هویت `limit_req zone=auth_limit burst=5 nodelay;`.
- مسدودسازی پویش فایل‌های مخفی حساس (`.env`، `.git`، `.aws`، کدهای اسکریپت `*.php`).

### ج) موتور دسترسی و پالیسی Casbin (`backend/app/core/security/`)
- فایل کانفیگ مدل: `rbac_model.conf`.
- فایل سیاست‌های پیش‌فرض: `rbac_policy.csv`.
- ماژول سرویس `casbin_enforcer.py` با دپندنسی آماده `RequireCasbinPolicy(resource, action)`.

### د) احراز هویت دوعاملی و کلیدهای عبور MFA (`backend/app/core/security/mfa.py`)
- تولید سکرت، لینک QR استاندارد `otpauth://`، و ۸ کد بازیابی یکبار مصرف.
- تابع تایید کدهای ۶ رقمی با تلورانس ۳۰ ثانیه‌ای ساعت کلاینت.
- ایجاد گزینه‌های رجیستریشن برای Passkeys تحت استاندارد WebAuthn.
- اندپوینت‌های `/api/v1/auth/mfa/totp/setup` و `/api/v1/auth/mfa/totp/verify` و `/api/v1/auth/mfa/passkey/register/options`.

---

## ۵. تست و راستی‌آزمایی

- اجرای تست‌های اختصاصی امنیت:
  ```bash
  cd backend && PYTHONPATH=. pytest tests/unit/test_security_suite.py
  ```
- اجرای کلیه تست‌های واحد بک‌اند:
  ```bash
  cd backend && PYTHONPATH=. pytest tests/unit/
  # خروجی: 144 passed
  ```
- بیلد و بررسی تایپ‌چک فرانت‌اند:
  ```bash
  cd frontend && npm run build
  # خروجی: Compiled successfully
  ```
