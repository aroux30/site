"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Inbox,
  Loader2,
  MessageSquare,
  Search,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn, toPersianDigits } from "@/lib/utils";
import {
  TICKET_PRIORITIES,
  TICKET_PRIORITY_VISUALS,
  TICKET_STATUSES,
  TICKET_STATUS_VISUALS,
  isTicketStale,
  formatTicketRelativeTime,
  type TicketPriority,
  type TicketStatus,
} from "@/lib/admin/ticket-domain";
import { fetchAdminTickets, type TicketItem } from "@/lib/api/tickets";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

/**
 * The list view of the unified tickets page.
 *
 * What changed from the old table, on purpose:
 *  - Search and filters are SERVER-side (the old page filtered only the
 *    rows already on screen — a ticket on page 2 was unfindable).
 *  - Rows show the customer's name + phone (the old list rendered a raw
 *    user UUID), the message count and the last message preview.
 *  - Priority filter chips exist at all (the old page had no way to find
 *    the urgent tickets).
 *  - Stale rows (active ticket untouched for 48h+) are flagged inline.
 */

const PAGE_SIZE = 20;

export interface TicketsListViewProps {
  search: string;
  onSearchChange: (value: string) => void;
  onOpenTicket: (ticket: TicketItem) => void;
}

export function TicketsListView({ search, onSearchChange, onOpenTicket }: TicketsListViewProps) {
  const [statusFilter, setStatusFilter] = useState<TicketStatus | "all">("all");
  const [priorityFilter, setPriorityFilter] = useState<TicketPriority | "all">("all");
  const [page, setPage] = useState(0);
  const [items, setItems] = useState<TicketItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const debouncedSearch = useDebouncedValue(search, 350);

  useEffect(() => {
    setPage(0);
  }, [debouncedSearch, statusFilter, priorityFilter]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchAdminTickets({
        status: statusFilter === "all" ? undefined : statusFilter,
        priority: priorityFilter === "all" ? undefined : priorityFilter,
        search: debouncedSearch.trim() || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setItems(result.items);
      setTotal(result.total);
    } catch (err) {
      setError(apiErrorMessage(err, "خطا در دریافت تیکت‌ها از سرور."));
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, debouncedSearch, page]);

  useEffect(() => {
    void load();
  }, [load]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="space-y-3 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="جستجو در شماره تیکت یا موضوع..."
              className="pe-9 ps-9"
              aria-label="جستجوی تیکت"
            />
            {search && (
              <button
                type="button"
                onClick={() => onSearchChange("")}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="پاک کردن جستجو"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void load()}
            disabled={loading}
            className="gap-2 text-xs"
          >
            <Loader2 className={cn("h-3.5 w-3.5", loading && "animate-spin")} />
            بروزرسانی
          </Button>
        </div>

        {/* Status chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => setStatusFilter("all")}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              statusFilter === "all"
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground",
            )}
          >
            همه وضعیت‌ها
          </button>
          {TICKET_STATUSES.map((status) => {
            const active = statusFilter === status;
            return (
              <button
                key={status}
                type="button"
                onClick={() => setStatusFilter(active ? "all" : status)}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : cn("hover:border-primary/50", TICKET_STATUS_VISUALS[status].chip),
                )}
              >
                {TICKET_STATUS_VISUALS[status].label}
              </button>
            );
          })}
        </div>

        {/* Priority chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">اولویت:</span>
          <button
            type="button"
            onClick={() => setPriorityFilter("all")}
            className={cn(
              "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
              priorityFilter === "all"
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:text-foreground",
            )}
          >
            همه
          </button>
          {TICKET_PRIORITIES.map((priority) => {
            const active = priorityFilter === priority;
            return (
              <button
                key={priority}
                type="button"
                onClick={() => setPriorityFilter(active ? "all" : priority)}
                className={cn(
                  "rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
                  active
                    ? "border-primary bg-primary text-primary-foreground"
                    : cn("hover:border-primary/50", TICKET_PRIORITY_VISUALS[priority].chip),
                )}
              >
                {TICKET_PRIORITY_VISUALS[priority].label}
              </button>
            );
          })}
        </div>
      </Card>

      {/* Error */}
      {error && (
        <div
          role="alert"
          className="flex items-center justify-between gap-3 rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          <span className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </span>
          <Button variant="outline" size="sm" onClick={() => void load()} className="text-xs">
            تلاش مجدد
          </Button>
        </div>
      )}

      {/* Table */}
      <Card className="overflow-hidden">
        <div className="relative overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3">تیکت</th>
                <th scope="col" className="px-4 py-3">مشتری</th>
                <th scope="col" className="hidden px-4 py-3 md:table-cell">اولویت</th>
                <th scope="col" className="hidden px-4 py-3 lg:table-cell">آخرین فعالیت</th>
                <th scope="col" className="px-4 py-3">وضعیت</th>
                <th scope="col" className="px-4 py-3">
                  <span className="sr-only">عملیات</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading && items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-0">
                    <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin" />
                      در حال دریافت تیکت‌ها...
                    </div>
                  </td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="p-0">
                    <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
                      <Inbox className="mb-2 h-8 w-8 opacity-40" />
                      <p className="text-sm">تیکتی با این شرایط یافت نشد.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                items.map((ticket) => {
                  const statusVisual = TICKET_STATUS_VISUALS[ticket.status];
                  const priorityVisual = TICKET_PRIORITY_VISUALS[ticket.priority];
                  const stale = isTicketStale(ticket.status, ticket.updated_at);
                  return (
                    <tr
                      key={ticket.id}
                      className={cn(
                        "cursor-pointer transition-colors hover:bg-muted/30",
                        stale && "bg-amber-500/5",
                      )}
                      onClick={() => onOpenTicket(ticket)}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-foreground">
                            {ticket.ticket_number}
                          </span>
                          {stale && (
                            <span title="بیش از ۴۸ ساعت بدون تغییر">
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />
                            </span>
                          )}
                        </div>
                        <p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">
                          {ticket.subject}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-xs font-medium text-foreground">
                          {ticket.customer_name ?? "بدون نام پروفایل"}
                        </p>
                        {ticket.customer_phone && (
                          <p className="font-mono text-[11px] text-muted-foreground" dir="ltr">
                            {toPersianDigits(ticket.customer_phone)}
                          </p>
                        )}
                      </td>
                      <td className="hidden px-4 py-3 md:table-cell">
                        <Badge variant="outline" className={cn("text-[10px]", priorityVisual.chip)}>
                          {priorityVisual.label}
                        </Badge>
                      </td>
                      <td className="hidden px-4 py-3 text-xs text-muted-foreground lg:table-cell">
                        <span className="flex items-center gap-1.5">
                          <MessageSquare className="h-3.5 w-3.5" />
                          {toPersianDigits(ticket.messages_count ?? 0)} پیام
                          <span className="text-border">•</span>
                          {formatTicketRelativeTime(ticket.updated_at, toPersianDigits)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className={cn("text-[11px]", statusVisual.chip)}>
                          {statusVisual.label}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="gap-1 text-xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenTicket(ticket);
                          }}
                        >
                          گفتگو
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Pager */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-xs text-muted-foreground">
            {toPersianDigits(total)} تیکت — صفحهٔ {toPersianDigits(page + 1)} از{" "}
            {toPersianDigits(totalPages)}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 0 || loading}
              onClick={() => setPage((p) => Math.max(0, p - 1))}
            >
              قبلی
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page + 1 >= totalPages || loading}
              onClick={() => setPage((p) => p + 1)}
            >
              بعدی
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
