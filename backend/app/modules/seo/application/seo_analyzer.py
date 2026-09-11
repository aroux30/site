"""Automated 0-100 SEO Scoring Engine for Iranian & E-commerce Market.

Similar to Rank Math / Yoast SEO, fine-tuned for Persian text and search practices.
Evaluates Title, Meta Description, URL/Slug, Content, and Media & Links.
"""

from __future__ import annotations

import html
import re
import urllib.parse
from typing import Any

from app.modules.seo.schemas.seo import (
    SeoAnalysisResponse,
    SeoCheckItem,
)

# -----------------------------------------------------------------------------
# Persian & General Text Normalization Utilities
# -----------------------------------------------------------------------------

_ARABIC_TO_PERSIAN_TRANS = str.maketrans(
    {
        "\u064a": "\u06cc",  # Arabic Yeh -> Persian Yeh
        "\u0649": "\u06cc",  # Alef Maksura -> Persian Yeh
        "\u0643": "\u06a9",  # Arabic Kaf -> Persian Kaf
        "\u0629": "\u0647",  # Teh Marbuta -> Heh
        "\u06c0": "\u0647",  # Heh with Yeh above -> Heh
    }
)

_DIGITS_TRANS = str.maketrans(
    {
        "\u06f0": "0",
        "\u06f1": "1",
        "\u06f2": "2",
        "\u06f3": "3",
        "\u06f4": "4",
        "\u06f5": "5",
        "\u06f6": "6",
        "\u06f7": "7",
        "\u06f8": "8",
        "\u06f9": "9",
        "\u0660": "0",
        "\u0661": "1",
        "\u0662": "2",
        "\u0663": "3",
        "\u0664": "4",
        "\u0665": "5",
        "\u0666": "6",
        "\u0667": "7",
        "\u0668": "8",
        "\u0669": "9",
    }
)

# Arabic / Persian diacritics (Harakat, Tanween, Tashdeed)
_DIACRITICS_RE = re.compile(r"[\u064b-\u0652\u0670\u0656\u0657\u0658]")
# ZWNJ (Zero-width non-joiner), zero-width space, NBSP
_ZWNJ_RE = re.compile(r"[\u200c\u200b\u200e\u200f\u00a0]")
# Multiple whitespaces
_MULTI_SPACE_RE = re.compile(r"\s+")
# Word tokenization (matches English/Latin words, numbers, and Persian/Arabic letters)
_WORD_TOKEN_RE = re.compile(r"[\w\u0600-\u06ff]+", re.UNICODE)


def normalize_text(text: str) -> str:
    """Normalize Persian and English text for robust comparison."""
    if not text:
        return ""
    # Translate Arabic Yeh/Kaf to Persian
    text = text.translate(_ARABIC_TO_PERSIAN_TRANS)
    # Translate digits to standard ASCII
    text = text.translate(_DIGITS_TRANS)
    # Remove diacritics
    text = _DIACRITICS_RE.sub("", text)
    # Replace ZWNJ and non-breaking spaces with standard space
    text = _ZWNJ_RE.sub(" ", text)
    # Convert HTML entities
    text = html.unescape(text)
    # Lowercase Latin characters
    text = text.lower()
    # Normalize spaces
    return _MULTI_SPACE_RE.sub(" ", text).strip()


def keyword_in_text(keyword: str, text: str) -> bool:
    """Check whether a focus keyword appears in text with normalization."""
    if not keyword or not text:
        return False
    norm_kw = normalize_text(keyword)
    norm_text = normalize_text(text)
    if not norm_kw or not norm_text:
        return False

    # Exact normalized substring match
    if norm_kw in norm_text:
        return True

    # Check compact match (ignoring spaces for compound Persian words, e.g. ضدآب vs ضد آب)
    compact_kw = norm_kw.replace(" ", "")
    compact_text = norm_text.replace(" ", "")
    return bool(len(compact_kw) >= 3 and compact_kw in compact_text)


def strip_html_and_markdown(content: str) -> str:
    """Strip HTML tags, markdown syntax, and scripts to extract plain readable text."""
    if not content:
        return ""

    # Remove script and style elements
    text = re.sub(r"(?is)<script.*?</script>", " ", content)
    text = re.sub(r"(?is)<style.*?</style>", " ", text)
    # Convert structural HTML tags to newlines or spaces
    text = re.sub(r"(?i)</?(?:p|div|h[1-6]|li|tr|blockquote|br)[^>]*>", "\n", text)
    # Remove all remaining HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Remove markdown image and link syntax: ![alt](url) -> alt, [text](url) -> text
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove markdown headers #, ##, ###
    text = re.sub(r"(?m)^#{1,6}\s*", " ", text)
    # Remove markdown bold/italic * or _
    text = re.sub(r"[*_~`]", " ", text)
    # Unescape HTML entities
    text = html.unescape(text)
    # Normalize spaces
    return _MULTI_SPACE_RE.sub(" ", text).strip()


def extract_introductory_paragraph(content: str) -> str:
    """Extract the introductory paragraph from HTML or markdown content."""
    if not content:
        return ""

    # Look for first non-empty <p> tag
    p_matches = re.findall(r"(?is)<p[^>]*>(.*?)</p>", content)
    for p in p_matches:
        cleaned = strip_html_and_markdown(p).strip()
        if len(cleaned) > 20:
            return cleaned

    # Fallback: split raw content by double newlines or paragraph breaks
    blocks = re.split(r"\n\s*\n", content)
    for block in blocks:
        cleaned = strip_html_and_markdown(block).strip()
        if len(cleaned) > 20:
            return cleaned

    # Fallback: first 150 words
    plain = strip_html_and_markdown(content)
    words = plain.split()
    return " ".join(words[:150])


# -----------------------------------------------------------------------------
# SEO Analyzer Engine
# -----------------------------------------------------------------------------


class SeoAnalyzer:
    """Automated 0-100 SEO Scoring Engine for Iranian & E-commerce Market.

    Check Categories:
    1. Title Checks (20 pts)
       - Focus keyword in SEO title (+8 pts)
       - Keyword near beginning of title (+4 pts)
       - Title length between 40 and 60 chars (+8 pts)
    2. Description Checks (15 pts)
       - Focus keyword in meta description (+8 pts)
       - Meta description length between 120 and 160 chars (+7 pts)
    3. URL / Slug Checks (10 pts)
       - Focus keyword in slug (+5 pts)
       - Clean and short slug (+5 pts)
    4. Content Checks (35 pts)
       - Focus keyword in introductory paragraph (+8 pts)
       - Content length: >= 600 words (+12 pts), >= 300 words (+6 pts), < 300 words (0 pts)
       - Keyword density: 1.0% to 2.5% (+8 pts), > 2.5% (-5 pts), < 1.0% (0 pts)
       - Headings presence: contains both H2 and H3 (+7 pts)
    5. Media & Links Checks (20 pts)
       - Image with alt attribute matching keyword (+10 pts)
       - Contains internal or outbound links (+10 pts)

    Total Maximum Score: 100 points.
    Grade:
       - 80-100: عالی (Green)
       - 50-79: متوسط و نیازمند بهبود (Yellow)
       - 0-49: ضعیف (Red)
    """

    def analyze(
        self,
        title: str = "",
        content: str = "",
        focus_keyword: str = "",
        slug: str = "",
        meta_description: str = "",
        images: list[Any] | None = None,
        internal_links: list[str] | None = None,
        *,
        images_count: int | None = None,
        has_image_alt: bool | None = None,
        internal_links_count: int | None = None,
    ) -> SeoAnalysisResponse:
        """Run full SEO analysis against all ranking factors and return structured report."""
        title = (title or "").strip()
        content = (content or "").strip()
        focus_keyword = (focus_keyword or "").strip()
        slug = (slug or "").strip()
        meta_description = (meta_description or "").strip()
        images = images or []
        internal_links = internal_links or []

        checklist: list[SeoCheckItem] = []

        # 1. Title Checks (20 pts)
        title_checks = self._check_title(title=title, focus_keyword=focus_keyword)
        checklist.extend(title_checks)

        # 2. Description Checks (15 pts)
        desc_checks = self._check_description(
            meta_description=meta_description, focus_keyword=focus_keyword
        )
        checklist.extend(desc_checks)

        # 3. URL / Slug Checks (10 pts)
        slug_checks = self._check_slug(slug=slug, focus_keyword=focus_keyword)
        checklist.extend(slug_checks)

        # 4. Content Checks (35 pts)
        content_checks, word_count, keyword_density = self._check_content(
            content=content, focus_keyword=focus_keyword
        )
        checklist.extend(content_checks)

        # 5. Media & Links Checks (20 pts)
        media_checks = self._check_media_and_links(
            content=content,
            focus_keyword=focus_keyword,
            images=images,
            internal_links=internal_links,
            images_count=images_count,
            has_image_alt=has_image_alt,
            internal_links_count=internal_links_count,
        )
        checklist.extend(media_checks)

        # Calculate Overall Score (0 to 100)
        raw_score = sum(item.points for item in checklist)
        overall_score = max(0, min(100, raw_score))

        # Determine Grade and Color
        grade, grade_color = self._determine_grade(overall_score)

        # Generate Actionable Recommendations
        recommendations = self._generate_recommendations(checklist)

        return SeoAnalysisResponse(
            score=overall_score,
            grade=grade,
            grade_color=grade_color,
            word_count=word_count,
            keyword_density=keyword_density,
            checklist=checklist,
            recommendations=recommendations,
        )

    # -------------------------------------------------------------------------
    # 1. Title Checks (20 pts)
    # -------------------------------------------------------------------------

    def _check_title(self, title: str, focus_keyword: str) -> list[SeoCheckItem]:
        items: list[SeoCheckItem] = []
        norm_title = normalize_text(title)
        norm_kw = normalize_text(focus_keyword)

        # Check 1.1: Does focus keyword appear in SEO title? (+8 pts)
        kw_in_title = bool(norm_kw and norm_title and (norm_kw in norm_title))
        if kw_in_title:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="حضور کلمه کلیدی در عنوان سئو",
                    message="کلمه کلیدی هدف در عنوان سئو صفحه قرار دارد.",
                    points=8,
                    max_points=8,
                    category="title",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="حضور کلمه کلیدی در عنوان سئو",
                    message=(
                        "کلمه کلیدی در عنوان سئو یافت نشد. "
                        "توصیه می‌شود کلمه کلیدی هدف را به عنوان صفحه اضافه کنید."
                    ),
                    points=0,
                    max_points=8,
                    category="title",
                )
            )

        # Check 1.2: Does keyword appear near the beginning of title? (+4 pts)
        near_beginning = False
        if kw_in_title:
            pos = norm_title.find(norm_kw)
            title_words = norm_title.split()
            kw_words = norm_kw.split()
            word_idx = 0
            if title_words and kw_words:
                try:
                    word_idx = title_words.index(kw_words[0])
                except ValueError:
                    word_idx = 999

            if pos == 0 or pos <= max(20, int(len(norm_title) * 0.45)) or word_idx <= 2:
                near_beginning = True

        if near_beginning:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="موقعیت کلمه کلیدی در عنوان سئو",
                    message="کلمه کلیدی در ابتدای عنوان سئو یا نزدیک به آن قرار گرفته است.",
                    points=4,
                    max_points=4,
                    category="title",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="موقعیت کلمه کلیدی در عنوان سئو",
                    message=(
                        "کلمه کلیدی در ابتدای عنوان سئو قرار ندارد. برای جلب نظر سریع کاربر "
                        "و موتور جستجو، کلمه کلیدی را در ابتدای عنوان قرار دهید."
                    ),
                    points=0,
                    max_points=4,
                    category="title",
                )
            )

        # Check 1.3: Title length between 40 and 60 chars? (+8 pts)
        title_len = len(title)
        if 40 <= title_len <= 60:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="طول عنوان سئو",
                    message=(
                        f"طول عنوان سئو استاندارد و بهینه است "
                        f"({title_len} کاراکتر، محدوده مناسب ۴۰ تا ۶۰ کاراکتر)."
                    ),
                    points=8,
                    max_points=8,
                    category="title",
                )
            )
        else:
            if title_len < 40:
                msg = (
                    f"طول عنوان سئو کوتاه است ({title_len} کاراکتر). "
                    "حداقل ۴۰ کاراکتر و تا ۶۰ کاراکتر برای نمایش مناسب در گوگل بنویسید."
                )
            else:
                msg = (
                    f"طول عنوان سئو بیش از حد طولانی است ({title_len} کاراکتر). "
                    "در نتایج جستجو ممکن است بریده شود (حداکثر ۶۰ کاراکتر)."
                )
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="طول عنوان سئو",
                    message=msg,
                    points=0,
                    max_points=8,
                    category="title",
                )
            )

        return items

    # -------------------------------------------------------------------------
    # 2. Description Checks (15 pts)
    # -------------------------------------------------------------------------

    def _check_description(self, meta_description: str, focus_keyword: str) -> list[SeoCheckItem]:
        items: list[SeoCheckItem] = []
        norm_desc = normalize_text(meta_description)
        norm_kw = normalize_text(focus_keyword)

        # Check 2.1: Does focus keyword appear in meta description? (+8 pts)
        kw_in_desc = bool(norm_kw and norm_desc and (norm_kw in norm_desc))
        if kw_in_desc:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="حضور کلمه کلیدی در توضیحات متا",
                    message=(
                        "کلمه کلیدی در توضیحات متا قرار دارد و نرخ کلیک (CTR) را افزایش می‌دهد."
                    ),
                    points=8,
                    max_points=8,
                    category="description",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="حضور کلمه کلیدی در توضیحات متا",
                    message=(
                        "کلمه کلیدی در توضیحات متا یافت نشد. قرار دادن کلمه کلیدی در توضیحات "
                        "متا برای جذب کلیک کاربران ضروری است."
                    ),
                    points=0,
                    max_points=8,
                    category="description",
                )
            )

        # Check 2.2: Meta description length between 120 and 160 chars? (+7 pts)
        desc_len = len(meta_description)
        if 120 <= desc_len <= 160:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="طول توضیحات متا",
                    message=(
                        f"طول توضیحات متا استاندارد است "
                        f"({desc_len} کاراکتر، محدوده مناسب ۱۲۰ تا ۱۶۰ کاراکتر)."
                    ),
                    points=7,
                    max_points=7,
                    category="description",
                )
            )
        else:
            if desc_len < 120:
                msg = (
                    f"توضیحات متا کوتاه است ({desc_len} کاراکتر). "
                    "طول استاندارد بین ۱۲۰ تا ۱۶۰ کاراکتر است."
                )
            else:
                msg = (
                    f"توضیحات متا بیش از حد طولانی است ({desc_len} کاراکتر). "
                    "حداکثر ۱۶۰ کاراکتر بنویسید تا در نتایج موتورهای جستجو بریده نشود."
                )
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="طول توضیحات متا",
                    message=msg,
                    points=0,
                    max_points=7,
                    category="description",
                )
            )

        return items

    # -------------------------------------------------------------------------
    # 3. URL / Slug Checks (10 pts)
    # -------------------------------------------------------------------------

    def _check_slug(self, slug: str, focus_keyword: str) -> list[SeoCheckItem]:
        items: list[SeoCheckItem] = []
        unquoted_slug = urllib.parse.unquote(slug).strip()
        # Normalization of slug: replace hyphens and underscores with spaces
        slug_words_text = unquoted_slug.replace("-", " ").replace("_", " ")
        norm_slug = normalize_text(slug_words_text)
        norm_kw = normalize_text(focus_keyword)

        # Check 3.1: Does focus keyword appear in slug? (+5 pts)
        kw_in_slug = False
        if norm_kw and norm_slug:
            if norm_kw in norm_slug or norm_kw.replace(" ", "-") in unquoted_slug.lower():
                kw_in_slug = True
            else:
                kw_parts = norm_kw.split()
                if kw_parts and all(part in norm_slug for part in kw_parts):
                    kw_in_slug = True

        if kw_in_slug:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="کلمه کلیدی در نامک (Slug)",
                    message="کلمه کلیدی هدف در آدرس URL / نامک گنجانده شده است.",
                    points=5,
                    max_points=5,
                    category="slug",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="کلمه کلیدی در نامک (Slug)",
                    message=(
                        "کلمه کلیدی در نامک (Slug) وجود ندارد. "
                        "توصیه می‌شود کلمه کلیدی را در آدرس صفحه بگنجانید."
                    ),
                    points=0,
                    max_points=5,
                    category="slug",
                )
            )

        # Check 3.2: Is slug clean and short? (+5 pts)
        clean_and_short = False
        slug_len = len(unquoted_slug)
        disallowed_chars = set(" !@#$%^&*()+=[]{}|\\;:'\",<>?/~`")
        has_disallowed = any(ch in disallowed_chars for ch in unquoted_slug)
        has_consecutive_hyphens = "--" in unquoted_slug

        if 3 <= slug_len <= 75 and not has_disallowed and not has_consecutive_hyphens:
            clean_and_short = True

        if clean_and_short:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="کوتاه و استاندارد بودن نامک",
                    message=(
                        f"نامک آدرس تمیز، کوتاه و استاندارد است "
                        f"({slug_len} کاراکتر، حداکثر ۷۵ کاراکتر)."
                    ),
                    points=5,
                    max_points=5,
                    category="slug",
                )
            )
        else:
            if slug_len > 75:
                msg = (
                    f"نامک صفحه طولانی است ({slug_len} کاراکتر). "
                    "برای سئو بهتر، نامک را به کمتر از ۷۵ کاراکتر کاهش دهید."
                )
            elif slug_len < 3:
                msg = "نامک بسیار کوتاه یا خالی است. یک نامک معنادار با کلمات کلیدی انتخاب کنید."
            else:
                msg = (
                    "نامک حاوی کاراکترهای نامعتبر، فاصله یا خط تیره‌های پیاپی است. "
                    "فقط از حروف، اعداد و خط تیره (-) استفاده کنید."
                )
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="کوتاه و استاندارد بودن نامک",
                    message=msg,
                    points=0,
                    max_points=5,
                    category="slug",
                )
            )

        return items

    # -------------------------------------------------------------------------
    # 4. Content Checks (35 pts)
    # -------------------------------------------------------------------------

    def _check_content(
        self, content: str, focus_keyword: str
    ) -> tuple[list[SeoCheckItem], int, float]:
        items: list[SeoCheckItem] = []
        plain_text = strip_html_and_markdown(content)
        norm_plain_text = normalize_text(plain_text)
        norm_kw = normalize_text(focus_keyword)

        # Word tokenization
        words = _WORD_TOKEN_RE.findall(norm_plain_text)
        word_count = len(words)

        # Check 4.1: Focus keyword in introductory paragraph? (+8 pts)
        intro_text = extract_introductory_paragraph(content)
        norm_intro = normalize_text(intro_text)
        kw_in_intro = bool(norm_kw and norm_intro and (norm_kw in norm_intro))

        if kw_in_intro:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="کلمه کلیدی در پاراگراف اول",
                    message="کلمه کلیدی هدف در پاراگراف ابتدایی محتوا ذکر شده است.",
                    points=8,
                    max_points=8,
                    category="content",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="کلمه کلیدی در پاراگراف اول",
                    message=(
                        "کلمه کلیدی در پاراگراف اول محتوا یافت نشد. "
                        "معرفی زودهنگام موضوع به مخاطب و موتور جستجو امتیاز مهمی دارد."
                    ),
                    points=0,
                    max_points=8,
                    category="content",
                )
            )

        # Check 4.2: Content length: >= 600 words (+12), >= 300 words (+6), < 300 words (0)
        if word_count >= 600:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="طول و جامعیت محتوا",
                    message=f"طول محتوا عالی است ({word_count} کلمه، بیش از ۶۰۰ کلمه استاندارد).",
                    points=12,
                    max_points=12,
                    category="content",
                )
            )
        elif word_count >= 300:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="طول و جامعیت محتوا",
                    message=(
                        f"طول محتوا قابل قبول است ({word_count} کلمه)، "
                        "اما برای رقابت در صفحات نخست گوگل حداقل ۶۰۰ کلمه بنویسید."
                    ),
                    points=6,
                    max_points=12,
                    category="content",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="طول و جامعیت محتوا",
                    message=(
                        f"محتوا بسیار کوتاه است ({word_count} کلمه). "
                        "حداقل ۳۰۰ کلمه و ترجیحاً بیش از ۶۰۰ کلمه تولید کنید."
                    ),
                    points=0,
                    max_points=12,
                    category="content",
                )
            )

        # Check 4.3: Keyword density: optimal 1.0% to 2.5% (+8), too high/stuffed (-5)
        kw_density = 0.0
        kw_count = 0
        if norm_kw and word_count > 0:
            pattern = re.escape(norm_kw)
            matches = re.findall(pattern, norm_plain_text)
            kw_count = len(matches)
            kw_words_len = max(1, len(norm_kw.split()))
            kw_density = round((kw_count * kw_words_len / word_count) * 100, 2)

        if 1.0 <= kw_density <= 2.5:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="تراکم کلمه کلیدی",
                    message=(
                        f"تراکم کلمه کلیدی بهینه است "
                        f"({kw_density:.1f}%، {kw_count} بار تکرار، محدوده ایده‌آل ۱ تا ۲.۵ درصد)."
                    ),
                    points=8,
                    max_points=8,
                    category="content",
                )
            )
        elif kw_density > 2.5:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="تراکم کلمه کلیدی",
                    message=(
                        f"تراکم کلمه کلیدی بیش از حد مجاز است ({kw_density:.1f}%، "
                        f"{kw_count} بار تکرار). خطر جریمه پر کردن کلمه کلیدی وجود دارد."
                    ),
                    points=-5,
                    max_points=8,
                    category="content",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="تراکم کلمه کلیدی",
                    message=(
                        f"تراکم کلمه کلیدی کم است ({kw_density:.1f}%، {kw_count} بار تکرار). "
                        "کلمه کلیدی را به شکل طبیعی به محدوده ۱ تا ۲.۵ درصد برسانید."
                    ),
                    points=0,
                    max_points=8,
                    category="content",
                )
            )

        # Check 4.4: Headings presence: contains H2 and H3 tags? (+7 pts)
        has_h2 = bool(re.search(r"(?i)<h2[\s>]", content) or re.search(r"(?m)^##\s+", content))
        has_h3 = bool(re.search(r"(?i)<h3[\s>]", content) or re.search(r"(?m)^###\s+", content))

        if has_h2 and has_h3:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="ساختار تیترها (H2 و H3)",
                    message=(
                        "محتوا به درستی با استفاده از تیترهای H2 و H3 "
                        "بخش‌بندی و ساختاربندی شده است."
                    ),
                    points=7,
                    max_points=7,
                    category="content",
                )
            )
        else:
            if not has_h2 and not has_h3:
                msg = (
                    "هیچ عنوان H2 یا H3 در محتوا یافت نشد. "
                    "از تیترهای H2 و H3 برای تقسیم‌بندی مطالب استفاده کنید."
                )
            elif not has_h2:
                msg = "عنوان H3 یافت شد اما تگ اصلی H2 وجود ندارد. عناوین اصلی را با H2 مشخص کنید."
            else:
                msg = (
                    "عنوان H2 یافت شد اما عنوان H3 وجود ندارد. "
                    "برای زیربخش‌ها از تگ H3 استفاده کنید."
                )
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="ساختار تیترها (H2 و H3)",
                    message=msg,
                    points=0,
                    max_points=7,
                    category="content",
                )
            )

        return items, word_count, kw_density

    # -------------------------------------------------------------------------
    # 5. Media & Links Checks (20 pts)
    # -------------------------------------------------------------------------

    def _check_media_and_links(
        self,
        content: str,
        focus_keyword: str,
        images: list[Any],
        internal_links: list[str],
        images_count: int | None = None,
        has_image_alt: bool | None = None,
        internal_links_count: int | None = None,
    ) -> list[SeoCheckItem]:
        items: list[SeoCheckItem] = []
        norm_kw = normalize_text(focus_keyword)

        # Check 5.1: Contains image with alt attribute matching keyword? (+10 pts)
        matched_image_alt = False

        if has_image_alt is True:
            matched_image_alt = True
        elif norm_kw:
            for img in images:
                alt_val = ""
                if isinstance(img, dict):
                    alt_val = str(img.get("alt") or img.get("alt_text") or "")
                elif hasattr(img, "alt_text"):
                    alt_val = str(getattr(img, "alt_text", "") or "")
                elif hasattr(img, "alt"):
                    alt_val = str(getattr(img, "alt", "") or "")

                if alt_val and keyword_in_text(norm_kw, alt_val):
                    matched_image_alt = True
                    break

            if not matched_image_alt and content:
                img_alt_tags = re.findall(
                    r"""(?is)<img\s+[^>]*alt\s*=\s*["']([^"']+)["'][^>]*>""",
                    content,
                )
                for alt_val in img_alt_tags:
                    if alt_val and keyword_in_text(norm_kw, alt_val):
                        matched_image_alt = True
                        break

            if not matched_image_alt and content:
                md_alts = re.findall(r"""!\[([^\]]+)\]\([^)]+\)""", content)
                for alt_val in md_alts:
                    if alt_val and keyword_in_text(norm_kw, alt_val):
                        matched_image_alt = True
                        break

        if matched_image_alt:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="تصویر با ویژگی Alt منطبق با کلمه کلیدی",
                    message=(
                        "تصویر با ویژگی متن جایگزین (Alt) منطبق با کلمه کلیدی در صفحه موجود است."
                    ),
                    points=10,
                    max_points=10,
                    category="media_links",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="تصویر با ویژگی Alt منطبق با کلمه کلیدی",
                    message=(
                        "هیچ تصویری با ویژگی Alt حاوی کلمه کلیدی یافت نشد. "
                        "متن جایگزین تصاویر به رتبه سئو و جستجوی تصاویر کمک می‌کند."
                    ),
                    points=0,
                    max_points=10,
                    category="media_links",
                )
            )

        # Check 5.2: Contains internal / outbound links? (+10 pts)
        has_links = bool(
            (internal_links_count is not None and internal_links_count > 0)
            or (internal_links and len(internal_links) > 0)
            or (
                content
                and (
                    re.search(r"""(?is)<a\s+[^>]*href\s*=\s*["'][^"']+["']""", content)
                    or re.search(r"""\[[^\]]+\]\([^)]+\)""", content)
                )
            )
        )

        if has_links:
            items.append(
                SeoCheckItem(
                    passed=True,
                    title="پیوندهای داخلی یا خارجی",
                    message=(
                        "پیوندهای داخلی یا خروجی برای هدایت کاربران "
                        "و خزنده‌های جستجو در محتوا قرار دارند."
                    ),
                    points=10,
                    max_points=10,
                    category="media_links",
                )
            )
        else:
            items.append(
                SeoCheckItem(
                    passed=False,
                    title="پیوندهای داخلی یا خارجی",
                    message=(
                        "هیچ لینک داخلی یا خروجی در صفحه یافت نشد. "
                        "پیوند به صفحات مرتبط و منابع معتبر اعتبار سئو را افزایش می‌دهد."
                    ),
                    points=0,
                    max_points=10,
                    category="media_links",
                )
            )

        return items

    # -------------------------------------------------------------------------
    # Grade & Recommendation Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _determine_grade(score: int) -> tuple[str, str]:
        """Assign Grade and Color based on Iranian / Rank Math standards.

        - 80 to 100: 'عالی' (green)
        - 50 to 79:  'متوسط و نیازمند بهبود' (yellow)
        - 0 to 49:   'ضعیف' (red)
        """
        if score >= 80:
            return "عالی", "green"
        if score >= 50:
            return "متوسط و نیازمند بهبود", "yellow"
        return "ضعیف", "red"

    @staticmethod
    def _generate_recommendations(checklist: list[SeoCheckItem]) -> list[str]:
        """Generate structured actionable recommendations for any failed checks."""
        recommendations: list[str] = []
        for item in checklist:
            if not item.passed:
                recommendations.append(item.message)
        return recommendations
