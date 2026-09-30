"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { MessageSquare, CornerDownLeft, Send, CheckCircle2, AlertCircle, Clock, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import {
  fetchPostComments,
  submitPostComment,
  type BlogComment,
} from "@/lib/api/blog";
import { toPersianDigits } from "@/lib/utils";
import { RemoteImage } from "@/components/shared/remote-image";
import { useAuth } from "@/hooks/use-auth";

interface BlogCommentsProps {
  postId: string;
  allowComments?: boolean;
  /** True when the operator requires accounts to comment
   *  (comment_registration). The form is replaced by a sign-in prompt —
   *  filling it and getting a 422 is a worse experience than being told. */
  requiresLogin?: boolean;
}

export function BlogComments({
  postId,
  allowComments = true,
  requiresLogin = false,
}: BlogCommentsProps) {
  const { toast } = useToast();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [comments, setComments] = useState<BlogComment[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);

  // Form state
  const [authorName, setAuthorName] = useState("");
  const [authorEmail, setAuthorEmail] = useState("");
  const [content, setContent] = useState("");
  const [replyTo, setReplyTo] = useState<{ id: string; name: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [submittedNotice, setSubmittedNotice] = useState(false);

  // The server is the source of truth for the gate (it enforces it on
  // create_comment); this flag just decides what the form area renders.
  const gateActive = requiresLogin && !authLoading && !isAuthenticated;

  useEffect(() => {
    loadComments();
  }, [postId]);

  const loadComments = async () => {
    setLoading(true);
    try {
      const data = await fetchPostComments(postId);
      setComments(data.items || []);
      setTotal(data.total || 0);
    } catch {
      setComments([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setSubmitting(true);
    try {
      await submitPostComment(postId, {
        content: content.trim(),
        author_name: authorName.trim() || undefined,
        author_email: authorEmail.trim() || undefined,
        parent_id: replyTo?.id,
      });

      setContent("");
      setReplyTo(null);
      setSubmittedNotice(true);
      toast({
        title: "دیدگاه شما ارسال شد",
        description: "پس از بررسی و تأیید ناظر، در سایت نمایش داده خواهد شد.",
      });
      await loadComments();
    } catch {
      toast({
        title: "خطا در ارسال دیدگاه",
        description: "لطفاً دوباره تلاش فرمایید.",
        variant: "destructive",
      });
    } finally {
      setSubmitting(false);
    }
  };

  if (!allowComments) {
    return (
      <div className="rounded-2xl border border-border bg-muted/40 p-6 text-center text-sm text-muted-foreground">
        امکان ارسال دیدگاه برای این مطلب بسته شده است.
      </div>
    );
  }

  return (
    <section className="mt-16 border-t border-border pt-12">
      <div className="mb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <MessageSquare className="h-6 w-6 text-emerald-600" />
          <h3 className="text-2xl font-bold">
            دیدگاه‌ها{" "}
            {total > 0 && (
              <span className="text-lg font-normal text-muted-foreground">
                ({toPersianDigits(String(total))})
              </span>
            )}
          </h3>
        </div>
      </div>

      {submittedNotice && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <span>دیدگاه شما با موفقیت ثبت شد و پس از تایید مدیریت نمایش داده می‌شود.</span>
        </div>
      )}

      {/* Comment Form — replaced by a sign-in prompt while
          comment_registration is on and the visitor is a guest. */}
      {gateActive ? (
        <Card className="mb-10 rounded-2xl border-border bg-card shadow-sm">
          <CardContent className="flex flex-col items-center gap-4 p-8 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600">
              <LogIn className="h-6 w-6" />
            </div>
            <div className="space-y-1">
              <h4 className="font-bold text-base">برای ثبت دیدگاه وارد شوید</h4>
              <p className="text-xs text-muted-foreground">
                ثبت دیدگاه در این سایت فقط برای کاربران عضو امکان‌پذیر است.
              </p>
            </div>
            <Button asChild className="gap-2">
              <Link href={`/login?redirect=${encodeURIComponent(`/blog`)}`}>
                <LogIn className="h-4 w-4" />
                ورود به حساب کاربری
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
      <Card className="mb-10 rounded-2xl border-border bg-card shadow-sm">
        <CardContent className="p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <h4 className="font-bold text-base text-foreground">
              {replyTo ? `پاسخ به ${replyTo.name}` : "دیدگاه خود را بنویسید"}
            </h4>

            {replyTo && (
              <div className="flex items-center justify-between rounded-lg bg-muted px-3 py-1.5 text-xs text-muted-foreground">
                <span>در حال پاسخ به: {replyTo.name}</span>
                <button
                  type="button"
                  onClick={() => setReplyTo(null)}
                  className="text-destructive hover:underline"
                >
                  انصراف از پاسخ
                </button>
              </div>
            )}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="c-name">نام شما (اختیاری)</Label>
                <Input
                  id="c-name"
                  value={authorName}
                  onChange={(e) => setAuthorName(e.target.value)}
                  placeholder="علی احمدی"
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="c-email">ایمیل (نمایش داده نمی‌شود)</Label>
                <Input
                  id="c-email"
                  type="email"
                  value={authorEmail}
                  onChange={(e) => setAuthorEmail(e.target.value)}
                  placeholder="ali@example.com"
                  dir="ltr"
                  className="text-left"
                />
              </div>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="c-content">متن دیدگاه</Label>
              <Textarea
                id="c-content"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="نظر یا پرسش خود را درباره این مقاله بنویسید..."
                rows={4}
                required
              />
            </div>

            <div className="flex justify-end">
              <Button type="submit" disabled={submitting || !content.trim()} className="gap-2">
                <Send className="h-4 w-4" />
                {submitting ? "در حال ارسال..." : "ارسال دیدگاه"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
      )}

      {/* Comments List */}
      {loading ? (
        <div className="py-8 text-center text-sm text-muted-foreground">
          در حال بارگذاری دیدگاه‌ها...
        </div>
      ) : comments.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          هنوز دیدگاهی برای این مقاله ثبت نشده است. اولین نفری باشید که نظر می‌دهد!
        </div>
      ) : (
        <div className="space-y-4">
          {comments.map((comment) => (
            <CommentItem
              key={comment.id}
              comment={comment}
              onReply={(c) => setReplyTo({ id: c.id, name: c.author_name || "کاربر" })}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function CommentItem({
  comment,
  onReply,
  depth = 0,
}: {
  comment: BlogComment;
  onReply: (comment: BlogComment) => void;
  depth?: number;
}) {
  const authorInitial = (comment.author_name || "ک")[0];
  const dateFormatted = toPersianDigits(
    new Date(comment.created_at).toLocaleDateString("fa-IR", {
      year: "numeric",
      month: "long",
      day: "numeric",
    }),
  );

  return (
    <div className={`space-y-3 ${depth > 0 ? "me-4 md:me-8 mt-3" : ""}`}>
      <div className="rounded-2xl border border-border bg-card p-5 shadow-xs transition-colors hover:border-emerald-500/30">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {/* Uploaded avatar wins, else the author's Gravatar; the initial
                is the final fallback for guests who left no email. */}
            {comment.author_avatar_url ? (
              <RemoteImage
                src={comment.author_avatar_url}
                alt={comment.author_name || "کاربر"}
                sizes="40px"
                className="h-10 w-10 shrink-0 rounded-full object-cover"
              />
            ) : (
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-emerald-600/10 font-bold text-emerald-600">
                {authorInitial}
              </div>
            )}
            <div>
              <h5 className="font-bold text-sm text-foreground">
                {comment.author_name || "کاربر مهمان"}
              </h5>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {dateFormatted}
              </span>
            </div>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onReply(comment)}
            className="h-8 gap-1 text-xs text-muted-foreground hover:text-emerald-600"
          >
            <CornerDownLeft className="h-3.5 w-3.5" />
            پاسخ
          </Button>
        </div>
        <p className="mt-3 text-sm leading-relaxed text-foreground/90 whitespace-pre-wrap">
          {comment.content}
        </p>
      </div>

      {/* Threaded Replies */}
      {comment.replies && comment.replies.length > 0 && (
        <div className="border-r-2 border-emerald-600/30 pe-2">
          {comment.replies.map((reply) => (
            <CommentItem
              key={reply.id}
              comment={reply}
              onReply={onReply}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}
