"use client";

/**
 * CmsPreviewDialog — see a CMS page as a reader will, without publishing it.
 *
 * The page list's draft button pointed at
 * `/api/v1/content/admin/pages/by-slug/<slug>`, which opens raw JSON in a new
 * tab. That is not a preview: it is the stored row, unrendered, with no
 * content, no layout and no sign of what a visitor would actually get.
 *
 * This dialog fetches the page through the admin API (cookie-authenticated, so
 * it is a client island on purpose — a draft must never be pulled during SSR
 * into a shared cache) and renders the body through the same `cleanHtml`
 * pipeline the storefront page uses.
 */

import { useEffect, useState } from "react";
import { Eye, Loader2, Lock } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { cmsPagesAdminApi, type CmsPage } from "@/lib/api/content";
import cleanHtml from "@/lib/sanitize-html";

interface CmsPreviewDialogProps {
  pageId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CmsPreviewDialog({ pageId, open, onOpenChange }: CmsPreviewDialogProps) {
  const { toast } = useToast();
  const [page, setPage] = useState<CmsPage | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !pageId) return;
    let cancelled = false;
    setLoading(true);
    setPage(null);
    (async () => {
      try {
        const res = await cmsPagesAdminApi.getPage(pageId);
        if (!cancelled) setPage(res);
      } catch {
        if (!cancelled) {
          toast({
            title: "خطا",
            description: "دریافت پیش‌نمایش برگه ممکن نشد",
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
  }, [open, pageId, toast]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-3xl overflow-y-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Eye className="h-4 w-4" />
            پیش‌نمایش برگه
          </DialogTitle>
          <DialogDescription>
            نمایش برگه در وضعیت فعلی، بدون انتشار در سایت.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            در حال بارگذاری پیش‌نمایش...
          </div>
        ) : page ? (
          <article className="space-y-6 py-2">
            <header className="space-y-2">
              <h1 className="text-2xl font-black leading-tight">{page.title}</h1>
              <div className="flex flex-wrap items-center gap-3 border-y border-border py-2 text-xs text-muted-foreground">
                <span>/{page.slug}</span>
                <span className="flex items-center gap-1">
                  <Lock className="h-3.5 w-3.5" />
                  وضعیت: {page.status}
                </span>
              </div>
            </header>

            {page.excerpt && (
              <p className="rounded-2xl border-r-4 border-primary bg-muted/40 p-4 text-sm font-medium leading-relaxed text-muted-foreground">
                {page.excerpt}
              </p>
            )}

            <div
              className="prose prose-sm max-w-none leading-relaxed text-foreground/90"
              dangerouslySetInnerHTML={{ __html: cleanHtml(page.body_html || "") }}
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
