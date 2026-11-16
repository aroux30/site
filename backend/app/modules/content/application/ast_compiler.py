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

        elif widget_type == "table":
            headers = props.get("headers", [])
            rows = props.get("rows", [])
            bordered = props.get("bordered", True)
            striped = props.get("striped", True)
            table_classes = ["w-full", "border-collapse", "text-right", "text-sm"]
            if bordered:
                table_classes.append("border border-border/80 rounded-xl overflow-hidden")

            thead_html = ""
            if headers:
                th_cells = "".join(
                    f'<th class="p-4 font-semibold text-muted-foreground border-b border-border/80">{html.escape(str(h))}</th>'
                    for h in headers
                )
                thead_html = f'<thead><tr class="bg-muted/40">{th_cells}</tr></thead>'

            tbody_rows = []
            for idx, row in enumerate(rows):
                tr_class = "hover:bg-muted/30"
                if striped and idx % 2 == 1:
                    tr_class += " bg-muted/10"
                td_cells = "".join(
                    f'<td class="p-4 text-foreground border-b border-border/60">{html.escape(str(cell))}</td>'
                    for cell in row
                )
                tbody_rows.append(f'<tr class="{tr_class}">{td_cells}</tr>')

            tbody_html = f'<tbody class="divide-y divide-border/60">{"".join(tbody_rows)}</tbody>'
            return f'<div{id_attr} class="builder-table overflow-x-auto {css_class}"{style_attr}><table class="{" ".join(table_classes)}">{thead_html}{tbody_html}</table></div>'

        elif widget_type == "form_input":
            label = html.escape(str(props.get("label", "")))
            name = html.escape(str(props.get("name", "field")))
            placeholder = html.escape(str(props.get("placeholder", "")))
            input_type = html.escape(str(props.get("input_type", "text")))
            required = " required" if props.get("required") else ""
            label_html = (
                f'<label class="block text-xs font-semibold text-foreground mb-1">{label}</label>'
                if label
                else ""
            )
            return (
                f'<div{id_attr} class="builder-form-group space-y-1 w-full {css_class}"{style_attr}>'
                f'{label_html}<input type="{input_type}" name="{name}" placeholder="{placeholder}"{required} '
                f'class="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary" /></div>'
            )

        elif widget_type == "form_textarea":
            label = html.escape(str(props.get("label", "")))
            name = html.escape(str(props.get("name", "message")))
            placeholder = html.escape(str(props.get("placeholder", "")))
            rows_num = int(props.get("rows", 4))
            required = " required" if props.get("required") else ""
            label_html = (
                f'<label class="block text-xs font-semibold text-foreground mb-1">{label}</label>'
                if label
                else ""
            )
            return (
                f'<div{id_attr} class="builder-form-group space-y-1 w-full {css_class}"{style_attr}>'
                f'{label_html}<textarea name="{name}" rows="{rows_num}" placeholder="{placeholder}"{required} '
                f'class="w-full rounded-xl border border-input bg-background p-3 text-sm transition focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"></textarea></div>'
            )

        elif widget_type == "form_select":
            label = html.escape(str(props.get("label", "")))
            name = html.escape(str(props.get("name", "select_field")))
            options = props.get("options", [])
            required = " required" if props.get("required") else ""
            label_html = (
                f'<label class="block text-xs font-semibold text-foreground mb-1">{label}</label>'
                if label
                else ""
            )
            opt_html = "".join(
                f'<option value="{html.escape(str(o.get("value", o) if isinstance(o, dict) else o))}">'
                f'{html.escape(str(o.get("label", o) if isinstance(o, dict) else o))}</option>'
                for o in options
            )
            return (
                f'<div{id_attr} class="builder-form-group space-y-1 w-full {css_class}"{style_attr}>'
                f'{label_html}<select name="{name}"{required} class="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm transition focus:border-primary focus:outline-none">{opt_html}</select></div>'
            )

        elif widget_type == "product_card":
            p_name = html.escape(str(props.get("name", "محصول فروشگاه")))
            p_price = html.escape(str(props.get("min_price", "")))
            p_img = html.escape(str(props.get("primary_image_url", "/placeholder-hero.svg")))
            p_instock = props.get("is_in_stock", True)
            stock_badge = "" if p_instock else '<span class="text-xs text-destructive font-bold">ناموجود</span>'
            return (
                f'<div{id_attr} class="builder-product-card rounded-2xl border border-border/60 bg-card p-4 flex flex-col space-y-3 {css_class}" data-widget="product_card"{style_attr}>'
                f'<div class="aspect-square rounded-xl bg-muted/20 overflow-hidden flex items-center justify-center">'
                f'<img src="{p_img}" alt="{p_name}" class="object-contain p-2 max-h-full" loading="lazy" />'
                f'</div>'
                f'<div class="flex-1">'
                f'<h3 class="font-bold text-foreground text-sm line-clamp-2">{p_name}</h3>'
                f'{stock_badge}'
                f'</div>'
                f'<div class="flex items-center justify-between pt-2 border-t border-border/60">'
                f'<span class="font-bold text-primary">{p_price} تومان</span>'
                f'<button type="button" class="rounded-xl bg-primary px-3 py-1.5 text-xs text-primary-foreground font-bold">خرید</button>'
                f'</div>'
                f'</div>'
            )

        elif widget_type == "image_gallery":
            images = props.get("images", [])
            imgs_html = "".join(
                f'<div class="aspect-square rounded-xl bg-muted/20 overflow-hidden flex items-center justify-center">'
                f'<img src="{html.escape(str(img.get("url", img) if isinstance(img, dict) else img))}" alt="{html.escape(str(img.get("alt", "تصویر") if isinstance(img, dict) else "تصویر"))}" class="object-contain p-2 max-h-full" loading="lazy" />'
                f'</div>'
                for img in images
            )
            return (
                f'<div{id_attr} class="builder-image-gallery grid grid-cols-2 gap-2 {css_class}" data-widget="image_gallery"{style_attr}>'
                f'{imgs_html or "<div class=\"p-4 text-center text-xs text-muted-foreground\">گالری تصاویر</div>"}'
                f'</div>'
            )

        elif widget_type == "star_rating":
            val = props.get("value", 5)
            rev_cnt = props.get("reviewCount", 0)
            return (
                f'<div{id_attr} class="builder-star-rating inline-flex items-center gap-1.5 p-2 rounded-lg bg-card border {css_class}" data-widget="star_rating"{style_attr}>'
                f'<span class="text-amber-400 font-bold">★ {val}</span>'
                f'<span class="text-xs text-muted-foreground">({rev_cnt} نظر)</span>'
                f'</div>'
            )

        elif widget_type == "review_histogram":
            avg = props.get("averageRating", 5)
            total = props.get("totalReviews", 0)
            return (
                f'<div{id_attr} class="builder-review-histogram rounded-2xl border border-border/60 bg-card p-4 space-y-2 {css_class}" data-widget="review_histogram"{style_attr}>'
                f'<div class="flex items-center justify-between">'
                f'<span class="text-lg font-bold text-foreground">{avg} از ۵</span>'
                f'<span class="text-xs text-muted-foreground">بر اساس {total} نظر</span>'
                f'</div>'
                f'<div class="h-2 rounded-full bg-muted overflow-hidden"><div class="h-full bg-emerald-500" style="width: 80%;"></div></div>'
                f'</div>'
            )

        elif widget_type == "recently_viewed":
            limit = props.get("limit", 4)
            return (
                f'<div{id_attr} class="builder-recently-viewed space-y-2 {css_class}" data-widget="recently_viewed" data-limit="{limit}"{style_attr}>'
                f'<h4 class="font-bold text-sm text-foreground">بازدیدهای اخیر شما</h4>'
                f'<div class="text-xs text-muted-foreground">نمایش آخرین محصولات بازدید شده</div>'
                f'</div>'
            )

        elif widget_type == "mega_menu":
            label = html.escape(str(props.get("label", "دسته‌بندی کالاها")))
            return (
                f'<nav{id_attr} class="builder-mega-menu inline-block {css_class}" data-widget="mega_menu"{style_attr}>'
                f'<button type="button" class="rounded-xl px-4 py-2 bg-muted/60 font-bold text-sm text-foreground flex items-center gap-2">{label}</button>'
                f'</nav>'
            )

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
