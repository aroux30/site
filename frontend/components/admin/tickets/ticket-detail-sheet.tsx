"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  MessageSquare,
  Phone,
  RefreshCw,
  Send,
  Shield,
  User,
} from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { cn, toPersianDigits } from "@/lib/utils";
import {
  TICKET_PRIORITY_VISUALS,
  TICKET_STATUS_VISUALS,
  TICKET_TRANSITIONS,
  isTicketStale,
  type TicketStatus,
} from "@/lib/admin/ticket-domain";
import {
  fetchAdminTicketById,
  replyAdminTicket,
  updateAdminTicketStatus,
  type TicketDetail,
} from "@/lib/api/tickets";
import { apiErrorMessage } from "@/lib/api/error-message";

/**
 * The ticket conversation drawer (side sheet).
 *
 * Loads the admin detail endpoint (messages + customer identity — the old
 * detail page rendered a raw user UUID). Status buttons offer exactly the
 * UI-policy transitions; the reply form is hidden for closed tickets
 * (the backend refuses messages on closed tickets with a 400 — the form
 * used to be shown anyway and the failure surfaced as a generic error).
 */

export interface TicketDetailSheetProps {
  ticketId: string | null;
  onClose: () => void;
  /** Fired after a successful status change or reply, so the caller resyncs. */
  onChanged: () => void;
}

export function TicketDetailSheet({ ticketId, onClose, onChanged }: TicketDetailSheetProps) {
  const { toast } = useToast();
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [changingTo, setChangingTo] = useState<TicketStatus | null>(null);
  const [replyText, setReplyText] = useState("");
  const [sending, setSending] = useState(false);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!ticketId) {
      setDetail(null);
      setLoadError(null);
      setReplyText("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    fetchAdminTicketById(ticketId)
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(apiErrorMessage(err, "گفتگوی تیکت دریافت نشد."));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId]);

  // Scroll to the newest message when the thread loads.
  useEffect(() => {
    if (detail && threadEndRef.current) {
      threadEndRef.current.scrollIntoView({ block: "nearest" });
    }
  }, [detail]);

  const allowedNext = useMemo(() => {
    if (!detail) return [] as TicketStatus[];
    return TICKET_TRANSITIONS[detail.status] ?? [];
  }, [detail]);

  const handleTransition = async (target: TicketStatus) => {
    if (!detail) return;
    setChangingTo(target);
    try {
      await updateAdminTicketStatus(detail.id, target);
      toast({
        title: "وضعیت تیکت تغییر کرد",
        description: `تیکت ${detail.ticket_number} به «${TICKET_STATUS_VISUALS[target].label}» منتقل شد.`,
        variant: "success",
      });
      const fresh = await fetchAdminTicketById(detail.id);
      setDetail(fresh);
      onChanged();
    } catch (err) {
      toast({
        title: "تغییر وضعیت ناموفق بود",
        description: apiErrorMessage(err, "سرور این تغییر را نپذیرفت."),
        variant: "destructive",
      });
    } finally {
      setChangingTo(null);
    }
  };

  const handleSendReply = async () => {
    if (!detail || !replyText.trim() || sending) return;
    setSending(true);
    try {
      await replyAdminTicket(detail.id, replyText.trim());
      const fresh = await fetchAdminTicketById(detail.id);
      setDetail(fresh);
      setReplyText("");
      toast({
        title: "پاسخ ارسال شد",
        description: "پاسخ کارشناس در گفتگو ثبت شد و به کاربر اطلاع داده می‌شود.",
        variant: "success",
      });
      onChanged();
    } catch (err) {
      toast({
        title: "ارسال پاسخ ناموفق بود",
        description: apiErrorMessage(err, "خطا در ارسال پاسخ."),
        variant: "destructive",
      });
    } finally {
      setSending(false);
    }
  };

  const sortedMessages = useMemo(() => {
    if (!detail) return [];
    return [...(detail.messages ?? [])].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
    );
  }, [detail]);

  const statusVisual = detail ? TICKET_STATUS_VISUALS[detail.status] : null;
  const priorityVisual = detail ? TICKET_PRIORITY_VISUALS[detail.priority] : null;
  const stale = detail ? isTicketStale(detail.status, detail.updated_at) : false;

  return (
    <Sheet open={Boolean(ticketId)} onOpenChange={(open) => !open && onClose()}>
      <SheetContent
        side="left"
        className="flex w-full flex-col overflow-hidden sm:max-w-2xl"
        dir="rtl"
        aria-describedby={undefined}
      >
        <SheetHeader className="shrink-0 text-right">
          <SheetTitle className="flex flex-wrap items-center gap-2">
            {detail ? (
              <>
                <span className="font-mono">{detail.ticket_number}</span>
                {statusVisual && (
                  <Badge variant="outline" className={cn("text-xs", statusVisual.chip)}>
                    {statusVisual.label}
                  </Badge>
                )}
                {priorityVisual && (
                  <Badge variant="outline" className={cn("text-xs", priorityVisual.chip)}>
                    {priorityVisual.label}
                  </Badge>
                )}
              </>
            ) : (
              "گفتگوی تیکت"
            )}
          </SheetTitle>
          <SheetDescription>{detail?.subject ?? "مشاهدهٔ گفتگو و پاسخ‌دهی به کاربر"}</SheetDescription>
        </SheetHeader>

        {loading && (
          <div className="flex min-h-48 flex-1 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {loadError && !loading && (
          <div
            role="alert"
            className="mt-4 flex items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
          >
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {loadError}
          </div>
        )}

        {detail && !loading && (
          <>
            {/* Scrollable middle: customer + transitions + thread */}
            <div className="min-h-0 flex-1 space-y-4 overflow-y-auto py-4">
              {stale && (
                <div className="flex items-center gap-2 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-xs font-medium text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  بیش از ۴۸ ساعت است که تغییری در این تیکت ثبت نشده — نیازمند پیگیری.
                </div>
              )}

              {/* Customer identity */}
              <div className="rounded-2xl border border-border p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-sm font-bold text-foreground">
                    <User className="h-4 w-4 text-primary" />
                    {detail.customer_name ?? "بدون نام پروفایل"}
                  </span>
                  {detail.customer_phone && (
                    <span className="flex items-center gap-1.5 font-mono text-xs text-muted-foreground" dir="ltr">
                      <Phone className="h-3 w-3" />
                      {toPersianDigits(detail.customer_phone)}
                    </span>
                  )}
                </div>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  تاریخ ثبت: {new Date(detail.created_at).toLocaleString("fa-IR")}
                </p>
              </div>

              {/* Transitions */}
              {allowedNext.length > 0 && (
                <div className="rounded-2xl border border-border p-4">
                  <h3 className="mb-3 text-sm font-bold text-foreground">تغییر وضعیت</h3>
                  <div className="flex flex-wrap gap-2">
                    {allowedNext
                      .slice()
                      .sort((a, b) => a.localeCompare(b))
                      .map((target) => (
                        <Button
                          key={target}
                          size="sm"
                          variant="outline"
                          disabled={changingTo !== null}
                          onClick={() => void handleTransition(target)}
                          className={cn("gap-1.5 text-xs", TICKET_STATUS_VISUALS[target].chip)}
                        >
                          {changingTo === target ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          )}
                          {TICKET_STATUS_VISUALS[target].label}
                        </Button>
                      ))}
                  </div>
                </div>
              )}

              {/* Thread */}
              <div className="space-y-3">
                <h3 className="flex items-center gap-2 text-sm font-bold text-foreground">
                  <MessageSquare className="h-4 w-4 text-primary" />
                  گفتگو ({toPersianDigits(sortedMessages.length)} پیام)
                </h3>
                {sortedMessages.length === 0 ? (
                  <p className="rounded-xl border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                    پیامی ثبت نشده است.
                  </p>
                ) : (
                  sortedMessages.map((msg) => {
                    const isStaff = msg.is_staff;
                    return (
                      <div key={msg.id} className={cn("flex gap-3", isStaff ? "justify-start" : "justify-end")}>
                        <div
                          className={cn(
                            "max-w-[85%] rounded-2xl p-3.5 shadow-sm sm:max-w-[75%]",
                            isStaff
                              ? "rounded-tr-none border border-primary/20 bg-primary/5"
                              : "rounded-tl-none border border-border bg-card",
                          )}
                        >
                          <div className="mb-1.5 flex items-center justify-between gap-4 border-b border-border/40 pb-1.5">
                            <span className="flex items-center gap-1.5 text-xs font-bold">
                              {isStaff ? (
                                <>
                                  <Shield className="h-3.5 w-3.5 text-primary" />
                                  <span className="text-primary">پشتیبانی سایت</span>
                                </>
                              ) : (
                                <>
                                  <User className="h-3.5 w-3.5 text-muted-foreground" />
                                  <span>{detail.customer_name ?? "کاربر"}</span>
                                </>
                              )}
                            </span>
                            <span className="text-[10px] text-muted-foreground">
                              {new Date(msg.created_at).toLocaleString("fa-IR")}
                            </span>
                          </div>
                          <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.body}</p>
                        </div>
                      </div>
                    );
                  })
                )}
                <div ref={threadEndRef} />
              </div>
            </div>

            {/* Fixed reply composer */}
            <div className="shrink-0 border-t border-border pt-4">
              {detail.status === "closed" ? (
                <p className="rounded-xl bg-muted/40 px-4 py-3 text-center text-xs text-muted-foreground">
                  این تیکت بسته شده است؛ برای پاسخ‌دهی ابتدا آن را بازگشایی کنید.
                </p>
              ) : (
                <div className="space-y-2">
                  <Textarea
                    aria-label="پاسخ کارشناس"
                    disabled={sending || changingTo !== null}
                    value={replyText}
                    onChange={(e) => setReplyText(e.target.value)}
                    placeholder="پاسخ کارشناس پشتیبانی به کاربر..."
                    rows={3}
                    className="resize-none text-sm"
                  />
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="sm"
                      disabled={sending || changingTo !== null || !replyText.trim()}
                      onClick={() => void handleSendReply()}
                      className="gap-2"
                    >
                      {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      ارسال پاسخ
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
