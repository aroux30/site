import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { CalendarDays } from "lucide-react";

import { apiInternalUrl } from "@/lib/api/server-base";
import { dateArchiveHref } from "@/lib/permalinks";

/** Year archive, e.g. /blog/archive/2026.
 *
 * The permalink structure already produced %year% paths, and the backend
 * served /archive/{year} — but no page existed, so every date-based permalink
 * 404'd. This is that page; the [month] route reuses it.
 */

interface ArchivePost {
  id: string;
  slug: string;
  title: string;
  excerpt: string | null;
  cover_image_url: string | null;
  published_at: string | null;
}

interface ArchivePayload {
  year: number;
  month: number | null;
  total: number;
  page: number;
  page_size: number;
  posts: ArchivePost[];
}

const PERSIAN_MONTHS = [
  "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
  "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
];

async function fetchArchive(
  year: number,
  month: number | null,
): Promise<ArchivePayload | null> {
  try {
    const path = month ? `${year}/${month}` : `${year}`;
    const res = await fetch(`${apiInternalUrl()}/blog/archive/${path}`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    return (await res.json()) as ArchivePayload;
  } catch {
    return null;
  }
}

type Props = { params: Promise<{ year: string; month?: string }> };

function parseYear(raw: string): number | null {
  const n = Number.parseInt(raw, 10);
  return Number.isFinite(n) && n >= 1970 && n <= 2200 ? n : null;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { year: rawYear, month: rawMonth } = await params;
  const year = parseYear(rawYear);
  if (year === null) return { title: "آرشیو نامعتبر" };
  const month = rawMonth ? Number.parseInt(rawMonth, 10) : null;
  const label = month
    ? `${PERSIAN_MONTHS[month - 1]} ${year}`
    : `سال ${year}`;
  return { title: `آرشیو ${label}`, description: `نوشته‌های منتشرشده در ${label}` };
}

export default async function ArchivePage({ params }: Props) {
  const { year: rawYear, month: rawMonth } = await params;
  const year = parseYear(rawYear);
  if (year === null) notFound();
  const month = rawMonth ? Number.parseInt(rawMonth, 10) : null;
  if (month !== null && (month < 1 || month > 12)) notFound();

  const data = await fetchArchive(year, month);
  if (!data) notFound();

  const label = month ? `${PERSIAN_MONTHS[month - 1]} ${year}` : `سال ${year}`;

  return (
    <div className="container mx-auto px-4 py-10 max-w-4xl" dir="rtl">
      <nav className="mb-6 flex items-center gap-2 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground">خانه</Link>
        <span>/</span>
        <Link href="/blog" className="hover:text-foreground">وبلاگ</Link>
        <span>/</span>
        <span className="font-medium text-foreground">آرشیو {label}</span>
      </nav>

      <header className="mb-8 flex items-center gap-2">
        <CalendarDays className="h-5 w-5 text-primary" />
        <h1 className="text-2xl font-black text-foreground">آرشیو {label}</h1>
        <span className="text-sm text-muted-foreground">({data.total} نوشته)</span>
      </header>

      {/* Month links, so a year archive is navigable without a calendar. */}
      {!month && (
        <div className="mb-8 flex flex-wrap gap-1.5">
          {PERSIAN_MONTHS.map((name, i) => (
            <Link
              key={name}
              href={dateArchiveHref(year, i + 1)}
              className="rounded-lg border border-border px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
            >
              {name}
            </Link>
          ))}
        </div>
      )}

      {data.posts.length === 0 ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          در این بازه نوشته‌ای منتشر نشده است.
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-border">
          {data.posts.map((post) => (
            <li key={post.id}>
              <Link
                href={`/blog/${post.slug}`}
                className="block py-4 transition-colors hover:bg-muted/30"
              >
                <h2 className="text-base font-bold text-foreground">{post.title}</h2>
                {post.excerpt && (
                  <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                    {post.excerpt}
                  </p>
                )}
                {post.published_at && (
                  <time
                    dateTime={post.published_at}
                    className="mt-1.5 block text-xs text-muted-foreground"
                  >
                    {new Date(post.published_at).toLocaleDateString("fa-IR")}
                  </time>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
