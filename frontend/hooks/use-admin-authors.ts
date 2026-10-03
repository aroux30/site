"use client";

/**
 * useAdminAuthors — every active user, for a picker or a filter.
 *
 * `listUsers` is paged with a server cap of 100, so a single call silently
 * returns only the first hundred people. An author filter that quietly omitted
 * user 143 would look like "this person has no posts" — the worst possible
 * answer, and a wrong one. So this walks the pages instead of asking for a
 * page_size the server would refuse anyway.
 *
 * Capped at `MAX_PAGES` so a large directory cannot spin forever: a store with
 * tens of thousands of accounts gets the most recent pages, and the caller is
 * told the list was truncated rather than being handed a silent subset.
 */
import { useEffect, useState } from "react";

import { usersAdminApi, type AdminUser } from "@/lib/api/users";

const PAGE_SIZE = 100;
/** 20 pages = 2,000 authors. Past that the picker is unusable anyway. */
const MAX_PAGES = 20;

export interface AdminAuthorsResult {
  authors: AdminUser[];
  loading: boolean;
  /** True when the directory is larger than what was fetched. */
  truncated: boolean;
}

export function useAdminAuthors(enabled = true): AdminAuthorsResult {
  const [authors, setAuthors] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoading(true);

    (async () => {
      const seen: AdminUser[] = [];
      let cut = false;
      try {
        for (let page = 1; page <= MAX_PAGES; page += 1) {
          const res = await usersAdminApi.listUsers({ page, page_size: PAGE_SIZE, is_active: true });
          seen.push(...res.items);
          // `listUsers` returns a total, not a page count, so the last page is
          // derived here rather than read.
          if (seen.length >= res.total) break;
          // Ran out of pages to walk while the server still had more.
          if (page === MAX_PAGES) cut = true;
        }
      } catch {
        // A failing lookup degrades to "no author list" — the rest of the
        // screen must keep working, and an empty picker is better than a
        // thrown error over a filter the user did not ask for.
        if (!cancelled) {
          setAuthors([]);
          setTruncated(false);
          setLoading(false);
        }
        return;
      }
      if (cancelled) return;
      setAuthors(seen);
      setTruncated(cut);
      setLoading(false);
    })();

    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return { authors, loading, truncated };
}
