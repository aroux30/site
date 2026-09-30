# Quality gates — contract and naming

## Purpose

An independent, clean-room implementation of the layered quality-gate pattern. The platform already has a strong domain core (row-locked inventory reservations, payment idempotency, a transactional outbox with `SKIP LOCKED` claiming and lease reclaim, an append-only wallet ledger, 478 backend and 255 frontend tests) but **no continuous-integration pipeline and no automated invariant gates**. This contract defines the gates that close that gap.

The reference repository that inspired this pattern has no reuse license; no source, configuration, workflow text, script, or document from it may be copied. Everything here is written for this codebase, its tools, and its stack.

## Gate principles

1. **A gate that cannot fail is not a gate.** Every script must have a demonstrable non-zero exit path, and at least one test proving it fails on the condition it claims to catch.
2. **Unmeasured is not PASS.** Any check a run did not perform must be reported as `not-run`, never as a pass.
3. **Fail loudly on missing prerequisites.** A missing database, unreachable server, or absent tool must produce an explicit error and non-zero exit — never a silently green skip.
4. **Named guarantees, not one big suite.** A dedicated workflow job that runs one specific check is legible as a promise; "run everything" is not.
5. **No rule weakening to make a gate pass.** Gates are fixed by correcting the code or by an explicit, documented, narrow allowance — never by `--exit-zero`, blanket ignores, or disabling a test.
6. **Gates must not mutate financial state.** Any gate that reads payments, orders, refunds, wallet, or inventory is read-only.

## Gate inventory

| Gate | Script | Workflow | Catches |
|---|---|---|---|
| Secret scanning | `scripts/gates/secret_scan.py` | `ci.yml` | Committed credentials, keys, tokens |
| Schema drift | `scripts/gates/schema_drift.py` | `ci.yml` | Live database diverging from the SQLAlchemy models / Alembic head |
| Environment contract | `scripts/gates/env_contract.py` | `ci.yml` | A variable declared in one deploy surface but missing or renamed in another |
| Money invariants | `scripts/gates/money_invariants.py` | `integrity-gates.yml` | Float/`Decimal` arithmetic, `round()`/`int()` coercion, or non-integer storage on monetary paths |
| Order lifecycle audit | `backend/app/modules/audit/application/lifecycle_auditor.py` | `integrity-gates.yml` | An order whose derived payment/fulfilment/return axes are mutually impossible |
| Concurrency and recovery | named pytest selections | `integrity-gates.yml` | Lost-update races, oversell, duplicate capture, worker-crash reclaim |
| i18n debt | `scripts/gates/i18n_completeness.mjs` | `frontend-gates.yml` | New hardcoded Persian literals, catalog key drift |
| Accessibility | `scripts/gates/a11y_gate.mjs` | `frontend-gates.yml` | WCAG regressions on customer funnels |
| Responsive journeys | `scripts/gates/responsive_gate.mjs` | `frontend-gates.yml` | Mobile overflow, clipped docked surfaces, zoom reflow |

## Interface contract

Every gate script in `scripts/gates/`:

- exits `0` when the condition is satisfied and non-zero otherwise;
- accepts `--json` and, with it, prints a single machine-readable object on stdout containing at least `{"gate": str, "ok": bool, "findings": [...], "measured": bool}`;
- without `--json`, prints a short human summary only;
- writes nothing outside its own stdout/stderr and any explicitly named evidence file;
- is runnable locally with the same command CI uses — a gate you cannot reproduce on your machine is not diagnosable.

`measured: false` means the gate could not perform its check (missing tool, unreachable dependency) and **must** be treated as a failure by CI unless the job explicitly permits that state.

## Money invariants (this platform's hard constraint)

Money is integer Iranian rials everywhere. On any module path that computes, stores, or compares money:

- no `float` or `Decimal` in a monetary annotation, literal, or comparison;
- no `round()`, `math.floor`, `math.ceil`, or `int(float_value)` coercion of an amount;
- stored columns are integer (`BigInteger`/`Numeric(...,0)`), never floating point;
- proportions (tax, discount, markup) are expressed as integer basis points and applied with explicit integer rounding, not as floats.

The gate reports the file and line of every violation. Exemptions require an inline, reasoned marker — never a directory-level exclusion.

## Lifecycle audit

The order aggregate keeps a single 12-state `status`. Deriving the implied **payment**, **fulfilment**, and **return** axes from the authoritative records (payments, shipments, returns, status history) lets an auditor detect combinations that must not exist — for example a captured payment on an order that never left `PENDING`, or a delivered shipment on a cancelled order.

The auditor is **read-only** and reuses the durable reconciliation findings store: it may write finding rows and audit-trail entries, and must never modify an order, payment, shipment, refund, or inventory row.

## Evidence and honesty

- Any marketing or UI claim about a capability must be traceable to the capability registry, which is conservative by construction: an external provider is never reported `LIVE` on local configuration alone.
- A document that records a point-in-time assessment and is later superseded must carry its own supersession banner naming what changed. A stale optimistic document is a defect.
- Release decisions must record, in writing, any capability accepted as incomplete.