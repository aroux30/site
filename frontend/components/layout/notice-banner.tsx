"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { X, Megaphone } from "lucide-react";

import { notificationsApi, type Notice, type NoticeTargetPage } from "@/lib/api/notifications";
import sanitizeHtml from "@/lib/sanitize-html";

/** Which targeted notices apply to the current route.
 *
 * A notice created in /admin/notices with `target_page = "checkout"` was
 * unreachable: the endpoint existed, the client existed, and nothing ever
 * called it, so a campaign targeted at checkout never reached the customer.
 *
 * The enum names are NOT paths. Reading them as paths matched `home` against
 * `/home` (the storefront root is `/`) and `dashboard` against `/dashboard`
 * (the customer panel is `/account`), so two of the four targets silently
 * never matched. Map each name to the route it actually means.
 */
const TARGET_PATHS: Record<Exclude<NoticeTargetPage, "all">, string> = {
  home: "/",
  checkout: "/checkout",
  dashboard: "/account",
};

function targetMatches(target: NoticeTargetPage, path: string): boolean {
  if (target === "all") return true;
  const base = TARGET_PATHS[target];
  if (!base) return false;
  if (base === "/") return path === "/";
  return path === base || path.startsWith(`${base}/`);
}

/** A dismissible banner for the active notices on the current page. */
export default function NoticeBanner() {
  const pathname = usePathname();
  const [notices, setNotices] = useState<Notice[]>([]);
  const [dismissed, setDismissed] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    // "all" fetches the site-wide set; the client filters by target_page so
    // one request serves every route rather than one per pathname.
    notificationsApi
      .getActiveNotices("all")
      .then((rows) => {
        if (!cancelled) setNotices(rows.filter((n) => n.is_active !== false));
      })
      .catch(() => {
        // A missing banner must never break a page.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = notices.filter(
    (n) => !dismissed[n.id] && targetMatches(n.target_page, pathname),
  );
  if (visible.length === 0) return null;

  return (
    <div className="w-full" dir="rtl">
      {visible.map((notice) => (
        <div
          key={notice.id}
          className="flex items-start gap-2 border-b border-border bg-primary/10 px-4 py-2.5 text-sm text-foreground"
        >
          <Megaphone className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0 flex-1">
            <p className="font-medium">{notice.title}</p>
            {/* Admin-authored HTML, sanitized: a notice is not a script host. */}
            {notice.content_html && (
              <div
                className="mt-0.5 text-xs leading-relaxed text-muted-foreground [&_a]:underline"
                dangerouslySetInnerHTML={{ __html: sanitizeHtml(notice.content_html) }}
              />
            )}
          </div>
          <button
            type="button"
            aria-label="بستن اطلاعیه"
            onClick={() => {
              setDismissed((d) => ({ ...d, [notice.id]: true }));
              // Recorded server-side so the banner stays closed across pages.
              notificationsApi.markNoticeSeen(notice.id).catch(() => {});
            }}
            className="shrink-0 rounded p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
}
