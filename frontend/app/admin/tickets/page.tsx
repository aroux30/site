"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Headphones, Kanban, List, Search, X } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { TicketsBoard } from "@/components/admin/tickets/tickets-board";
import { TicketsListView } from "@/components/admin/tickets/tickets-list-view";
import { TicketDetailSheet } from "@/components/admin/tickets/ticket-detail-sheet";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";
import type { TicketItem } from "@/lib/api/tickets";

/**
 * مرکز پشتیبانی و تیکت‌ها — one page, two views (list + board).
 *
 * Same shape as the unified orders page (owner order 2026-10-10: the two
 * orders pages became one; tickets follow the same pattern): the list is
 * for scanning/filtering, the board is for moving tickets through the
 * support workflow by drag & drop. The conversation drawer is shared by
 * both views.
 */

type ViewMode = "list" | "board";

const VIEW_STORAGE_KEY = "admin-tickets-view";

function TicketsPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const urlView = searchParams.get("view");
  const [view, setView] = useState<ViewMode>(urlView === "board" ? "board" : "list");
  const [search, setSearch] = useState("");
  const [openTicketId, setOpenTicketId] = useState<string | null>(null);
  // Bumped to force the board to resync after a drawer change.
  const [boardSyncToken, setBoardSyncToken] = useState(0);
  const debouncedSearch = useDebouncedValue(search, 350);

  const switchView = (next: ViewMode) => {
    setView(next);
    const params = new URLSearchParams(searchParams.toString());
    if (next === "board") params.set("view", "board");
    else params.delete("view");
    const qs = params.toString();
    router.replace(qs ? `/admin/tickets?${qs}` : "/admin/tickets", { scroll: false });
  };

  const openTicket = (ticket: TicketItem) => setOpenTicketId(ticket.id);

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
            <Headphones className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              مرکز پشتیبانی و تیکت‌ها
            </h1>
            <p className="text-xs text-muted-foreground sm:text-sm">
              مشاهده، دسته‌بندی و پاسخ‌گویی به درخواست‌های پشتیبانی (نمای لیست و کانبان)
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="relative w-full sm:w-64">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو در شماره تیکت یا موضوع..."
              className="h-9 ps-9 pe-9 text-xs sm:text-sm"
              aria-label="جستجوی تیکت"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="پاک کردن جستجو"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          <div
            role="tablist"
            aria-label="حالت نمایش تیکت‌ها"
            className="flex items-center rounded-lg border border-border bg-muted/40 p-0.5"
          >
            <button
              role="tab"
              aria-selected={view === "list"}
              type="button"
              onClick={() => switchView("list")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                view === "list"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <List className="h-3.5 w-3.5" />
              لیست
            </button>
            <button
              role="tab"
              aria-selected={view === "board"}
              type="button"
              onClick={() => switchView("board")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                view === "board"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Kanban className="h-3.5 w-3.5" />
              کانبان
            </button>
          </div>
        </div>
      </div>

      {view === "list" ? (
        <TicketsListView search={search} onSearchChange={setSearch} onOpenTicket={openTicket} />
      ) : (
        <TicketsBoard key={boardSyncToken} search={debouncedSearch} onOpenTicket={openTicket} />
      )}

      <TicketDetailSheet
        ticketId={openTicketId}
        onClose={() => setOpenTicketId(null)}
        onChanged={() => {
          if (view === "board") setBoardSyncToken((t) => t + 1);
        }}
      />
    </div>
  );
}

export default function AdminTicketsPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-64 items-center justify-center text-muted-foreground">
          در حال بارگذاری...
        </div>
      }
    >
      <TicketsPageInner />
    </Suspense>
  );
}
