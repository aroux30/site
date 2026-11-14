"""Unit tests for Visual Page Builder ASTCompiler (Phase P0)."""

from __future__ import annotations

import pytest
from app.modules.content.application.ast_compiler import ASTCompiler
from app.modules.content.domain.builder_ast import (
    BuilderElement,
    ContainerLayout,
    PageAST,
    ResponsiveStyles,
    SpacingBox,
    UnitValue,
)


def test_ast_compiler_renders_semantic_html():
    ast = PageAST(
        schema_version=1,
        title="صفحه تست کامپایلر",
        slug="test-compile",
        root_elements=[
            BuilderElement(
                id="el_sec01",
                name="بخش یک",
                type="container",
                layout=ContainerLayout(kind="flex", direction="column"),
                children=[
                    BuilderElement(
                        id="el_head01",
                        name="سرتیتر",
                        type="widget",
                        widget_type="heading",
                        widget_props={"text": "عنوان تستی", "tag": "h1"},
                    ),
                    BuilderElement(
                        id="el_btn01",
                        name="دکمه",
                        type="widget",
                        widget_type="button",
                        widget_props={"label": "ثبت نام", "url": "/register"},
                    ),
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert '<div class="builder-document" dir="rtl">' in result
    assert '<h1 id="el_head01"' in result
    assert "عنوان تستی</h1>" in result
    assert '<a href="/register" id="el_btn01"' in result
    assert "ثبت نام</a>" in result


def test_ast_compiler_strips_malicious_script_tags():
    ast = PageAST(
        schema_version=1,
        title="تست امنیت",
        slug="test-xss",
        root_elements=[
            BuilderElement(
                id="el_sec01",
                name="بخش امن",
                type="container",
                children=[
                    BuilderElement(
                        id="el_txt01",
                        name="متن غنی",
                        type="widget",
                        widget_type="text_editor",
                        widget_props={
                            "content": '<p>متن سالم</p><script>alert("hacked")</script><img src="x" onerror="alert(1)">'
                        },
                    )
                ],
            )
        ],
    )
    result = ASTCompiler.compile(ast)
    assert "<script>" not in result
    assert "alert" not in result
    assert "onerror" not in result
    assert "متن سالم" in result
