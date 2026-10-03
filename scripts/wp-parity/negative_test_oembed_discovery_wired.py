"""Negative test for check_oembed_discovery_wired.

Three hops that each look complete alone, and the failure this guards is the
one they produce together: a link that exists, points somewhere real, and
describes nothing.

  A. Drop the `format` and `url` parameters from the discovery endpoint. Every
     frontend check still passes — the page still advertises a link, it still
     points at this route — and the route answers with the provider list it
     always did, ignoring what the consumer asked about.
  B. Make the link relative. A consumer fetches it with no referer and no base,
     so it resolves against nothing; every string check still passes.
  C. Stop sending `url`, keeping `format`. The link still has the right shape
     and the endpoint still accepts a format, and a consumer gets a document
     with no page in it.
  E. **The runtime case.** Accept `url` in the signature and drop it from the
     response. Every source check passes — the parameter is declared, the
     string is there — and a consumer that followed the link gets a document
     with no page in it. This is the regression the static half cannot see,
     and the live probe is what catches it.

Run:  python scripts/wp-parity/negative_test_oembed_discovery_wired.py
"""

from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import console_safe  # noqa: F401  — makes stdout safe for non-ASCII

GATE = os.path.join(HERE, "check_oembed_discovery_wired.py")
ROUTES = os.path.join(ROOT, "backend", "app", "modules", "content",
                      "api", "routes.py")
HREFLANG = os.path.join(ROOT, "frontend", "lib", "hreflang.ts")


def run_gate() -> tuple[int, str]:
    proc = subprocess.run(
        [sys.executable, GATE], capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=300,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def edit(label: str, path: str, fn) -> bool:
    with open(path, encoding="utf-8", newline="") as fh:
        on_disk = fh.read()
    crlf = "\r\n" in on_disk
    original = on_disk.replace("\r\n", "\n")

    def write(text: str) -> None:
        payload = text.replace("\n", "\r\n") if crlf else text
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(payload)

    try:
        changed = fn(original)
    except AssertionError as exc:
        print(f"FAIL: {label} — {exc}")
        return False
    if changed == original:
        print(f"FAIL: {label} — nothing changed.")
        return False

    write(changed)
    try:
        rc, out = run_gate()
    finally:
        write(original)

    rc_after, _ = run_gate()
    if rc_after != 0:
        print(f"FAIL: {label} — the gate did not pass again after restoring.")
        return False
    if rc == 0:
        print(f"FAIL: {label} still passed. The gate cannot see it.")
        return False

    caught = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("- ")]
    print(f"  {label} -> caught")
    for line in caught[:1]:
        print(f"      {line[:140]}")
    return True


def main() -> int:
    rc, out = run_gate()
    if rc != 0:
        print("FAIL: the gate does not pass on the real code.")
        print(out.strip()[-700:])
        return 1
    print("gate passes on the real code")

    ok = True

    def drop_params(text: str) -> str:
        start = text.find("async def oembed_discovery(")
        if start == -1:
            raise AssertionError("the discovery route is not in the expected shape")
        end = text.find("-> dict[str, Any]:", start)
        sig = text[start:end]
        if "url:" not in sig or "format:" not in sig:
            raise AssertionError("the parameters are not both there to remove")
        return text[:start] + "async def oembed_discovery(db: AsyncSession = Depends(get_db)) " + text[end:]

    ok = edit("A: drop url and format from the endpoint", ROUTES, drop_params) and ok

    def make_relative(text: str) -> str:
        needle = "  return `${SITE_URL}/api/v1/content/oembed?url="
        if needle not in text:
            raise AssertionError("the discovery helper is not in the expected shape")
        return text.replace(needle, "  return `/api/v1/content/oembed?url=", 1)

    ok = edit("B: make the discovery link relative", HREFLANG, make_relative) and ok

    def drop_url_only(text: str) -> str:
        needle = "?url=${encodeURIComponent(url)}&format=json"
        if needle not in text:
            raise AssertionError("the query string is not in the expected shape")
        return text.replace(needle, "?format=json", 1)

    ok = edit("C: stop sending the page url", HREFLANG, drop_url_only) and ok

    # E: the runtime-only regression. The parameter is still declared — so the
    #    signature check passes — and the route still answers 200 — so a status
    #    check would pass too — but the document names no page. Only a caller
    #    reading the body catches it.
    def drop_from_response(text: str) -> str:
        needle = '        "url": url,' + "\n"
        if needle not in text:
            raise AssertionError("the url echo is not in the expected shape")
        return text.replace(needle, "", 1)

    ok = edit("E: the endpoint stops echoing the page url", ROUTES,
              drop_from_response) and ok

    if not ok:
        return 1
    print("\nPASS: the gate sees an endpoint that ignores its parameters, a "
          "relative link, a link with no page in it, and — through the live "
          "probe — a response that stops naming the page.")
    return 0


if __name__ == "__main__":
    sys.exit(main())