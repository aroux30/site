"use client";

import React, { useState, useEffect } from "react";
import { MessageSquare, Plus, Send, AlertCircle, Loader2, ChevronDown, ChevronUp } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { fetchUserTickets, fetchUserTicketById, createUserTicket, replyUserTicket, type TicketItem, type TicketDetail } from "@/lib/api/tickets";

const statusLabels: Record<TicketItem["status"], string> = {
  open: "باز",
  in_progress: "در حال بررسی",
  waiting: "در انتظار پاسخ کاربر",
  resolved: "حل‌شده",
  closed: "بسته‌شده",
};

export default function AccountTicketsPage() {
  const [tickets, setTickets] = useState<TicketItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newSubject, setNewSubject] = useState("");
  const [newMessage, setNewMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeTicket, setActiveTicket] = useState<TicketDetail | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [replyText, setReplyText] = useState("");
  const [replySending, setReplySending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchUserTickets({ skip: page * 20, limit: 20 })
      .then((data) => {
        if (!cancelled) { setTickets(data.items); setTotal(data.total); }
      })
      .catch(() => { if (!cancelled) setError("خطا در بارگذاری تیکت‌ها. لطفاً دوباره تلاش کنید."); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, refresh]);

  useEffect(() => {
    setActiveTicket(null);
    setChatError(null);
    setReplyText("");
    setActionError(null);
    if (!expandedId) return;
    let cancelled = false;
    setChatLoading(true);
    fetchUserTicketById(expandedId)
      .then((detail) => { if (!cancelled) setActiveTicket(detail); })
      .catch(() => { if (!cancelled) setChatError("خطا در بارگذاری گفتگو. گفتگو را ببندید و دوباره باز کنید."); })
      .finally(() => { if (!cancelled) setChatLoading(false); });
    return () => { cancelled = true; };
  }, [expandedId]);

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSubject.trim() || !newMessage.trim() || submitting) return;
    setSubmitting(true);
    setActionError(null);
    try {
      await createUserTicket({ subject: newSubject.trim(), body: newMessage.trim() });
      setPage(0);
      setRefresh((value) => value + 1);
      setShowNewForm(false);
      setNewSubject("");
      setNewMessage("");
    } catch {
      setActionError("خطا در ثبت تیکت جدید. لطفاً دوباره تلاش کنید.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleSendReply = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!expandedId || activeTicket?.id !== expandedId || !replyText.trim() || replySending) return;
    const ticketId = expandedId;
    setReplySending(true);
    setActionError(null);
    try {
      const msg = await replyUserTicket(ticketId, replyText.trim());
      setActiveTicket((prev) => prev?.id === ticketId ? {
        ...prev,
        status: prev.status === "waiting" ? "in_progress" : prev.status,
        messages: [...prev.messages, msg],
      } : prev);
      setTickets((prev) => prev.map((ticket) => ticket.id === ticketId && ticket.status === "waiting"
        ? { ...ticket, status: "in_progress" } : ticket));
      setReplyText("");
    } catch {
      setActionError("خطا در ارسال پیام. لطفاً دوباره تلاش کنید.");
    } finally {
      setReplySending(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-foreground">تیکت‌های پشتیبانی</h1>
          <p className="text-sm text-muted-foreground">پیگیری درخواست‌ها و ارتباط مستقیم با کارشناسان پشتیبانی</p>
        </div>
        <Button onClick={() => setShowNewForm(!showNewForm)} className="gap-2" size="sm" disabled={submitting}>
          <Plus className="h-4 w-4" />{showNewForm ? "بستن فرم" : "ثبت تیکت جدید"}
        </Button>
      </div>
      {actionError && <div role="alert" className="rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">{actionError}</div>}
      {showNewForm && (
        <Card className="p-6 border-primary/20">
          <h2 className="mb-4 text-base font-bold text-foreground">ثبت درخواست پشتیبانی جدید</h2>
          <form onSubmit={handleCreateTicket} className="space-y-4">
            <div className="space-y-2">
              <label htmlFor="ticket-subject" className="text-xs font-medium text-foreground">موضوع تیکت</label>
              <Input id="ticket-subject" value={newSubject} onChange={(e) => setNewSubject(e.target.value)} placeholder="عنوان خلاصه درخواست..." maxLength={500} required disabled={submitting} />
            </div>
            <div className="space-y-2">
              <label htmlFor="ticket-body" className="text-xs font-medium text-foreground">متن پیام و توضیحات</label>
              <Textarea id="ticket-body" value={newMessage} onChange={(e) => setNewMessage(e.target.value)} placeholder="توضیحات کامل درخواست خود را بنویسید..." rows={4} required disabled={submitting} />
            </div>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setShowNewForm(false)} disabled={submitting}>انصراف</Button>
              <Button type="submit" size="sm" disabled={submitting || !newSubject.trim() || !newMessage.trim()} className="gap-2">
                {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}ارسال تیکت
              </Button>
            </div>
          </form>
        </Card>
      )}
      {loading ? (
        <div role="status" className="flex h-48 items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" /><span className="ms-2 text-sm text-muted-foreground">در حال دریافت تیکت‌ها...</span>
        </div>
      ) : error ? (
        <div role="alert" className="flex flex-wrap items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" />{error}
          <Button variant="outline" size="sm" onClick={() => setRefresh((value) => value + 1)}>تلاش دوباره</Button>
        </div>
      ) : tickets.length === 0 ? (
        <Card className="p-8 text-center">
          <MessageSquare className="mx-auto h-12 w-12 text-muted-foreground/50 mb-3" />
          <h3 className="text-base font-bold text-foreground">هیچ تیکتی ثبت نشده است</h3>
          <p className="text-xs text-muted-foreground mt-1 mb-4">در صورت وجود هرگونه ابهام یا مشکل، می‌توانید تیکت جدید ثبت کنید.</p>
          <Button size="sm" onClick={() => setShowNewForm(true)}>ثبت تیکت جدید</Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {tickets.map((ticket) => {
            const isExpanded = expandedId === ticket.id;
            const conversation = activeTicket?.id === ticket.id ? activeTicket : null;
            return (
              <Card key={ticket.id} className="overflow-hidden">
                <button type="button" aria-expanded={isExpanded} disabled={replySending}
                  onClick={() => setExpandedId(isExpanded ? null : ticket.id)}
                  className="flex w-full flex-col sm:flex-row sm:items-center justify-between p-4 text-start hover:bg-muted/40 transition-colors gap-3 disabled:opacity-60">
                  <span className="space-y-1 min-w-0">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground text-sm break-words">{ticket.subject}</span>
                      <Badge variant="outline">{statusLabels[conversation?.status ?? ticket.status]}</Badge>
                    </span>
                    <span className="text-xs text-muted-foreground flex flex-wrap items-center gap-2">
                      <span className="break-all">{ticket.ticket_number}</span><span>•</span>
                      <span>{new Date(ticket.created_at).toLocaleDateString("fa-IR")}</span>
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1 text-xs">
                    {isExpanded ? <>بستن گفتگو <ChevronUp className="h-4 w-4" /></> : <>مشاهده گفتگو <ChevronDown className="h-4 w-4" /></>}
                  </span>
                </button>
                {isExpanded && (
                  <div className="border-t border-border bg-muted/20 p-4 space-y-4">
                    {chatLoading ? (
                      <div role="status" className="flex items-center justify-center py-6 text-sm text-muted-foreground"><Loader2 className="h-5 w-5 animate-spin me-2" />در حال بارگذاری گفتگو...</div>
                    ) : chatError ? (
                      <p role="alert" className="text-sm text-destructive">{chatError}</p>
                    ) : conversation ? (
                      <>
                        <div className="space-y-3 max-h-80 overflow-y-auto p-1">
                          {conversation.messages.map((msg) => (
                            <div key={msg.id} className={`flex ${msg.is_staff ? "justify-end" : "justify-start"}`}>
                              <div className={`max-w-[85%] rounded-2xl p-3 text-xs shadow-sm ${msg.is_staff ? "bg-card text-foreground border border-border rounded-tl-none" : "bg-primary/10 text-foreground border border-primary/20 rounded-tr-none"}`}>
                                <div className="font-bold mb-1 text-[11px] text-muted-foreground">{msg.is_staff ? "کارشناس پشتیبانی" : "شما"}</div>
                                <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.body}</p>
                              </div>
                            </div>
                          ))}
                        </div>
                        {conversation.status !== "closed" ? (
                          <form onSubmit={handleSendReply} className="flex gap-2 pt-2">
                            <Input aria-label="متن پاسخ" value={replyText} onChange={(e) => setReplyText(e.target.value)} placeholder="پیام خود را بنویسید..." className="text-xs" disabled={replySending} required />
                            <Button type="submit" size="sm" disabled={replySending || !replyText.trim()} className="shrink-0 gap-1.5">
                              {replySending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}ارسال
                            </Button>
                          </form>
                        ) : <div className="text-center text-xs text-muted-foreground py-2">این تیکت بسته‌شده است.</div>}
                      </>
                    ) : null}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
      {!error && total > 20 && (
        <nav aria-label="صفحه‌بندی تیکت‌ها" className="flex items-center justify-center gap-3">
          <Button variant="outline" size="sm" disabled={loading || replySending || page === 0} onClick={() => { setExpandedId(null); setPage(page - 1); }}>قبلی</Button>
          <span className="text-xs">صفحه {(page + 1).toLocaleString("fa-IR")} از {Math.ceil(total / 20).toLocaleString("fa-IR")}</span>
          <Button variant="outline" size="sm" disabled={loading || replySending || (page + 1) * 20 >= total} onClick={() => { setExpandedId(null); setPage(page + 1); }}>بعدی</Button>
        </nav>
      )}
    </div>
  );
}
