"use client";

/**
 * ContentToolsCard — the two maintenance actions WordPress puts under Tools.
 *
 * Both existed on the server as one-off capabilities with no reachable
 * surface, so an operator who needed them had to call the API by hand:
 *
 *  - **Convert categories to tags.** A store migrated from WordPress arrives
 *    with everything filed under categories, because that is what WordPress's
 *    importer produces when someone was using "categories" as a keyword
 *    field. Once they are noise, the move is to make them tags and start over.
 *  - **Empty the trash.** Both content types had a soft delete and a restore,
 *    and no way to finish the job — so the trash only ever grew, and an
 *    operator who trashed a hundred posts by accident had no way back.
 *
 * Neither is a normal setting, so they live on their own card rather than in
 * the content settings form where a mistyped value would change them silently.
 */
import { useState } from "react";
import { AlertTriangle, Loader2, Tags, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { toPersianDigits } from "@/lib/utils";
import { blogAdminApi } from "@/lib/api/blog";
import { cmsPagesAdminApi } from "@/lib/api/content";

const fa = (n: number | undefined) => toPersianDigits(String(n ?? 0));

export function ContentToolsCard() {
  const { toast } = useToast();
  const [busy, setBusy] = useState<"convert" | "posts" | "pages" | null>(null);

  /** Both purges share a window, because they are the same decision made twice. */
  const [postDays, setPostDays] = useState("30");
  const [pageDays, setPageDays] = useState("30");

  const [clearCategories, setClearCategories] = useState(false);

  const days = (v: string) => {
    const n = Number.parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : undefined;
  };

  const convert = async () => {
    const warning = clearCategories
      ? "دسته‌های همه‌ی نوشته‌ها جدا می‌شوند و فقط برچسب باقی می‌ماند. این کار از طریق تاریخچه قابل بازگشت نیست."
      : "به هر نوشته‌ی دسته‌دار یک برچسب هم‌نام با دسته‌اش اضافه می‌شود. دسته‌ها دست‌نخورده می‌مانند.";
    if (!window.confirm(`${warning}\n\nادامه می‌دهید؟`)) return;

    setBusy("convert");
    try {
      const res = await blogAdminApi.categoriesToTags({ clearCategories });
      toast({
        title: `${fa(res.converted)} نوشته تبدیل شد`,
        description:
          `${fa(res.tags_created)} برچسب ساخته شد` +
          (res.tags_reused ? `، ${fa(res.tags_reused)} برچسب موجود استفاده شد` : "") +
          (res.skipped_no_category
            ? `. ${fa(res.skipped_no_category)} نوشته دسته نداشت و دست‌نخورده ماند`
            : ""),
      });
    } catch {
      toast({
        title: "تبدیل دسته به برچسب ناموفق بود",
        description: "هیچ نوشته‌ای تغییر نکرد.",
        variant: "destructive",
      });
    } finally {
      setBusy(null);
    }
  };

  const empty = async (kind: "posts" | "pages") => {
    const what = kind === "posts" ? "نوشته‌ها" : "برگه‌ها";
    // Not named `window`: a local of that name shadows the global, and
    // `window.confirm` then silently becomes a call on a string.
    const keepDays = days(kind === "posts" ? postDays : pageDays);
    const message = keepDays
      ? `فقط مواردی که بیش از ${fa(keepDays)} روز در زباله‌دان ${what} مانده‌اند برای همیشه حذف می‌شوند. تازه‌ترها می‌مانند تا اگر اشتباهی زباله کردید راه بازیابی باشد.`
      : `همه‌ی ${what} داخل زباله‌دان برای همیشه حذف می‌شوند. این عمل برگشت‌پذیر نیست.`;
    if (!window.confirm(`${message}\n\nادامه می‌دهید؟`)) return;

    setBusy(kind);
    try {
      const res =
        kind === "posts"
          ? await blogAdminApi.emptyPostTrash(keepDays)
          : await cmsPagesAdminApi.emptyPageTrash(keepDays);
      toast({
        title: `${fa(res.removed)} ${what} برای همیشه حذف شد`,
        description: "فهرست به‌روزرسانی شد.",
      });
    } catch {
      toast({
        title: "خالی‌کردن زباله‌دان ناموفق بود",
        variant: "destructive",
      });
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="space-y-5 p-5" dir="rtl">
      <div className="flex items-center gap-2">
        <Tags className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">ابزارهای محتوا</h3>
      </div>

      {/* Category → tag converter */}
      <section className="space-y-3 rounded-xl border border-border p-4">
        <div>
          <h4 className="text-sm font-medium">تبدیل دسته‌ها به برچسب</h4>
          <p className="mt-1 text-xs text-muted-foreground">
            برای فروشگاهی که از وردپرس آمده و همه‌چیز را زیر دسته گذاشته است. به هر
            نوشته‌ی دسته‌دار یک برچسب هم‌نام با دسته‌اش اضافه می‌شود.
          </p>
        </div>
        <label className="flex items-start gap-2 text-xs">
          <input
            type="checkbox"
            checked={clearCategories}
            onChange={(e) => setClearCategories(e.target.checked)}
            className="mt-0.5 h-3.5 w-3.5"
          />
          <span>
            دسته‌ها هم جدا شوند
            <span className="block text-[11px] text-muted-foreground">
              بدون این تیک، کار برگشت‌پذیر است: کافی است برچسب‌های افزوده را پاک
              کنید.
            </span>
          </span>
        </label>
        <Button
          variant="outline"
          size="sm"
          className="gap-1.5"
          disabled={busy !== null}
          onClick={() => void convert()}
        >
          {busy === "convert" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Tags className="h-3.5 w-3.5" />
          )}
          اجرای تبدیل
        </Button>
      </section>

      {/* Trash purge */}
      <section className="space-y-3 rounded-xl border border-border p-4">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <div>
            <h4 className="text-sm font-medium">خالی‌کردن زباله‌دان</h4>
            <p className="mt-1 text-xs text-muted-foreground">
              حذف دائمی محتوایی که زباله شده. با تعیین «نگه‌داشتن» فقط قدیمی‌ها پاک
              می‌شوند و اگر اشتباهی زباله کردید راه بازگشت می‌ماند.
            </p>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {(
            [
              ["posts", "نوشته‌ها", postDays, setPostDays],
              ["pages", "برگه‌ها", pageDays, setPageDays],
            ] as const
          ).map(([kind, label, value, setValue]) => (
            <div key={kind} className="space-y-2 rounded-lg border border-border/60 p-3">
              <Label htmlFor={`trash-${kind}`} className="text-xs">
                {label}
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id={`trash-${kind}`}
                  type="number"
                  min={1}
                  dir="ltr"
                  value={value}
                  onChange={(e) => setValue(e.target.value)}
                  className="h-8 text-left font-mono text-xs"
                />
                <span className="whitespace-nowrap text-[11px] text-muted-foreground">
                  روز نگه‌داشتن
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="w-full gap-1.5 text-destructive hover:bg-destructive/10"
                disabled={busy !== null}
                onClick={() => void empty(kind)}
              >
                {busy === kind ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
                خالی‌کردن زباله‌دان {label}
              </Button>
            </div>
          ))}
        </div>
      </section>
    </Card>
  );
}