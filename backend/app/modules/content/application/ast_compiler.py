"""Visual Page Builder AST to HTML Compiler (Phase P0).

Compiles a validated PageAST tree into clean, semantic, SEO-friendly,
and sanitized HTML suitable for fallback and SSR display.
"""

from __future__ import annotations

import html
from typing import Any

from app.modules.content.domain.builder_ast import (
    BuilderElement,
    ContainerLayout,
    PageAST,
    ResponsiveStyles,
)
from app.shared.content.html_sanitizer import sanitize_html


class ASTCompiler:
    """Server-side compiler translating a PageAST tree into semantic HTML."""

    @classmethod
    def compile(cls, ast: PageAST) -> str:
        """Compile the full PageAST document into a single sanitized HTML string."""
        buffer: list[str] = []
        # Root document wrapper with RTL direction
        buffer.append('<div class="builder-document" dir="rtl">')
        for el in ast.root_elements:
            buffer.append(cls._compile_element(el))
        buffer.append("</div>")

        raw_html = "".join(buffer)
        return sanitize_html(raw_html)

    @classmethod
    def _compile_element(cls, el: BuilderElement) -> str:
        if el.is_hidden:
            return ""

        if el.type == "container":
            return cls._compile_container(el)
        elif el.type == "widget":
            return cls._compile_widget(el)
        return ""

    @classmethod
    def _compile_container(cls, el: BuilderElement) -> str:
        tag = "section"
        classes = ["builder-container", "relative"]
        style_parts: list[str] = []

        layout = el.layout or ContainerLayout()
        if layout.kind == "flex":
            classes.append("flex")
            if layout.direction == "column":
                classes.append("flex-col")
            elif layout.direction == "row":
                classes.append("flex-row")
            elif layout.direction == "column-reverse":
                classes.append("flex-col-reverse")
            elif layout.direction == "row-reverse":
                classes.append("flex-row-reverse")

            if layout.justify_content == "center":
                classes.append("justify-center")
            elif layout.justify_content == "between":
                classes.append("justify-between")
            elif layout.justify_content == "end":
                classes.append("justify-end")
            elif layout.justify_content == "start":
                classes.append("justify-start")

            if layout.align_items == "center":
                classes.append("items-center")
            elif layout.align_items == "start":
                classes.append("items-start")
            elif layout.align_items == "end":
                classes.append("items-end")

            if layout.gap and layout.gap.value > 0:
                style_parts.append(f"gap: {layout.gap.to_css()};")
        elif layout.kind == "grid":
            classes.append("grid")
            cols = max(1, min(12, layout.grid_columns))
            classes.append(f"grid-cols-1 md:grid-cols-{min(cols, 2)} lg:grid-cols-{cols}")
            if layout.gap and layout.gap.value > 0:
                style_parts.append(f"gap: {layout.gap.to_css()};")

        # Compile responsive padding / margin styles
        style_parts.extend(cls._compile_styles(el.styles))

        if el.styles.custom_css_class:
            classes.append(el.styles.custom_css_class)

        style_attr = f' style="{" ".join(style_parts)}"' if style_parts else ""
        class_attr = f' class="{" ".join(classes)}"'
        id_attr = f' id="{html.escape(el.id)}"'

        children_html = "".join(cls._compile_element(child) for child in el.children)
        return f"<{tag}{id_attr}{class_attr}{style_attr}>{children_html}</{tag}>"

    @classmethod
    def _compile_widget(cls, el: BuilderElement) -> str:
        widget_type = el.widget_type or "unknown"
        props = el.widget_props or {}
        styles = cls._compile_styles(el.styles)
        style_attr = f' style="{" ".join(styles)}"' if styles else ""
        id_attr = f' id="{html.escape(el.id)}"'
        css_class = el.styles.custom_css_class or ""

        if widget_type == "heading":
            tag = props.get("tag", "h2")
            if tag not in ("h1", "h2", "h3", "h4", "h5", "h6"):
                tag = "h2"
            text = html.escape(str(props.get("text", "")))
            return f'<{tag}{id_attr} class="font-bold text-foreground {css_class}"{style_attr}>{text}</{tag}>'

        elif widget_type == "text_editor":
            content = str(props.get("content", ""))
            return f'<div{id_attr} class="prose dark:prose-invert max-w-none {css_class}"{style_attr}>{content}</div>'

        elif widget_type == "button":
            label = html.escape(str(props.get("label", "کلیک کنید")))
            url = html.escape(str(props.get("url", "#")))
            target = ' target="_blank" rel="noopener noreferrer"' if props.get("new_tab") else ""
            return f'<a href="{url}"{id_attr} class="inline-flex items-center justify-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground transition hover:opacity-90 {css_class}"{target}{style_attr}>{label}</a>'

        elif widget_type == "image":
            src = html.escape(str(props.get("url", "")))
            alt = html.escape(str(props.get("alt", "")))
            return f'<img src="{src}" alt="{alt}"{id_attr} class="rounded-xl object-cover max-w-full h-auto {css_class}" loading="lazy"{style_attr} />'

        elif widget_type == "divider":
            return f'<hr{id_attr} class="my-6 border-border/80 {css_class}"{style_attr} />'

        elif widget_type == "spacer":
            h = props.get("height", 32)
            return f'<div{id_attr} class="w-full {css_class}" style="height: {int(h)}px;" aria-hidden="true"></div>'

        elif widget_type == "html_custom" or widget_type == "legacy_html":
            raw_html = str(props.get("html", props.get("content", "")))
            return f'<div{id_attr} class="builder-custom-html {css_class}"{style_attr}>{raw_html}</div>'

        elif widget_type == "product_grid":
            category_id = props.get("category_id", "")
            limit = props.get("limit", 6)
            return f'<div{id_attr} class="builder-product-grid {css_class}" data-widget="product_grid" data-category="{category_id}" data-limit="{limit}"{style_attr}><div class="py-8 text-center text-muted-foreground">بارگذاری ویترین محصولات...</div></div>'

        elif widget_type == "product_title":
            title_text = html.escape(str(props.get("fallback_title", "عنوان محصول")))
            return f'<h1{id_attr} class="text-2xl lg:text-3xl font-bold text-foreground {css_class}"{style_attr}>{title_text}</h1>'

        elif widget_type == "product_price":
            price_text = html.escape(str(props.get("fallback_price", "۰ تومان")))
            return f'<div{id_attr} class="text-xl font-black text-primary {css_class}"{style_attr}>{price_text}</div>'

        elif widget_type == "add_to_cart":
            btn_label = html.escape(str(props.get("label", "افزودن به سبد خرید")))
            return f'<button type="button"{id_attr} class="w-full rounded-xl bg-primary py-3 px-6 font-bold text-primary-foreground shadow transition hover:bg-primary/90 {css_class}"{style_attr}>{btn_label}</button>'

        # Generic fallback for any other registered widget
        fallback_title = html.escape(str(props.get("title", widget_type)))
        return f'<div{id_attr} class="builder-widget builder-{widget_type} {css_class}" data-widget="{html.escape(widget_type)}"{style_attr}>{fallback_title}</div>'

    @classmethod
    def _compile_styles(cls, styles: ResponsiveStyles) -> list[str]:
        parts: list[str] = []
        base = styles.mobile

        if base.padding:
            p = base.padding
            parts.append(f"padding: {p.top.to_css()} {p.right.to_css()} {p.bottom.to_css()} {p.left.to_css()};")
        if base.margin:
            m = base.margin
            parts.append(f"margin: {m.top.to_css()} {m.right.to_css()} {m.bottom.to_css()} {m.left.to_css()};")
        if base.width:
            parts.append(f"width: {base.width.to_css()};")
        if base.min_height:
            parts.append(f"min-height: {base.min_height.to_css()};")
        if base.typography and base.typography.color:
            color = base.typography.color
            if color.startswith("var(--"):
                parts.append(f"color: hsl({color});")
            else:
                parts.append(f"color: {color};")
        if base.background and base.background.color:
            bg_color = base.background.color
            if bg_color.startswith("var(--"):
                parts.append(f"background-color: hsl({bg_color});")
            else:
                parts.append(f"background-color: {bg_color};")

        return parts
