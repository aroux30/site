"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ChevronRight,
  Send,
  User,
  Shield,
  Clock,
  CheckCircle2,
  AlertCircle,
  Loader2,
  RefreshCw,
  ArrowRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import { apiErrorMessage } from "@/lib/api/error-message";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  fetchAdminTicketById,
  replyAdminTicket,
  updateAdminTicketStatus,
  type TicketDetail,
  type TicketMessage,
} from "@/lib/api/tickets";

export default function AdminTicketDetailPage() {
  const params = useParams();
  const ticketId = params.id as string;

  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: ticket = null,
    loading,
    error,
    reload: loadTicket,
  } = useAdminQuery<TicketDetail | null>({
    queryKey: ["admin", "tickets", ticketId],
    enabled: Boolean(ticketId),
    queryFn: async () => {
      const data = await fetchAdminTicketById(ticketId);
      if (!data) throw new Error("تیکت مورد نظر یافت نشد.");
      return data;
    },
    fallbackError: "خطا در بارگذاری اطلاعات تیکت. لطفاً صفحه را مجدداً بارگذاری کنید.",
  });

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!replyText.trim() || sending) return;

    setSending(true);
    setActionError(null);
    try {
      await replyAdminTicket(ticketId, replyText.trim());
      await loadTicket();
      setReplyText("");
    } catch {
      setActionError("خطا در ارسال پاسخ. لطفاً دوباره تلاش کنید.");
    } finally {
      setSending(false);
    }
  };

  const handleStatusChange = async (newStatus: TicketDetail["status"]) => {
    if (!ticket || statusUpdating) return;
    setStatusUpdating(true);
    setActionError(null);
    try {
      await updateAdminTicketStatus(ticketId, newStatus);
      await loadTicket();
    } catch {
      setActionError("خطا در تغییر وضعیت تیکت.");
    } finally {
      setStatusUpdating(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ms-2 text-sm text-muted-foreground">در حال بارگذاری گفتگو...</span>
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="space-y-4">
        <Link href="/admin/tickets" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowRight className="h-4 w-4" /> بازگشت به لیست تیکت‌ها
        </Link>
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-destructive">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <span>{error || "تیکت یافت نشد."}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Link href="/admin/tickets" className="hover:text-foreground">
            تیکت‌ها
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span className="font-medium text-foreground">گفتگوی تیکت #{ticket.id.slice(0, 8)}</span>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={loadTicket} disabled={loading} className="gap-1 text-xs">
            <RefreshCw className="h-3.5 w-3.5" /> به‌روزرسانی
          </Button>
          <Link href="/admin/tickets">
            <Button variant="ghost" size="sm" className="gap-1 text-xs">
              <ArrowRight className="h-3.5 w-3.5" /> بازگشت
            </Button>
          </Link>
        </div>
      </div>

      {/* Ticket Overview Card */}
      <Card className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border pb-4">
          <div>
            <h1 className="text-xl font-bold text-foreground">{ticket.subject}</h1>
            <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-muted-foreground">
              <span className="break-all">شماره تیکت: {ticket.ticket_number}</span>
              <span>•</span>
              <span className="break-all">شناسه کاربر: {ticket.user_id}</span>
              <span>•</span>
              <span>
                تاریخ ثبت:{" "}
                {ticket.created_at
                  ? new Date(ticket.created_at).toLocaleDateString("fa-IR", {
                      year: "numeric",
                      month: "long",
                      day: "numeric",
                    })
                  : "—"}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">تغییر وضعیت:</span>
            <select
              value={ticket.status}
              aria-label="وضعیت تیکت"
              disabled={statusUpdating || sending}
              onChange={(e) => handleStatusChange(e.target.value as TicketDetail["status"])}
              className="h-9 rounded-md border border-input bg-background px-2.5 py-1 text-xs ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="open">باز</option>
              <option value="in_progress">در حال بررسی</option>
              <option value="waiting">در انتظار پاسخ کاربر</option>
              <option value="resolved">حل‌شده</option>
              <option value="closed">بسته‌شده</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Messages Thread */}
      <div className="space-y-4">
        {(!ticket.messages || ticket.messages.length === 0) ? (
          <Card className="p-8 text-center text-muted-foreground text-sm">
            پیامی در این تیکت ثبت نشده است.
          </Card>
        ) : (
          ticket.messages.map((msg) => {
            const isAdmin = msg.is_staff;
            return (
              <div
                key={msg.id}
                className={`flex gap-3 ${isAdmin ? "justify-start" : "justify-end"}`}
              >
                <div
                  className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-4 shadow-sm ${
                    isAdmin
                      ? "border border-primary/20 bg-primary/5 text-foreground rounded-tr-none"
                      : "border border-border bg-card text-foreground rounded-tl-none"
                  }`}
                >
                  <div className="mb-2 flex items-center justify-between gap-4 border-b border-border/40 pb-1.5">
                    <div className="flex items-center gap-1.5 text-xs font-bold">
                      {isAdmin ? (
                        <>
                          <Shield className="h-3.5 w-3.5 text-primary" />
                          <span className="text-primary">پشتیبانی سایت</span>
                        </>
                      ) : (
                        <>
                          <User className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>کاربر</span>
                        </>
                      )}
                    </div>
                    <span className="text-[10px] text-muted-foreground" dir="ltr">
                      {msg.created_at
                        ? new Date(msg.created_at).toLocaleTimeString("fa-IR", {
                            hour: "2-digit",
                            minute: "2-digit",
                          })
                        : ""}
                    </span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.body}</p>
                </div>
              </div>
            );
          })
        )}
      </div>

      {actionError && <p role="alert" className="text-sm text-destructive">{actionError}</p>}

      {/* Reply Form */}
      {ticket.status !== "closed" ? (
        <Card className="p-4">
          <form onSubmit={handleSendReply} className="space-y-3">
            <Textarea
              aria-label="پاسخ کارشناس"
              disabled={sending || statusUpdating}
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="پاسخ کارشناس پشتیبانی به کاربر..."
              rows={3}
              className="resize-none text-sm"
            />
            <div className="flex justify-end">
              <Button type="submit" size="sm" disabled={sending || statusUpdating || !replyText.trim()} className="gap-2">
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                ارسال پاسخ به کاربر
              </Button>
            </div>
          </form>
        </Card>
      ) : (
        <Card className="p-4 text-center text-xs text-muted-foreground bg-muted/30">
          این تیکت بسته‌شده است. برای ارسال پاسخ ابتدا وضعیت آن را تغییر دهید.
        </Card>
      )}
    </div>
  );
}
