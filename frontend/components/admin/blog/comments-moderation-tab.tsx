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
  StickyNote,
  Pencil,
  Undo2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  commentTarget,
  submitResourceComment,
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
  // The row the j/k shortcuts have moved to. Kept as an index rather than an
  // id so paging and refiltering do not leave it pointing at a row that is no
  // longer on screen; it is clamped on every use.
  const [focusIndex, setFocusIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<CommentStatus | "all">("all");
  // Omitted shows both, which is what a moderator wants by default: a note is
  // in the same table, styled apart, and narrowing to one is a deliberate act.
  const [typeFilter, setTypeFilter] = useState<"comment" | "note" | undefined>(undefined);
  const [total, setTotal] = useState(0);
  // Server-side paging. The tab used to fetch a fixed 50 rows and page
  // over those, so comment 51 onward was unreachable.
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const PAGE_SIZE = 50;

  // Edit dialog: the body, the author fields, and the status in one
  // place. A moderator correcting a name or a spam address has no
  // other route to it.
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<BlogComment | null>(null);
  const [editContent, setEditContent] = useState("");
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [editUrl, setEditUrl] = useState("");
  const [editStatus, setEditStatus] = useState<CommentStatus>("approved");
  const [editSaving, setEditSaving] = useState(false);

  // Private note
  const [noteDialogOpen, setNoteDialogOpen] = useState(false);
  const [noteTarget, setNoteTarget] = useState<BlogComment | null>(null);
  const [noteContent, setNoteContent] = useState("");
  const [noting, setNoting] = useState(false);

  // Reply dialog
  const [replyDialogOpen, setReplyDialogOpen] = useState(false);
  const [replyTarget, setReplyTarget] = useState<BlogComment | null>(null);
  const [replyContent, setReplyContent] = useState("");
  const [replying, setReplying] = useState(false);

  useEffect(() => {
    loadComments();
  }, [statusFilter, typeFilter, page, search]);

  // WordPress-style keyboard shortcuts:
  //   j / k       navigate rows (next / prev)
  //   a           approve
  //   u           unapprove (back to pending)
  //   s           mark spam
  //   t           trash
  //   d           delete (with confirmation)
  //   e           edit
  //   ?           show help toast
  //
  // Inactive while the user is typing in an input, textarea or contentEditable:
  // typing "just a note" would otherwise approve, trash and unapprove the row
  // under the cursor on the letters j, t, a, u.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable)
      ) {
        return;
      }
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (comments.length === 0) return;

      const idx = Math.max(0, Math.min(focusIndex, comments.length - 1));
      const current = comments[idx];
      if (!current) return;

      switch (e.key) {
        case "j":
          e.preventDefault();
          setFocusIndex((prev) => Math.min(comments.length - 1, prev + 1));
          break;
        case "k":
          e.preventDefault();
          setFocusIndex((prev) => Math.max(0, prev - 1));
          break;
        case "a":
          e.preventDefault();
          void runBulk("approve", [current]);
          break;
        case "u":
          e.preventDefault();
          void runBulk("unapprove", [current]);
          break;
        case "s":
          e.preventDefault();
          void runBulk("spam", [current]);
          break;
        case "t":
          e.preventDefault();
          void runBulk("trash", [current]);
          break;
        case "e":
          e.preventDefault();
          openEdit(current);
          break;
        case "d":
          e.preventDefault();
          void handleDelete(current.id);
          break;
        case "?":
          e.preventDefault();
          toast({
            title: "میانبرهای صفحه‌کلید",
            description: "j/k پیمایش | a تأیید | u لغو تأیید | s اسپم | t زباله‌دان | d حذف | e ویرایش",
          });
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [comments, focusIndex]);

  const loadComments = async () => {
    setLoading(true);
    try {
      const data = await blogAdminApi.listComments({
        status: statusFilter === "all" ? undefined : statusFilter,
        comment_type: typeFilter,
        search: search || undefined,
        page,
        page_size: PAGE_SIZE,
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
    // A comment on a CMS page has post_id === null, so posting by post id sent
    // the reply to `/blog/posts/null/comments` and it came back 422. Address
    // the reply by (resource_type, resource_id) like the API expects.
    const target = commentTarget(replyTarget);
    if (!target) {
      toast({
        title: "پاسخ ممکن نیست",
        description: "این دیدگاه به هیچ مطلب یا صفحه‌ای متصل نیست.",
        variant: "destructive",
      });
      return;
    }
    setReplying(true);
    try {
      await submitResourceComment(target.resourceType, target.resourceId, {
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

  const handleNote = async () => {
    if (!noteTarget?.resource_id || !noteContent.trim()) return;
    setNoting(true);
    try {
      await blogAdminApi.createCommentNote({
        resource_type: (noteTarget.resource_type || "blog_post") as
          | "blog_post"
          | "cms_page",
        resource_id: noteTarget.resource_id,
        content: noteContent.trim(),
        parent_id: noteTarget.id,
      });
      toast({ title: "یادداشت خصوصی ثبت شد" });
      setNoteDialogOpen(false);
      setNoteContent("");
      await loadComments();
    } catch {
      toast({ title: "ثبت یادداشت ناموفق بود", variant: "destructive" });
    } finally {
      setNoting(false);
    }
  };

  const openEdit = (c: BlogComment) => {
    setEditTarget(c);
    setEditContent(c.content);
    setEditName(c.author_name ?? "");
    setEditEmail(c.author_email ?? "");
    setEditUrl(c.author_url ?? "");
    setEditStatus(c.status);
    setEditDialogOpen(true);
  };

  const handleUnapprove = async (c: BlogComment) => {
    try {
      await blogAdminApi.bulkComments([c.id], "unapprove");
      toast({ title: `«${c.author_name || "دیدگاه"}» به در انتظار بررسی برگشت` });
      await loadComments();
    } catch {
      toast({
        title: "لغو تأیید ناموفق بود",
        variant: "destructive",
      });
    }
  };

  const saveEdit = async () => {
    if (!editTarget) return;
    setEditSaving(true);
    try {
      // Only what changed is sent. The server treats an omitted field as
      // "leave alone" and an empty one as "clear it", so sending a blank
      // email because the operator never touched it would erase the address
      // that identifies the commenter.
      const patch: Parameters<typeof blogAdminApi.updateComment>[1] = {};
      if (editContent.trim() !== editTarget.content) patch.content = editContent.trim();
      if (editName.trim() !== (editTarget.author_name ?? "")) {
        patch.author_name = editName.trim();
      }
      if (editEmail.trim() !== (editTarget.author_email ?? "")) {
        patch.author_email = editEmail.trim();
      }
      if (editUrl.trim() !== (editTarget.author_url ?? "")) {
        patch.author_url = editUrl.trim();
      }
      if (editStatus !== editTarget.status) patch.status = editStatus;

      if (Object.keys(patch).length === 0) {
        setEditDialogOpen(false);
        return;
      }
      await blogAdminApi.updateComment(editTarget.id, patch);
      toast({ title: "دیدگاه ویرایش شد" });
      setEditDialogOpen(false);
      await loadComments();
    } catch {
      toast({ title: "ذخیره ویرایش ناموفق بود", variant: "destructive" });
    } finally {
      setEditSaving(false);
    }
  };

  const runBulk = async (
    action: "approve" | "unapprove" | "spam" | "trash" | "restore",
    rows: BlogComment[],
  ) => {
    try {
      const res = await blogAdminApi.bulkComments(
        rows.map((c) => c.id),
        action,
      );
      if (res.failed > 0) {
        toast({
          title: `${toPersianDigits(String(res.ok))} مورد انجام شد، ${toPersianDigits(String(res.failed))} مورد ناموفق`,
          description: "بعضی دیدگاه‌ها در این فاصله حذف شده بودند.",
          variant: "destructive",
        });
      } else {
        toast({
          title: `${toPersianDigits(String(res.ok))} دیدگاه با موفقیت تغییر کرد`,
        });
      }
      await loadComments();
      return true;
    } catch {
      toast({
        title: "عملیات گروهی ناموفق بود",
        description: "هیچ دیدگاهی تغییر نکرد.",
        variant: "destructive",
      });
      return false;
    }
  };

  /** Bulk moderation, one action over the selected rows.
   *
   *  `trash` is the default destination for anything unwanted rather than
   *  delete: a mistaken bulk action on a spam wave is then one click from
   *  undone, and a permanent delete of forty threads is not.
   */
  const bulkActions = [
    {
      id: "approve",
      label: "تأیید",
      onRun: async (rows: BlogComment[]) => await runBulk("approve", rows),
    },
    {
      id: "unapprove",
      label: "بازگشت به در انتظار",
      onRun: async (rows: BlogComment[]) => await runBulk("unapprove", rows),
    },
    {
      id: "spam",
      label: "اسپم",
      onRun: async (rows: BlogComment[]) => await runBulk("spam", rows),
    },
    {
      id: "trash",
      label: "انتقال به زباله‌دان",
      onRun: async (rows: BlogComment[]) => await runBulk("trash", rows),
    },
    {
      // The other half of trash. Without it the bulk trash action is a
      // one-way door: a moderator clearing a wave by mistake has no way back
      // except the panel's own per-row control, which is exactly what the
      // bulk path is supposed to save them from.
      id: "restore",
      label: "بازگردانی از زباله‌دان",
      onRun: async (rows: BlogComment[]) => await runBulk("restore", rows),
    },
  ];

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
          {/* The address a comment came from is the single most useful signal
              when deciding what is spam — two comments from one address are
              one campaign. It is on the admin response only, so rendering it
              here cannot leak it to a reader. */}
          {c.author_ip && (
            <div className="text-[11px] text-muted-foreground/80 dir-ltr text-right mt-0.5">
              {c.author_ip}
            </div>
          )}
          {c.author_url && (
            <a
              href={c.author_url}
              target="_blank"
              rel="noopener noreferrer nofollow"
              className="text-[11px] text-primary/80 dir-ltr text-right mt-0.5 block truncate hover:underline"
              title={c.author_url}
            >
              {c.author_url.replace(/^https?:\/\//, "")}
            </a>
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
          {/* A note is styled apart rather than moved to its own screen: it is
              the same row in the same thread, it just never reaches a reader. */}
          {c.comment_type === "note" && (
            <Badge
              variant="outline"
              className="border-amber-500/40 bg-amber-500/10 text-[10px] text-amber-700 dark:text-amber-400"
            >
              یادداشت خصوصی
            </Badge>
          )}
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
          {/* Moderation actions are meaningless on a note: it is written by the
              team, is always approved, and a public reply to it would be a
              comment nobody can see the context of. */}
          {c.comment_type === "note" ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setNoteTarget(c);
                  setNoteContent("");
                  setNoteDialogOpen(true);
                }}
                className="h-8 gap-1 text-xs text-amber-700 hover:bg-amber-500/10 dark:text-amber-400"
              >
                <StickyNote className="h-3.5 w-3.5" />
                افزودن یادداشت
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleDelete(c.id)}
                className="h-8 gap-1 text-xs text-destructive hover:bg-destructive/10"
              >
                <Trash2 className="h-3.5 w-3.5" />
                حذف
              </Button>
            </>
          ) : (
            <>
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
          {/* Un-approving is the one moderation move with no button: a comment
              that slipped through is the one a moderator needs to pull back,
              and before this the only way was to edit the row's status
              through the API. */}
          {c.status === "approved" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleUnapprove(c)}
              className="h-8 gap-1 text-xs text-amber-600 hover:text-amber-700 hover:bg-amber-50 dark:hover:bg-amber-950/20"
              title="بازگشت به در انتظار بررسی"
            >
              <Undo2 className="h-3.5 w-3.5" />
              لغو تأیید
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => openEdit(c)}
            className="h-8 gap-1 text-xs"
            title="ویرایش متن و مشخصات نویسنده"
          >
            <Pencil className="h-3.5 w-3.5" />
            ویرایش
          </Button>
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
            </>
          )}
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
            <span
              className="text-[11px] text-muted-foreground hidden sm:inline"
              title="کلیدهای میانبر: j/k پیمایش، a تأیید، u لغو تأیید، s اسپم، t زباله‌دان، d حذف، e ویرایش، ؟ راهنما"
            >
              (میانبرها: <kbd className="rounded border px-1 text-[10px]">؟</kbd>)
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
              {/* The bulk trash action above writes CommentStatus.TRASH
                  through the same endpoint, so this filter is not decorative.
                  It was removed on the belief that nothing could ever produce
                  TRASH — which the trash button in this very panel does, on
                  every moderation screen. Without it the trash was a one-way
                  door: a moderator who cleared a spam wave could not see what
                  they had trashed, let alone put it back. */}
              <option value="trash">زباله‌دان</option>
            </select>
            <select
              value={typeFilter ?? "all"}
              onChange={(e) =>
                setTypeFilter(
                  e.target.value === "all" ? undefined : (e.target.value as "comment" | "note"),
                )
              }
              className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              aria-label="فیلتر نوع"
            >
              <option value="all">دیدگاه‌ها و یادداشت‌ها</option>
              <option value="comment">فقط دیدگاه‌ها</option>
              <option value="note">فقط یادداشت‌های خصوصی</option>
            </select>
            <Button variant="outline" size="sm" onClick={loadComments} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>
      </Card>

      <div className="flex items-center gap-2">
        <Input
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            // A narrowed list is shorter, so page 4 would show nothing. Same
            // reset a filter change gets below.
            setPage(1);
          }}
          placeholder="جست‌وجو در متن، نام، ایمیل یا وب‌سایت نویسنده..."
          aria-label="جست‌وجو در دیدگاه‌ها"
          className="text-xs"
        />
        {search && (
          <Button
            variant="ghost"
            size="sm"
            className="h-9 text-xs"
            onClick={() => {
              setSearch("");
              setPage(1);
            }}
          >
            پاک کردن
          </Button>
        )}
      </div>

      <DataTable<BlogComment>
        columns={columns}
        rows={comments}
        rowKey={(c) => c.id}
        emptyMessage={
          loading
            ? "در حال بارگذاری..."
            : search
              ? `دیدگاهی با «${search}» پیدا نشد`
              : "دیدگاهی یافت نشد."
        }
        selectable
        bulkActions={bulkActions}
        pageSize={PAGE_SIZE}
        serverTotal={total}
        onServerPageChange={setPage}
      />

      {/* Edit dialog */}
      <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
        <DialogContent className="max-w-xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>ویرایش دیدگاه</DialogTitle>
            <DialogDescription>
              فقط فیلدهای تغییرکرده ذخیره می‌شوند؛ بقیه دست‌نخورده می‌مانند.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="grid gap-2">
              <Label htmlFor="edit-content">متن دیدگاه</Label>
              <Textarea
                id="edit-content"
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                rows={5}
                className="text-sm"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="edit-name">نام نویسنده</Label>
                <Input
                  id="edit-name"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="text-xs"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-email">ایمیل</Label>
                <Input
                  id="edit-email"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  dir="ltr"
                  className="text-left font-mono text-xs"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-url">وب‌سایت</Label>
                <Input
                  id="edit-url"
                  value={editUrl}
                  onChange={(e) => setEditUrl(e.target.value)}
                  dir="ltr"
                  placeholder="https://"
                  className="text-left font-mono text-xs"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="edit-status">وضعیت</Label>
                <select
                  id="edit-status"
                  value={editStatus}
                  onChange={(e) => setEditStatus(e.target.value as CommentStatus)}
                  className="h-9 rounded-md border border-input bg-background px-3 text-xs"
                >
                  <option value="approved">تأیید شده</option>
                  <option value="pending">در انتظار بررسی</option>
                  <option value="spam">اسپم / جفنگ</option>
                  <option value="trash">زباله‌دان</option>
                </select>
              </div>
            </div>
            {editTarget?.author_ip && (
              <p className="text-[11px] text-muted-foreground" dir="ltr">
                IP: {editTarget.author_ip}
              </p>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setEditDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void saveEdit()} disabled={editSaving}>
              {editSaving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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

      {/* Private note dialog — a comment row the team can see and no reader can. */}
      <Dialog open={noteDialogOpen} onOpenChange={setNoteDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <StickyNote className="h-4 w-4 text-amber-600" />
              یادداشت خصوصی
            </DialogTitle>
            <DialogDescription>
              فقط همین جدول مدیریت آن را می‌بیند؛ در صفحه‌ی عمومی، فید و شمارنده‌ی
              دیدگاه‌ها ظاهر نمی‌شود. برای گفت‌وگوی داخلی تیم استفاده کنید، نه پاسخ به
              مشتری.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {noteTarget && (
              <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                درباره‌ی: «{noteTarget.content.slice(0, 100)}»
              </p>
            )}
            <Textarea
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              placeholder="یادداشت داخلی برای همکاران..."
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoteDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={handleNote} disabled={noting || !noteContent.trim()}>
              {noting ? "در حال ثبت..." : "ثبت یادداشت"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
