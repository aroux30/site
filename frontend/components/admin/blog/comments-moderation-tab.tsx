"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  MessageSquare,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  RefreshCw,
  Clock,
  User,
  CornerDownLeft,
  ExternalLink,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toPersianDigits } from "@/lib/utils";
import {
  blogAdminApi,
  submitPostComment,
  type BlogComment,
  type CommentStatus,
} from "@/lib/api/blog";

const commentStatusMeta: Record<CommentStatus, { label: string; className: string }> = {
  approved: { label: "تأیید شده", className: "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" },
  pending: { label: "در انتظار بررسی", className: "bg-amber-500/10 text-amber-600 border-amber-500/20" },
  spam: { label: "اسپم / جفنگ", className: "bg-rose-500/10 text-rose-600 border-rose-500/20" },
  trash: { label: "زباله‌دان", className: "bg-muted text-muted-foreground border-border" },
};

export function CommentsModerationTab() {
  const { toast } = useToast();
  const [comments, setComments] = useState<BlogComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<CommentStatus | "all">("all");
  const [total, setTotal] = useState(0);

  // Reply dialog
  const [replyDialogOpen, setReplyDialogOpen] = useState(false);
  const [replyTarget, setReplyTarget] = useState<BlogComment | null>(null);
  const [replyContent, setReplyContent] = useState("");
  const [replying, setReplying] = useState(false);

  useEffect(() => {
    loadComments();
  }, [statusFilter]);

  const loadComments = async () => {
    setLoading(true);
    try {
      const data = await blogAdminApi.listComments({
        status: statusFilter === "all" ? undefined : statusFilter,
        page_size: 50,
      });
      setComments(data.items || []);
      setTotal(data.total || 0);
    } catch {
      toast({
        title: "خطا در دریافت دیدگاه‌ها",
        description: "اتصال به سرویس برقرار نشد.",
        variant: "destructive",
      });
      setComments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await blogAdminApi.approveComment(id);
      toast({ title: "دیدگاه تأیید شد" });
      await loadComments();
    } catch {
      toast({ title: "تأیید دیدگاه ناموفق بود", variant: "destructive" });
    }
  };

  const handleSpam = async (id: string) => {
    try {
      await blogAdminApi.spamComment(id);
      toast({ title: "دیدگاه به عنوان اسپم علامت‌گذاری شد" });
      await loadComments();
    } catch {
      toast({ title: "عملیات ناموفق بود", variant: "destructive" });
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("این دیدگاه حذف شود؟")) return;
    try {
      await blogAdminApi.deleteComment(id);
      toast({ title: "دیدگاه حذف شد" });
      await loadComments();
    } catch {
      toast({ title: "حذف دیدگاه ناموفق بود", variant: "destructive" });
    }
  };

  const openReply = (comment: BlogComment) => {
    setReplyTarget(comment);
    setReplyContent("");
    setReplyDialogOpen(true);
  };

  const handleSendReply = async () => {
    if (!replyTarget || !replyContent.trim()) return;
    setReplying(true);
    try {
      await submitPostComment(replyTarget.post_id, {
        content: replyContent.trim(),
        parent_id: replyTarget.id,
        author_name: "مدیریت سایت",
      });
      toast({ title: "پاسخ دیدگاه ارسال و ثبت شد" });
      setReplyDialogOpen(false);
      await loadComments();
    } catch {
      toast({ title: "ارسال پاسخ ناموفق بود", variant: "destructive" });
    } finally {
      setReplying(false);
    }
  };

  const columns: DataTableColumn<BlogComment>[] = [
    {
      key: "author",
      header: "نویسنده",
      className: "font-medium text-foreground",
      render: (c) => (
        <div>
          <div className="flex items-center gap-1.5 font-bold text-sm">
            <User className="h-3.5 w-3.5 text-muted-foreground" />
            <span>{c.author_name || "کاربر مهمان"}</span>
          </div>
          {c.author_email && (
            <div className="text-xs text-muted-foreground dir-ltr text-right mt-0.5">
              {c.author_email}
            </div>
          )}
        </div>
      ),
    },
    {
      key: "content",
      header: "متن دیدگاه",
      className: "text-sm",
      render: (c) => (
        <div className="space-y-1 max-w-md">
          <p className="line-clamp-2 text-foreground/90 whitespace-pre-wrap">{c.content}</p>
          {c.parent_id && (
            <Badge variant="outline" className="text-[10px] text-muted-foreground">
              در پاسخ به دیدگاهی دیگر
            </Badge>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (c) => {
        const meta = commentStatusMeta[c.status] || {
          label: c.status,
          className: "bg-muted text-muted-foreground",
        };
        return (
          <Badge variant="outline" className={`text-xs ${meta.className}`}>
            {meta.label}
          </Badge>
        );
      },
    },
    {
      key: "created_at",
      header: "تاریخ ثبت",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (c) =>
        toPersianDigits(
          new Date(c.created_at).toLocaleDateString("fa-IR", {
            year: "numeric",
            month: "short",
            day: "numeric",
          }),
        ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-center",
      render: (c) => (
        <div className="flex items-center justify-center gap-1.5 flex-wrap">
          {c.status !== "approved" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleApprove(c.id)}
              className="h-8 gap-1 text-xs text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/20"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              تأیید
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => openReply(c)}
            className="h-8 gap-1 text-xs"
          >
            <CornerDownLeft className="h-3.5 w-3.5" />
            پاسخ
          </Button>
          {c.status !== "spam" && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleSpam(c.id)}
              className="h-8 gap-1 text-xs text-amber-600 hover:text-amber-700"
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              اسپم
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDelete(c.id)}
            className="h-8 gap-1 text-xs text-destructive hover:bg-destructive/10"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <MessageSquare className="h-5 w-5 text-emerald-600" />
            <span className="font-bold text-sm text-foreground">
              مدیریت دیدگاه‌ها ({toPersianDigits(String(total))})
            </span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value as CommentStatus | "all")}
              className="h-9 rounded-md border border-input bg-background px-3 text-xs"
            >
              <option value="all">همه وضعیت‌ها</option>
              <option value="pending">در انتظار بررسی</option>
              <option value="approved">تأیید شده</option>
              <option value="spam">اسپم / جفنگ</option>
              {/* No trash option: nothing in the codebase ever writes
                  CommentStatus.TRASH, so this filter could only ever return an
                  empty list. Add the option back when a moderation trash path
                  exists. */}
            </select>
            <Button variant="outline" size="sm" onClick={loadComments} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </Card>

      <DataTable<BlogComment>
        columns={columns}
        rows={comments}
        rowKey={(c) => c.id}
        emptyMessage={loading ? "در حال بارگذاری..." : "دیدگاهی یافت نشد."}
      />

      {/* Reply Dialog */}
      <Dialog open={replyDialogOpen} onOpenChange={setReplyDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>پاسخ به دیدگاه {replyTarget?.author_name || "کاربر"}</DialogTitle>
            <DialogDescription>
              دیدگاه مرجع: «{replyTarget?.content.slice(0, 100)}...»
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <Textarea
              value={replyContent}
              onChange={(e) => setReplyContent(e.target.value)}
              placeholder="متن پاسخ مدیریت..."
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReplyDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={handleSendReply} disabled={replying || !replyContent.trim()}>
              {replying ? "در حال ارسال..." : "ارسال پاسخ"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
