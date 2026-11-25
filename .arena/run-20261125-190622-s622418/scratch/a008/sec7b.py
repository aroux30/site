target = ".arena/run-20261125-190622-s622418/r0/a008.md"
part = """#### 7.2 Backend Pytest Suite: `backend/app/tests/unit/test_ast_compiler_interactive_widgets.py`

```python
import pytest
from app.modules.content.application.ast_compiler import ASTCompiler
from app.modules.content.domain.builder_ast import BuilderElement, PageAST, ResponsiveStyles, DeviceStyle

def test_ast_compiler_form_container_with_honeypot_and_xss_protection():
    form_element = BuilderElement(
        id="el_form_test",
        name="فرم ثبت نام",
        type="container",
        widget_type="form_container",
        widget_props={
            "submit_url": "/api/v1/forms/submit?ref=test",
            "success_message": "با موفقیت ثبت شد <script>alert(1)</script>",
            "error_message": "خطا رخ داده است",
        },
        children=[
            BuilderElement(
                id="el_f_name",
                name="نام",
                type="widget",
                widget_type="form_input",
                widget_props={"label": "نام کامل", "name": "full_name", "required": True},
            ),
            BuilderElement(
                id="el_f_agree",
                name="تایید",
                type="widget",
                widget_type="form_checkbox",
                widget_props={"label": "شرایط را می‌پذیرم", "name": "agree", "checked": True},
            ),
        ]
    )
    ast = PageAST(schema_version=1, root_elements=[form_element])
    compiled_html = ASTCompiler.compile(ast)

    # Assertions
    assert '<form' in compiled_html
    assert 'data-form-container="true"' in compiled_html
    assert 'action="/api/v1/forms/submit?ref=test"' in compiled_html
    assert 'name="_hp_website"' in compiled_html
    assert 'display:none !important;' in compiled_html
    assert '<script>' not in compiled_html  # XSS neutralization
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in compiled_html
    assert 'name="full_name"' in compiled_html
    assert 'required' in compiled_html
    assert 'type="checkbox"' in compiled_html
    assert 'checked' in compiled_html

def test_ast_compiler_accordion_and_tabs_rendering():
    accordion = BuilderElement(
        id="el_acc_test",
        name="آکاردئون",
        type="widget",
        widget_type="accordion",
        widget_props={
            "items": [
                {"title": "پرسش ۱", "content": "پاسخ مشروح ۱", "default_open": True},
                {"title": "پرسش ۲", "content": "پاسخ مشروح ۲", "default_open": False},
            ]
        }
    )
    ast = PageAST(schema_version=1, root_elements=[accordion])
    compiled_html = ASTCompiler.compile(ast)

    assert '<details' in compiled_html
    assert '<summary' in compiled_html
    assert 'پرسش ۱' in compiled_html
    assert 'پاسخ مشروح ۱' in compiled_html
    assert 'data-widget="accordion"' in compiled_html

def test_ast_compiler_countdown_ssr_precalculated_blocks():
    countdown = BuilderElement(
        id="el_cd_test",
        name="شمارنده",
        type="widget",
        widget_type="countdown",
        widget_props={
            "title": "حراج پایان فصل",
            "target_date": "2027-12-31T23:59:59Z",
        }
    )
    ast = PageAST(schema_version=1, root_elements=[countdown])
    compiled_html = ASTCompiler.compile(ast)

    assert 'data-widget="countdown"' in compiled_html
    assert 'حراج پایان فصل' in compiled_html
    assert 'روز' in compiled_html
    assert 'ساعت' in compiled_html
    assert 'دقیقه' in compiled_html
    assert 'ثانیه' in compiled_html
    assert 'dir="ltr"' in compiled_html
```

"""
with open(target, "a", encoding="utf-8") as f:
    f.write(part)
print("Part 7B appended successfully")
