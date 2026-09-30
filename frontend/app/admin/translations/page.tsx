"use client";

/**
 * Translation management (i18n admin) — «ترجمه‌ها».
 *
 * Blog translations are typed post relationships ("translation"); CMS page
 * translations share a translation_group. Pick a source item, see its
 * existing translations, link an existing item, or snapshot-duplicate the
 * source into a new draft in the chosen locale.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Languages, Link2, Loader2, Plus, RefreshCw, Unlink } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import {
  translationsApi,
  type AdminListItem,
} from "@/lib/api/translations";

type Kind = "posts" | "pages";

const STATUS_LABELS: Record<string, string> = {
  draft: "پیش‌نویس",
  published: "منتشرشده",
  archived: "بایگانی",
};

export default function TranslationsPage() {
  const { toast } = useToast();
  const [kind, setKind] = useState<Kind>("posts");
  const [items, setItems] = useState<AdminListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [source, setSource] = useState<AdminListItem | null>(null);
  const [links, setLinks] = useState<{ id: string; target: AdminListItem }[]>([]);
  const [linksLoading, setLinksLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [targetId, setTargetId] = useState("");
  const [newLocale, setNewLocale] = useState("en");

  const loadItems = useCallback(
    async (k: Kind) => {
      setLoading(true);
      try {
        setItems(k === "posts" ? await translationsApi.listPosts() : await translationsApi.listPages());
      } catch {
        toast({ title: "بارگذاری فهرست ناموفق بود", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void loadItems(kind);
    setSource(null);
    setLinks([]);
  }, [kind, loadItems]);

  const byId = useMemo(() => new Map(items.map((i) => [i.id, i])), [items]);
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (i) => i.title.toLowerCase().includes(q) || i.slug.toLowerCase().includes(q),
    );
  }, [items, search]);

  const loadLinks = useCallback(
    async (item: AdminListItem) => {
      if (kind !== "posts") {
        // Pages: group members come from the same list.
        const members = items.filter(
          (i) =>
            i.id !== item.id &&
            i.translation_group &&
            i.translation_group === item.translation_group,
        );
        setLinks(members.map((m) => ({ id: m.id, target: m })));
        return;
      }
      setLinksLoading(true);
      try {
        const rels = await translationsApi.listPostRelationships(item.id);
        const translationRels = rels.filter((r) => r.relationship_type === "translation");
        setLinks(
          translationRels
            .map((r) => {
              const otherId =
                r.source_post_id === item.id ? r.target_post_id : r.source_post_id;
              const target = byId.get(otherId);
              return target ? { id: r.id, target } : null;
            })
            .filter((x): x is { id: string; target: AdminListItem } => x !== null),
        );
      } catch {
        toast({ title: "بارگذاری ترجمه‌ها ناموفق بود", variant: "destructive" });
      } finally {
        setLinksLoading(false);
      }
    },
    [kind, items, byId, toast],
  );

  const pickSource = useCallback(
    (item: AdminListItem) => {
      setSource(item);
      setTargetId("");
      void loadLinks(item);
    },
    [loadLinks],
  );

  const linkTarget = useCallback(async () => {
    if (!source || !targetId) return;
    setBusy(true);
    try {
      if (kind === "posts") {
        await translationsApi.linkPosts(source.id, targetId);
      } else {
        await translationsApi.linkPages(source.id, targetId);
        // Re-read the list so translation_group values refresh.
        await loadItems(kind);
      }
      toast({ title: "ترجمه پیوند شد" });
      setTargetId("");
      if (kind === "posts") await loadLinks(source);
    } catch {
      toast({ title: "پیوند ناموفق بود", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  }, [source, targetId, kind, loadItems, loadLinks, toast]);

  const unlink = useCallback(
    async (linkId: string) => {
      if (!source) return;
      setBusy(true);
      try {
        if (kind === "posts") {
          await translationsApi.unlinkPostRelationship(source.id, linkId);
        } else {
          await translationsApi.unlinkPages(source.id, linkId);
          await loadItems(kind);
        }
        toast({ title: "پیوند ترجمه حذف شد" });
        if (kind === "posts") await loadLinks(source);
      } catch {
        toast({ title: "حذف پیوند ناموفق بود", variant: "destructive" });
      } finally {
        setBusy(false);
      }
    },
    [source, kind, loadItems, loadLinks, toast],
  );

  const createTranslation = useCallback(async () => {
    if (!source || kind !== "posts") return;
    setBusy(true);
    try {
      await translationsApi.duplicateAsTranslation(source.id, newLocale);
      toast({
        title: "ترجمه ساخته شد",
        description: "پیش‌نویس جدید در وبلاگ باز کنید و متن را ترجمه کنید",
      });
      await loadItems(kind);
      await loadLinks(source);
    } catch {
      toast({ title: "ساخت ترجمه ناموفق بود", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  }, [source, kind, newLocale, loadItems, loadLinks, toast]);

  const locales = ["fa", "en", "ar"];

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-bold">
            <Languages className="h-5 w-5 text-primary" /> مدیریت ترجمه‌ها
          </h1>
          <p className="text-xs text-muted-foreground">
            محتوای چندزبانه: هر ترجمه یک ردیف مستقل با slug و زبان خودش است
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-border p-1">
          {(["posts", "pages"] as Kind[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setKind(k)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                kind === k ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {k === "posts" ? "مقالات بلاگ" : "صفحات CMS"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
        {/* Source list */}
        <Card className="space-y-3 p-4">
          <div className="flex gap-2">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جستجو در عنوان یا نامک…"
              className="h-9 text-xs"
            />
            <Button variant="outline" size="sm" onClick={() => void loadItems(kind)} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
          <div className="max-h-[520px] space-y-1.5 overflow-y-auto pe-1">
            {filtered.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => pickSource(item)}
                className={`flex w-full items-center justify-between gap-2 rounded-lg border p-2.5 text-start text-xs transition-colors ${
                  source?.id === item.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50"
                }`}
              >
                <span className="line-clamp-1 font-medium">{item.title}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {item.locale && (
                    <Badge variant="outline" className="text-[10px]" dir="ltr">
                      {item.locale}
                    </Badge>
                  )}
                  {item.status && (
                    <span className="text-[10px] text-muted-foreground">
                      {STATUS_LABELS[item.status] ?? item.status}
                    </span>
                  )}
                </span>
              </button>
            ))}
            {!loading && filtered.length === 0 && (
              <p className="py-6 text-center text-xs text-muted-foreground">موردی یافت نشد.</p>
            )}
          </div>
        </Card>

        {/* Link panel */}
        <Card className="space-y-4 p-4">
          {!source ? (
            <p className="py-16 text-center text-xs text-muted-foreground">
              یک مورد از فهرست انتخاب کنید تا ترجمه‌هایش مدیریت شود.
            </p>
          ) : (
            <>
              <div>
                <div className="text-sm font-semibold">{source.title}</div>
                <div className="font-mono text-[11px] text-muted-foreground" dir="ltr">
                  /{source.slug}
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-xs">ترجمه‌های فعلی</Label>
                {linksLoading ? (
                  <p className="flex items-center gap-2 py-3 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" /> در حال بارگذاری…
                  </p>
                ) : links.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                    هنوز ترجمه‌ای پیوند نشده است.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {links.map((link) => (
                      <div
                        key={link.id}
                        className="flex items-center justify-between gap-2 rounded-lg border border-border p-2.5"
                      >
                        <div className="min-w-0">
                          <div className="line-clamp-1 text-xs font-medium">{link.target.title}</div>
                          <div className="font-mono text-[10px] text-muted-foreground" dir="ltr">
                            {link.target.locale ?? "?"} · /{link.target.slug}
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void unlink(link.id)}
                          disabled={busy}
                          aria-label="حذف پیوند"
                        >
                          <Unlink className="h-4 w-4 text-muted-foreground" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-3">
                <Label className="text-xs">پیوند یک مورد موجود به‌عنوان ترجمه</Label>
                <div className="flex gap-2">
                  <select
                    value={targetId}
                    onChange={(e) => setTargetId(e.target.value)}
                    className="h-9 flex-1 rounded-md border border-input bg-background px-2 text-xs"
                  >
                    <option value="">انتخاب کنید…</option>
                    {items
                      .filter((i) => i.id !== source.id)
                      .map((i) => (
                        <option key={i.id} value={i.id}>
                          {i.title} ({i.locale ?? "?"})
                        </option>
                      ))}
                  </select>
                  <Button size="sm" onClick={() => void linkTarget()} disabled={busy || !targetId} className="gap-1.5">
                    <Link2 className="h-3.5 w-3.5" /> پیوند
                  </Button>
                </div>
              </div>

              {kind === "posts" && (
                <div className="space-y-2 rounded-lg border border-border bg-muted/20 p-3">
                  <Label className="text-xs">ساخت ترجمه‌ی جدید از این مقاله</Label>
                  <p className="text-[11px] text-muted-foreground">
                    یک پیش‌نویس کپی می‌شود، زبانش تغییر می‌کند و به‌عنوان ترجمه پیوند می‌خورد.
                  </p>
                  <div className="flex gap-2">
                    <select
                      value={newLocale}
                      onChange={(e) => setNewLocale(e.target.value)}
                      className="h-9 flex-1 rounded-md border border-input bg-background px-2 text-xs"
                    >
                      {locales.map((l) => (
                        <option key={l} value={l}>
                          {l}
                        </option>
                      ))}
                    </select>
                    <Button size="sm" onClick={() => void createTranslation()} disabled={busy} className="gap-1.5">
                      <Plus className="h-3.5 w-3.5" /> ساخت ترجمه
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
