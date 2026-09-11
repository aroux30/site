# 🚀 Enterprise Stress Load Testing Suite (Locust)
## شبیه‌ساز تست بارگذاری و استرس همزمان ۱۰,۰۰۰ کاربر (Iranian Headless E-Commerce Platform)

این پکیج جهت ارزیابی، بنچ‌مارک و تست استرس رفتار پلتفرم تحت بارگذاری سنگین همروند (High-Concurrency / Spike Traffic) شامل کمپین‌های فروش ویژه (یلدا، بلک فرایدی و سال نو) طراحی شده است.

---

## ۱. معماری و نیازمندی‌های شبیه‌سازی ۱۰,۰۰۰ کاربر همزمان (Capacity & Math Model)

### ۱.۱. تفاوت همروندی کاربران (Active Sessions) و نرخ درخواست (RPS)
در تست بارگذاری واقعی:
- **سناریو ۱: ۱۰,۰۰۰ کاربر فعال با زمان تفکر طبیعی (Think Time = 2s–4s):**
  $$\text{Throughput} \approx \frac{10,000 \text{ Users}}{3 \text{ Seconds}} \approx 3,333 \text{ Requests/Sec (RPS)}$$
- **سناریو ۲: هجوم ناگهانی استرس (Spike / Stampede / Zero Think Time):**
  $$\text{Throughput} \ge 10,000 \text{ Requests/Sec}$$

برای تحمل این ترافیک بدون بروز خطاهای `502 Bad Gateway`، `504 Gateway Timeout` یا `Connection Refused`، تنظیمات در ۵ لایه زیر اجباری است:

---

## ۲. راهنمای تیونینگ سرور برای پایداری ۱۰,۰۰۰ کاربر (Production Server Tuning)

### ۲.۱. تنظیمات هسته لینوکس (`/etc/sysctl.conf`)
سوکت‌های TCP و بافرهای شبکه سیستم‌عامل باید ارتقا یابند:

```ini
# افزایش سقف فایل دیسکریپتورها
fs.file-max = 2097152

# افزایش صف اتصالات ورودی TCP (جلوگیری از Drop شدن SYN packets)
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535

# بازیافت سریع پورت‌های در وضعیت TIME_WAIT
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_fin_timeout = 15

# بازه پورت‌های Ephemeral جهت برقراری اتصال به Upstream
net.ipv4.ip_local_port_range = 1024 65535

# بافرهای حافظه سوکت‌های شبکه
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
```
اجرای اعمال تغییرات: `sysctl -p`

### ۲.۲. تنظیمات محدودیت دیسکریپتورها (`/etc/security/limits.conf`)
```text
* soft nofile 100000
* hard nofile 100000
root soft nofile 100000
root hard nofile 100000
```

### ۲.۳. پیکربندی Nginx Reverse Proxy (`nginx.prod.conf`)
برای پروکسی کردن ۱۰,۰۰۰ اتصال کلاینت، Nginx به حداقل ۲۰,۰۰۰ تا ۳۰,۰۰۰ اتصال همروند نیاز دارد (۱۰k ورودی + ۱۰k به Backend):

```nginx
worker_processes auto;
worker_rlimit_nofile 100000;

events {
    worker_connections 32768;
    multi_accept on;
    use epoll;
}

http {
    # Keepalive اتصالات بالادستی به کانتینرهای FastAPI
    upstream backend {
        least_conn;
        server backend:8000 max_fails=3 fail_timeout=30s;
        keepalive 256;
    }

    # مجاز کردن ترافیک تست استرس با توکن ویژه (عدم اعمال Rate Limit تکی)
    map $http_x_load_test_bypass $limit_key {
        "stress-test-authorized-2026" "";
        default $binary_remote_addr;
    }

    limit_req_zone $limit_key zone=api_limit:20m rate=1000r/s;
}
```

### ۲.۴. معماری اتصال به دیتابیس (SQLAlchemy Pool & PgBouncer)
در سرور دیتابیس، امکان باز کردن مستقیم ۱۰,۰۰۰ اتصال PostgreSQL همزمان وجود ندارد (هر پردازش Postgres نیازمند ۵ الی ۱۰ مگابایت رم است که منجر به کرش سرور با ۱۰۰ گیگابایت مصرف رم می‌شود).
- **راهکار معمارانه:**
  1. **PgBouncer (Transaction Mode):** ۱۰,۰۰۰ اتصال کلاینت را روی یک استخر (Pool) بهینه شامل ۱۰۰ الی ۲۰۰ کانکشن واقعی پایگاه‌داده مولتی‌پلکس (Multiplex) می‌کند.
  2. **کَش ردیس (Redis Layer):** بیش از ۸۵٪ درخواست‌های کاتالوگ و صفحات محصول باید توسط Redis سرویس‌دهی شوند تا بار از دیتابیس برداشته شود.

---

## ۳. ساختار پکیج Locust در پروژه

```
load_tests/
├── locustfile.py               # فایل ورودی اصلی و تعریف User Personaها
├── locust.conf                 # فایل کانفیگ پیش‌فرض Locust
├── docker-compose.locust.yml   # کلاستر توزیع‌شده Locust Master + Workers
├── run_stress_test.py          # اسکریپت پایتون خودکار با تحلیل SLA و تولید گزارش
├── run_stress_test.sh          # اسکریپت شل قابل اجرا در Linux
├── common/
│   ├── config.py               # آدرس سرور، هدرهای تست و کلیدواژه‌های فارسی
│   └── helpers.py              # توابع تولید Session، اعتبارسنجی JSON و ژنراتور نیم‌فاصله
├── scenarios/
│   ├── browsing.py             # پیمایش دسته‌ها، لیست محصولات و جستجوی فارسی (ZWNJ)
│   ├── cart.py                 # سبد خرید، افزودن کالا و اعتبارسنجی موجودی
│   ├── checkout.py             # دریافت پیش‌فاکتور (Quote) و بررسی قفل همروندی
│   ├── health.py               # پروب‌های لایونس و آمادگی (/api/health/ready)
│   └── wallet.py               # استعلام موجودی کیف پول و تراکنش‌ها
└── shapes/
    └── load_shapes.py          # الگوهای بارگذاری پله‌ای و Spike ۱۰,۰۰۰ کاربری
```

---

## ۴. نحوه اجرای تست‌های استرس

### سناریو ۱: اجرای تست سریع Headless محلی (۵۰ تا ۵۰۰ کاربر)
```bash
python load_tests/run_stress_test.py --users 100 --spawn-rate 20 --run-time 30s --headless
```

### سناریو ۲: اجرای تست بارگذاری استرس متوسط (۱,۰۰۰ کاربر) با بررسی خودکار SLA
```bash
python load_tests/run_stress_test.py --users 1000 --spawn-rate 100 --run-time 1m --headless --assert-sla
```

### سناریو ۳: اجرای کلاستر توزیع‌شده برای تست کامل ۱۰,۰۰۰ کاربر همزمان (Docker Distributed)
برای شبیه‌سازی واقعی ۱۰,۰۰۰ کاربر، کلاستر لوکاست متشکل از ۱ مستر و ۸ ورکر اجرا می‌شود:

```bash
# راه‌اندازی مستر و ۸ ورکر
docker compose -f load_tests/docker-compose.locust.yml up --scale locust-worker=8 -d

# باز کردن پنل تحت وب در مرورگر:
# http://localhost:8089
```

پس از باز شدن داشبورد:
- **Number of users:** `10000`
- **Spawn rate:** `200`
- **Host:** `https://site.arouxpingg.com`
- روی دکمه **Start Swarming** کلیک کنید.

---

## ۵. خروجی‌ها و گزارش‌های تولیدی

هر اجرای اسکریپت `run_stress_test.py` مصنوعات زیر را در مسیر `load_tests/reports/` تولید می‌کند:
1. **گزارش تصویری تعاملی (HTML Report):** شامل نمودارهای خطی RPS، زمان پاسخگویی Response Time (p50, p95, p99) و توزیع خطاها.
2. **فایل‌های داده آماری (CSV Files):** `_stats.csv`، `_failures.csv` و `_stats_history.csv`.
3. **خلاصه یکپارچه CI/CD (JSON Summary):** قابل خواندن در خط لوله گیت‌هاب جهت Fail/Pass خودکار بر اساس SLA.
