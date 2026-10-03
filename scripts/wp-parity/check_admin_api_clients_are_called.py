"""Guard: an admin API client with no caller is not a feature.

P0 "کاربران: UI انتساب نقش به کاربر". The routes and the typed client both
existed — `assignUserRoles`, `removeUserRoles`, `getUserRoles` — with **zero
callers** anywhere in the app. A complete, working feature an operator cannot
reach.

That shape has appeared in this codebase more than once, and it is the single
most expensive kind of gap to leave in place: everything is written, everything
is tested, and the store is no better off than if none of it existed. Nobody
notices from reading the code, because every layer is present.

So this is not "does the client exist" — it is "does something call it". The
client is the one file allowed to mention the name; every other file mentioning
it is a consumer, and the count is what the guard asserts.

    python scripts/wp-parity/check_admin_api_clients_are_called.py
"""

from __future__ import annotations

import ast
import io
import re
import sys
from pathlib import Path

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(__file__))
import console_safe  # noqa: F401  — idempotent. A plain TextIOWrapper
# here is closed by the next module that wraps stdout, which is how a test
# that imports a guard ends up dying on "I/O operation on closed file".

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
LIB = FRONTEND / "lib" / "api"

#: (label, file defining the symbol, exported symbol). A symbol with no caller
#: outside its own file is a feature no operator can reach.
CLIENT_SYMBOLS: tuple[tuple[str, str, str], ...] = (
    ("assign a role to a user", "rbac.ts", "assignUserRoles"),
    ("remove a role from a user", "rbac.ts", "removeUserRoles"),
    ("read a user's roles", "rbac.ts", "getUserRoles"),
)

#: Where a call counts. Everything under app/ and components/ is shipped UI;
#: lib/ is not, because a client in a library that only another client calls is
#: the same gap one layer down.
CONSUMER_ROOTS = (FRONTEND / "app", FRONTEND / "components", FRONTEND / "hooks")


def _walk(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [p for p in root.rglob("*.ts*") if p.is_file()]


def _without_comments(text: str) -> str:
    """The source with block comments blanked out, line structure preserved.

    A JSX element named in a comment is not a render site, and a guard that reads
    one as a render site passes on a component that nothing mounts. Stripped
    rather than parsed because the rest of the file is not valid Python AST, and
    a TypeScript-aware parser is not available here.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:end]))
            i = end
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(" " * (end - i))
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _called_in_typescript(text: str, symbol: str) -> bool:
    """Whether ``symbol`` is *called* in already-decommented TypeScript.

    Two forms, because both are how this codebase writes it:
    ``rbacApi.assignUserRoles(...)`` and a bare ``assignUserRoles(...)``. A
    definition or an import does not match either — they are followed by a space
    or a brace, not an open paren.
    """
    return bool(
        re.search(rf"\.{re.escape(symbol)}\s*\(", text)
        or re.search(rf"(?<![\w.]){re.escape(symbol)}\s*\(", text)
    )


def main() -> int:
    failures: list[str] = []
    consumers: list[Path] = []
    for root in CONSUMER_ROOTS:
        consumers.extend(_walk(root))
    # Skip Next.js route files that only re-export: a `export *` from a page does
    # not call anything. Counting them would let a barrel file stand in for a UI.
    consumers = [
        p for p in consumers if not re.search(r"^\s*export\s+\*\s+from", p.read_text(encoding="utf-8"), re.M)
    ]

    for label, filename, symbol in CLIENT_SYMBOLS:
        path = LIB / filename
        if not path.is_file():
            failures.append("%s: %s does not exist" % (label, path))
            continue

        defined = re.search(
            r"^\s*(?:export\s+const|const)\s+(\w+)\s*=\s*\{", path.read_text(encoding="utf-8"), re.M
        )
        if not defined or not re.search(rf"\b{re.escape(symbol)}\s*:", path.read_text(encoding="utf-8")):
            failures.append(
                "%s: %s no longer defines %s, so the endpoint behind it is "
                "unreachable from the admin" % (label, path.name, symbol)
            )
            continue

        # A call, not a mention — and not even a mention-in-a-comment.
        #
        # `import { assignUserRoles }` followed by nothing is the exact shape that
        # made this gap. Commenting the call out and leaving the name in a comment
        # is the next one down, and a regex is blind to it, so the call is located
        # through the syntax tree: a Comment node cannot satisfy it.
        #
        # The client's own file is excluded from the search explicitly rather than
        # by directory, because a re-export barrel under lib/ would otherwise
        # satisfy every symbol forever.
        # Located structurally where possible, textually where the file is
        # TypeScript (which ast.parse rejects). A `//`-commented-out call is
        # excluded by the text form too: the name is followed by `(`, but the
        # line before it starts a comment.
        callers = []
        for p in consumers:
            text = p.read_text(encoding="utf-8")
            if not re.search(rf"\b{re.escape(symbol)}\b", text):
                continue
            try:
                tree = ast.parse(text)
            except SyntaxError:
                tree = None
            if tree is not None:
                called = any(
                    isinstance(n, ast.Call)
                    and (
                        (isinstance(n.func, ast.Attribute) and n.func.attr == symbol)
                        or (isinstance(n.func, ast.Name) and n.func.id == symbol)
                    )
                    for n in ast.walk(tree)
                )
            else:
                called = _called_in_typescript(_without_comments(text), symbol)
            if called:
                callers.append(p)
        if not callers:
            failures.append(
                "%s: %s has no call under app/, components/ or hooks/ -- the "
                "endpoint and the client both work and no operator can reach "
                "them" % (label, symbol)
            )

    # And the editor itself. The symbol-level check above is satisfied by the
    # editor's own calls, so a component that is complete, correct and rendered
    # nowhere passes it — the file exists, the endpoints work, and no operator
    # ever sees the screen. That is the same gap one component up, and the two
    # assertions are independent on purpose.
    editor = FRONTEND / "components" / "admin" / "users" / "user-roles-editor.tsx"
    if editor.is_file():
        rendered = [
            p
            for p in consumers
            if p != editor
            and re.search(
                r"<UserRolesEditor\b",
                _without_comments(p.read_text(encoding="utf-8")),
            )
        ]
        if not rendered:
            failures.append(
                "the role-assignment editor is not rendered by any admin screen, so "
                "the whole feature is unreachable even though it is built"
            )

    for f in failures:
        print("FAIL: %s" % f)
    if failures:
        print("")
        print("%d admin client(s) are shipped but unreachable." % len(failures))
        return 1
    print(
        "PASS: every role-assignment client is called by shipped UI (%d file(s) scanned)."
        % len(consumers)
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
