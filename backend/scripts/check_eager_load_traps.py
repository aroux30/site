"""Guard: no response schema may read a lazy relationship from an ORM object.

This class of break 500s a page and looks like data loss. The response schema
carries ``from_attributes=True``, so ``Schema.model_validate(row)`` makes
pydantic fetch **every** field it can find on the ORM object — including
relationship attributes. When one of those relationships is ``lazy="select"``,
that fetch is blocking IO issued from a sync context inside a running asyncio
loop, and SQLAlchemy raises ``MissingGreenlet``.

The symptom is silent and misleading: the request 500s only when a row happens
to carry the relationship. With one uncategorized post the blog list returned
200; as soon as a single post had a category, ``GET /admin/blog/posts`` and
``GET /blog/posts`` both returned 500 while the table still showed 15 posts.
The list appeared "empty" rather than broken.

Two shapes are checked, because both trigger it:

1. ``Schema.model_validate(obj)`` where ``obj.<something>`` is an ORM attribute.
2. Any other hand-off of an ORM instance into pydantic (a bare
   ``model_validate``, or a schema field typed as the ORM class), which pydantic
   resolves through the same attribute reads.

A relationship is "lazy" when its mapper is anything other than selectin,
subquery or joined (``lazy="raise"`` also counts: it turns a silent IO into a
loud error, so it must not be reached either).

Run:  cd backend && PYTHONPATH=. python scripts/check_eager_load_traps.py
Exit: 0 when no trap was found, 1 when at least one was.
"""

from __future__ import annotations

import ast
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(BACKEND, "app")

#: Relationship mapper strategies that are safe to let pydantic read: they are
#: loaded as part of the original query, so touching them costs no extra IO and
#: never reaches a blocking IO path.
EAGER_LAZY = {"selectin", "subquery", "joined", "immediate"}

#: Modules under this path are not application code.
SKIP_DIR_PARTS = {"__pycache__", "alembic", "versions", "tests", "_archived"}


def _iter_python_files() -> list[str]:
    out: list[str] = []
    for root, dirs, files in os.walk(APP):
        dirs[:] = [d for d in dirs if d not in SKIP_DIR_PARTS]
        for name in files:
            if name.endswith(".py"):
                out.append(os.path.join(root, name))
    return out


def _lazy_relationships() -> dict[str, set[tuple[str, str]]]:
    """Map every ORM class to the relationships that are not eagerly loaded.

    Keys are fully-qualified class names so a schema can be matched against the
    models it might be handed.
    """
    sys.path.insert(0, BACKEND)
    try:
        import importlib
        import pkgutil

        import app.modules as _modules

        for m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
            try:
                importlib.import_module(m.name)
            except Exception:  # noqa: BLE001 - an unimportable module is not our subject
                pass

        from app.core.database.base import Base
    except Exception as exc:  # noqa: BLE001
        print(f"could not load the ORM registry: {exc}")
        return {}

    out: dict[str, set[tuple[str, str]]] = {}
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        name = f"{cls.__module__}.{cls.__name__}"
        lazy = set()
        for rel_name, rel in mapper.relationships.items():
            strategy = rel.lazy
            if strategy in EAGER_LAZY:
                continue
            # "raise" is not eager either: reading it would raise, so treat it
            # as a trap rather than a safe field.
            lazy.add((name, rel_name))
        if lazy:
            out[name] = lazy
    return out


def _attribute_reads(tree: ast.Module) -> dict[str, set[str]]:
    """Map each local variable name to the attribute names read off it."""
    out: dict[str, set[str]] = {}

    def visit(node: ast.AST, root: str | None) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name):
                base = root or child.value.id
                out.setdefault(base, set()).add(child.attr)
                visit(child, base)
            else:
                visit(child, root)

    visit(tree, None)
    return out


def _variable_models(tree: ast.Module, models: dict[str, str]) -> dict[str, set[str]]:
    """Infer which ORM class each local variable holds.

    Two sources, both conservative:

    1. An annotated assignment or parameter: ``post: BlogPost`` / ``def f(post:
       BlogPost)``.
    2. A variable assigned straight from a query: ``post = (await
       db.execute(select(BlogPost...))).scalar_one()``.

    Only a name the module actually binds to one of those counts. Guessing from
    a variable's *name* is how this gate reported four false positives the first
    time it ran.
    """
    out: dict[str, set[str]] = {}

    def note(name: str, ann: ast.AST | None) -> None:
        if ann is None:
            return
        text = ast.unparse(ann).replace("|", " ").replace("[", " ").replace("]", " ")
        for token in text.split():
            simple = token.split(".")[-1]
            if simple in models:
                out.setdefault(name, set()).add(simple)

    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            note(node.target.id, node.annotation)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
                note(arg.arg, arg.annotation)
            if args.vararg:
                note(args.vararg.arg, args.vararg.annotation)

    # `x = (await db.execute(select(Model ...))).scalar_one()` and friends.
    selected: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "select"
            and node.args
        ):
            for arg in node.args:
                text = ast.unparse(arg).split(".")[-1]
                if text in models:
                    selected.add(text)
    if selected:
        for node in ast.walk(tree):
            if (
                isinstance(node, (ast.Assign, ast.AnnAssign))
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Attribute)
                and node.value.func.attr
                in {"scalar_one", "scalar_one_or_none", "scalar", "first", "one", "all"}
            ):
                text = ast.unparse(node.value).lower()
                if any(f"select({m.lower()}" in text.replace(" ", "") for m in selected) or any(
                    m.lower() in text for m in selected
                ):
                    target = node.targets[0] if isinstance(node, ast.Assign) else node.target
                    if isinstance(target, ast.Name):
                        out.setdefault(target.id, set()).update(selected)
    return out


def _attribute_chains(node: ast.expr):
    """Every ``var.attr[.attr...]`` chain anywhere inside ``node``.

    Composite arguments are the hole a live 500 slipped through
    (2026-10-10): ``sorted(row.billings or [], ...)`` and
    ``len(row.billings)`` wrap the attribute read in a BoolOp/Call, and the
    old walker only looked at arguments that were themselves an
    ``ast.Attribute``. Subscribing expressions are descended into so the
    read is still found.
    """
    for child in ast.walk(node):
        if not isinstance(child, ast.Attribute):
            continue
        chain: list[str] = []
        cursor: ast.expr = child
        while isinstance(cursor, ast.Attribute):
            chain.append(cursor.attr)
            cursor = cursor.value
        if isinstance(cursor, ast.Name) and chain:
            chain.reverse()
            yield cursor.id, chain


def _objects_in(
    args: list[ast.expr],
    attr_reads: dict[str, set[str]],
    var_models: dict[str, set[str]],
    lazy_simple: set[tuple[str, str]],
):
    """Yield (model, lazy relationship names, source text) for each ORM object.

    Walks the argument's attribute chain back to the root variable and asks the
    ORM mapper whether the last hop is a relationship on that variable's class.
    """
    for arg in args:
        for root, chain in _attribute_chains(arg):
            models_here = var_models.get(root, set())
            for model in models_here:
                rels = [a for a in chain if (model, a) in lazy_simple]
                if rels:
                    yield model, sorted(set(rels)), ast.unparse(arg)


def _schema_field_classes(tree: ast.Module, orm_classes: set[str]) -> dict[str, set[str]]:
    """Map each pydantic BaseModel subclass to the ORM classes its fields name.

    Scoped to pydantic schemas on purpose. An ORM model class declares its own
    relationships as annotated attributes, and those are read by SQLAlchemy
    through its own machinery — never through pydantic's ``from_attributes`` —
    so a model file is not a trap site. Letting one in reported 13 findings
    that were all noise.

    Only names that are genuinely the ORM class count. A same-named local
    definition wins: ``ContentType = Literal["post", "page"]`` in the search
    schemas is a string alias, not ``content.domain.builder.ContentType``, and
    treating the name alone as the model produced four findings that were all
    wrong.
    """
    # Names bound in this module to something that is not a class: type aliases,
    # constants, imported functions. A field typed with one of these can never
    # be an ORM attribute.
    not_a_model: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    not_a_model.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                not_a_model.add(node.target.id)

    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if node.name in orm_classes:
            continue  # an ORM model: its relationships are SQLAlchemy's business
        bases = {ast.unparse(b) for b in node.bases}
        if not any("BaseModel" in b for b in bases):
            continue
        refs: set[str] = set()
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.AnnAssign) and stmt.annotation is not None:
                ref = ast.unparse(stmt.annotation)
                for token in ref.replace("[", " ").replace("]", " ").replace("|", " ").split():
                    token = token.split(".")[-1]
                    if token[:1].isupper() and token not in not_a_model and token in orm_classes:
                        refs.add(token)
        if refs:
            out[node.name] = refs
    return out


def _model_classes() -> dict[str, str]:
    """Map a bare class name to its fully-qualified name."""
    sys.path.insert(0, BACKEND)
    try:
        import importlib
        import pkgutil

        import app.modules as _modules

        for m in pkgutil.walk_packages(_modules.__path__, "app.modules."):
            try:
                importlib.import_module(m.name)
            except Exception:  # noqa: BLE001
                pass

        from app.core.database.base import Base
    except Exception:  # noqa: BLE001
        return {}
    return {
        mapper.class_.__name__: f"{mapper.class_.__module__}.{mapper.class_.__name__}"
        for mapper in Base.registry.mappers
    }


def main() -> int:
    lazy_rels = _lazy_relationships()
    if not lazy_rels:
        print("no lazy relationships found; the registry did not load")
        return 1

    by_fq = {rel for rels in lazy_rels.values() for rel in rels}
    models = _model_classes()
    orm_classes = set(models)
    model_simple = {
        simple
        for simple, fq in models.items()
        if fq in lazy_rels
    }
    # (model, relationship) keyed by simple model name for cheap matching.
    lazy_simple = {
        (fq.rsplit(".", 1)[-1], rel_name)
        for fq, rel_name in by_fq
    }

    findings: list[str] = []

    for path in _iter_python_files():
        rel_path = os.path.relpath(path, BACKEND)
        try:
            source = open(path, encoding="utf-8").read()
            tree = ast.parse(source, filename=path)
        except SyntaxError as exc:
            print(f"  (skipped, unparseable: {exc})")
            continue

        schema_refs = _schema_field_classes(tree, orm_classes)
        # Which attributes are read on which local variable, and which of those
        # attributes is a lazy relationship of an ORM class. This is what makes
        # `post.category` resolve: `post` comes from a query over BlogPost, and
        # `category` is a lazy relationship on it.
        attr_reads = _attribute_reads(tree)
        var_models = _variable_models(tree, models)

        for node in ast.walk(tree):
            # Case 1: Schema.model_validate(obj.attr) — hand a whole ORM object
            # to pydantic and it reads every attribute it can reach.
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "model_validate"
                and isinstance(node.func.value, ast.Name)
                and node.args
            ):
                schema = node.func.value.id
                for model, rels, chain in _objects_in(node.args, attr_reads, var_models, lazy_simple):
                    findings.append(
                        f"{rel_path}:{node.lineno}: {schema}.model_validate({chain}) hands a "
                        f"{model} to pydantic, which will read its lazy "
                        f"relationship(s) {', '.join(rels)}"
                    )

            # Case 2: a field typed as the ORM class. from_attributes resolves
            # the attribute on the same lazy IO path.
            for schema, refs in schema_refs.items():
                for model in sorted(refs & model_simple):
                    rels = sorted(r for m, r in lazy_simple if m == model)
                    if not rels:
                        continue
                    for stmt in ast.walk(tree):
                        if (
                            isinstance(stmt, ast.AnnAssign)
                            and stmt.annotation is not None
                            and model in ast.unparse(stmt.annotation).replace("|", " ")
                        ):
                            findings.append(
                                f"{rel_path}:{stmt.lineno}: {schema}."
                                f"{getattr(stmt.target, 'id', '?')} is typed as the ORM "
                                f"class {model}, so from_attributes reads its lazy "
                                f"relationship(s) {', '.join(rels)}"
                            )

    print("eager-load traps")
    print("-" * 68)
    if findings:
        for f in sorted(set(findings)):
            print(f"  FAIL {f}")
        print("-" * 68)
        print(f"{len(set(findings))} trap(s). A lazy relationship read from a")
        print("response schema raises MissingGreenlet under asyncio and 500s the")
        print("request. Build the schema field by field, or eager-load the")
        print("relationship in the query.")
        return 1

    print(f"  no trap: {len(model_simple)} model(s) checked, "
          f"{len(lazy_simple)} lazy relationship(s) known")
    print("-" * 68)
    print("pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
