"use client";

import { useEffect, useMemo, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { EmptyState, ErrorState, PageLoader } from "@/components/shared/page-state";
import { cn } from "@/lib/utils";
import {
  BulkActionBar,
  ColumnVisibilityControl,
  ListEngineProvider,
  PaginationBar,
  SortableHeader,
  useListEngine,
  type BulkAction,
} from "@/components/admin/list-engine";

/**
 * Canonical admin data table.
 *
 * Now backed by the list engine (`list-engine.tsx`), which owns sorting,
 * selection, pagination and column visibility. A screen that only wants the
 * old render-only behaviour passes no new props and gets exactly what it did
 * before — every one of the 40 existing call sites keeps working unchanged.
 */

export interface DataTableColumn<T> {
  /** Stable column key. */
  key: string;
  header: ReactNode;
  /** Extra classes for both th and td (alignment, width, monospace...). */
  className?: string;
  /** Render the cell content for a row. */
  render: (row: T) => ReactNode;
  /** Hide this column below `lg` (keeps wide tables usable on mobile). */
  hideOnMobile?: boolean;
  /** Pin the column to the table's scroll edge (RTL: the left edge) so its
   *  content — per-row actions — stays visible while the table scrolls
   *  horizontally. Needs a solid bg on the cells to cover the scrolled
   *  content passing underneath. */
  stickyEdge?: boolean;
  /** Tiered hiding for wide tables: the column disappears below the given
   *  breakpoint and comes back above it. Tiers: md 768 / lg 1024 / xl 1280 /
   *  2xl 1536. A 9-column table squeezed into a 1280px admin viewport (with
   *  the sidebar) pushed its action buttons out of the card — hiding the
   *  low-priority columns per tier keeps every cell contained. */
  hideBelow?: "md" | "lg" | "xl" | "2xl";
  /** Make the header sortable. Value is compared with `<`/`>` on the row. */
  sortValue?: (row: T) => string | number | null | undefined;
  /** Label for the Screen Options column picker. Defaults to the key. */
  columnLabel?: string;
  /**
   * Pinned column: never hidden by the Screen Options picker and not listed
   * in it. WordPress's `cb` (select-all) column behaves the same — hiding the
   * only per-row checkbox would make bulk selection unreachable.
   */
  alwaysVisible?: boolean;
}

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  loadingMessage?: string;
  /** Error message — when set, an ErrorState row is shown instead of data. */
  error?: string | null;
  emptyMessage?: string;
  emptyDescription?: string;
  /** Rendered inside the empty state (e.g. a create button). */
  emptyAction?: ReactNode;
  emptyIcon?: ReactNode;
  onRowClick?: (row: T) => void;
  /** Optional per-row extra classes (e.g. highlighting high-risk rows). */
  rowClassName?: (row: T) => string;
  className?: string;
  /** Use table-layout: fixed for equal column distribution (default: auto). */
  tableLayout?: "auto" | "fixed";
  /** Minimum table width (px as CSS length). Below it the wrapper scrolls
   *  horizontally instead of letting `whitespace-nowrap` cells overflow the
   *  card — the admin products table at ~1280 viewports pushed its action
   *  buttons outside the card borders without this. */
  minWidth?: string;

  // ── list-engine features; all optional ───────────────────────────────────
  /** Show a select-all checkbox column and enable `bulkActions`. */
  selectable?: boolean;
  bulkActions?: BulkAction<T>[];
  /** Extra inputs a bulk action needs (e.g. a destination role), rendered
   *  beside the action buttons rather than nested inside one. */
  bulkControls?: ReactNode;
  /** Slice `rows` client-side and show a pager. Omit for server-paginated data. */
  pageSize?: number;
  /**
   * Server-side pagination. Pass `rows` = the page the server returned plus
   * `serverTotal` = how many rows exist across every page; the table then
   * pages over that total instead of over the rows in hand.
   *
   * `rows` already being one page means sorting is the server's job: sorting
   * a single page in the browser would reorder rows the server picked, and
   * would say "sorted" while the rest of the set is untouched. So in this mode
   * the sortable headers render as plain labels rather than sort buttons.
   */
  serverTotal?: number;
  /** Fires on pager navigation; the caller refetches with the new page. */
  onServerPageChange?: (page: number, pageSize: number) => void;
  /** Persist column visibility under this key (WordPress "Screen Options"). */
  columnVisibilityKey?: string;
  /** Initial sort, applied to the whole (unsliced) set. */
  defaultSort?: { key: string; dir?: "asc" | "desc" };
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading = false,
  loadingMessage = "در حال دریافت داده‌ها...",
  error = null,
  emptyMessage = "موردی یافت نشد.",
  emptyDescription,
  emptyAction,
  emptyIcon,
  onRowClick,
  rowClassName,
  className,
  tableLayout = "auto",
  minWidth,
  selectable = false,
  bulkActions,
  bulkControls,
  pageSize,
  serverTotal,
  onServerPageChange,
  columnVisibilityKey,
  defaultSort,
}: DataTableProps<T>) {
  const engine = useListEngine<T>({ initialPageSize: pageSize, initialSort: defaultSort });
  const isServerPaged = serverTotal !== undefined;

  const sortableColumns = useMemo(
    () => (isServerPaged ? [] : columns.filter((c) => c.sortValue)),
    [columns, isServerPaged]
  );

  // Sort the whole set, then slice. Sorting after slicing would only order
  // within the current page, which reads as a broken sort.
  const sorted = useMemo(() => {
    if (!engine.sortKey) return rows;
    const col = sortableColumns.find((c) => c.key === engine.sortKey);
    if (!col?.sortValue) return rows;
    const dir = engine.sortDir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      // Nulls sort last in both directions; a row with no date should not lead
      // a "newest first" list just because it is empty.
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (av < bv) return -1 * dir;
      if (av > bv) return 1 * dir;
      return 0;
    });
  }, [rows, engine.sortKey, engine.sortDir, sortableColumns]);

  // The size selector lives in the engine: the `pageSize` prop is only its
  // initial value. Client-side paging must slice with the live engine size,
  // or picking a new size never applies (the trigger just snaps back).
  const clientPageSize = pageSize ? engine.pageSize : null;
  const totalPages = isServerPaged
    ? Math.max(1, Math.ceil(serverTotal / (pageSize || 25)))
    : clientPageSize
      ? Math.max(1, Math.ceil(sorted.length / clientPageSize))
      : 1;
  // A filter that shrinks the result set can leave the current page past the
  // end, which renders an empty table with no explanation.
  useEffect(() => {
    if (engine.page > totalPages) engine.setPage(totalPages);
  }, [engine.page, totalPages, engine]);

  const visible = useMemo(() => {
    // Server mode: `rows` is already one page, so slicing again would hide
    // rows the server sent.
    if (isServerPaged || !clientPageSize) return sorted;
    const start = (engine.page - 1) * clientPageSize;
    return sorted.slice(start, start + clientPageSize);
  }, [sorted, engine.page, clientPageSize, isServerPaged]);

  const selectedRows = useMemo(
    () => rows.filter((r) => engine.selected.has(rowKey(r))),
    [rows, engine.selected, rowKey]
  );
  const engineWithRows = useMemo(() => ({ ...engine, selectedRows }), [engine, selectedRows]);

  // Pinned (`alwaysVisible`) columns survive even when a stale localStorage
  // entry says they are hidden — the picker can no longer produce that state,
  // but preferences written before the flag existed can.
  const shown = useMemo(
    () => columns.filter((c) => c.alwaysVisible || !engine.hiddenColumns.has(c.key)),
    [engine, columns]
  );
  const mobileHidden = (col: DataTableColumn<T>) => {
    if (col.hideOnMobile) return "hidden lg:table-cell";
    switch (col.hideBelow) {
      case "md":
        return "hidden md:table-cell";
      case "xl":
        return "hidden xl:table-cell";
      case "2xl":
        return "hidden 2xl:table-cell";
      case "lg":
        return "hidden lg:table-cell";
      default:
        return "";
    }
  };
  const stickyClass = (col: DataTableColumn<T>) =>
    col.stickyEdge ? "sticky left-0 z-10 bg-card" : "";

  // The select-all checkbox covers the page on screen, not the whole filtered
  // set — checking 3 boxes when 20 rows are rendered would be a lie.
  const shownKeys = visible.map(rowKey);
  const allShownSelected = shownKeys.length > 0 && shownKeys.every((k) => engine.selected.has(k));
  const someShownSelected = shownKeys.some((k) => engine.selected.has(k));

  const onRowKeyDown = (row: T) => (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (!onRowClick) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onRowClick(row);
    }
  };

  const colCount = shown.length + (selectable ? 1 : 0);

  return (
    <ListEngineProvider state={engineWithRows}>
      <div className={cn("space-y-2", className)}>
        {(selectable || columnVisibilityKey) && (
          <div className="flex flex-wrap items-center gap-2">
            {columnVisibilityKey && (
              <ColumnVisibilityControl
                storageKey={columnVisibilityKey}
                columns={columns
                  .filter((c) => !c.alwaysVisible)
                  .map((c) => ({
                    key: c.key,
                    label: c.columnLabel ?? (typeof c.header === "string" ? c.header : c.key),
                  }))}
              />
            )}
          </div>
        )}

        {selectable && (
          <BulkActionBar rows={visible} actions={bulkActions ?? []} controls={bulkControls} />
        )}

        <Card className="overflow-hidden">
          {/* `relative` is load-bearing, not decoration: the sr-only spans in
              action columns are position:absolute, and with no positioned
              ancestor their containing block is the viewport — the scroller's
              clip does not apply to them, so in RTL they extend the document's
              scrollable overflow to the left (measured: 574px page scrollWidth
              at a 390px viewport on the dashboard). As their containing block,
              the scroller clips them again. The table itself was always
              contained — it keeps scrolling inside the card unchanged. */}
          <div className="relative overflow-x-auto">
            <table
              className={cn("w-full text-center text-xs lg:text-sm", tableLayout === "fixed" && "table-fixed")}
              style={minWidth ? { minWidth } : undefined}
            >
              <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  {selectable && (
                    <th scope="col" className="w-12 px-2 py-2 align-middle sm:px-3 lg:px-4">
                      <Checkbox
                        checked={allShownSelected ? true : someShownSelected ? "indeterminate" : false}
                        onCheckedChange={() => engine.toggleAll(shownKeys)}
                        aria-label="انتخاب همهٔ ردیف‌های این صفحه"
                      />
                    </th>
                  )}
                  {shown.map((col) => {
                    const cellClass = cn("px-2 py-2 align-middle whitespace-nowrap sm:px-3 lg:px-4", col.className, mobileHidden(col), stickyClass(col));
                    if (col.sortValue) {
                      return (
                        <SortableHeader
                          key={col.key}
                          columnKey={col.key}
                          className={cellClass}
                          engine={engine}
                        >
                          {col.header}
                        </SortableHeader>
                      );
                    }
                    return (
                      <th key={col.key} scope="col" className={cellClass}>
                        {col.header}
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr>
                    <td colSpan={colCount} className="p-0">
                      <PageLoader message={loadingMessage} className="min-h-0 py-10" />
                    </td>
                  </tr>
                ) : error ? (
                  <tr>
                    <td colSpan={colCount} className="p-0">
                      <ErrorState
                        title="خطا در دریافت داده‌ها"
                        description={error}
                        className="border-0 bg-transparent min-h-0 py-8"
                      />
                    </td>
                  </tr>
                ) : visible.length === 0 ? (
                  <tr>
                    <td colSpan={colCount} className="p-0">
                      <EmptyState
                        title={emptyMessage}
                        description={emptyDescription}
                        action={emptyAction}
                        icon={emptyIcon}
                        className="border-0 bg-transparent min-h-0 py-8"
                      />
                    </td>
                  </tr>
                ) : (
                  visible.map((row) => {
                    const key = rowKey(row);
                    return (
                      <tr
                        key={key}
                        onClick={onRowClick ? () => onRowClick(row) : undefined}
                        onKeyDown={onRowClick ? onRowKeyDown(row) : undefined}
                        // A row that behaves like a button must be reachable and
                        // operable by keyboard; tabIndex alone would make it a
                        // focus stop with no announced role.
                        tabIndex={onRowClick ? 0 : undefined}
                        role={onRowClick ? "button" : undefined}
                        aria-label={onRowClick ? `باز کردن ردیف ${key}` : undefined}
                        className={cn(
                          "transition-colors hover:bg-muted/30",
                          onRowClick && "cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
                          engine.selected.has(key) && "bg-muted/50",
                          rowClassName?.(row)
                        )}
                      >
                        {selectable && (
                          <td className="px-2 py-2 align-middle sm:px-3 lg:px-4" onClick={(e) => e.stopPropagation()}>
                            <Checkbox
                              checked={engine.selected.has(key)}
                              onCheckedChange={() => engine.toggleRow(key)}
                              aria-label={`انتخاب ردیف ${key}`}
                            />
                          </td>
                        )}
                        {shown.map((col) => (
                          <td
                            key={col.key}
                            className={cn("px-2 py-2 align-middle sm:px-3 lg:px-4", col.className, mobileHidden(col), stickyClass(col))}
                          >
                            {col.render(row)}
                          </td>
                        ))}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {(isServerPaged
          ? (pageSize || 25) < serverTotal
          : !!pageSize && sorted.length > pageSize) && (
          <PaginationBar
            totalRows={isServerPaged ? serverTotal : sorted.length}
            page={engine.page}
            pageSize={isServerPaged ? pageSize || 25 : clientPageSize!}
            onPageChange={
              isServerPaged
                ? (p) => onServerPageChange?.(p, pageSize || 25)
                : engine.setPage
            }
            onPageSizeChange={
              isServerPaged
                ? (p) => onServerPageChange?.(1, p)
                : engine.setPageSize
            }
          />
        )}
      </div>
    </ListEngineProvider>
  );
}
