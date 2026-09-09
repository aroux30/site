"""Unit tests for the automated 0-100 SEO Scoring Engine (Iranian market / Rank Math style)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.seo.application.seo_analyzer import (
    SeoAnalyzer,
    keyword_in_text,
    normalize_text,
    strip_html_and_markdown,
)
from app.modules.seo.schemas.seo import SeoAnalysisRequest, SeoAnalysisResponse

# -----------------------------------------------------------------------------
# Normalization & Helpers Tests
# -----------------------------------------------------------------------------


def test_normalize_persian_text():
    """Verify Arabic Yeh/Kaf, diacritics, ZWNJ, and numerals are normalized."""
    # Arabic Yeh \u064a and Kaf \u0643
    arabic_str = "كتابهاي عربي با تخفيف ۱۰۰٪"
    norm = normalize_text(arabic_str)
    assert "ک" in norm  # Persian Kaf
    assert "ی" in norm  # Persian Yeh
    assert "100" in norm  # ASCII digits

    # ZWNJ removal/spacing
    zwnj_str = "می‌دانیم که گوشی‌موبایل عالی است"
    norm_zwnj = normalize_text(zwnj_str)
    assert "می دانیم" in norm_zwnj or "میدانیم" in norm_zwnj
    assert "گوشی موبایل" in norm_zwnj

    # Diacritics
    diacritic_str = "کِتابِ دَرسِی"
    assert normalize_text(diacritic_str) == "کتاب درسی"


def test_keyword_in_text():
    """Verify keyword matching with Persian variations."""
    assert keyword_in_text("گوشی سامسونگ", "بهترین قیمت خرید گوشی سامسونگ در بازار")
    # Arabic kaf/yeh in target or keyword
    assert keyword_in_text("كتاب", "انواع کتاب موجود است")
    # ZWNJ vs space
    assert keyword_in_text("ضد آب", "این ساعت کاملاً ضدآب است")
    # Empty inputs
    assert not keyword_in_text("", "متن تستی")
    assert not keyword_in_text("تست", "")


def test_strip_html_and_markdown():
    """Verify HTML tags and markdown formatting are stripped cleanly."""
    html_content = (
        "<h2>تیتر اصلی</h2><p>این یک <strong>پاراگراف</strong> تستی است.</p>"
        "<script>alert(1)</script>"
    )
    stripped = strip_html_and_markdown(html_content)
    assert "تیتر اصلی" in stripped
    assert "پاراگراف" in stripped
    assert "alert" not in stripped
    assert "<" not in stripped

    md_content = (
        "## تیتر مارک‌داون\n\nمتن [لینک دار](https://example.com) "
        "و تصویر ![توضیح](img.jpg)"
    )
    stripped_md = strip_html_and_markdown(md_content)
    assert "تیتر مارک‌داون" in stripped_md
    assert "متن لینک دار" in stripped_md


# -----------------------------------------------------------------------------
# SEO Scoring Engine Tests
# -----------------------------------------------------------------------------


def test_perfect_seo_score_100():
    """Verify that fulfilling all 13 criteria yields a perfect 100/100 score with 'عالی'."""
    analyzer = SeoAnalyzer()
    kw = "گوشی سامسونگ"

    # Title: contains kw (+8), near beginning (+4), 40-60 chars (+8) -> 20 pts
    title = "راهنمای جامع خرید گوشی سامسونگ در بازار ایران"
    assert 40 <= len(title) <= 60

    # Meta description: contains kw (+8), 120-160 chars (+7) -> 15 pts
    meta_desc = (
        "راهنمای خرید گوشی سامسونگ با مشخصات کامل و مقایسه قیمت روز انواع مدل‌ها "
        "در فروشگاه اینترنتی با ارسال رایگان و ضمانت اصالت فیزیکی کالا به سراسر کشور."
    )
    assert 120 <= len(meta_desc) <= 160

    # Slug: contains kw (+5), clean & short (+5) -> 10 pts
    slug = "راهنمای-خرید-گوشی-سامسونگ"

    # Content:
    # - kw in intro (+8)
    # - >= 600 words (+12)
    # - density 1.0% to 2.5% (+8)
    # - H2 and H3 (+7) -> 35 pts
    content = (
        f"<p>خرید {kw} یکی از مهم‌ترین انتخاب‌های کاربران دنیای فناوری است.</p>"
        "<h2>بررسی مشخصات فنی</h2>"
        + (" واژه نمونه برای طول متن محتوای سئو"*25 + f" {kw} ")*6
        + "<h3>جمع‌بندی و نتیجه‌گیری</h3><p>پایان بررسی و معرفی مدل‌ها.</p>"
    )

    # Media & Links:
    # - image with alt matching kw (+10)
    # - internal/external links (+10) -> 20 pts
    images = [{"url": "https://example.com/samsung.jpg", "alt": f"تصویر {kw} مدل جدید"}]
    internal_links = ["https://example.com/smartphones"]

    res = analyzer.analyze(
        title=title,
        content=content,
        focus_keyword=kw,
        slug=slug,
        meta_description=meta_desc,
        images=images,
        internal_links=internal_links,
    )

    assert res.score == 100
    assert res.grade == "عالی"
    assert res.grade_color == "green"
    assert res.word_count >= 600
    assert 1.0 <= res.keyword_density <= 2.5
    assert len(res.recommendations) == 0
    assert all(item.passed for item in res.checklist)


def test_empty_content_zero_score():
    """Verify empty inputs yield 0 score, 'ضعیف' grade, and all recommendations."""
    analyzer = SeoAnalyzer()
    res = analyzer.analyze()

    assert res.score == 0
    assert res.grade == "ضعیف"
    assert res.grade_color == "red"
    assert res.word_count == 0
    assert res.keyword_density == 0.0
    assert len(res.recommendations) == 13
    assert not any(item.passed for item in res.checklist)


def test_title_checks_breakdown():
    """Verify Title checks: present (8), near beginning (4), length 40-60 (8)."""
    analyzer = SeoAnalyzer()
    kw = "لپ تاپ ایسوس"

    # Case A: Keyword at start, length within 40-60 (e.g. 45 chars)
    title_a = "لپ تاپ ایسوس گیمینگ مدل راگ برای خرید آنلاین"
    res_a = analyzer.analyze(title=title_a, focus_keyword=kw)
    title_items_a = [item for item in res_a.checklist if item.category == "title"]
    assert len(title_items_a) == 3
    assert all(item.passed for item in title_items_a)
    assert sum(item.points for item in title_items_a) == 20

    # Case B: Keyword at end (not near start), title too short (<40 chars)
    title_b = "فروشگاه آنلاین انواع لپ تاپ ایسوس"
    res_b = analyzer.analyze(title=title_b, focus_keyword=kw)
    title_items_b = {item.title: item for item in res_b.checklist if item.category == "title"}
    assert title_items_b["حضور کلمه کلیدی در عنوان سئو"].passed is True
    assert title_items_b["حضور کلمه کلیدی در عنوان سئو"].points == 8
    # Title length is < 40
    assert title_items_b["طول عنوان سئو"].passed is False
    assert title_items_b["طول عنوان سئو"].points == 0


def test_description_checks():
    """Verify Meta Description checks: keyword present (8) and length 120-160 (7)."""
    analyzer = SeoAnalyzer()
    kw = "دوربین مداربسته"

    # Optimal description
    good_desc = (
        "خرید انواع دوربین مداربسته با دید در شب عالی و کیفیت تصویر فوق‌العاده با گارانتی "
        "دو ساله شرکتی و امکان ارسال به سراسر کشور در فروشگاه تخصصی تجهیزات امنیتی."
    )
    assert 120 <= len(good_desc) <= 160

    res = analyzer.analyze(meta_description=good_desc, focus_keyword=kw)
    desc_items = [item for item in res.checklist if item.category == "description"]
    assert all(item.passed for item in desc_items)
    assert sum(item.points for item in desc_items) == 15

    # Short description without keyword
    short_desc = "خرید تجهیزات امنیتی منزل با تخفیف."
    res_short = analyzer.analyze(meta_description=short_desc, focus_keyword=kw)
    desc_items_short = [item for item in res_short.checklist if item.category == "description"]
    assert not any(item.passed for item in desc_items_short)
    assert sum(item.points for item in desc_items_short) == 0


def test_slug_checks():
    """Verify Slug checks: keyword present (5) and clean/short (5)."""
    analyzer = SeoAnalyzer()
    kw = "ساعت هوشمند"

    # Good slug
    good_slug = "خرید-ساعت-هوشمند-ضدآب"
    res = analyzer.analyze(slug=good_slug, focus_keyword=kw)
    slug_items = [item for item in res.checklist if item.category == "slug"]
    assert all(item.passed for item in slug_items)
    assert sum(item.points for item in slug_items) == 10

    # Dirty slug with spaces or illegal characters
    dirty_slug = "smart watch خرید ساعت هوشمند!@#?="
    res_dirty = analyzer.analyze(slug=dirty_slug, focus_keyword=kw)
    slug_dict = {item.title: item for item in res_dirty.checklist if item.category == "slug"}
    assert slug_dict["کوتاه و استاندارد بودن نامک"].passed is False
    assert slug_dict["کوتاه و استاندارد بودن نامک"].points == 0


def test_content_length_tiers():
    """Verify tier points: >= 600 words (+12), >= 300 words (+6), < 300 words (0)."""
    analyzer = SeoAnalyzer()

    # >= 600 words
    content_600 = "کلمه "*650
    res_600 = analyzer.analyze(content=content_600)
    len_item_600 = next(i for i in res_600.checklist if i.title == "طول و جامعیت محتوا")
    assert len_item_600.passed is True
    assert len_item_600.points == 12

    # 300..599 words
    content_350 = "کلمه "*350
    res_350 = analyzer.analyze(content=content_350)
    len_item_350 = next(i for i in res_350.checklist if i.title == "طول و جامعیت محتوا")
    assert len_item_350.passed is True
    assert len_item_350.points == 6

    # < 300 words
    content_150 = "کلمه "*150
    res_150 = analyzer.analyze(content=content_150)
    len_item_150 = next(i for i in res_150.checklist if i.title == "طول و جامعیت محتوا")
    assert len_item_150.passed is False
    assert len_item_150.points == 0


def test_keyword_density_optimal_vs_stuffing():
    """Verify optimal density 1.0%-2.5% (+8) vs stuffing > 2.5% (-5 pts penalty)."""
    analyzer = SeoAnalyzer()
    kw = "کفش ورزشی"

    # Optimal density: 5 repetitions in 500 words = (5*2)/500 = 2.0%
    optimal_content = (" کلمه تست "*48 + f" {kw} ")*5
    res_opt = analyzer.analyze(content=optimal_content, focus_keyword=kw)
    density_item_opt = next(i for i in res_opt.checklist if "تراکم کلمه کلیدی" in i.title)
    assert density_item_opt.passed is True
    assert density_item_opt.points == 8

    # Keyword stuffing: 30 repetitions in 300 words -> density ~ 20%
    stuffed_content = (" تست "*3 + f" {kw} ")*30
    res_stuffed = analyzer.analyze(content=stuffed_content, focus_keyword=kw)
    density_item_stuffed = next(i for i in res_stuffed.checklist if "تراکم کلمه کلیدی" in i.title)
    assert density_item_stuffed.passed is False
    assert density_item_stuffed.points == -5


def test_headings_presence_markdown_and_html():
    """Verify detection of H2 and H3 in HTML and markdown."""
    analyzer = SeoAnalyzer()

    # HTML headings
    html_content = "<h2>عنوان اصلی</h2><p>توضیح</p><h3>زیر عنوان</h3>"
    res_html = analyzer.analyze(content=html_content)
    h_item = next(i for i in res_html.checklist if "H2 و H3" in i.title)
    assert h_item.passed is True
    assert h_item.points == 7

    # Markdown headings
    md_content = "## عنوان اصلی\n\nمتن نمونه\n\n### زیر عنوان"
    res_md = analyzer.analyze(content=md_content)
    h_item_md = next(i for i in res_md.checklist if "H2 و H3" in i.title)
    assert h_item_md.passed is True
    assert h_item_md.points == 7

    # Missing H3
    missing_h3 = "<h2>فقط عنوان دو</h2><p>متن</p>"
    res_missing = analyzer.analyze(content=missing_h3)
    h_item_missing = next(i for i in res_missing.checklist if "H2 و H3" in i.title)
    assert h_item_missing.passed is False
    assert h_item_missing.points == 0


def test_media_and_links_checks():
    """Verify image alt keyword check (+10) and internal/external links check (+10)."""
    analyzer = SeoAnalyzer()
    kw = "تبلت اپل"

    # Via parameters
    res_params = analyzer.analyze(
        focus_keyword=kw,
        has_image_alt=True,
        internal_links_count=3,
    )
    media_items = [i for i in res_params.checklist if i.category == "media_links"]
    assert all(i.passed for i in media_items)
    assert sum(i.points for i in media_items) == 20

    # Via HTML content detection
    html_content = (
        '<img src="apple.jpg" alt="خرید تبلت اپل مدل پرو">'
        '<a href="/products">فروشگاه</a>'
    )
    res_html = analyzer.analyze(content=html_content, focus_keyword=kw)
    media_items_html = [i for i in res_html.checklist if i.category == "media_links"]
    assert all(i.passed for i in media_items_html)
    assert sum(i.points for i in media_items_html) == 20


def test_grade_boundaries():
    """Verify grade mapping: 80-100 (عالی), 50-79 (متوسط و نیازمند بهبود), 0-49 (ضعیف)."""
    analyzer = SeoAnalyzer()

    grade_80, color_80 = analyzer._determine_grade(80)
    assert grade_80 == "عالی"
    assert color_80 == "green"

    grade_79, color_79 = analyzer._determine_grade(79)
    assert grade_79 == "متوسط و نیازمند بهبود"
    assert color_79 == "yellow"

    grade_50, color_50 = analyzer._determine_grade(50)
    assert grade_50 == "متوسط و نیازمند بهبود"
    assert color_50 == "yellow"

    grade_49, color_49 = analyzer._determine_grade(49)
    assert grade_49 == "ضعیف"
    assert color_49 == "red"


def test_url_encoded_persian_slug():
    """Verify URL-encoded Persian slug is decoded and checked properly."""
    import urllib.parse
    analyzer = SeoAnalyzer()
    kw = "کفش چرم"
    persian_slug = "خرید-کفش-چرم-طبیعی"
    encoded_slug = urllib.parse.quote(persian_slug)

    res = analyzer.analyze(slug=encoded_slug, focus_keyword=kw)
    slug_items = {item.title: item for item in res.checklist if item.category == "slug"}
    assert slug_items["کلمه کلیدی در نامک (Slug)"].passed is True
    assert slug_items["کلمه کلیدی در نامک (Slug)"].points == 5
    assert slug_items["کوتاه و استاندارد بودن نامک"].passed is True
    assert slug_items["کوتاه و استاندارد بودن نامک"].points == 5


def test_pydantic_schema_validation():
    """Verify Pydantic v2 schema serialization and deserialization."""
    req = SeoAnalysisRequest(
        title="عنوان تستی صفحه",
        content="<p>متن تستی</p>",
        focus_keyword="کلمه کلیدی",
        slug="test-slug",
        meta_description="توضیحات متا برای تست سیستم سئو",
        images_count=2,
        has_image_alt=True,
        internal_links_count=1,
    )
    dumped = req.model_dump()
    assert dumped["images_count"] == 2
    assert dumped["has_image_alt"] is True

    analyzer = SeoAnalyzer()
    res = analyzer.analyze(**dumped)
    assert isinstance(res, SeoAnalysisResponse)
    json_data = res.model_dump_json()
    assert "score" in json_data
    assert "grade" in json_data



# -----------------------------------------------------------------------------
# API Route Tests
# -----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_seo_analyze_endpoint():
    """Verify POST /api/v1/seo/analyze and /seo/analyze with FastAPI TestClient."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "title": "راهنمای جامع خرید هدفون بلوتوثی اصل",
            "content": (
                "<h2>بررسی</h2><h3>مدل‌ها</h3><p>خرید هدفون بلوتوثی بسیار جذاب است.</p>"
                + " متن تستی " * 100
            ),
            "focus_keyword": "هدفون بلوتوثی",
            "slug": "خرید-هدفون-بلوتوثی",
            "meta_description": (
                "بهترین قیمت خرید هدفون بلوتوثی با کیفیت صدای عالی و ارسال سریع به سراسر "
                "ایران در فروشگاه آنلاین لوازم جانبی دیجیتال."
            ),
            "has_image_alt": True,
            "internal_links_count": 2,
        }

        # Test both /api/v1/seo/analyze and /seo/analyze
        for url in ["/api/v1/seo/analyze", "/seo/analyze"]:
            response = await client.post(url, json=payload)
            assert response.status_code == 200
            data = response.json()
            assert "score" in data
            assert "grade" in data
            assert "checklist" in data
            assert "recommendations" in data
            assert isinstance(data["score"], int)
            assert 0 <= data["score"] <= 100
            assert len(data["checklist"]) == 13


@pytest.mark.asyncio
async def test_api_seo_product_score_not_found():
    """Verify GET /api/v1/seo/products/{id}/score returns 404 when product is missing."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    fake_id = str(uuid.uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Mock DB get_db dependency to return a session where product lookup is None
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.core.database.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.get(f"/api/v1/seo/products/{fake_id}/score")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_seo_blog_score_not_found():
    """Verify GET /api/v1/seo/blog/{slug}/score returns 404 when article is missing."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        from app.core.database.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.get("/api/v1/seo/blog/non-existent-article/score")
            assert response.status_code == 404
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_seo_product_score_success():
    """Verify GET /api/v1/seo/products/{id}/score calculates and returns score for mock product."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.modules.catalog.domain.models import Product, ProductImage, ProductTag, Tag

    test_id = uuid.uuid4()
    mock_product = MagicMock(spec=Product)
    mock_product.id = test_id
    mock_product.name = "گوشی سامسونگ مدل A54"
    mock_product.slug = "samsung-galaxy-a54"
    mock_product.seo_title = "خرید گوشی سامسونگ مدل A54 با قیمت عالی روز"
    mock_product.seo_description = (
        "خرید گوشی سامسونگ با گارانتی معتبر شرکتی و قیمت روز مناسب در فروشگاه اینترنتی "
        "به همراه تحویل فوری در محل خریدار."
    )
    mock_product.description = (
        "<h2>بررسی فنی</h2><p>خرید گوشی سامسونگ پیشنهاد مناسبی است.</p>"
        + " متن توضیحات محصول " * 150
    )
    mock_product.short_description = "گوشی سامسونگ اصل"
    mock_product.meta_keywords = "گوشی سامسونگ, سامسونگ"

    mock_tag = MagicMock(spec=Tag)
    mock_tag.name = "گوشی سامسونگ"
    mock_pt = MagicMock(spec=ProductTag)
    mock_pt.tag = mock_tag
    mock_product.product_tags = [mock_pt]

    mock_img = MagicMock(spec=ProductImage)
    mock_img.url = "https://example.com/a54.jpg"
    mock_img.alt_text = "گوشی سامسونگ گلکسی"
    mock_product.images = [mock_img]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.unique.return_value.scalar_one_or_none.return_value = mock_product
        mock_db.execute.return_value = mock_result

        from app.core.database.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.get(f"/api/v1/seo/products/{test_id}/score")
            assert response.status_code == 200
            data = response.json()
            assert "score" in data
            assert data["score"] > 0
            assert "grade" in data
            assert "checklist" in data
            assert len(data["checklist"]) == 13
        finally:
            app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_api_seo_blog_score_success():
    """Verify GET /api/v1/seo/blog/{slug}/score calculates and returns score for mock blog post."""
    from httpx import ASGITransport, AsyncClient

    from app.main import app
    from app.modules.blog.domain.models import BlogCategory, BlogPost

    mock_category = MagicMock(spec=BlogCategory)
    mock_category.name = "راهنمای خرید"

    mock_post = MagicMock(spec=BlogPost)
    mock_post.id = uuid.uuid4()
    mock_post.title = "راهنمای خرید لپ تاپ مهندسی در سال جدید"
    mock_post.slug = "guide-buying-laptop"
    mock_post.excerpt = (
        "راهنمای خرید لپ تاپ مهندسی با بررسی کامل پردازنده، حافظه رم و کارت گرافیک "
        "در فروشگاه آنلاین."
    )
    mock_post.content = (
        "<h2>مقدمه</h2><p>راهنمای خرید لپ تاپ یکی از مقالات مهم است.</p>"
        + " متن راهنما " * 120
    )
    mock_post.cover_image_url = "https://example.com/laptop.jpg"
    mock_post.category = mock_category

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        mock_db = AsyncMock()
        # First query: BlogPost
        # Second query: SEOMetadata
        mock_db_result_post = MagicMock()
        mock_db_result_post.scalar_one_or_none.return_value = mock_post

        mock_db_result_seo = MagicMock()
        mock_db_result_seo.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_db_result_post, mock_db_result_seo]

        from app.core.database.session import get_db
        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            response = await client.get("/api/v1/seo/blog/guide-buying-laptop/score")
            assert response.status_code == 200
            data = response.json()
            assert "score" in data
            assert data["score"] > 0
            assert "grade" in data
            assert "checklist" in data
            assert len(data["checklist"]) == 13
        finally:
            app.dependency_overrides.pop(get_db, None)
