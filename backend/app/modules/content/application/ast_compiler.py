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
    def compile(cls, ast: PageAST, is_authenticated: bool = False) -> str:
        """Compile the full PageAST document into a single sanitized HTML string.

        When is_authenticated is False, blocks with auth_visibility="authenticated"
        are omitted from the server output entirely to prevent leaking private content.
        """
        buffer: list[str] = []
        # Root document wrapper with RTL direction
        buffer.append('<div class="builder-document" dir="rtl">')
        for el in ast.root_elements:
            compiled = cls._compile_element(el, is_authenticated=is_authenticated)
            if compiled:
                buffer.append(compiled)
        buffer.append("</div>")

        raw_html = "".join(buffer)
        return sanitize_html(raw_html)

    @classmethod
    def _parse_custom_attributes(cls, raw: str | None) -> str:
        """Parse key|value pairs from custom_attributes (Elementor Parity)."""
        if not raw:
            return ""
        attrs: list[str] = []
        blacklist = {"id", "class", "style", "data-element-id", "data-auth", "data-global-component"}
        for line in raw.strip().splitlines():
            line = line.strip()
            if not line or "|" not in line:
                continue
            parts = line.split("|", 1)
            k = parts[0].strip().lower()
            v = parts[1].strip()
            if not k or k in blacklist or k.startswith("on") or "javascript:" in v.lower():
                continue
            attrs.append(f' {html.escape(k)}="{html.escape(v)}"')
        return "".join(attrs)

    @classmethod
    def _compile_element(cls, el: BuilderElement, is_authenticated: bool = False) -> str:
        if el.is_hidden:
            return ""

        # Server-side authVisibility filtering (P5 Production Hardening):
        # Drop completely from compiled HTML so guests cannot inspect member-only content
        if el.auth_visibility == "authenticated" and not is_authenticated:
            return ""
        if el.auth_visibility == "guest" and is_authenticated:
            return ""

        if el.type == "container":
            return cls._compile_container(el, is_authenticated=is_authenticated)
        elif el.type == "widget":
            return cls._compile_widget(el)
        return ""

    @classmethod
    def _compile_container(cls, el: BuilderElement, is_authenticated: bool = False) -> str:
        is_form = el.widget_type == "form_container"
        tag = "form" if is_form else "section"
        classes = ["builder-container", "relative"]
        style_parts: list[str] = []

        # Conditional visibility classes
        if not el.visible_on_desktop:
            classes.append("lg:hidden")
        if not el.visible_on_tablet:
            classes.append("md:max-lg:hidden")
        if not el.visible_on_mobile:
            classes.append("max-md:hidden")

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

        # Boxed container layout: restrict maxWidth and auto-center
        if layout.boxed_width and layout.boxed_width.value > 0:
            style_parts.append(f"max-width: {layout.boxed_width.to_css()}; margin-left: auto; margin-right: auto;")

        # Compile responsive padding / margin / advanced layout styles
        style_parts.extend(cls._compile_styles(el.styles))

        if el.styles.animation and el.styles.animation != "none":
            classes.append(f"builder-animate-{el.styles.animation}")
            if el.styles.animation_duration:
                style_parts.append(f"animation-duration: {el.styles.animation_duration}s;")
            if el.styles.animation_delay:
                style_parts.append(f"animation-delay: {el.styles.animation_delay}s;")

        if el.styles.custom_css_class:
            classes.append(el.styles.custom_css_class)

        style_attr = f' style="{" ".join(style_parts)}"' if style_parts else ""
        class_attr = f' class="{" ".join(classes)}"'
        element_id = el.styles.custom_css_id or el.id
        id_attr = f' id="{html.escape(element_id)}"'
        extra_attrs = ""
        if el.auth_visibility != "all":
            extra_attrs += f' data-auth="{html.escape(el.auth_visibility)}"'
        if el.global_component_id:
            extra_attrs += f' data-global-component="{html.escape(el.global_component_id)}"'
        if el.styles.custom_attributes:
            extra_attrs += cls._parse_custom_attributes(el.styles.custom_attributes)

        # Compile background overlay if present
        overlay = el.styles.mobile.background_overlay
        overlay_html = ""
        if overlay and overlay.type != "none":
            ov_styles = ["position: absolute;", "inset: 0;", "pointer-events: none;", "border-radius: inherit;"]
            if overlay.opacity is not None:
                ov_styles.append(f"opacity: {overlay.opacity};")
            if overlay.type == "color" and overlay.color:
                ov_styles.append(f"background-color: {overlay.color};")
            elif overlay.type == "gradient" and overlay.gradient:
                dir_map = {"to-r": "to right", "to-l": "to left", "to-b": "to bottom", "to-t": "to top"}
                d = dir_map.get(overlay.gradient.direction, "to bottom")
                ov_styles.append(f"background-image: linear-gradient({d}, {overlay.gradient.from_color}, {overlay.gradient.to_color});")
            overlay_html = f'<div class="builder-background-overlay" style="{" ".join(ov_styles)}" aria-hidden="true"></div>'

        # Compile shape dividers if present (Elementor Parity)
        top_divider = el.styles.shape_divider_top
        bottom_divider = el.styles.shape_divider_bottom
        shape_color = html.escape(el.styles.shape_divider_color or "#ffffff")
        shape_dividers_html = ""
        if top_divider and top_divider != "none":
            shape_dividers_html += f'<div class="builder-shape-divider builder-shape-divider-top" data-shape="{html.escape(top_divider)}" style="position: absolute; top: 0; left: 0; width: 100%; height: 48px; overflow: hidden; pointer-events: none; z-index: 10;"><img src="/shapes/{html.escape(top_divider)}.svg" alt="" style="width: 100%; height: 100%; display: block;" /></div>'
        if bottom_divider and bottom_divider != "none":
            shape_dividers_html += f'<div class="builder-shape-divider builder-shape-divider-bottom" data-shape="{html.escape(bottom_divider)}" style="position: absolute; bottom: 0; left: 0; width: 100%; height: 48px; overflow: hidden; pointer-events: none; z-index: 10; transform: rotate(180deg);"><img src="/shapes/{html.escape(bottom_divider)}.svg" alt="" style="width: 100%; height: 100%; display: block;" /></div>'

        if is_form:
            props = el.widget_props or {}
            submit_url = html.escape(str(props.get("submit_url", "/api/v1/content/forms/submit")))
            extra_attrs += f' action="{submit_url}" method="POST" data-form-container="true"'
            if props.get("success_message"):
                extra_attrs += f' data-success-message="{html.escape(str(props["success_message"]))}"'
            if props.get("error_message"):
                extra_attrs += f' data-error-message="{html.escape(str(props["error_message"]))}"'
            # Include anti-spam honeypot hidden field inside form
            hp_field = '<input type="text" name="_hp_website" style="display:none !important;" tabindex="-1" autocomplete="off" aria-hidden="true" />'
            children_html = overlay_html + shape_dividers_html + hp_field + "".join(
                cls._compile_element(child, is_authenticated=is_authenticated) for child in el.children
            )
        else:
            children_html = overlay_html + shape_dividers_html + "".join(
                cls._compile_element(child, is_authenticated=is_authenticated) for child in el.children
            )

        return f"<{tag}{id_attr}{class_attr}{style_attr}{extra_attrs}>{children_html}</{tag}>"

    @classmethod
    def _compile_widget(cls, el: BuilderElement) -> str:
        widget_type = el.widget_type or "unknown"
        props = el.widget_props or {}
        styles = cls._compile_styles(el.styles)

        classes_list = []
        if not el.visible_on_desktop:
            classes_list.append("lg:hidden")
        if not el.visible_on_tablet:
            classes_list.append("md:max-lg:hidden")
        if not el.visible_on_mobile:
            classes_list.append("max-md:hidden")

        if el.styles.custom_css_class:
            classes_list.append(el.styles.custom_css_class)
        prop_class = props.get("customCssClass")
        if prop_class and str(prop_class) not in classes_list:
            classes_list.append(str(prop_class))
        if el.styles.animation and el.styles.animation != "none":
            classes_list.append(f"builder-animate-{el.styles.animation}")
            if el.styles.animation_duration:
                styles.append(f"animation-duration: {el.styles.animation_duration}s;")
            if el.styles.animation_delay:
                styles.append(f"animation-delay: {el.styles.animation_delay}s;")

        style_attr = f' style="{" ".join(styles)}"' if styles else ""
        widget_id = el.styles.custom_css_id or el.id
        id_attr = f' id="{html.escape(widget_id)}"'
        extra_attrs = ""
        if el.auth_visibility != "all":
            extra_attrs += f' data-auth="{html.escape(el.auth_visibility)}"'
        if el.global_component_id:
            extra_attrs += f' data-global-component="{html.escape(el.global_component_id)}"'
        if el.styles.custom_attributes:
            extra_attrs += cls._parse_custom_attributes(el.styles.custom_attributes)
        css_class = " ".join(classes_list)

        if widget_type == "heading":
            tag = props.get("tag", "h2")
            if tag not in ("h1", "h2", "h3", "h4", "h5", "h6"):
                tag = "h2"
            text = html.escape(str(props.get("text", "")))
            return f'<{tag}{id_attr} class="font-bold text-foreground break-words {css_class}"{style_attr}{extra_attrs}>{text}</{tag}>'

        elif widget_type in ("text_editor", "text", "paragraph"):
            content = str(props.get("content", props.get("text", "")))
            return f'<div{id_attr} class="prose dark:prose-invert max-w-none break-words {css_class}"{style_attr}{extra_attrs}>{content}</div>'

        elif widget_type == "button":
            label = html.escape(str(props.get("label", "کلیک کنید")))
            url = html.escape(str(props.get("url", "#")))
            target = ' target="_blank" rel="noopener noreferrer"' if props.get("new_tab") else ""
            return f'<a href="{url}"{id_attr} class="inline-flex items-center justify-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground transition hover:opacity-90 {css_class}"{target}{style_attr}{extra_attrs}>{label}</a>'

        elif widget_type == "image":
            src = html.escape(str(props.get("url", "")))
            alt = html.escape(str(props.get("alt", "")))
            return f'<img src="{src}" alt="{alt}"{id_attr} class="rounded-xl object-cover max-w-full h-auto {css_class}" loading="lazy"{style_attr}{extra_attrs} />'

        elif widget_type == "divider":
            return f'<hr{id_attr} class="my-6 border-border/80 {css_class}"{style_attr}{extra_attrs} />'

        elif widget_type == "spacer":
            h = props.get("height", 32)
            return f'<div{id_attr} class="w-full {css_class}" style="height: {int(h)}px;" aria-hidden="true"{extra_attrs}></div>'

        elif widget_type == "html_custom" or widget_type == "legacy_html":
            raw_html = str(props.get("html", props.get("content", "")))
            return f'<div{id_attr} class="builder-custom-html {css_class}"{style_attr}{extra_attrs}>{raw_html}</div>'

        elif widget_type == "product_title":
            title_text = html.escape(str(props.get("fallback_title", "عنوان محصول")))
            return f'<h1{id_attr} class="text-2xl lg:text-3xl font-bold text-foreground {css_class}"{style_attr}{extra_attrs}>{title_text}</h1>'

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

        elif widget_type == "product_price":
            price_val = props.get("price", props.get("min_price", "۰"))
            compare_price = props.get("compare_at_price")
            curr = html.escape(str(props.get("currency", "تومان")))
            badge_html = ""
            del_html = ""
            if compare_price:
                del_html = f'<del class="text-xs text-muted-foreground">{html.escape(str(compare_price))} {curr}</del>'
                try:
                    p_norm = str(price_val).replace(",", "").replace("،", "")
                    c_norm = str(compare_price).replace(",", "").replace("،", "")
                    for pd, ed in [("۰","0"),("۱","1"),("۲","2"),("۳","3"),("۴","4"),("۵","5"),("۶","6"),("۷","7"),("۸","8"),("۹","9")]:
                        p_norm = p_norm.replace(pd, ed)
                        c_norm = c_norm.replace(pd, ed)
                    c_float = float(c_norm)
                    p_float = float(p_norm)
                    if c_float > p_float and c_float > 0:
                        diff = int(((c_float - p_float) / c_float) * 100)
                        badge_html = f'<span class="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full font-bold">{diff}% تخفیف</span>'
                except (ValueError, TypeError, ZeroDivisionError):
                    pass
            return (
                f'<div{id_attr} class="builder-product-price flex items-center gap-2 {css_class}" data-widget="product_price"{style_attr}>'
                f'<span class="text-xl font-black text-primary">{html.escape(str(price_val))} {curr}</span>'
                f'{del_html}'
                f'{badge_html}'
                f'</div>'
            )

        elif widget_type == "add_to_cart":
            label = html.escape(str(props.get("label", "افزودن به سبد خرید")))
            variant_id = html.escape(str(props.get("variant_id", "")))
            return (
                f'<button type="button"{id_attr} class="builder-add-to-cart w-full rounded-xl bg-primary py-3 px-6 font-bold text-primary-foreground shadow hover:bg-primary/90 transition {css_class}" '
                f'data-widget="add_to_cart" data-variant-id="{variant_id}"{style_attr}>'
                f'{label}'
                f'</button>'
            )

        elif widget_type == "product_variants":
            p_title = html.escape(str(props.get("product_title", "انتخاب تنوع محصول")))
            variants = props.get("variants", [])
            opts_html = "".join(
                f'<button type="button" class="px-3 py-1.5 rounded-lg border border-border text-xs font-semibold hover:border-primary transition" data-variant-id="{html.escape(str(v.get("id", "")))}">'
                f'{html.escape(str(v.get("title", v.get("name", "تنوع"))))} - {html.escape(str(v.get("price", "")))} تومان'
                f'</button>'
                for v in variants
            )
            empty_opts_span = '<span class="text-xs text-muted-foreground">بدون تنوع</span>'
            opts_content = opts_html if opts_html else empty_opts_span
            return (
                f'<div{id_attr} class="builder-product-variants space-y-2 {css_class}" data-widget="product_variants"{style_attr}>'
                f'<label class="block text-xs font-bold text-foreground">{p_title}</label>'
                f'<div class="flex flex-wrap gap-2">{opts_content}</div>'
                f'</div>'
            )

        elif widget_type == "mini_cart":
            count = int(props.get("item_count", 0))
            return (
                f'<div{id_attr} class="builder-mini-cart inline-flex items-center gap-2 p-2 rounded-xl bg-card border border-border/80 {css_class}" data-widget="mini_cart"{style_attr}>'
                f'<span class="text-xs font-bold">سبد خرید</span>'
                f'<span class="bg-primary text-primary-foreground text-xs font-bold px-2 py-0.5 rounded-full">{count}</span>'
                f'</div>'
            )

        elif widget_type == "cart_summary":
            subtotal = html.escape(str(props.get("subtotal", "۰")))
            return (
                f'<div{id_attr} class="builder-cart-summary p-4 rounded-2xl border border-border/80 bg-card space-y-3 {css_class}" data-widget="cart_summary"{style_attr}>'
                f'<h3 class="font-bold text-sm text-foreground">خلاصه سبد خرید</h3>'
                f'<div class="flex justify-between text-xs text-muted-foreground"><span>مجموع اقلام:</span><span class="font-bold text-foreground">{subtotal} تومان</span></div>'
                f'<a href="/checkout" class="block w-full py-2.5 rounded-xl bg-emerald-600 text-white font-bold text-xs text-center hover:bg-emerald-700 transition">ادامه فرآیند خرید</a>'
                f'</div>'
            )

        elif widget_type in ("product_grid", "loop_grid"):
            limit = int(props.get("limit", 4))
            cat = html.escape(str(props.get("category", "all")))
            flt = html.escape(str(props.get("filter", "all")))
            show_pag = props.get("show_pagination", False)
            cards = []
            for i in range(min(limit, 8)):
                card = (
                    f'<div class="rounded-xl border border-border/60 p-3 bg-card space-y-2">'
                    f'<div class="aspect-square bg-muted/20 rounded-lg flex items-center justify-center">'
                    f'<img src="/placeholder-hero.svg" alt="محصول" class="p-2 max-h-full" loading="lazy" />'
                    f'</div>'
                    f'<h4 class="font-bold text-xs">کالای فروشگاه {i+1}</h4>'
                    f'<span class="text-xs text-primary font-bold">۳۵۰,۰۰۰ تومان</span>'
                    f'</div>'
                )
                cards.append(card)
            grid_cards_html = "".join(cards)
            pagination_btn = (
                '<div class="text-center pt-2"><button type="button" class="px-4 py-2 rounded-xl border border-primary text-xs font-bold text-primary hover:bg-primary/5 transition">مشاهده محصولات بیشتر</button></div>'
                if show_pag
                else ""
            )
            return (
                f'<div{id_attr} class="builder-product-grid space-y-4 {css_class}" data-widget="{html.escape(widget_type)}" data-category="{cat}" data-filter="{flt}" data-limit="{limit}"{style_attr}>'
                f'<div class="grid grid-cols-2 md:grid-cols-4 gap-4">{grid_cards_html}</div>'
                f'{pagination_btn}'
                f'</div>'
            )

        elif widget_type == "form_checkbox":
            label = html.escape(str(props.get("label", "شرایط و قوانین را می‌پذیرم")))
            name = html.escape(str(props.get("name", "accept_terms")))
            required = " required" if props.get("required") else ""
            checked = " checked" if props.get("checked") else ""
            return (
                f'<div{id_attr} class="builder-form-checkbox flex items-center gap-2 {css_class}"{style_attr}>'
                f'<input type="checkbox" id="chk_{html.escape(el.id)}" name="{name}"{checked}{required} class="rounded border-input text-primary focus:ring-primary h-4 w-4" />'
                f'<label for="chk_{html.escape(el.id)}" class="text-xs font-medium text-foreground cursor-pointer">{label}</label>'
                f'</div>'
            )

        elif widget_type == "form_radio":
            label = html.escape(str(props.get("label", "گزینش")))
            name = html.escape(str(props.get("name", "radio_group")))
            options = props.get("options", ["گزینه یک", "گزینه دو"])
            opts_html = "".join(
                f'<label class="flex items-center gap-2 text-xs text-foreground cursor-pointer">'
                f'<input type="radio" name="{name}" value="{html.escape(str(o))}" class="text-primary focus:ring-primary h-4 w-4" />'
                f'<span>{html.escape(str(o))}</span>'
                f'</label>'
                for o in options
            )
            return (
                f'<div{id_attr} class="builder-form-radio space-y-1.5 {css_class}"{style_attr}>'
                f'<span class="block text-xs font-semibold text-foreground">{label}</span>'
                f'<div class="flex flex-col gap-1.5">{opts_html}</div>'
                f'</div>'
            )

        elif widget_type == "accordion":
            items = props.get("items", [{"title": "پرسش متداول ۱", "content": "پاسخ پرسش متداول ۱"}])
            items_html = "".join(
                f'<details class="group rounded-xl border border-border/80 bg-card overflow-hidden" {"open" if (itm.get("default_open") or (itm.get("default_open") is None and idx == 0)) else ""}>'
                f'<summary class="p-3.5 font-bold text-xs text-foreground cursor-pointer list-none flex items-center justify-between hover:bg-muted/40 transition select-none">'
                f'<span>{html.escape(str(itm.get("title", "پرسش")))}</span>'
                f'<span class="transition-transform group-open:rotate-180">▾</span>'
                f'</summary>'
                f'<div class="p-3.5 pt-0 text-xs text-muted-foreground border-t border-border/40 leading-relaxed">'
                f'{html.escape(str(itm.get("content", "")))}'
                f'</div>'
                f'</details>'
                for idx, itm in enumerate(items)
            )
            return f'<div{id_attr} class="builder-accordion space-y-2 w-full {css_class}" data-widget="accordion"{style_attr}>{items_html}</div>'

        elif widget_type == "tabs":
            tabs_list = props.get("tabs", [{"title": "تب ۱", "content": "محتوای تب ۱"}, {"title": "تب ۲", "content": "محتوای تب ۲"}])
            header_html = "".join(
                f'<button type="button" class="px-4 py-2 text-xs font-bold border-b-2 {"border-primary text-primary" if idx == 0 else "border-transparent text-muted-foreground"} hover:text-foreground transition">'
                f'{html.escape(str(t.get("title", f"تب {idx+1}")))}'
                f'</button>'
                for idx, t in enumerate(tabs_list)
            )
            content_html = "".join(
                f'<div class="p-4 text-xs text-muted-foreground leading-relaxed {"" if idx == 0 else "hidden"}">'
                f'{html.escape(str(t.get("content", "")))}'
                f'</div>'
                for idx, t in enumerate(tabs_list)
            )
            return (
                f'<div{id_attr} class="builder-tabs rounded-xl border border-border/80 bg-card overflow-hidden w-full {css_class}" data-widget="tabs"{style_attr}>'
                f'<div class="flex border-b border-border/60 bg-muted/30">{header_html}</div>'
                f'<div class="tab-contents">{content_html}</div>'
                f'</div>'
            )

        elif widget_type == "countdown":
            title = html.escape(str(props.get("title", "پیشنهاد شگفت‌انگیز")))
            target_str = str(props.get("target_date", "2026-12-31T23:59:59"))
            target = html.escape(target_str)
            d_fa, h_fa, m_fa, s_fa = "۰۲", "۱۴", "۳۵", "۰۰"
            try:
                from datetime import datetime, timezone
                now_utc = datetime.now(timezone.utc)
                target_dt = datetime.fromisoformat(target_str.replace("Z", "+00:00"))
                diff_sec = max(0, int((target_dt - now_utc).total_seconds()))
                d = diff_sec // 86400
                h = (diff_sec % 86400) // 3600
                m = (diff_sec % 3600) // 60
                s = diff_sec % 60
                persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                def to_fa(num: int) -> str:
                    s_num = f"{num:02d}"
                    return "".join(persian_digits[int(ch)] for ch in s_num)
                d_fa, h_fa, m_fa, s_fa = to_fa(d), to_fa(h), to_fa(m), to_fa(s)
            except Exception:
                pass
            return (
                f'<div{id_attr} class="builder-countdown p-4 rounded-2xl bg-card border border-border/80 text-center space-y-3 {css_class}" data-widget="countdown" data-target="{target}"{style_attr}>'
                f'<h3 class="font-bold text-sm text-foreground">{title}</h3>'
                f'<div class="flex items-center justify-center gap-2 text-center" dir="ltr">'
                f'<div class="bg-muted/60 p-2 rounded-xl min-w-[50px]"><span class="block text-lg font-black text-primary">{d_fa}</span><span class="text-[10px] text-muted-foreground">روز</span></div>'
                f'<span class="font-bold text-primary">:</span>'
                f'<div class="bg-muted/60 p-2 rounded-xl min-w-[50px]"><span class="block text-lg font-black text-primary">{h_fa}</span><span class="text-[10px] text-muted-foreground">ساعت</span></div>'
                f'<span class="font-bold text-primary">:</span>'
                f'<div class="bg-muted/60 p-2 rounded-xl min-w-[50px]"><span class="block text-lg font-black text-primary">{m_fa}</span><span class="text-[10px] text-muted-foreground">دقیقه</span></div>'
                f'<span class="font-bold text-primary">:</span>'
                f'<div class="bg-muted/60 p-2 rounded-xl min-w-[50px]"><span class="block text-lg font-black text-primary">{s_fa}</span><span class="text-[10px] text-muted-foreground">ثانیه</span></div>'
                f'</div>'
                f'</div>'
            )

        elif widget_type == "video":
            v_type = props.get("video_type", "direct")
            v_url = html.escape(str(props.get("url", "")))
            poster = html.escape(str(props.get("poster", "")))
            if v_type in ("aparat", "youtube"):
                return (
                    f'<div{id_attr} class="builder-video aspect-video w-full rounded-2xl overflow-hidden border border-border/80 bg-black {css_class}" data-widget="video"{style_attr}>'
                    f'<iframe src="{v_url}" class="w-full h-full border-0" allowfullscreen loading="lazy"></iframe>'
                    f'</div>'
                )
            else:
                poster_attr = f' poster="{poster}"' if poster else ""
                return (
                    f'<div{id_attr} class="builder-video w-full rounded-2xl overflow-hidden border border-border/80 bg-black {css_class}" data-widget="video"{style_attr}>'
                    f'<video src="{v_url}" controls{poster_attr} class="w-full max-h-[500px]"></video>'
                    f'</div>'
                )

        elif widget_type == "icon_box":
            title = html.escape(str(props.get("title", "ارسال سریع و رایگان")))
            desc = html.escape(str(props.get("description", "تحویل سفارش‌ها در سریع‌ترین زمان ممکن به سراسر کشور")))
            return (
                f'<div{id_attr} class="builder-icon-box p-4 rounded-2xl border border-border/80 bg-card flex items-start gap-3 {css_class}" data-widget="icon_box"{style_attr}>'
                f'<div class="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0 font-bold">★</div>'
                f'<div class="space-y-1">'
                f'<h4 class="font-bold text-xs text-foreground">{title}</h4>'
                f'<p class="text-[11px] text-muted-foreground leading-relaxed">{desc}</p>'
                f'</div>'
                f'</div>'
            )

        elif widget_type == "social_links":
            links = props.get("links", [{"platform": "instagram", "url": "#"}, {"platform": "telegram", "url": "#"}])
            links_html = "".join(
                f'<a href="{html.escape(str(l.get("url", "#")))}" target="_blank" rel="noopener noreferrer" class="p-2 rounded-xl bg-muted/60 hover:bg-primary hover:text-white transition text-xs font-bold">'
                f'{html.escape(str(l.get("platform", "لینک")))}'
                f'</a>'
                for l in links
            )
            return (
                f'<div{id_attr} class="builder-social-links flex items-center gap-2 {css_class}" data-widget="social_links"{style_attr}>'
                f'{links_html}'
                f'</div>'
            )

        elif widget_type == "counter":
            title = html.escape(str(props.get("title", props.get("label", "شمارنده"))))
            ending = props.get("ending_number", props.get("target_number", 100))
            prefix = html.escape(str(props.get("prefix", "")))
            suffix = html.escape(str(props.get("suffix", "")))
            return (
                f'<div{id_attr} class="builder-counter p-4 rounded-2xl border border-border/80 bg-card text-center space-y-1 {css_class}" data-widget="counter"{style_attr}>'
                f'<div class="text-3xl font-black text-primary font-mono">{prefix}{ending}{suffix}</div>'
                f'<div class="text-xs font-semibold text-muted-foreground">{title}</div>'
                f'</div>'
            )

        elif widget_type == "progress_bar":
            title = html.escape(str(props.get("title", "پیشرفت کار")))
            pct = max(0, min(100, int(props.get("percentage", 75))))
            show_pct = props.get("show_percentage", True)
            pct_span = f'<span class="font-mono text-primary">{pct}%</span>' if show_pct else ""
            return (
                f'<div{id_attr} class="builder-progress-bar space-y-1.5 w-full text-right {css_class}" data-widget="progress_bar"{style_attr}>'
                f'<div class="flex items-center justify-between text-xs font-semibold text-foreground"><span>{title}</span>{pct_span}</div>'
                f'<div class="h-3 w-full rounded-full bg-muted overflow-hidden"><div class="h-full bg-primary rounded-full" style="width: {pct}%;"></div></div>'
                f'</div>'
            )

        elif widget_type == "testimonial":
            author = html.escape(str(props.get("author", props.get("author_name", "نام مشتری"))))
            role = html.escape(str(props.get("role", props.get("author_role", ""))))
            company = html.escape(str(props.get("company", "")))
            quote = html.escape(str(props.get("quote", "")))
            avatar = html.escape(str(props.get("avatar_url", "/placeholder-hero.svg")))
            role_part = f"{role} - {company}" if company else role
            return (
                f'<blockquote{id_attr} class="builder-testimonial p-4 rounded-2xl border border-border/80 bg-card space-y-3 {css_class}" data-widget="testimonial"{style_attr}>'
                f'<p class="text-xs text-muted-foreground leading-relaxed italic">«{quote}»</p>'
                f'<div class="flex items-center gap-3 pt-2 border-t border-border/60">'
                f'<img src="{avatar}" alt="{author}" class="w-9 h-9 rounded-full object-cover shrink-0" loading="lazy" />'
                f'<div><div class="text-xs font-bold text-foreground">{author}</div><div class="text-[10px] text-muted-foreground">{role_part}</div></div>'
                f'</div>'
                f'</blockquote>'
            )

        elif widget_type == "alert":
            title = html.escape(str(props.get("title", "اعلان")))
            msg = html.escape(str(props.get("message", props.get("description", ""))))
            a_type = str(props.get("alert_type", "info"))
            return (
                f'<div{id_attr} class="builder-alert builder-alert-{html.escape(a_type)} p-3.5 rounded-xl border text-right space-y-1 {css_class}" data-widget="alert"{style_attr}>'
                f'<div class="text-xs font-bold">{title}</div>'
                f'<div class="text-[11px] leading-relaxed opacity-90">{msg}</div>'
                f'</div>'
            )

        elif widget_type == "call_to_action":
            title = html.escape(str(props.get("title", "اقدام به عمل")))
            desc = html.escape(str(props.get("description", "")))
            btn_label = html.escape(str(props.get("button_label", "شروع کنید")))
            btn_url = html.escape(str(props.get("button_url", "/products")))
            badge = html.escape(str(props.get("badge", "")))
            badge_html = f'<span class="inline-block px-2.5 py-0.5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold">{badge}</span>' if badge else ""
            return (
                f'<div{id_attr} class="builder-cta p-6 rounded-2xl border border-primary/20 bg-primary/5 text-center space-y-3 {css_class}" data-widget="call_to_action"{style_attr}>'
                f'{badge_html}'
                f'<h3 class="text-lg font-bold text-foreground">{title}</h3>'
                f'<p class="text-xs text-muted-foreground max-w-md mx-auto leading-relaxed">{desc}</p>'
                f'<div><a href="{btn_url}" class="inline-flex items-center justify-center px-5 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow hover:bg-primary/90 transition">{btn_label}</a></div>'
                f'</div>'
            )

        elif widget_type == "animated_headline":
            before = html.escape(str(props.get("before_text", "")))
            highlight = html.escape(str(props.get("highlighted_text", "تیتر متحرک")))
            after = html.escape(str(props.get("after_text", "")))
            return (
                f'<h2{id_attr} class="builder-animated-headline text-2xl lg:text-3xl font-extrabold text-foreground text-center py-2 {css_class}" data-widget="animated_headline"{style_attr}>'
                f'<span class="before-text">{before} </span>'
                f'<span class="highlighted-text text-primary underline decoration-wavy">{highlight}</span>'
                f'<span class="after-text"> {after}</span>'
                f'</h2>'
            )

        elif widget_type == "flip_box":
            front_title = html.escape(str(props.get("front_title", "روی کارت")))
            front_desc = html.escape(str(props.get("front_desc", "")))
            back_title = html.escape(str(props.get("back_title", "پشت کارت")))
            back_desc = html.escape(str(props.get("back_desc", "")))
            btn_text = html.escape(str(props.get("button_text", "مشاهده")))
            btn_url = html.escape(str(props.get("button_url", "#")))
            return (
                f'<div{id_attr} class="builder-flip-box p-6 rounded-2xl border border-border/80 bg-card text-center space-y-2 {css_class}" data-widget="flip_box"{style_attr}>'
                f'<h4 class="font-bold text-foreground text-base">{front_title}</h4>'
                f'<p class="text-xs text-muted-foreground">{front_desc}</p>'
                f'<div class="pt-2 border-t border-border/50">'
                f'<div class="font-bold text-xs text-primary">{back_title}</div>'
                f'<p class="text-[11px] text-muted-foreground">{back_desc}</p>'
                f'<a href="{btn_url}" class="inline-block mt-2 px-4 py-1.5 rounded-lg bg-primary text-white text-xs font-bold">{btn_text}</a>'
                f'</div>'
                f'</div>'
            )

        elif widget_type == "blockquote":
            text = html.escape(str(props.get("text", "")))
            author = html.escape(str(props.get("author", "")))
            return (
                f'<blockquote{id_attr} class="builder-blockquote border-r-4 border-primary pr-4 py-2 my-2 bg-primary/5 rounded-l-xl text-right {css_class}" data-widget="blockquote"{style_attr}>'
                f'<p class="text-xs font-medium leading-relaxed">{text}</p>'
                f'<cite class="block text-[11px] text-muted-foreground not-italic">— {author}</cite>'
                f'</blockquote>'
            )

        elif widget_type == "menu_anchor":
            anchor_id = html.escape(str(props.get("anchor_id", "section-target")))
            return f'<div id="{anchor_id}" class="builder-menu-anchor w-full h-0 opacity-0 pointer-events-none -my-1" aria-hidden="true"></div>'

        elif widget_type == "icon":
            icon_key = html.escape(str(props.get("icon", "star")))
            view = str(props.get("view", "default"))
            shape = str(props.get("shape", "circle"))
            size = int(props.get("size", 32))
            rotate = int(props.get("rotate", 0))
            url = str(props.get("url", ""))
            new_tab = bool(props.get("newTab", False))
            target_attr = ' target="_blank" rel="noopener noreferrer"' if new_tab else ""

            view_classes = "text-primary"
            if view == "stacked":
                view_classes = "bg-primary text-white shadow-sm"
            elif view == "framed":
                view_classes = "border-2 border-primary text-primary bg-transparent"

            shape_class = "rounded-full" if shape == "circle" else "rounded-xl"
            pad_style = f"padding: {round(size * 0.4)}px;" if view != "default" else ""
            rot_style = f"transform: rotate({rotate}deg);" if rotate else ""
            inline_style = f' style="{pad_style} {rot_style}"'.strip()

            inner_icon = f'<div class="inline-flex items-center justify-center {view_classes} {shape_class}"{inline_style}><span style="font-size: {size}px; line-height: 1;">★</span></div>'
            if url:
                return f'<div{id_attr} class="builder-icon inline-block {css_class}" data-widget="icon"{style_attr}><a href="{html.escape(url)}"{target_attr}>{inner_icon}</a></div>'
            return f'<div{id_attr} class="builder-icon inline-block {css_class}" data-widget="icon"{style_attr}>{inner_icon}</div>'

        elif widget_type == "icon_list":
            layout = str(props.get("layout", "vertical"))
            raw_items = props.get("items", [])
            items = raw_items if isinstance(raw_items, list) and raw_items else [
                {"text": "ارسال سریع به سراسر کشور", "icon": "truck", "url": ""},
                {"text": "ضمانت بازگشت ۷ روزه", "icon": "shield-check", "url": ""},
            ]
            list_class = "space-y-2.5" if layout != "horizontal" else "flex flex-wrap items-center gap-4 space-y-0"
            items_html = ""
            for item in items:
                text = html.escape(str(item.get("text", "")))
                url = item.get("url", "")
                text_content = f'<a href="{html.escape(str(url))}" class="hover:underline">{text}</a>' if url else f'<span>{text}</span>'
                items_html += (
                    f'<li class="flex items-center gap-2.5 text-xs text-foreground">'
                    f'<div class="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0 text-[10px]">✓</div>'
                    f'{text_content}'
                    f'</li>'
                )
            return (
                f'<ul{id_attr} class="builder-icon-list w-full text-right {list_class} {css_class}" data-widget="icon_list"{style_attr}>'
                f'{items_html}'
                f'</ul>'
            )

        elif widget_type == "price_table":
            title = html.escape(str(props.get("title", "پلن استاندارد")))
            subtitle = html.escape(str(props.get("subtitle", "")))
            price = html.escape(str(props.get("price", "۴۹۰,۰۰۰")))
            currency = html.escape(str(props.get("currency", "تومان")))
            period = html.escape(str(props.get("period", "ماهانه")))
            badge = html.escape(str(props.get("badge", "")))
            is_featured = bool(props.get("is_featured", False))
            btn_label = html.escape(str(props.get("button_label", "انتخاب و شروع پلن")))
            btn_url = html.escape(str(props.get("button_url", "/checkout")))

            featured_border = "border-primary shadow-md ring-2 ring-primary/20" if is_featured else "border-border/80"
            badge_html = f'<div class="absolute top-3 left-3 bg-primary text-white text-[10px] font-bold px-2.5 py-0.5 rounded-full">{badge}</div>' if badge else ""
            subtitle_html = f'<p class="text-[11px] text-muted-foreground">{subtitle}</p>' if subtitle else ""
            period_html = f'<span class="text-[10px] text-muted-foreground/80">/ {period}</span>' if period else ""

            features = props.get("features", [])
            features_html = ""
            if isinstance(features, list):
                for f in features:
                    f_text = html.escape(str(f.get("text", "")))
                    f_avail = bool(f.get("available", True))
                    status_class = "text-foreground font-medium" if f_avail else "text-muted-foreground line-through opacity-70"
                    icon_circle = "bg-emerald-500/10 text-emerald-600" if f_avail else "bg-muted text-muted-foreground/40"
                    icon_char = "✓" if f_avail else "–"
                    features_html += (
                        f'<li class="flex items-center gap-2">'
                        f'<div class="w-4 h-4 rounded-full flex items-center justify-center shrink-0 {icon_circle} text-[10px]">{icon_char}</div>'
                        f'<span class="{status_class}">{f_text}</span>'
                        f'</li>'
                    )

            btn_bg = "bg-primary text-white hover:bg-primary/90" if is_featured else "bg-muted/80 text-foreground hover:bg-muted"

            return (
                f'<div{id_attr} class="builder-price-table w-full max-w-sm rounded-3xl border bg-card p-6 text-right space-y-5 shadow-sm relative overflow-hidden {featured_border} {css_class}" data-widget="price_table"{style_attr}>'
                f'{badge_html}'
                f'<div class="space-y-1">'
                f'<h3 class="text-base font-extrabold text-foreground">{title}</h3>'
                f'{subtitle_html}'
                f'</div>'
                f'<div class="flex items-baseline gap-1.5 border-y border-border/60 py-4">'
                f'<span class="text-2xl font-black text-primary font-mono">{price}</span>'
                f'<span class="text-xs font-semibold text-muted-foreground">{currency}</span>'
                f'{period_html}'
                f'</div>'
                f'<ul class="space-y-2.5 text-xs">{features_html}</ul>'
                f'<a href="{btn_url}" class="block w-full text-center py-2.5 rounded-xl font-bold text-xs transition shadow-sm {btn_bg}">{btn_label}</a>'
                f'</div>'
            )

        elif widget_type == "price_list":
            sep_style = str(props.get("separator_style", "dotted"))
            raw_items = props.get("items", [])
            items = raw_items if isinstance(raw_items, list) and raw_items else [
                {"title": "مشاوره اختصاصی", "price": "۳۵۰,۰۰۰ تومان", "description": "جلسه ۱ ساعته"}
            ]
            border_cls = "border-dotted" if sep_style == "dotted" else ("border-dashed" if sep_style == "dashed" else "border-solid")
            sep_html = f'<div class="flex-1 border-b border-border/80 mx-1 {border_cls}"></div>' if sep_style != "none" else ""

            items_html = ""
            for it in items:
                t = html.escape(str(it.get("title", "")))
                p = html.escape(str(it.get("price", "")))
                d = html.escape(str(it.get("description", "")))
                desc_html = f'<p class="text-[11px] text-muted-foreground">{d}</p>' if d else ""
                items_html += (
                    f'<div class="space-y-1">'
                    f'<div class="flex items-baseline justify-between gap-3">'
                    f'<span class="text-xs font-bold text-foreground shrink-0">{t}</span>'
                    f'{sep_html}'
                    f'<span class="text-xs font-black text-primary font-mono shrink-0">{p}</span>'
                    f'</div>'
                    f'{desc_html}'
                    f'</div>'
                )
            return (
                f'<div{id_attr} class="builder-price-list w-full space-y-4 text-right {css_class}" data-widget="price_list"{style_attr}>'
                f'{items_html}'
                f'</div>'
            )

        elif widget_type == "image_box":
            img_url = html.escape(str(props.get("image_url", props.get("url", "/placeholder-hero.svg"))))
            title = html.escape(str(props.get("title", "عنوان جعبه تصویر")))
            desc = html.escape(str(props.get("description", "")))
            link = props.get("link", props.get("url_link", ""))
            pos = str(props.get("position", "top"))
            flex_cls = "flex flex-col items-center text-center" if pos == "top" else ("flex flex-row-reverse items-start gap-4 text-right" if pos == "left" else "flex flex-row items-start gap-4 text-right")
            img_html = f'<img src="{img_url}" alt="{title}" class="rounded-xl object-cover max-w-full h-auto mb-2" loading="lazy" />'
            desc_html = f'<p class="text-xs text-muted-foreground leading-relaxed">{desc}</p>' if desc else ""
            inner = (
                f'{img_html}'
                f'<div class="space-y-1">'
                f'<h3 class="font-bold text-sm text-foreground">{title}</h3>'
                f'{desc_html}'
                f'</div>'
            )
            if link:
                return f'<div{id_attr} class="builder-image-box {flex_cls} {css_class}" data-widget="image_box"{style_attr}><a href="{html.escape(str(link))}" class="block hover:opacity-90">{inner}</a></div>'
            return f'<div{id_attr} class="builder-image-box {flex_cls} {css_class}" data-widget="image_box"{style_attr}>{inner}</div>'

        elif widget_type == "toggle":
            raw_items = props.get("items", [{"title": "آیتم بازشونده ۱", "content": "توضیحات آیتم ۱"}])
            items_html = ""
            if isinstance(raw_items, list):
                for itm in raw_items:
                    t_title = html.escape(str(itm.get("title", "آیتم بازشونده")))
                    t_content = html.escape(str(itm.get("content", "")))
                    open_attr = " open" if itm.get("is_open") else ""
                    items_html += (
                        f'<details class="group rounded-xl border border-border/80 bg-card overflow-hidden"{open_attr}>'
                        f'<summary class="p-3.5 font-bold text-xs text-foreground cursor-pointer list-none flex items-center justify-between hover:bg-muted/40 transition select-none">'
                        f'<span>{t_title}</span>'
                        f'<span class="transition-transform group-open:rotate-180">▾</span>'
                        f'</summary>'
                        f'<div class="p-3.5 pt-0 text-xs text-muted-foreground border-t border-border/40 leading-relaxed">'
                        f'{t_content}'
                        f'</div>'
                        f'</details>'
                    )
            return f'<div{id_attr} class="builder-toggle space-y-2 w-full {css_class}" data-widget="toggle"{style_attr}>{items_html}</div>'

        elif widget_type == "share_buttons":
            raw_networks = props.get("networks", ["telegram", "whatsapp", "twitter", "linkedin"])
            skin = str(props.get("skin", "gradient"))
            shape = str(props.get("shape", "rounded"))
            shape_cls = "rounded-full" if shape == "circle" else ("rounded-none" if shape == "square" else "rounded-xl")

            net_labels = {
                "telegram": ("تلگرام", "bg-[#229ED9] text-white"),
                "whatsapp": ("واتس‌اپ", "bg-[#25D366] text-white"),
                "twitter": ("توییتر (X)", "bg-[#000000] text-white"),
                "linkedin": ("لینکدین", "bg-[#0077B5] text-white"),
                "facebook": ("فیس‌بوک", "bg-[#1877F2] text-white"),
                "email": ("ایمیل", "bg-muted text-foreground"),
            }
            btns_html = ""
            if isinstance(raw_networks, list):
                for net in raw_networks:
                    label, col_cls = net_labels.get(str(net), (str(net), "bg-primary text-white"))
                    btns_html += (
                        f'<button type="button" class="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold transition shadow-xs hover:opacity-90 {shape_cls} {col_cls}">'
                        f'<span>{html.escape(label)}</span>'
                        f'</button>'
                    )
            return f'<div{id_attr} class="builder-share-buttons flex flex-wrap items-center gap-2 {css_class}" data-widget="share_buttons"{style_attr}>{btns_html}</div>'

        elif widget_type == "progress_tracker":
            direction = str(props.get("direction", "horizontal"))
            track_type = str(props.get("tracker_type", "relative"))
            height_px = int(props.get("height", 4))
            styles_inline = f'height: {height_px}px;'
            if styles:
                styles_inline += " " + " ".join(styles)
            return (
                f'<div{id_attr} class="builder-progress-tracker w-full bg-muted/60 overflow-hidden rounded-full {css_class}" data-widget="progress_tracker" style="{styles_inline}"{extra_attrs}>'
                f'<div class="h-full bg-primary rounded-full transition-all duration-150" style="width: 45%;"></div>'
                f'</div>'
            )

        elif widget_type == "table_of_contents":
            title = html.escape(str(props.get("title", "فهرست محتوا")))
            items = props.get("items", [{"text": "مقدمه و بررسی اجمالی", "level": 2}, {"text": "ویژگی‌ها و مزایای کلیدی", "level": 2}, {"text": "نتیجه‌گیری", "level": 3}])
            list_html = ""
            if isinstance(items, list):
                for itm in items:
                    txt = html.escape(str(itm.get("text", "")))
                    lvl = int(itm.get("level", 2))
                    indent = "pr-4 text-xs font-medium text-muted-foreground" if lvl > 2 else "font-bold text-xs text-foreground"
                    list_html += f'<li class="{indent} hover:text-primary transition"><a href="#" onclick="return false;">• {txt}</a></li>'
            return (
                f'<nav{id_attr} class="builder-toc p-4 rounded-2xl border border-border/80 bg-card/60 space-y-2 text-right {css_class}" data-widget="table_of_contents"{style_attr}>'
                f'<h4 class="font-bold text-xs text-foreground pb-1 border-b border-border/60">{title}</h4>'
                f'<ul class="space-y-1.5 pt-1">{list_html}</ul>'
                f'</nav>'
            )

        elif widget_type == "hotspot":
            img_url = html.escape(str(props.get("image_url", "/placeholder-hero.svg")))
            alt = html.escape(str(props.get("alt", "تصویر با نقاط تعاملی")))
            spots = props.get("spots", [{"x": 30, "y": 45, "title": "نقطه ۱", "content": "توضیحات نقطه ۱"}])
            spots_html = ""
            if isinstance(spots, list):
                for s in spots:
                    x = max(0, min(100, float(s.get("x", 50))))
                    y = max(0, min(100, float(s.get("y", 50))))
                    s_title = html.escape(str(s.get("title", "")))
                    s_content = html.escape(str(s.get("content", "")))
                    spots_html += (
                        f'<div class="absolute -translate-x-1/2 -translate-y-1/2 group/spot cursor-pointer" style="left: {x}%; top: {y}%;">'
                        f'<span class="w-4 h-4 rounded-full bg-primary text-white flex items-center justify-center text-[10px] font-bold shadow-md ring-4 ring-primary/30 animate-pulse">+</span>'
                        f'<div class="absolute bottom-full right-1/2 translate-x-1/2 mb-2 hidden group-hover/spot:block w-44 p-2 bg-popover text-popover-foreground text-xs rounded-xl shadow-xl border border-border z-20 pointer-events-none">'
                        f'<div class="font-bold text-[11px] mb-0.5">{s_title}</div>'
                        f'<div class="text-[10px] text-muted-foreground leading-relaxed">{s_content}</div>'
                        f'</div>'
                        f'</div>'
                    )
            return (
                f'<div{id_attr} class="builder-hotspot relative inline-block rounded-2xl overflow-hidden max-w-full {css_class}" data-widget="hotspot"{style_attr}>'
                f'<img src="{img_url}" alt="{alt}" class="w-full h-auto block rounded-2xl" loading="lazy" />'
                f'{spots_html}'
                f'</div>'
            )

        elif widget_type == "lottie":
            url = html.escape(str(props.get("url", props.get("animation_url", "https://assets10.lottiefiles.com/packages/lf20_myejioos.json"))))
            loop = "true" if props.get("loop", True) else "false"
            autoplay = "true" if props.get("autoplay", True) else "false"
            return (
                f'<div{id_attr} class="builder-lottie flex items-center justify-center p-2 {css_class}" data-widget="lottie" data-url="{url}" data-loop="{loop}" data-autoplay="{autoplay}"{style_attr}>'
                f'<div class="w-32 h-32 rounded-2xl bg-muted/40 border border-border/80 flex flex-col items-center justify-center gap-1.5 text-muted-foreground text-xs font-mono">'
                f'<span class="text-primary font-bold text-sm">✦ Lottie</span>'
                f'<span class="text-[10px] opacity-75 truncate max-w-[100px]">{url.split("/")[-1]}</span>'
                f'</div>'
                f'</div>'
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
            top = p.top.to_css() if p.top else "0px"
            right = p.right.to_css() if p.right else (top if p.is_linked else "0px")
            bottom = p.bottom.to_css() if p.bottom else (top if p.is_linked else "0px")
            left = p.left.to_css() if p.left else (top if p.is_linked else "0px")
            parts.append(f"padding: {top} {right} {bottom} {left};")
        if base.margin:
            m = base.margin
            top = m.top.to_css() if m.top else "0px"
            right = m.right.to_css() if m.right else (top if m.is_linked else "0px")
            bottom = m.bottom.to_css() if m.bottom else (top if m.is_linked else "0px")
            left = m.left.to_css() if m.left else (top if m.is_linked else "0px")
            parts.append(f"margin: {top} {right} {bottom} {left};")
        if base.width:
            parts.append(f"width: {base.width.to_css()};")
        if base.min_height:
            parts.append(f"min-height: {base.min_height.to_css()};")
        if base.typography:
            typo = base.typography
            if typo.color:
                color = typo.color
                if color.startswith("var(--"):
                    parts.append(f"color: hsl({color});")
                else:
                    parts.append(f"color: {color};")
            if typo.font_size:
                parts.append(f"font-size: {typo.font_size.to_css()};")
            if typo.font_weight and typo.font_weight != "inherit":
                parts.append(f"font-weight: {typo.font_weight};")
            if typo.line_height:
                parts.append(f"line-height: {typo.line_height.to_css()};")
            if typo.text_align and typo.text_align != "inherit":
                parts.append(f"text-align: {typo.text_align};")
            if typo.font_family and typo.font_family != "inherit":
                parts.append(f"font-family: {typo.font_family};")
        if base.border:
            b = base.border
            if b.style and b.style != "none":
                parts.append(f"border-style: {b.style};")
                if b.color:
                    b_color = b.color
                    if b_color.startswith("var(--"):
                        parts.append(f"border-color: hsl({b_color});")
                    else:
                        parts.append(f"border-color: {b_color};")
                if b.width and b.width.top:
                    parts.append(f"border-width: {b.width.top.to_css()};")
            if b.radius:
                r = b.radius
                parts.append(f"border-radius: {r.top.to_css()} {r.right.to_css()} {r.bottom.to_css()} {r.left.to_css()};")

        if base.background and base.background.color:
            bg_color = base.background.color
            if bg_color.startswith("var(--"):
                parts.append(f"background-color: hsl({bg_color});")
            else:
                parts.append(f"background-color: {bg_color};")
        elif base.background and base.background.gradient:
            grad = base.background.gradient
            direction_css = grad.direction.replace("to-", "to ")
            parts.append(f"background-image: linear-gradient({direction_css}, {grad.from_color}, {grad.to_color});")
        elif base.background and base.background.image_url:
            parts.append(f"background-image: url('{base.background.image_url}');")
            if base.background.position:
                parts.append(f"background-position: {base.background.position};")
            if base.background.size:
                parts.append(f"background-size: {base.background.size};")

        if base.box_shadow and base.box_shadow != "none":
            parts.append(f"box-shadow: {base.box_shadow};")

        # Advanced Layout (P4)
        if base.position and base.position != "inherit":
            parts.append(f"position: {base.position};")
        if base.top:
            parts.append(f"top: {base.top.to_css()};")
        if base.bottom:
            parts.append(f"bottom: {base.bottom.to_css()};")
        if base.left:
            parts.append(f"left: {base.left.to_css()};")
        if base.right:
            parts.append(f"right: {base.right.to_css()};")
        if base.z_index is not None:
            parts.append(f"z-index: {base.z_index};")
        if base.opacity is not None:
            parts.append(f"opacity: {base.opacity};")
        if base.overflow and base.overflow != "inherit":
            parts.append(f"overflow: {base.overflow};")
        if base.display and base.display != "inherit":
            parts.append(f"display: {base.display};")
        if base.flex_direction and base.flex_direction != "inherit":
            parts.append(f"flex-direction: {base.flex_direction};")
        if base.justify_content and base.justify_content != "inherit":
            jc_map = {"start": "flex-start", "end": "flex-end", "between": "space-between", "around": "space-around", "evenly": "space-evenly"}
            parts.append(f"justify-content: {jc_map.get(base.justify_content, base.justify_content)};")
        if base.align_items and base.align_items != "inherit":
            ai_map = {"start": "flex-start", "end": "flex-end"}
            parts.append(f"align-items: {ai_map.get(base.align_items, base.align_items)};")
        if base.align_self and base.align_self != "inherit":
            as_map = {"start": "flex-start", "end": "flex-end"}
            parts.append(f"align-self: {as_map.get(base.align_self, base.align_self)};")
        if base.order is not None:
            parts.append(f"order: {base.order};")
        if base.flex_grow is not None:
            parts.append(f"flex-grow: {base.flex_grow};")
        if base.flex_wrap and base.flex_wrap != "inherit":
            parts.append(f"flex-wrap: {base.flex_wrap};")
        if base.gap:
            parts.append(f"gap: {base.gap.to_css()};")
        if base.grid_template_columns:
            parts.append(f"grid-template-columns: {base.grid_template_columns};")
        if base.opacity is not None:
            parts.append(f"opacity: {base.opacity};")
        if base.filter:
            parts.append(f"filter: {base.filter};")
        if base.box_shadow:
            parts.append(f"box-shadow: {base.box_shadow};")
        if base.transform:
            t = base.transform
            t_parts = []
            if t.rotate:
                t_parts.append(f"rotate({t.rotate}deg)")
            if t.scale:
                t_parts.append(f"scale({t.scale})")
            if t.skew_x:
                t_parts.append(f"skewX({t.skew_x}deg)")
            if t.skew_y:
                t_parts.append(f"skewY({t.skew_y}deg)")
            if t.translate_x or t.translate_y:
                t_parts.append(f"translate({t.translate_x or 0}px, {t.translate_y or 0}px)")
            if t_parts:
                parts.append(f"transform: {' '.join(t_parts)};")
        if base.mask and base.mask.shape and base.mask.shape != "none":
            m = base.mask
            parts.append(f"-webkit-mask-image: url('/masks/{m.shape}.svg'); mask-image: url('/masks/{m.shape}.svg');")
            if m.size:
                parts.append(f"mask-size: {m.size}; -webkit-mask-size: {m.size};")
            if m.position:
                parts.append(f"mask-position: {m.position}; -webkit-mask-position: {m.position};")

        return parts
