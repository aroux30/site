"use client";

/**
 * Local SEO card (Rank Math Pro parity): the store's business profile.
 *
 * The values feed the LocalBusiness JSON-LD the storefront emits — the
 * preview below renders the exact node through the same backend builder, so
 * what the operator sees is what Google reads. Empty fields are omitted from
 * the node, which is why the card says so instead of implying blanks ship.
 */

import { useCallback, useEffect, useState } from "react";
import { Code2, Loader2, MapPin, Save } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import {
  fetchLocalSeo,
  previewLocalSeo,
  saveLocalSeo,
  type LocalSeoData,
} from "@/lib/api/seo";

export function LocalSeoSettingsCard() {
  const { toast } = useToast();
  const [data, setData] = useState<LocalSeoData | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await fetchLocalSeo();
      setData(result);
      setValues(result.values);
      const p = await previewLocalSeo();
      setPreview(p.node);
    } catch {
      toast({ title: "خواندن اطلاعات کسب‌وکار ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      const result = await saveLocalSeo(values);
      setData(result);
      const p = await previewLocalSeo();
      setPreview(p.node);
      toast({ title: "اطلاعات کسب‌وکار ذخیره شد" });
    } catch {
      toast({ title: "ذخیره ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="flex items-center justify-center p-6">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <MapPin className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">سئوی محلی (کسب‌وکار)</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        اطلاعات کسب‌وکار شما در داده‌های ساخت‌یافتهٔ LocalBusiness قرار می‌گیرد — همان
        چیزی که گوگل در نتایج محلی می‌خواند. فیلدهای خالی در اسکیما نمی‌آیند.
      </p>

      <div className="grid gap-4 sm:grid-cols-2">
        {(data?.fields ?? []).map((field) => {
          const isType = field.key === "local_seo_business_type";
          const isCoord =
            field.key === "local_seo_latitude" || field.key === "local_seo_longitude";
          return (
            <div key={field.key} className="space-y-2">
              <Label htmlFor={field.key}>{field.label}</Label>
              {isType ? (
                <select
                  id={field.key}
                  value={values[field.key] ?? ""}
                  onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  {(data?.business_types ?? []).map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={field.key}
                  dir={isCoord ? "ltr" : "auto"}
                  value={values[field.key] ?? ""}
                  onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}
                  placeholder={field.placeholder}
                />
              )}
            </div>
          );
        })}
      </div>

      {preview ? (
        <div className="mt-4 rounded-lg border border-border bg-muted/30 p-3">
          <div className="mb-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <Code2 className="h-3 w-3" />
            پیش‌نمایش اسکیمای LocalBusiness (همان چیزی که گوگل می‌خواند)
          </div>
          <pre
            dir="ltr"
            className="max-h-40 overflow-auto whitespace-pre-wrap break-all text-[10px] leading-relaxed"
          >
            {JSON.stringify(preview, null, 2)}
          </pre>
        </div>
      ) : (
        <p className="mt-4 text-[11px] text-muted-foreground">
          با پرکردن «نام کسب‌وکار» اسکیما ساخته می‌شود؛ بدون نام، نودی منتشر نمی‌شود.
        </p>
      )}

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره اطلاعات کسب‌وکار"}
        </Button>
      </div>
    </Card>
  );
}

export default LocalSeoSettingsCard;
