"""AST scan: stdlib-logging loggers called with structlog-style kwargs.

`logging.Logger.info("evt", key=value)` raises
`TypeError: Logger._log() got an unexpected keyword argument 'key'` at RUNTIME —
invisible in unit tests where the level is disabled, and a 500 under a
configured server. This scan finds every call site.

Valid stdlib kwargs (never flagged): exc_info, extra, stack_info, stacklevel.

Usage: check_stdlib_logger_kwargs.py [ROOT]
ROOT defaults to backend/app; the optional argument exists so the negative
test can point the scan at a sabotaged copy in a temp directory.
"""
import ast
import os
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BACKEND, "app")
VALID = {"exc_info", "extra", "stack_info", "stacklevel"}
METHODS = {"debug", "info", "warning", "error", "exception", "critical"}

findings = []

for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    for fn in filenames:
        if not fn.endswith(".py"):
            continue
        path = os.path.join(dirpath, fn)
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue

        # Which names are stdlib loggers in this file?
        stdlib_logger_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if (isinstance(node.value, ast.Call)
                        and isinstance(node.value.func, ast.Attribute)
                        and node.value.func.attr == "getLogger"):
                    for t in node.targets:
                        if isinstance(t, ast.Name):
                            stdlib_logger_names.add(t.id)

        if not stdlib_logger_names:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if not (isinstance(f, ast.Attribute) and f.attr in METHODS):
                continue
            if not (isinstance(f.value, ast.Name) and f.value.id in stdlib_logger_names):
                continue
            for kw in node.keywords:
                if kw.arg and kw.arg not in VALID:
                    findings.append(
                        f"{os.path.relpath(path, BACKEND)}:"
                        f"{node.lineno} {f.value.id}.{f.attr}(... {kw.arg}=...)"
                    )

print(f"stdlib-logger kwarg-call findings: {len(findings)}")
for f in findings:
    print("  " + f)
sys.exit(1 if findings else 0)
