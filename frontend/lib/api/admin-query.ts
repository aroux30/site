"use client";

/**
 * The one way an admin page loads server data.
 *
 * Admin pages used to each carry their own `useEffect` + `useState(loading)` +
 * `useState(error)` + manual `try/catch`. Fifty-seven hand-written fetch
 * blocks meant fifty-seven places to get error handling wrong, and a few of
 * them swallowed the error silently — the products page rendered fabricated
 * rows on failure because its `catch` did nothing. The class of bug cannot be
 * fixed one page at a time; it needs a single path that does not have a
 * silent branch.
 *
 * This wraps TanStack Query behind the same `{ data, loading, error, reload }`
 * shape the pages already destructure, so the migration is mechanical and the
 * call sites do not have to learn a new vocabulary.
 *
 * Why not call `useQuery` directly in each page:
 *   - `loading` here is `isPending || isFetching`, matching what the old
 *     `setLoading(true)` meant across a manual refetch. Plain `isPending` is
 *     false during a background refetch, which would leave the page's spinner
 *     out of sync with the button the operator just pressed.
 *   - `error` is the message string the pages already render, not an `Error`
 *     object. Two different error helpers (`errorText`, `errorDetail`,
 *     `operationError`) grew up locally because each page needed that
 *     conversion; doing it once removes them.
 *   - `reload()` is what the "تلاش مجدد" buttons call. It awaits the refetch
 *     so a caller can `setSaving(false)` after it, as the old `await load()`
 *     allowed.
 */

import { useCallback, useEffect, useRef } from "react";
import {
  useQuery,
  useQueryClient,
  type QueryKey,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useToast } from "@/components/ui/use-toast";

export interface AdminQueryResult<T> {
  /** Last successful data, or `undefined` before the first load resolves. */
  data: T | undefined;
  /** True while a request is in flight, including background refetches. */
  loading: boolean;
  /** Operator-facing message, or `null` when the last load succeeded. */
  error: string | null;
  /**
   * Re-run the query and resolve once it settles. Use this from a button that
   * must not re-enable before fresh data arrives.
   */
  reload: () => Promise<void>;
}

export interface AdminQueryOptions<T> {
  /** Cache identity. Keep it stable — an inline array is a new key each render. */
  queryKey: QueryKey;
  /** Must resolve; throw to signal failure. */
  queryFn: () => Promise<T>;
  /** Shown in `error` when the thrown value carries no usable message. */
  fallbackError: string;
  /** Skip the request (e.g. waiting on a route param). */
  enabled?: boolean;
  /**
   * Extra TanStack options. `placeholderData: keepPreviousData` is the common
   * one — it keeps the previous page of a paginated list on screen while the
   * next loads, instead of collapsing to a spinner.
   */
  options?: Omit<
    UseQueryOptions<T, unknown, T, QueryKey>,
    "queryKey" | "queryFn" | "enabled"
  >;
  /**
   * Report load failures as a toast instead of (or in addition to) rendering
   * `error`. Some pages do this, and several pair the message with a second
   * line of guidance — `toastDescription` carries that line so a migration
   * does not quietly drop half the message.
   */
  toastOnError?: boolean;
  toastDescription?: string;
}

export function useAdminQuery<T>({
  queryKey,
  queryFn,
  fallbackError,
  enabled = true,
  options,
  toastOnError = false,
  toastDescription,
}: AdminQueryOptions<T>): AdminQueryResult<T> {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const query = useQuery<T, unknown, T, QueryKey>({
    queryKey,
    queryFn,
    enabled,
    ...options,
  });

  // `isFetching` covers the background refetch; `isPending` covers the first
  // load. The old manual `setLoading(true)` spanned both, so the true
  // equivalent is the union, not either one alone.
  const loading = query.isPending || query.isFetching;

  const error = query.isError ? apiErrorMessage(query.error, fallbackError) : null;

  // Some admin pages report load failures as a toast and keep the table
  // empty. That is a page-level choice, so it is opt-in here rather than
  // baked into the hook — but it must be the SAME message object the page
  // would have built, or the two paths drift.
  const shownErrorRef = useRef<string | null>(null);
  useEffect(() => {
    if (!toastOnError || !error) return;
    if (shownErrorRef.current === error) return;
    shownErrorRef.current = error;
    toast({
      title: error,
      ...(toastDescription ? { description: toastDescription } : {}),
      variant: "destructive",
    });
  }, [error, toastOnError, toast, toastDescription]);

  const reload = useCallback(async () => {
    // Mark the cached value stale WITHOUT triggering a fetch of its own
    // (`refetchType: "none"`), then run exactly one refetch. Doing a plain
    // invalidate here fires its own fetch, so a "تلاش مجدد" click would hit
    // the server twice — visible in tests as a counter that jumped by two.
    await queryClient.invalidateQueries({ queryKey, exact: true, refetchType: "none" });
    await queryClient.refetchQueries({ queryKey, exact: true });
  }, [queryClient, queryKey]);

  return { data: query.data, loading, error, reload };
}

/**
 * Invalidate one or more cached queries after a write.
 *
 * Every admin mutation needs this: the old pages called `load()` by hand after
 * a save, which only refreshed the list the page happened to own. A new
 * warehouse, for instance, changes both the warehouse list and the
 * stock-by-warehouse view — invalidating by prefix refreshes both without the
 * caller having to enumerate them.
 */
export function useAdminInvalidate() {
  const queryClient = useQueryClient();
  return useCallback(
    (...keys: QueryKey[]) => {
      for (const queryKey of keys) {
        void queryClient.invalidateQueries({ queryKey });
      }
    },
    [queryClient],
  );
}

/**
 * Run a mutation with the admin module's error convention.
 *
 * Returns the same shape the pages already use for their save handlers: a
 * boolean, and the message to show when it is false. The old handlers each
 * did this inline with their own `try/catch` and their own error helper.
 */
export function useAdminMutation() {
  const invalidate = useAdminInvalidate();
  return useCallback(
    async <T>(
      fn: () => Promise<T>,
      {
        fallbackError,
        onSuccess,
        invalidateKeys = [],
      }: {
        fallbackError: string;
        onSuccess?: (result: T) => void;
        invalidateKeys?: QueryKey[];
      },
    ): Promise<{ ok: true; data: T } | { ok: false; error: string }> => {
      try {
        const data = await fn();
        if (invalidateKeys.length > 0) invalidate(...invalidateKeys);
        onSuccess?.(data);
        return { ok: true, data };
      } catch (err) {
        return { ok: false, error: apiErrorMessage(err, fallbackError) };
      }
    },
    [invalidate],
  );
}
