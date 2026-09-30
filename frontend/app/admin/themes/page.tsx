"use client";

/**
 * Switchable themes (WordPress appearance parity).
 *
 * Each theme is a named token set. Activation copies the tokens into the
 * ``theme`` single type the storefront already consumes (lib/theme.ts), so a
 * switch goes live with no deploy. Builtin presets are seeded server-side;
 * operators can also snapshot the current look as a new theme and delete
 * their own snapshots. The preview pane reloads the storefront in an iframe
 * after every change — correct here, because activation swaps the whole
 * token set. Per-keystroke live preview belongs to the color editor itself
 * (/admin/cms ThemeEditor), which streams tokens through the postMessage
 * bridge in components/shared/theme-preview-bridge.tsx.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Check,
  Loader2,
  Monitor,
  Plus,
  RefreshCw,
  Save,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { themesApi, type SiteTheme, type ThemeTokens } from "@/lib/api/themes";

const COLOR_KEYS = ["primary", "secondary", "accent", "background", "surface", "text", "muted"];

function ThemeSwatches({ tokens }: { tokens: ThemeTokens }) {
  return (
    <div className="flex gap-1.5">
      {COLOR_KEYS.map((key) => (
        <span
          key={key}
          className="h-6 w-6 rounded-full border border-border shadow-sm"
          style={{ backgroundColor: tokens.colors?.[key] ?? "#888" }}
          title={key}
        />
      ))}
    </div>
  );
}

export default function ThemesPage() {
  const { toast } = useToast();
  const [themes, setThemes] = useState<SiteTheme[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [saveName, setSaveName] = useState("");
  const [saving, setSaving] = useState(false);
  const [previewKey, setPreviewKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setThemes(await themesApi.list());
    } catch {
      toast({ title: "بارگذاری پوسته‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const activate = useCallback(
    async (theme: SiteTheme) => {
      setBusyId(theme.id);
      try {
        const res = await themesApi.activate(theme.id);
        toast({ title: res.message || `پوسته «${theme.name}» فعال شد` });
        await load();
        setPreviewKey((k) => k + 1);
      } catch {
        toast({ title: "فعال‌سازی ناموفق بود", variant: "destructive" });
      } finally {
        setBusyId(null);
      }
    },
    [load, toast],
  );

  const remove = useCallback(
    async (theme: SiteTheme) => {
      setBusyId(theme.id);
      try {
        await themesApi.remove(theme.id);
        toast({ title: `پوسته «${theme.name}» حذف شد` });
        await load();
      } catch {
        toast({ title: "حذف ناموفق بود؛ پوسته‌های پیش‌فرض قابل حذف نیستند", variant: "destructive" });
      } finally {
        setBusyId(null);
      }
    },
    [load, toast],
  );

  const saveCurrent = useCallback(async () => {
    const name = saveName.trim();
    if (!name) {
      toast({ title: "نام پوسته را وارد کنید", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      // Snapshot the CURRENT live tokens (the theme single type the
      // storefront renders from) so "save" always captures what is on air.
      const res = await fetch("/api/v1/content/single-types/theme");
      const doc = (await res.json()) as { value?: ThemeTokens };
      const tokens = doc.value ?? { colors: {} };
      await themesApi.create(name, tokens);
      toast({ title: "پوسته ذخیره شد" });
      setSaveName("");
      await load();
    } catch {
      toast({ title: "ذخیره پوسته ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  }, [saveName, load, toast]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold">پوسته‌ها</h1>
          <p className="text-xs text-muted-foreground">
            ظاهر فروشگاه را بدون دیپلوی عوض کنید؛ فعال‌سازی بلافاصله اعمال می‌شود
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> بارگذاری مجدد
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {loading ? (
          <Card className="p-8 text-center text-xs text-muted-foreground md:col-span-2 xl:col-span-3">
            در حال بارگذاری…
          </Card>
        ) : (
          themes.map((theme) => (
            <Card
              key={theme.id}
              className={`space-y-3 p-4 ${theme.is_active ? "border-primary ring-1 ring-primary/30" : ""}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{theme.name}</span>
                  {theme.is_active && (
                    <Badge className="gap-1 text-[10px]">
                      <Check className="h-3 w-3" /> فعال
                    </Badge>
                  )}
                  {theme.is_builtin && (
                    <Badge variant="secondary" className="text-[10px]">
                      پیش‌فرض
                    </Badge>
                  )}
                </div>
              </div>
              <ThemeSwatches tokens={theme.tokens} />
              <div className="flex items-center justify-between gap-2 pt-1">
                <span className="font-mono text-[10px] text-muted-foreground" dir="ltr">
                  {theme.slug}
                </span>
                <div className="flex gap-2">
                  {!theme.is_active && (
                    <Button
                      size="sm"
                      onClick={() => void activate(theme)}
                      disabled={busyId === theme.id}
                      className="gap-1.5"
                    >
                      {busyId === theme.id ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Check className="h-3.5 w-3.5" />
                      )}
                      فعال‌سازی
                    </Button>
                  )}
                  {!theme.is_builtin && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void remove(theme)}
                      disabled={busyId === theme.id}
                      aria-label="حذف پوسته"
                    >
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))
        )}
      </div>

      <Card className="space-y-3 p-5">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Save className="h-4 w-4 text-primary" /> ذخیره‌ی ظاهر فعلی به‌عنوان پوسته
        </div>
        <div className="flex flex-wrap gap-2">
          <Input
            value={saveName}
            onChange={(e) => setSaveName(e.target.value)}
            placeholder="مثلاً «پوسته نوروزی»"
            className="min-w-[200px] flex-1 text-xs"
          />
          <Button size="sm" onClick={() => void saveCurrent()} disabled={saving} className="gap-1.5">
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
            ذخیره
          </Button>
        </div>
        <p className="text-[11px] text-muted-foreground">
          رنگ‌های فعلی فروشگاه (همان که در «محتوا و منوساز → رنگ‌های تم» دیده می‌شود) به‌عنوان یک پوسته‌ی قابل بازگشت ذخیره می‌شود.
        </p>
      </Card>

      <Card className="overflow-hidden p-0">
        <div className="flex items-center gap-2 border-b border-border px-4 py-3 text-sm font-medium">
          <Monitor className="h-4 w-4 text-primary" />
          پیش‌نمایش فروشگاه
          <Button
            variant="ghost"
            size="sm"
            className="ms-auto"
            onClick={() => setPreviewKey((k) => k + 1)}
          >
            <RefreshCw className="h-3.5 w-3.5" /> تازه‌سازی
          </Button>
        </div>
        <iframe
          key={previewKey}
          src="/"
          title="پیش‌نمایش فروشگاه"
          className="h-[560px] w-full border-0 bg-background"
        />
      </Card>
    </div>
  );
}
