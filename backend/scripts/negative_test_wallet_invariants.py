"""Negative test: prove check_wallet_invariants.py can actually fail.

A gate that cannot fail is not a gate. This injects each violation class into
a throwaway copy of the wallet module and asserts the gate reports it. It never
touches the real source — the injection happens in a temp tree the gate is
pointed at via the WALLET_GATE_ROOT override.

    cd backend && PYTHONPATH=. python scripts/negative_test_wallet_invariants.py
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_BACKEND = Path(__file__).resolve().parents[1]
_GATE = _BACKEND / "scripts" / "check_wallet_invariants.py"
_REAL_WALLET = _BACKEND / "app" / "modules" / "wallet"

_CASES = {
    "float_money": (
        "application/wallet_service.py",
        "new_balance = ledger_balance + amount",
        "new_balance = float(ledger_balance + amount)",
    ),
    "english_detail": (
        "application/wallet_service.py",
        'detail="مبلغ واریز باید یک عدد صحیح مثبت (ریال) باشد.",',
        'detail="Credit amount must be positive",',
    ),
    "unbalanced_journal": (
        "application/wallet_service.py",
        "    assert debit_tx.amount + credit_tx.amount == 0, (",
        "    assert debit_tx.amount + credit_tx.amount == 1, (",
    ),
    "missing_transfer_type": (
        "application/wallet_service.py",
        "debit_type=WalletTransactionType.TRANSFER_OUT,",
        "debit_type=WalletTransactionType.DEBIT,",
    ),
}


def _run_gate(root: Path) -> int:
    env = dict(os.environ)
    env["WALLET_GATE_ROOT"] = str(root)
    proc = subprocess.run(
        [sys.executable, str(_GATE), "--json"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=str(_BACKEND),
    )
    return proc.returncode


def main() -> int:
    failures: list[str] = []

    for name, (rel, old, new) in _CASES.items():
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(_REAL_WALLET, root / "wallet")
            target = root / "wallet" / rel
            text = target.read_text(encoding="utf-8")
            if old not in text:
                failures.append(f"{name}: injection anchor not found ({old[:40]!r})")
                continue
            target.write_text(text.replace(old, new, 1), encoding="utf-8")

            # The gate reads paths relative to _BACKEND/app/modules/wallet by
            # default; WALLET_GATE_ROOT redirects it at the injected copy.
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
    print("\nALL NEGATIVE CASES PASSED: the gate fails on every injected defect.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
