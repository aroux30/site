"use client";

/**
 * Admin notices — the persistent, dismissible strip under the admin header.
 *
 * The toast that exists already is the wrong shape for this: it vanishes on a
 * timer, so a scheduled notice about a migration, a low-stock problem or a
 * failed export was gone before the operator had read it, and re-reading it
 * meant opening the notices page by remembering it existed.
 *
 * A notice here survives navigation. Dismissal is recorded server-side
 * (`POST /notifications/notices/{id}/seen`), so a dismissed notice stays
 * dismissed on the next device and after the next reload — a notice that comes
 * back on every page view trains people to ignore the strip.
 *
 * Dismissal is optimistic on purpose: the strip closes immediately and the
 * request follows. Waiting for a round trip to hide a banner the user has
 * already dismissed makes the control feel broken on a slow connection, and the
 * failure case is benign — a notice that reappears once is better than a button
 * that does not respond.
 */

import { useEffect, useState } from "react";
import { AlertTriangle, Info, X, Wrench } from "lucide-react";

import { notificationsApi, type Notice, type NoticeType } from "@/lib/api/notifications";
import { cn } from "@/lib/utils";

/** Notices shown at once. More than a few and the strip is the page. */
const MAX_VISIBLE = 4;

/**
 * Visual treatment per notice type.
 *
 * `popup` and `banner` both land in the admin strip: a "popup" aimed at the
 * dashboard is an in-page message for an operator, which is exactly what this
 * is. The distinction only matters on the storefront, where a popup is modal.
 */
const TYPE_STYLE: Record<
  NoticeType,
  { icon: typeof Info; className: string; label: string }
> = {
  // The three types the model actually has (NoticeType in
  // backend/app/modules/notifications/domain/notice_models.py). All three land
  // in the admin strip: aimed at the dashboard, a "popup" is an in-page message
  // for an operator, which is exactly this component. The type only decides
  // the treatment, not the audience.
  banner: {
    icon: Info,
    className: "border-border bg-muted/60 text-foreground",
    label: "بنر",
  },
  popup: {
    icon: Wrench,
    className: "border-border bg-muted/60 text-foreground",
    label: "اطلاعیه",
  },
  alert_bar: {
    icon: AlertTriangle,
    className: "border-amber-500/40 bg-amber-500/10 text-amber-800 dark:text-amber-300",
    label: "هشدار",
  },
};
interface AdminNoticesProps {
  /**
   * The admin page context, passed to the API so targeted notices filter.
   *
   * Defaults to "all", not "dashboard": TargetPage only knows all, home,
   * checkout and dashboard, so pinning this to "dashboard" would hide every
   * notice on the twenty other admin screens — the exact opposite of a
   * persistent strip. A page can still narrow it by passing a target.
   */
  targetPage?: string;
  className?: string;
}

export function AdminNotices({ targetPage = "all", className }: AdminNoticesProps) {
  const [notices, setNotices] = useState<Notice[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await notificationsApi.getActiveNotices(targetPage);
        if (!cancelled) setNotices(rows.slice(0, MAX_VISIBLE));
      } catch {
        // A notice strip that cannot load must not take the admin page with it.
        // The notices page is still reachable, so silence here is the right
        // failure: an error toast above an empty strip helps nobody.
        if (!cancelled) setNotices([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [targetPage]);

  if (notices.length === 0) return null;

  const dismiss = (noticeId: string) => {
    // Close first, ask the server second (see the note at the top).
    setNotices((prev) => prev.filter((n) => n.id !== noticeId));
    void notificationsApi
      .markNoticeSeen(noticeId)
      .catch(() => undefined);
  };

  return (
    <div className={cn("space-y-2", className)} role="status" aria-live="polite">
      {notices.map((notice) => {
        const style = TYPE_STYLE[notice.notice_type] ?? TYPE_STYLE.banner;
        const Icon = style.icon;
        return (
          <div
            key={notice.id}
            className={cn(
              "flex items-start gap-3 rounded-lg border px-3 py-2.5 text-sm",
              style.className,
            )}
          >
            <Icon className="mt-0.5 h-4 w-4 shrink-0" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{notice.title}</p>
              {/* The body is server-side HTML and was sanitized on the way in
                  (see NoticeCreateRequest.content_html). It is rendered, not
                  escaped: an admin-authored notice that shows its own tags is
                  not a feature anyone wants. */}
              <div
                className="mt-0.5 text-xs leading-relaxed opacity-90 [&_a]:underline"
                dangerouslySetInnerHTML={{ __html: notice.content_html }}
              />
            </div>
            <button
              type="button"
              onClick={() => dismiss(notice.id)}
              aria-label={`بستن اطلاعیه: ${notice.title}`}
              className="shrink-0 rounded p-0.5 opacity-60 transition-opacity hover:opacity-100"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
