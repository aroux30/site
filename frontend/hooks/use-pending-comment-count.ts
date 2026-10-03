"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { blogAdminApi } from "@/lib/api/blog";
import { useAuth } from "@/hooks/use-auth";

/** The awaiting-mod bubble for the admin bar.
 *
 *  WordPress shows a count on the Comments menu so a moderator knows an
 *  unanswered comment is waiting without opening the page. On a store the gap
 *  is sharper: a customer asking where their review went, and nobody noticing
 *  because nothing said so.
 *
 *  Three decisions, each of which has a wrong version that looks fine:
 *
 *  - polled, not pushed. A comment arrives while the admin is on the orders
 *    page; there is no event to subscribe to without a socket, and a badge
 *    that only updates on navigation is the badge that was always wrong.
 *  - paused when the tab is hidden. Polling a tab nobody is looking at spends
 *    requests to update a number nobody sees.
 *  - silent on failure. A 403 from a moderator who cannot moderate comments,
 *    or an outage, must not put a badge on the bar — a badge showing an error
 *    is worse than no badge, and a thrown error would take the whole admin
 *    chrome down with it.
 */
export function usePendingCommentCount(): {
  pending: number | null;
  refresh: () => Promise<void>;
} {
  const [pending, setPending] = useState<number | null>(null);
  const { user } = useAuth();
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const counts = await blogAdminApi.pendingCommentCount();
      setPending(counts.pending + counts.spam);
    } catch {
      // Leave the last known value rather than clearing it: a transient
      // failure should not make a real queue look empty, which is exactly the
      // mistake this badge exists to prevent.
    }
  }, []);

  useEffect(() => {
    // Only for someone who can actually moderate. Asking anyway would spend a
    // 403 every poll for every admin who cannot see the number.
    //
    // A superuser counts: the RBAC layer grants everything to them, so they
    // can moderate, but their `permissions` list is empty precisely because
    // there is nothing left to enumerate. Without this check the badge would
    // be hidden from the one person most likely to be watching the queue.
    const canModerate =
      user?.is_superuser === true ||
      user?.permissions?.includes("blog:moderate_comments") ||
      user?.permissions?.includes("blog:write");

    if (!canModerate) return;

    let cancelled = false;
    const tick = async () => {
      if (cancelled || document.hidden) return;
      await refresh();
    };

    void tick();
    timer.current = setInterval(tick, 60_000);
    return () => {
      cancelled = true;
      if (timer.current) clearInterval(timer.current);
      timer.current = null;
    };
  }, [refresh, user]);

  return { pending, refresh };
}