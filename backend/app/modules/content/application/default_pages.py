"""Core default storefront pages — seeded at startup, WordPress-install style.

The storefront's content pages (/about, /terms, /contact, /faq) are part of
the site's core: a fresh install ships them, like WordPress's installer
creates its default pages. The database is only the *storage for edits* —
operator changes from /admin/pages — so every backend startup guarantees the
defaults exist and never touches a row an operator has already customized
(insert-only, idempotent).

This mirrors the RBAC ``permission_seed`` contract: a seeding failure must
never block startup, so the lifespan caller wraps it in try/except.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.modules.content.domain.models import CmsPage, FAQItem, PageStatus

ABOUT_HTML = """
<h2>داستان ما</h2>
<p>ما با هدف ارائه بهترین تجربه خرید آنلاین، از سال ۱۳۹۸ فعالیت خود را آغاز کردیم و امروز افتخار خدمت‌رسانی به هزاران مشتری در سراسر ایران را داریم.</p>
<p>باور ما ساده است: خرید آنلاین باید سریع، مطمئن و شفاف باشد. برای همین هر کالا را پیش از عرضه بررسی می‌کنیم، قیمت‌ها را شفاف نگه می‌داریم و پشتیبانی را پاسخگوی ۷ روز هفته کرده‌ایم.</p>
<h2>آمار ما در یک نگاه</h2>
<ul>
<li>بیش از ۵ سال تجربه در تجارت الکترونیک</li>
<li>بیش از ۵۰٬۰۰۰ مشتری وفادار</li>
<li>بیش از ۱۰٬۰۰۰ کالای متنوع</li>
<li>۹۸٪ رضایت مشتریان</li>
</ul>
<h2>تیم ما</h2>
<ul>
<li><strong>سارا احمدی</strong> — مدیرعامل و بنیان‌گذار</li>
<li><strong>محمد رضایی</strong> — مدیر فنی</li>
<li><strong>زهرا کریمی</strong> — مدیر بازاریابی</li>
<li><strong>امیر حسینی</strong> — مدیر پشتیبانی</li>
</ul>
<h2>ارزش‌های ما</h2>
<p><strong>اعتماد:</strong> ضمانت اصالت کالا و بازگشت وجه در صورت مغایرت.</p>
<p><strong>شفافیت:</strong> قیمت واقعی، بدون هزینه پنهان.</p>
<p><strong>پاسخگویی:</strong> پشتیبانی انسانی، سریع و واقعی.</p>
"""

TERMS_HTML = """
<p>استفاده از خدمات این فروشگاه به منزله پذیرش کلیه قوانین، مقررات تجارت الکترونیکی و ضوابط زیر است. لطفاً پیش از ثبت سفارش این صفحه را با دقت مطالعه فرمایید.</p>
<p><em>آخرین بروزرسانی: شهریور ۱۴۰۵</em></p>
<h2>۱. تعاریف و کلیات</h2>
<p>کلیه اصول و رویه‌های این فروشگاه منطبق با قوانین جمهوری اسلامی ایران، قانون تجارت الکترونیک و قانون حمایت از حقوق مصرف‌کننده است و کاربر نیز موظف به رعایت قوانین مرتبط با کاربر است.</p>
<ul>
<li><strong>فروشگاه:</strong> وب‌سایت فروشگاه آنلاین ارائه دهنده کالا و خدمات الکترونیکی.</li>
<li><strong>مشتری یا کاربر:</strong> هر شخصی که با اطلاعات هویتی خود در سایت ثبت‌نام کرده و از خدمات استفاده می‌نماید.</li>
<li><strong>روز کاری:</strong> به معنی روز شنبه تا پنج‌شنبه هر هفته، به استثنای تعطیلات عمومی در ایران است.</li>
</ul>
<h2>۲. حساب کاربری و امنیت</h2>
<p>کاربران هنگام ثبت‌نام باید شماره تلفن همراه معتبر و متعلق به خود را وارد نمایند. کدهای تایید هویت (OTP) محرمانه بوده و مسئولیت حفظ امنیت و هرگونه فعالیت تحت حساب کاربری به عهده کاربر است.</p>
<p>فروشگاه هویت و سوابق دسترسی را با پروتکل‌های امنیتی روز دنیا و رمزنگاری چندمرحله‌ای محافظت می‌نماید و متعهد است اطلاعات خصوصی کاربران را در اختیار اشخاص ثالث قرار ندهد.</p>
<h2>۳. ثبت و پردازش سفارش</h2>
<p>ثبت سفارش در ۷ روز هفته و ۲۴ ساعت شبانه‌روز امکان‌پذیر است. پس از نهایی شدن پرداخت، سفارش وارد چرخه پردازش، انبارداری و بسته‌بندی خواهد شد. کد رهگیری پستی بلافاصله پس از تحویل به ناوگان حمل از طریق پنل و پیامک به اطلاع خریدار می‌رسد.</p>
<blockquote>در صورت بروز هرگونه مغایرت قیمتی ناشی از اشتباهات سیستمی، حق لغو سفارش و استرداد وجه ظرف کمتر از ۲۴ ساعت برای فروشگاه محفوظ است.</blockquote>
<h2>۴. شیوه و قوانین پرداخت</h2>
<p>پرداخت در فروشگاه از طریق درگاه‌های پرداخت رسمی شبکه شتاب (زرین‌پال، سداد، به‌پرداخت، سامان و غیره)، واریز از کیف‌پول اعتباری و انتقال کارت به کارت با تایید فیش واریز امکان‌پذیر است.</p>
<h2>۵. حمل و نقل و تحویل</h2>
<p>سفارشات شهر تهران با پیک اختصاصی و سایر نقاط کشور از طریق پست با بسته‌بندی ایمن ضدضربه ارسال می‌گردند. خریدار موظف است هنگام دریافت کالا، سلامت فیزیکی بسته را بررسی نماید.</p>
<h2>۶. مالکیت فکری</h2>
<p>تمامی محتویات، طرح گرافیکی، تصاویر محصولات، کدهای فنی و نام تجاری متعلق به این فروشگاه بوده و هرگونه کپی‌برداری تجاری بدون کسب مجوز کتبی پیگرد قانونی دارد.</p>
"""

CONTACT_HTML = """
<p>ما همیشه آماده شنیدن نظرات، پیشنهادها و پاسخ به پرسش‌های شما هستیم. از طریق فرم پیام، تلفن یا ایمیل با ما در ارتباط باشید؛ کارشناسان ما در سریع‌ترین زمان پاسخ می‌دهند.</p>
<h2>ساعات پاسخگویی</h2>
<ul>
<li>شنبه تا پنج‌شنبه: ۹ صبح تا ۶ عصر</li>
<li>پاسخ به پیام‌های فرم تماس: حداکثر یک روز کاری</li>
</ul>
<h2>پیش از تماس</h2>
<p>برای پیگیری سفارش، وضعیت مرجوعی یا سوالات پرتکرار (ارسال، پرداخت، ضمانت) ابتدا صفحه «سوالات متداول» را ببینید؛ شاید پاسخ شما همان‌جا آماده باشد.</p>
"""

#: Core pages with their default copy. The slug keys are the storefront
#: routes' contracts — the frontend pages fetch exactly these slugs.
DEFAULT_PAGES: list[dict[str, str]] = [
    {
        "slug": "about",
        "title": "درباره ما",
        "excerpt": "داستان ما، تیم و ارزش‌هایی که با آن کار می‌کنیم.",
        "body_html": ABOUT_HTML,
    },
    {
        "slug": "terms",
        "title": "شرایط و قوانین استفاده از خدمات",
        "excerpt": "شرایط، ضوابط و قوانین استفاده از خدمات و خریدهای آنلاین در فروشگاه.",
        "body_html": TERMS_HTML,
    },
    {
        "slug": "contact",
        "title": "تماس با ما",
        "excerpt": "راه‌های ارتباط با پشتیبانی فروشگاه و ساعات پاسخگویی.",
        "body_html": CONTACT_HTML,
    },
]

DEFAULT_FAQS: list[dict[str, str]] = [
    {
        "category": "سفارش و ارسال",
        "question": "سفارش من چه زمانی ارسال می‌شود؟",
        "answer": "سفارش‌های ثبت‌شده تا ساعت ۱۴ همان روز پردازش و تحویل پست می‌شوند. پس از تحویل به ناوگان حمل، کد رهگیری از طریق پنل کاربری و پیامک برای شما ارسال می‌شود.",
    },
    {
        "category": "سفارش و ارسال",
        "question": "هزینه ارسال چقدر است؟",
        "answer": "هزینه ارسال به تهران با پیک اختصاصی و به سایر شهرها با پست محاسبه می‌شود و در مرحله پرداخت پیش از نهایی‌کردن سفارش نمایش داده می‌شود.",
    },
    {
        "category": "پرداخت",
        "question": "چه روش‌های پرداختی پشتیبانی می‌شود؟",
        "answer": "پرداخت آنلاین از طریق درگاه‌های رسمی شبکه شتاب، کیف‌پول اعتباری فروشگاه و انتقال کارت به کارت با تایید فیش واریزی امکان‌پذیر است.",
    },
    {
        "category": "پرداخت",
        "question": "اگر مبلغ سفارش از حسابم کم شد اما سفارش ثبت نشد چه کنم؟",
        "answer": "در صورت مغایرت، مبلغ ظرف ۲۴ تا ۷۲ ساعت کاری به‌صورت خودکار توسط بانک به کارت شما بازمی‌گردد. اگر بازنگشت، از طریق فرم تماس با پشتیبانی اطلاع دهید.",
    },
    {
        "category": "ضمانت و مرجوعی",
        "question": "ضمانت اصالت کالا به چه شکل است؟",
        "answer": "تمامی کالاها اصل و دارای گارانتی رسمی هستند. در صورت احراز مغایرت کالا با سفارش، هزینه کامل بازگردانده می‌شود.",
    },
    {
        "category": "ضمانت و مرجوعی",
        "question": "چطور می‌توانم کالای خریداری‌شده را مرجوع کنم؟",
        "answer": "تا ۷ روز پس از دریافت، در صورت سالم بودن بسته و کالا می‌توانید از پنل کاربری درخواست مرجوعی ثبت کنید؛ راهنمای کامل مراحل برای شما پیامک می‌شود.",
    },
]

#: Cache keys the storefront FAQ reads through; cleared after a fresh seed so
#: a new install never serves a stale empty answer.
_FAQ_CACHE_PATTERN = "*content:faqs:*"


async def _clear_faq_cache() -> int:
    try:
        from app.core.config.settings import get_settings

        client_url = str(get_settings().REDIS_URL)
        import redis.asyncio as aioredis

        client = aioredis.from_url(client_url)
        keys = [
            k.decode() if isinstance(k, bytes) else k
            for k in await client.keys(_FAQ_CACHE_PATTERN)
        ]
        if keys:
            await client.delete(*keys)
        await client.aclose()
        return len(keys)
    except Exception:  # noqa: BLE001 — a cache miss is survivable
        return 0


async def seed_default_pages(db) -> dict[str, int]:
    """Create any missing core page / FAQ row. Never updates existing rows.

    Returns counters for the startup log: pages_created, faqs_created,
    cache_cleared.
    """
    pages_created = 0
    for spec in DEFAULT_PAGES:
        page = (await db.scalars(select(CmsPage).filter_by(slug=spec["slug"]))).first()
        if page is not None:
            continue
        db.add(
            CmsPage(
                title=spec["title"],
                slug=spec["slug"],
                body_html=spec["body_html"],
                excerpt=spec["excerpt"],
                status=PageStatus.PUBLISHED,
                published_at=datetime.now(timezone.utc),
            )
        )
        await db.flush()
        pages_created += 1

    faqs_created = 0
    has_faq = (await db.scalars(select(FAQItem).limit(1))).first()
    if has_faq is None:
        for position, entry in enumerate(DEFAULT_FAQS, start=1):
            db.add(
                FAQItem(
                    question=entry["question"],
                    answer_html=f"<p>{entry['answer']}</p>",
                    category=entry["category"],
                    position=position,
                    is_active=True,
                )
            )
        await db.flush()
        faqs_created = len(DEFAULT_FAQS)

    cache_cleared = await _clear_faq_cache() if (pages_created or faqs_created) else 0

    return {
        "pages_created": pages_created,
        "faqs_created": faqs_created,
        "cache_cleared": cache_cleared,
    }
