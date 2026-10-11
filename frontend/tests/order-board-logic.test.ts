import { describe, expect, it } from "vitest";

import {
  BOARD_COLUMNS,
  COLUMN_BACKEND_STATUSES,
  CUSTOMIZABLE_COLUMNS,
  OFF_BOARD_STATUSES,
  PIPELINE_ORDER,
  STATUS_TO_COLUMN,
  ORDER_STATUSES,
  ORDER_STATUS_TRANSITIONS,
  PAYMENT_VISUALS,
  STATUS_VISUALS,
  advanceActionLabel,
  derivePaymentStatus,
  hoursSince,
  isOrderStale,
  isTerminal,
  isTransitionAllowed,
  nextInPipeline,
  resolveDropTarget,
  rialsToToman,
  statusToColumnFor,
  type OrderStatus,
} from "@/lib/admin/order-domain";

/**
 * Board/list domain logic — the pieces that decide what an operator sees
 * and what a drag is allowed to do. Every assertion here corresponds to a
 * rule the old pages violated:
 *  - every status must render somewhere (the old board dropped 5 statuses)
 *  - the pipeline advance button must not skip stages
 *  - payment status must never be invented as "paid"
 *  - stale flags must only fire for statuses where waiting matters
 */

/** Lane members of a board column; the lanes always exist (BOARD_COLUMNS). */
const laneMembers = (lane: OrderStatus): readonly OrderStatus[] =>
  COLUMN_BACKEND_STATUSES[lane] ?? [];

describe("board columns", () => {
  it("the default board is all seven statuses, one column each", () => {
    // Owner decision (2026-10-11, revised): every status is its OWN column —
    // «در انتظار تایید پرداخت», «در انتظار تایید کارت به کارت», «در حال انجام»,
    // «در حال پردازش», «تکمیل شده», «لغو شده» and «بازگشت وجه».
    expect(BOARD_COLUMNS).toEqual([
      "waiting_payment_gateway",
      "waiting_payment_card",
      "pending",
      "processing",
      "completed",
      "canceled",
      "refunded",
    ]);
  });

  it("every status is visible: inside a column's lane or explicitly off-board", () => {
    // Visibility is no longer "is a column name" — «تایید شده» has no column
    // of its own but rides the «در حال پردازش» lane. The real rule is that
    // every status is either in some lane or listed off-board.
    const covered = new Set<string>([
      ...BOARD_COLUMNS.flatMap((lane) => COLUMN_BACKEND_STATUSES[lane] ?? []),
      ...OFF_BOARD_STATUSES,
    ]);
    for (const status of ORDER_STATUSES) {
      expect(covered.has(status), `${status} would be invisible`).toBe(true);
    }
    // …and nothing is both on and off board.
    for (const status of OFF_BOARD_STATUSES) {
      expect(STATUS_TO_COLUMN[status], `${status} is both on and off board`).toBeUndefined();
    }
  });
});

/**
 * The list/board desync the owner reported (2026-10-10): the list chips and
 * the board columns carried separate status lists, so the same label showed
 * different orders in the two views. Both views now resolve their filter
 * through `COLUMN_BACKEND_STATUSES`; these are the rules that keep them
 * agreeing, and each one has been negative-tested.
 */
describe("lane grouping (list and board must resolve identically)", () => {
  it("every status is claimed by exactly one lane", () => {
    const owner = new Map<string, string[]>();
    for (const lane of BOARD_COLUMNS) {
      for (const member of laneMembers(lane)) {
        owner.set(member, [...(owner.get(member) ?? []), lane]);
      }
    }
    const visible = [...new Set(BOARD_COLUMNS.flatMap((l) => laneMembers(l)))];
    for (const status of visible) {
      expect(
        owner.get(status)?.length,
        `${status} appears in ${owner.get(status)?.length} columns (double-counted headers)`,
      ).toBe(1);
    }
  });

  it("STATUS_TO_COLUMN covers every lane member exactly once", () => {
    for (const lane of BOARD_COLUMNS) {
      for (const member of laneMembers(lane)) {
        expect(STATUS_TO_COLUMN[member], `${member} has no column`).toBe(lane);
      }
    }
  });

  it("off-board statuses have no column and are exactly the unmapped ones", () => {
    for (const status of OFF_BOARD_STATUSES) {
      expect(STATUS_TO_COLUMN[status], `${status} is off-board but has a column`).toBeUndefined();
    }
    const mapped = new Set(Object.keys(STATUS_TO_COLUMN));
    for (const status of ORDER_STATUSES) {
      const expected = mapped.has(status) ? false : true;
      expect(OFF_BOARD_STATUSES.includes(status), `${status} misclassified`).toBe(expected);
    }
  });

  it("grouped lanes are ordered along the fulfillment path", () => {
    for (const lane of BOARD_COLUMNS) {
      const members = laneMembers(lane);
      if (members.length < 2) continue;
      const indexes = members.map((m) => PIPELINE_ORDER.indexOf(m));
      expect(
        indexes.every((i) => i >= 0),
        `${lane} holds a status outside the chain: ${members.join(",")}`,
      ).toBe(true);
      expect(
        indexes,
        `${lane} members are out of pipeline order: ${members.join(",")}`,
      ).toEqual([...indexes].sort((a, b) => a - b));
    }
  });

  it("both payment buckets are on the board as their own columns and stay distinguishable", () => {
    // The one distinction the backend keeps is payment: a gateway order is
    // abandoned by the customer and expires, a card-to-card receipt waits for
    // an admin forever. Both are active work and both get their own lane, so
    // neither collapses into the other.
    for (const status of ["waiting_payment_gateway", "waiting_payment_card"] as const) {
      expect(BOARD_COLUMNS, `${status} is not a column`).toContain(status);
      expect(STATUS_TO_COLUMN[status]).toBe(status);
      expect(laneMembers(status)).toEqual([status]);
    }
    expect(STATUS_VISUALS.waiting_payment_gateway.label).not.toBe(STATUS_VISUALS.waiting_payment_card.label);
    expect(STATUS_VISUALS.waiting_payment_gateway.dot).not.toBe(STATUS_VISUALS.waiting_payment_card.dot);
  });

  it("refunded is a column of its own, toggleable like the rest", () => {
    // A refund is a money outcome reached through /payments/{id}/refund, but
    // the owner asked for every status to be visible as its own lane, so it
    // ships ON and can be switched off like any other column.
    expect(STATUS_TO_COLUMN.refunded).toBe("refunded");
    expect(BOARD_COLUMNS).toContain("refunded");
    expect(laneMembers("refunded")).toEqual(["refunded"]);
    expect(CUSTOMIZABLE_COLUMNS).toContain("refunded");
  });

  it("the whole chain pending→completed is on the board (no advance runs off the end)", () => {
    for (const status of PIPELINE_ORDER) {
      expect(STATUS_TO_COLUMN[status], `${status} has no column`).toBeDefined();
    }
  });
});

describe("resolveDropTarget (what a drop actually PATCHes)", () => {
  it("returns a status that is a member of the lane", () => {
    for (const from of ORDER_STATUSES) {
      for (const lane of BOARD_COLUMNS) {
        const target = resolveDropTarget(from, lane);
        if (target === null) continue;
        expect(
          laneMembers(lane),
          `${from} → ${lane} produced ${target}, which is not in that lane`,
        ).toContain(target);
      }
    }
  });

  it("never returns an ILLEGAL transition — the core safety rule", () => {
    for (const from of ORDER_STATUSES) {
      for (const lane of BOARD_COLUMNS) {
        const target = resolveDropTarget(from, lane);
        if (target === null) continue;
        expect(
          isTransitionAllowed(from, target),
          `${from} → ${target} (via lane ${lane}) is not allowed by the state machine`,
        ).toBe(true);
      }
    }
  });

  it("never asks for a jump past a stage (one step, not a skip)", () => {
    // A pending order dropped on «در حال پردازش» must land on `processing` —
    // the FIRST lane member one legal step away — not on `completed`, which
    // the backend rejects.
    expect(resolveDropTarget("pending", "processing")).toBe("processing");
    expect(resolveDropTarget("pending", "completed")).toBeNull();
    expect(resolveDropTarget("processing", "completed")).toBe("completed");
  });

  it("both payment buckets step into pending, not past it", () => {
    // waiting_payment_gateway and waiting_payment_card share an identical transition set, so
    // the resolver must offer them the same single legal step.
    expect(resolveDropTarget("waiting_payment_gateway", "pending")).toBe("pending");
    expect(resolveDropTarget("waiting_payment_card", "pending")).toBe("pending");
    // …and neither may jump straight to processing.
    expect(isTransitionAllowed("waiting_payment_gateway", "processing")).toBe(false);
    expect(isTransitionAllowed("waiting_payment_card", "processing")).toBe(false);
  });

  it("returns null when no lane member is reachable", () => {
    expect(resolveDropTarget("completed", "processing")).toBeNull();
    expect(resolveDropTarget("canceled", "processing")).toBeNull();
    expect(resolveDropTarget("refunded", "processing")).toBeNull();
  });

  it("a drop onto a 1:1 column sets exactly that status", () => {
    expect(resolveDropTarget("completed", "completed")).toBeNull(); // already there
    expect(resolveDropTarget("pending", "completed")).toBeNull();
    expect(resolveDropTarget("pending", "canceled")).toBe("canceled");
    expect(resolveDropTarget("processing", "refunded")).toBe("refunded");
  });

  it("a 1:1 column accepts nothing — its own status is skipped, not matched", () => {
    // Every lane is now one status wide, so the resolver's self-match skip is
    // the ONLY thing standing between a drop and a self-assignment (which the
    // backend rejects: no status transitions to itself). The own-lane no-op is
    // enforced by the BOARD; the resolver must still return null rather than
    // hand back the status the card already has.
    for (const lane of BOARD_COLUMNS) {
      expect(laneMembers(lane), `${lane} is not 1:1`).toEqual([lane]);
      expect(
        resolveDropTarget(lane, lane),
        `${lane} resolved a drop onto itself`,
      ).toBeNull();
    }
  });

  it("pending advances by drag to processing, and the payment buckets to pending", () => {
    // With one column per status these are all ordinary cross-lane drops: the
    // card lands on the column that IS the status it steps to.
    expect(resolveDropTarget("pending", "processing")).toBe("processing");
    expect(resolveDropTarget("waiting_payment_gateway", "pending")).toBe("pending");
    expect(resolveDropTarget("processing", "completed")).toBe("completed");
  });
});

describe("advance button follows the real state machine", () => {
  it("every advance is a legal move to the NEXT reachable pipeline stage", () => {
    for (const status of ORDER_STATUSES) {
      const next = nextInPipeline(status);
      if (!next) continue;
      expect(
        isTransitionAllowed(status, next),
        `${status} → ${next} is not legal`,
      ).toBe(true);
      // Nothing between the current stage and `next` is reachable either —
      // otherwise the walk stopped early and the button skips a stage.
      const from = PIPELINE_ORDER.indexOf(status);
      const to = PIPELINE_ORDER.indexOf(next);
      expect(to, `${status} → ${next} moves backwards`).toBeGreaterThan(from);
      for (let i = from + 1; i < to; i++) {
        expect(
          isTransitionAllowed(status, PIPELINE_ORDER[i]!),
          `${status} → ${PIPELINE_ORDER[i]} is legal but was skipped`,
        ).toBe(false);
      }
    }
  });

  it("the branch at the head of the chain never crosses to the other bucket", () => {
    // The one structural difference from the old linear chain: both payment
    // buckets step into `pending`, so a naive index+1 walk would make
    // waiting_payment_gateway advance to waiting_payment_card — a 422 the moment it is fired.
    expect(nextInPipeline("waiting_payment_gateway")).toBe("pending");
    expect(nextInPipeline("waiting_payment_card")).toBe("pending");
    expect(isTransitionAllowed("waiting_payment_gateway", "waiting_payment_card")).toBe(false);
    expect(isTransitionAllowed("waiting_payment_card", "waiting_payment_gateway")).toBe(false);
  });

  it("EVERY chain advance crosses to a different column", () => {
    // Each status is its own column now, so the same-lane guard the board
    // uses to ignore DROPS can never swallow an advance click: the target is
    // always a different lane. This pins the fact, so the two paths cannot be
    // re-merged into one guard.
    for (const status of ["waiting_payment_gateway", "waiting_payment_card", "pending", "processing"] as const) {
      const next = nextInPipeline(status);
      if (!next) continue;
      expect(
        statusToColumnFor(next, BOARD_COLUMNS),
        `${status} → ${next} lands in the SAME column, so the same-lane drop guard would swallow it`,
      ).not.toBe(statusToColumnFor(status, BOARD_COLUMNS));
    }
    // The last chain move is processing → completed, still on the board.
    expect(statusToColumnFor(nextInPipeline("processing")!, BOARD_COLUMNS)).toBe("completed");
  });

  it("advancing never leaves the board — every chain stage has a column", () => {
    // The old map had processing → completed under a machine where that move
    // was REJECTED, so «تکمیل سفارش» could only fail. And a shorter lane made
    // the last stage advance off the board entirely.
    for (const status of ORDER_STATUSES) {
      const next = nextInPipeline(status);
      if (!next) continue;
      expect(STATUS_TO_COLUMN[next], `${next} (target of ${status}) has no column`).toBeDefined();
    }
  });

  it("processing does NOT skip to a terminal state", () => {
    // Explicit regression guard: the backend machine has no shortcut from
    // processing except completed/canceled/refunded, and `nextInPipeline` must
    // walk the real chain rather than jumping to the lane's last member.
    expect(nextInPipeline("processing")).toBe("completed");
    expect(isTransitionAllowed("processing", "completed")).toBe(true);
    // pending must NOT offer completed (the old bug: the button could only 422).
    expect(isTransitionAllowed("pending", "completed")).toBe(false);
    expect(resolveDropTarget("pending", "completed")).toBeNull();
  });

  it("every advance label names its own stage", () => {
    // Both payment buckets advance into `pending`, so they share the label —
    // but it must be the payment one, not a generic "next step".
    expect(advanceActionLabel("waiting_payment_gateway")).toBe("تایید پرداخت");
    expect(advanceActionLabel("waiting_payment_card")).toBe("تایید پرداخت");
    expect(advanceActionLabel("pending")).toBe("شروع پردازش");
    expect(advanceActionLabel("processing")).toBe("تکمیل سفارش");
  });

  it("completed has no next stage", () => {
    expect(nextInPipeline("completed")).toBeNull();
    expect(advanceActionLabel("completed")).toBeNull();
  });

  it("canceled and refunded are terminal", () => {
    // Both are exits, not stages: nothing follows a closed order.
    expect(nextInPipeline("canceled")).toBeNull();
    expect(nextInPipeline("refunded")).toBeNull();
    expect(isTerminal("canceled")).toBe(true);
    expect(isTerminal("refunded")).toBe(true);
  });

  it("each advance TARGET has exactly one label, and none is a generic placeholder", () => {
    // Uniqueness is per target, not per source: waiting_payment_gateway and
    // waiting_payment_card both step into `pending`, so they legitimately share a
    // label. What must never happen is two DIFFERENT stages wearing the same
    // generic wording — that is what made the old buttons indistinguishable.
    const byTarget = new Map<OrderStatus, string>();
    for (const status of ORDER_STATUSES) {
      const next = nextInPipeline(status);
      const label = advanceActionLabel(status);
      if (!next || !label) continue;
      const existing = byTarget.get(next);
      if (existing) {
        expect(existing, `${status} and an earlier status both advance to ${next}`).toBe(label);
      } else {
        byTarget.set(next, label);
      }
    }
    expect(byTarget.size).toBeGreaterThan(0);
    // No stage falls through to the "مرحله بعد" catch-all.
    expect([...byTarget.values()]).not.toContain("مرحله بعد");
  });
});

describe("advance button", () => {
  it("never offers an advance from a terminal status", () => {
    for (const status of ORDER_STATUSES) {
      if (isTerminal(status)) {
        expect(advanceActionLabel(status), `${status} is terminal but offers advance`).toBeNull();
        expect(nextInPipeline(status), `${status} is terminal but has a next stage`).toBeNull();
      }
    }
  });

  it("a canceled or refunded order offers no way forward", () => {
    // These are reached by cancellation/refund, not by advancing, so a button
    // promising movement out of them would only ever 422.
    for (const status of ["canceled", "refunded", "completed"] as const) {
      expect(advanceActionLabel(status)).toBeNull();
    }
  });
});

describe("payment derivation (never invent 'paid')", () => {
  it("no payment rows → unpaid, not paid", () => {
    expect(derivePaymentStatus(null)).toBe("unpaid");
    expect(derivePaymentStatus(undefined)).toBe("unpaid");
    expect(derivePaymentStatus([])).toBe("unpaid");
  });

  it("a completed payment → paid", () => {
    expect(derivePaymentStatus([{ status: "completed" }])).toBe("paid");
    expect(
      derivePaymentStatus([{ status: "failed" }, { status: "completed" }]),
    ).toBe("paid");
  });

  it("refunded beats completed when both exist", () => {
    expect(
      derivePaymentStatus([{ status: "completed" }, { status: "refunded" }]),
    ).toBe("refunded");
  });

  it("only failed rows → failed; pending/processing → pending", () => {
    expect(derivePaymentStatus([{ status: "failed" }])).toBe("failed");
    expect(derivePaymentStatus([{ status: "pending" }])).toBe("pending");
    expect(derivePaymentStatus([{ status: "processing" }])).toBe("pending");
  });

  it("every derivable status has a visual", () => {
    for (const s of ["paid", "pending", "failed", "refunded", "unpaid"] as const) {
      expect(PAYMENT_VISUALS[s], `missing visual for ${s}`).toBeDefined();
    }
  });
});

describe("staleness", () => {
  const iso = (hoursAgo: number) =>
    new Date(Date.now() - hoursAgo * 3_600_000).toISOString();

  it("flags active statuses after 24h", () => {
    // Both payment buckets are tracked: waiting_payment_card in particular is an
    // operator's job that never expires, so a receipt sitting unread for a day
    // is exactly the thing that should glow.
    for (const status of ["waiting_payment_gateway", "waiting_payment_card", "pending", "processing"] as const) {
      expect(isOrderStale(status, iso(25)), `${status} @25h should be stale`).toBe(true);
      expect(isOrderStale(status, iso(23)), `${status} @23h should not be stale`).toBe(false);
    }
  });

  it("never flags statuses where waiting is normal or final", () => {
    for (const status of ["completed", "canceled", "refunded"] as const) {
      expect(isOrderStale(status, iso(100)), `${status} must not be stale`).toBe(false);
    }
  });

  it("an unparsable date is not stale (never a false alarm)", () => {
    expect(isOrderStale("pending", "not-a-date")).toBe(false);
    expect(hoursSince("not-a-date")).toBe(0);
  });
});

describe("money conversion", () => {
  it("converts Rials to integer Toman, truncating", () => {
    expect(rialsToToman(1_000_000)).toBe(100_000);
    expect(rialsToToman(15)).toBe(1);
    expect(rialsToToman(0)).toBe(0);
    expect(rialsToToman(null)).toBe(0);
    expect(rialsToToman(undefined)).toBe(0);
  });
});

describe("status visuals", () => {
  it("each status has distinct label and all class slots filled", () => {
    const labels = new Set<string>();
    for (const status of ORDER_STATUSES) {
      const v = STATUS_VISUALS[status];
      expect(v.label.length).toBeGreaterThan(0);
      expect(v.description.length).toBeGreaterThan(0);
      expect(v.dot.length).toBeGreaterThan(0);
      expect(v.chip.length).toBeGreaterThan(0);
      expect(v.soft.length).toBeGreaterThan(0);
      expect(v.solid.length).toBeGreaterThan(0);
      expect(labels.has(v.label), `duplicate label ${v.label}`).toBe(false);
      labels.add(v.label);
    }
  });
});

describe("transition sanity (in-module invariants)", () => {
  it("every transition target is a known status", () => {
    const known = new Set<string>(ORDER_STATUSES);
    for (const status of ORDER_STATUSES) {
      for (const target of ORDER_STATUS_TRANSITIONS[status]) {
        expect(known.has(target), `${status} → ${target}: unknown target`).toBe(true);
      }
    }
  });

  it("no status transitions to itself", () => {
    for (const status of ORDER_STATUSES) {
      expect(
        ORDER_STATUS_TRANSITIONS[status].includes(status),
        `${status} → itself`,
      ).toBe(false);
    }
  });
});
