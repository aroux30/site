"use client";

/**
 * Renders a storefront widget area configured in /admin/widgets.
 *
 * Follows the same contract as the CMS-driven footer columns: nothing renders
 * until the fetch resolves, and a failure or an empty area renders nothing at
 * all — never a placeholder, never an error box. An unconfigured install must
 * look exactly as it did before widgets existed.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, Mail, Share2 } from "lucide-react";

import { widgetsApi, type Widget } from "@/lib/api/wp-parity";
import { fetchBlogPosts } from "@/lib/api/blog";
import { newsletterApi } from "@/lib/api/newsletter";

type Cache = Awaited<ReturnType<typeof widgetsApi.publicAreas>>;

// One shared in-flight promise: the header and footer both mount on every
// page, and without this they would each fire their own request for the
// same payload.
let inFlight: Promise<Cache> | null = null;

function loadWidgets(): Promise<Cache> {
  inFlight ??= widgetsApi.publicAreas().catch((err) => {
    inFlight = null; // let a later mount retry
    throw err;
  });
  return inFlight;
}

function WidgetBody({ widget }: { widget: Widget }) {
  const config = widget.config ?? {};
  const text = typeof config.content === "string" ? config.content : "";
  const url = typeof config.url === "string" ? config.url : "";
  const items = Array.isArray(config.items) ? config.items : [];

  switch (widget.type) {
    case "text":
      return text ? (
        <p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
          {text}
        </p>
      ) : null;

    case "custom_html":
      // Admin-authored HTML, rendered as markup rather than as visible source.
      //
      // Safe because the server sanitizes this on the way into the database:
      // `WidgetService.update_area` runs the value through the project's bleach
      // allowlist before it is stored, so the string here has already had its
      // scripts, event handlers and javascript: URLs removed. Rendering it as
      // text instead — which is what this used to do — meant the widget type did
      // nothing an admin asked for, and the right response to that is a
      // sanitized renderer rather than a widget that displays its own source.
      //
      // That ordering is load-bearing: the guarantee lives at write time, so it
      // holds for every reader of this row and not only for this component. A
      // comment here that claims the value is sanitized is not what makes it so.
      return text ? (
        // eslint-disable-next-line @eslint-react/no-danger -- sanitized
        // server-side on write by WidgetService._sanitise_widgets; see above
        <div
          className="custom-html-widget text-sm leading-relaxed"
          dangerouslySetInnerHTML={{ __html: text }}
        />
      ) : null;

    case "image":
      return url ? (
        // eslint-disable-next-line @next/next/no-img-element -- admin-supplied external URL, dimensions unknown
        <img src={url} alt={widget.title ?? ""} className="max-w-full rounded-lg" loading="lazy" />
      ) : null;

    case "search":
      return (
        <div className="relative">
          <Search className="absolute end-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="search"
            placeholder="جستجو..."
            aria-label="جستجو در فروشگاه"
            className="h-9 w-full rounded-lg border border-input bg-background pe-9 ps-3 text-sm"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                const q = (e.target as HTMLInputElement).value.trim();
                if (q) window.location.href = `/search?q=${encodeURIComponent(q)}`;
              }
            }}
          />
        </div>
      );

    case "newsletter":
      return <NewsletterWidget source={typeof config.source === "string" ? config.source : "widget"} />;

    case "social_links":
      return (
        <div className="flex flex-wrap gap-2">
          {items.map((item, i) => {
            const link =
              typeof item === "object" && item !== null
                ? (item as { url?: string; label?: string })
                : null;
            if (!link?.url) return null;
            return (
              <a
                key={`${link.url}-${i}`}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex h-9 w-9 items-center justify-center rounded-full bg-muted text-muted-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
                title={link.label ?? link.url}
              >
                <Share2 className="h-4 w-4" />
              </a>
            );
          })}
        </div>
      );

    case "menu":
      return items.length > 0 ? (
        <nav className="flex flex-col gap-2">
          {items.map((item, i) => {
            const link =
              typeof item === "object" && item !== null
                ? (item as { url?: string; label?: string })
                : null;
            if (!link?.url) return null;
            return (
              <Link
                key={`${link.url}-${i}`}
                href={link.url}
                prefetch={false}
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label ?? link.url}
              </Link>
            );
          })}
        </nav>
      ) : null;

    case "recent_posts":
      return <RecentPostsWidget limit={numberOf(config.count, 5)} />;

    case "categories":
      return <TermListWidget kind="category" limit={numberOf(config.count, 10)} />;

    case "tags":
      return <TagCloudWidget limit={numberOf(config.count, 20)} />;

    case "archives":
      return (
        <ArchivesWidget
          limit={numberOf(config.count, 12)}
          type={config.type === "yearly" ? "yearly" : "monthly"}
        />
      );

    case "recent_comments":
      return <RecentCommentsWidget limit={numberOf(config.count, 5)} />;

    case "pages":
      return (
        <PagesWidget
          limit={numberOf(config.count, 10)}
          sortby={config.sortby === "menu_order" ? "menu_order" : "title"}
        />
      );

    case "meta":
      return <MetaWidget />;

    case "rss":
      return <RssWidget url={url} label={widget.title ?? ""} />;

    case "links": {
      // Same shape as social_links/menu: an operator-maintained {url,label}
      // list. Rendered as a plain link list rather than the icon row.
      const links = items.filter(
        (item): item is { url?: string; label?: string } =>
          typeof item === "object" && item !== null,
      );
      const withUrl = links.filter((l) => l.url);
      return withUrl.length > 0 ? (
        <ul className="flex flex-col gap-1.5 text-sm">
          {withUrl.map((l, i) => (
            <li key={`${l.url}-${i}`}>
              <a
                href={l.url}
                className="text-muted-foreground transition-colors hover:text-foreground"
              >
                {l.label || l.url}
              </a>
            </li>
          ))}
        </ul>
      ) : null;
    }

    case "calendar":
      return <CalendarWidget />;

    case "spacer":
      return <div className="h-6" aria-hidden />;

    // Anything unknown renders nothing rather than an empty heading.
    default:
      return null;
  }
}

/** Coerce an admin-configured count, ignoring nonsense rather than rendering
 *  an empty list that looks broken. */
function numberOf(value: unknown, fallback: number): number {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) && n > 0 ? Math.min(Math.trunc(n), 50) : fallback;
}

/** Newsletter signup, wired to the real double opt-in endpoint.
 *
 * This was a bare input and a button with no handler, so the one widget that
 * collected an email address did nothing at all.
 */
function NewsletterWidget({ source }: { source: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [message, setMessage] = useState("");

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed || state === "sending") return;
    setState("sending");
    setMessage("");
    try {
      const { message: serverMessage } = await newsletterApi.subscribe(trimmed, source);
      setState("sent");
      setMessage(serverMessage);
      setEmail("");
    } catch (err) {
      setState("error");
      setMessage(
        err instanceof Error ? err.message : "ثبت‌نام انجام نشد. لطفاً دوباره تلاش کنید.",
      );
    }
  };

  if (state === "sent") {
    return <p className="rounded-lg bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-400">{message}</p>;
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <div className="flex gap-2">
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="ایمیل شما"
          aria-label="ایمیل برای خبرنامه"
          className="h-9 flex-1 rounded-lg border border-input bg-background px-3 text-sm"
        />
        <button
          type="submit"
          disabled={state === "sending"}
          className="h-9 shrink-0 rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground disabled:opacity-60"
        >
          <Mail className="h-4 w-4" />
        </button>
      </div>
      {state === "error" && message && (
        <p className="text-xs text-destructive">{message}</p>
      )}
    </form>
  );
}

/** Recent published posts, fetched from the public blog API. */
function RecentPostsWidget({ limit }: { limit: number }) {
  const [posts, setPosts] = useState<{ slug: string; title: string }[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetchBlogPosts({ page_size: limit })
      .then((data) => {
        if (!cancelled) {
          setPosts((data.items ?? []).map((p) => ({ slug: p.slug, title: p.title })));
        }
      })
      .catch(() => {
        // A widget is decoration: a failed feed must not break the page.
      });
    return () => { cancelled = true; };
  }, [limit]);

  if (posts.length === 0) return null;
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {posts.map((post) => (
        <li key={post.slug}>
          <Link
            href={`/blog/${post.slug}`}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            {post.title}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Shared list renderer for the category and tag widgets. */
function TermListWidget({ kind, limit }: { kind: "category" | "tag"; limit: number }) {
  const [terms, setTerms] = useState<{ slug: string; name: string }[]>([]);

  useEffect(() => {
    let cancelled = false;
    const url = kind === "category" ? "/api/v1/blog/categories" : "/api/v1/blog/tags";
    fetch(url, { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: unknown) => {
        if (cancelled || !data) return;
        const rows = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items ?? [];
        setTerms(
          (rows as { slug: string; name: string }[])
            .filter((t) => t?.slug && t?.name)
            .slice(0, limit),
        );
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [kind, limit]);

  if (terms.length === 0) return null;
  const base = kind === "category" ? "/blog/category" : "/blog/tag";
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {terms.map((term) => (
        <li key={term.slug}>
          <Link
            href={`${base}/${term.slug}`}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            {term.name}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Tag cloud, sized by each term's post count. */
function TagCloudWidget({ limit }: { limit: number }) {
  const [tags, setTags] = useState<{ slug: string; name: string; count?: number }[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/blog/tags", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: unknown) => {
        if (cancelled || !data) return;
        const rows = Array.isArray(data) ? data : (data as { items?: unknown[] })?.items ?? [];
        setTags((rows as { slug: string; name: string; count?: number }[]).slice(0, limit));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);

  if (tags.length === 0) return null;
  const max = Math.max(...tags.map((t) => t.count ?? 1), 1);
  return (
    <div className="flex flex-wrap gap-1.5">
      {tags.map((tag) => {
        const ratio = (tag.count ?? 1) / max;
        return (
          <Link
            key={tag.slug}
            href={`/blog/tag/${tag.slug}`}
            className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground transition-colors hover:bg-primary hover:text-primary-foreground"
            style={{ fontSize: `${0.75 + ratio * 0.35}rem` }}
          >
            {tag.name}
          </Link>
        );
      })}
    </div>
  );
}

/** Monthly (or yearly) archive links, newest first. */
function ArchivesWidget({ limit, type }: { limit: number; type: "monthly" | "yearly" }) {
  const [months, setMonths] = useState<Array<{ year: number; month: number | null; count: number }>>([]);

  useEffect(() => {
    let cancelled = false;
    // The sitemap-entries payload already carries the published date archives
    // with counts; reusing it keeps one source for "which months exist".
    fetch("/api/v1/content/sitemap-entries", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: unknown) => {
        if (cancelled || !data) return;
        const rows = (data as { blog_date_archives?: Array<{ loc?: string; count?: number }> })
          .blog_date_archives;
        const parsed: Array<{ year: number; month: number | null; count: number }> = [];
        for (const row of rows ?? []) {
          // loc looks like "/blog/archive/2026/9" or "/blog/archive/2026".
          const m = /\/(\d{4})(?:\/(\d{1,2}))?\/?$/.exec(row.loc ?? "");
          if (!m) continue;
          parsed.push({
            year: Number(m[1]),
            month: m[2] ? Number(m[2]) : null,
            count: row.count ?? 0,
          });
        }
        parsed.sort((a, b) => (b.year - a.year) || ((b.month ?? 0) - (a.month ?? 0)));
        setMonths(parsed.slice(0, limit));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);

  if (months.length === 0) return null;
  const monthNames = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
  ];
  // Group by year when showing yearly links. The physical storefront route is
  // /blog/archive/{year}[/{month}] — the same path `dateArchiveHref` builds —
  // so the widget links there, not to the backend's bare /archive shape.
  const shown = type === "yearly"
    ? Array.from(new Set(months.map((m) => m.year))).slice(0, limit).map((y) => ({
        key: `y-${y}`,
        href: `/blog/archive/${y}`,
        label: String(y),
        count: months.filter((m) => m.year === y).reduce((s, m) => s + m.count, 0),
      }))
    : months.map((m) => ({
        key: `${m.year}-${m.month ?? "all"}`,
        href: m.month
          ? `/blog/archive/${m.year}/${String(m.month).padStart(2, "0")}`
          : `/blog/archive/${m.year}`,
        // Gregorian month numbers come back from the API; label with the
        // Persian month name where it is a real month, else the year.
        label: m.month ? `${monthNames[m.month - 1] ?? m.month} ${m.year}` : String(m.year),
        count: m.count,
      }));
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {shown.map((row) => (
        <li key={row.key}>
          <Link
            href={row.href}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            {row.label}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Most recent approved comments across the blog (RSS-backed, no JSON route). */
function RecentCommentsWidget({ limit }: { limit: number }) {
  const [comments, setComments] = useState<Array<{ author: string; excerpt: string; link?: string }>>([]);

  useEffect(() => {
    let cancelled = false;
    // The comments RSS feed is the public, already-ordered read for this. A
    // JSON list route would be a second surface to keep in sync; parsing the
    // feed keeps one source of truth for "recent approved comments".
    fetch("/feed/comments/rss", { credentials: "include" })
      .then((res) => (res.ok ? res.text() : ""))
      .then((xml) => {
        if (cancelled || !xml) return;
        const doc = new DOMParser().parseFromString(xml, "text/xml");
        const items = Array.from(doc.querySelectorAll("item")).slice(0, limit);
        setComments(
          items.map((item) => ({
            author: item.querySelector("dc\\:creator, creator")?.textContent?.trim() ?? "",
            excerpt: (item.querySelector("description")?.textContent ?? "")
              .replace(/<[^>]*>/g, " ")
              .replace(/\s+/g, " ")
              .trim()
              .slice(0, 80),
            link: item.querySelector("link")?.textContent?.trim(),
          })),
        );
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit]);

  if (comments.length === 0) return null;
  return (
    <ul className="flex flex-col gap-2 text-sm">
      {comments.map((c, i) => (
        <li key={`${c.author}-${i}`} className="text-muted-foreground">
          <span className="font-medium text-foreground">{c.author}</span>
          {c.link ? (
            <>
              {" روی "}
              <Link href={c.link} prefetch={false} className="hover:text-foreground">
                این نوشته
              </Link>
            </>
          ) : null}
          {c.excerpt ? <div className="mt-0.5 text-xs">«{c.excerpt}»</div> : null}
        </li>
      ))}
    </ul>
  );
}

/** Published CMS pages, alphabetical or by menu order. */
function PagesWidget({ limit, sortby }: { limit: number; sortby: "title" | "menu_order" }) {
  const [pages, setPages] = useState<Array<{ slug: string; title: string; menu_order?: number }>>([]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/content/pages", { credentials: "include" })
      .then((res) => (res.ok ? res.json() : null))
      .then((data: unknown) => {
        if (cancelled || !data) return;
        const rows = ((data as { items?: unknown[] }).items ?? []) as Array<{
          slug: string;
          title: string;
          menu_order?: number;
        }>;
        const sorted = [...rows].sort((a, b) =>
          sortby === "menu_order"
            ? (a.menu_order ?? 0) - (b.menu_order ?? 0)
            : a.title.localeCompare(b.title, "fa"),
        );
        setPages(sorted.slice(0, limit));
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [limit, sortby]);

  if (pages.length === 0) return null;
  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {pages.map((p) => (
        <li key={p.slug}>
          <Link
            href={`/${p.slug}`}
            className="text-muted-foreground transition-colors hover:text-foreground"
          >
            {p.title}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** WordPress's "Meta" widget: login/logout, entries feed, admin link. */
function MetaWidget() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    let cancelled = false;
    // A cheap presence check: the account endpoint answers 401 for guests.
    fetch("/api/v1/auth/me", { credentials: "include" })
      .then((res) => {
        if (!cancelled) setLoggedIn(res.ok);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  return (
    <ul className="flex flex-col gap-1.5 text-sm">
      {loggedIn ? (
        <>
          <li>
            <Link href="/account" className="text-muted-foreground hover:text-foreground">
              حساب من
            </Link>
          </li>
          <li>
            <Link href="/admin" className="text-muted-foreground hover:text-foreground">
              پیشخوان مدیریت
            </Link>
          </li>
        </>
      ) : (
        <>
          <li>
            <Link href="/login" className="text-muted-foreground hover:text-foreground">
              ورود
            </Link>
          </li>
          <li>
            <Link href="/register" className="text-muted-foreground hover:text-foreground">
              ثبت‌نام
            </Link>
          </li>
        </>
      )}
      <li>
        <Link href="/blog/feed/rss" className="text-muted-foreground hover:text-foreground">
          خوراک نوشته‌ها
        </Link>
      </li>
      <li>
        <Link href="/feed/comments/rss" className="text-muted-foreground hover:text-foreground">
          خوراک دیدگاه‌ها
        </Link>
      </li>
    </ul>
  );
}

/** A link to an RSS feed (WordPress's RSS widget in its simple form). */
function RssWidget({ url, label }: { url: string; label: string }) {
  if (!url) return null;
  return (
    <a
      href={url}
      className="text-sm text-muted-foreground transition-colors hover:text-foreground"
      rel="noopener noreferrer"
    >
      {label || url}
    </a>
  );
}

/** A month grid of the current month, marking days with published posts. */
function CalendarWidget() {
  const [days, setDays] = useState<Set<number> | null>(null);

  useEffect(() => {
    let cancelled = false;
    const now = new Date();
    // The date-archive endpoint answers with the post list for a month; its
    // `total` tells us whether any day in the month has a post. Day-level
    // marks are not in the payload, so the calendar marks nothing rather than
    // fabricating days — an empty grid is honest, a wrong dot is not.
    fetch(`/api/v1/blog/archive/${now.getFullYear()}/${now.getMonth() + 1}`, {
      credentials: "include",
    })
      .then((res) => (res.ok ? res.json() : null))
      .then(() => {
        if (!cancelled) setDays(new Set());
      })
      .catch(() => {
        if (!cancelled) setDays(null);
      });
    return () => { cancelled = true; };
  }, []);

  if (days === null) return null;
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  const firstDay = new Date(year, month, 1).getDay(); // 0 = Sunday
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  // Saturday is the first column in the Persian calendar week.
  const leading = (firstDay + 1) % 7;
  const cells: Array<number | null> = [
    ...Array.from({ length: leading }, () => null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  return (
    <div className="text-xs">
      <div className="mb-1.5 grid grid-cols-7 gap-1 text-center text-[10px] text-muted-foreground">
        {["ش", "ی", "د", "س", "چ", "پ", "ج"].map((d) => (
          <span key={d}>{d}</span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => (
          <span
            key={i}
            className={`rounded py-0.5 text-center ${
              day === now.getDate() ? "bg-primary text-primary-foreground" : "text-muted-foreground"
            }`}
          >
            {day ?? ""}
          </span>
        ))}
      </div>
    </div>
  );
}

export function WidgetArea({
  area,
  className,
}: {
  area: string;
  className?: string;
}) {
  const [widgets, setWidgets] = useState<Widget[]>([]);

  useEffect(() => {
    let cancelled = false;
    loadWidgets()
      .then((cache) => {
        if (!cancelled) setWidgets(cache.areas[area]?.widgets ?? []);
      })
      .catch(() => {
        // Silent by design: a widget failure must not break the page.
      });
    return () => {
      cancelled = true;
    };
  }, [area]);

  const renderable = widgets.filter((w) => w.type !== "spacer");
  if (renderable.length === 0) return null;

  return (
    <div className={className}>
      {renderable.map((widget) => (
        <section key={widget.id} className="mb-6 last:mb-0">
          {widget.title && (
            <h3 className="mb-2.5 text-sm font-bold text-foreground">{widget.title}</h3>
          )}
          <WidgetBody widget={widget} />
        </section>
      ))}
    </div>
  );
}

/** True when at least one of the given areas has content — lets a layout
 *  avoid rendering an empty column wrapper. */
export function useHasWidgets(areasToCheck: string[]): boolean {
  const [has, setHas] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadWidgets()
      .then((cache) => {
        if (cancelled) return;
        setHas(
          areasToCheck.some((a) => (cache.areas[a]?.widgets ?? []).length > 0),
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [areasToCheck]);

  return has;
}
