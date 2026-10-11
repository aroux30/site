"""Negative test: prove check_wallet_switch_hiding.py can actually fail.

A gate that cannot fail is not a gate. This is the exact failure the project
already lived through: the wallet module was switched off, the backend correctly
refused every mutation, and the storefront still showed the menu entry, the
balance chip, the tab and the checkout payment method. A server-side gate was
green the whole time, because the defect was in the client.

Each case below re-injects that defect into a throwaway copy of the frontend and
asserts the gate reports it. The real source is never touched — the gate is
redirected at the copy via the WALLET_HIDE_GATE_ROOT override.

    cd backend && PYTHONPATH=. python scripts/negative_test_wallet_switch_hiding.py
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_BACKEND = Path(__file__).resolve().parents[1]
_GATE = _BACKEND / "scripts" / "check_wallet_switch_hiding.py"
_REAL_FRONTEND = _BACKEND.parent / "frontend"

# The only paths the gate reads. Copying the whole frontend (node_modules and
# three .next-* build dirs) would be slow and pointless.
_COPY_PATHS = (
    "components/account/account-dashboard.tsx",
    "app/(store)/checkout/page.tsx",
    "app/(account)/account/wallet/page.tsx",
)

_CASES = {
    # The originally-reported bug, verbatim: the guard was on the action
    # buttons only.
    "nav_entry_unguarded": (
        "components/account/account-dashboard.tsx",
        "...(walletFeatures.enabled\n"
        '      ? [{ key: "wallet" as const, label: "کیف پول", icon: WalletIcon,'
        " highlight: formatPrice(walletBalance) }]\n"
        "      : []),",
        '{ key: "wallet" as const, label: "کیف پول", icon: WalletIcon,'
        " highlight: formatPrice(walletBalance) },",
    ),
    "balance_chip_unguarded": (
        "components/account/account-dashboard.tsx",
        "{walletFeatures.enabled && (\n"
        '          <div className="flex items-center gap-3">\n'
        '            <div className="flex items-center gap-2 rounded-lg border'
        ' bg-card px-3 py-1.5 text-sm">\n'
        '              <span className="text-xs text-muted-foreground">'
        "موجودی کیف پول:</span>",
        "{\n"
        '          <div className="flex items-center gap-3">\n'
        '            <div className="flex items-center gap-2 rounded-lg border'
        ' bg-card px-3 py-1.5 text-sm">\n'
        '              <span className="text-xs text-muted-foreground">'
        "موجودی کیف پول:</span>",
    ),
    # The subtlest one: the response mapping stops reading the switch, so every
    # guard still "passes" the gate while checking a hard-coded `true`.
    "switch_never_read": (
        "components/account/account-dashboard.tsx",
        "enabled: f?.enabled ?? true,",
        "enabled: true,",
    ),
    "checkout_wallet_method_shown": (
        "app/(store)/checkout/page.tsx",
        "(m) => m.is_enabled && (m.provider !== \"wallet\" || walletEnabled),",
        "(m) => m.is_enabled,",
    ),
    "checkout_split_card_shown": (
        "app/(store)/checkout/page.tsx",
        "{walletEnabled && walletBalanceRials > 0 && (",
        "{walletBalanceRials > 0 && (",
    ),
    "checkout_submit_ignores_switch": (
        "app/(store)/checkout/page.tsx",
        "if (walletEnabled && splitEnabled && walletBalanceRials > 0"
        " && orderData.total > 0) {",
        "if (splitEnabled && walletBalanceRials > 0 && orderData.total > 0) {",
    ),
    "checkout_stale_selection": (
        "app/(store)/checkout/page.tsx",
        'current === "wallet" ? "zarinpal" : current,',
        "current,",
    ),
    "deeplink_still_renders": (
        "app/(account)/account/wallet/page.tsx",
        'if (verdict === "redirect") router.replace("/account");',
        "if (verdict === \"redirect\") return;",
    ),
}


def _run_gate(root: Path) -> int:
    import os

    env = dict(os.environ)
    env["WALLET_HIDE_GATE_ROOT"] = str(root)
    proc = subprocess.run(
        [sys.executable, str(_GATE), "--json"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(_BACKEND),
    )
    return proc.returncode


def main() -> int:
    # Baseline: the real tree must be clean, otherwise every case below would
    # "fail the gate" for a reason unrelated to the injection and the test
    # would prove nothing.
    if _run_gate(_REAL_FRONTEND) != 0:
        print("FAIL: the gate is already red on the real frontend; injections "
              "would prove nothing.")
        return 1
    print("PASS baseline: real frontend is green.")

    failures: list[str] = []

    for name, (rel, old, new) in _CASES.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for p in _COPY_PATHS:
                dest = root / p
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_REAL_FRONTEND / p, dest)

            target = root / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                failures.append(f"{name}: injection anchor not found ({old[:60]!r})")
                continue
            target.write_text(text.replace(old, new, 1), encoding="utf-8")

            rc = _run_gate(root)
            if rc == 0:
                failures.append(f"{name}: gate did NOT fail on the injected defect")
            else:
                print(f"PASS negative: {name} -> gate failed as expected (rc={rc})")

    if failures:
        print("\nFAIL: negative test did not prove the gate can fail:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"\nALL {len(_CASES)} NEGATIVE CASES PASSED: the gate fails on every "
          f"injected defect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
