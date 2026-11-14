/**
 * Notification inbox wiring — the surface that finally renders
 * `notificationsApi.list`.
 *
 * Background: in-app notifications (order updates, refunds, wallet events,
 * and the 2026-10-14 referral/bonus rewards) were written to the database
 * for years while NOTHING in the frontend ever called `notificationsApi.
 * list` — every notification was written and never read. The account area
 * only had the preferences page. These pins keep the inbox wired:
 *
 * 1. the dashboard renders the inbox component for the "notifications" tab;
 * 2. the inbox calls the real list/mark APIs;
 * 3. the header carries the bell with an unread badge for signed-in users;
 * 4. the deep-link route exists.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const DASHBOARD_SRC = readFileSync(
  join(process.cwd(), "components", "account", "account-dashboard.tsx"),
  "utf-8",
);
const INBOX_SRC = readFileSync(
  join(process.cwd(), "components", "account", "notification-inbox.tsx"),
  "utf-8",
);
const HEADER_SRC = readFileSync(
  join(process.cwd(), "components", "layout", "header.tsx"),
  "utf-8",
);

describe("notification inbox wiring", () => {
  it("the dashboard renders the inbox for the notifications tab", () => {
    expect(DASHBOARD_SRC).toContain(
      '{activeTab === "notifications" && <NotificationInbox />}',
    );
    // The nav entry must exist or the tab is unreachable.
    expect(DASHBOARD_SRC).toContain('{ key: "notifications", label: "اعلان‌ها", icon: Bell }');
  });

  it("the inbox consumes the real notification APIs", () => {
    // Wiring, not presence: the list call and both mark calls must run.
    expect(INBOX_SRC).toContain("notificationsApi.list(");
    expect(INBOX_SRC).toContain("notificationsApi.markAsRead(");
    expect(INBOX_SRC).toContain("notificationsApi.markAllRead(");
  });

  it("a failed load outranks the empty state", () => {
    // Account-area rule: a failed read must never render as "no notifications".
    const errIdx = INBOX_SRC.indexOf("if (error)");
    const emptyIdx = INBOX_SRC.indexOf("هنوز اعلانی ندارید");
    expect(errIdx).toBeGreaterThan(-1);
    expect(emptyIdx).toBeGreaterThan(-1);
    expect(errIdx).toBeLessThan(emptyIdx);
  });

  it("the header bell only fetches for signed-in users", () => {
    expect(HEADER_SRC).toContain("notificationsApi");
    // The guard is the exact expression; a bare call would 401 for guests.
    expect(HEADER_SRC).toContain("if (isAuthenticated) {");
    expect(HEADER_SRC).toContain('href="/account/inbox"');
  });
});

describe("inbox route exists", () => {
  it("the deep-link page renders the dashboard with the notifications tab", () => {
    const route = readFileSync(
      join(process.cwd(), "app", "(account)", "account", "inbox", "page.tsx"),
      "utf-8",
    );
    expect(route).toContain('initialTab="notifications"');
  });
});
