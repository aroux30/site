import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  ORDER_STATUSES,
  ORDER_STATUS_TRANSITIONS,
  CUSTOMER_CANCELABLE,
  BOARD_COLUMNS,
  COLUMN_BACKEND_STATUSES,
  CUSTOMIZABLE_COLUMNS,
  OFF_BOARD_STATUSES,
  STATUS_TO_COLUMN,
  STATUS_VISUALS,
  readStoredColumns,
  statusToColumnFor,
  writeStoredColumns,
  type OrderStatus,
} from "@/lib/admin/order-domain";

/**
 * State-machine parity: TypeScript mirror ↔ Python source of truth.
 *
 * The frontend keeps a copy of the backend transition table so drag & drop
 * can refuse an illegal move before firing a request that is guaranteed to
 * fail. A copy that silently drifts is worse than no copy: the UI would
 * present a move as legal, the server would reject it, and the operator
 * would learn not to trust the board.
 *
 * This test reads the Python file and parses `_VALID_TRANSITIONS` and
 * `_CUSTOMER_CANCELABLE` from it — not a hand-typed copy of the expected
 * table. If someone edits the backend machine, this fails until the TS
 * mirror is updated (and vice versa).
 *
 * The parser is deliberately strict: if the Python table's shape changes so
 * the parser can no longer find it, the test FAILS (with a message saying
 * so) rather than passing vacuously on an empty parse.
 */

const BACKEND_SERVICE = join(
  process.cwd(),
  "..",
  "backend",
  "app",
  "modules",
  "orders",
  "application",
  "order_service.py",
);

function parsePythonTransitions(sourceRaw: string): Record<string, string[]> {
  // The backend file carries CRLF line endings on Windows; normalise before
  // any indexOf on "\n}\n" or the anchor search silently misses.
  const source = sourceRaw.replace(/\r\n/g, "\n");
  // Anchor on the exact declaration, not a substring of a comment.
  const declIndex = source.indexOf("_VALID_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {");
  if (declIndex === -1) {
    throw new Error(
      "_VALID_TRANSITIONS declaration not found in order_service.py — " +
        "the backend machine moved or was renamed; update this parser.",
    );
  }
  // Take everything from the declaration to the closing "}\n" at column 0.
  const afterDecl = source.slice(declIndex);
  const closeIndex = afterDecl.indexOf("\n}\n");
  if (closeIndex === -1) {
    throw new Error("could not find the end of _VALID_TRANSITIONS in order_service.py");
  }
  const body = afterDecl.slice(0, closeIndex);

  const table: Record<string, string[]> = {};
  // Entry shape:  OrderStatus.NAME: frozenset(\n { OrderStatus.A, ... }\n ),
  // or the one-line variant. Regex per entry: capture NAME, then the set body.
  const entryRe = /OrderStatus\.([A-Z_]+)\s*:\s*frozenset\(\s*\{([^}]*)\}\s*\)/g;
  let m: RegExpExecArray | null;
  while ((m = entryRe.exec(body)) !== null) {
    const from = (m[1] ?? "").toLowerCase();
    const targets = [...(m[2] ?? "").matchAll(/OrderStatus\.([A-Z_]+)/g)].map((t) =>
      (t[1] ?? "").toLowerCase(),
    );
    table[from] = targets.sort();
  }

  // The two terminal entries carry a trailing comment instead of members:
  //   OrderStatus.COMPLETED: frozenset(),  # terminal
  const terminalRe = /OrderStatus\.([A-Z_]+)\s*:\s*frozenset\(\s*\)/g;
  while ((m = terminalRe.exec(body)) !== null) {
    table[(m[1] ?? "").toLowerCase()] = [];
  }

  const count = Object.keys(table).length;
  // 7 since 2026-10-11: the twelve-status physical-store chain was replaced by
  // the digital-store chain (waiting_payment_gateway, waiting_payment_card, pending, processing,
  // completed, canceled, refunded). This guard exists so a silent shape change
  // is loud — it must be bumped deliberately, not made permissive.
  if (count !== 7) {
    throw new Error(
      `parsed ${count} statuses from _VALID_TRANSITIONS, expected 7 — ` +
        "the Python table changed shape and this parser needs updating " +
        `(parsed: ${Object.keys(table).join(", ")})`,
    );
  }
  return table;
}

function parsePythonCustomerCancelable(sourceRaw: string): string[] {
  const source = sourceRaw.replace(/\r\n/g, "\n");
  const idx = source.indexOf("_CUSTOMER_CANCELABLE: frozenset[OrderStatus] = frozenset(");
  if (idx === -1) {
    throw new Error("_CUSTOMER_CANCELABLE declaration not found in order_service.py");
  }
  const chunk = source.slice(idx, idx + 400);
  const names = [...chunk.matchAll(/OrderStatus\.([A-Z_]+)/g)].map((t) =>
    (t[1] ?? "").toLowerCase(),
  );
  if (names.length === 0) {
    throw new Error("parsed zero statuses from _CUSTOMER_CANCELABLE");
  }
  return names.sort();
}

describe("order status enum parity", () => {
  const pythonSource = readFileSync(BACKEND_SERVICE, "utf-8");

  it("TS ORDER_STATUSES matches the backend OrderStatus enum exactly", () => {
    // Parse the enum block from models.py rather than the service.
    // Normalise CRLF first (same reason as parsePythonTransitions).
    const models = readFileSync(
      join(
        process.cwd(),
        "..",
        "backend",
        "app",
        "modules",
        "orders",
        "domain",
        "models.py",
      ),
      "utf-8",
    ).replace(/\r\n/g, "\n");
    const enumIdx = models.indexOf("class OrderStatus(str, enum.Enum):");
    expect(enumIdx, "OrderStatus enum not found in models.py").toBeGreaterThan(-1);
    const enumBody = models.slice(enumIdx, models.indexOf("\n\n\n", enumIdx));
    const values = [...enumBody.matchAll(/=\s*"([a-z_]+)"/g)].map((m) => m[1]);

    // 7 since 2026-10-11: the physical-store chain was replaced by the
    // digital-store chain (payment buckets + pending → processing → completed
    // + canceled/refunded).
    expect(values.length, "enum values parsed").toBe(7);
    expect([...ORDER_STATUSES].sort()).toEqual([...values].sort());
  });

  it("every status has a visual (no status can render unlabeled)", () => {
    for (const status of ORDER_STATUSES) {
      expect(STATUS_VISUALS[status], `STATUS_VISUALS missing ${status}`).toBeDefined();
      expect(STATUS_VISUALS[status].label.length).toBeGreaterThan(0);
    }
  });

  it("every status is either in a board lane or an explicit off-board status", () => {
    // A status is visible on the board when it rides a lane, not only when it
    // is a column name: the two payment buckets have no column of their own but
    // live in «در حال پردازش».
    const covered = new Set<string>([
      ...BOARD_COLUMNS.flatMap((lane) => COLUMN_BACKEND_STATUSES[lane] ?? []),
      ...OFF_BOARD_STATUSES,
    ]);
    for (const status of ORDER_STATUSES) {
      expect(covered.has(status), `${status} is neither on the board nor listed off-board`).toBe(
        true,
      );
    }
  });

  it("the payment distinction survives: both waiting buckets are their own columns", () => {
    // The whole reason the enum kept two payment statuses is that they are
    // handled differently — waiting_payment_gateway expires to canceled on a timer,
    // waiting_payment_card waits for an admin and never expires. Each must therefore be
    // on the board as its OWN column (never invisible, never collapsed together).
    for (const status of ["waiting_payment_gateway", "waiting_payment_card"] as const) {
      expect(STATUS_TO_COLUMN[status], `${status} is off the board`).toBe(status);
      expect(
        COLUMN_BACKEND_STATUSES[status],
        `${status} does not hold exactly itself`,
      ).toEqual([status]);
      expect(STATUS_VISUALS[status].label).not.toBe(STATUS_VISUALS.processing.label);
    }
  });

  it("every customizable column is a real, distinct column", () => {
    // The settings popover renders one checkbox per entry; a duplicate or an
    // unknown key would produce two checkboxes bound to the same toggle.
    expect(new Set(CUSTOMIZABLE_COLUMNS).size).toBe(CUSTOMIZABLE_COLUMNS.length);
    for (const column of CUSTOMIZABLE_COLUMNS) {
      expect(ORDER_STATUSES as readonly string[], `${column} is not a status`).toContain(column);
      expect(
        (COLUMN_BACKEND_STATUSES[column] ?? []).length,
        `${column} holds nothing`,
      ).toBeGreaterThan(0);
    }
  });

  it("the default board columns are a subset of the customizable ones", () => {
    // A default column the popover cannot toggle would be a column an operator
    // can never remove.
    for (const column of BOARD_COLUMNS) {
      expect(CUSTOMIZABLE_COLUMNS as readonly string[]).toContain(column);
    }
  });
});

describe("column customization (persisted selection)", () => {
  // A fake Storage: the real one is unavailable under jsdom's default config
  // and, more importantly, these tests must not depend on machine state.
  function fakeStorage(initial?: string) {
    const data = new Map<string, string>();
    if (initial !== undefined) data.set("admin.orders.boardColumns", initial);
    return {
      getItem: (k: string) => data.get(k) ?? null,
      setItem: (k: string, v: string) => void data.set(k, v),
      read: () => data.get("admin.orders.boardColumns"),
    };
  }

  it("no stored key means no preference (the caller uses the defaults)", () => {
    expect(readStoredColumns(fakeStorage())).toBeNull();
    expect(readStoredColumns(fakeStorage("not json at all"))).toBeNull();
    expect(readStoredColumns(fakeStorage('{"not":"an array"}'))).toBeNull();
  });

  it("a stored selection round-trips", () => {
    const storage = fakeStorage();
    writeStoredColumns(["canceled", "completed"], storage);
    expect(readStoredColumns(storage)).toEqual(["completed", "canceled"]);
  });

  it("restores board order regardless of the order they were saved in", () => {
    // The lanes are ordered left-to-right; a hand-edited or stale key must not
    // be able to shuffle «لغو شده» in front of «در حال پردازش».
    const storage = fakeStorage(JSON.stringify(["refunded", "canceled", "processing"]));
    expect(readStoredColumns(storage)).toEqual(["processing", "canceled", "refunded"]);
  });

  it("an empty or all-unknown selection falls back rather than blanking the board", () => {
    // A board with no columns shows no orders at all, so a corrupt value must
    // be treated as "no preference", never as "hide everything".
    expect(readStoredColumns(fakeStorage("[]"))).toBeNull();
    expect(readStoredColumns(fakeStorage(JSON.stringify(["nonsense", "packing"])))).toBeNull();
  });

  it("unknown entries are dropped but the valid ones survive", () => {
    // `packing` and `shipped` were deleted from the backend enum; an old
    // browser key naming them must not throw or resurrect a dead column.
    const storage = fakeStorage(JSON.stringify(["packing", "completed", "shipped"]));
    expect(readStoredColumns(storage)).toEqual(["completed"]);
  });

  it("duplicates collapse to one column", () => {
    const storage = fakeStorage(JSON.stringify(["completed", "completed"]));
    expect(readStoredColumns(storage)).toEqual(["completed"]);
  });

  it("a missing storage (SSR, blocked cookies) is a no-op, not a crash", () => {
    expect(readStoredColumns(null)).toBeNull();
    expect(() => writeStoredColumns(["completed"], null)).not.toThrow();
  });

  it("a storage that throws on write does not break the toggle", () => {
    // Private-mode Safari and quota errors both throw; losing the preference
    // is acceptable, breaking the board is not.
    const hostile = {
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    };
    expect(() => writeStoredColumns(["completed"], hostile)).not.toThrow();
  });

  it("statusToColumnFor tracks the selection, not the default wiring", () => {
    // With every status its own column, dropping one from the selection must
    // make it unreachable — and dropping a *different* one must not move the
    // survivors into the hole.
    expect(statusToColumnFor("refunded", BOARD_COLUMNS)).toBe("refunded");
    expect(statusToColumnFor("refunded", ["completed", "canceled"])).toBeUndefined();
    expect(statusToColumnFor("completed", ["processing"])).toBeUndefined();
    // …while every surviving column still owns exactly itself.
    expect(statusToColumnFor("waiting_payment_card", ["processing", "pending"])).toBeUndefined();
    expect(statusToColumnFor("pending", ["processing", "pending"])).toBe("pending");
  });
});

describe("transition table parity (TS mirror vs Python source)", () => {
  const pythonSource = readFileSync(BACKEND_SERVICE, "utf-8");
  const python = parsePythonTransitions(pythonSource);

  it("TS and Python agree on every transition", () => {
    for (const status of ORDER_STATUSES) {
      const tsTargets = [...(ORDER_STATUS_TRANSITIONS[status as OrderStatus] ?? [])].sort();
      const pyTargets = python[status] ?? [];
      expect(
        tsTargets,
        `transition mismatch for "${status}": TS=${tsTargets.join(",")} PY=${pyTargets.join(",")}`,
      ).toEqual(pyTargets);
    }
  });

  it("customer-cancelable set matches", () => {
    const pythonCancelable = parsePythonCustomerCancelable(pythonSource);
    expect([...CUSTOMER_CANCELABLE].sort()).toEqual(pythonCancelable);
  });

  it("terminal statuses have no outgoing transitions on either side", () => {
    for (const status of ORDER_STATUSES) {
      const tsLen = (ORDER_STATUS_TRANSITIONS[status as OrderStatus] ?? []).length;
      const pyLen = (python[status] ?? []).length;
      if (tsLen === 0) expect(pyLen, `PY has transitions out of terminal ${status}`).toBe(0);
      if (pyLen === 0) expect(tsLen, `TS has transitions out of terminal ${status}`).toBe(0);
    }
  });
});
