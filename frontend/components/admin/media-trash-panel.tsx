"use client";

/**
 * The media trash: soft-deleted assets with restore and permanent delete.
 *
 * P0 "مدیا: سطل زباله". Delete used to take the row and the bytes in one step,
 * so an image a product was using could not be brought back. The delete now
 * trashes; this is where an operator undoes that, and where a purge (which does
 * remove the bytes) is asked for explicitly.
 */

import { useState } from "react";
import { RotateCcw, Trash2, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { mediaApi, type MediaAsset } from "@/lib/api/media";
import { toPersianDigits } from "@/lib/utils";
import { useAdminMutation } from "@/lib/api/admin-query";

export default function MediaTrashPanel({
  onChanged,
}: {
  /** Called after any restore or purge so the library list refetches. */
  onChanged: () => void;
}) {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [items, setItems] = useState<MediaAsset[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await mediaApi.listTrash();
      setItems(data.items);
    } catch {
      setItems([]);
      toast({ title: "خواندن سطل زباله ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  const restore = async (id: string, name: string) => {
    setBusy(id);
    const result = await runMutation(() => mediaApi.restore(id), {
      fallbackError: "بازگردانی ناموفق بود",
    });
    setBusy(null);
    if (!result.ok) {
      // The service refuses when the bytes are gone; say that plainly rather
      // than "try again", because retrying cannot help.
      toast({
        title: result.error,
        description: "اگر فایل روی دیسک نباشد، بازگردانی ممکن نیست.",
        variant: "destructive",
      });
      return;
    }
    toast({ title: `«${name}» به کتابخانه برگشت` });
    await load();
    onChanged();
  };

  const purge = async (id: string, name: string) => {
    if (
      !confirm(
        `«${name}» برای همیشه حذف شود؟\n\n` +
          "این کار فایل را از روی سرور پاک می‌کند و قابل بازگشت نیست.",
      )
    ) {
      return;
    }
    setBusy(id);
    const result = await runMutation(() => mediaApi.purge(id), {
      fallbackError: "حذف دائمی ناموفق بود",
    });
    setBusy(null);
    if (!result.ok) {
      toast({ title: result.error, variant: "destructive" });
      return;
    }
    toast({ title: `«${name}» برای همیشه حذف شد` });
    await load();
    onChanged();
  };

  const emptyAll = async () => {
    if (!confirm("کل سطل زباله خالی شود؟\n\nهمه فایل‌ها برای همیشه حذف می‌شوند.")) return;
    const result = await runMutation(() => mediaApi.emptyTrash(), {
      fallbackError: "خالی‌کردن سطل زباله ناموفق بود",
    });
    if (!result.ok) {
      toast({ title: result.error, variant: "destructive" });
      return;
    }
    toast({ title: `${toPersianDigits(String(result.data?.purged ?? 0))} فایل حذف شد` });
    await load();
    onChanged();
  };

  // Nothing loaded yet: show the action, not an empty list that reads as
  // "the trash is empty" before it has been asked.
  const notLoaded = items === null;

  return (
    <Card className="rounded-xl border-border bg-card p-4">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Trash2 className="h-5 w-5 text-muted-foreground" />
          <div>
            <h2 className="text-sm font-semibold text-foreground">سطل زباله رسانه</h2>
            <p className="text-xs text-muted-foreground">
              حذف یک فایل فقط آن را به اینجا می‌برد؛ فایل روی سرور می‌ماند تا بازگردانده شود.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
            {loading ? "در حال خواندن..." : "نمایش سطل زباله"}
          </Button>
          {!notLoaded && (items?.length ?? 0) > 0 && (
            <Button variant="destructive" size="sm" onClick={() => void emptyAll()}>
              <AlertTriangle className="ml-2 h-4 w-4" />
              خالی‌کردن کل سطل
            </Button>
          )}
        </div>
      </div>

      {!notLoaded && (items?.length ?? 0) === 0 && (
        <p className="py-6 text-center text-sm text-muted-foreground">سطل زباله خالی است.</p>
      )}

      <ul className="space-y-2">
        {(items ?? []).map((a) => (
          <li
            key={a.id}
            className="flex items-center justify-between gap-3 rounded-lg border border-border p-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-foreground">{a.file_name}</p>
              <p className="text-xs text-muted-foreground">
                {toPersianDigits(String(a.file_size ?? 0))} بایت
                {a.mime_type ? ` · ${a.mime_type}` : ""}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={busy === a.id}
                onClick={() => void restore(a.id, a.file_name)}
              >
                <RotateCcw className="ml-2 h-4 w-4" />
                بازگردانی
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={busy === a.id}
                onClick={() => void purge(a.id, a.file_name)}
              >
                حذف دائمی
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
