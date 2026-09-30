"""Code-registered block patterns for the page editor (WordPress parity).

WordPress ships a *block patterns* library: ready-made section templates an
editor inserts into a page and then fills with real copy. This module is the
same idea, registered in code the way :mod:`app.shared.content.shortcodes`
registers handlers — no new DB table, no migration. Each pattern is a static
HTML fragment (Tailwind classes matching the storefront's shadcn-style
semantic tokens) with ``{{slot}}`` placeholders and declared defaults, so the
editor can list them, render a preview with variable substitution, and insert
the result into a ``CmsPage.body_html``.

Usage::

    from app.modules.content.domain.block_patterns import (
        grouped_patterns,
        render_pattern,
    )

    groups = grouped_patterns()                      # list grouped by category
    html = render_pattern("hero-banner", {"title": "حراج پاییزی"})
"""

from __future__ import annotations

import html as _html
import re
import textwrap
from dataclasses import dataclass, field

from app.core.exceptions.handlers import NotFoundError

# Matches {{slot_name}} tokens inside pattern HTML.
_SLOT_RE = re.compile(r"\{\{\s*([a-z0-9_]+)\s*\}\}")


@dataclass(frozen=True)
class PatternVariable:
    """One editable slot of a pattern, with the editor label and fallback."""

    name: str
    label: str  # Persian label shown in the editor form
    default: str = ""


@dataclass(frozen=True)
class BlockPattern:
    """A ready-made section template the editor can insert into a page."""

    slug: str
    title: str  # Persian display title
    description: str  # Persian editor hint
    category: str  # Persian category label (grouping key)
    html: str
    keywords: tuple[str, ...] = ()
    variables: tuple[PatternVariable, ...] = field(default=())


def _frag(markup: str) -> str:
    """Dedent a triple-quoted fragment so stored HTML starts at column 0."""
    return textwrap.dedent(markup).strip()


# ── Registered patterns ────────────────────────────────────────────────────
# Order matters: grouped_patterns() emits categories in first-appearance order.

_PATTERNS: tuple[BlockPattern, ...] = (
    BlockPattern(
        slug="hero-banner",
        title="بنر اصلی (هیرو)",
        description="بنر بزرگ ابتدای صفحه با عنوان، زیرعنوان، تصویر و دکمه فراخوان",
        category="بنر و هیرو",
        keywords=("hero", "بنر", "هدر", "فراخوان"),
        variables=(
            PatternVariable("title", "عنوان", "کالکشن جدید رسید"),
            PatternVariable("subtitle", "زیرعنوان", "جدیدترین محصولات فصل با تخفیف ویژه"),
            PatternVariable("image_url", "آدرس تصویر", "/placeholder-hero.svg"),
            PatternVariable("cta_text", "متن دکمه", "همین حالا بخرید"),
            PatternVariable("cta_url", "لینک دکمه", "/products"),
        ),
        html=_frag(
            """
            <section
              class="relative overflow-hidden rounded-2xl bg-primary text-primary-foreground"
            >
              <div class="grid items-center gap-8 px-6 py-14 md:grid-cols-2 md:px-12">
                <div class="space-y-4">
                  <h1 class="text-3xl font-bold leading-tight md:text-5xl">{{title}}</h1>
                  <p class="text-base opacity-90 md:text-lg">{{subtitle}}</p>
                  <a href="{{cta_url}}"
                     class="inline-flex items-center rounded-xl bg-primary-foreground px-6 py-3
                            font-semibold text-primary transition hover:opacity-90">
                    {{cta_text}}
                  </a>
                </div>
                <img src="{{image_url}}" alt="{{title}}"
                     class="h-64 w-full rounded-xl object-cover md:h-80" loading="lazy" />
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="feature-grid",
        title="شبکه ویژگی‌ها",
        description="سه ویژگی یا مزیت فروشگاه با آیکن، عنوان و توضیح کوتاه",
        category="محتوا",
        keywords=("features", "ویژگی", "مزایا", "خدمات"),
        variables=(
            PatternVariable("title", "عنوان بخش", "چرا از ما بخرید؟"),
            PatternVariable("subtitle", "زیرعنوان", "مزیت‌هایی که خرید را برای شما آسان می‌کنند"),
            PatternVariable("item1_title", "عنوان ویژگی ۱", "ارسال سریع"),
            PatternVariable("item1_text", "توضیح ویژگی ۱", "ارسال به سراسر کشور در کمترین زمان"),
            PatternVariable("item2_title", "عنوان ویژگی ۲", "ضمانت اصالت"),
            PatternVariable(
                "item2_text", "توضیح ویژگی ۲", "تمام کالاها اصل و دارای گارانتی هستند"
            ),
            PatternVariable("item3_title", "عنوان ویژگی ۳", "پرداخت امن"),
            PatternVariable(
                "item3_text", "توضیح ویژگی ۳", "درگاه‌های بانکی معتبر و بازگشت وجه تضمین‌شده"
            ),
        ),
        html=_frag(
            """
            <section class="py-12">
              <div class="space-y-2 text-center">
                <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
                <p class="text-muted-foreground">{{subtitle}}</p>
              </div>
              <div class="mt-8 grid gap-6 md:grid-cols-3">
                <div class="rounded-xl border bg-background p-6 text-center shadow-sm">
                  <div class="mb-3 text-3xl">🚚</div>
                  <h3 class="font-semibold text-foreground">{{item1_title}}</h3>
                  <p class="mt-1 text-sm text-muted-foreground">{{item1_text}}</p>
                </div>
                <div class="rounded-xl border bg-background p-6 text-center shadow-sm">
                  <div class="mb-3 text-3xl">✅</div>
                  <h3 class="font-semibold text-foreground">{{item2_title}}</h3>
                  <p class="mt-1 text-sm text-muted-foreground">{{item2_text}}</p>
                </div>
                <div class="rounded-xl border bg-background p-6 text-center shadow-sm">
                  <div class="mb-3 text-3xl">🔒</div>
                  <h3 class="font-semibold text-foreground">{{item3_title}}</h3>
                  <p class="mt-1 text-sm text-muted-foreground">{{item3_text}}</p>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="product-showcase-cta",
        title="معرفی محصولات با دکمه",
        description="تصویر محصول کنار متن معرفی و دکمه رفتن به لیست محصولات",
        category="محصولات",
        keywords=("product", "محصول", "کالکشن", "cta"),
        variables=(
            PatternVariable("title", "عنوان", "پیشنهاد ویژه این هفته"),
            PatternVariable("subtitle", "توضیح", "منتخبی از پرفروش‌ترین محصولات با قیمت استثنایی"),
            PatternVariable("image_url", "آدرس تصویر", "/placeholder-product.svg"),
            PatternVariable("cta_text", "متن دکمه", "مشاهده محصولات"),
            PatternVariable("cta_url", "لینک دکمه", "/products"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border bg-background p-6 shadow-sm md:p-10">
              <div class="grid items-center gap-8 md:grid-cols-2">
                <img src="{{image_url}}" alt="{{title}}"
                     class="h-72 w-full rounded-xl object-cover" loading="lazy" />
                <div class="space-y-4">
                  <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
                  <p class="text-muted-foreground">{{subtitle}}</p>
                  <a href="{{cta_url}}"
                     class="inline-flex items-center rounded-xl bg-primary px-6 py-3 font-semibold
                            text-primary-foreground transition hover:bg-primary/90">
                    {{cta_text}}
                  </a>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="testimonials",
        title="نظرات مشتریان",
        description="دو نقل‌قول از مشتریان برای ایجاد اعتماد",
        category="اعتماد و بازخورد",
        keywords=("testimonials", "نظر", "بازخورد", "اعتماد"),
        variables=(
            PatternVariable("title", "عنوان بخش", "مشتریان ما چه می‌گویند"),
            PatternVariable(
                "item1_text", "متن نظر اول", "کیفیت محصولات عالی بود و ارسال سریع انجام شد."
            ),
            PatternVariable("item1_name", "نام مشتری اول", "سارا محمدی"),
            PatternVariable(
                "item2_text", "متن نظر دوم", "پشتیبانی بسیار پاسخگو بود؛ حتماً دوباره خرید می‌کنم."
            ),
            PatternVariable("item2_name", "نام مشتری دوم", "علی رضایی"),
        ),
        html=_frag(
            """
            <section class="py-12">
              <h2 class="mb-8 text-center text-2xl font-bold text-foreground md:text-3xl">
                {{title}}
              </h2>
              <div class="grid gap-6 md:grid-cols-2">
                <figure class="rounded-xl border bg-background p-6 shadow-sm">
                  <blockquote class="text-foreground">«{{item1_text}}»</blockquote>
                  <figcaption class="mt-4 text-sm font-medium text-muted-foreground">
                    — {{item1_name}}
                  </figcaption>
                </figure>
                <figure class="rounded-xl border bg-background p-6 shadow-sm">
                  <blockquote class="text-foreground">«{{item2_text}}»</blockquote>
                  <figcaption class="mt-4 text-sm font-medium text-muted-foreground">
                    — {{item2_name}}
                  </figcaption>
                </figure>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="faq-accordion",
        title="پرسش‌های متداول",
        description="آکاردئون سه پرسش و پاسخ با تگ‌های details/summary",
        category="پرسش‌های متداول",
        keywords=("faq", "سوال", "پرسش", "آکاردئون"),
        variables=(
            PatternVariable("title", "عنوان بخش", "پرسش‌های متداول"),
            PatternVariable("q1", "پرسش ۱", "چند روز به طول می‌انجامد تا سفارش ارسال شود؟"),
            PatternVariable("a1", "پاسخ ۱", "سفارش‌های تا ساعت ۱۴ روز کاری بعد ارسال می‌شوند."),
            PatternVariable("q2", "پرسش ۲", "امکان مرجوع کردن کالا وجود دارد؟"),
            PatternVariable(
                "a2", "پاسخ ۲", "بله، تا ۷ روز پس از دریافت می‌توانید کالا را مرجوع کنید."
            ),
            PatternVariable("q3", "پرسش ۳", "چه روش‌های پرداختی پشتیبانی می‌شود؟"),
            PatternVariable(
                "a3", "پاسخ ۳", "پرداخت آنلاین از طریق درگاه‌های بانکی و کارت به کارت."
            ),
        ),
        html=_frag(
            """
            <section class="py-12">
              <h2 class="mb-6 text-center text-2xl font-bold text-foreground md:text-3xl">
                {{title}}
              </h2>
              <div class="mx-auto max-w-3xl space-y-3">
                <details class="group rounded-xl border bg-background p-4 shadow-sm">
                  <summary class="cursor-pointer font-semibold text-foreground">{{q1}}</summary>
                  <p class="mt-3 text-sm text-muted-foreground">{{a1}}</p>
                </details>
                <details class="group rounded-xl border bg-background p-4 shadow-sm">
                  <summary class="cursor-pointer font-semibold text-foreground">{{q2}}</summary>
                  <p class="mt-3 text-sm text-muted-foreground">{{a2}}</p>
                </details>
                <details class="group rounded-xl border bg-background p-4 shadow-sm">
                  <summary class="cursor-pointer font-semibold text-foreground">{{q3}}</summary>
                  <p class="mt-3 text-sm text-muted-foreground">{{a3}}</p>
                </details>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="newsletter-signup",
        title="فرم عضویت در خبرنامه",
        description="دعوت به عضویت در خبرنامه با فیلد ایمیل و دکمه",
        category="فرم و خبرنامه",
        keywords=("newsletter", "خبرنامه", "ایمیل", "عضویت"),
        variables=(
            PatternVariable("title", "عنوان", "از تخفیف‌ها زودتر باخبر شوید"),
            PatternVariable(
                "subtitle", "زیرعنوان", "با عضویت در خبرنامه، اولین نفر باشید که حراج‌ها را می‌بیند."
            ),
            PatternVariable("placeholder", "متن راهنمای فیلد", "ایمیل شما"),
            PatternVariable("button_text", "متن دکمه", "عضویت"),
            PatternVariable("action_url", "نشانی عضویت", "/newsletter/subscribe"),
        ),
        # A link, not a <form>. WordPress dropped <form> from kses in 5.0.1 and
        # so does our allowlist, which meant this pattern shipped broken: the
        # whole form was stripped on save (754 -> 244 bytes) and the editor saw
        # an empty box. The old markup also posted to /newsletter, which is not
        # a route that exists. The subscribe page owns the real form.
        html=_frag(
            """
            <section class="rounded-2xl bg-primary/10 p-8 text-center md:p-12">
              <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
              <p class="mt-2 text-muted-foreground">{{subtitle}}</p>
              <p class="mx-auto mt-4 max-w-md text-sm text-muted-foreground">{{placeholder}}</p>
              <a href="{{action_url}}"
                 class="mt-6 inline-flex rounded-xl bg-primary px-6 py-3 font-semibold
                        text-primary-foreground transition hover:bg-primary/90">
                {{button_text}}
              </a>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="image-text",
        title="تصویر و متن",
        description="بخش دو ستونی تصویر کنار متن با دکمه اختیاری",
        category="محتوا",
        keywords=("about", "درباره", "متن", "تصویر"),
        variables=(
            PatternVariable("title", "عنوان", "داستان ما"),
            PatternVariable(
                "body", "متن", "ما از سال ۱۳۹۰ با هدف ارائه کالاهای اصل و باکیفیت فعالیت می‌کنیم."
            ),
            PatternVariable("image_url", "آدرس تصویر", "/placeholder-about.svg"),
            PatternVariable("cta_text", "متن دکمه", "بیشتر بدانید"),
            PatternVariable("cta_url", "لینک دکمه", "/about"),
        ),
        html=_frag(
            """
            <section class="py-12">
              <div class="grid items-center gap-8 md:grid-cols-2">
                <img src="{{image_url}}" alt="{{title}}"
                     class="h-72 w-full rounded-xl object-cover shadow-sm" loading="lazy" />
                <div class="space-y-4">
                  <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
                  <p class="leading-7 text-muted-foreground">{{body}}</p>
                  <a href="{{cta_url}}"
                     class="inline-flex items-center rounded-xl border border-primary px-6 py-3
                            font-semibold text-primary transition hover:bg-primary/10">
                    {{cta_text}}
                  </a>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="countdown-offer",
        title="بنر فروش ویژه با شمارش معکوس",
        description="نوار تخفیف فوری با کد تخفیف و زمان پایان",
        category="فروش و تخفیف",
        keywords=("offer", "sale", "تخفیف", "شمارش معکوس", "حراج"),
        variables=(
            PatternVariable("title", "عنوان", "فروش ویژه پایان فصل"),
            PatternVariable("subtitle", "زیرعنوان", "تا ۵۰٪ تخفیف روی هزاران کالا"),
            PatternVariable("ends_at", "زمان پایان (متن)", "شنبه ۲۳:۵۹"),
            PatternVariable("discount_code", "کد تخفیف", "SEASON50"),
            PatternVariable("cta_text", "متن دکمه", "خرید با تخفیف"),
            PatternVariable("cta_url", "لینک دکمه", "/products?discount=1"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl bg-amber-500/15 p-6 text-center md:p-10">
              <p class="text-sm font-medium uppercase tracking-wide text-amber-600">
                ⏰ {{ends_at}}
              </p>
              <h2 class="mt-2 text-2xl font-bold text-foreground md:text-4xl">{{title}}</h2>
              <p class="mt-2 text-muted-foreground">{{subtitle}}</p>
              <p
                class="mt-4 inline-block rounded-lg border border-dashed border-amber-600 px-4 py-2
                       font-mono text-lg font-bold text-amber-700"
              >
                {{discount_code}}
              </p>
              <div class="mt-6">
                <a href="{{cta_url}}"
                   class="inline-flex items-center rounded-xl bg-primary px-8 py-3 font-semibold
                          text-primary-foreground transition hover:bg-primary/90">
                  {{cta_text}}
                </a>
              </div>
            </section>
            """
        ),
    ),
)

PATTERNS: dict[str, BlockPattern] = {p.slug: p for p in _PATTERNS}


def get_pattern(slug: str) -> BlockPattern:
    """Return one pattern by slug, or raise NotFoundError."""
    pattern = PATTERNS.get(slug)
    if pattern is None:
        raise NotFoundError("BlockPattern", f"Block pattern '{slug}' not found")
    return pattern


def grouped_patterns() -> list[dict[str, object]]:
    """All patterns grouped by category, in first-appearance category order."""
    groups: dict[str, list[BlockPattern]] = {}
    for pattern in _PATTERNS:
        groups.setdefault(pattern.category, []).append(pattern)
    return [
        {
            "category": category,
            "patterns": [
                {
                    "slug": p.slug,
                    "title": p.title,
                    "description": p.description,
                    "category": p.category,
                    "keywords": list(p.keywords),
                    "variables": [
                        {"name": v.name, "label": v.label, "default": v.default}
                        for v in p.variables
                    ],
                }
                for p in patterns
            ],
        }
        for category, patterns in groups.items()
    ]


def render_pattern(slug: str, variables: dict[str, str] | None = None) -> str:
    """Render one pattern with ``variables`` substituted into its slots.

    Slots the caller did not provide fall back to their declared default — an
    editor rendering a fresh pattern sees the placeholder copy instead of a
    literal ``{{title}}``. Values are HTML-escaped, since slots land in both
    text and attribute contexts. Unknown keys in ``variables`` are ignored.
    """
    pattern = get_pattern(slug)
    provided = variables or {}
    resolved = {
        var.name: _html.escape(provided.get(var.name) or var.default, quote=True)
        for var in pattern.variables
    }
    return _SLOT_RE.sub(lambda m: resolved.get(m.group(1), m.group(0)), pattern.html)
