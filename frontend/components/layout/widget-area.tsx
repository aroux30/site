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
    case "custom_html":
      // Admin-authored HTML. Rendered as text, not markup: a widget area is
      // not a script host, and dangerouslySetInnerHTML here would make every
      // admin account a stored-XSS vector.
      return text ? (
        <p className="whitespace-pre-line text-sm leading-relaxed text-muted-foreground">
          {text}
        </p>
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
    const url = kind === "category" ? "/blog/categories" : "/blog/tags";
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
    fetch("/blog/tags", { credentials: "include" })
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
