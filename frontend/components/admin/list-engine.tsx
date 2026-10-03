"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

/**
 * The admin list-table engine.
 *
 * Before this, every admin screen hand-rolled its own sort state, page state and
 * bulk-selection state, and 15 of them kept their own `selected` Set — so
 * "add bulk edit to this list" meant writing the whole thing again. This holds
 * that state once so a screen only declares *what* is sortable, paginated and
 * selectable.
 *
 * It is deliberately data-source agnostic: it does not fetch. A screen that
 * already has a page of rows (server-paginated, or client-filtered) can adopt
 * the pieces it needs without changing where the data comes from.
 */

export interface BulkAction<T> {
  id: string;
  label: ReactNode;
  /** Return true when the action actually ran, so the selection can clear. */
  onRun: (selected: T[]) => Promise<boolean> | boolean;
  /** Ask before running. WordPress makes this mandatory for destructive acts. */
  confirm?: (selected: T[]) => string | null;
  variant?: "default" | "destructive";
}

interface ListEngineState<T> {
  // Sorting
  sortKey: string | null;
  sortDir: "asc" | "desc";
  setSort: (key: string) => void;
  // Selection
  selected: Set<string>;
  toggleRow: (key: string) => void;
  toggleAll: (keys: string[]) => void;
  clearSelection: () => void;
  selectedRows: T[];
  // Pagination (client-side; server-paginated screens pass rows already sliced)
  page: number;
  pageSize: number;
  setPage: (page: number) => void;
  setPageSize: (size: number) => void;
  // Column visibility (WordPress's "Screen Options")
  hiddenColumns: Set<string>;
  toggleColumn: (key: string) => void;
  visibleColumns: <C>(columns: C[]) => C[];
}

const ListEngineContext = createContext<ListEngineState<unknown> | null>(null);

export function useListEngine<T>(options?: {
  initialPageSize?: number;
  initialSort?: { key: string; dir?: "asc" | "desc" };
}) {
  const [sortKey, setSortKey] = useState<string | null>(options?.initialSort?.key ?? null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">(options?.initialSort?.dir ?? "asc");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(options?.initialPageSize ?? 20);
  const [hiddenColumns, setHiddenColumns] = useState<Set<string>>(new Set());

  const setSort = useCallback((key: string) => {
    setSortKey((current) => {
      if (current === key) {
        // Same column: flip direction. A fresh column resets to ascending, which
        // is what a user expects when they click an unsorted header.
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        return current;
      }
      setSortDir("asc");
      return key;
    });
    setPage(1);
  }, []);

  const toggleRow = useCallback((key: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const toggleAll = useCallback((keys: string[]) => {
    setSelected((current) => {
      const next = new Set(current);
      const allSelected = keys.length > 0 && keys.every((k) => next.has(k));
      if (allSelected) keys.forEach((k) => next.delete(k));
      else keys.forEach((k) => next.add(k));
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => setSelected(new Set()), []);

  // Changing page size while on page 5 of 2 would show an empty table, so the
  // page resets. WordPress does the same when the rows-per-page changes.
  const changePageSize = useCallback((size: number) => {
    setPageSize(size);
    setPage(1);
  }, []);

  const toggleColumn = useCallback((key: string) => {
    setHiddenColumns((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  const value = useMemo(
    () => ({
      sortKey,
      sortDir,
      setSort,
      selected,
      toggleRow,
      toggleAll,
      clearSelection,
      // The caller owns `rows`; it injects the resolved list via
      // `selectedRows` on the engine object it passes to the provider.
      selectedRows: [] as T[],
      page,
      pageSize,
      setPage,
      setPageSize: changePageSize,
      hiddenColumns,
      toggleColumn,
      visibleColumns: (<C extends { key: string }>(cols: C[]) =>
        cols.filter((c) => !hiddenColumns.has(c.key))) as <C>(columns: C[]) => C[],
    }),
    [
      sortKey,
      sortDir,
      setSort,
      selected,
      toggleRow,
      toggleAll,
      clearSelection,
      page,
      pageSize,
      changePageSize,
      hiddenColumns,
      toggleColumn,
    ]
  );

  return value;
}

/** Inside a screen that already owns a `ListEngineProvider`. */
export function useListSelection<T>(): ListEngineState<T> {
  const ctx = useContext(ListEngineContext);
  if (!ctx) throw new Error("useListSelection must be used inside ListEngineProvider");
  return ctx as ListEngineState<T>;
}

export function ListEngineProvider<T>({
  children,
  state,
}: {
  children: ReactNode;
  state: ListEngineState<T>;
}) {
  return (
    <ListEngineContext.Provider value={state as ListEngineState<unknown>}>
      {children}
    </ListEngineContext.Provider>
  );
}

/** Sortable column header with `aria-sort` so it is announced, not just drawn. */
export function SortableHeader({
  columnKey,
  children,
  className,
  engine,
}: {
  columnKey: string;
  children: ReactNode;
  className?: string;
  engine?: Pick<ListEngineState<unknown>, "sortKey" | "sortDir" | "setSort">;
}) {
  const active = engine?.sortKey === columnKey;
  const ariaSort = !engine
    ? undefined
    : active
      ? engine.sortDir === "asc"
        ? "ascending"
        : "descending"
      : "none";

  if (!engine) {
    return (
      <th scope="col" className={className}>
        {children}
      </th>
    );
  }

  return (
    <th scope="col" aria-sort={ariaSort} className={cn("p-0", className)}>
      <button
        type="button"
        onClick={() => engine.setSort(columnKey)}
        className="flex w-full items-center gap-1 px-4 py-3 text-right font-medium hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {children}
        <span aria-hidden="true" className="text-[10px] opacity-70">
          {active ? (engine.sortDir === "asc" ? "▲" : "▼") : "↕"}
        </span>
      </button>
    </th>
  );
}

/** The bulk-action bar. Renders nothing when nothing is selected, so a screen
 *  does not have to reserve space for it. */
export function BulkActionBar<T>({
  rows,
  actions,
  className,
  controls,
}: {
  rows: T[];
  actions: BulkAction<T>[];
  className?: string;
  /**
   * Extra inputs an action needs before it can run — a destination role for
   * "change role", say. Rendered as a sibling of the action buttons, never
   * inside one: an input nested in a button is invalid HTML and a click on it
   * would also fire the button's action. A screen that passes none gets the
   * bar exactly as it was.
   */
  controls?: ReactNode;
}) {
  const { selected, selectedRows, clearSelection, toggleAll, setPage } = useListSelection<T>();
  const [busy, setBusy] = useState<string | null>(null);

  const keys = rows.map((r) => (r as { id?: string }).id).filter(Boolean) as string[];

  if (selected.size === 0 || actions.length === 0) return null;

  const run = async (action: BulkAction<T>) => {
    // Named `targets`, not `rows`: `rows` is the prop and shadowing it made
    // TypeScript infer a circular type.
    const targets =
      selectedRows.length > 0
        ? selectedRows
        : rows.filter((r) => selected.has((r as { id?: string }).id!));
    const message = action.confirm?.(targets);
    if (message && !window.confirm(message)) return;
    setBusy(action.id);
    try {
      const ok = await action.onRun(targets);
      if (ok) {
        clearSelection();
        // The server may now hold fewer rows on this page; page 1 is the only
        // page guaranteed to be populated.
        if (setPage) setPage(1);
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <div
      role="toolbar"
      aria-label="کنش‌های گروهی"
      className={cn(
        "flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2",
        className
      )}
    >
      <span className="text-xs font-medium">{selected.size} مورد انتخاب شده</span>
      {controls && <div className="flex flex-wrap items-center gap-2">{controls}</div>}
      <div className="flex flex-wrap gap-2">
        {actions.map((action) => (
          <Button
            key={action.id}
            type="button"
            size="sm"
            variant={action.variant === "destructive" ? "destructive" : "outline"}
            disabled={busy !== null}
            onClick={() => run(action)}
          >
            {busy === action.id ? "در حال اجرا..." : action.label}
          </Button>
        ))}
      </div>
      <Button
        type="button"
        size="sm"
        variant="ghost"
        className="mr-auto"
        onClick={() => {
          clearSelection();
          toggleAll([]);
        }}
      >
        لغو انتخاب
      </Button>
    </div>
  );
}

/** WordPress's "Screen Options": per-user column visibility, persisted. */
export function ColumnVisibilityControl({
  columns,
  storageKey,
  className,
}: {
  columns: { key: string; label: string }[];
  storageKey: string;
  className?: string;
}) {
  const { hiddenColumns, toggleColumn } = useListSelection<unknown>();
  const [open, setOpen] = useState(false);

  // Restore on mount. Wrapped because localStorage throws in private mode and
  // in some SSR-adjacent contexts; a missing preference is not worth a crash.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as string[];
        if (Array.isArray(parsed)) parsed.forEach((k) => toggleColumn(k));
      }
    } catch {
      /* preference is optional */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, JSON.stringify([...hiddenColumns]));
    } catch {
      /* preference is optional */
    }
  }, [hiddenColumns, storageKey]);

  if (!open) {
    return (
      <Button type="button" size="sm" variant="outline" onClick={() => setOpen(true)} className={className}>
        ستون‌ها
      </Button>
    );
  }

  return (
    <div className={cn("flex flex-wrap items-center gap-2 rounded-lg border border-border p-2", className)}>
      {columns.map((col) => (
        <label key={col.key} className="flex cursor-pointer items-center gap-1.5 text-xs">
          <Checkbox
            checked={!hiddenColumns.has(col.key)}
            onCheckedChange={() => toggleColumn(col.key)}
            aria-label={`نمایش ستون ${col.label}`}
          />
          {col.label}
        </label>
      ))}
      <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)}>
        بستن
      </Button>
    </div>
  );
}

/** Page-size selector plus prev/next, for a client-paginated list. */
export function PaginationBar({
  totalRows,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
  className,
  sizeOptions = [10, 20, 50, 100],
}: {
  totalRows: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  className?: string;
  sizeOptions?: number[];
}) {
  const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
  const from = totalRows === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(totalRows, page * pageSize);

  return (
    <div className={cn("flex flex-wrap items-center justify-between gap-2 text-xs", className)}>
      <span className="text-muted-foreground">
        نمایش {from} تا {to} از {totalRows} مورد
      </span>
      <div className="flex items-center gap-2">
        <Select value={String(pageSize)} onValueChange={(v) => onPageSizeChange(Number(v))}>
          <SelectTrigger className="h-8 w-24 text-xs" aria-label="تعداد در هر صفحه">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {sizeOptions.map((n) => (
              <SelectItem key={n} value={String(n)}>
                {n} در صفحه
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          قبلی
        </Button>
        <span className="min-w-16 text-center">
          صفحه {page} از {totalPages}
        </span>
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          بعدی
        </Button>
      </div>
    </div>
  );
}
