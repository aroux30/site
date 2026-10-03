"use client";

/**
 * RevisionCompareDialog — see what actually changed between two stored
 * revisions of a post.
 *
 * The backend has had a field-level diff (including a word-level inline diff
 * of the body) with no caller at all: the revisions dialog offered a list and
 * a restore button and nothing else, so an editor who wanted to know what a
 * restore would throw away had to restore it and look.
 *
 * Two revisions are picked by id rather than by number, because restoring an
 * old number back onto the post creates a new row that claims the same number.
 */
import { useEffect, useState } from "react";
import { GitCompare, Loader2, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  blogAdminApi,
  type BlogRevision,
  type RevisionDiffResponse,
  type RevisionDiffToken,
} from "@/lib/api/blog";
import { toPersianDigits } from "@/lib/utils";

interface RevisionCompareDialogProps {
  postId: string | null;
  revisions: BlogRevision[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RevisionCompareDialog({
  postId,
  revisions,
  open,
  onOpenChange,
}: RevisionCompareDialogProps) {
  const { toast } = useToast();
  const [aId, setAId] = useState<string | null>(null);
  const [bId, setBId] = useState<string | null>(null);
  const [diff, setDiff] = useState<RevisionDiffResponse | null>(null);
  const [loading, setLoading] = useState(false);

  // Default to the two most recent revisions: that is the comparison an editor
  // opens this for nine times out of ten ("what did I just change?").
  useEffect(() => {
    if (!open) return;
    setDiff(null);
    const first = revisions[0];
    const second = revisions[1];
    setAId(second ? second.id : null);
    setBId(first ? first.id : null);
  }, [open, revisions]);

  useEffect(() => {
    if (!open || !postId || !aId || !bId || aId === bId) {
      setDiff(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    (async () => {
      try {
        const res = await blogAdminApi.diffRevisions(postId, aId, bId);
        if (!cancelled) setDiff(res);
      } catch {
        if (!cancelled) {
          toast({
            title: "خطا",
            description: "محاسبه‌ی تفاوت دو نسخه ممکن نشد",
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
  }, [open, postId, aId, bId, toast]);

  const num = (n: number) => toPersianDigits(String(n));

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] max-w-4xl overflow-y-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitCompare className="h-4 w-4" />
            مقایسه نسخه‌ها
          </DialogTitle>
          <DialogDescription>
            دو نسخه را انتخاب کنید تا تفاوت فیلد به فیلد نمایش داده شود. نسخه‌ی قدیمی سمت
            راست و نسخه‌ی جدید سمت چپ است.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-3 py-2 sm:grid-cols-2">
          <div className="grid gap-2">
            <span className="text-xs font-medium text-muted-foreground">نسخه‌ی قدیمی</span>
            <select
              value={aId ?? ""}
              onChange={(e) => setAId(e.target.value || null)}
              className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              aria-label="انتخاب نسخه‌ی قدیمی"
            >
              <option value="">انتخاب کنید</option>
              {revisions.map((r) => (
                <option key={r.id} value={r.id}>
                  نسخه {num(r.revision_number)} — {r.title}
                </option>
              ))}
            </select>
          </div>
          <div className="grid gap-2">
            <span className="text-xs font-medium text-muted-foreground">نسخه‌ی جدید</span>
            <select
              value={bId ?? ""}
              onChange={(e) => setBId(e.target.value || null)}
              className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              aria-label="انتخاب نسخه‌ی جدید"
            >
              <option value="">انتخاب کنید</option>
              {revisions.map((r) => (
                <option key={r.id} value={r.id}>
                  نسخه {num(r.revision_number)} — {r.title}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            در حال محاسبه‌ی تفاوت...
          </div>
        ) : !aId || !bId ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            برای مقایسه، دو نسخه‌ی متفاوت را انتخاب کنید.
          </p>
        ) : aId === bId ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            یک نسخه را با خودش نمی‌شود مقایسه کرد.
          </p>
        ) : diff && !diff.changed ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
            <Check className="h-4 w-4 text-emerald-600" />
            این دو نسخه در هیچ فیلدی تفاوت ندارند.
          </div>
        ) : diff ? (
          <div className="space-y-4 py-2">
            {diff.fields
              .filter((f) => f.changed)
              .map((f) => (
                <section key={f.field} className="rounded-xl border border-border">
                  <header className="border-b border-border bg-muted/40 px-3 py-2 text-xs font-bold">
                    {f.label}
                  </header>
                  {f.inline_diff ? (
                    <p className="px-3 py-3 text-sm leading-7">
                      {f.inline_diff.map((tok: RevisionDiffToken, i: number) => (
                        <span
                          key={i}
                          className={
                            tok.op === "insert"
                              ? "rounded bg-emerald-500/20 px-0.5 text-emerald-800 dark:text-emerald-300"
                              : tok.op === "delete"
                                ? "rounded bg-destructive/20 px-0.5 line-through"
                                : ""
                          }
                        >
                          {tok.text}{" "}
                        </span>
                      ))}
                    </p>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 px-3 py-3 text-sm sm:grid-cols-2">
                      <div className="rounded-lg bg-destructive/10 p-2">
                        <span className="mb-1 block text-[11px] text-muted-foreground">قدیمی</span>
                        {f.a || <span className="text-muted-foreground">—</span>}
                      </div>
                      <div className="rounded-lg bg-emerald-500/10 p-2">
                        <span className="mb-1 block text-[11px] text-muted-foreground">جدید</span>
                        {f.b || <span className="text-muted-foreground">—</span>}
                      </div>
                    </div>
                  )}
                </section>
              ))}
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
