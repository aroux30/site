"""Tests for email attachments and the admin-editable template guard.

Two features, one file, because both are about what the email service will put
in a customer's inbox.

Attachments: the message has to become multipart/mixed with the alternative
pair intact. Files added before the body break the structure some clients rely
on to choose a rendering, which is why the order in ``build_mime_message`` is
load-bearing and not cosmetic.

Templates: a template is HTML an operator writes from a screen, so it is *not*
run through the content sanitizer — an operator who can script an order
confirmation is a much smaller problem than a public one. It is still refused
the things that execute in a mail client, because those cost nothing to block
and the alternative is a template that silently does nothing.
"""

from __future__ import annotations

import pytest

import app.modules.blog.domain.models  # noqa: F401
import app.modules.rbac.domain.models  # noqa: F401
import app.modules.users.domain.models  # noqa: F401
from app.modules.notifications.application.email_service import (
    MAX_ATTACHMENT_BYTES,
    EmailDeliveryError,
    SmtpConfig,
    build_mime_message,
)
from app.modules.notifications.application.email_template_service import (
    sanitize_email_template,
    validate_variables,
    variables_used,
)


def _config() -> SmtpConfig:
    return SmtpConfig(
        host="smtp.example.com",
        port=587,
        from_address="shop@example.com",
        from_name="فروشگاه",
        username="user",
        password="pass",
        use_tls=True,
    )


# ------------------------------------------------------------ attachments


def test_a_plain_message_is_still_multipart_alternative():
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="سفارش",
        html_body="<p>متن</p>",
        text_body="متن",
    )
    assert msg.get_content_subtype() == "alternative"


def test_one_attachment_makes_it_multipart_mixed():
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="فاکتور",
        html_body="<p>پیوست</p>",
        text_body="پیوست",
        attachments=[
            {"filename": "invoice.pdf", "content": b"%PDF-1.4", "content_type": "application/pdf"}
        ],
    )
    assert msg.get_content_subtype() == "mixed"
    assert [a.get_filename() for a in msg.iter_attachments()] == ["invoice.pdf"]


def test_the_body_stays_an_alternative_pair_under_the_files():
    # The reason files are added after the body rather than before: a client
    # walks the parts looking for the alternative pair, and interleaving breaks
    # that walk.
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="s",
        html_body="<p>h</p>",
        text_body="t",
        attachments=[{"filename": "a.txt", "content": b"x", "content_type": "text/plain"}],
    )
    subtypes = [p.get_content_subtype() for p in msg.iter_parts()]
    assert "alternative" in subtypes
    assert subtypes.index("alternative") == 0, "the body must come before the files"


def test_several_attachments():
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="s",
        html_body="<p>h</p>",
        text_body="t",
        attachments=[
            {"filename": "a.pdf", "content": b"a", "content_type": "application/pdf"},
            {"filename": "b.pdf", "content": b"b", "content_type": "application/pdf"},
        ],
    )
    assert sorted(a.get_filename() for a in msg.iter_attachments()) == ["a.pdf", "b.pdf"]


def test_a_missing_filename_is_skipped_not_fatal():
    # One bad entry must not lose the whole email: the message still goes out,
    # without that file.
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="s",
        html_body="<p>h</p>",
        text_body="t",
        attachments=[
            {"filename": "", "content": b"x"},
            {"filename": "ok.txt", "content": b"y", "content_type": "text/plain"},
        ],
    )
    assert [a.get_filename() for a in msg.iter_attachments()] == ["ok.txt"]


def test_non_bytes_content_is_skipped():
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="s",
        html_body="<p>h</p>",
        text_body="t",
        attachments=[{"filename": "a.txt", "content": "a string, not bytes"}],
    )
    assert list(msg.iter_attachments()) == []


def test_an_oversized_attachment_is_refused():
    # Refused here rather than by the SMTP relay: a 200 MB file read into
    # memory and then rejected by the server is the worst of both.
    with pytest.raises(EmailDeliveryError):
        build_mime_message(
            config=_config(),
            recipient="c@example.com",
            subject="s",
            html_body="<p>h</p>",
            text_body="t",
            attachments=[
                {
                    "filename": "big.bin",
                    "content": b"x" * (MAX_ATTACHMENT_BYTES + 1),
                }
            ],
        )


def test_an_undeclared_type_falls_back_to_octet_stream():
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="s",
        html_body="<p>h</p>",
        text_body="t",
        attachments=[{"filename": "a.unknownext", "content": b"x"}],
    )
    part = next(msg.iter_attachments())
    assert part.get_content_type() == "application/octet-stream"


def test_persian_filenames_survive():
    # Invoice names in an Iranian store are Persian; a mangled name makes the
    # attachment useless even though the bytes arrived.
    msg = build_mime_message(
        config=_config(),
        recipient="c@example.com",
        subject="s",
        html_body="<p>h</p>",
        text_body="t",
        attachments=[{"filename": "فاکتور-۱۴۰۴.pdf", "content": b"x", "content_type": "application/pdf"}],
    )
    assert next(msg.iter_attachments()).get_filename() == "فاکتور-۱۴۰۴.pdf"


# ------------------------------------------------------- template guard


@pytest.mark.parametrize(
    "hostile",
    [
        "<p>ok</p><script>fetch('/x')</script>",
        "<p>ok</p><SCRIPT>x</SCRIPT>",
        "<iframe src='https://evil'></iframe>",
        "<object data='x'></object>",
        "<embed src='x'>",
        "<base href='https://evil'>",
        "<link rel=stylesheet href='https://evil/x.css'>",
        "<form action='https://evil'><input></form>",
    ],
)
def test_executing_markup_is_refused(hostile):
    with pytest.raises(Exception):
        sanitize_email_template(hostile)


@pytest.mark.parametrize(
    "hostile",
    [
        '<a href="javascript:alert(1)">x</a>',
        '<a href="JavaScript:alert(1)">x</a>',
        '<img src="data:text/html,<script>x</script>">',
        "<a href='vbscript:msgbox'>x</a>",
        '<img src="file:///etc/passwd">',
        '<body background="javascript:x">',
    ],
)
def test_dangerous_url_schemes_are_refused(hostile):
    with pytest.raises(Exception):
        sanitize_email_template(hostile)


@pytest.mark.parametrize(
    "safe",
    [
        '<div dir="rtl"><p style="color:#111">سلام</p></div>',
        '<table><tr><td>۱۲۰ تومان</td></tr></table>',
        '<a href="https://example.com/order/1">مشاهده سفارش</a>',
        '<img src="https://cdn.example.com/logo.png" alt="نشان">',
        '<p style="text-align:center">با تشکر</p>',
    ],
)
def test_ordinary_email_markup_is_kept(safe):
    # The guard must not become the reason an email cannot be styled: a
    # template that lost its table and its colours is not usable, and an
    # operator would work around it.
    assert sanitize_email_template(safe) == safe


def test_an_empty_template_is_refused():
    with pytest.raises(Exception):
        sanitize_email_template("   ")


def test_an_oversized_template_is_refused():
    with pytest.raises(Exception):
        sanitize_email_template("<p>x</p>" * 60_000)


# --------------------------------------------------------- the variables


def test_variables_are_extracted_in_first_use_order():
    assert variables_used("{{order_number}} {{amount}} {{order_number}}") == [
        "order_number",
        "amount",
    ]


def test_variables_in_the_subject_count():
    assert variables_used("<p>x</p>", "سفارش {{order_number}}") == ["order_number"]


def test_spaced_braces_are_accepted():
    # send_from_template accepts "{{ name }}", so the linter must too.
    assert variables_used("{{ amount }}") == ["amount"]


def test_variable_names_are_validated():
    assert validate_variables(["a", "b_2", "_c"]) == ["a", "b_2", "_c"]
    with pytest.raises(Exception):
        validate_variables(["2bad"])
    with pytest.raises(Exception):
        validate_variables(["has space"])


def test_duplicate_variables_collapse_preserving_order():
    assert validate_variables(["b", "a", "b"]) == ["b", "a"]


def test_no_variables_is_an_empty_list():
    assert validate_variables(None) == []
    assert validate_variables([]) == []


# --------------------------------------------------------- route ordering


def test_preview_is_not_shadowed_by_the_name_parameter():
    """``/admin/email-templates/preview`` must not be read as name="preview".

    A path-parameter route declared first swallows every literal path under
    it: the preview request would become a template lookup for a template named
    "preview" and 404, so the editor's preview pane would silently never work.
    """
    import app.modules.notifications.api.routes as routes

    order = [
        getattr(r, "path", "")
        for r in routes.router.routes
        if "email-templates" in getattr(r, "path", "")
    ]
    assert order[0] == "/admin/email-templates"
    assert "/admin/email-templates/preview" in order
    # The literal has to come before the parameterised path.
    assert order.index("/admin/email-templates/preview") < order.index(
        "/admin/email-templates/{name}"
    )


# --------------------------------------- the attachment reaches a real flow


def test_the_order_confirmation_passes_an_attachment():
    """P2 gap 25 is only closed when a real flow sends a file.

    ``build_mime_message`` accepting an ``attachments`` argument is a
    capability, not a feature: nothing in the app passed one, so no invoice,
    report or receipt had ever been attached to an email. Asserted on the call
    site because the unit tests on the builder pass either way.
    """
    import inspect

    from app.modules.automation.application import outbox_worker

    src = inspect.getsource(outbox_worker)
    assert "attachments=" in src, (
        "the order-confirmation email passes no attachment, so the invoice is "
        "never attached and gap 25 is not actually closed"
    )
    assert "_invoice_attachment" in src


def test_the_attachment_is_built_by_a_helper_not_inlined():
    import inspect

    from app.modules.automation.application import outbox_worker

    src = inspect.getsource(outbox_worker)
    assert "def _invoice_attachment(" in src, (
        "the attachment has to come from a helper: it needs its own failure "
        "handling so a missing PDF cannot fail the whole outbox message"
    )


def test_the_attachment_helper_never_raises():
    """A failure here must be soft: the email goes without its file.

    The alternative is re-queuing an outbox message for a customer who has
    already seen the in-app notification, every retry, for a missing PDF.
    """
    import inspect

    from app.modules.automation.application import outbox_worker

    src = inspect.getsource(outbox_worker._invoice_attachment)
    # The whole body after the docstring is inside a try.
    body = src.split('"""')[-1]
    assert "except Exception" in body, "a PDF read failure must not raise"
    assert "return None" in body, "and must report no attachment instead"
