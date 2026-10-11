import { describe, expect, it } from "vitest";

import {
  TICKET_BOARD_COLUMNS,
  TICKET_NEXT_STEP,
  TICKET_PRIORITIES,
  TICKET_PRIORITY_VISUALS,
  TICKET_STATUSES,
  TICKET_STATUS_VISUALS,
  TICKET_TRANSITIONS,
  formatTicketRelativeTime,
  hoursSinceUpdate,
  isTicketActive,
  isTicketStale,
  isTicketTerminal,
  isTicketTransitionAllowed,
  ticketAdvanceLabel,
  type TicketStatus,
} from "@/lib/admin/ticket-domain";

/**
 * Ticket board/list domain logic.
 *
 * IMPORTANT CONTEXT: the support backend has NO state machine (the PATCH
 * accepts any status), so unlike the orders parity test there is nothing
 * to mirror from Python. The transition table is UI policy; these tests
 * pin its internal invariants and the presentation coverage that the old
 * tickets page lacked (it rendered a raw user UUID and had no priority
 * filter at all).
 */

describe("ticket status coverage", () => {
  it("every status is a board column", () => {
    expect([...TICKET_BOARD_COLUMNS].sort()).toEqual([...TICKET_STATUSES].sort());
  });

  it("every status and priority has a complete visual", () => {
    for (const status of TICKET_STATUSES) {
      const v = TICKET_STATUS_VISUALS[status];
      expect(v.label.length).toBeGreaterThan(0);
      expect(v.description.length).toBeGreaterThan(0);
      expect(v.dot.length).toBeGreaterThan(0);
      expect(v.chip.length).toBeGreaterThan(0);
      expect(v.soft.length).toBeGreaterThan(0);
      expect(v.solid.length).toBeGreaterThan(0);
    }
    for (const priority of TICKET_PRIORITIES) {
      const v = TICKET_PRIORITY_VISUALS[priority];
      expect(v.label.length).toBeGreaterThan(0);
      expect(v.chip.length).toBeGreaterThan(0);
      expect(v.dot.length).toBeGreaterThan(0);
    }
  });

  it("labels are unique (no copy-paste drift)", () => {
    const labels = TICKET_STATUSES.map((s) => TICKET_STATUS_VISUALS[s].label);
    expect(new Set(labels).size).toBe(labels.length);
  });
});

describe("transition policy invariants", () => {
  it("every transition target is a known status", () => {
    const known = new Set<string>(TICKET_STATUSES);
    for (const status of TICKET_STATUSES) {
      for (const target of TICKET_TRANSITIONS[status]) {
        expect(known.has(target), `${status} → ${target}: unknown target`).toBe(true);
      }
    }
  });

  it("no status transitions to itself", () => {
    for (const status of TICKET_STATUSES) {
      expect(TICKET_TRANSITIONS[status].includes(status), `${status} → itself`).toBe(false);
    }
  });

  it("closed only reopens to open", () => {
    expect([...TICKET_TRANSITIONS.closed]).toEqual(["open"]);
  });

  it("every status is reachable from open (no dead workflow branch)", () => {
    // BFS from open across the transition graph.
    const seen = new Set<TicketStatus>(["open"]);
    const queue: TicketStatus[] = ["open"];
    while (queue.length > 0) {
      const current = queue.shift()!;
      for (const target of TICKET_TRANSITIONS[current]) {
        if (!seen.has(target)) {
          seen.add(target);
          queue.push(target);
        }
      }
    }
    for (const status of TICKET_STATUSES) {
      expect(seen.has(status), `${status} is unreachable from open`).toBe(true);
    }
  });

  it("advance steps are legal transitions", () => {
    for (const status of TICKET_STATUSES) {
      const next = TICKET_NEXT_STEP[status];
      if (next) {
        expect(
          isTicketTransitionAllowed(status, next),
          `${status} advance → ${next} is not a legal transition`,
        ).toBe(true);
        expect(ticketAdvanceLabel(status), `${status} has no advance label`).toBeTruthy();
      }
    }
  });
});

describe("active/stale clocks", () => {
  it("active means not resolved and not closed", () => {
    expect(isTicketActive("open")).toBe(true);
    expect(isTicketActive("in_progress")).toBe(true);
    expect(isTicketActive("waiting")).toBe(true);
    expect(isTicketActive("resolved")).toBe(false);
    expect(isTicketActive("closed")).toBe(false);
  });

  it("stale fires only for active tickets past 48h", () => {
    const iso = (hoursAgo: number) =>
      new Date(Date.now() - hoursAgo * 3_600_000).toISOString();
    for (const status of ["open", "in_progress", "waiting"] as const) {
      expect(isTicketStale(status, iso(49)), `${status} @49h`).toBe(true);
      expect(isTicketStale(status, iso(47)), `${status} @47h`).toBe(false);
    }
    for (const status of ["resolved", "closed"] as const) {
      expect(isTicketStale(status, iso(1000)), `${status} must not be stale`).toBe(false);
    }
    expect(isTicketStale("open", "not-a-date")).toBe(false);
    expect(hoursSinceUpdate("not-a-date")).toBe(0);
  });

  it("relative time handles the buckets", () => {
    const pd = (v: string | number) => String(v);
    const iso = (hoursAgo: number) =>
      new Date(Date.now() - hoursAgo * 3_600_000).toISOString();
    expect(formatTicketRelativeTime(iso(0.01), pd)).toBe("چند لحظه پیش");
    expect(formatTicketRelativeTime(iso(3), pd)).toContain("ساعت");
    expect(formatTicketRelativeTime(iso(25), pd)).toBe("دیروز");
    expect(formatTicketRelativeTime("nope", pd)).toBe("نامشخص");
  });

  it("terminal helper mirrors the table", () => {
    for (const status of TICKET_STATUSES) {
      expect(isTicketTerminal(status)).toBe(TICKET_TRANSITIONS[status].length === 0);
    }
  });
});
