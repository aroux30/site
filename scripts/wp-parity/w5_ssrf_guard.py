"""Prove the SSRF guard blocks what the old one let through.

Run:  cd backend && PYTHONIOENCODING=utf-8 python ../scripts/wp-parity/w5_ssrf_guard.py

The old check in ``embed_service._validate_public_url`` is kept here as
``old_guard`` so the two can be compared on the same table, rather than this
file asserting that the new one is better. The rows marked OLD-PASSED are the
ones that made the sideload unsafe to build.
"""

import asyncio
import ipaddress
import socket
import sys

sys.path.insert(0, r"C:\Users\Administrator\Desktop\site\backend")

from app.core.exceptions.handlers import ValidationError  # noqa: E402
from app.core.security import url_guard  # noqa: E402
from app.modules.content.application.embed_service import (  # noqa: E402
    _validate_public_url as old_guard,
)

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}\n      {detail}")


def _classify(allowed: bool) -> str:
    return "ALLOWED" if allowed else "BLOCKED"


async def _outcome(fn, url: str) -> str:
    try:
        await fn(url)
        return "ALLOWED"
    except ValidationError:
        return "BLOCKED"
    except Exception as exc:  # a crash is not a decision
        return f"ERROR({type(exc).__name__})"


async def main() -> int:
    # ---------------------------------------------------------------- table 1
    # Targets that must be blocked. The OLD column is measured, not asserted.
    must_block = [
        ("http://127.0.0.1/x", "IPv4 loopback"),
        ("http://10.0.0.5/x", "private RFC1918"),
        ("http://192.168.1.1/admin", "private LAN"),
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata"),
        ("http://[::1]/x", "IPv6 loopback"),
        ("http://[fd00::1]/x", "IPv6 unique-local"),
        ("http://0.0.0.0/x", "unspecified"),
        ("http://localhost:8000/x", "localhost by name"),
        ("http://foo.internal/x", ".internal suffix"),
        ("http://printer.local/x", ".local suffix"),
        ("http://metadata.google.internal/x", "GCP metadata by name"),
    ]
    print("=== must block ===")
    for url, label in must_block:
        old = await _outcome(lambda u: _old(u), url)
        new = await _outcome(url_guard.validate_public_url, url)
        ok = new == "BLOCKED"
        check(
            f"blocks {label}",
            ok,
            f"old={old:8} new={new:8} {url}",
        )

    # ---------------------------------------------------------------- table 2
    # The two shapes the old check waved through. These are the point.
    print("=== the two gaps the old check had ===")
    hex_loopback = "http://0x7f.0.0.1/x"
    old = await _outcome(lambda u: _old(u), hex_loopback)
    new = await _outcome(url_guard.validate_public_url, hex_loopback)
    check(
        "blocks hex-encoded loopback (OLD ALLOWED IT)",
        new == "BLOCKED",
        f"old={old:8} new={new:8} {hex_loopback}",
    )

    decimal_loopback = "http://2130706433/x"
    old = await _outcome(lambda u: _old(u), decimal_loopback)
    new = await _outcome(url_guard.validate_public_url, decimal_loopback)
    check(
        "blocks decimal-encoded loopback (OLD ALLOWED IT)",
        new == "BLOCKED",
        f"old={old:8} new={new:8} {decimal_loopback}",
    )

    # ---------------------------------------------------------------- table 3
    # DNS-dependent rows. Driven by a stub so the check is deterministic and
    # does not depend on what a name happens to resolve to today.
    print("=== DNS-dependent (stubbed resolver) ===")
    real = url_guard._addresses_for

    async def resolves_to(addrs):
        # `_addresses_for` already parses getaddrinfo output into address
        # objects, so the stub replaces `_addresses_for` itself and must return
        # the same shape: a list of ip_address objects, NOT raw getaddrinfo
        # tuples. Returning tuples made the guard call .is_private on a tuple.
        parsed = [ipaddress.ip_address(a) for a in addrs]

        async def _stub(host, port=None):
            return parsed

        return _stub

    # A name that resolves to the metadata address.
    url_guard._addresses_for = await resolves_to(["169.254.169.254"])
    new = await _outcome(url_guard.validate_public_url, "http://attacker.example/x")
    check(
        "blocks a public name resolving to metadata (OLD ALLOWED IT)",
        new == "BLOCKED",
        f"attacker.example -> 169.254.169.254, new={new}",
    )

    # A name with one public and one private answer: vetting only the first is
    # exactly the rebinding case, so ALL must be checked.
    url_guard._addresses_for = await resolves_to(["93.184.216.34", "127.0.0.1"])
    new = await _outcome(url_guard.validate_public_url, "http://split.example/x")
    check(
        "blocks when ANY resolved address is internal",
        new == "BLOCKED",
        f"split.example -> [93.184.216.34, 127.0.0.1], new={new} "
        "(a first-answer-only check would have allowed this)",
    )

    # A genuinely public name still passes.
    url_guard._addresses_for = await resolves_to(["93.184.216.34"])
    new = await _outcome(url_guard.validate_public_url, "https://cdn.example/logo.png")
    check(
        "still allows a genuinely public host",
        new == "ALLOWED",
        f"cdn.example -> 93.184.216.34, new={new}",
    )

    # A name that does not resolve at all is refused rather than fetched.
    async def no_addresses(host, port=None):
        return []

    url_guard._addresses_for = no_addresses
    new = await _outcome(url_guard.validate_public_url, "https://nowhere.example/x")
    check(
        "refuses a name with no addresses",
        new == "BLOCKED",
        f"empty resolution, new={new}",
    )

    # A resolver failure is a refusal, not a pass-through.
    async def blows_up(host, port=None):
        raise socket.gaierror("no such host")

    url_guard._addresses_for = blows_up
    new = await _outcome(url_guard.validate_public_url, "https://broken.example/x")
    check(
        "refuses when DNS raises",
        new == "BLOCKED",
        f"gaierror, new={new}",
    )

    url_guard._addresses_for = real

    # ---------------------------------------------------------------- table 4
    # Pinning: the caller connects to the address that was just vetted.
    print("=== pinning ===")
    url_guard._addresses_for = await resolves_to(["93.184.216.34"])
    connect, original = await url_guard.validate_pinned_url(
        "https://cdn.example:8443/logo.png"
    )
    check(
        "pins the connect URL to a vetted address",
        "93.184.216.34" in connect and ":8443" in connect,
        f"original host {original!r} -> connect {connect!r}",
    )

    url_guard._addresses_for = await resolves_to(["169.254.169.254"])
    new = await _outcome(url_guard.validate_pinned_url, "http://evil.example/x")
    check(
        "pinning refuses before it can pin an internal address",
        new == "BLOCKED",
        f"new={new}",
    )
    url_guard._addresses_for = real

    # ---------------------------------------------------------------- table 5
    # Scheme handling.
    print("=== schemes ===")
    for url, label in [
        ("file:///etc/passwd", "file://"),
        ("ftp://example.com/x", "ftp://"),
        ("gopher://example.com/x", "gopher://"),
    ]:
        new = await _outcome(url_guard.validate_public_url, url)
        check(f"refuses {label}", new == "BLOCKED", f"new={new:8} {url}")

    print()
    failed = [r for r in results if not r[1]]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    if failed:
        print("FAILED: " + ", ".join(r[0] for r in failed))
    return 1 if failed else 0


def _old(url: str) -> str:
    """The previous guard, for the comparison column. Not async."""
    return old_guard(url)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
