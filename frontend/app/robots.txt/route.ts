/**
 * Virtual /robots.txt (WordPress parity).
 *
 * P1 "تنظیمات: robots.txt مجازی با دستور قالب". This was a Next.js metadata
 * route (app/robots.ts), which generated a fixed document: an operator could
 * not add a single line — a Crawl-delay, a rule for one crawler — without a
 * deploy, which is exactly what WordPress's "robots.txt" filter exists to avoid.
 *
 * It is a Route Handler rather than a metadata route so it can append the
 * operator's extra rules (site option `robots_extra_rules`) after the generated
 * ones. The generated half is unchanged from the metadata version — the same
 * allow/disallow set and the same AI-crawler block — so nothing a crawler saw
 * before this change was a surprise, and the store's privacy toggle
 * (blog_public) still drives it through the shared public discussion endpoint.
 */

import { fetchPublicDiscussionOptions } from "@/lib/public-options";
import { apiInternalUrl } from "@/lib/api/server-base";

/** The operator's extra robots.txt lines, verbatim. Absent on failure — the
 *  generated rules are still a valid robots.txt, so an outage must not turn
 *  /robots.txt into a 500 that crawlers read as "no rules at all". */
async function fetchExtraRules(): Promise<string> {
  try {
    const res = await fetch(`${apiInternalUrl()}/settings/public/robots-extra`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return "";
    const data = (await res.json()) as { extra?: string };
    return typeof data.extra === "string" ? data.extra : "";
  } catch {
    return "";
  }
}

export async function GET(): Promise<Response> {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

  // The blog can be switched off in Settings → Reading. That already emits a
  // `noindex` meta tag on the blog subtree, but a crawler that honours
  // robots.txt and ignores meta robots would still walk it — and this file
  // used to advertise the sitemap unconditionally, which points at the blog
  // entries. Read the same public flag the blog metadata reads, so the two
  // surfaces cannot disagree.
  const [{ searchVisible }, extra] = await Promise.all([
    fetchPublicDiscussionOptions(),
    fetchExtraRules(),
  ]);

  const lines: string[] = ["User-Agent: *"];
  if (searchVisible) {
    lines.push("Allow: /");
    lines.push(
      "Disallow: /admin/",
      "Disallow: /account/",
      "Disallow: /checkout/",
      "Disallow: /api/",
      // Result pages are an unbounded crawlable parameter space
      // (?q=&category=&min_price=&sort=) that all emit the same `products`
      // metadata — indexable thin duplicates, and they compete with the
      // category pages that are actually meant to rank.
      "Disallow: /search",
    );
  } else {
    lines.push("Disallow: /");
  }

  lines.push("");
  // Crawlers that feed generative models. Kept always disallowed regardless of
  // blog_public: the storefront does not want its catalogue in a training set.
  for (const ua of ["GPTBot", "CCBot", "ClaudeBot", "anthropic-ai", "Bytespider"]) {
    lines.push(`User-Agent: ${ua}`, "Disallow: /", "");
  }

  // No point advertising a sitemap when the whole site is disallowed.
  if (searchVisible) {
    lines.push(`Sitemap: ${baseUrl}/sitemap.xml`);
  }

  const trimmedExtra = extra.trim();
  if (trimmedExtra) {
    lines.push("", "# قواعد سفارشی اپراتور", trimmedExtra);
  }

  return new Response(lines.join("\n") + "\n", {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=0, must-revalidate",
    },
  });
}