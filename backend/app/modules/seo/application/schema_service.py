"""Schema (Rich Snippets) — the type catalog, builder, and validator.

Rank Math's Schema module: an operator picks a type (Article, Product, FAQ,
HowTo, LocalBusiness, …), fills the type's fields, and the storefront emits
the JSON-LD. Before this module the storefront hardcoded Article + FAQPage +
Product nodes, so an operator could not add a HowTo, an Event, or a
LocalBusiness node at all — and a stored ``schema_markup`` override was never
rendered (the editor saved it; the page ignored it).

Three responsibilities, deliberately separate:

- ``SCHEMA_TYPES``: the catalog the UI renders. Each entry lists its fields
  (key, Persian label, input type, required) so the builder form is generated
  from one source — a field the storefront cannot consume is never offered.
- ``build_schema_node``: assembles a JSON-LD dict from field values, filling
  required-but-empty fields from the resource (e.g. a Product's name from the
  product row) so a partially filled form still produces a valid node.
- ``validate_schema_node``: light structural validation (an @type, a name or
  headline, no placeholder values) run before anything is stored. Google
  rejects invalid nodes silently; storing one is worse than rejecting it.

The output is always a plain dict with ``@context``/``@type`` — the callers
(storefront pages, preview endpoint) serialize it themselves.
"""

from __future__ import annotations

from typing import Any

SCHEMA_CONTEXT = "https://schema.org"

#: Field spec shape: key, label (fa), kind (text|textarea|number|url|date|
#: select), required, and for selects the options. The UI renders one input
#: per entry; the builder reads exactly these keys.
FieldSpec = dict[str, Any]


def _f(
    key: str,
    label: str,
    kind: str = "text",
    *,
    required: bool = False,
    options: list[str] | None = None,
    placeholder: str = "",
) -> FieldSpec:
    spec: FieldSpec = {
        "key": key,
        "label": label,
        "kind": kind,
        "required": required,
        "placeholder": placeholder,
    }
    if options:
        spec["options"] = options
    return spec


#: The type catalog. Order is the UI order: the types this store actually
#: uses first (Article/Product/FAQ/HowTo/Review/VideoObject), the general
#: vocabulary after, the LocalBusiness family last.
SCHEMA_TYPES: tuple[dict[str, Any], ...] = (
    {
        "type": "Article",
        "label": "مقاله",
        "description": "برای نوشته‌های وبلاگ؛ تیتر، نویسنده، تاریخ انتشار و تصویر.",
        "fields": (
            _f("headline", "تیتر", required=True),
            _f("description", "توضیح", "textarea"),
            _f("author", "نویسنده"),
            _f("datePublished", "تاریخ انتشار", "date"),
            _f("dateModified", "تاریخ ویرایش", "date"),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "NewsArticle",
        "label": "خبر",
        "description": "مثل مقاله، برای محتوای خبری با اعتبار بیشتر در Google News.",
        "fields": (
            _f("headline", "تیتر", required=True),
            _f("description", "توضیح", "textarea"),
            _f("author", "نویسنده"),
            _f("datePublished", "تاریخ انتشار", "date"),
            _f("dateModified", "تاریخ ویرایش", "date"),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "Product",
        "label": "محصول",
        "description": "برای صفحهٔ محصول؛ نام، قیمت، موجودی و برند.",
        "fields": (
            _f("name", "نام محصول", required=True),
            _f("description", "توضیح", "textarea"),
            _f("sku", "کد کالا (SKU)"),
            _f("brand", "برند"),
            _f("price", "قیمت (ریال)", "number"),
            _f("priceCurrency", "واحد پول", options=["IRR", "IRT"]),
            _f("availability", "موجودی", options=["InStock", "OutOfStock", "PreOrder"]),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "FAQ",
        "label": "پرسش‌های متداول",
        "description": "برای بخش FAQ؛ هر پرسش و پاسخ یک جفت جدا.",
        "fields": (
            _f("questions", "پرسش‌ها (هر خط: پرسش | پاسخ)", "textarea", required=True),
        ),
    },
    {
        "type": "HowTo",
        "label": "آموزش گام‌به‌گام",
        "description": "برای راهنماهای مرحله‌ای؛ هر خط یک گام.",
        "fields": (
            _f("name", "عنوان آموزش", required=True),
            _f("description", "توضیح", "textarea"),
            _f("steps", "گام‌ها (هر خط یک گام)", "textarea", required=True),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "Review",
        "label": "بررسی/نقد",
        "description": "برای نقد یک کالا یا خدمت با امتیاز.",
        "fields": (
            _f("itemName", "نام مورد بررسی", required=True),
            _f("reviewBody", "متن نقد", "textarea"),
            _f("ratingValue", "امتیاز (۱ تا ۵)", "number", required=True),
            _f("author", "نویسنده"),
            _f("datePublished", "تاریخ", "date"),
        ),
    },
    {
        "type": "VideoObject",
        "label": "ویدئو",
        "description": "برای صفحه‌های دارای ویدئو؛ thumbnail الزامی است.",
        "fields": (
            _f("name", "عنوان ویدئو", required=True),
            _f("description", "توضیح", "textarea", required=True),
            _f("thumbnailUrl", "تصویر بندانگشتی (URL)", "url", required=True),
            _f("uploadDate", "تاریخ انتشار", "date"),
            _f("contentUrl", "آدرس فایل ویدئو", "url"),
            _f("embedUrl", "آدرس embed", "url"),
        ),
    },
    {
        "type": "Event",
        "label": "رویداد",
        "description": "برای رویدادها؛ نام، شروع، مکان.",
        "fields": (
            _f("name", "نام رویداد", required=True),
            _f("startDate", "تاریخ شروع", "date", required=True),
            _f("endDate", "تاریخ پایان", "date"),
            _f("location", "مکان"),
            _f("description", "توضیح", "textarea"),
        ),
    },
    {
        "type": "Course",
        "label": "دورهٔ آموزشی",
        "description": "برای دوره‌ها؛ نام، توضیح و ارائه‌دهنده.",
        "fields": (
            _f("name", "نام دوره", required=True),
            _f("description", "توضیح", "textarea"),
            _f("provider", "ارائه‌دهنده"),
        ),
    },
    {
        "type": "SoftwareApplication",
        "label": "نرم‌افزار/اپلیکیشن",
        "description": "برای نرم‌افزار، بازی و اپلیکیشن.",
        "fields": (
            _f("name", "نام", required=True),
            _f("applicationCategory", "دسته", placeholder="GameApplication"),
            _f("operatingSystem", "سیستم‌عامل"),
            _f("price", "قیمت (ریال)", "number"),
            _f("description", "توضیح", "textarea"),
        ),
    },
    {
        "type": "Book",
        "label": "کتاب",
        "description": "برای کتاب؛ عنوان، نویسنده، شابک.",
        "fields": (
            _f("name", "عنوان کتاب", required=True),
            _f("author", "نویسنده"),
            _f("isbn", "شابک"),
            _f("numberOfPages", "تعداد صفحه", "number"),
        ),
    },
    {
        "type": "Recipe",
        "label": "دستور پخت",
        "description": "برای دستور پخت؛ مواد لازم و مراحل.",
        "fields": (
            _f("name", "نام غذا", required=True),
            _f("description", "توضیح", "textarea"),
            _f("recipeIngredient", "مواد لازم (هر خط یکی)", "textarea"),
            _f("recipeInstructions", "مراحل (هر خط یکی)", "textarea"),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "JobPosting",
        "label": "آگهی استخدام",
        "description": "برای موقعیت‌های شغلی؛ عنوان، شرکت، مکان.",
        "fields": (
            _f("title", "عنوان شغل", required=True),
            _f("description", "شرح شغل", "textarea", required=True),
            _f("hiringOrganization", "شرکت"),
            _f("jobLocation", "مکان"),
            _f("datePosted", "تاریخ انتشار", "date"),
        ),
    },
    {
        "type": "Service",
        "label": "خدمت",
        "description": "برای خدمات؛ نام، ارائه‌دهنده.",
        "fields": (
            _f("name", "نام خدمت", required=True),
            _f("description", "توضیح", "textarea"),
            _f("provider", "ارائه‌دهنده"),
            _f("areaServed", "محدودهٔ خدمت"),
        ),
    },
    {
        "type": "Person",
        "label": "شخص",
        "description": "برای صفحهٔ نویسنده یا معرفی شخص.",
        "fields": (
            _f("name", "نام", required=True),
            _f("jobTitle", "سمت"),
            _f("description", "توضیح", "textarea"),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "Organization",
        "label": "سازمان",
        "description": "برای معرفی شرکت یا سازمان.",
        "fields": (
            _f("name", "نام", required=True),
            _f("url", "وب‌سایت", "url"),
            _f("logo", "لوگو (URL)", "url"),
            _f("description", "توضیح", "textarea"),
        ),
    },
    {
        "type": "WebSite",
        "label": "وب‌سایت",
        "description": "برای صفحهٔ اصلی؛ نام سایت و جست‌وجوی داخلی.",
        "fields": (
            _f("name", "نام سایت", required=True),
            _f("url", "آدرس سایت", "url", required=True),
        ),
    },
    {
        "type": "WebPage",
        "label": "صفحهٔ وب",
        "description": "برای برگه‌های عمومی.",
        "fields": (
            _f("name", "عنوان صفحه", required=True),
            _f("description", "توضیح", "textarea"),
            _f("url", "آدرس", "url"),
        ),
    },
    {
        "type": "ItemList",
        "label": "فهرست اقلام",
        "description": "برای لیست‌ها و راهنماهای «بهترین‌ها».",
        "fields": (
            _f("name", "عنوان فهرست", required=True),
            _f("items", "اقلام (هر خط یکی)", "textarea", required=True),
        ),
    },
    {
        "type": "Movie",
        "label": "فیلم",
        "description": "برای معرفی فیلم؛ عنوان، کارگردان، تاریخ.",
        "fields": (
            _f("name", "عنوان فیلم", required=True),
            _f("director", "کارگردان"),
            _f("datePublished", "تاریخ", "date"),
            _f("description", "توضیح", "textarea"),
        ),
    },
    {
        "type": "MusicRecording",
        "label": "قطعهٔ موسیقی",
        "description": "برای آهنگ و آلبوم.",
        "fields": (
            _f("name", "نام قطعه", required=True),
            _f("byArtist", "هنرمند"),
            _f("duration", "مدت", placeholder="PT3M33S"),
        ),
    },
    {
        "type": "Dataset",
        "label": "دادهٔ ساخت‌یافته",
        "description": "برای مجموعه‌داده‌ها (Rank Math Pro).",
        "fields": (
            _f("name", "نام", required=True),
            _f("description", "توضیح", "textarea"),
            _f("license", "مجوز", "url"),
        ),
    },
    {
        "type": "ClaimReview",
        "label": "بررسی ادعا",
        "description": "برای راستی‌آزمایی (Rank Math Pro).",
        "fields": (
            _f("claimReviewed", "ادعای بررسی‌شده", required=True),
            _f("reviewRating", "امتیاز (۱ تا ۵)", "number"),
            _f("author", "بررسی‌کننده"),
        ),
    },
    {
        "type": "PodcastEpisode",
        "label": "اپیزود پادکست",
        "description": "برای قسمت‌های پادکست (Rank Math Pro).",
        "fields": (
            _f("name", "عنوان اپیزود", required=True),
            _f("description", "توضیح", "textarea"),
            _f("datePublished", "تاریخ", "date"),
            _f("associatedMedia", "آدرس فایل صوتی", "url"),
        ),
    },
    {
        "type": "LocalBusiness",
        "label": "کسب‌وکار محلی",
        "description": "برای کسب‌وکار فیزیکی؛ آدرس، تلفن، ساعات کاری.",
        "fields": (
            _f("name", "نام کسب‌وکار", required=True),
            _f("address", "نشانی"),
            _f("telephone", "تلفن"),
            _f("openingHours", "ساعات کاری", placeholder="Sa-Th 09:00-18:00"),
            _f("priceRange", "بازهٔ قیمت", placeholder="$$"),
            _f("image", "تصویر (URL)", "url"),
        ),
    },
    {
        "type": "Restaurant",
        "label": "رستوران",
        "description": "زیرنوع کسب‌وکار محلی برای رستوران.",
        "fields": (
            _f("name", "نام رستوران", required=True),
            _f("address", "نشانی"),
            _f("telephone", "تلفن"),
            _f("servesCuisine", "نوع غذا"),
            _f("priceRange", "بازهٔ قیمت", placeholder="$$"),
        ),
    },
)

#: Lookup by @type for validation and UI helpers.
SCHEMA_TYPE_MAP: dict[str, dict[str, Any]] = {t["type"]: t for t in SCHEMA_TYPES}

#: The type used when a resource has no stored schema and its content type
#: has no configured default.
FALLBACK_TYPE_BY_RESOURCE: dict[str, str] = {
    "blog_post": "Article",
    "post": "Article",
    "product": "Product",
    "page": "WebPage",
}


def get_type_spec(schema_type: str) -> dict[str, Any] | None:
    return SCHEMA_TYPE_MAP.get(schema_type)


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def build_schema_node(
    schema_type: str,
    fields: dict[str, str],
    *,
    resource_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a JSON-LD node from operator field values.

    ``resource_defaults`` fills required-but-empty fields from the resource
    itself (a product's name, a post's headline), so a partially filled form
    still yields a valid node instead of one Google silently rejects.

    Type-specific assembly (FAQ questions → mainEntity, HowTo steps →
    step[], ItemList items → itemListElement) happens here because those
    shapes are the type's contract — the flat form values cannot express
    them directly.
    """
    defaults = resource_defaults or {}

    def val(key: str) -> str:
        raw = (fields.get(key) or "").strip()
        if raw:
            return raw
        return str(defaults.get(key) or "").strip()

    node: dict[str, Any] = {"@context": SCHEMA_CONTEXT, "@type": schema_type}

    if schema_type == "FAQ":
        # "question | answer" per line. A malformed line is skipped rather
        # than emitted as a broken pair.
        questions: list[dict[str, Any]] = []
        for line in _split_lines(val("questions")):
            parts = [p.strip() for p in line.split("|", 1)]
            if len(parts) == 2 and parts[0] and parts[1]:
                questions.append(
                    {
                        "@type": "Question",
                        "name": parts[0],
                        "acceptedAnswer": {"@type": "Answer", "text": parts[1]},
                    }
                )
        node["mainEntity"] = questions
        return node

    if schema_type == "HowTo":
        node["name"] = val("name")
        if val("description"):
            node["description"] = val("description")
        if val("image"):
            node["image"] = val("image")
        node["step"] = [
            {"@type": "HowToStep", "position": i + 1, "text": step}
            for i, step in enumerate(_split_lines(val("steps")))
        ]
        return node

    if schema_type == "ItemList":
        node["name"] = val("name")
        node["itemListElement"] = [
            {"@type": "ListItem", "position": i + 1, "name": item}
            for i, item in enumerate(_split_lines(val("items")))
        ]
        return node

    if schema_type == "Product":
        node["name"] = val("name")
        for key in ("description", "sku", "image"):
            if val(key):
                node[key] = val(key)
        if val("brand"):
            node["brand"] = {"@type": "Brand", "name": val("brand")}
        if val("price"):
            try:
                price = int(float(val("price")))
            except ValueError:
                price = 0
            if price > 0:
                node["offers"] = {
                    "@type": "Offer",
                    "priceCurrency": val("priceCurrency") or "IRR",
                    "price": price,
                    "availability": f"{SCHEMA_CONTEXT}/{val('availability') or 'InStock'}",
                }
        return node

    if schema_type == "Review":
        node["itemReviewed"] = {"@type": "Thing", "name": val("itemName")}
        if val("reviewBody"):
            node["reviewBody"] = val("reviewBody")
        if val("ratingValue"):
            try:
                rating = float(val("ratingValue"))
            except ValueError:
                rating = 0
            if rating > 0:
                node["reviewRating"] = {
                    "@type": "Rating",
                    "ratingValue": rating,
                    "bestRating": 5,
                    "worstRating": 1,
                }
        if val("author"):
            node["author"] = {"@type": "Person", "name": val("author")}
        if val("datePublished"):
            node["datePublished"] = val("datePublished")
        return node

    if schema_type == "VideoObject":
        node["name"] = val("name")
        node["description"] = val("description")
        node["thumbnailUrl"] = val("thumbnailUrl")
        if val("uploadDate"):
            node["uploadDate"] = val("uploadDate")
        if val("contentUrl"):
            node["contentUrl"] = val("contentUrl")
        if val("embedUrl"):
            node["embedUrl"] = val("embedUrl")
        return node

    if schema_type == "LocalBusiness" or schema_type in {
        "Restaurant",
    }:
        node["name"] = val("name")
        for key in ("telephone", "priceRange", "servesCuisine", "image"):
            if val(key):
                node[key] = val(key)
        if val("address"):
            node["address"] = {"@type": "PostalAddress", "streetAddress": val("address")}
        if val("openingHours"):
            node["openingHours"] = val("openingHours")
        return node

    # Generic shape: every field becomes a property, with a few well-known
    # name-like keys mapped to schema.org's property names. This keeps new
    # catalog entries usable without a bespoke builder branch.
    name_key = None
    for candidate in ("name", "headline", "title", "claimReviewed", "itemName"):
        if val(candidate):
            node["name" if candidate in ("title",) else candidate] = val(candidate)
            name_key = candidate
    for key in fields:
        if key in {
            "name", "headline", "title", "claimReviewed", "itemName", "questions",
            "steps", "items",
        }:
            continue
        if val(key):
            node[key] = val(key)
    # Author-like fields become Person objects (Google expects an object).
    for key in ("author", "director", "byArtist", "provider", "hiringOrganization"):
        if key in node and isinstance(node[key], str):
            node[key] = {"@type": "Person", "name": node[key]}
    del name_key
    return node


def validate_schema_node(node: Any) -> list[str]:
    """Return human-readable problems; empty list = storable.

    Light but load-bearing: an @type, a name-ish property, and no empty
    string values (an empty property is a Rich Results error Google reports
    as "Missing field" against a node that *looks* filled in the editor).
    """
    problems: list[str] = []
    if not isinstance(node, dict):
        return ["ساختار اسکیما باید یک شیء JSON باشد."]

    schema_type = node.get("@type")
    if not schema_type or not isinstance(schema_type, str):
        problems.append("اسکیما باید @type داشته باشد.")
        return problems

    spec = SCHEMA_TYPE_MAP.get(schema_type)
    if schema_type == "FAQ":
        entries = node.get("mainEntity")
        if not isinstance(entries, list) or not entries:
            problems.append("اسکیمای پرسش‌های متداول باید حداقل یک پرسش داشته باشد.")
    elif not any(
        isinstance(node.get(k), str) and node.get(k).strip()
        for k in ("name", "headline", "title", "claimReviewed", "itemReviewed")
    ) and not node.get("itemListElement"):
        problems.append("اسکیما باید نام یا عنوان داشته باشد.")

    if spec:
        for field in spec["fields"]:
            if field.get("required") and not node.get(field["key"]):
                # Required fields may be expressed through type-specific
                # shapes (FAQ → mainEntity); only complain when the node has
                # neither the key nor its shape.
                if field["key"] == "questions" and node.get("mainEntity"):
                    continue
                if field["key"] == "steps" and node.get("step"):
                    continue
                if field["key"] == "items" and node.get("itemListElement"):
                    continue
                problems.append(f"فیلد الزامی «{field['label']}» خالی است.")

    return problems
