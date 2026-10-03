"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { blogAdminApi } from "@/lib/api/blog";
import { useToast } from "@/components/ui/use-toast";

/** Editing lock and autosave for one CMS page.
 *
 *  WordPress applies one mechanism to everything an author can edit. Posts had
 *  it; pages did not, which meant two editors on the same page overwrote each
 *  other silently and a lost draft was simply lost.
 *
 *  The three decisions that are not obvious:
 *
 *  - **The lock is advisory and does not block typing.** Refusing the keystroke
 *    would make "someone else is editing this" into a data-loss event for the
 *    person who got there second. So it warns, and the save is what the lock
 *    actually protects.
 *  - **Autosave is debounced and only while the document is dirty.** Every
 *    keystroke is not a save; the snapshot exists so a closed tab or a crash
 *    costs nothing, and a request per character would make the page feel like
 *    it was fighting the server.
 *  - **The snapshot is never loaded automatically.** Restoring over what is on
 *    screen would destroy the newer text. The caller offers it, a human
 *    decides.
 */

const AUTOSAVE_DELAY_MS = 3_000;
const HEARTBEAT_MS = 60_000;

export interface EditorLockState {
  /** True when another user holds the lock — never true for the person editing. */
  lockedByOther: string | null;
  /** Take the lock away from whoever has it. */
  takeOver: () => Promise<void>;
  release: () => Promise<void>;
}

export function usePageEditingLock(
  pageId: string | null,
  kind: "pages" | "posts" = "pages",
): EditorLockState {
  const [lockedByOther, setLockedByOther] = useState<string | null>(null);
  const heldRef = useRef(false);

  const release = useCallback(async () => {
    if (!pageId || !heldRef.current) return;
    heldRef.current = false;
    setLockedByOther(null);
    try {
      await blogAdminApi.releaseLock(pageId, kind);
    } catch {
      // The lock expires on its own; a failed release is not worth interrupting
      // the editor over, and saying so would be noise.
    }
  }, [pageId]);

  const takeOver = useCallback(async () => {
    if (!pageId) return;
    try {
      // The dedicated take-over route, not acquire-then-check: `acquire`
      // reports "already held" for a lock somebody else owns, so calling it
      // against a foreign lock returns true and hands back no lock at all.
      const res = await blogAdminApi.takeOverLock(pageId, kind);
      if (res.acquired) {
        heldRef.current = true;
        setLockedByOther(null);
      }
    } catch {
      // Leave the banner up: the point of a failed take-over is that somebody
      // else still has it.
    }
  }, [pageId, kind]);

  useEffect(() => {
    if (!pageId) return;
    let cancelled = false;

    const check = async () => {
      try {
        const state = await blogAdminApi.checkLock(pageId, kind);
        if (cancelled) return;
        if (state.locked && !state.locked_by) return;
        const mine = state.locked_by === null || state.locked_by === undefined;
        heldRef.current = mine;
        setLockedByOther(state.locked ? (state.locked_by ?? "کاربر دیگری") : null);
      } catch {
        // A failing check must not block editing.
      }
    };

    void check();
    const beat = setInterval(() => {
      if (heldRef.current) {
        void blogAdminApi.heartbeatLock(pageId, kind).catch(() => undefined);
      } else {
        void check();
      }
    }, HEARTBEAT_MS);

    // Leaving the page must release the lock, or the next editor sees a
    // phantom occupant until the heartbeat times out.
    const onUnload = () => {
      if (heldRef.current) {
        void blogAdminApi.releaseLock(pageId, kind);
      }
    };
    window.addEventListener("beforeunload", onUnload);

    return () => {
      cancelled = true;
      clearInterval(beat);
      window.removeEventListener("beforeunload", onUnload);
      void release();
    };
  }, [pageId, kind, release]);

  return { lockedByOther, takeOver, release };
}

/** Debounced autosave for a CMS page's editing payload.
 *
 *  Returns `save` for the explicit case and `markClean` for after a real save,
 *  because a successful save should clear the snapshot — otherwise the editor
 *  is offered back the text it just published.
 */
export function usePageAutosave(
  pageId: string | null,
  payload: Record<string, unknown>,
  kind: "pages" | "posts" = "pages",
): { dirty: boolean; savedAt: string | null; markClean: () => void } {
  const { toast } = useToast();
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The payload is re-created on every keystroke; a ref keeps the timer from
  // being reset by its own identity changing.
  const latest = useRef(payload);
  latest.current = payload;

  const save = useCallback(async () => {
    if (!pageId) return;
    try {
      const result = await blogAdminApi.saveAutosave(pageId, latest.current, kind);
      if (result.saved) {
        setSavedAt(result.saved_at ?? new Date().toISOString());
        setDirty(false);
      }
    } catch {
      toast({
        title: "ذخیره‌ی خودکار ناموفق بود",
        description: "می‌توانید ذخیره‌ی دستی بزنید.",
        variant: "destructive",
      });
    }
  }, [pageId, toast]);

  useEffect(() => {
    if (!pageId || !dirty) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      void save();
    }, AUTOSAVE_DELAY_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [dirty, payload, pageId, save]);

  const markClean = useCallback(() => {
    setDirty(false);
    if (!pageId) return;
    // Drop the snapshot so the next load is not offered text that was already
    // saved deliberately.
    void blogAdminApi.clearAutosave(pageId, kind).catch(() => undefined);
  }, [pageId]);

  return { dirty, savedAt, markClean };
}