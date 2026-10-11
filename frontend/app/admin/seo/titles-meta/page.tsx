"use client";

/**
 * Titles & Meta — default title/description templates per content type
 * (Rank Math's "Titles & Meta" panel).
 *
 * One template per content type, rendered by the backend's variable engine
 * (`seo.application.template_engine`). The variable catalog comes from the
 * API (not a hardcoded list here) so the UI and the renderer cannot drift —
 * offering a variable the renderer does not know would silently produce
 * empty meta tags.
 *
 * Live preview: the panel renders each template against sample values
 * server-side, so what the operator sees is exactly what the storefront will
 * emit, not a client-side approximation.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2, RotateCcw, Save, Wand2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import {
  fetchTitlesMeta,
  previewTitlesMeta,
  updateTitlesMeta,
  type TitlesMeta,
  type TitlesMetaTemplateEntry,
} from "@/lib/api/seo";

interface Draft {
  title: string;
  description: string;
}

export default function TitlesMetaPage() {
  const { toast } = useToast();
  const [meta, setMeta] = useState<TitlesMeta | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [separator, setSeparator] = useState("|");
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchTitlesMeta();
      setMeta(data);
      setSeparator(data.separator);
      const next: Record<string, Draft> = {};
      for (const t of data.templates) {
        next[t.content_type] = {
          title: t.title_template,
          description: t.description_template,
        };
      }
      setDrafts(next);
    } catch {
      toast({ title: "دریافت قالب‌های عنوان ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Live preview per row, debounced — one server round trip per pause, not
  // per keystroke (the renderer is authoritative; approximating it in the
  // client is how previews start lying).
  const debounceRef = useState<{ t: ReturnType<typeof setTimeout> | null }>({
    t: null,
  })[0];
  const schedulePreview = useCallback(
    (contentType: string, template: string) => {
      if (debounceRef.t) clearTimeout(debounceRef.t);
      debounceRef.t = setTimeout(async () => {
        try {
          const { rendered } = await previewTitlesMeta({
            template,
            content_type: contentType,
          });
          setPreviews((prev) => ({ ...prev, [contentType]: rendered }));
        } catch {
          // Preview failure is cosmetic; leave the last preview in place.
        }
      }, 500);
    },
    [debounceRef],
  );

  useEffect(() => {
    if (!meta) return;
    for (const t of meta.templates) {
      schedulePreview(t.content_type, drafts[t.content_type]?.title ?? "");
    }
    // Only on load: typing schedules its own preview.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [meta]);

  const setDraft = (contentType: string, field: keyof Draft, value: string) => {
    setDrafts((prev) => {
      const existing = prev[contentType] ?? { title: "", description: "" };
      return { ...prev, [contentType]: { ...existing, [field]: value } };
    });
    if (field === "title") schedulePreview(contentType, value);
  };

  const resetRow = (entry: TitlesMetaTemplateEntry) => {
    setDrafts((prev) => ({
      ...prev,
      [entry.content_type]: {
        title: entry.title_template,
        description: entry.description_template,
      },
    }));
    schedulePreview(entry.content_type, entry.title_template);
  };

  const save = async () => {
    setSaving(true);
    try {
      const templates: Record<string, { title: string; description: string }> = {};
      for (const [ct, draft] of Object.entries(drafts)) {
        templates[ct] = { title: draft.title, description: draft.description };
      }
      const data = await updateTitlesMeta({ separator, templates });
      setMeta(data);
      toast({ title: "قالب‌های عنوان و توضیحات ذخیره شد" });
    } catch {
      toast({ title: "ذخیره قالب‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const variableHelp = useMemo(() => meta?.variables ?? [], [meta]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold">عنوان و توضیحات پیش‌فرض</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            قالب پیش‌فرض هر نوع محتوا. متغیرها با علامت درصد نوشته می‌شوند، مثل{" "}
            <code dir="ltr" className="mx-1">%title% %sep% %sitename%</code>
          </p>
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? (
            <Loader2 className="h-4 w-4 ms-1 animate-spin" />
          ) : (
            <Save className="h-4 w-4 ms-1" />
          )}
          {saving ? "در حال ذخیره..." : "ذخیره همه"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">جداکننده عنوان</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Input
              value={separator}
              onChange={(e) => setSeparator(e.target.value)}
              className="w-24"
              dir="ltr"
            />
            <span className="text-xs text-muted-foreground">
              بین عنوان و نام سایت قرار می‌گیرد (متغیر <code dir="ltr">%sep%</code>).
            </span>
          </div>
        </CardContent>
      </Card>

      {meta?.templates.map((entry) => (
        <Card key={entry.content_type}>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">{entry.label}</CardTitle>
              <div className="flex items-center gap-2">
                {entry.title_customized && (
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary">
                    سفارشی‌شده
                  </span>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => resetRow(entry)}
                  title="بازگردانی به مقدار ذخیره‌شده"
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-2">
                <Label>قالب عنوان</Label>
                <Input
                  dir="ltr"
                  value={drafts[entry.content_type]?.title ?? ""}
                  onChange={(e) => setDraft(entry.content_type, "title", e.target.value)}
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-2">
                <Label>قالب توضیحات</Label>
                <Input
                  dir="ltr"
                  value={drafts[entry.content_type]?.description ?? ""}
                  onChange={(e) =>
                    setDraft(entry.content_type, "description", e.target.value)
                  }
                  className="font-mono text-xs"
                />
              </div>
            </div>
            {previews[entry.content_type] && (
              <div className="rounded-lg border border-border bg-muted/30 p-3">
                <div className="mb-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <Wand2 className="h-3 w-3" />
                  پیش‌نمایش با مقادیر نمونه
                </div>
                <div className="text-sm font-medium text-primary">
                  {previews[entry.content_type]}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      ))}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">متغیرهای قابل استفاده</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {variableHelp.map((v) => (
              <div
                key={v.name}
                className="flex items-center justify-between rounded-lg border border-border px-3 py-2"
              >
                <div>
                  <code dir="ltr" className="text-xs font-bold text-primary">
                    {v.name}
                  </code>
                  <div className="text-[11px] text-muted-foreground">{v.label}</div>
                </div>
                <span className="text-[11px] text-muted-foreground" dir="auto">
                  {v.example}
                </span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
