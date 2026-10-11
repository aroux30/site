import { describe, expect, it } from "vitest";
import { readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

import {
  adminLinks,
  adminNavGroups,
  dashboardLink,
  findActiveGroupId,
  isNavItemActive,
} from "@/lib/admin-nav";

/**
 * The admin route ↔ navigation guard.
 *
 * A page that is never linked is never visited, so no rendering test can
 * catch it — that is how /admin/exceptions and /admin/integrations once
 * shipped invisible (reachable only by typing the URL). This test reads the
 * routes from the filesystem and fails in BOTH directions: a route with no
 * nav entry, or a nav entry pointing at a route that does not exist.
 *
 * It also pins the grouped-nav behavior that replaced the flat 44-item list:
 * the data-exchange parent/child pair must highlight exactly one row, and
 * every page must resolve to the group that contains it.
 */

// Vitest runs with cwd = frontend/ (where vitest.config.ts lives), so the
// filesystem walk is anchored there rather than to import.meta.url (which is
// not a file: URL under the jsdom test environment).
const APP_ADMIN_DIR = join(process.cwd(), "app", "admin");

/** Routes deliberately absent from the sidebar, each with its reason. */
const UNLINKED_BY_DESIGN = new Map([
  ["/admin", "redirects to /admin/dashboard"],
  ["/admin/editor-probe", "dev-only editor harness, noindex, opened by scripts"],
  [
    "/admin/kanban",
    "redirects to /admin/orders?view=board (merged into the orders page 2026-10-10)",
  ],
]);

function discoverAdminRoutes(): string[] {
  const routes: string[] = [];
  const walk = (dir: string) => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        // Dynamic segments ([id]) are detail pages reached from their list
        // page; a made-up id would 404 by design and prove nothing.
        if (/^\[.+\]$/.test(entry)) continue;
        walk(full);
      } else if (entry === "page.tsx") {
        const rel = relative(APP_ADMIN_DIR, dir).split(sep).join("/");
        routes.push(rel === "" || rel === "." ? "/admin" : `/admin/${rel}`);
      }
    }
  };
  walk(APP_ADMIN_DIR);
  return routes.sort();
}

function navHrefs(): string[] {
  return adminLinks.map((item) => item.href);
}

describe("admin nav ↔ route reachability", () => {
  const routes = discoverAdminRoutes();
  const linked = new Set(navHrefs());

  it("discovers a non-trivial route set (guards against a broken walk)", () => {
    // If the walk broke (wrong dir, empty result), every other assertion here
    // would pass vacuously. Pin a floor and a known member.
    expect(routes.length).toBeGreaterThanOrEqual(40);
    expect(routes).toContain("/admin/dashboard");
  });

  it("links every admin route (a route with no nav entry is unreachable)", () => {
    const missing = routes.filter(
      (route) => !linked.has(route) && !UNLINKED_BY_DESIGN.has(route),
    );
    expect(missing, `routes with no sidebar entry: ${missing.join(", ")}`).toEqual(
      [],
    );
  });

  it("every nav entry points at a real route (a dead link is worse than none)", () => {
    const routeSet = new Set(routes);
    const dead = navHrefs().filter((href) => !routeSet.has(href));
    expect(dead, `nav entries with no page: ${dead.join(", ")}`).toEqual([]);
  });

  it("keeps the unlinked-by-design list honest", () => {
    for (const [route, reason] of UNLINKED_BY_DESIGN) {
      expect(routes, `${route} (${reason}) no longer exists — remove it from the list`).toContain(route);
      expect(linked.has(route), `${route} is both linked and listed unlinked`).toBe(false);
    }
  });
});

describe("admin nav structure", () => {
  it("has no duplicate hrefs", () => {
    const hrefs = navHrefs();
    const dupes = hrefs.filter((href, i) => hrefs.indexOf(href) !== i);
    expect(dupes, `duplicate entries: ${dupes.join(", ")}`).toEqual([]);
  });

  it("has no duplicate icons within a group (a repeated glyph is the flat-list smell)", () => {
    for (const group of adminNavGroups) {
      const names = group.items.map((item) => item.icon.displayName ?? item.icon.name);
      const dupes = names.filter((name, i) => names.indexOf(name) !== i);
      expect(
        dupes,
        `group "${group.label}" repeats icon(s): ${dupes.join(", ")}`,
      ).toEqual([]);
    }
  });

  it("keeps every group non-empty and uniquely identified", () => {
    const ids = adminNavGroups.map((group) => group.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const group of adminNavGroups) {
      expect(group.items.length, `group "${group.label}" is empty`).toBeGreaterThan(0);
    }
  });
});

describe("active-state logic", () => {
  const dataExchange = adminLinks.find((item) => item.href === "/admin/data-exchange")!;
  const exportChild = dataExchange.children!.find(
    (child) => child.href === "/admin/data-exchange/export",
  )!;

  it("highlights exactly one row for the parent/child pair", () => {
    // On the export page only the child highlights; the parent stays plain.
    // The old flat list lit BOTH rows because the parent's prefix match
    // caught the child's URL.
    expect(isNavItemActive("/admin/data-exchange/export", exportChild)).toBe(true);
    expect(isNavItemActive("/admin/data-exchange/export", dataExchange)).toBe(false);

    // On the parent page only the parent highlights.
    expect(isNavItemActive("/admin/data-exchange", dataExchange)).toBe(true);
    expect(isNavItemActive("/admin/data-exchange", exportChild)).toBe(false);
  });

  it("keeps a detail route under its list page", () => {
    const orders = adminLinks.find((item) => item.href === "/admin/orders")!;
    expect(isNavItemActive("/admin/orders/123", orders)).toBe(true);
  });

  it("does not highlight on a sibling prefix (orders vs order-ish paths)", () => {
    const orders = adminLinks.find((item) => item.href === "/admin/orders")!;
    // startsWith(`${href}/`) — a bare prefix like /admin/orders-x must not match.
    expect(isNavItemActive("/admin/orders-x", orders)).toBe(false);
  });

  it("maps every linked route to its owning group", () => {
    for (const item of adminLinks) {
      if (item.href === dashboardLink.href) {
        expect(findActiveGroupId(item.href)).toBeNull();
        continue;
      }
      expect(
        findActiveGroupId(item.href),
        `no group owns ${item.href}`,
      ).not.toBeNull();
    }
  });

  it("routes nested children to the parent's group", () => {
    expect(findActiveGroupId("/admin/data-exchange/export")).toBe("system");
    expect(findActiveGroupId("/admin/audit")).toBe("system");
    expect(findActiveGroupId("/admin/products")).toBe("store");
  });
});
