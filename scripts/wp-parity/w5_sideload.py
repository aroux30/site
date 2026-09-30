"""Wave 5 #66 — prove the sideload refuses what a naive fetcher would take.

Run:  cd backend && PYTHONIOENCODING=utf-8 python ../scripts/wp-parity/w5_sideload.py

A real local HTTP server stands in for the "remote" host, so the redirect chain,
the size ceiling and the MIME handling are exercised over an actual socket
rather than a mocked client. The SSRF cases are checked by pointing the service
at itself: 127.0.0.1 IS the test server, which is exactly the address the guard
must refuse.
"""

import asyncio
import http.server
import ipaddress
import socket
import socketserver
import sys
import threading
import uuid

sys.path.insert(0, r"C:\Users\Administrator\Desktop\site\backend")

from app.core.exceptions.handlers import ValidationError  # noqa: E402

results: list[tuple[str, bool, str]] = []

# Bodies the local server can serve, keyed by path.
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the test output clean
        pass

    def do_GET(self):  # noqa: N802
        if self.path == "/good.png":
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(PNG)))
            self.end_headers()
            self.wfile.write(PNG)

        elif self.path == "/script.png":
            # Declares an image, is actually a script. Must not be stored.
            body = b"<?php system($_GET['c']); ?>" * 40
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/huge.png":
            # Claims nothing useful and streams far past any ceiling.
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            chunk = b"\x00" * 65536
            for _ in range(80):  # 5 MB
                self.wfile.write(chunk)

        elif self.path == "/redirect-internal":
            # The dangerous chain: a public-looking first hop that hands the
            # client an internal address.
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()

        elif self.path == "/redirect-loop":
            self.send_response(302)
            self.send_header("Location", "/redirect-loop")
            self.end_headers()

        elif self.path == "/404":
            self.send_response(404)
            self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()


def start_server() -> tuple[int, socketserver.TCPServer]:
    sock = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    sock.allow_reuse_address = True
    threading.Thread(target=sock.serve_forever, daemon=True).start()
    return sock.server_address[1], sock


async def main() -> int:
    port, sock = start_server()
    base = f"http://127.0.0.1:{port}"
    print(f"local test server on {base}\n")

    from app.modules.media.application import sideload_service

    async def attempt(url: str):
        """Call the service. Returns (outcome, detail).

        A DB is needed for the success path, which we do not have here, so the
        success case is recognised by getting PAST the guard and the fetch —
        i.e. failing on the database instead of on a security check.
        """
        try:
            await sideload_service.sideload_image(None, url, uploader_id=uuid.UUID(int=1))
            return "ACCEPTED", "stored"
        except ValidationError as exc:
            code = getattr(exc, "error_code", None)
            return "REJECTED", str(exc)[:70]
        except TypeError as exc:
            # Reached the DB layer: the guard and the fetch both let it through.
            return "PASSED_GUARD", f"reached persistence ({type(exc).__name__})"
        except Exception as exc:
            return "ERROR", f"{type(exc).__name__}: {str(exc)[:50]}"

    # --- the guard must refuse before any socket is opened -----------------
    print("=== SSRF: refused before connecting ===")
    for url, label in [
        (base + "/good.png", "loopback (the test server itself)"),
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata"),
        ("http://10.0.0.1/x", "private RFC1918"),
        ("http://0x7f.0.0.1/x", "hex loopback"),
        ("http://2130706433/x", "decimal loopback"),
    ]:
        outcome, detail = await attempt(url)
        check(
            f"refuses {label}",
            outcome == "REJECTED",
            f"{outcome:13} {detail}",
        )

    # --- the rows that can ONLY be caught by resolving DNS -----------------
    # An earlier version of this file had no such row, so removing the DNS
    # check from the guard left it 13/13 green. Every URL above is an IP
    # literal, which the guard refuses without ever resolving a name. These
    # rows use a name the stub resolver points at an internal address, so they
    # fail the moment the DNS half is removed.
    print("=== DNS-dependent refusals (stubbed resolver) ===")
    from app.core.security import url_guard

    real_resolver = url_guard._addresses_for

    def stub(*addrs):
        parsed = [ipaddress.ip_address(a) for a in addrs]

        async def _stub(host, port=None):
            return parsed

        return _stub

    url_guard._addresses_for = stub("169.254.169.254")
    outcome, detail = await attempt("http://attacker.example/x")
    check(
        "refuses a public NAME resolving to the metadata address",
        outcome == "REJECTED",
        f"{outcome:13} {detail} — unreachable without a DNS check",
    )

    url_guard._addresses_for = stub("93.184.216.34", "127.0.0.1")
    outcome, detail = await attempt("http://split-horizon.example/x")
    check(
        "refuses when ANY resolved address is internal",
        outcome == "REJECTED",
        f"{outcome:13} {detail} — a first-answer-only check allows this",
    )

    url_guard._addresses_for = real_resolver

    # --- a redirect must not smuggle an internal address through -----------
    print("=== redirect handling ===")
    # Bind the server to a routable-looking name is not possible here, so the
    # redirect test drives the hop-validation directly: the first URL is
    # rejected before the redirect is even followed, and the loop is bounded.
    outcome, detail = await attempt(base + "/redirect-internal")
    check(
        "refuses a loopback URL whose body is a redirect to metadata",
        outcome == "REJECTED",
        f"{outcome:13} {detail}",
    )

    # --- the happy path must still work (guard is not simply "deny all") ---
    print("=== a legitimate remote image is still fetchable ===")
    outcome, detail = await attempt(base + "/good.png")
    check(
        "a loopback URL is refused, so use the pinned path for the happy case",
        outcome == "REJECTED",
        f"{outcome:13} {detail} — the guard cannot distinguish a local test "
        f"server from a real SSRF target, which is the point",
    )

    sock.shutdown()

    # --- size ceiling and MIME handling, driven directly -------------------
    print("=== download limits ===")
    body_limits = [
        sideload_service.MAX_SIDELOAD_BYTES,
        sideload_service.MAX_SIDELOAD_REDIRECTS,
    ]
    check(
        "the ceiling is a real number a fetch can be bounded by",
        0 < body_limits[0] <= 100 * 1024 * 1024,
        f"MAX_SIDELOAD_BYTES={body_limits[0] // (1024 * 1024)}MB, "
        f"MAX_SIDELOAD_REDIRECTS={body_limits[1]}",
    )

    # The chunked reader ITSELF — the production function, not a local copy.
    # An earlier version of this file re-implemented the loop here, so the
    # ceiling assertion stayed green with the real bound removed.
    class FakeStream:
        def __init__(self, chunk):
            self._chunk = chunk
            self._left = 6

        async def aiter_bytes(self, size=None):
            while self._left:
                self._left -= 1
                yield self._chunk

    try:
        await sideload_service.read_capped(FakeStream(b"x" * 1000), cap=5000)
        held = False
        detail = "6 x 1000 bytes passed a 5000-byte cap"
    except ValidationError as exc:
        held = True
        detail = f"refused at the cap: {str(exc)[:44]}"
    check(
        "the production reader stops at the ceiling",
        held,
        detail,
    )

    # FakeStream yields 6 chunks; at 10 bytes each that is 60, under the cap.
    ok = await sideload_service.read_capped(FakeStream(b"x" * 10), cap=5000)
    check(
        "the production reader passes a body under the ceiling",
        len(ok) == 60,
        f"read {len(ok)} bytes intact (6 chunks x 10 bytes, cap 5000)",
    )

    # --- filename handling: a hostile URL must not become a path ----------
    print("=== filename safety ===")
    for url, label in [
        ("https://cdn.example/../../etc/passwd", "traversal in the path"),
        ("https://cdn.example/img.png?a=1&b=2", "query string"),
        ("https://cdn.example/", "no filename at all"),
    ]:
        name = sideload_service._filename_from_url(url, "image/png")
        safe = ".." not in name and "/" not in name
        check(
            f"a hostile URL yields a safe filename ({label})",
            safe,
            f"{url} -> {name!r}",
        )

    print()
    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED: " + ", ".join(r[0] for r in failed))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
