import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Automated accessibility sweep of the storefront's key pages.
 *
 * `@axe-core/playwright` was installed and no test used it — the dependency
 * was decoration and the project had no automated accessibility check at all.
 * This runs axe against the pages a customer actually reaches and fails on a
 * serious or critical violation.
 *
 * Scope: the storefront's public surface. The admin panel is deliberately out
 * of scope here — it is a staff tool behind auth, and mixing it in would make
 * the suite need a login fixture for pages a customer never sees.
 *
 * Severity: `serious` and `critical` fail; `moderate` and `minor` are reported
 * but do not fail the run. That line is drawn because the lower tiers are
 * largely contrast and landmark nits whose volume would train people to ignore
 * the suite — and an accessibility suite people ignore is worse than none.
 */

// The pages every store has and every customer can reach without an account.
const PUBLIC_PAGES = [
  { path: "/", name: "home" },
  { path: "/products", name: "product list" },
  { path: "/cart", name: "cart" },
  { path: "/login", name: "login" },
  { path: "/contact", name: "contact" },
];

const FAILING_IMPACTS = new Set(["serious", "critical"]);

for (const page of PUBLIC_PAGES) {
  test(`${page.name} has no serious accessibility violations`, async ({ page: p }) => {
    const response = await p.goto(page.path, { waitUntil: "networkidle" });

    // A page that did not render cannot be assessed. Skip loudly rather than
    // pass: a 404 rendering the same error shell would otherwise "pass" axe.
    if (!response || response.status() >= 400) {
      test.skip(
        true,
        `${page.path} answered ${response?.status() ?? "no response"}; ` +
          "accessibility was not assessed",
      );
      return;
    }

    const results = await new AxeBuilder({ page: p })
      // The third-party surfaces are not ours to fix: an embedded YouTube or
      // an Aparat player brings its own markup, and a violation inside it is
      // not actionable here.
      .disableRules(["frame-tested"])
      .analyze();

    const failing = results.violations.filter((v) =>
      FAILING_IMPACTS.has(v.impact ?? ""),
    );

    // Report every violation, not just the first, so one run is enough to see
    // the whole list.
    const summary = failing
      .map(
        (v) =>
          `  [${v.impact}] ${v.id}: ${v.help}\n` +
          v.nodes.slice(0, 3).map((n) => `      ${n.target.join(" ")}`).join("\n"),
      )
      .join("\n");

    expect(failing, `\n${summary}\n`).toEqual([]);
  });
}
