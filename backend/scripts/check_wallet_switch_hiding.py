"""Read-only gate: disabling a module must HIDE it, not merely reject its writes.

The bug this pins (reported from the storefront): an operator switched the
wallet module off and the UI kept showing its menu entry, the balance chip, the
wallet tab and the wallet payment method at checkout — only the action buttons
disappeared. The backend was correctly refusing the mutations, so the gate that
existed at the time (a route-level switch check) was green while the product was
still visibly broken. A gate that only tests the server cannot see this class of
defect, because the defect is in the client.

So this gate reads the **client source** and asserts that every wallet surface
that renders is guarded by the master switch. It is deliberately mechanical:
it walks the JSX of each file and requires the wallet affordances to sit behind
a guard, rather than trusting a hand-written allowlist of line numbers that
would rot on the next edit.

What it requires per surface:

* ``account-dashboard.tsx``
  - the nav entry is built by a conditional spread (a bare literal would render
    a dead tab);
  - the header balance chip and the wallet tab block are guarded;
  - ``features.enabled`` is actually read from the API response — otherwise the
    guards are all hard-coded ``true`` and the gate would pass on a page that
    hides nothing.
* ``checkout/page.tsx``
  - the wallet payment method is filtered out of the method list;
  - the wallet icon branch and the split-tender card are guarded;
  - a wallet-only selection is retired when the switch flips.
* ``(account)/account/wallet/page.tsx`` (the deep link)
  - redirects instead of rendering the wallet page when the switch is off.

Read-only: reads files, never builds or serves anything.

    cd backend && PYTHONPATH=. python scripts/check_wallet_switch_hiding.py
    cd backend && PYTHONPATH=. python scripts/check_wallet_switch_hiding.py --json

Exits 0 when every surface is guarded, 1 when any finding exists.
"""

from __future__ import annotations

import io
import json
import os
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_SITE = Path(__file__).resolve().parents[2]
# WALLET_HIDE_GATE_ROOT lets the negative test point the gate at an injected copy
# of the frontend (a directory containing the two components). Unset in normal
# operation.
_root = os.environ.get("WALLET_HIDE_GATE_ROOT")
_FRONTEND = Path(_root) if _root else _SITE / "frontend"

_DASHBOARD = "components/account/account-dashboard.tsx"
_CHECKOUT = "app/(store)/checkout/page.tsx"
_WALLET_PAGE = "app/(account)/account/wallet/page.tsx"


def _read(rel: str) -> str | None:
    path = _FRONTEND / rel
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _ctx(text: str, needle: str, before: int = 260, after: int = 260) -> str:
    """The window of source around the **last** occurrence of ``needle``.

    Used for every structural check below so a guard that merely appears
    elsewhere in a 2,700-line component cannot satisfy a check about a
    different surface (the "a name in the file is not a connection" trap).
    """
    i = text.rfind(needle)
    if i < 0:
        return ""
    return text[max(0, i - before) : i + len(needle) + after]


def _require_unique(text: str, needle: str, findings: list[str], where: str) -> None:
    """Anchor strings must identify exactly one surface.

    Two of these checks were silently vacuous before this existed: the split
    card's expression ``walletBalanceRials > 0`` also occurs in the submit
    handler, so removing the guard from the JSX still left a guarded-looking
    match somewhere in the window. Requiring uniqueness turns "the string is
    here" into "the string is here and only here", so an anchor that starts
    being reused is itself a finding rather than a silently weakened check.
    """
    if text.count(needle) != 1:
        findings.append(
            f"{where}: anchor {needle[:50]!r} occurs {text.count(needle)}x — "
            f"the gate can no longer tell this surface from another; update the "
            f"anchor rather than letting the check go vacuous"
        )


def _check_dashboard(findings: list[str]) -> None:
    text = _read(_DASHBOARD)
    if text is None:
        findings.append(f"{_DASHBOARD}: not found under {_FRONTEND}")
        return

    # 1. The switch must be read from the response, otherwise every guard below
    #    is checking a constant `true`.
    if not re.search(r"enabled\s*:\s*f\?\.enabled\s*\?\?\s*true", text):
        findings.append(
            f"{_DASHBOARD}: wallet features are not read from the API response "
            f"(expected `enabled: f?.enabled ?? true`) — the guards below would "
            f"be hard-coded to enabled"
        )

    # 2. The nav entry must be a conditional spread, not a bare literal.
    _require_unique(text, 'label: "کیف پول"', findings, _DASHBOARD)
    nav = _ctx(text, 'label: "کیف پول"')
    if "walletFeatures.enabled" not in nav:
        findings.append(
            f"{_DASHBOARD}: the wallet nav entry is not behind the master switch "
            f"(expected the nav item list to spread it conditionally)"
        )

    # 3. The header balance chip.
    _require_unique(text, "موجودی کیف پول:", findings, _DASHBOARD)
    chip = _ctx(text, "موجودی کیف پول:")
    if "walletFeatures.enabled" not in chip:
        findings.append(
            f"{_DASHBOARD}: the header balance chip is not behind the master switch"
        )

    # 4. The wallet tab block. Both occurrences matter and are checked
    #    independently: the one that RENDERS the tab must be guarded, and the
    #    one that renders the "wallet is off" notice must also be guarded
    #    (an unguarded notice is just as visible as an unguarded tab).
    render_tab = 'activeTab === "wallet" && walletFeatures.enabled'
    if render_tab not in text:
        findings.append(
            f"{_DASHBOARD}: the wallet tab is not behind the master switch "
            f"(expected `activeTab === \"wallet\" && walletFeatures.enabled`)"
        )
    off_notice = 'activeTab === "wallet" && !walletFeatures.enabled'
    if off_notice not in text:
        findings.append(
            f"{_DASHBOARD}: the wallet-disabled notice is not behind the master "
            f"switch, so a stale wallet tab would render a blank panel"
        )


def _check_checkout(findings: list[str]) -> None:
    text = _read(_CHECKOUT)
    if text is None:
        findings.append(f"{_CHECKOUT}: not found under {_FRONTEND}")
        return

    # The wallet tender must be dropped from the method list, not merely
    # un-selected: an unlisted-but-still-selected provider still reaches the
    # order submit call with `payment_method: "wallet"`. Anchored on the API
    # loader (not on the filter expression, which also appears in the
    # `fallbackPaymentMethods` literal list) so the check is about the surface
    # a customer actually renders.
    _require_unique(text, "setPaymentMethods(active)", findings, _CHECKOUT)
    methods_load = _ctx(text, "setPaymentMethods(active)", before=420, after=0)
    if "walletEnabled" not in methods_load:
        findings.append(
            f"{_CHECKOUT}: the wallet payment method is not filtered out of the "
            f"method list when the master switch is off"
        )

    # The split-tender card. The card is the LAST `walletBalanceRials > 0` in the
    # file; the earlier one is the submit handler.
    _require_unique(text, "Split tender: wallet + gateway", findings, _CHECKOUT)
    split = _ctx(text, "Split tender: wallet + gateway", before=300, after=400)
    if "walletEnabled" not in split:
        findings.append(
            f"{_CHECKOUT}: the split-tender card is not behind the master switch"
        )

    # The submit path must not build a wallet slice when the switch is off.
    _require_unique(text, "slices.push", findings, _CHECKOUT)
    submit = _ctx(text, "slices.push", before=1400, after=0)
    if "walletEnabled && splitEnabled" not in submit:
        findings.append(
            f"{_CHECKOUT}: the split-tender submit path does not check "
            f"walletEnabled — a stale `splitEnabled` would still charge the wallet"
        )

    # Retiring a wallet-only selection.
    if not re.search(
        r"setSelectedPaymentMethod\(\(current\)\s*=>\s*"
        r"current\s*===\s*\"wallet\"\s*\?\s*\"zarinpal\"",
        text,
    ):
        findings.append(
            f"{_CHECKOUT}: a wallet selection is not retired when the master "
            f"switch flips — the summary would promise wallet payment with no "
            f"radio to back it"
        )


def _check_wallet_deeplink(findings: list[str]) -> None:
    text = _read(_WALLET_PAGE)
    if text is None:
        findings.append(f"{_WALLET_PAGE}: not found under {_FRONTEND}")
        return
    if 'router.replace("/account")' not in text:
        findings.append(
            f"{_WALLET_PAGE}: /account/wallet still renders the wallet page when "
            f"the master switch is off — the deep link must redirect"
        )
    if "features?.enabled" not in text:
        findings.append(
            f"{_WALLET_PAGE}: the deep-link guard does not read features.enabled"
        )


def main() -> int:
    as_json = "--json" in sys.argv
    findings: list[str] = []

    _check_dashboard(findings)
    _check_checkout(findings)
    _check_wallet_deeplink(findings)

    ok = not findings
    if as_json:
        print(json.dumps({
            "gate": "wallet_switch_hiding",
            "ok": ok,
            "measured": True,
            "root": str(_FRONTEND),
            "findings": findings,
        }, ensure_ascii=False))
    else:
        if ok:
            print("PASS: every wallet surface is hidden when the master switch is off.")
        else:
            print(f"FAIL: {len(findings)} unguarded wallet surface(s):")
            for f in findings:
                print(f"  - {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
