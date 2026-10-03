"use client";

/**
 * UI-string catalogue (admin).
 *
 * The backend has had a string catalogue and its endpoints since the WP parity
 * pass, and nothing rendered it: the admin strings are hardcoded Persian in
 * every component, and `lib/i18n.ts` holds an empty catalogue. So a store that
 * wanted an English or Arabic admin had no screen to translate into and no
 * reader for what it wrote.
 *
 * The screen makes the existing half usable. It does not migrate the codebase:
 * that is a separate, mechanical job, and pretending otherwise would be the
 * kind of claim this project's audits keep finding. What it does is give the
 * strings that *are* in the catalogue a place to be edited and exported.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Languages,
  Save,
  Search,
  Download,
  TriangleAlert,
  Plus,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { settingsI18nApi, type I18nString } from "@/lib/api/settings";
import { toPersianDigits } from "@/lib/utils";

/** Mirrors KNOWN_LOCALES in backend/app/modules/settings/application/i18n_service.py. */
const LOCALES: Array<{ code: string; label: string }> = [
  { code: "fa", label: "فارسی" },
  { code: "en", label: "English" },
  { code: "ar", label: "العربية" },
];

export default function AdminI18nPage() {
  const { toast } = useToast();
  const [strings, setStrings] = useState<I18nString[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [localeFilter, setLocaleFilter] = useState<string>("all");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");
  const [newLocale, setNewLocale] = useState("en");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setStrings(await settingsI18nApi.list());
    } catch {
      toast({ title: "خواندن کاتالوگ ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  /** key per locale, so the grid reads as one row per key. */
  const grouped = useMemo(() => {
    const byKey = new Map<string, Partial<Record<string, I18nString>>>();
    for (const s of strings) {
      const entry = byKey.get(s.key) ?? {};
      entry[s.locale] = s;
      byKey.set(s.key, entry);
    }
    return Array.from(byKey.entries())
      .map(([key, byLocale]) => ({ key, byLocale }))
      .sort((a, b) => a.key.localeCompare(b.key));
  }, [strings]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return grouped.filter(
      (g) =>
        (!q || g.key.toLowerCase().includes(q)) &&
        (localeFilter === "all" ||
          Object.values(g.byLocale).some((s) => s?.locale === localeFilter)),
    );
  }, [grouped, search, localeFilter]);

  /** How many of the three locales each key has. */
  const coverage = useMemo(() => {
    const counts = { complete: 0, partial: 0, total: grouped.length };
    for (const g of grouped) {
      const have = LOCALES.filter((l) => g.byLocale[l.code]).length;
      if (have === LOCALES.length) counts.complete += 1;
      else if (have > 0) counts.partial += 1;
    }
    return counts;
  }, [grouped]);

  const save = async (key: string, locale: string, value: string) => {
    setBusy(true);
    try {
      await settingsI18nApi.upsert({ key, locale, value });
      setDrafts((prev) => {
        const next = { ...prev };
        delete next[`${key}:${locale}`];
        return next;
      });
      await load();
      toast({ title: "رشته ذخیره شد" });
    } catch {
      toast({ title: "ذخیره رشته ناموفق بود", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const add = async () => {
    if (!newKey.trim() || !newValue.trim()) return;
    setBusy(true);
    try {
      await settingsI18nApi.upsert({
        key: newKey.trim(),
        locale: newLocale,
        value: newValue.trim(),
      });
      setNewKey("");
      setNewValue("");
      await load();
      toast({ title: "رشته افزوده شد" });
    } catch {
      toast({ title: "افزودن رشته ناموفق بود", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const exportJson = () => {
    // A JSON file the operator can hand to a translator, and that can be
    // diffed when a word changes. Dumped from the rows on screen rather than
    // re-fetched, so it matches what the editor was showing.
    const out: Record<string, Record<string, string>> = {};
    for (const g of grouped) {
      for (const [locale, s] of Object.entries(g.byLocale)) {
        if (s) (out[g.key] ??= {})[locale] = s.value;
      }
    }
    const blob = new Blob([JSON.stringify(out, null, 2)], {
      type: "application/json;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "i18n-catalogue.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <Languages className="h-5 w-5 text-primary" />
            کاتالوگ رشته‌های رابط
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            رشته‌هایی که در کاتالوگ ثبت شده‌اند. رشته‌هایی که هنوز در کامپوننت‌ها
            فارسی هاردکد شده‌اند باید اول به کاتالوگ مهاجرت داده شوند؛ این صفحه
            فقط رشته‌های موجود را ویرایش می‌کند.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={exportJson} disabled={!grouped.length}>
          <Download className="h-4 w-4" /> خروجی JSON
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <Badge variant="outline">
          {toPersianDigits(String(coverage.total))} کلید
        </Badge>
        <Badge variant="outline" className="border-emerald-500/40 text-emerald-700 dark:text-emerald-400">
          {toPersianDigits(String(coverage.complete))} کامل
        </Badge>
        <Badge variant="outline" className="border-amber-500/40 text-amber-700 dark:text-amber-400">
          {toPersianDigits(String(coverage.partial))} ناقص
        </Badge>
      </div>

      <Card className="flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-[200px] flex-1">
          <Label htmlFor="i18n-search" className="flex items-center gap-1 text-xs">
            <Search className="h-3.5 w-3.5" /> جست‌وجوی کلید
          </Label>
          <Input
            id="i18n-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="common.save"
            dir="ltr"
            className="text-left font-mono text-xs"
          />
        </div>
        <div className="w-40">
          <Label htmlFor="i18n-locale" className="text-xs">زبان</Label>
          <select
            id="i18n-locale"
            value={localeFilter}
            onChange={(e) => setLocaleFilter(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value="all">همه</option>
            {LOCALES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
      </Card>

      <Card className="flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-[180px] flex-1">
          <Label htmlFor="i18n-new-key" className="flex items-center gap-1 text-xs">
            <Plus className="h-3.5 w-3.5" /> کلید جدید
          </Label>
          <Input
            id="i18n-new-key"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            placeholder="checkout.pay_now"
            dir="ltr"
            className="text-left font-mono text-xs"
          />
        </div>
        <div className="w-32">
          <Label htmlFor="i18n-new-locale" className="text-xs">زبان</Label>
          <select
            id="i18n-new-locale"
            value={newLocale}
            onChange={(e) => setNewLocale(e.target.value)}
            className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs"
          >
            {LOCALES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-[200px] flex-1">
          <Label htmlFor="i18n-new-value" className="text-xs">مقدار</Label>
          <Input
            id="i18n-new-value"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            placeholder="متن نمایشی"
          />
        </div>
        <Button size="sm" onClick={() => void add()} disabled={busy || !newKey.trim() || !newValue.trim()}>
          <Plus className="h-4 w-4" /> افزودن
        </Button>
      </Card>

      {loading ? (
        <p className="text-sm text-muted-foreground">در حال خواندن کاتالوگ...</p>
      ) : filtered.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          {grouped.length === 0
            ? "کاتالوگ خالی است. با فرم بالا اولین رشته را اضافه کنید."
            : "رشته‌ای با این فیلتر پیدا نشد."}
        </Card>
      ) : (
        <div className="space-y-3">
          {filtered.map((g) => (
            <Card key={g.key} className="p-4">
              <p className="mb-3 font-mono text-xs font-bold" dir="ltr">
                {g.key}
              </p>
              <div className="grid gap-3 md:grid-cols-3">
                {LOCALES.map((l) => {
                  const existing = g.byLocale[l.code];
                  const draftKey = `${g.key}:${l.code}`;
                  const draft = drafts[draftKey];
                  const value = draft ?? existing?.value ?? "";
                  const dirty = draft !== undefined && draft !== (existing?.value ?? "");
                  return (
                    <div key={l.code} className="grid gap-1.5">
                      <Label className="flex items-center justify-between text-[11px]">
                        <span>{l.label}</span>
                        {existing && !dirty && (
                          <span className="text-[10px] text-muted-foreground">ذخیره شده</span>
                        )}
                        {!existing && (
                          <span className="text-[10px] text-amber-600">ندارد</span>
                        )}
                      </Label>
                      <Textarea
                        value={value}
                        onChange={(e) =>
                          setDrafts((prev) => ({ ...prev, [draftKey]: e.target.value }))
                        }
                        rows={2}
                        dir={l.code === "fa" || l.code === "ar" ? "rtl" : "ltr"}
                        className="text-xs"
                        placeholder="—"
                      />
                      <Button
                        size="sm"
                        variant={dirty ? "default" : "ghost"}
                        onClick={() => void save(g.key, l.code, value)}
                        disabled={busy || !value.trim() || !dirty}
                      >
                        <Save className="h-3.5 w-3.5" /> ذخیره
                      </Button>
                    </div>
                  );
                })}
              </div>
            </Card>
          ))}
        </div>
      )}

      {coverage.partial > 0 && (
        <p className="flex items-start gap-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-800 dark:text-amber-300">
          <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" />
          {toPersianDigits(String(coverage.partial))} کلید فقط در بعضی زبان‌ها ترجمه شده‌اند.
          رشته‌ی مفقود هنگام نمایش، خودِ کلید را نشان می‌دهد — این عمدی است تا
          ترجمه‌ی جاافتاده به‌جای متن خالی دیده شود.
        </p>
      )}
    </div>
  );
}
