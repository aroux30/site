import type { Metadata } from "next";
import { siteOrigin } from "@/lib/site-url";
import ArchivePage from "../../[year]/page";

/** Month archive, e.g. /blog/archive/2026/09.
 *
 * The year page already handles an optional month segment, so this only
 * forwards the params rather than duplicating the render.
 *
 * `generateMetadata` is NOT forwarded with it: Next reads metadata from the
 * page file of the route that is serving, and a component re-export does
 * not register one. Without this export the month page inherited the blog
 * layout's metadata — title "مجله و بلاگ" and canonical `/blog` — so every
 * month URL advertised in the sitemap told Google "I am the blog index"
 * (live-verified 2026-10-10, reported by the monitoring session). The body
 * still renders through the shared component.
 */

const PERSIAN_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

export async function generateMetadata({
  params,
}: {
  params: Promise<{ year: string; month: string }>;
}): Promise<Metadata> {
  const { year: rawYear, month: rawMonth } = await params;
  const year = Number.parseInt(rawYear, 10);
  const month = Number.parseInt(rawMonth, 10);
  if (!Number.isFinite(year) || year < 1970 || year > 2200) {
    return { title: "آرشیو نامعتبر" };
  }
  if (!Number.isFinite(month) || month < 1 || month > 12) {
    return { title: "آرشیو نامعتبر" };
  }
  const label = `${PERSIAN_MONTHS[month - 1]} ${year}`;
  // Self-canonical, month-scoped: this is the URL the sitemap advertises.
  const base = siteOrigin().replace(/\/$/, "");
  return {
    title: `آرشیو ${label}`,
    description: `نوشته‌های منتشرشده در ${label}`,
    alternates: { canonical: `${base}/blog/archive/${year}/${month}` },
  };
}

export default function MonthArchivePage({
  params,
}: {
  params: Promise<{ year: string; month: string }>;
}) {
  return <ArchivePage params={params} />;
}
