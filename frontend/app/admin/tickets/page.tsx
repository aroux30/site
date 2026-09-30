"use client";

import { useState } from "react";
import Link from "next/link";
import { Search, Filter, ChevronLeft, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { fetchAdminTickets, type TicketItem } from "@/lib/api/tickets";
import { useAdminQuery } from "@/lib/api/admin-query";

const TICKETS_QUERY_KEY = "admin-tickets" as const;

const statusLabels: Record<TicketItem["status"], string> = {
  open: "باز", in_progress: "در حال بررسی", waiting: "در انتظار پاسخ کاربر", resolved: "حل‌شده", closed: "بسته‌شده",
};
const priorityLabels: Record<TicketItem["priority"], string> = {
  urgent: "فوری و بحرانی", high: "بالا", medium: "متوسط", low: "پایین",
};

export default function AdminTicketsPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<TicketItem["status"] | "all">("all");
  const [page, setPage] = useState(0);

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [TICKETS_QUERY_KEY, statusFilter, page],
    queryFn: () => fetchAdminTickets({ status: statusFilter === "all" ? undefined : statusFilter, skip: page * 20, limit: 20 }),
    fallbackError: "خطا در دریافت لیست تیکت‌ها. لطفاً دوباره تلاش کنید.",
  });
  const tickets: TicketItem[] = data?.items ?? [];
  const total = data?.total ?? 0;

  const filteredTickets = tickets.filter((ticket) => {
    const term = search.toLowerCase().trim();
    return !term || [ticket.subject, ticket.ticket_number, ticket.user_id].some((value) => value.toLowerCase().includes(term));
  });

  const columns: DataTableColumn<TicketItem>[] = [
    {
      key: "subject", header: "موضوع تیکت", render: (ticket) => (
        <div>
          <Link href={`/admin/tickets/${ticket.id}`} className="font-semibold text-foreground hover:text-primary transition-colors">{ticket.subject}</Link>
          <div className="text-xs text-muted-foreground mt-0.5 break-all">{ticket.ticket_number}</div>
        </div>
      ),
    },
    { key: "user", header: "شناسه کاربر", render: (ticket) => <span dir="ltr" className="text-xs break-all">{ticket.user_id}</span> },
    { key: "status", header: "وضعیت", render: (ticket) => <Badge variant="outline">{statusLabels[ticket.status]}</Badge> },
    { key: "priority", header: "اولویت", render: (ticket) => <Badge variant={ticket.priority === "urgent" ? "destructive" : "outline"}>{priorityLabels[ticket.priority]}</Badge> },
    {
      key: "date", header: "تاریخ ثبت", className: "text-xs text-muted-foreground",
      render: (ticket) => new Date(ticket.created_at).toLocaleDateString("fa-IR"),
    },
    {
      key: "actions", header: <span className="sr-only">مشاهده</span>, className: "text-center",
      render: (ticket) => <Link href={`/admin/tickets/${ticket.id}`} className="inline-flex items-center gap-1 text-xs">مشاهده گفتگو<ChevronLeft className="h-3.5 w-3.5" /></Link>,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مرکز پشتیبانی و تیکت‌ها</h1>
          <p className="text-sm text-muted-foreground">مشاهده، دسته‌بندی و پاسخ‌گویی به درخواست‌های پشتیبانی کاربران</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading} className="gap-2">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />به‌روزرسانی
        </Button>
      </div>
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input aria-label="جستجو در تیکت‌های صفحه جاری" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="جستجو در این صفحه: موضوع، شماره تیکت یا شناسه کاربر..." className="ps-9" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select aria-label="فیلتر وضعیت" value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value as typeof statusFilter); setPage(0); }} className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm">
              <option value="all">همه وضعیت‌ها</option>
              {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </div>
        </div>
      </Card>
      <DataTable<TicketItem> columns={columns} rows={filteredTickets} rowKey={(ticket) => ticket.id} loading={loading} error={error} emptyMessage="هیچ تیکتی با این فیلتر در این صفحه یافت نشد." />
      {!error && total > 20 && (
        <nav aria-label="صفحه‌بندی تیکت‌ها" className="flex items-center justify-center gap-3">
          <Button variant="outline" size="sm" disabled={loading || page === 0} onClick={() => setPage(page - 1)}>قبلی</Button>
          <span className="text-xs">صفحه {(page + 1).toLocaleString("fa-IR")} از {Math.ceil(total / 20).toLocaleString("fa-IR")}</span>
          <Button variant="outline" size="sm" disabled={loading || (page + 1) * 20 >= total} onClick={() => setPage(page + 1)}>بعدی</Button>
        </nav>
      )}
    </div>
  );
}
