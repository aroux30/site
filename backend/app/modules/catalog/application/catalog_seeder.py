"""Comprehensive Iranian E-Commerce Catalog Seeder.

Creates standard e-commerce hierarchical categories, brands, products,
variants, images, and inventory rows with realistic prices and details.
"""

import asyncio
import uuid
from typing import Any
import structlog
from sqlalchemy import select, func, delete
from app.core.database.session import async_session_factory
from app.modules.catalog.domain.models import (
    Category,
    Brand,
    Product,
    ProductVariant,
    ProductImage,
    ProductType,
    ProductStatus,
)
from app.modules.inventory.domain.models import InventoryItem
from app.modules.search.application.search_service import SearchService

logger = structlog.get_logger(__name__)

# Prices are in Toman * 10 (stored as Rial in DB)
def toman_to_rial(toman: int) -> int:
    return toman * 10


CATEGORIES_DATA = [
    # Level 0 Roots
    {
        "name": "کالای دیجیتال",
        "slug": "digital-goods",
        "description": "انواع گوشی‌های هوشمند، تبلت، ساعت هوشمند و لوازم دیجیتال پیشرفته با گارانتی معتبر شرکتی.",
        "image_url": "https://images.unsplash.com/photo-1519389950473-47ba0277781c?w=500&q=80",
        "position": 10,
        "children": [
            {
                "name": "گوشی هوشمند",
                "slug": "smartphones",
                "description": "جدیدترین پرچمداران اپل، سامسونگ، شیائومی با رجیستری رسمی و ارسال فوری.",
                "image_url": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?w=500&q=80",
                "position": 1,
            },
            {
                "name": "تبلت و کتاب‌خوان",
                "slug": "tablets",
                "description": "انواع آی‌پد و تبلت‌های سامسونگ برای طراحی، مطالعه و کارهای روزمره.",
                "image_url": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=500&q=80",
                "position": 2,
            },
            {
                "name": "ساعت و مچ‌بند هوشمند",
                "slug": "smartwatches",
                "description": "ساعت‌های هوشمند اپل واچ و گلکسی واچ برای پایش سلامت و ورزش.",
                "image_url": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500&q=80",
                "position": 3,
            },
        ],
    },
    {
        "name": "لپ‌تاپ و کامپیوتر",
        "slug": "laptops-computers",
        "description": "مک‌بوک‌ها، لپ‌تاپ‌های مهندسی و گیمینگ، مانیتور و قطعات کامپیوتر.",
        "image_url": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?w=500&q=80",
        "position": 20,
        "children": [
            {
                "name": "لپ‌تاپ و اولترابوک",
                "slug": "ultrabooks",
                "description": "لپ‌تاپ‌های باریک، سبک و قدرتمند اداری و دانشجویی.",
                "image_url": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500&q=80",
                "position": 1,
            },
            {
                "name": "لپ‌تاپ گیمینگ",
                "slug": "gaming-laptops",
                "description": "سیستم‌های گیمینگ پرقدرت ایسوس ROG، لنوو Legion و اچ‌پی OMEN.",
                "image_url": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=500&q=80",
                "position": 2,
            },
            {
                "name": "مانیتور و نمایشگر",
                "slug": "monitors",
                "description": "نمایشگرهای 4K و گیمینگ نرخ تازه‌سازی بالا مخصوص طراحان و گیمرها.",
                "image_url": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=500&q=80",
                "position": 3,
            },
        ],
    },
    {
        "name": "لوازم جانبی دیجیتال",
        "slug": "accessories",
        "description": "تجهیزات جانبی باکیفیت شامل شارژر، قاب، هدفون و پاوربانک.",
        "image_url": "https://images.unsplash.com/photo-1583394838336-acd977736f90?w=500&q=80",
        "position": 30,
        "children": [
            {
                "name": "شارژر و کابل",
                "slug": "chargers-cables",
                "description": "آداپتورهای فست شارژ انکر، کابل‌های بادوام تایپ سی و لایتنینگ.",
                "image_url": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=500&q=80",
                "position": 1,
            },
            {
                "name": "هدفون و هندزفری",
                "slug": "headphones",
                "description": "ایرپادز، گلکسی بادز و هدفون‌های نویزکنسلینگ سونی و انکر.",
                "image_url": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500&q=80",
                "position": 2,
            },
            {
                "name": "پاوربانک و شارژر همراه",
                "slug": "powerbanks",
                "description": "پاوربانک‌های ظرفیت بالا با فناوری شارژ سریع PD و ایمن.",
                "image_url": "https://images.unsplash.com/photo-1609592424300-c9a96e2b3438?w=500&q=80",
                "position": 3,
            },
            {
                "name": "قاب و کاور گوشی",
                "slug": "phone-cases",
                "description": "انواع قاب‌های سیلیکونی، ضدضربه، مگ‌سیف و فانتزی.",
                "image_url": "https://images.unsplash.com/photo-1601784551446-20c9e07cdbdb?w=500&q=80",
                "position": 4,
            },
        ],
    },
    {
        "name": "کنسول و گیمینگ",
        "slug": "gaming",
        "description": "کنسول‌های پلی‌استیشن، ایکس‌باکس، لوازم جانبی و تجهیزات گیمینگ حرفه‌ای.",
        "image_url": "https://images.unsplash.com/photo-1486401899868-0e435ed85128?w=500&q=80",
        "position": 40,
        "children": [
            {
                "name": "کنسول بازی",
                "slug": "consoles",
                "description": "پلی‌استیشن ۵ اسلیم، ایکس‌باکس سری ایکس و اس با پلمپ اصلی.",
                "image_url": "https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=500&q=80",
                "position": 1,
            },
            {
                "name": "دسته و کنترلر",
                "slug": "controllers",
                "description": "دسته‌های دوئل‌سنس و کنترلرهای بیسیم گیمینگ.",
                "image_url": "https://images.unsplash.com/photo-1592840496694-26d035b52b48?w=500&q=80",
                "position": 2,
            },
        ],
    },
]

BRANDS_DATA = [
    {"name": "اپل", "slug": "apple", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/f/fa/Apple_logo_black.svg"},
    {"name": "سامسونگ", "slug": "samsung", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/2/24/Samsung_Logo.svg"},
    {"name": "شیائومی", "slug": "xiaomi", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/2/29/Xiaomi_logo.svg"},
    {"name": "ایسوس", "slug": "asus", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/2/2e/ASUS_Logo.svg"},
    {"name": "لنوو", "slug": "lenovo", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/b/b8/Lenovo_logo_2015.svg"},
    {"name": "سونی", "slug": "sony", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/c/ca/Sony_logo.svg"},
    {"name": "انکر", "slug": "anker", "logo_url": "https://upload.wikimedia.org/wikipedia/commons/b/b7/Anker_logo.svg"},
]

PRODUCTS_SPEC = [
    # Smartphones
    {
        "name": "گوشی موبایل اپل مدل iPhone 16 Pro Max",
        "slug": "apple-iphone-16-pro-max",
        "category_slug": "smartphones",
        "brand_slug": "apple",
        "price": 89_500_000,
        "compare_at_price": 94_000_000,
        "sku": "IPHONE-16PM-256",
        "image": "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=800&q=80",
        "description": "پرچمدار جدید اپل با چیپست A18 Pro، بدنه تیتانیومی مقاوم، دکمه کنترل دوربین اختصاصی و سیستم هوش مصنوعی Apple Intelligence.",
    },
    {
        "name": "گوشی موبایل سامسونگ مدل Galaxy S24 Ultra",
        "slug": "samsung-galaxy-s24-ultra",
        "category_slug": "smartphones",
        "brand_slug": "samsung",
        "price": 68_900_000,
        "compare_at_price": 72_000_000,
        "sku": "SAM-S24U-256",
        "image": "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=800&q=80",
        "description": "گوشی کهکشانی سامسونگ مجهز به هوش مصنوعی پیشرفته Galaxy AI، دوربین ۲۰۰ مگاپیکسلی خارق‌العاده و قلم هوشمند S-Pen.",
    },
    {
        "name": "گوشی موبایل شیائومی مدل 14 Ultra 5G",
        "slug": "xiaomi-14-ultra",
        "category_slug": "smartphones",
        "brand_slug": "xiaomi",
        "price": 59_000_000,
        "compare_at_price": 63_000_000,
        "sku": "MI-14U-512",
        "image": "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=800&q=80",
        "description": "شاهکار عکاسی شیائومی با همکاری شرکت معتبر لایکا، سنسور ۱ اینچی سونی و پردازنده قدرتمند اسنپ‌دراگون ۸ نسل ۳.",
    },
    # Tablets
    {
        "name": "تبلت اپل مدل iPad Pro M4 (11 inch)",
        "slug": "apple-ipad-pro-m4-11",
        "category_slug": "tablets",
        "brand_slug": "apple",
        "price": 62_000_000,
        "compare_at_price": 66_000_000,
        "sku": "IPAD-PRO-M4-11",
        "image": "https://images.unsplash.com/photo-1544244015-0df4b3ffc6b0?w=800&q=80",
        "description": "نازک‌ترین محصول تاریخ اپل مجهز به تراشه فوق‌العاده سریع M4 و صفحه نمایش بی‌نظیر Ultra Retina XDR OLED.",
    },
    {
        "name": "تبلت سامسونگ مدل Galaxy Tab S9 Ultra",
        "slug": "samsung-galaxy-tab-s9-ultra",
        "category_slug": "tablets",
        "brand_slug": "samsung",
        "price": 54_500_000,
        "compare_at_price": 58_000_000,
        "sku": "SAM-TABS9U-256",
        "image": "https://images.unsplash.com/photo-1561154464-82e9adf32764?w=800&q=80",
        "description": "بزرگترین و قدرتمندترین تبلت اندرویدی با نمایشگر ۱۴.۶ اینچی داینامیک امولد ۲X و مقاومت کامل در برابر آب IP68.",
    },
    # Smartwatches
    {
        "name": "ساعت هوشمند اپل واچ اولترا ۲ (Apple Watch Ultra 2)",
        "slug": "apple-watch-ultra-2",
        "category_slug": "smartwatches",
        "brand_slug": "apple",
        "price": 43_800_000,
        "compare_at_price": 46_500_000,
        "sku": "AW-ULTRA2-49",
        "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=800&q=80",
        "description": "ساعت ورزشی و ماجراجویی اپل با بدنه تیتانیومی ۴۹ میلی‌متری، روشنایی ۳۰۰۰ نیت و شارژدهی تا ۷۲ ساعت در حالت ذخیره نیرو.",
    },
    {
        "name": "ساعت هوشمند سامسونگ مدل Galaxy Watch Ultra",
        "slug": "samsung-galaxy-watch-ultra",
        "category_slug": "smartwatches",
        "brand_slug": "samsung",
        "price": 31_000_000,
        "compare_at_price": 34_000_000,
        "sku": "SAM-WATCH-ULTRA",
        "image": "https://images.unsplash.com/photo-1508685096489-7aacd43bd3b1?w=800&q=80",
        "description": "ساعت پرچمدار اولترا سامسونگ با مقاومت در شرایط سخت تا دمای ۵۵ درجه، پایش دقیق ضربان و اکسیژن خون و بدنه تیتانیومی.",
    },
    # Laptops
    {
        "name": "لپ‌تاپ اپل مدل MacBook Pro 16 M3 Max",
        "slug": "apple-macbook-pro-16-m3-max",
        "category_slug": "ultrabooks",
        "brand_slug": "apple",
        "price": 185_000_000,
        "compare_at_price": 195_000_000,
        "sku": "MBP-16-M3MAX",
        "image": "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800&q=80",
        "description": "نهایت قدرت پردازشی برای برنامه‌نویسان و تدوین‌گران با تراشه ۱۶ هسته‌ای M3 Max، رم ۳۶ گیگابایت و ۲۲ ساعت شارژدهی باتری.",
    },
    {
        "name": "لپ‌تاپ گیمینگ ایسوس ROG Strix SCAR 18",
        "slug": "asus-rog-strix-scar-18",
        "category_slug": "gaming-laptops",
        "brand_slug": "asus",
        "price": 172_000_000,
        "compare_at_price": 180_000_000,
        "sku": "ASUS-SCAR18-4090",
        "image": "https://images.unsplash.com/photo-1603302576837-37561b2e2302?w=800&q=80",
        "description": "هیولای گیمینگ ایسوس با پردازنده Core i9 14900HX، کارت گرافیک RTX 4090 ۱۶ گیگابایت و نمایشگر ۲۴۰ هرتز Mini LED.",
    },
    {
        "name": "لپ‌تاپ لنوو مدل Legion Pro 7i",
        "slug": "lenovo-legion-pro-7i",
        "category_slug": "gaming-laptops",
        "brand_slug": "lenovo",
        "price": 128_000_000,
        "compare_at_price": 135_000_000,
        "sku": "LENOVO-LEGION-PRO7",
        "image": "https://images.unsplash.com/photo-1588872657578-7efd1f1555ed?w=800&q=80",
        "description": "لپ‌تاپ قدرتمند گیمینگ لنوو با سیستم خنک‌کننده اختصاصی Coldfront، هوش مصنوعی Lenovo AI Engine+ و گرافیک RTX 4080.",
    },
    {
        "name": "مانیتور ایسوس مدل ROG Swift OLED PG32UCDM",
        "slug": "asus-rog-swift-oled-pg32ucdm",
        "category_slug": "monitors",
        "brand_slug": "asus",
        "price": 79_000_000,
        "compare_at_price": 84_000_000,
        "sku": "ASUS-PG32UCDM-4K",
        "image": "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf?w=800&q=80",
        "description": "مانیتور ۳۲ اینچی 4K QD-OLED با نرخ تازه‌سازی ۲۴۰ هرتز، زمان پاسخگویی ۰.۰۳ میلی‌ثانیه و کنتراست بی‌نهایت.",
    },
    # Audio & Headphones
    {
        "name": "هدفون بلوتوثی سونی مدل WH-1000XM5",
        "slug": "sony-wh-1000xm5",
        "category_slug": "headphones",
        "brand_slug": "sony",
        "price": 18_900_000,
        "compare_at_price": 20_500_000,
        "sku": "SONY-WH1000XM5",
        "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=800&q=80",
        "description": "بهترین هدفون نویزکنسلینگ جهان با دو پردازنده اختصاصی نویزگیر، ۸ میکروفون هوشمند و کیفیت صدای فوق‌العاده Hi-Res Audio.",
    },
    {
        "name": "هدفون اپل مدل AirPods Pro (نسل دوم Type-C)",
        "slug": "apple-airpods-pro-2-type-c",
        "category_slug": "headphones",
        "brand_slug": "apple",
        "price": 12_800_000,
        "compare_at_price": 13_900_000,
        "sku": "AIRPODS-PRO-2-USBC",
        "image": "https://images.unsplash.com/photo-1600294037681-c80b4cb5b434?w=800&q=80",
        "description": "جدیدترین ایرپادز پرو مجهز به تراشه H2، درگاه شارژ تایپ سی، صدای فراگیر شخصی‌سازی شده و حذف نویز تا دو برابر قوی‌تر.",
    },
    {
        "name": "شارژر دیواری ۶۵ وات انکر مدل GaNPrime 735",
        "slug": "anker-ganprime-735-65w",
        "category_slug": "chargers-cables",
        "brand_slug": "anker",
        "price": 2_450_000,
        "compare_at_price": 2_700_000,
        "sku": "ANKER-735-65W",
        "image": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?w=800&q=80",
        "description": "شارژر فوق‌العاده جمع‌وجور و سریع با فناوری GaNPrime، سه درگاه همزمان (دو درگاه تایپ سی و یک USB-A) برای شارژ لپ‌تاپ و گوشی.",
    },
    {
        "name": "پاوربانک ۲۴۰۰۰ میلی‌آمپر انکر مدل 737 (PowerCore 24K)",
        "slug": "anker-737-powerbank-140w",
        "category_slug": "powerbanks",
        "brand_slug": "anker",
        "price": 6_900_000,
        "compare_at_price": 7_500_000,
        "sku": "ANKER-737-140W",
        "image": "https://images.unsplash.com/photo-1609592424300-c9a96e2b3438?w=800&q=80",
        "description": "پاوربانک هوشمند پرچمدار با خروجی فوق‌العاده ۱۴۰ وات Power Delivery 3.1، صفحه نمایش دیجیتال رنگی و قابلیت شارژ سریع مک‌بوک پرو.",
    },
    # Gaming
    {
        "name": "کنسول بازی سونی مدل PlayStation 5 Slim",
        "slug": "sony-playstation-5-slim",
        "category_slug": "consoles",
        "brand_slug": "sony",
        "price": 31_500_000,
        "compare_at_price": 33_500_000,
        "sku": "PS5-SLIM-1TB",
        "image": "https://images.unsplash.com/photo-1606813907291-d86efa9b94db?w=800&q=80",
        "description": "نسخه جدید و باریک‌تر کنسول محبوب نسل نهمی پلی‌استیشن ۵ با حافظه پرسرعت ۱ ترابایت SSD و قابلیت اجرای بازی‌ها با وضوح 4K 120Hz.",
    },
    {
        "name": "دسته بازی سونی مدل DualSense Edge",
        "slug": "sony-dualsense-edge-controller",
        "category_slug": "controllers",
        "brand_slug": "sony",
        "price": 10_900_000,
        "compare_at_price": 12_000_000,
        "sku": "DUALSENSE-EDGE-PS5",
        "image": "https://images.unsplash.com/photo-1592840496694-26d035b52b48?w=800&q=80",
        "description": "کنترلر فوق‌العاده حرفه‌ای پلی‌استیشن با قابلیت شخصی‌سازی کامل دکمه‌ها، استیک‌های تعویض‌پذیر و پدل‌های پشتی قابل برنامه‌ریزی.",
    },
]


async def seed_catalog():
    async with async_session_factory() as session:
        print("Starting catalog seeding...")

        # 1. Seed Brands
        brand_map = {}
        for b_data in BRANDS_DATA:
            res = await session.execute(select(Brand).where(Brand.slug == b_data["slug"]))
            existing = res.scalar_one_or_none()
            if not existing:
                brand = Brand(
                    name=b_data["name"],
                    slug=b_data["slug"],
                    logo_url=b_data["logo_url"],
                    is_active=True,
                )
                session.add(brand)
                await session.flush()
                brand_map[b_data["slug"]] = brand.id
            else:
                brand_map[b_data["slug"]] = existing.id
        print(f"Brands ready: {len(brand_map)}")

        # 2. Seed Categories (with hierarchy depth & path)
        cat_map = {}
        for root_data in CATEGORIES_DATA:
            res = await session.execute(select(Category).where(Category.slug == root_data["slug"]))
            root_cat = res.scalar_one_or_none()
            if not root_cat:
                root_cat = Category(
                    name=root_data["name"],
                    slug=root_data["slug"],
                    description=root_data.get("description"),
                    image_url=root_data.get("image_url"),
                    depth=0,
                    path=root_data["slug"],
                    position=root_data.get("position", 0),
                    is_active=True,
                )
                session.add(root_cat)
                await session.flush()
            cat_map[root_data["slug"]] = root_cat.id

            # Seed children
            for child_data in root_data.get("children", []):
                c_res = await session.execute(select(Category).where(Category.slug == child_data["slug"]))
                child_cat = c_res.scalar_one_or_none()
                if not child_cat:
                    child_cat = Category(
                        name=child_data["name"],
                        slug=child_data["slug"],
                        parent_id=root_cat.id,
                        description=child_data.get("description"),
                        image_url=child_data.get("image_url"),
                        depth=1,
                        path=f"{root_data['slug']}/{child_data['slug']}",
                        position=child_data.get("position", 0),
                        is_active=True,
                    )
                    session.add(child_cat)
                    await session.flush()
                cat_map[child_data["slug"]] = child_cat.id

        # Granular accessory subcategories so total categories exceed 50 (for pagination table test)
        for i in range(1, 42):
            sub_slug = f"acc-part-{i}"
            c_res = await session.execute(select(Category).where(Category.slug == sub_slug))
            if not c_res.scalar_one_or_none():
                p_id = cat_map.get("accessories")
                sub_cat = Category(
                    name=f"لوازم و تجهیزات جانبی شماره {i}",
                    slug=sub_slug,
                    parent_id=p_id,
                    depth=1,
                    path=f"accessories/{sub_slug}",
                    position=i,
                    is_active=True,
                )
                session.add(sub_cat)
                await session.flush()
                cat_map[sub_slug] = sub_cat.id

        print(f"Categories ready: {len(cat_map)}")

        # 3. Seed Products, Variants, Images, Inventory
        # Ensure we have at least 65 products so the pagination bar (pageSize=50) is active
        all_specs = list(PRODUCTS_SPEC)
        for base in PRODUCTS_SPEC:
            for variant_idx in (1, 2, 3):
                all_specs.append({
                    "name": f"{base['name']} - رنگ {['مشکی', 'نقره‌ای', 'تیتانیوم'][variant_idx - 1]}",
                    "slug": f"{base['slug']}-var-{variant_idx}",
                    "category_slug": base["category_slug"],
                    "brand_slug": base["brand_slug"],
                    "price": base["price"] + variant_idx * 500_000,
                    "compare_at_price": (base.get("compare_at_price") or base["price"]) + variant_idx * 500_000,
                    "sku": f"{base['sku']}-V{variant_idx}",
                    "image": base.get("image"),
                    "description": base.get("description"),
                })

        seeded_products_count = 0
        for p_data in all_specs:
            res = await session.execute(select(Product).where(Product.slug == p_data["slug"]))
            if res.scalar_one_or_none():
                continue

            category_id = cat_map.get(p_data["category_slug"])
            brand_id = brand_map.get(p_data["brand_slug"])
            if not category_id:
                continue

            product = Product(
                name=p_data["name"],
                slug=p_data["slug"],
                category_id=category_id,
                brand_id=brand_id,
                description=p_data.get("description"),
                short_description=p_data["name"],
                product_type=ProductType.SIMPLE,
                status=ProductStatus.ACTIVE,
                is_active=True,
                is_featured=True,
                min_order_quantity=1,
            )
            session.add(product)
            await session.flush()

            # Add primary image
            if p_data.get("image"):
                p_img = ProductImage(
                    product_id=product.id,
                    url=p_data["image"],
                    alt_text=p_data["name"],
                    is_primary=True,
                    position=0,
                )
                session.add(p_img)

            # Add default variant
            price_rial = toman_to_rial(p_data["price"])
            compare_price_rial = toman_to_rial(p_data["compare_at_price"]) if p_data.get("compare_at_price") else None
            variant = ProductVariant(
                product_id=product.id,
                sku=p_data["sku"],
                price=price_rial,
                compare_at_price=compare_price_rial,
                is_active=True,
                position=0,
            )
            session.add(variant)
            await session.flush()

            # Add inventory item with high available stock
            inv = InventoryItem(
                variant_id=variant.id,
                available=50,
                reserved=0,
                committed=0,
                damaged=0,
                incoming=0,
                low_stock_threshold=5,
            )
            session.add(inv)
            seeded_products_count += 1

        await session.commit()
        print(f"Products seeded successfully: {seeded_products_count}")

        # 4. Reindex Elasticsearch
        print("Reindexing Elasticsearch with new catalog...")
        search_svc = SearchService()
        reindex_res = await search_svc.reindex_all(session)
        print(f"Elasticsearch reindex complete: {reindex_res.indexed} indexed, {reindex_res.errors} errors")


if __name__ == "__main__":
    asyncio.run(seed_catalog())
