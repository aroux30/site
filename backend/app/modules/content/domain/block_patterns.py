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
            PatternVariable("q2", "پرسش ۲", "آیا محصولات دارای ضمانت هستند؟"),
            PatternVariable(
                "a2", "پاسخ ۲", "بله، تمامی محصولات با ضمانت اصالت و سلامت کالا ارسال می‌شوند."
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
    # ── الگوهای کامپوننت‌های جدید (فاز ۱–۴) ──────────────────────────
    BlockPattern(
        slug="star-rating-display",
        title="نمایش امتیاز ستاره‌ای",
        description="نوار ستاره‌های امتیاز محصول با عدد و تعداد نظرات",
        category="محصولات",
        keywords=("rating", "star", "امتیاز", "ستاره", "نظر"),
        variables=(
            PatternVariable("rating", "امتیاز (۰ تا ۵)", "۴.۳"),
            PatternVariable("review_count", "تعداد نظرات", "۱۲۸"),
        ),
        html=_frag(
            """
            <div class="inline-flex items-center gap-2 rounded-xl border border-border/60 bg-card px-4 py-2" dir="rtl">
              <span class="text-amber-400 text-lg leading-none tracking-wider">★★★★☆</span>
              <span class="font-bold tabular-nums text-sm text-foreground">{{rating}}</span>
              <span class="text-xs text-muted-foreground">({{review_count}} نظر)</span>
            </div>
            """
        ),
    ),
    BlockPattern(
        slug="review-histogram",
        title="نمودار توزیع امتیاز",
        description="نمودار میله‌ای توزیع ستاره‌ها با میانگین و تعداد کل نظرات",
        category="محصولات",
        keywords=("review", "histogram", "نمودار", "امتیاز", "توزیع"),
        variables=(
            PatternVariable("average", "میانگین امتیاز", "۴.۳"),
            PatternVariable("total", "تعداد کل نظرات", "۱۲۸"),
            PatternVariable("star5", "تعداد ۵ ستاره", "۶۱"),
            PatternVariable("star4", "تعداد ۴ ستاره", "۴۲"),
            PatternVariable("star3", "تعداد ۳ ستاره", "۱۵"),
            PatternVariable("star2", "تعداد ۲ ستاره", "۷"),
            PatternVariable("star1", "تعداد ۱ ستاره", "۳"),
        ),
        html=_frag(
            """
            <div class="rounded-2xl border border-border/60 bg-card p-5" dir="rtl">
              <div class="flex items-center gap-4 mb-5">
                <div class="text-center">
                  <div class="text-4xl font-bold tabular-nums text-foreground">{{average}}</div>
                  <div class="text-xs text-muted-foreground mt-0.5">از ۵</div>
                </div>
                <div>
                  <div class="text-amber-400 text-base leading-none mb-1">★★★★☆</div>
                  <div class="text-xs text-muted-foreground">بر اساس {{total}} نظر ثبت‌شده</div>
                </div>
              </div>
              <div class="space-y-2">
                <div class="flex items-center gap-2"><span class="w-4 text-xs font-medium text-center">۵</span><span class="text-amber-400 text-xs">★</span><div class="flex-1 h-2 rounded-full bg-muted/60 overflow-hidden"><div class="h-full rounded-full bg-emerald-500" style="width:100%"></div></div><span class="w-8 text-xs text-muted-foreground">{{star5}}</span></div>
                <div class="flex items-center gap-2"><span class="w-4 text-xs font-medium text-center">۴</span><span class="text-amber-400 text-xs">★</span><div class="flex-1 h-2 rounded-full bg-muted/60 overflow-hidden"><div class="h-full rounded-full bg-emerald-500" style="width:69%"></div></div><span class="w-8 text-xs text-muted-foreground">{{star4}}</span></div>
                <div class="flex items-center gap-2"><span class="w-4 text-xs font-medium text-center">۳</span><span class="text-amber-400 text-xs">★</span><div class="flex-1 h-2 rounded-full bg-muted/60 overflow-hidden"><div class="h-full rounded-full bg-amber-400" style="width:25%"></div></div><span class="w-8 text-xs text-muted-foreground">{{star3}}</span></div>
                <div class="flex items-center gap-2"><span class="w-4 text-xs font-medium text-center">۲</span><span class="text-amber-400 text-xs">★</span><div class="flex-1 h-2 rounded-full bg-muted/60 overflow-hidden"><div class="h-full rounded-full bg-red-400" style="width:11%"></div></div><span class="w-8 text-xs text-muted-foreground">{{star2}}</span></div>
                <div class="flex items-center gap-2"><span class="w-4 text-xs font-medium text-center">۱</span><span class="text-amber-400 text-xs">★</span><div class="flex-1 h-2 rounded-full bg-muted/60 overflow-hidden"><div class="h-full rounded-full bg-red-400" style="width:5%"></div></div><span class="w-8 text-xs text-muted-foreground">{{star1}}</span></div>
              </div>
            </div>
            """
        ),
    ),
    BlockPattern(
        slug="product-card-grid",
        title="شبکه کارت محصول",
        description="سه کارت محصول در یک ردیف با تصویر، عنوان، قیمت و دکمه خرید",
        category="محصولات",
        keywords=("product", "card", "grid", "کارت", "محصول", "شبکه"),
        variables=(
            PatternVariable("title", "عنوان بخش", "محصولات پرفروش"),
            PatternVariable("p1_name", "نام محصول ۱", "هدفون بلوتوثی"),
            PatternVariable("p1_price", "قیمت محصول ۱", "۱۸,۵۰۰,۰۰۰ تومان"),
            PatternVariable("p1_image", "تصویر محصول ۱", "/placeholder-product.svg"),
            PatternVariable("p1_url", "لینک محصول ۱", "/products/product-1"),
            PatternVariable("p2_name", "نام محصول ۲", "ایرپاد پرو"),
            PatternVariable("p2_price", "قیمت محصول ۲", "۱۲,۹۰۰,۰۰۰ تومان"),
            PatternVariable("p2_image", "تصویر محصول ۲", "/placeholder-product.svg"),
            PatternVariable("p2_url", "لینک محصول ۲", "/products/product-2"),
            PatternVariable("p3_name", "نام محصول ۳", "اسپیکر بلوتوثی"),
            PatternVariable("p3_price", "قیمت محصول ۳", "۸,۷۵۰,۰۰۰ تومان"),
            PatternVariable("p3_image", "تصویر محصول ۳", "/placeholder-product.svg"),
            PatternVariable("p3_url", "لینک محصول ۳", "/products/product-3"),
        ),
        html=_frag(
            """
            <section class="py-8" dir="rtl">
              <h2 class="mb-6 text-2xl font-bold text-foreground text-center md:text-3xl">{{title}}</h2>
              <div class="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
                <div class="group rounded-2xl border border-border/60 bg-card overflow-hidden transition-all hover:shadow-xl hover:border-primary/30">
                  <a href="{{p1_url}}" class="block h-56 bg-muted/20 overflow-hidden"><img src="{{p1_image}}" alt="{{p1_name}}" class="h-full w-full object-contain p-4 transition-transform group-hover:scale-105" loading="lazy"/></a>
                  <div class="p-4 space-y-2">
                    <a href="{{p1_url}}"><h3 class="font-bold text-foreground group-hover:text-primary transition-colors line-clamp-2">{{p1_name}}</h3></a>
                    <div class="flex items-center justify-between pt-2 border-t border-border/60">
                      <span class="font-black text-primary text-lg">{{p1_price}}</span>
                      <a href="{{p1_url}}" class="rounded-xl bg-emerald-700 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-800 transition-colors">خرید</a>
                    </div>
                  </div>
                </div>
                <div class="group rounded-2xl border border-border/60 bg-card overflow-hidden transition-all hover:shadow-xl hover:border-primary/30">
                  <a href="{{p2_url}}" class="block h-56 bg-muted/20 overflow-hidden"><img src="{{p2_image}}" alt="{{p2_name}}" class="h-full w-full object-contain p-4 transition-transform group-hover:scale-105" loading="lazy"/></a>
                  <div class="p-4 space-y-2">
                    <a href="{{p2_url}}"><h3 class="font-bold text-foreground group-hover:text-primary transition-colors line-clamp-2">{{p2_name}}</h3></a>
                    <div class="flex items-center justify-between pt-2 border-t border-border/60">
                      <span class="font-black text-primary text-lg">{{p2_price}}</span>
                      <a href="{{p2_url}}" class="rounded-xl bg-emerald-700 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-800 transition-colors">خرید</a>
                    </div>
                  </div>
                </div>
                <div class="group rounded-2xl border border-border/60 bg-card overflow-hidden transition-all hover:shadow-xl hover:border-primary/30">
                  <a href="{{p3_url}}" class="block h-56 bg-muted/20 overflow-hidden"><img src="{{p3_image}}" alt="{{p3_name}}" class="h-full w-full object-contain p-4 transition-transform group-hover:scale-105" loading="lazy"/></a>
                  <div class="p-4 space-y-2">
                    <a href="{{p3_url}}"><h3 class="font-bold text-foreground group-hover:text-primary transition-colors line-clamp-2">{{p3_name}}</h3></a>
                    <div class="flex items-center justify-between pt-2 border-t border-border/60">
                      <span class="font-black text-primary text-lg">{{p3_price}}</span>
                      <a href="{{p3_url}}" class="rounded-xl bg-emerald-700 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-800 transition-colors">خرید</a>
                    </div>
                  </div>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="text-marquee",
        title="متن چرخشی تبلیغاتی",
        description="نوار متن متحرک برای اطلاع‌رسانی ارسال رایگان، ضمانت و…",
        category="بنر و هیرو",
        keywords=("marquee", "متن چرخشی", "اطلاع‌رسانی", "نوار"),
        variables=(
            PatternVariable("text1", "متن ۱", "ارسال رایگان برای سفارش‌های بالای ۵۰۰ هزار تومان"),
            PatternVariable("text2", "متن ۲", "ضمانت بازگشت ۷ روزه بدون قید و شرط"),
            PatternVariable("text3", "متن ۳", "پرداخت امن با رمز دوم پویا"),
            PatternVariable("text4", "متن ۴", "پشتیبانی ۲۴ ساعته"),
        ),
        html=_frag(
            """
            <div class="rounded-xl bg-primary/10 px-4 py-3 text-center" dir="rtl">
              <p class="text-sm font-bold text-primary">{{text1}} · {{text2}} · {{text3}} · {{text4}}</p>
            </div>
            """
        ),
    ),
    BlockPattern(
        slug="stats-counter",
        title="شمارنده آمار",
        description="چهار عدد آماری بزرگ (محصول، سفارش، رضایت و…) در یک ردیف",
        category="محتوا",
        keywords=("stats", "counter", "آمار", "شمارنده", "عدد"),
        variables=(
            PatternVariable("stat1_value", "عدد ۱", "۱,۲۳۴"),
            PatternVariable("stat1_label", "برچسب ۱", "محصول"),
            PatternVariable("stat2_value", "عدد ۲", "۵,۶۷۸"),
            PatternVariable("stat2_label", "برچسب ۲", "سفارش"),
            PatternVariable("stat3_value", "عدد ۳", "۹۸٪"),
            PatternVariable("stat3_label", "برچسب ۳", "رضایت مشتری"),
            PatternVariable("stat4_value", "عدد ۴", "۲۴"),
            PatternVariable("stat4_label", "برچسب ۴", "ساعت پشتیبانی"),
        ),
        html=_frag(
            """
            <section class="py-8" dir="rtl">
              <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <div class="rounded-xl border border-border/60 p-4 text-center">
                  <div class="text-2xl font-black text-primary tabular-nums">{{stat1_value}}</div>
                  <span class="text-xs text-muted-foreground">{{stat1_label}}</span>
                </div>
                <div class="rounded-xl border border-border/60 p-4 text-center">
                  <div class="text-2xl font-black text-emerald-600 tabular-nums">{{stat2_value}}</div>
                  <span class="text-xs text-muted-foreground">{{stat2_label}}</span>
                </div>
                <div class="rounded-xl border border-border/60 p-4 text-center">
                  <div class="text-2xl font-black text-amber-600 tabular-nums">{{stat3_value}}</div>
                  <span class="text-xs text-muted-foreground">{{stat3_label}}</span>
                </div>
                <div class="rounded-xl border border-border/60 p-4 text-center">
                  <div class="text-2xl font-black text-blue-600 tabular-nums">{{stat4_value}}</div>
                  <span class="text-xs text-muted-foreground">{{stat4_label}}</span>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="image-gallery-showcase",
        title="گالری تصاویر",
        description="شبکه چهار تصویر با گوشه‌های گرد برای نمایش محصول یا پرتفولیو",
        category="محصولات",
        keywords=("gallery", "image", "گالری", "تصویر", "عکس"),
        variables=(
            PatternVariable("title", "عنوان", "گالری محصولات"),
            PatternVariable("img1", "تصویر ۱", "/placeholder-product.svg"),
            PatternVariable("img2", "تصویر ۲", "/placeholder-product.svg"),
            PatternVariable("img3", "تصویر ۳", "/placeholder-product.svg"),
            PatternVariable("img4", "تصویر ۴", "/placeholder-product.svg"),
        ),
        html=_frag(
            """
            <section class="py-8" dir="rtl">
              <h2 class="mb-6 text-2xl font-bold text-foreground text-center">{{title}}</h2>
              <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
                <img src="{{img1}}" alt="تصویر ۱" class="h-48 w-full rounded-xl object-cover border border-border/60" loading="lazy"/>
                <img src="{{img2}}" alt="تصویر ۲" class="h-48 w-full rounded-xl object-cover border border-border/60" loading="lazy"/>
                <img src="{{img3}}" alt="تصویر ۳" class="h-48 w-full rounded-xl object-cover border border-border/60" loading="lazy"/>
                <img src="{{img4}}" alt="تصویر ۴" class="h-48 w-full rounded-xl object-cover border border-border/60" loading="lazy"/>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="discount-badge-banner",
        title="نوار تخفیف با بَج",
        description="نوار رنگی با درصد تخفیف و لینک محصولات",
        category="فروش و تخفیف",
        keywords=("discount", "badge", "تخفیف", "بج", "حراج"),
        variables=(
            PatternVariable("percent", "درصد تخفیف", "۳۰"),
            PatternVariable("text", "متن", "تخفیف ویژه روی محصولات منتخب"),
            PatternVariable("cta_text", "متن دکمه", "مشاهده محصولات"),
            PatternVariable("cta_url", "لینک", "/products"),
        ),
        html=_frag(
            """
            <div class="flex flex-wrap items-center justify-between gap-4 rounded-2xl bg-red-500/10 p-5" dir="rtl">
              <div class="flex items-center gap-3">
                <span class="rounded-xl bg-red-500 px-3 py-1.5 text-lg font-black text-white">{{percent}}٪</span>
                <span class="font-bold text-foreground">{{text}}</span>
              </div>
              <a href="{{cta_url}}" class="rounded-xl bg-red-500 px-5 py-2.5 text-sm font-bold text-white hover:bg-red-600 transition-colors">{{cta_text}}</a>
            </div>
            """
        ),
    ),
    BlockPattern(
        slug="mega-menu-categories",
        title="لیست دسته‌بندی‌ها",
        description="شبکه دسته‌بندی‌ها با لینک به صفحه هر دسته",
        category="ناوبری",
        keywords=("category", "menu", "دسته‌بندی", "ناوبری", "منو"),
        variables=(
            PatternVariable("title", "عنوان", "دسته‌بندی محصولات"),
            PatternVariable("cat1_name", "دسته ۱", "لپ‌تاپ و کامپیوتر"),
            PatternVariable("cat1_url", "لینک دسته ۱", "/category/laptop"),
            PatternVariable("cat2_name", "دسته ۲", "موبایل و تبلت"),
            PatternVariable("cat2_url", "لینک دسته ۲", "/category/mobile"),
            PatternVariable("cat3_name", "دسته ۳", "هدفون و اسپیکر"),
            PatternVariable("cat3_url", "لینک دسته ۳", "/category/audio"),
            PatternVariable("cat4_name", "دسته ۴", "لوازم جانبی"),
            PatternVariable("cat4_url", "لینک دسته ۴", "/category/accessories"),
        ),
        html=_frag(
            """
            <section class="py-8" dir="rtl">
              <h2 class="mb-6 text-2xl font-bold text-foreground text-center">{{title}}</h2>
              <div class="grid grid-cols-2 gap-3 md:grid-cols-4">
                <a href="{{cat1_url}}" class="rounded-xl border border-border/60 bg-card p-5 text-center font-bold text-foreground transition hover:border-primary/40 hover:shadow-lg hover:text-primary">{{cat1_name}}</a>
                <a href="{{cat2_url}}" class="rounded-xl border border-border/60 bg-card p-5 text-center font-bold text-foreground transition hover:border-primary/40 hover:shadow-lg hover:text-primary">{{cat2_name}}</a>
                <a href="{{cat3_url}}" class="rounded-xl border border-border/60 bg-card p-5 text-center font-bold text-foreground transition hover:border-primary/40 hover:shadow-lg hover:text-primary">{{cat3_name}}</a>
                <a href="{{cat4_url}}" class="rounded-xl border border-border/60 bg-card p-5 text-center font-bold text-foreground transition hover:border-primary/40 hover:shadow-lg hover:text-primary">{{cat4_name}}</a>
              </div>
            </section>
            """
        ),
    ),
    # ── الگوهای المنتوری برگزیده (Elementor-inspired Curated Patterns) ───
    BlockPattern(
        slug="pricing-table",
        title="جدول قیمت‌گذاری و تعرفه‌ها",
        description="۳ پلن تعرفه (پایه، حرفه‌ای، ویژه) با امکانات تیک‌خورده و دکمه‌های اقدام",
        category="قیمت‌گذاری و تعرفه",
        keywords=("pricing", "table", "تعرفه", "قیمت", "پلن", "اشتراک", "بسته"),
        variables=(
            PatternVariable("title", "عنوان بخش", "پلن‌های قیمت‌گذاری و تعرفه‌ها"),
            PatternVariable(
                "subtitle",
                "زیرعنوان",
                "پلن متناسب با کسب‌وکار خود را انتخاب کنید و رشد خود را شتاب دهید",
            ),
            # پلن ۱: پایه
            PatternVariable("plan1_name", "نام پلن ۱", "پایه"),
            PatternVariable("plan1_desc", "توضیح پلن ۱", "مناسب برای شروع و کسب‌وکارهای نوپا"),
            PatternVariable("plan1_price", "قیمت پلن ۱", "۲۹۰,۰۰۰ تومان"),
            PatternVariable("plan1_period", "دوره پرداخت پلن ۱", "/ ماهانه"),
            PatternVariable("plan1_f1", "ویژگی ۱ پلن ۱", "دسترسی به امکانات پایه"),
            PatternVariable("plan1_f2", "ویژگی ۲ پلن ۱", "پشتیبانی ایمیلی"),
            PatternVariable("plan1_f3", "ویژگی ۳ پلن ۱", "۱ کاربر فعال"),
            PatternVariable("plan1_cta", "متن دکمه پلن ۱", "انتخاب پلن پایه"),
            PatternVariable("plan1_url", "لینک دکمه پلن ۱", "/pricing?plan=basic"),
            # پلن ۲: حرفه‌ای
            PatternVariable("plan2_badge", "برچسب پلن ۲", "محبوب‌ترین"),
            PatternVariable("plan2_name", "نام پلن ۲", "حرفه‌ای"),
            PatternVariable(
                "plan2_desc",
                "توضیح پلن ۲",
                "بهترین انتخاب برای تیم‌ها و شرکت‌های در حال توسعه",
            ),
            PatternVariable("plan2_price", "قیمت پلن ۲", "۶۹۰,۰۰۰ تومان"),
            PatternVariable("plan2_period", "دوره پرداخت پلن ۲", "/ ماهانه"),
            PatternVariable("plan2_f1", "ویژگی ۱ پلن ۲", "تمامی امکانات پلن پایه"),
            PatternVariable("plan2_f2", "ویژگی ۲ پلن ۲", "پشتیبانی اولویت‌دار تیکت و تلفن"),
            PatternVariable("plan2_f3", "ویژگی ۳ پلن ۲", "تا ۵ کاربر فعال همزمان"),
            PatternVariable("plan2_f4", "ویژگی ۴ پلن ۲", "گزارش‌های پیشرفته و تحلیلی"),
            PatternVariable("plan2_cta", "متن دکمه پلن ۲", "شروع پلن حرفه‌ای"),
            PatternVariable("plan2_url", "لینک دکمه پلن ۲", "/pricing?plan=pro"),
            # پلن ۳: ویژه
            PatternVariable("plan3_name", "نام پلن ۳", "ویژه"),
            PatternVariable(
                "plan3_desc",
                "توضیح پلن ۳",
                "راهکار جامع برای سازمان‌ها و پروژه‌های با مقیاس بالا",
            ),
            PatternVariable("plan3_price", "قیمت پلن ۳", "۱,۴۹۰,۰۰۰ تومان"),
            PatternVariable("plan3_period", "دوره پرداخت پلن ۳", "/ ماهانه"),
            PatternVariable("plan3_f1", "ویژگی ۱ پلن ۳", "دسترسی نامحدود به تمامی قابلیت‌ها"),
            PatternVariable("plan3_f2", "ویژگی ۲ پلن ۳", "پشتیبانی ۲۴ ساعته اختصاصی"),
            PatternVariable("plan3_f3", "ویژگی ۳ پلن ۳", "کاربران نامحدود و مدیریت دسترسی"),
            PatternVariable("plan3_f4", "ویژگی ۴ پلن ۳", "پشتیبان‌گیری ابری روزانه"),
            PatternVariable("plan3_cta", "متن دکمه پلن ۳", "ارتباط با کارشناسان"),
            PatternVariable("plan3_url", "لینک دکمه پلن ۳", "/contact?plan=enterprise"),
        ),
        html=_frag(
            """
            <section class="py-12" dir="rtl">
              <div class="mx-auto max-w-6xl px-4">
                <div class="mb-10 text-center">
                  <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
                  <p class="mt-2 text-sm text-muted-foreground md:text-base">{{subtitle}}</p>
                </div>
                <div class="grid grid-cols-1 items-stretch gap-6 md:grid-cols-3">
                  <div class="flex flex-col justify-between rounded-2xl border border-border/60 bg-card p-6 shadow-sm transition hover:shadow-md">
                    <div>
                      <h3 class="text-xl font-bold text-foreground">{{plan1_name}}</h3>
                      <p class="mt-1 text-xs text-muted-foreground">{{plan1_desc}}</p>
                      <div class="mt-5 flex items-baseline gap-1">
                        <span class="text-2xl font-extrabold text-foreground tabular-nums">{{plan1_price}}</span>
                        <span class="text-xs text-muted-foreground">{{plan1_period}}</span>
                      </div>
                      <ul class="mt-6 space-y-3 text-sm text-muted-foreground">
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan1_f1}}</span>
                        </li>
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan1_f2}}</span>
                        </li>
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan1_f3}}</span>
                        </li>
                      </ul>
                    </div>
                    <div class="mt-8 pt-4 border-t border-border/40">
                      <a href="{{plan1_url}}" class="block w-full rounded-xl border border-primary bg-background py-2.5 text-center text-sm font-semibold text-primary transition hover:bg-primary hover:text-primary-foreground">{{plan1_cta}}</a>
                    </div>
                  </div>
                  <div class="relative flex flex-col justify-between rounded-2xl border-2 border-primary bg-card p-6 shadow-lg shadow-primary/5 md:-translate-y-2">
                    <div class="absolute -top-3.5 left-1/2 -translate-x-1/2 rounded-full bg-primary px-3 py-0.5 text-xs font-bold text-primary-foreground shadow-sm">
                      {{plan2_badge}}
                    </div>
                    <div>
                      <h3 class="text-xl font-bold text-primary">{{plan2_name}}</h3>
                      <p class="mt-1 text-xs text-muted-foreground">{{plan2_desc}}</p>
                      <div class="mt-5 flex items-baseline gap-1">
                        <span class="text-3xl font-black text-primary tabular-nums">{{plan2_price}}</span>
                        <span class="text-xs text-muted-foreground">{{plan2_period}}</span>
                      </div>
                      <ul class="mt-6 space-y-3 text-sm text-foreground">
                        <li class="flex items-center gap-2 font-medium">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">✓</span>
                          <span>{{plan2_f1}}</span>
                        </li>
                        <li class="flex items-center gap-2 font-medium">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">✓</span>
                          <span>{{plan2_f2}}</span>
                        </li>
                        <li class="flex items-center gap-2 font-medium">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">✓</span>
                          <span>{{plan2_f3}}</span>
                        </li>
                        <li class="flex items-center gap-2 font-medium">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">✓</span>
                          <span>{{plan2_f4}}</span>
                        </li>
                      </ul>
                    </div>
                    <div class="mt-8 pt-4 border-t border-border/40">
                      <a href="{{plan2_url}}" class="block w-full rounded-xl bg-primary py-2.5 text-center text-sm font-semibold text-primary-foreground shadow transition hover:bg-primary/90">{{plan2_cta}}</a>
                    </div>
                  </div>
                  <div class="flex flex-col justify-between rounded-2xl border border-border/60 bg-card p-6 shadow-sm transition hover:shadow-md">
                    <div>
                      <h3 class="text-xl font-bold text-foreground">{{plan3_name}}</h3>
                      <p class="mt-1 text-xs text-muted-foreground">{{plan3_desc}}</p>
                      <div class="mt-5 flex items-baseline gap-1">
                        <span class="text-2xl font-extrabold text-foreground tabular-nums">{{plan3_price}}</span>
                        <span class="text-xs text-muted-foreground">{{plan3_period}}</span>
                      </div>
                      <ul class="mt-6 space-y-3 text-sm text-muted-foreground">
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan3_f1}}</span>
                        </li>
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan3_f2}}</span>
                        </li>
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan3_f3}}</span>
                        </li>
                        <li class="flex items-center gap-2">
                          <span class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/10 text-xs font-bold text-emerald-600">✓</span>
                          <span>{{plan3_f4}}</span>
                        </li>
                      </ul>
                    </div>
                    <div class="mt-8 pt-4 border-t border-border/40">
                      <a href="{{plan3_url}}" class="block w-full rounded-xl border border-border bg-muted/40 py-2.5 text-center text-sm font-semibold text-foreground transition hover:bg-muted">{{plan3_cta}}</a>
                    </div>
                  </div>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="price-list",
        title="لیست قیمت آیتم‌ها و خدمات",
        description="لیست قیمت اقلام و خدمات با خط نقطه‌چین اتصال و قیمت به تومان",
        category="قیمت‌گذاری و تعرفه",
        keywords=("price", "list", "منو", "قیمت", "خدمات", "تعرفه", "نقطه‌چین"),
        variables=(
            PatternVariable("title", "عنوان لیست", "لیست قیمت خدمات و محصولات"),
            PatternVariable(
                "subtitle",
                "توضیح یا یادداشت",
                "قیمت‌ها به تومان و شامل کلیه خدمات جانبی است",
            ),
            # آیتم ۱
            PatternVariable("item1_title", "عنوان آیتم ۱", "مشاوره تخصصی و تحلیل نیازسنجی"),
            PatternVariable(
                "item1_desc",
                "توضیح آیتم ۱",
                "جلسه آنلاین ۹۰ دقیقه‌ای به همراه ارائه سند راهبردی",
            ),
            PatternVariable("item1_price", "قیمت آیتم ۱", "۴۵۰,۰۰۰ تومان"),
            # آیتم ۲
            PatternVariable("item2_title", "عنوان آیتم ۲", "نصب و پیکربندی اولیه نرم‌افزار"),
            PatternVariable(
                "item2_desc",
                "توضیح آیتم ۲",
                "راه‌اندازی کامل سیستم و آموزش کار با پنل مدیریت",
            ),
            PatternVariable("item2_price", "قیمت آیتم ۲", "۸۵۰,۰۰۰ تومان"),
            # آیتم ۳
            PatternVariable("item3_title", "عنوان آیتم ۳", "پشتیبانی فنی و نگهداری ماهانه"),
            PatternVariable(
                "item3_desc",
                "توضیح آیتم ۳",
                "پایش مداوم، به‌روزرسانی امنیتی و پشتیبان‌گیری منظم",
            ),
            PatternVariable("item3_price", "قیمت آیتم ۳", "۱,۲۰۰,۰۰۰ تومان"),
            # آیتم ۴
            PatternVariable("item4_title", "عنوان آیتم ۴", "توسعه و سفارشی‌سازی اختصاصی"),
            PatternVariable(
                "item4_desc",
                "توضیح آیتم ۴",
                "طراحی و پیاده‌سازی ویژگی‌های خاص متناسب با سفارش شما",
            ),
            PatternVariable("item4_price", "قیمت آیتم ۴", "۲,۵۰۰,۰۰۰ تومان"),
            # آیتم ۵
            PatternVariable("item5_title", "عنوان آیتم ۵", "بسته آموزش و توانمندسازی پرسنل"),
            PatternVariable(
                "item5_desc",
                "توضیح آیتم ۵",
                "کارگاه آموزشی حضوری یا آنلاین با ارائه گواهی دوره",
            ),
            PatternVariable("item5_price", "قیمت آیتم ۵", "۱,۸۰۰,۰۰۰ تومان"),
        ),
        html=_frag(
            """
            <section class="py-10" dir="rtl">
              <div class="mx-auto max-w-3xl rounded-2xl border border-border/60 bg-card p-6 shadow-sm md:p-8">
                <div class="mb-8 border-b border-border/60 pb-4 text-center">
                  <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
                  <p class="mt-1 text-sm text-muted-foreground">{{subtitle}}</p>
                </div>
                <div class="space-y-6">
                  <div class="group">
                    <div class="flex items-baseline justify-between gap-2">
                      <span class="font-bold text-foreground transition-colors group-hover:text-primary">{{item1_title}}</span>
                      <span class="flex-1 border-b-2 border-dotted border-border/80 mx-2"></span>
                      <span class="shrink-0 font-black text-primary tabular-nums">{{item1_price}}</span>
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">{{item1_desc}}</p>
                  </div>
                  <div class="group">
                    <div class="flex items-baseline justify-between gap-2">
                      <span class="font-bold text-foreground transition-colors group-hover:text-primary">{{item2_title}}</span>
                      <span class="flex-1 border-b-2 border-dotted border-border/80 mx-2"></span>
                      <span class="shrink-0 font-black text-primary tabular-nums">{{item2_price}}</span>
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">{{item2_desc}}</p>
                  </div>
                  <div class="group">
                    <div class="flex items-baseline justify-between gap-2">
                      <span class="font-bold text-foreground transition-colors group-hover:text-primary">{{item3_title}}</span>
                      <span class="flex-1 border-b-2 border-dotted border-border/80 mx-2"></span>
                      <span class="shrink-0 font-black text-primary tabular-nums">{{item3_price}}</span>
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">{{item3_desc}}</p>
                  </div>
                  <div class="group">
                    <div class="flex items-baseline justify-between gap-2">
                      <span class="font-bold text-foreground transition-colors group-hover:text-primary">{{item4_title}}</span>
                      <span class="flex-1 border-b-2 border-dotted border-border/80 mx-2"></span>
                      <span class="shrink-0 font-black text-primary tabular-nums">{{item4_price}}</span>
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">{{item4_desc}}</p>
                  </div>
                  <div class="group">
                    <div class="flex items-baseline justify-between gap-2">
                      <span class="font-bold text-foreground transition-colors group-hover:text-primary">{{item5_title}}</span>
                      <span class="flex-1 border-b-2 border-dotted border-border/80 mx-2"></span>
                      <span class="shrink-0 font-black text-primary tabular-nums">{{item5_price}}</span>
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground">{{item5_desc}}</p>
                  </div>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="icon-box-grid",
        title="جعبه‌های مزایا و خدمات",
        description="۴ ستون جعبه خدمات و مزایا با آیکون، عنوان و توضیح مختصر",
        category="محتوا",
        keywords=("icon", "box", "grid", "مزایا", "خدمات", "آیکون", "ستون", "ویژگی"),
        variables=(
            PatternVariable("title", "عنوان بخش", "چرا خدمات ما را انتخاب می‌کنند؟"),
            PatternVariable(
                "subtitle",
                "زیرعنوان",
                "ارائه برترین راهکارها با تمرکز بر کیفیت، سرعت و رضایت شما",
            ),
            # جعبه ۱
            PatternVariable("box1_icon", "آیکون ۱", "🚀"),
            PatternVariable("box1_title", "عنوان جعبه ۱", "تحویل سریع و آنی"),
            PatternVariable(
                "box1_desc",
                "توضیح جعبه ۱",
                "کلیه سفارش‌ها در کوتاه‌ترین زمان پردازش و آماده ارسال یا تحویل می‌شوند.",
            ),
            # جعبه ۲
            PatternVariable("box2_icon", "آیکون ۲", "🛡️"),
            PatternVariable("box2_title", "عنوان جعبه ۲", "تضمین اصالت و کیفیت"),
            PatternVariable(
                "box2_desc",
                "توضیح جعبه ۲",
                "تضمین صددرصدی اصالت تمامی کالاها همراه با گارانتی معتبر شرکتی.",
            ),
            # جعبه ۳
            PatternVariable("box3_icon", "آیکون ۳", "💳"),
            PatternVariable("box3_title", "عنوان جعبه ۳", "پرداخت امن و مطمئن"),
            PatternVariable(
                "box3_desc",
                "توضیح جعبه ۳",
                "پشتیبانی از درگاه‌های بانکی عضو شاپرک و امنیت کامل تراکنش‌ها.",
            ),
            # جعبه ۴
            PatternVariable("box4_icon", "آیکون ۴", "🎧"),
            PatternVariable("box4_title", "عنوان جعبه ۴", "پشتیبانی هفت‌روزه"),
            PatternVariable(
                "box4_desc",
                "توضیح جعبه ۴",
                "کارشناسان مجرب در تمام روزهای هفته آماده پاسخگویی به سوالات شما هستند.",
            ),
        ),
        html=_frag(
            """
            <section class="py-12" dir="rtl">
              <div class="space-y-2 text-center">
                <h2 class="text-2xl font-bold text-foreground md:text-3xl">{{title}}</h2>
                <p class="text-sm text-muted-foreground md:text-base">{{subtitle}}</p>
              </div>
              <div class="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <div class="group rounded-2xl border border-border/60 bg-card p-6 text-center shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-md">
                  <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-2xl transition-transform group-hover:scale-110">
                    {{box1_icon}}
                  </div>
                  <h3 class="font-bold text-foreground text-lg group-hover:text-primary transition-colors">{{box1_title}}</h3>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground md:text-sm">{{box1_desc}}</p>
                </div>
                <div class="group rounded-2xl border border-border/60 bg-card p-6 text-center shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-md">
                  <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-2xl transition-transform group-hover:scale-110">
                    {{box2_icon}}
                  </div>
                  <h3 class="font-bold text-foreground text-lg group-hover:text-primary transition-colors">{{box2_title}}</h3>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground md:text-sm">{{box2_desc}}</p>
                </div>
                <div class="group rounded-2xl border border-border/60 bg-card p-6 text-center shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-md">
                  <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-2xl transition-transform group-hover:scale-110">
                    {{box3_icon}}
                  </div>
                  <h3 class="font-bold text-foreground text-lg group-hover:text-primary transition-colors">{{box3_title}}</h3>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground md:text-sm">{{box3_desc}}</p>
                </div>
                <div class="group rounded-2xl border border-border/60 bg-card p-6 text-center shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-md">
                  <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-2xl transition-transform group-hover:scale-110">
                    {{box4_icon}}
                  </div>
                  <h3 class="font-bold text-foreground text-lg group-hover:text-primary transition-colors">{{box4_title}}</h3>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground md:text-sm">{{box4_desc}}</p>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="author-bio",
        title="کارت معرفی کارشناس / نویسنده",
        description="کارت معرفی نویسنده یا کارشناس با عکس، نام، سمت، بیوگرافی و راه‌های ارتباطی",
        category="محتوا",
        keywords=("author", "bio", "نویسنده", "کارشناس", "پروفایل", "بیوگرافی", "درباره"),
        variables=(
            PatternVariable("name", "نام و نام خانوادگی", "دکتر رضا کاظمی"),
            PatternVariable("role", "سمت یا تخصص", "پژوهشگر ارشد و کارشناس تجربه کاربری"),
            PatternVariable("badge", "برچسب یا گواهی", "نویسنده برگزیده"),
            PatternVariable("avatar_url", "آدرس تصویر پروفایل", "/placeholder-avatar.svg"),
            PatternVariable(
                "bio",
                "متن بیوگرافی",
                "بیش از یک دهه سابقه در تحلیل داده، طراحی تجربه کاربری و تولید محتوای تخصصی در کسب‌وکارهای مدرن فناوری.",
            ),
            PatternVariable("contact_email", "ایمیل یا شناسه ارتباطی", "reza.kazemi@example.com"),
            PatternVariable("cta_text", "متن دکمه ارتباط", "ارسال پیام یا مشاوره"),
            PatternVariable("cta_url", "لینک دکمه ارتباط", "/contact?to=author"),
        ),
        html=_frag(
            """
            <section class="py-8" dir="rtl">
              <div class="mx-auto max-w-2xl rounded-2xl border border-border/60 bg-card p-6 shadow-sm md:p-8">
                <div class="flex flex-col items-center gap-6 text-center sm:flex-row sm:items-start sm:text-right">
                  <img src="{{avatar_url}}" alt="{{name}}" class="h-28 w-28 shrink-0 rounded-2xl border-2 border-primary/20 object-cover shadow-sm" loading="lazy" />
                  <div class="flex-1 space-y-3">
                    <div class="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
                      <h3 class="text-xl font-bold text-foreground">{{name}}</h3>
                      <span class="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-semibold text-primary">{{badge}}</span>
                    </div>
                    <p class="text-sm font-medium text-muted-foreground">{{role}}</p>
                    <p class="text-sm leading-relaxed text-foreground/80">{{bio}}</p>
                    <div class="flex flex-wrap items-center justify-center gap-3 pt-3 border-t border-border/40 sm:justify-start">
                      <a href="{{cta_url}}" class="inline-flex items-center rounded-xl bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90">
                        {{cta_text}}
                      </a>
                      <span class="text-xs font-mono text-muted-foreground" dir="ltr">{{contact_email}}</span>
                    </div>
                  </div>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="pull-quote",
        title="نقل‌قول و پیام برجسته",
        description="نقل‌قول چشم‌نواز با گیومه بزرگ، خط حاشیه رنگی، متن پیام و مشخصات گوینده",
        category="محتوا",
        keywords=("quote", "pullquote", "نقل‌قول", "پیام", "برجسته", "سخن", "گیومه"),
        variables=(
            PatternVariable(
                "quote_text",
                "متن نقل‌قول",
                "سرمایه‌گذاری روی کیفیت و جلب رضایت مشتری، پایدارترین استراتژی برای تمایز و موفقیت در بازار رقابتی است.",
            ),
            PatternVariable("author_name", "نام گوینده", "سهراب رحمانی"),
            PatternVariable("author_title", "سمت یا جایگاه گوینده", "مدیر ارشد محصول"),
            PatternVariable("source_note", "منبع یا نام رویداد", "همایش سالانه نوآوری و تجارت دیجیتال"),
        ),
        html=_frag(
            """
            <figure class="relative my-8 overflow-hidden rounded-2xl border-r-4 border-primary bg-primary/5 p-6 shadow-sm md:p-8" dir="rtl">
              <div class="absolute -top-4 left-6 select-none font-serif text-8xl font-black text-primary/15 pointer-events-none" aria-hidden="true">
                ”
              </div>
              <blockquote class="relative z-10 text-lg font-medium leading-relaxed text-foreground md:text-xl md:leading-9">
                «{{quote_text}}»
              </blockquote>
              <figcaption class="relative z-10 mt-5 flex flex-wrap items-center gap-3 border-t border-primary/10 pt-4 text-sm">
                <span class="font-bold text-foreground">{{author_name}}</span>
                <span class="text-muted-foreground">·</span>
                <span class="text-muted-foreground">{{author_title}}</span>
                <span class="text-muted-foreground">·</span>
                <span class="rounded-md bg-background/80 px-2 py-0.5 text-xs font-medium text-primary">{{source_note}}</span>
              </figcaption>
            </figure>
            """
        ),
    ),
    BlockPattern(
        slug="support-callout",
        title="جعبه راهنما و مشاوره خرید",
        description="کادر مشاوره و راهنمای خرید با آیکون راهنما، توضیحات و دکمه‌های تماس و ارتباط",
        category="پشتیبانی و تماس",
        keywords=("support", "callout", "مشاوره", "پشتیبانی", "تماس", "راهنما", "گفتگو", "تلفن"),
        variables=(
            PatternVariable("title", "عنوان راهنما", "نیاز به مشاوره قبل از خرید دارید؟"),
            PatternVariable(
                "description",
                "متن راهنما",
                "کارشناسان فنی ما آماده پاسخگویی به تمامی سوالات شما و ارائه بهترین پیشنهاد متناسب با نیاز و بودجه‌تان هستند.",
            ),
            PatternVariable("icon", "آیکون یا نماد", "💬"),
            PatternVariable("badge_text", "برچسب وضعیت", "پاسخگویی سریع"),
            PatternVariable("phone_label", "عنوان تماس تلفنی", "تماس مستقیم:"),
            PatternVariable("phone_number", "شماره تماس", "۰۲۱-۸۸۸۸۹۹۹۹"),
            PatternVariable("phone_url", "لینک شماره تماس", "tel:02188889999"),
            PatternVariable("cta_text", "متن دکمه ارتباط آنلاین", "شروع گفتگوی آنلاین"),
            PatternVariable("cta_url", "لینک دکمه ارتباط", "/chat"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-primary/20 bg-gradient-to-l from-primary/10 via-card to-background p-6 shadow-sm md:p-8" dir="rtl">
              <div class="flex flex-col items-center justify-between gap-6 md:flex-row">
                <div class="flex items-start gap-4">
                  <div class="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-primary text-2xl text-primary-foreground shadow-md">
                    {{icon}}
                  </div>
                  <div class="space-y-1.5">
                    <div class="flex items-center gap-2">
                      <h3 class="text-xl font-bold text-foreground">{{title}}</h3>
                      <span class="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-600">{{badge_text}}</span>
                    </div>
                    <p class="max-w-xl text-sm leading-relaxed text-muted-foreground">{{description}}</p>
                  </div>
                </div>
                <div class="flex shrink-0 flex-wrap items-center gap-3">
                  <a href="{{phone_url}}" class="inline-flex items-center gap-2 rounded-xl border border-border/80 bg-background px-4 py-2.5 text-sm font-bold text-foreground transition hover:border-primary/50 hover:text-primary">
                    <span>📞</span>
                    <span>{{phone_label}}</span>
                    <span class="font-mono text-xs tabular-nums text-primary" dir="ltr">{{phone_number}}</span>
                  </a>
                  <a href="{{cta_url}}" class="inline-flex items-center rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-primary-foreground shadow transition hover:bg-primary/90">
                    {{cta_text}}
                  </a>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="comparison-table",
        title="جدول مقایسه محصولات و مشخصات",
        description="مقایسه ویژگی‌ها، مشخصات فنی و گارانتی کالاها در جدول ۳ ستونه با نشانگر تیک، ضربدر و دکمه خرید",
        category="قیمت‌گذاری و تعرفه",
        keywords=("مقایسه", "جدول", "مشخصات", "تفاوت", "بررسی", "انتخاب", "comparison", "specs"),
        variables=(
            PatternVariable("title", "عنوان بخش", "مقایسه مشخصات و ویژگی‌های فنی"),
            PatternVariable(
                "subtitle",
                "زیرعنوان",
                "تفاوت مدل‌های مختلف را به دقت بررسی کرده و متناسب‌ترین گزینه را انتخاب کنید",
            ),
            PatternVariable("col1_title", "عنوان ستون مشخصات", "ویژگی‌ها و قابلیت‌ها"),
            PatternVariable("col2_badge", "برچسب مدل پیشنهادی", "پیشنهاد ویژه"),
            PatternVariable("col2_name", "نام مدل ۲ (پیشنهادی)", "مدل پرو (Pro Edition)"),
            PatternVariable("col2_price", "قیمت مدل ۲", "۴,۸۵۰,۰۰۰ تومان"),
            PatternVariable("col2_cta", "متن دکمه مدل ۲", "خرید مدل پرو"),
            PatternVariable("col2_url", "لینک دکمه مدل ۲", "/products"),
            PatternVariable("col3_name", "نام مدل ۳ (استاندارد)", "مدل استاندارد (Standard)"),
            PatternVariable("col3_price", "قیمت مدل ۳", "۲,۹۰۰,۰۰۰ تومان"),
            PatternVariable("col3_cta", "متن دکمه مدل ۳", "مشاهده و خرید"),
            PatternVariable("col3_url", "لینک دکمه مدل ۳", "/products"),
            PatternVariable("f1_name", "ویژگی ۱", "گارانتی رسمی و خدمات پس از فروش"),
            PatternVariable("f1_v2", "مقدار ویژگی ۱ در مدل ۲", "۱۸ ماه تعویض فوری"),
            PatternVariable("f1_v3", "مقدار ویژگی ۱ در مدل ۳", "۱۲ ماه تعمیر رایگان"),
            PatternVariable("f2_name", "ویژگی ۲", "پشتیبانی فنی و مشاوره اختصاصی"),
            PatternVariable("f2_v2", "مقدار ویژگی ۲ در مدل ۲", "۲۴ ساعته (حتی تعطیلات)"),
            PatternVariable("f2_v3", "مقدار ویژگی ۲ در مدل ۳", "روزهای کاری ۹ الی ۱۷"),
            PatternVariable("f3_name", "ویژگی ۳", "ارسال اکسپرس و بیمه کالا"),
            PatternVariable("f3_v2", "مقدار ویژگی ۳ در مدل ۲", "رایگان با بیمه کامل"),
            PatternVariable("f3_v3", "مقدار ویژگی ۳ در مدل ۳", "ارسال عادی پستی"),
            PatternVariable("f4_name", "ویژگی ۴", "مهلت تست و عودت بی قید و شرط"),
            PatternVariable("f4_v2", "مقدار ویژگی ۴ در مدل ۲", "۱۴ روز تضمین کامل"),
            PatternVariable("f4_v3", "مقدار ویژگی ۴ در مدل ۳", "۷ روز کاری"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-border/80 bg-card p-6 shadow-sm md:p-8" dir="rtl">
              <div class="mb-8 text-center">
                <h3 class="text-2xl font-bold tracking-tight text-foreground md:text-3xl">{{title}}</h3>
                <p class="mt-2 text-sm text-muted-foreground md:text-base">{{subtitle}}</p>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full min-w-[600px] border-collapse text-right text-sm">
                  <thead>
                    <tr class="border-b border-border/80">
                      <th class="p-4 font-semibold text-muted-foreground w-2/5">{{col1_title}}</th>
                      <th class="p-4 text-center w-3/10 bg-primary/5 rounded-t-xl border-x border-t border-primary/20">
                        <span class="inline-block rounded-full bg-primary/20 px-2.5 py-0.5 text-xs font-bold text-primary mb-1">{{col2_badge}}</span>
                        <div class="font-bold text-foreground text-base">{{col2_name}}</div>
                        <div class="mt-1 font-bold text-primary text-lg">{{col2_price}}</div>
                      </th>
                      <th class="p-4 text-center w-3/10">
                        <div class="font-bold text-foreground text-base">{{col3_name}}</div>
                        <div class="mt-1 font-semibold text-muted-foreground text-base">{{col3_price}}</div>
                      </th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-border/60">
                    <tr class="hover:bg-muted/30">
                      <td class="p-4 font-medium text-foreground">{{f1_name}}</td>
                      <td class="p-4 text-center font-bold text-emerald-600 bg-primary/5 border-x border-primary/20">✓ {{f1_v2}}</td>
                      <td class="p-4 text-center text-muted-foreground">{{f1_v3}}</td>
                    </tr>
                    <tr class="hover:bg-muted/30">
                      <td class="p-4 font-medium text-foreground">{{f2_name}}</td>
                      <td class="p-4 text-center font-bold text-emerald-600 bg-primary/5 border-x border-primary/20">✓ {{f2_v2}}</td>
                      <td class="p-4 text-center text-muted-foreground">{{f2_v3}}</td>
                    </tr>
                    <tr class="hover:bg-muted/30">
                      <td class="p-4 font-medium text-foreground">{{f3_name}}</td>
                      <td class="p-4 text-center font-bold text-emerald-600 bg-primary/5 border-x border-primary/20">✓ {{f3_v2}}</td>
                      <td class="p-4 text-center text-muted-foreground">{{f3_v3}}</td>
                    </tr>
                    <tr class="hover:bg-muted/30">
                      <td class="p-4 font-medium text-foreground">{{f4_name}}</td>
                      <td class="p-4 text-center font-bold text-emerald-600 bg-primary/5 border-x border-primary/20">✓ {{f4_v2}}</td>
                      <td class="p-4 text-center text-muted-foreground">{{f4_v3}}</td>
                    </tr>
                  </tbody>
                  <tfoot>
                    <tr class="border-t border-border">
                      <td class="p-4"></td>
                      <td class="p-4 text-center bg-primary/5 rounded-b-xl border-x border-b border-primary/20">
                        <a href="{{col2_url}}" class="inline-flex w-full items-center justify-center rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-primary-foreground shadow transition hover:bg-primary/90">
                          {{col2_cta}}
                        </a>
                      </td>
                      <td class="p-4 text-center">
                        <a href="{{col3_url}}" class="inline-flex w-full items-center justify-center rounded-xl border border-border bg-background px-4 py-2.5 text-sm font-semibold text-foreground transition hover:border-primary/50 hover:text-primary">
                          {{col3_cta}}
                        </a>
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="process-steps",
        title="مراحل گام‌به‌گام خرید و تحویل",
        description="نمایش ۴ گام شفاف فرآیند ثبت سفارش تا تحویل کالا با شماره فارسی، آیکون و کادرهای مدرن",
        category="محتوا",
        keywords=("مراحل", "گام", "خرید", "ارسال", "تحویل", "فرایند", "process", "steps", "timeline"),
        variables=(
            PatternVariable("title", "عنوان بخش", "سفارش تا تحویل در ۴ مرحله آسان"),
            PatternVariable(
                "subtitle",
                "زیرعنوان",
                "تجربه خریدی لذت‌بخش، شفاف و بدون دغدغه از ثبت تا دریافت سفارش",
            ),
            PatternVariable("s1_num", "شماره گام ۱", "۱"),
            PatternVariable("s1_title", "عنوان گام ۱", "انتخاب هوشمند کالا"),
            PatternVariable("s1_desc", "توضیح گام ۱", "بررسی نقد و مشخصات فنی کالاها و انتخاب بهترین گزینه"),
            PatternVariable("s2_num", "شماره گام ۲", "۲"),
            PatternVariable("s2_title", "عنوان گام ۲", "پرداخت امن شتابی"),
            PatternVariable("s2_desc", "توضیح گام ۲", "تسویه از طریق درگاه‌های امن شاپرک با کلیه کارت‌های بانکی"),
            PatternVariable("s3_num", "شماره گام ۳", "۳"),
            PatternVariable("s3_title", "عنوان گام ۳", "بسته‌بندی ایمن و تست"),
            PatternVariable("s3_desc", "توضیح گام ۳", "کنترل سلامت فیزیکی و آماده‌سازی در کارتن‌های ضربه‌گیر استاندارد"),
            PatternVariable("s4_num", "شماره گام ۴", "۴"),
            PatternVariable("s4_title", "عنوان گام ۴", "تحویل اکسپرس درب منزل"),
            PatternVariable("s4_desc", "توضیح گام ۴", "ارسال سریع با کد رهگیری پیامکی پستی تا زمان تحویل"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-border/70 bg-gradient-to-b from-card to-background p-6 shadow-sm md:p-10" dir="rtl">
              <div class="mb-10 text-center">
                <h3 class="text-2xl font-bold tracking-tight text-foreground md:text-3xl">{{title}}</h3>
                <p class="mt-2 text-sm text-muted-foreground md:text-base">{{subtitle}}</p>
              </div>
              <div class="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
                <div class="relative rounded-xl border border-border/80 bg-card p-5 transition hover:border-primary/50 hover:shadow-md">
                  <div class="flex items-center justify-between mb-4">
                    <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 font-mono text-lg font-bold text-primary">{{s1_num}}</span>
                    <span class="text-xl">🔍</span>
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{s1_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{s1_desc}}</p>
                </div>
                <div class="relative rounded-xl border border-border/80 bg-card p-5 transition hover:border-primary/50 hover:shadow-md">
                  <div class="flex items-center justify-between mb-4">
                    <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 font-mono text-lg font-bold text-primary">{{s2_num}}</span>
                    <span class="text-xl">💳</span>
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{s2_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{s2_desc}}</p>
                </div>
                <div class="relative rounded-xl border border-border/80 bg-card p-5 transition hover:border-primary/50 hover:shadow-md">
                  <div class="flex items-center justify-between mb-4">
                    <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 font-mono text-lg font-bold text-primary">{{s3_num}}</span>
                    <span class="text-xl">📦</span>
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{s3_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{s3_desc}}</p>
                </div>
                <div class="relative rounded-xl border border-border/80 bg-card p-5 transition hover:border-primary/50 hover:shadow-md">
                  <div class="flex items-center justify-between mb-4">
                    <span class="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 font-mono text-lg font-bold text-emerald-600">{{s4_num}}</span>
                    <span class="text-xl">🚀</span>
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{s4_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{s4_desc}}</p>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="lead-capture-form",
        title="فرم درخواست مشاوره تلفنی و تماس فوری",
        description="باکس شکیل ثبت نام و شماره موبایل جهت تماس رایگان کارشناس در کمتر از ۱۵ دقیقه",
        category="پشتیبانی و تماس",
        keywords=("مشاوره", "تماس", "فرم", "لید", "شماره", "کارشناس", "lead", "form", "contact"),
        variables=(
            PatternVariable("title", "عنوان فرم", "درخواست مشاوره رایگان خرید"),
            PatternVariable(
                "subtitle",
                "زیرعنوان",
                "شماره همراه خود را وارد کنید تا کارشناسان فنی ما در کمتر از ۱۵ دقیقه با شما تماس بگیرند.",
            ),
            PatternVariable("badge_text", "برچسب اطمینان", "پاسخگویی در کمتر از ۱۵ دقیقه"),
            PatternVariable("name_placeholder", "متن راهنمای فیلد نام", "نام و نام خانوادگی"),
            PatternVariable("phone_placeholder", "متن راهنمای شماره تماس", "شماره همراه (مثلاً ۰۹۱۲۳۴۵۶۷۸۹)"),
            PatternVariable("topic_placeholder", "موضوع یا کالای مورد نظر", "کالا یا موضوع مشاوره مورد نظر"),
            PatternVariable("button_text", "متن دکمه ارسال", "درخواست تماس رایگان کارشناس"),
            PatternVariable("privacy_note", "پیام حریم خصوصی", "اطلاعات تماس شما نزد ما کاملاً محفوظ است و صرفاً جهت مشاوره استفاده می‌شود."),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-primary/25 bg-gradient-to-br from-card via-card to-primary/5 p-6 shadow-sm md:p-10" dir="rtl">
              <div class="mx-auto max-w-2xl text-center">
                <span class="inline-block rounded-full bg-primary/15 px-3 py-1 text-xs font-bold text-primary mb-3">{{badge_text}}</span>
                <h3 class="text-2xl font-bold tracking-tight text-foreground md:text-3xl">{{title}}</h3>
                <p class="mt-2 text-sm text-muted-foreground">{{subtitle}}</p>
                <form class="mt-8 space-y-4" onsubmit="event.preventDefault(); alert('درخواست مشاوره شما با موفقیت ثبت شد.');">
                  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <input type="text" placeholder="{{name_placeholder}}" required class="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
                    <input type="tel" dir="ltr" placeholder="{{phone_placeholder}}" required class="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
                  </div>
                  <input type="text" placeholder="{{topic_placeholder}}" class="w-full rounded-xl border border-border bg-background px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20" />
                  <button type="submit" class="w-full rounded-xl bg-primary px-6 py-3.5 text-base font-bold text-primary-foreground shadow-md transition hover:bg-primary/90 focus:outline-none">
                    {{button_text}}
                  </button>
                  <p class="text-xs text-muted-foreground text-center mt-3">🔒 {{privacy_note}}</p>
                </form>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="alert-banner",
        title="نوار اعلان و هشدار مهم فروشگاه",
        description="کادر اطلاعیه با استایل ویژه کهربایی/سبز، برچسب فوری، متن راهنما و دکمه مشاهده جزییات",
        category="فروش و تخفیف",
        keywords=("اعلان", "هشدار", "اطلاعیه", "خبر", "توجه", "alert", "notice", "announcement"),
        variables=(
            PatternVariable("icon", "آیکون یا ایموجی", "📢"),
            PatternVariable("badge", "برچسب وضعیت", "اطلاعیه مهم"),
            PatternVariable("title", "عنوان اطلاعیه", "آغاز جشنواره شگفت‌انگیز پاییزه"),
            PatternVariable(
                "description",
                "متن اعلان",
                "ارسال رایگان برای تمام سفارش‌های بالای ۵۰۰ هزار تومان و تخفیف ویژه تا ۴۰٪ روی اقلام منتخب تا پایان هفته فعال شد.",
            ),
            PatternVariable("cta_text", "متن دکمه پیگیری", "مشاهده تخفیف‌ها"),
            PatternVariable("cta_url", "لینک دکمه", "/search?sale=true"),
        ),
        html=_frag(
            """
            <aside class="rounded-2xl border border-amber-500/30 bg-gradient-to-r from-amber-500/10 via-card to-background p-5 shadow-sm md:p-6" dir="rtl" role="alert">
              <div class="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
                <div class="flex items-center gap-3.5">
                  <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-xl">{{icon}}</span>
                  <div>
                    <div class="flex items-center gap-2">
                      <span class="rounded bg-amber-500/20 px-2 py-0.5 text-xs font-bold text-amber-700 dark:text-amber-400">{{badge}}</span>
                      <h4 class="font-bold text-foreground text-base">{{title}}</h4>
                    </div>
                    <p class="mt-1 text-xs text-muted-foreground md:text-sm">{{description}}</p>
                  </div>
                </div>
                <a href="{{cta_url}}" class="inline-flex shrink-0 items-center gap-2 rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-amber-700 md:text-sm">
                  <span>{{cta_text}}</span>
                  <span>←</span>
                </a>
              </div>
            </aside>
            """
        ),
    ),
    BlockPattern(
        slug="floating-contact-bar",
        title="نوار ارتباط سریع و شبکه‌های اجتماعی",
        description="ردیف دکمه‌های تماس تلفنی، واتساپ، تلگرام، بله و ایتا با نشانگر پاسخگویی آنلاین",
        category="پشتیبانی و تماس",
        keywords=("تماس", "ارتباط", "واتساپ", "تلگرام", "ایتا", "بله", "پشتیبانی", "contact", "social"),
        variables=(
            PatternVariable("heading", "عنوان نوار", "راه‌های ارتباطی سریع با پشتیبانی"),
            PatternVariable("status_text", "متن وضعیت آنلاین", "پاسخگویی آنلاین کارشناسان"),
            PatternVariable("phone_label", "عنوان تلفن", "تلفن پشتیبانی"),
            PatternVariable("phone_num", "شماره تماس", "۰۲۱-۸۸۸۸۹۹۹۹"),
            PatternVariable("phone_url", "لینک شماره", "tel:02188889999"),
            PatternVariable("whatsapp_label", "برچسب واتساپ", "واتساپ"),
            PatternVariable("whatsapp_url", "لینک واتساپ", "https://wa.me/989120000000"),
            PatternVariable("telegram_label", "برچسب تلگرام", "تلگرام"),
            PatternVariable("telegram_url", "لینک تلگرام", "https://t.me/store_support"),
            PatternVariable("eitaa_label", "برچسب ایتا", "ایتا"),
            PatternVariable("eitaa_url", "لینک ایتا", "https://eitaa.com/store_support"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-border bg-card p-5 shadow-sm md:p-6" dir="rtl">
              <div class="flex flex-col items-center justify-between gap-4 md:flex-row">
                <div class="flex items-center gap-3">
                  <span class="relative flex h-3 w-3">
                    <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                    <span class="relative inline-flex h-3 w-3 rounded-full bg-emerald-500"></span>
                  </span>
                  <div>
                    <h4 class="font-bold text-foreground text-sm md:text-base">{{heading}}</h4>
                    <span class="text-xs text-muted-foreground">{{status_text}}</span>
                  </div>
                </div>
                <div class="flex flex-wrap items-center justify-center gap-2.5">
                  <a href="{{phone_url}}" class="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background px-3.5 py-2 text-xs font-bold text-foreground transition hover:border-primary hover:text-primary">
                    <span>📞</span>
                    <span>{{phone_label}}:</span>
                    <span class="font-mono" dir="ltr">{{phone_num}}</span>
                  </a>
                  <a href="{{whatsapp_url}}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-emerald-700">
                    <span>💬</span>
                    <span>{{whatsapp_label}}</span>
                  </a>
                  <a href="{{telegram_url}}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 rounded-xl bg-sky-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-sky-700">
                    <span>✈️</span>
                    <span>{{telegram_label}}</span>
                  </a>
                  <a href="{{eitaa_url}}" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1.5 rounded-xl bg-orange-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-orange-700">
                    <span>📱</span>
                    <span>{{eitaa_label}}</span>
                  </a>
                </div>
              </div>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="brand-logo-carousel",
        title="ردیف برندهای همکار و نمادهای اعتماد",
        description="شبکه نمایش لوگوی برندهای معتبر همکار، اصالت کالا و نمادهای اعتماد الکترونیکی",
        category="اعتماد و بازخورد",
        keywords=("برند", "لوگو", "همکاران", "نماد", "اعتماد", "اینماد", "partners", "brands", "logos"),
        variables=(
            PatternVariable("title", "عنوان بخش", "برندهای معتبر و شرکای تجاری رسمی"),
            PatternVariable("subtitle", "زیرعنوان", "تضمین اصالت و سلامت کلیه محصولات با همکاری مستقیم برترین سازندگان"),
            PatternVariable("b1", "نام برند ۱", "سامسونگ (Samsung)"),
            PatternVariable("b2", "نام برند ۲", "اپل (Apple)"),
            PatternVariable("b3", "نام برند ۳", "شیائومی (Xiaomi)"),
            PatternVariable("b4", "نام برند ۴", "ایسوس (ASUS)"),
            PatternVariable("b5", "نام برند ۵", "لنوو (Lenovo)"),
            PatternVariable("b6", "نام برند ۶", "سونی (Sony)"),
            PatternVariable("trust_badge", "متن نماد اعتماد", "دارای نماد اعتماد الکترونیکی ۵ ستاره و عضو اتحادیه کشوری کسب‌وکارهای مجازی"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-border/80 bg-card/60 p-6 shadow-sm md:p-8" dir="rtl">
              <div class="mb-6 text-center">
                <h3 class="text-xl font-bold tracking-tight text-foreground md:text-2xl">{{title}}</h3>
                <p class="mt-1 text-xs text-muted-foreground md:text-sm">{{subtitle}}</p>
              </div>
              <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-6">
                <div class="flex h-16 items-center justify-center rounded-xl border border-border/60 bg-background/80 p-3 text-center text-xs font-bold text-muted-foreground transition hover:border-primary hover:text-foreground">
                  {{b1}}
                </div>
                <div class="flex h-16 items-center justify-center rounded-xl border border-border/60 bg-background/80 p-3 text-center text-xs font-bold text-muted-foreground transition hover:border-primary hover:text-foreground">
                  {{b2}}
                </div>
                <div class="flex h-16 items-center justify-center rounded-xl border border-border/60 bg-background/80 p-3 text-center text-xs font-bold text-muted-foreground transition hover:border-primary hover:text-foreground">
                  {{b3}}
                </div>
                <div class="flex h-16 items-center justify-center rounded-xl border border-border/60 bg-background/80 p-3 text-center text-xs font-bold text-muted-foreground transition hover:border-primary hover:text-foreground">
                  {{b4}}
                </div>
                <div class="flex h-16 items-center justify-center rounded-xl border border-border/60 bg-background/80 p-3 text-center text-xs font-bold text-muted-foreground transition hover:border-primary hover:text-foreground">
                  {{b5}}
                </div>
                <div class="flex h-16 items-center justify-center rounded-xl border border-border/60 bg-background/80 p-3 text-center text-xs font-bold text-muted-foreground transition hover:border-primary hover:text-foreground">
                  {{b6}}
                </div>
              </div>
              <p class="mt-5 text-center text-xs text-muted-foreground">🏅 {{trust_badge}}</p>
            </section>
            """
        ),
    ),
    BlockPattern(
        slug="product-highlights",
        title="مزایای کلیدی و برتری‌های کالا",
        description="۳ کارت گرادیان با آیکون‌های بولت‌دار و توضیحات فنی برای صفحات تک‌محصول و لندینگ",
        category="محصولات",
        keywords=("مزایا", "ویژگی", "برتری", "برجسته", "گارانتی", "highlights", "features", "advantages"),
        variables=(
            PatternVariable("title", "عنوان مزایا", "چرا این محصول ارزش خرید بالایی دارد؟"),
            PatternVariable(
                "subtitle",
                "زیرعنوان",
                "۳ ویژگی متمایزکننده که این کالا را در بین گزینه‌های موجود بی‌رقیب می‌سازد",
            ),
            PatternVariable("c1_icon", "آیکون کارت ۱", "🛡️"),
            PatternVariable("c1_title", "عنوان کارت ۱", "ضمانت اصالت ۱۰۰٪ فیزیکی"),
            PatternVariable("c1_desc", "توضیح کارت ۱", "تضمین کتبی اصالت کالا همراه با هولوگرام معتبر شرکتی و ثبت در سامانه جامع تجارت"),
            PatternVariable("c2_icon", "آیکون کارت ۲", "🔄"),
            PatternVariable("c2_title", "عنوان کارت ۲", "۷ روز مهلت تست و بازگشت"),
            PatternVariable("c2_desc", "توضیح کارت ۲", "امکان بازگشت کالا بدون قید و شرط و استرداد کامل وجه در صورت عدم رضایت"),
            PatternVariable("c3_icon", "آیکون کارت ۳", "⚡"),
            PatternVariable("c3_title", "عنوان کارت ۳", "پشتیبانی فنی و نصب رایگان"),
            PatternVariable("c3_desc", "توضیح کارت ۳", "راهنمایی تخصصی و تنظیمات اولیه توسط تیم کارشناسان فنی مجرب فروشگاه"),
        ),
        html=_frag(
            """
            <section class="rounded-2xl border border-border/70 bg-gradient-to-l from-primary/5 via-card to-background p-6 shadow-sm md:p-8" dir="rtl">
              <div class="mb-8 text-center">
                <h3 class="text-2xl font-bold tracking-tight text-foreground md:text-3xl">{{title}}</h3>
                <p class="mt-2 text-sm text-muted-foreground md:text-base">{{subtitle}}</p>
              </div>
              <div class="grid grid-cols-1 gap-6 md:grid-cols-3">
                <div class="rounded-xl border border-border/80 bg-background/90 p-5 shadow-sm transition hover:border-primary/50 hover:shadow-md">
                  <div class="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-2xl">
                    {{c1_icon}}
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{c1_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{c1_desc}}</p>
                </div>
                <div class="rounded-xl border border-border/80 bg-background/90 p-5 shadow-sm transition hover:border-primary/50 hover:shadow-md">
                  <div class="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-2xl">
                    {{c2_icon}}
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{c2_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{c2_desc}}</p>
                </div>
                <div class="rounded-xl border border-border/80 bg-background/90 p-5 shadow-sm transition hover:border-primary/50 hover:shadow-md">
                  <div class="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-2xl">
                    {{c3_icon}}
                  </div>
                  <h4 class="text-base font-bold text-foreground">{{c3_title}}</h4>
                  <p class="mt-2 text-xs leading-relaxed text-muted-foreground">{{c3_desc}}</p>
                </div>
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
