"""Read-only gate: the wallet module's money invariants hold.

Three things this gate pins, each of which was a real defect class in this
project or a real trap found while building the module:

1. **No float money.** ADR-012 requires integer Rial everywhere; a ``float``,
   ``Decimal`` or ``round()`` on an amount is the money-drift bug class. The
   gate scans the wallet module's money-bearing files for those.
2. **The transfer pair is balanced.** A P2P transfer writes a ``TRANSFER_OUT``
   (negative) and a ``TRANSFER_IN`` (positive) leg sharing one
   ``journal_entry_id``. Their signed amounts must sum to zero — a broken pair
   mints or destroys money.
3. **User-facing wallet errors are Persian.** The backend must not answer a
   Persian-speaking customer with an English sentence. Every ``detail=``
   literal in ``wallet_service.py`` that reaches a user must contain a
   non-ASCII (Persian) character.

Read-only: never opens a DB connection, never touches financial state.

    cd backend && PYTHONPATH=. python scripts/check_wallet_invariants.py
    cd backend && PYTHONPATH=. python scripts/check_wallet_invariants.py --json

Exits 0 when every invariant holds, 1 when any finding exists.
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

_BACKEND = Path(__file__).resolve().parents[1]
# WALLET_GATE_ROOT lets the negative test point the gate at an injected copy of
# the wallet module (a directory containing a ``wallet/`` subpackage). Unset in
# normal operation.
_gate_root = os.environ.get("WALLET_GATE_ROOT")
_WALLET = Path(_gate_root) / "wallet" if _gate_root else _BACKEND / "app" / "modules" / "wallet"

# Files that carry wallet money logic. Scanned for float/Decimal/round.
_MONEY_FILES = [
    _WALLET / "application" / "wallet_service.py",
    _WALLET / "domain" / "models.py",
]

# Tokens that are never acceptable on a money expression.
_FORBIDDEN_MONEY_TOKENS = ("float(", "Decimal")
# Tokens that are fine in general (pagination, counting) but not on money.
# Only flagged when the same line references a money identifier.
_FORBIDDEN_ON_MONEY_TOKENS = ("round(", "math.floor(", "math.ceil(")
_MONEY_KEYWORDS = (
    "amount", "balance", "rial", "toman", "price", "cost", "fee", "discount", "subtotal",
)

# detail=... string literals in the wallet service that are user-facing. We
# accept a detail as "Persian" if it contains at least one non-ASCII char.
_DETAIL_RE = re.compile(r"detail\s*=\s*(f?)(['\"])(.*?)\2", re.DOTALL)


def _check_no_float_money(findings: list[str]) -> None:
    for path in _MONEY_FILES:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            # Skip comments — a comment that explains "never float" must not
            # itself trip the gate.
            if stripped.startswith("#"):
                continue
            for token in _FORBIDDEN_MONEY_TOKENS:
                if token in line:
                    findings.append(
                        f"{path.name}:{lineno}: money code uses '{token}' "
                        f"(ADR-012 requires integer Rial)"
                    )
            # round/floor/ceil are legitimate for page counts; only flag them
            # when the line also names a money quantity.
            lowered = line.lower()
            if any(k in lowered for k in _MONEY_KEYWORDS):
                for token in _FORBIDDEN_ON_MONEY_TOKENS:
                    if token in line:
                        findings.append(
                            f"{path.name}:{lineno}: '{token}' applied near a money "
                            f"identifier (ADR-012 requires integer Rial)"
                        )


def _check_persian_details(findings: list[str]) -> None:
    path = _WALLET / "application" / "wallet_service.py"
    if not path.exists():
        findings.append("wallet_service.py not found")
        return
    text = path.read_text(encoding="utf-8")
    for match in _DETAIL_RE.finditer(text):
        detail = match.group(3)
        # A detail that is purely a variable/expression reference (no letters
        # in a natural language) is not a user-facing literal we can judge.
        if not any(ch.isalpha() and ord(ch) < 128 for ch in detail):
            continue
        has_persian = any(ord(ch) > 0x7F for ch in detail)
        if not has_persian:
            snippet = detail.strip()[:60]
            findings.append(
                f"wallet_service.py: non-Persian user-facing detail: {snippet!r}"
            )


def _check_transfer_pair_balanced(findings: list[str]) -> None:
    """The journal helper must assert the pair sums to zero before flush.

    This is a source-level structural check (the gate is read-only and does
    not run the DB): ``record_journal_entry`` must contain the zero-sum
    assertion, and the transfer path must pass TRANSFER_OUT/TRANSFER_IN.
    """
    path = _WALLET / "application" / "wallet_service.py"
    if not path.exists():
        findings.append("wallet_service.py not found")
        return
    text = path.read_text(encoding="utf-8")
    # Match the actual ``assert`` statement, not the same phrase quoted in a
    # comment or docstring — a substring check would pass on a file whose only
    # remaining mention is prose, which is the "presence is not a wiring"
    # trap. The assertion must be a real statement.
    if not re.search(
        r"^\s*assert\s+debit_tx\.amount\s*\+\s*credit_tx\.amount\s*==\s*0\b",
        text,
        re.MULTILINE,
    ):
        findings.append(
            "wallet_service.py: the journal zero-sum assertion is missing — "
            "an unbalanced pair mints or destroys money"
        )
    # Same reasoning for the transfer legs: require the enum members to be
    # passed as arguments, not merely named somewhere.
    if "debit_type=WalletTransactionType.TRANSFER_OUT" not in text:
        findings.append(
            "wallet_service.py: transfer debit leg must pass "
            "debit_type=WalletTransactionType.TRANSFER_OUT"
        )
    if "credit_type=WalletTransactionType.TRANSFER_IN" not in text:
        findings.append(
            "wallet_service.py: transfer credit leg must pass "
            "credit_type=WalletTransactionType.TRANSFER_IN"
        )


def main() -> int:
    as_json = "--json" in sys.argv
    findings: list[str] = []

    _check_no_float_money(findings)
    _check_persian_details(findings)
    _check_transfer_pair_balanced(findings)

    ok = not findings
    if as_json:
        print(json.dumps({
            "gate": "wallet_invariants",
            "ok": ok,
            "measured": True,
            "findings": findings,
        }, ensure_ascii=False))
    else:
        if ok:
            print("PASS: wallet money invariants hold "
                  "(no float money, transfer pair balanced, Persian errors).")
        else:
            print(f"FAIL: {len(findings)} wallet invariant finding(s):")
            for f in findings:
                print(f"  - {f}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
