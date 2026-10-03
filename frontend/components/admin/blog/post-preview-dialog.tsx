"use client";

/**
 * PostPreviewDialog — see a post exactly as a reader will, before publishing.
 *
 * The admin list's preview button used to open `/blog/<slug>`, which is a
 * server component reading the *public* endpoint. A draft is not there, so the
 * button 404'd, and the admin-only `previewPost` route had no caller at all —
 * drafts were reviewed by publishing and hoping.
 *
 * This dialog fetches through `previewPost` (which is access-checked and hands
 * back any status) and renders with the same `cleanHtml` pipeline the article
 * page uses. It is deliberately a client island: the draft body must never be
 * fetched during SSR, where it would land in a cache or a prefetch that a
 * later visitor could read.
 */

import { useEffect, useState } from "react";
import { Eye, Loader2, Calendar, User, Lock } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { blogAdminApi, type BlogPost } from "@/lib/api/blog";
import cleanHtml from "@/lib/sanitize-html";
import { RemoteImage } from "@/components/shared/remote-image";

interface PostPreviewDialogProps {
  postId: string | null;
  /** Used only for the dialog title before the body arrives. */
  fallbackTitle?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function PostPreviewDialog({
  postId,
  fallbackTitle,
  open,
  onOpenChange,
}: PostPreviewDialogProps) {
  const { toast } = useToast();
  const [post, setPost] = useState<BlogPost | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !postId) return;
    let cancelled = false;
    setLoading(true);
    setPost(null);
    (async () => {
      try {
        const res = await blogAdminApi.previewPost(postId);
        if (!cancelled) setPost(res);
      } catch {
        if (!cancelled) {
          toast({
            title: "خطا",
            description: "دریافت پیش‌نمایش نوشته ممکن نشد",
            variant: "destructive",
          });
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, postId, toast]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="h-4 w-4" />
            پیش‌نمایش نوشته
          </DialogTitle>
          <DialogDescription>
            این نوشته در هر وضعیتی (حتی پیش‌نویس) نمایش داده می‌شود. هیچ بازدیدی برای
            بازدیدکنندگان ثبت نمی‌شود.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            در حال بارگذاری پیش‌نمایش...
          </div>
        ) : post ? (
          <article className="space-y-6 py-2">
            <header className="space-y-3">
              <h1 className="text-2xl font-black leading-tight">{post.title || fallbackTitle}</h1>
              <div className="flex flex-wrap items-center gap-4 border-y border-border py-3 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <User className="h-3.5 w-3.5" />
                  {post.author_name || "تیم تحریریه"}
                </span>
                {post.published_at && (
                  <span className="flex items-center gap-1">
                    <Calendar className="h-3.5 w-3.5" />
                    {new Date(post.published_at).toLocaleDateString("fa-IR")}
                  </span>
                )}
                <span className="flex items-center gap-1">
                  <Lock className="h-3.5 w-3.5" />
                  وضعیت: {post.status}
                </span>
              </div>
            </header>

            {post.cover_image_url && (
              <div className="relative h-56 overflow-hidden rounded-2xl border border-border">
                <RemoteImage
                  src={post.cover_image_url}
                  alt={post.title}
                  className="h-full w-full object-cover"
                />
              </div>
            )}

            {post.excerpt && (
              <p className="rounded-2xl border-r-4 border-primary bg-muted/40 p-4 text-sm font-medium leading-relaxed text-muted-foreground">
                {post.excerpt}
              </p>
            )}

            <div
              className="prose prose-sm max-w-none leading-relaxed text-foreground/90"
              dangerouslySetInnerHTML={{ __html: cleanHtml(post.content || "") }}
            />
          </article>
        ) : (
          <p className="py-12 text-center text-sm text-muted-foreground">
            پیش‌نمایشی برای نمایش وجود ندارد.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}