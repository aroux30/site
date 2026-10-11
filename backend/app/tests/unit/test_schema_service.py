"""Tests for the Schema service — the Rich Snippets builder and validator.

Pins the behaviors Rank Math's Schema module promises:

- Every catalog type assembles a node with @context/@type.
- Type-specific shapes: FAQ lines → mainEntity, HowTo lines → step[],
  ItemList lines → itemListElement — a flat form value cannot express these.
- Required-but-empty fields fall back to the resource (a Product's name from
  the product row), so a partially filled form still yields a valid node.
- The validator rejects the silent killers: missing @type, no name-ish
  property, required fields empty.
- Malformed input never raises: a bad line is skipped, a bad number is
  ignored, a non-dict node is a validation problem.
"""

from __future__ import annotations

import pytest

from app.modules.seo.application import schema_service as ss


def test_catalog_is_substantial_and_well_formed():
    assert len(ss.SCHEMA_TYPES) >= 20
    seen: set[str] = set()
    for entry in ss.SCHEMA_TYPES:
        assert entry["type"] not in seen, f"duplicate type {entry['type']}"
        seen.add(entry["type"])
        assert entry["label"]
        assert entry["fields"], f"{entry['type']} has no fields"
        for field in entry["fields"]:
            assert field["key"] and field["label"] and field["kind"]


def test_every_catalog_type_builds_a_node():
    """Every offered type must produce @context/@type — a type the builder
    cannot assemble would render an empty editor form."""
    for entry in ss.SCHEMA_TYPES:
        values = {f["key"]: "مقدار تست" for f in entry["fields"]}
        node = ss.build_schema_node(entry["type"], values)
        assert node["@context"] == ss.SCHEMA_CONTEXT
        assert node["@type"] == entry["type"]


def test_faq_lines_become_main_entity():
    node = ss.build_schema_node(
        "FAQ",
        {"questions": "پرسش یک | پاسخ یک\nپرسش دو | پاسخ دو\nخط خراب بدون جداکننده"},
    )
    assert node["@type"] == "FAQ"
    assert len(node["mainEntity"]) == 2
    assert node["mainEntity"][0]["name"] == "پرسش یک"
    assert node["mainEntity"][0]["acceptedAnswer"]["text"] == "پاسخ یک"


def test_howto_lines_become_steps():
    node = ss.build_schema_node(
        "HowTo",
        {"name": "راهنما", "steps": "گام اول\nگام دوم"},
    )
    assert [s["position"] for s in node["step"]] == [1, 2]
    assert node["step"][0]["text"] == "گام اول"


def test_itemlist_lines_become_list_items():
    node = ss.build_schema_node("ItemList", {"name": "بهترین‌ها", "items": "الف\nب"})
    assert len(node["itemListElement"]) == 2
    assert node["itemListElement"][1]["name"] == "ب"


def test_product_resource_default_fills_empty_name():
    """A partially filled form must still be valid: name comes from the row."""
    node = ss.build_schema_node(
        "Product",
        {"name": "", "price": "100000"},
        resource_defaults={"name": "کالای واقعی"},
    )
    assert node["name"] == "کالای واقعی"


def test_product_price_builds_offer():
    node = ss.build_schema_node(
        "Product", {"name": "کالا", "price": "150000", "availability": "InStock"}
    )
    assert node["offers"]["price"] == 150000
    assert node["offers"]["availability"].endswith("InStock")


def test_product_bad_price_does_not_raise():
    node = ss.build_schema_node("Product", {"name": "کالا", "price": "هزار"})
    assert "offers" not in node  # zero/invalid price → no offer, not a crash


def test_review_rating_object():
    node = ss.build_schema_node(
        "Review",
        {"itemName": "کالا", "ratingValue": "4.5", "author": "علی"},
    )
    assert node["reviewRating"]["ratingValue"] == 4.5
    assert node["author"]["@type"] == "Person"


def test_local_business_address_object():
    node = ss.build_schema_node(
        "LocalBusiness", {"name": "فروشگاه", "address": "تهران، خیابان اول"}
    )
    assert node["address"]["@type"] == "PostalAddress"


def test_validator_rejects_missing_type():
    problems = ss.validate_schema_node({"name": "چیزی"})
    assert problems and "@type" in problems[0]


def test_validator_rejects_nameless_node():
    problems = ss.validate_schema_node({"@type": "Article"})
    assert any("نام یا عنوان" in p for p in problems)


def test_validator_rejects_empty_required_field():
    problems = ss.validate_schema_node(
        {"@type": "Review", "name": "x", "reviewRating": {"ratingValue": 5}}
    )
    # itemReviewed missing → required itemName complaint
    assert any("الزامی" in p for p in problems)


def test_validator_accepts_good_faq():
    node = ss.build_schema_node("FAQ", {"questions": "q | a"})
    assert ss.validate_schema_node(node) == []


def test_validator_rejects_empty_faq():
    problems = ss.validate_schema_node({"@type": "FAQ", "mainEntity": []})
    assert problems


def test_validator_rejects_non_dict():
    assert ss.validate_schema_node(["not", "a", "dict"])


def test_unknown_type_gets_generic_shape_not_crash():
    node = ss.build_schema_node("MadeUpType", {"name": "تست", "extra": "ارزش"})
    assert node["@type"] == "MadeUpType"
    assert node["name"] == "تست"
    assert node["extra"] == "ارزش"


def test_author_like_fields_become_objects():
    node = ss.build_schema_node("Article", {"headline": "خبر", "author": "نویسنده"})
    assert node["author"] == {"@type": "Person", "name": "نویسنده"}


def test_get_type_spec():
    assert ss.get_type_spec("Product") is not None
    assert ss.get_type_spec("Nope") is None
