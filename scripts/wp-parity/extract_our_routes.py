"""Extract our backend's real route inventory via AST (no server boot needed)."""

import ast
import collections
import json
import os
import re
import sys

ROOT = r"C:\Users\Administrator\Desktop\site"
HTTP = {"get", "post", "put", "patch", "delete", "head", "options", "api_route"}


def literal(node):
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def walk_file(path):
    """Yield (lineno, method, path, func_name, deps) for every route decorator."""
    try:
        src = open(path, encoding="utf-8", errors="ignore").read()
        tree = ast.parse(src)
    except Exception:
        return
    lines = src.splitlines()
    for n in ast.walk(tree):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in n.decorator_list:
            head = ast.unparse(dec).split("(")[0]
            method = head.split(".")[-1]
            if method not in HTTP:
                continue
            if "router" not in head and not head.startswith("app"):
                continue
            args = dec.args if isinstance(dec, ast.Call) else []
            raw_path = None
            if args:
                raw_path = literal(args[0])
            if raw_path is None:
                raw_path = ast.unparse(args[0]) if args else "?"
            deps = []
            # NOTE: FastAPI route guards live in the decorator's KEYWORD args
            # (dependencies=[...]), not its positional args. Reading only
            # dec.args reported every guarded route as unguarded.
            for kw in dec.keywords if isinstance(dec, ast.Call) else []:
                if kw.arg:
                    deps.append(ast.unparse(kw.value))
            # A route is guarded if EITHER form is present:
            #   dependencies=[_require_x]   (decorator keyword)
            #   _: Any = _require_x          (function default parameter)
            dep_src = " ".join(deps)
            func_args = list(n.args.args) + list(n.args.kwonlyargs)
            func_defaults = list(n.args.defaults) + [d for d in n.args.kw_defaults if d is not None]
            param_src = " ".join(ast.unparse(d) for d in func_defaults)
            for a in func_args:
                if a.annotation:
                    param_src += " " + ast.unparse(a.annotation)
            guard_src = dep_src + " " + param_src
            yield {
                "file": os.path.relpath(path, ROOT).replace("\\", "/"),
                "line": n.lineno,
                "method": method.upper(),
                "path": raw_path,
                "func": n.name,
                "deps": deps,
                "dep_src": guard_src[:400],
                "guarded": bool(re.search(r"_require_|RequirePermissions|RequireRole|require_", guard_src)),
                "doc": (ast.get_docstring(n) or "")[:200],
            }


def main():
    rows = []
    for base in ("backend/app",):
        for dirpath, _dirs, files in os.walk(os.path.join(ROOT, base)):
            if "__pycache__" in dirpath:
                continue
            for f in sorted(files):
                if not f.endswith(".py"):
                    continue
                p = os.path.join(dirpath, f)
                rows.extend(walk_file(p))
    rows.sort(key=lambda r: (r["file"], r["line"]))
    out = os.path.join(ROOT, "scripts", "wp-parity", "our_routes.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=1, ensure_ascii=False)

    bymod = collections.Counter()
    for r in rows:
        parts = r["file"].split("/")
        mod = parts[3] if len(parts) > 3 and parts[2] == "modules" else "CORE"
        bymod[mod] += 1
    print("TOTAL ROUTES:", len(rows))
    for k, v in bymod.most_common():
        print(f"{v:5d}  {k}")
    print("written:", out)


if __name__ == "__main__":
    main()
