"""Report duplicate and dangling revision identifiers across alembic migrations.

`ast` rather than a regex: `down_revision` is often a tuple spanning several
lines, and a regex over the file collects every quoted string in it — 2,415
"dangling references" the first time this was run, all of them column names.

    python scripts/audit_migration_graph.py [path/to/alembic/versions]
"""
import ast
import os
import sys


def collect(versions_dir):
    defined = {}      # revision id -> filename
    parents = {}      # filename -> list of parent ids
    for name in sorted(os.listdir(versions_dir)):
        if not name.endswith(".py"):
            continue
        path = os.path.join(versions_dir, name)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError as exc:
            print(f"UNPARSEABLE {name}: {exc}")
            continue
        rev = None
        downs = []
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id == "revision" and isinstance(node.value, ast.Constant):
                    rev = node.value.value
                elif target.id == "down_revision":
                    if node.value is None or (
                        isinstance(node.value, ast.Constant) and node.value.value is None
                    ):
                        downs = []
                    elif isinstance(node.value, ast.Constant):
                        downs = [str(node.value.value)]
                    elif isinstance(node.value, (ast.Tuple, ast.List)):
                        downs = [
                            str(e.value)
                            for e in node.value.elts
                            if isinstance(e, ast.Constant)
                        ]
        if rev:
            defined.setdefault(rev, []).append(name)
        parents[name] = downs
    return defined, parents


def main():
    root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    versions = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "backend", "alembic", "versions")
    defined, parents = collect(versions)

    dupes = {r: f for r, f in defined.items() if len(f) > 1}
    dangling = []
    for name, downs in parents.items():
        for d in downs:
            if d not in defined:
                dangling.append((name, d))

    print(f"revisions defined: {len(defined)} across {len(parents)} files")
    print(f"duplicate ids: {len(dupes)}")
    for r, files in sorted(dupes.items()):
        print(f"  {r}")
        for f in files:
            print(f"     {f}")
    print(f"dangling down_revision references: {len(dangling)}")
    for name, d in sorted(dangling):
        print(f"  {name} -> {d}")

    return 1 if dupes or dangling else 0


if __name__ == "__main__":
    sys.exit(main())