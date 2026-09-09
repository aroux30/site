"""Database seed script for Iranian E-Commerce Platform.

Populates categories, brands, products, variants, inventory, shipping methods,
coupons, settings, and gamification rules.

Usage::

    python scripts/seed.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.session import async_session_factory
from app.modules.catalog.domain.models import (
    Brand,
    Category,
    Product,
    ProductImage,
    ProductStatus,
    ProductType,
    ProductVariant,
)
from app.modules.discounts.domain.models import (
    Coupon,
    Discount,
    DiscountScope,
    DiscountType,
)
from app.modules.gamification.domain.models import GamificationRule, Reward
from app.modules.inventory.domain.models import InventoryItem
from app.modules.settings.domain.models import SiteSetting
from app.modules.shipping.domain.models import ShippingMethod, ShippingRate


async def seed() -> None:
    """Run database seed transaction."""
    print("🌱 Starting database seed...")

    async with async_session_factory() as db:
        # 1. Site Settings
        print("  - Seeding site settings...")
        settings_data = [
            ("site_title", {"value": "فروشگاه اینترنتی ایرانیان"}, "general", "عنوان اصلی وب‌سایت", True),
            ("support_phone", {"value": "۰۲۱-۸۸۸۸۸۸۸۸"}, "contact", "شماره تلفن پشتیبانی", True),
            ("free_shipping_min_toman", {"value": 500_000}, "shipping", "حداقل مبلغ برای ارسال رایگان (تومان)", True),
        ]
        for key, val, grp, desc, pub in settings_data:
            stmt = select(SiteSetting).where(SiteSetting.key == key)
            if not (await db.execute(stmt)).scalar_one_or_none():
                db.add(SiteSetting(key=key, value=val, group=grp, description=desc, is_public=pub))

        # 2. Shipping Methods
        print("  - Seeding shipping methods...")
        shipping_methods = [
            ("پست پیشتاز سراسری", "pishtaz", "شرکت ملی پست", 3, 5, 450_000),  # 45,000 Toman in Rials
            ("ارسال اکسپرس فوری (تهران)", "express", "پیک اختصاصی", 1, 1, 850_000),  # 85,000 Toman
            ("تیپاکس هوایی", "tipax", "تیپاکس", 1, 2, 700_000),  # 70,000 Toman
        ]
        for name, slug, prov, min_d, max_d, rate_price in shipping_methods:
            stmt = select(ShippingMethod).where(ShippingMethod.slug == slug)
            method = (await db.execute(stmt)).scalar_one_or_none()
            if not method:
                method = ShippingMethod(
                    name=name,
                    slug=slug,
                    provider=prov,
                    estimated_days_min=min_d,
                    estimated_days_max=max_d,
                    is_active=True,
                )
                db.add(method)
                await db.flush()

                # Default nationwide rate
                db.add(ShippingRate(
                    method_id=method.id,
                    province="all",
                    min_weight=0,
                    max_weight=10000,
                    min_order_amount=0,
                    price=rate_price,
                ))

        # 3. Brands
        print("  - Seeding brands...")
        brands_data = [
            ("اپل", "apple", "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg"),
            ("سامسونگ", "samsung", "https://upload.wikimedia.org/wikipedia/commons/2/24/Samsung_Logo.svg"),
            ("شیائومی", "xiaomi", "https://upload.wikimedia.org/wikipedia/commons/a/ae/Xiaomi_logo_%282021-%29.svg"),
            ("سونی", "sony", "https://upload.wikimedia.org/wikipedia/commons/c/ca/Sony_logo.svg"),
            ("ایسوس", "asus", "https://upload.wikimedia.org/wikipedia/commons/2/2e/ASUS_Logo.svg"),
        ]
        brand_map = {}
        for name, slug, logo in brands_data:
            stmt = select(Brand).where(Brand.slug == slug)
            b = (await db.execute(stmt)).scalar_one_or_none()
            if not b:
                b = Brand(name=name, slug=slug, logo_url=logo, is_active=True)
                db.add(b)
                await db.flush()
            brand_map[slug] = b

        # 4. Categories
        print("  - Seeding categories...")
        categories_data = [
            ("کالای دیجیتال", "digital", "کالای دیجیتال و گجت‌های هوشمند"),
            ("گوشی موبایل", "mobile", "انواع گوشی‌های هوشمند پرچمدار و اقتصادی"),
            ("لپ‌تاپ و اولترابوک", "laptops", "لپ‌تاپ‌های گیمینگ، مهندسی و اداری"),
            ("لوازم جانبی و صوتی", "audio", "هدفون، هندزفری، اسپیکر و پاوربانک"),
            ("ساعت هوشمند", "smartwatch", "ساعت‌ها و مچ‌بندهای سلامتی و ورزشی"),
        ]
        cat_map = {}
        root_cat = None
        for name, slug, desc in categories_data:
            stmt = select(Category).where(Category.slug == slug)
            c = (await db.execute(stmt)).scalar_one_or_none()
            if not c:
                parent_id = root_cat.id if slug != "digital" and root_cat else None
                c = Category(
                    name=name,
                    slug=slug,
                    description=desc,
                    parent_id=parent_id,
                    depth=1 if parent_id else 0,
                    path=f"/{slug}",
                    is_active=True,
                )
                db.add(c)
                await db.flush()
            if slug == "digital":
                root_cat = c
            cat_map[slug] = c

        # 5. Products & Variants
        print("  - Seeding products and variants...")
        products_data = [
            {
                "name": "گوشی موبایل سامسونگ گلکسی S24 Ultra",
                "slug": "samsung-galaxy-s24-ultra",
                "short_description": "پرچمدار بی‌رقیب سامسونگ با هوش مصنوعی Galaxy AI و دوربین ۲۰۰ مگاپیکسلی",
                "description": "گوشی سامسونگ گلکسی اس ۲۴ اولترا مجهز به پردازنده اسنپدراگون ۸ نسل ۳، قلم S-Pen اختصاصی، شیشه ضد انعکاس تیتانیومی و پشتیبانی نرم‌افزاری ۷ ساله.",
                "brand": "samsung",
                "category": "mobile",
                "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=800",
                "variants": [
                    {"sku": "SAM-S24U-256", "price_toman": 68_500_000, "name": "۲۵۶ گیگابایت / خاکستری تیتانیوم", "stock": 15},
                    {"sku": "SAM-S24U-512", "price_toman": 77_900_000, "name": "۵۱۲ گیگابایت / مشکی تیتانیوم", "stock": 10},
                ],
            },
            {
                "name": "گوشی موبایل اپل آیفون 16 پرو مکس",
                "slug": "apple-iphone-16-pro-max",
                "short_description": "قدرتمندترین آیفون تاریخ با چیپست A18 Pro و کلید دوربین Camera Control",
                "description": "آیفون ۱۶ پرو مکس با بدنه تیتانیومی سبک، نمایشگر ۶.۹ اینچی Super Retina XDR، زوم اپتیکال ۵ برابری و سیستم هوشمند Apple Intelligence.",
                "brand": "apple",
                "category": "mobile",
                "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=800",
                "variants": [
                    {"sku": "APL-IP16PM-256", "price_toman": 95_000_000, "name": "۲۵۶ گیگابایت / تیتانیوم صحرایی", "stock": 8},
                    {"sku": "APL-IP16PM-512", "price_toman": 108_000_000, "name": "۵۱۲ گیگابایت / تیتانیوم طبیعی", "stock": 5},
                ],
            },
            {
                "name": "لپ‌تاپ اولترابوک ایسوس ذن‌بوک 14 OLED",
                "slug": "asus-zenbook-14-oled",
                "short_description": "اولترابوک فوق باریک با پردازنده اینتل Core Ultra 7 و نمایشگر 120Hz OLED",
                "description": "ایسوس Zenbook 14 OLED با وزن تنها ۱.۲ کیلوگرم، باتری قدرتمند با بازدهی ۱۵ ساعت کار مداوم، ۱۶ گیگابایت رم LPDDR5X و ۱ ترابایت حافظه SSD NVMe.",
                "brand": "asus",
                "category": "laptops",
                "image": "https://images.unsplash.com/photo-1541807084-5c52b6b3adef?w=800",
                "variants": [
                    {"sku": "ASU-ZB14-U7", "price_toman": 62_000_000, "name": "Core Ultra 7 / 16GB / 1TB SSD", "stock": 12},
                ],
            },
            {
                "name": "هدفون بی‌سیم نویز کنسلینگ سونی WH-1000XM5",
                "slug": "sony-wh-1000xm5-wireless-headphones",
                "short_description": "پادشاه حذف نویز با دو پردازنده اختصاصی و صدای فوق شفاف Hi-Res Audio",
                "description": "هدفون روگوشی سونی WH-1000XM5 با طراحی ارگونومیک جدید، ۸ میکروفون جهت حذف صدای محیط، شارژدهی ۳۰ ساعته و شارژ سریع ۳ دقیقه‌ای برای ۳ ساعت پخش.",
                "brand": "sony",
                "category": "audio",
                "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800",
                "variants": [
                    {"sku": "SNY-XM5-BLK", "price_toman": 16_800_000, "name": "رنگ مشکی مات", "stock": 25},
                    {"sku": "SNY-XM5-SLV", "price_toman": 16_800_000, "name": "رنگ نقره‌ای پلاتینیوم", "stock": 18},
                ],
            },
            {
                "name": "ساعت هوشمند اپل واچ اولترا ۲",
                "slug": "apple-watch-ultra-2",
                "short_description": "سخت‌جان‌ترین ساعت هوشمند اپل با روشنایی ۳۰۰۰ نیت و GPS دو فرکانسه",
                "description": "اپل واچ اولترا ۲ مناسب غواصی و ورزش‌های ماجراجویانه، بدنه تیتانیومی ضد ضربه ۴۹ میلی‌متری و عمر باتری تا ۷۲ ساعت در حالت ذخیره انرژی.",
                "brand": "apple",
                "category": "smartwatch",
                "image": "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800",
                "variants": [
                    {"sku": "APL-WUO2-ALP", "price_toman": 48_500_000, "name": "بند آلپاین نارنجی", "stock": 14},
                ],
            },
            {
                "name": "پاوربانک ۲۰۰۰۰ میلی‌آمپر ۵۰ وات شیائومی",
                "slug": "xiaomi-50w-powerbank-20000",
                "short_description": "پاوربانک فست شارژ ۵۰ واتی با قابلیت شارژ لپ‌تاپ و سه خروجی همزمان",
                "description": "پاوربانک شیائومی با پورت Type-C دوطرفه ۵۰ وات، حفاظت چندگانه الکترونیکی در برابر نوسان برق و بدنه ضد خط و خش مات.",
                "brand": "xiaomi",
                "category": "audio",
                "image": "https://images.unsplash.com/photo-1609091839311-d5365f9ff1c5?w=800",
                "variants": [
                    {"sku": "XIA-PB20-50W", "price_toman": 2_450_000, "name": "مشکی مات", "stock": 40},
                ],
            },
        ]

        for pdata in products_data:
            stmt = select(Product).where(Product.slug == pdata["slug"])
            prod = (await db.execute(stmt)).scalar_one_or_none()
            if not prod:
                brand = brand_map.get(pdata["brand"])
                cat = cat_map.get(pdata["category"])
                prod = Product(
                    name=pdata["name"],
                    slug=pdata["slug"],
                    short_description=pdata["short_description"],
                    description=pdata["description"],
                    brand_id=brand.id if brand else None,
                    category_id=cat.id if cat else None,
                    product_type=ProductType.VARIABLE,
                    status=ProductStatus.ACTIVE,
                    is_active=True,
                    is_featured=True,
                )
                db.add(prod)
                await db.flush()

                # Primary Image
                db.add(ProductImage(
                    product_id=prod.id,
                    url=pdata["image"],
                    alt_text=prod.name,
                    is_primary=True,
                    position=0,
                ))

                # Variants & Inventory
                for i, vdata in enumerate(pdata["variants"]):
                    # Price stored in Rials (1 Toman = 10 Rials)
                    price_rials = vdata["price_toman"] * 10
                    variant = ProductVariant(
                        product_id=prod.id,
                        sku=vdata["sku"],
                        price=price_rials,
                        compare_at_price=int(price_rials * 1.05),
                        cost=int(price_rials * 0.85),
                        is_active=True,
                        position=i,
                    )
                    db.add(variant)
                    await db.flush()

                    # Stock inventory item
                    db.add(InventoryItem(
                        variant_id=variant.id,
                        available=vdata["stock"],
                        reserved=0,
                        committed=0,
                        track_inventory=True,
                        low_stock_threshold=3,
                    ))

        # 6. Coupons
        print("  - Seeding promotional coupons...")
        now = datetime.now(timezone.utc)
        discounts = [
            ("تخفیف ۱۰ درصدی خوش‌آمدگویی", DiscountType.PERCENTAGE, 1000, "WELCOME", 500_000_000),  # 10%
            ("تخفیف ۵۰ هزار تومانی ویژه", DiscountType.FIXED, 500_000, "OFF50", 1_000_000),  # 50,000 Toman in Rials
        ]
        for dname, dtype, dval, code, min_cart in discounts:
            stmt = select(Coupon).where(Coupon.code == code)
            if not (await db.execute(stmt)).scalar_one_or_none():
                disc = Discount(
                    name=dname,
                    type=dtype,
                    value=dval,
                    min_cart_amount=min_cart,
                    starts_at=now - timedelta(days=1),
                    ends_at=now + timedelta(days=365),
                    is_active=True,
                    scope=DiscountScope.GLOBAL,
                )
                db.add(disc)
                await db.flush()
                db.add(Coupon(
                    discount_id=disc.id,
                    code=code,
                    is_active=True,
                    starts_at=now - timedelta(days=1),
                    ends_at=now + timedelta(days=365),
                ))

        # 7. Gamification Rules & Rewards
        print("  - Seeding gamification rules & rewards...")
        rules = [
            ("ثبت سفارش موفق", "order_completed", 100),
            ("ثبت دیدگاه برای محصول", "review_submitted", 25),
            ("ثبت‌نام در وب‌سایت", "user_registered", 50),
        ]
        for rname, ev_type, pts in rules:
            stmt = select(GamificationRule).where(GamificationRule.event_type == ev_type)
            if not (await db.execute(stmt)).scalar_one_or_none():
                db.add(GamificationRule(name=rname, event_type=ev_type, points=pts, is_active=True))

        rewards = [
            ("کد تخفیف ۵۰ هزار تومانی", "کد تخفیف اختصاصی برای سفارش بعدی شما", "coupon", 100, 50),
            ("ارسال کاملاً رایگان سفارش", "ارسال رایگان بدون محدودیت سقف خرید", "shipping", 50, 100),
            ("تی‌شرت اختصاصی فروشگاه ایرانیان", "تی‌شرت باکیفیت طرح اختصاصی برنامه", "gift", 250, 20),
        ]
        for rw_name, rw_desc, rw_type, pts_req, qty in rewards:
            stmt = select(Reward).where(Reward.name == rw_name)
            if not (await db.execute(stmt)).scalar_one_or_none():
                db.add(Reward(
                    name=rw_name,
                    description=rw_desc,
                    type=rw_type,
                    points_required=pts_req,
                    quantity_available=qty,
                    is_active=True,
                ))

        await db.commit()
        print("✅ Database seed completed successfully!")


if __name__ == "__main__":
    asyncio.run(seed())
