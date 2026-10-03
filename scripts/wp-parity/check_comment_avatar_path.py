"""Guard: every comment response must be built by `_build_response`.

A guest comment used to 500 on every storefront. ``BlogCommentResponse``
deliberately omits ``author_email`` — a public reader has no business receiving
it — and the avatar pass read that field off the response anyway, so
``_attach_avatars`` raised AttributeError for any comment without a user row,
which on a storefront is most of them.

The fix moved the email into an instance map that only `_build_response`
populates. That works exactly as long as every path that hands a response to
`_attach_avatars` went through `_build_response`, and nothing on the type system
or the linter notices when one stops doing so.

So this asserts the single-chokepoint rule: no direct `model_validate(comment)`
outside `_build_response` itself.

    python scripts/wp-parity/check_comment_avatar_path.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "backend" / "app" / "modules" / "blog" / "application" / "comment_service.py"
SCHEMAS = ROOT / "backend" / "app" / "modules" / "blog" / "schemas" / "blog.py"


def _class_span(tree: ast.Module, name: str) -> tuple[int, int] | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node.lineno, node.end_lineno or node.lineno
    return None


def main() -> int:
    failures: list[str] = []
    tree = ast.parse(SERVICE.read_text(encoding="utf-8"))

    # 1. The schema really does withhold the email — if that ever changes, the
    #    whole workaround is obsolete and should be removed, not extended.
    #    Read off the AST rather than slicing the text: the docstring above the
    #    class mentions author_email while describing the omission, so a text
    #    search reports a field that is not there.
    schema_tree = ast.parse(SCHEMAS.read_text(encoding="utf-8"))
    public_cls = next(
        (
            n
            for n in ast.walk(schema_tree)
            if isinstance(n, ast.ClassDef) and n.name == "BlogCommentResponse"
        ),
        None,
    )
    if public_cls is None:
        failures.append("could not find BlogCommentResponse in the backend schema")
    else:
        fields = {
            n.target.id
            for n in public_cls.body
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
        }
        if "author_email" in fields:
            failures.append(
                "BlogCommentResponse now carries author_email, so the avatar side "
                "table is dead weight — delete it rather than keeping two ways to "
                "reach the email"
            )

    # 2. Only `_build_response` may call model_validate on a comment row. Its
    #    own two calls are the implementation, not a bypass. Matched on the
    #    enclosing function name, and over both FunctionDef and AsyncFunctionDef
    #    — matching only the async form missed the definition after it lost its
    #    @staticmethod and became a plain `def`, so the guard flagged the very
    #    function it exists to protect.
    allowed: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "_build_response"
        ):
            allowed.update(
                n.lineno for n in ast.walk(node) if hasattr(n, "lineno")
            )

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "model_validate"
            and isinstance(node.func.value, ast.Name)
            and "Comment" in node.func.value.id
            and node.lineno not in allowed
        ):
            failures.append(
                "line %d builds a comment response with %s.model_validate(...) "
                "directly; route it through _build_response so the avatar pass "
                "still finds the author email"
                % (node.lineno, node.func.value.id)
            )

    # 3. The actual 500. The guest email may be read from exactly one place
    #    inside `_attach_avatars`: the map `_build_response` fills. An earlier
    #    version exempted the name `comment` on the theory that it was the model
    #    row — but the loop iterates responses, so `comment` *is* the thing that
    #    has no such field. A peer session proved the hole by injecting
    #    `self._email_by_comment.get(str(comment.id)) or comment.author_email`:
    #    the map stays referenced, so the guard passed, and the first guest
    #    comment still raised AttributeError. So no exemption at all — any
    #    `.author_email` in this function is a bug, whatever it is read from.
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != "_attach_avatars":
            continue
        for call in ast.walk(node):
            if isinstance(call, ast.Attribute) and call.attr == "author_email":
                owner = ast.unparse(call.value)
                failures.append(
                    "line %d reads .author_email off %s inside _attach_avatars; "
                    "the comment objects here are BlogCommentResponse, which does "
                    "not carry that field, so a guest comment 500s. Read it from "
                    "self._email_by_comment instead." % (call.lineno, owner)
                )
        if "self._email_by_comment" not in ast.unparse(node):
            failures.append(
                "_attach_avatars no longer reads from the staged email map, so the "
                "guest Gravatar fallback is either gone or reading the response"
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d problem(s)." % len(failures))
        return 1

    print("PASS: every comment response goes through _build_response, and the avatar "
          "pass reads the email from the map, not off a response.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
