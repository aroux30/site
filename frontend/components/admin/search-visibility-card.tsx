"use client";

/**
 * Search-engine visibility card — WordPress's "Search engine visibility"
 * (the `blog_public` option), promoted to the SEO area.
 *
 * The switch lived in three places before this card: Settings → General
 * (`SiteIdentityCard`), Settings → Content & Media (`ContentSettingsCard`) and
 * the backend's SEO status service. Three editors for one option meant a
 * change in one screen left the others showing a stale value. This is now the
 * single write path; the other two screens read it for display only, and the
 * option is documented as SEO-owned.
 *
 * Stored as "1"/"0" (WordPress convention). Anything else is treated as
 * visible — a corrupt value must never silently deindex the store.
 */

import { useCallback, useEffect, useState } from "react";
import { Eye, EyeOff, Loader2, Save, Search } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { useAdminMutation } from "@/lib/api/admin-query";

const OPTION_KEY = "blog_public";

export function SearchVisibilityCard() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [visible, setVisible] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const opts = await siteOptionsApi.list();
      setVisible((opts[OPTION_KEY] ?? "1") !== "0");
    } catch {
      toast({ title: "خواندن وضعیت نمایش ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    const result = await runMutation(
      () => siteOptionsApi.set(OPTION_KEY, visible ? "1" : "0"),
      { fallbackError: "ذخیره وضعیت نمایش ناموفق بود" },
    );
    setSaving(false);
    if (!result.ok) {
      toast({ title: result.error, variant: "destructive" });
      return;
    }
    toast({
      title: visible
        ? "سایت برای موتورهای جست‌وجو مجاز شد"
        : "سایت از موتورهای جست‌وجو پنهان شد",
      description: visible
        ? "دستور noindex از robots.txt برداشته می‌شود."
        : "دستور noindex در robots.txt نوشته می‌شود و صفحات وبلاگ ایندکس نمی‌شوند.",
    });
    await load();
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Search className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">
          نمایش در موتورهای جست‌وجو
        </h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        همان تنظیم وردپرس «Search engine visibility». پنهان‌کردن، دستور
        <code dir="ltr" className="mx-1">noindex</code>
        را در <code dir="ltr">robots.txt</code> می‌نویسد و صفحات وبلاگ را از
        ایندکس خارج می‌کند — ساختار سایت حفظ می‌شود، فقط دیده نمی‌شود.
      </p>

      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        disabled={loading || saving}
        className="flex w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2.5 text-sm disabled:opacity-60"
        aria-pressed={visible}
      >
        <span className={visible ? "" : "text-muted-foreground line-through"}>
          {visible ? "موتورهای جست‌وجو مجاز" : "پنهان از موتورهای جست‌وجو"}
        </span>
        {visible ? (
          <Eye className="h-4 w-4 text-muted-foreground" />
        ) : (
          <EyeOff className="h-4 w-4 text-muted-foreground" />
        )}
      </button>

      {!visible && (
        <p className="mt-3 rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          سایت الان از موتورهای جست‌وجو پنهان است. این حالت برای محیط
          توسعه یا پیش از انتشار درست است، نه برای فروشگاه زنده.
        </p>
      )}

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={loading || saving} className="gap-2">
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? "در حال ذخیره..." : "ذخیره وضعیت نمایش"}
        </Button>
      </div>
    </Card>
  );
}

export default SearchVisibilityCard;
