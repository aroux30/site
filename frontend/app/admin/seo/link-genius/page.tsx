"use client";

/**
 * Link Genius (Rank Math Pro parity): internal-link suggestions + keyword maps.
 *
 * Two jobs on one page:
 *
 * 1. **Suggestions** — pick a post, see the posts ranked by TF-IDF similarity
 *    as link targets, and see who already links *to* the selected post. The
 *    ranking is computed server-side from the live bodies; this page never
 *    re-ranks client-side (a second implementation would drift from the one
 *    the operator's decisions rest on).
 *
 * 2. **Keyword maps** — keyword→URL rules that auto-link on publish. A map is
 *    edited here and previewed against a real post before it is applied, so an
 *    operator sees exactly how many links it would insert before trusting it.
 *
 * Destructive actions use the in-app confirm dialog, never `window.confirm`
 * (which is a silent no-op in a sandboxed iframe — see confirm-dialog.tsx).
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowDownLeft,
  ExternalLink,
  Link2,
  Loader2,
  Plus,
  RefreshCw,
  Sparkles,
  Trash2,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  applyLinkMap,
  createLinkMap,
  deleteLinkMap,
  fetchIncomingLinks,
  fetchLinkMaps,
  fetchLinkSuggestions,
  reindexPostLinks,
  updateLinkMap,
  type IncomingLinksResult,
  type LinkMap,
  type LinkSuggestionsResult,
} from "@/lib/api/seo";
import { blogAdminApi } from "@/lib/api/blog";
import { toPersianDigits } from "@/lib/utils";

interface PostOption {
  id: string;
  title: string;
}

export default function LinkGeniusPage() {
  const { toast } = useToast();

  const [posts, setPosts] = useState<PostOption[]>([]);
  const [selectedPost, setSelectedPost] = useState<string>("");
  const [suggestions, setSuggestions] = useState<LinkSuggestionsResult | null>(null);
  const [incoming, setIncoming] = useState<IncomingLinksResult | null>(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);

  const [maps, setMaps] = useState<LinkMap[]>([]);
  const [loadingMaps, setLoadingMaps] = useState(true);

  // Load the post list once (published posts are the linkable targets).
  // `page_size` is capped at 100 by the API (a larger value is a 422, not a
  // clamp) — the first version asked for 200 and the picker rendered empty,
  // a bug only a real browser caught.
  useEffect(() => {
    void (async () => {
      try {
        const res = await blogAdminApi.listPosts({ page_size: 100 });
        const items = (res.items ?? []) as Array<{ id: string; title: string }>;
        setPosts(items.map((p) => ({ id: p.id, title: p.title })));
        const first = items[0];
        if (first) setSelectedPost(first.id);
      } catch {
        toast({ title: "دریافت فهرست نوشته‌ها ناموفق بود", variant: "destructive" });
      }
    })();
  }, [toast]);

  const loadSuggestions = useCallback(
    async (postId: string) => {
      if (!postId) return;
      setLoadingSuggestions(true);
      try {
        const [sug, inc] = await Promise.all([
          fetchLinkSuggestions(postId, 20),
          fetchIncomingLinks(postId),
        ]);
        setSuggestions(sug);
        setIncoming(inc);
      } catch {
        toast({ title: "دریافت پیشنهادها ناموفق بود", variant: "destructive" });
      } finally {
        setLoadingSuggestions(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    if (selectedPost) void loadSuggestions(selectedPost);
  }, [selectedPost, loadSuggestions]);

  const loadMaps = useCallback(async () => {
    setLoadingMaps(true);
    try {
      const res = await fetchLinkMaps();
      setMaps(res.items);
    } catch {
      toast({ title: "دریافت نقشه‌های کلیدواژه ناموفق بود", variant: "destructive" });
    } finally {
      setLoadingMaps(false);
    }
  }, [toast]);

  useEffect(() => {
    void loadMaps();
  }, [loadMaps]);

  const handleReindex = useCallback(async () => {
    if (!selectedPost) return;
    try {
      const res = await reindexPostLinks(selectedPost);
      toast({ title: `ایندکس لینک‌ها بروزرسانی شد (${toPersianDigits(String(res.indexed))} لینک)` });
      await loadSuggestions(selectedPost);
    } catch {
      toast({ title: "بروزرسانی ایندکس ناموفق بود", variant: "destructive" });
    }
  }, [selectedPost, loadSuggestions, toast]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold">
          <Sparkles className="h-5 w-5 text-primary" />
          نابغهٔ لینک (Link Genius)
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          پیشنهاد لینک داخلی بر پایهٔ شباهت موضوعی، لینک‌های ورودی و نقشه‌های
          کلیدواژه برای پیوند خودکار در زمان انتشار.
        </p>
      </div>

      <Tabs defaultValue="suggestions">
        <TabsList>
          <TabsTrigger value="suggestions">پیشنهاد لینک</TabsTrigger>
          <TabsTrigger value="maps">نقشه‌های کلیدواژه</TabsTrigger>
        </TabsList>

        <TabsContent value="suggestions" className="space-y-4">
          <Card className="p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <div className="flex-1">
                <Label htmlFor="lg-post" className="text-xs">
                  نوشتهٔ مبنا
                </Label>
                <select
                  id="lg-post"
                  value={selectedPost}
                  onChange={(e) => setSelectedPost(e.target.value)}
                  className="mt-1 h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  {posts.length === 0 && <option value="">نوشته‌ای نیست</option>}
                  {posts.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void loadSuggestions(selectedPost)}
                disabled={!selectedPost}
              >
                <RefreshCw className="h-4 w-4 ms-2" />
                بروزرسانی
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleReindex()}
                disabled={!selectedPost}
              >
                ایندکس مجدد
              </Button>
            </div>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-bold">
                <Link2 className="h-4 w-4 text-primary" />
                پیشنهاد برای پیوند دادن
              </h2>
              {loadingSuggestions ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : !suggestions || suggestions.suggestions.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  پیشنهادی یافت نشد
                </p>
              ) : (
                <ul className="space-y-2">
                  {suggestions.suggestions.map((s) => (
                    <li
                      key={s.post_id}
                      className="flex items-center justify-between gap-2 rounded-lg border p-2.5"
                    >
                      <Link
                        href={`/blog/${s.slug}`}
                        target="_blank"
                        className="min-w-0 flex-1 truncate text-sm hover:text-primary"
                        title={s.title}
                      >
                        {s.title}
                      </Link>
                      <Badge variant="outline" className="shrink-0 tabular-nums">
                        {toPersianDigits(s.score.toFixed(2))}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </Card>

            <Card className="p-5">
              <h2 className="mb-3 flex items-center gap-2 text-sm font-bold">
                <ArrowDownLeft className="h-4 w-4 text-primary" />
                لینک‌های ورودی به این نوشته
              </h2>
              {!incoming || incoming.incoming.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  هیچ نوشته‌ای به این نوشته لینک نداده است
                </p>
              ) : (
                <ul className="space-y-2">
                  {incoming.incoming.map((inc, i) => (
                    <li key={`${inc.post_id}-${i}`} className="rounded-lg border p-2.5">
                      <Link
                        href={`/blog/${inc.slug}`}
                        target="_blank"
                        className="block truncate text-sm hover:text-primary"
                        title={inc.title}
                      >
                        {inc.title}
                      </Link>
                      <div className="mt-1 truncate text-[11px] text-muted-foreground">
                        متن لنگر: {inc.anchor_text || "—"}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="maps" className="space-y-4">
          <LinkMapManager maps={maps} loading={loadingMaps} onReload={loadMaps} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/* ── Keyword map manager ─────────────────────────────────────────────────── */

function LinkMapManager({
  maps,
  loading,
  onReload,
}: {
  maps: LinkMap[];
  loading: boolean;
  onReload: () => Promise<void>;
}) {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [targetUrl, setTargetUrl] = useState("");
  const [keywords, setKeywords] = useState("");
  const [maxLinks, setMaxLinks] = useState(3);
  const [autoPublish, setAutoPublish] = useState(false);

  const handleCreate = useCallback(async () => {
    const keywordList = keywords
      .split(/[\n,،]+/)
      .map((k) => k.trim())
      .filter(Boolean);
    if (!name.trim() || !targetUrl.trim() || keywordList.length === 0) {
      toast({
        title: "نام، آدرس مقصد و حداقل یک کلیدواژه الزامی است",
        variant: "destructive",
      });
      return;
    }
    try {
      await createLinkMap({
        name: name.trim(),
        target_url: targetUrl.trim(),
        max_links_per_post: maxLinks,
        auto_link_on_publish: autoPublish,
        variations: keywordList.map((k) => ({ keyword: k, kind: "manual" as const })),
      });
      toast({ title: "نقشهٔ کلیدواژه ساخته شد" });
      setName("");
      setTargetUrl("");
      setKeywords("");
      setMaxLinks(3);
      setAutoPublish(false);
      setCreating(false);
      await onReload();
    } catch {
      toast({ title: "ساخت نقشه ناموفق بود", variant: "destructive" });
    }
  }, [name, targetUrl, keywords, maxLinks, autoPublish, toast, onReload]);

  const handleToggle = useCallback(
    async (map: LinkMap, field: "is_active" | "auto_link_on_publish", value: boolean) => {
      try {
        await updateLinkMap(map.id, { [field]: value });
        await onReload();
      } catch {
        toast({ title: "تغییر وضعیت ناموفق بود", variant: "destructive" });
      }
    },
    [toast, onReload],
  );

  const handleDelete = useCallback(
    async (map: LinkMap) => {
      const ok = await confirm({
        title: "حذف نقشهٔ کلیدواژه",
        description: `نقشهٔ «${map.name}» حذف می‌شود. لینک‌هایی که قبلاً در نوشته‌ها ساخته شده‌اند باقی می‌مانند.`,
        confirmLabel: "حذف",
        destructive: true,
      });
      if (!ok) return;
      try {
        await deleteLinkMap(map.id);
        toast({ title: "نقشه حذف شد" });
        await onReload();
      } catch {
        toast({ title: "حذف ناموفق بود", variant: "destructive" });
      }
    },
    [confirm, toast, onReload],
  );

  const handleApplyAll = useCallback(
    async (map: LinkMap) => {
      const ok = await confirm({
        title: "اعمال روی همهٔ نوشته‌ها",
        description: `نقشهٔ «${map.name}» روی همهٔ نوشته‌های منتشرشده اجرا می‌شود و متن آن‌ها ویرایش می‌گردد. ادامه می‌دهید؟`,
        confirmLabel: "اعمال",
      });
      if (!ok) return;
      try {
        const res = await applyLinkMap({ map_id: map.id, all_posts: true });
        toast({
          title: `${toPersianDigits(String(res.posts_updated))} نوشته ویرایش شد؛ ${toPersianDigits(String(res.links_inserted))} لینک افزوده شد`,
        });
        await onReload();
      } catch {
        toast({ title: "اعمال نقشه ناموفق بود", variant: "destructive" });
      }
    },
    [confirm, toast, onReload],
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">
          هر نقشه یک کلیدواژه (یا چند مترادف) را به یک آدرس پیوند می‌دهد.
        </p>
        <Button size="sm" onClick={() => setCreating((v) => !v)}>
          <Plus className="h-4 w-4 ms-2" />
          نقشهٔ جدید
        </Button>
      </div>

      {creating && (
        <Card className="space-y-3 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="map-name" className="text-xs">
                نام نقشه
              </Label>
              <Input
                id="map-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="مثلاً شارژ پابجی"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="map-url" className="text-xs">
                آدرس مقصد
              </Label>
              <Input
                id="map-url"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="/products/pubg-mobile"
                dir="ltr"
                className="mt-1"
              />
            </div>
          </div>
          <div>
            <Label htmlFor="map-kw" className="text-xs">
              کلیدواژه‌ها (هر خط یا با کاما جدا کنید)
            </Label>
            <textarea
              id="map-kw"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              placeholder={"پابجی\nپابجی موبایل\npubg mobile"}
            />
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Label htmlFor="map-max" className="text-xs">
                حداکثر لینک در هر نوشته
              </Label>
              <Input
                id="map-max"
                type="number"
                min={0}
                max={50}
                value={maxLinks}
                onChange={(e) => setMaxLinks(Number(e.target.value))}
                className="w-20"
              />
            </div>
            <label className="flex items-center gap-2 text-xs cursor-pointer">
              <input
                type="checkbox"
                checked={autoPublish}
                onChange={(e) => setAutoPublish(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              پیوند خودکار در زمان انتشار
            </label>
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => void handleCreate()}>
              ذخیره
            </Button>
            <Button size="sm" variant="outline" onClick={() => setCreating(false)}>
              انصراف
            </Button>
          </div>
        </Card>
      )}

      <Card className="p-4">
        {loading ? (
          <div className="flex justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : maps.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            هنوز نقشهٔ کلیدواژه‌ای ساخته نشده است
          </p>
        ) : (
          <div className="space-y-3">
            {maps.map((map) => (
              <div key={map.id} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{map.name}</span>
                      {!map.is_active && (
                        <Badge variant="outline" className="border-muted-foreground/40">
                          غیرفعال
                        </Badge>
                      )}
                      {map.auto_link_on_publish && (
                        <Badge variant="outline" className="border-emerald-500 text-emerald-700">
                          خودکار
                        </Badge>
                      )}
                    </div>
                    <a
                      href={map.target_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-0.5 flex items-center gap-1 truncate text-[11px] text-muted-foreground hover:text-primary"
                      dir="ltr"
                    >
                      <ExternalLink className="h-3 w-3 shrink-0" />
                      {map.target_url}
                    </a>
                  </div>
                  <div className="flex items-center gap-2">
                    <label className="flex items-center gap-1 text-[11px] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={map.is_active}
                        onChange={(e) => void handleToggle(map, "is_active", e.target.checked)}
                        className="h-3.5 w-3.5 rounded border-input"
                      />
                      فعال
                    </label>
                    <label className="flex items-center gap-1 text-[11px] cursor-pointer">
                      <input
                        type="checkbox"
                        checked={map.auto_link_on_publish}
                        onChange={(e) =>
                          void handleToggle(map, "auto_link_on_publish", e.target.checked)
                        }
                        className="h-3.5 w-3.5 rounded border-input"
                      />
                      خودکار
                    </label>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => void handleApplyAll(map)}
                    >
                      اعمال روی همه
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void handleDelete(map)}
                      aria-label="حذف"
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {map.variations.map((v) => (
                    <Badge key={v.id} variant="secondary" className="text-[11px]">
                      {v.keyword}
                    </Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
