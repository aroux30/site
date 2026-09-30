# راهنمای جامع سرویس‌ها، پورت‌ها و دسترسی‌های سرور
## پلتفرم فروشگاه اینترنتی سازمانی (Enterprise E-Commerce Platform)
**آدرس دامنه رسمی:** [https://site.arouxpingg.com](https://site.arouxpingg.com)  
**آی‌پی سرور:** `<production-host>`  
**مسیر پروژه روی سرور:** `/root/site`  

---

## ۱. جدول دسترسی به پنل‌ها و سرویس‌های فعال فروشگاه

| نام سرویس | نقش و کاربرد | آدرس دسترسی (URL) | پورت | نام کاربری | رمز عبور پیش‌فرض سرور |
|---|---|---|:---:|:---:|:---:|
| **فروشگاه اصلی (Storefront)** | ظاهر اصلی سایت برای خرید کاربران | [https://site.arouxpingg.com](https://site.arouxpingg.com) | ۴۴۳ (SSL) | — | — |
| **داشبورد مدیریت (Admin)** | مدیریت سفارش‌ها، محصولات، کاربران، کانبان و گزارش‌ها | [https://site.arouxpingg.com/admin/dashboard](https://site.arouxpingg.com/admin/dashboard) | ۴۴۳ (SSL) | `09123456789` | `ADMIN_INITIAL_PASSWORD` (از .env سرور) |
| **مستندات Swagger API** | کاتالوگ تعاملی و اجرای تستی ۱۷۴ اندپوینت بک‌اند | [https://site.arouxpingg.com/docs](https://site.arouxpingg.com/docs) | ۴۴۳ (SSL) | — | — |
| **مستندات ReDoc API** | نمایش گرافیکی و ساختاریافته مشخصات فنی API | [https://site.arouxpingg.com/redoc](https://site.arouxpingg.com/redoc) | ۴۴۳ (SSL) | — | — |
| **فضای ذخیره‌سازی MinIO S3** | پنل مدیریت ابری فایل‌ها، تصاویر محصولات و فیش‌های بانکی | `http://<production-host>:9001` | ۹۰۰۱ | `minioadmin` | `MINIO_ROOT_PASSWORD` (از .env سرور) |
| **داشبورد مانیتورینگ Grafana** | مشاهده نمودارهای مصرف CPU، رم و ترافیک سرور | `http://<production-host>:3005` | ۳۰۰۵ | `admin` | `GRAFANA_ADMIN_PASSWORD` (از .env سرور) |
| **موتور متریک Prometheus** | جمع‌آوری آمار و متغیرهای کارایی سرور و داکر | `http://<production-host>:9090` | ۹۰۹۰ | — | — |
| **موتور جستجوی Elasticsearch** | هسته جستجوی فارسی، فیلترها و اصلاح املایی کالاها | `http://<production-host>:9200` | ۹۲۰۰ | — | — |
| **پایگاه داده PostgreSQL** | بانک اطلاعاتی اصلی سیستم (۷۵ جدول اطلاعاتی) | `localhost:5432` (کانتینر) | ۵۴۳۲ | `ecommerce` | `POSTGRES_PASSWORD` (از .env سرور) |
| **حافظه کش Redis** | مدیریت نشست‌ها، سبد خرید مهمان و Rate Limit | `localhost:6379` (کانتینر) | ۶۳۷۹ | — | `REDIS_PASSWORD` (از .env سرور) |

---

## ۲. پروژه‌های مستقل شما روی همین سرور (کاملاً فعال و بدون تداخل)

| نام پروژه | موضوع | پورت دسترسی | آدرس دسترسی |
|---|---|:---:|---|
| **پروژه املاک (Real Estate)** | سامانه املاک و مستغلات | ۳۰۰۱ | `http://<production-host>:3001` |
| **ربات ریزرگلد (Razer Gold)** | پنل و ربات ریزرگلد | ۸۰۸۰ | `http://<production-host>:8080` |
| **فرانت سئو (SEO Frontend)** | پنل کاربری سئو | ۳۰۰۲ | `http://<production-host>:3002` |
| **بک‌اند سئو (SEO Backend)** | اندپوینت‌های سئو | ۸۰۰۲ | `http://<production-host>:8002/docs` |
| **ربات و پنل VPN** | سرویس و ربات تلگرام VPN | ۸۰۰۳ و ۴۴۳ | `https://bot.pingmiss.online` |

---

## ۳. دستورات پرکاربرد خط فرمان در سرور (از طریق SSH)

```bash
# رفتن به پوشه اصلی پروژه
cd /root/site

# مشاهده وضعیت سلامت تمام کانتینرها
docker ps --filter "name=ecommerce"

# بررسی لاگ خطاهای کانتینر بک‌اند
docker logs ecommerce-backend --tail 50 -f

# بررسی لاگ خطاهای کانتینر فرانت‌اند
docker logs ecommerce-frontend --tail 50 -f

# اجرای تست‌های خودکار بک‌اند روی سرور
docker exec ecommerce-backend pytest tests/ -v

# ایجاد بکاپ دستی از دیتابیس (PostgreSQL + MinIO؛ خروجی در پوشه backups/)
bash scripts/backup.sh -d ecommerce

# تست بازیابی بکاپ بدون دست‌زدن به داده‌های اصلی (بکاپ را در یک دیتابیس موقت
# بازیابی می‌کند، تعداد رکوردها را چاپ می‌کند و سپس دیتابیس موقت را حذف می‌کند)
bash scripts/verify_backup.sh

# بازیابی واقعی از یک بکاپ مشخص (مخرب است؛ checksum قبل از بازیابی بررسی می‌شود)
bash scripts/restore.sh -f backups/app_db_20260909_120000.sql.gz -y
```

راهنمای کامل بکاپ/بازیابی: `docs/runbooks/BACKUP_RESTORE.md`
