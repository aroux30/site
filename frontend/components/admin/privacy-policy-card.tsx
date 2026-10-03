"use client";

/**
 * Choose which CMS page is the store's privacy policy.
 *
 * P1 "حریم خصوصی: انتخابگر صفحه‌ی سیاست". The backend half already existed —
 * the ``privacy.policy_page`` option, ``PrivacyPolicyService`` and the public
 * ``/settings/public/privacy-policy`` endpoint — but the only way to set the
 * option was the raw site-options editor, typing a slug by hand. WordPress
 * gives this its own picker in Settings → Privacy, and the option's own
 * docstring says "an operator can publish the policy as an ordinary CMS page
 * and edit it without a deploy" — which was not reachable without knowing the
 * option key.
 *
 * Only published, public pages can be chosen, matching what the service will
 * actually serve: picking a draft would silently fall back to "no policy" and
 * read as the picker not working.
 */

import { useCallback, useEffect, useState } from "react";
import { ExternalLink, FileText, Loader2 } from "lucide-react";

import { cmsPagesAdminApi } from "@/lib/api/content";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";

const POLICY_OPTION_KEY = "privacy.policy_page";

interface PageOption {
  slug: string;
  title: string;
}

export function PrivacyPolicyCard() {
  const { toast } = useToast();
  const [pages, setPages] = useState<PageOption[]>([]);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const [options, list] = await Promise.all([
        siteOptionsApi.list(),
        cmsPagesAdminApi.listPages({ status: "published" }),
      ]);
      setSelected(options[POLICY_OPTION_KEY] ?? "");
      // Keep only the fields the picker needs, and only public pages — a
      // private published page is treated as "no policy" by the service, so
      // offering it would be a choice that cannot work.
      setPages(
        (list?.items ?? [])
          .filter((p) => (p.visibility ?? "public") === "public")
          .map((p) => ({ slug: p.slug, title: p.title })),
      );
    } catch {
      setLoadError("دریافت صفحه‌های منتشرشده ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save(): Promise<void> {
    setSaving(true);
    try {
      // Empty clears the option, which the service reads as "no policy
      // published" — the honest state for a store that has not written one.
      await siteOptionsApi.set(POLICY_OPTION_KEY, selected || null);
      toast({
        title: "صفحهٔ سیاست حریم خصوصی ذخیره شد",
        description: selected
          ? "فرم‌های ثبت‌نام و دیدگاه اکنون به این صفحه پیوند می‌دهند."
          : "هیچ صفحه‌ای انتخاب نشده؛ فرم‌ها بدون پیوند نمایش داده می‌شوند.",
        variant: "success",
      });
    } catch {
      toast({
        title: "ذخیره ناموفق بود",
        description: "لطفاً کمی بعد دوباره تلاش کنید.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <FileText className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">صفحهٔ سیاست حریم خصوصی</h2>
      </div>

      <p className="mb-4 text-xs leading-relaxed text-muted-foreground">
        صفحه‌ای از محتوای سایت که به‌عنوان سیاست حریم خصوصی به فرم‌های ثبت‌نام، سفارش و
        دیدگاه پیوند می‌خورد. فقط صفحه‌های منتشرشده و عمومی قابل انتخاب هستند؛ پیش‌نویس یا
        صفحهٔ خصوصی به‌عنوان «سیاستی وجود ندارد» خوانده می‌شود.
      </p>

      {loadError ? (
        <div className="space-y-2">
          <p className="text-xs text-destructive">{loadError}</p>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            تلاش مجدد
          </Button>
        </div>
      ) : loading ? (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          در حال بارگذاری...
        </div>
      ) : (
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="privacy-policy-page" className="text-xs font-medium">
              صفحهٔ سیاست
            </Label>
            <select
              id="privacy-policy-page"
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              disabled={saving}
            >
              <option value="">— هیچ صفحه‌ای (بدون پیوند) —</option>
              {pages.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.title} (/{p.slug})
                </option>
              ))}
            </select>
            {pages.length === 0 && (
              <p className="text-[11px] text-amber-600 dark:text-amber-400">
                هیچ صفحهٔ منتشرشده و عمومی‌ای وجود ندارد. ابتدا از بخش «برگه‌ها» یک صفحه
                بسازید و منتشر کنید.
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : "ذخیره"}
            </Button>
            {selected && (
              <Button variant="outline" asChild>
                <a
                  href={`/${selected}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  مشاهدهٔ صفحه
                </a>
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
