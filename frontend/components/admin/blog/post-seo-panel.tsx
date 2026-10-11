"use client";

/**
 * SEO panel for the blog editor — Rank Math's "SEO" box, adapted.
 *
 * The site had a full SEO engine (scoring, metadata table, admin page at
 * /admin/seo) but the blog editor showed none of it: a writer had to leave
 * the editor, find the SEO page, and retype the article's title there to get
 * a score. The focus keyword had nowhere to be stored at all. This panel
 * brings the three things a writer needs next to the content:
 *
 * 1. The focus keyword field (stored in `seo_metadata.focus_keyword`).
 * 2. SEO title and meta description overrides.
 * 3. A live score with the failing checks, computed by the same backend
 *    analyzer the /admin/seo page uses (`POST /seo/analyze`) — no second
 *    scoring implementation to drift.
 *
 * The panel only exists for a SAVED post: `seo_metadata` keys on the post's
 * UUID, which does not exist before the first save. A new post shows a note
 * to save first, the same rule the terms picker follows.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Search, Sparkles } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { SchemaBuilder } from "@/components/admin/blog/schema-builder";
import {
  analyzeSeo,
  fetchSeoMeta,
  upsertSeoMeta,
  scoreBand,
  type SeoAnalysis,
  type SeoCheckItem,
} from "@/lib/api/seo";

interface PostSeoPanelProps {
  /** Null while the post is unsaved; nothing can be stored yet. */
  postId: string | null;
  /** Live editor values — the analyzer scores what the writer sees. */
  title: string;
  content: string;
  slug: string;
  excerpt: string;
}

/** Strip tags for the analyzer's word count (it counts text, not markup). */
function textLength(html: string): number {
  return html.replace(/<[^>]+>/g, " ").trim().length;
}

export function PostSeoPanel({ postId, title, content, slug, excerpt }: PostSeoPanelProps) {
  const { toast } = useToast();
  const [keyword, setKeyword] = useState("");
  const [seoTitle, setSeoTitle] = useState("");
  const [seoDescription, setSeoDescription] = useState("");
  // The canonical field existed in the API (read/write) and the storefront
  // consumed it, but the panel had no input for it (SEO audit F-18).
  const [canonicalUrl, setCanonicalUrl] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [analysis, setAnalysis] = useState<SeoAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [savingMeta, setSavingMeta] = useState(false);
  // Advanced/Social tab state (Rank Math's Advanced + Social tabs). The
  // robots tri-state matters: null = no explicit choice, true = force
  // noindex/nofollow, false = force index/follow.
  const [robotsNoindex, setRobotsNoindex] = useState<boolean | null>(null);
  const [robotsNofollow, setRobotsNofollow] = useState<boolean | null>(null);
  const [ogType, setOgType] = useState("");
  const [twitterTitle, setTwitterTitle] = useState("");
  const [twitterDescription, setTwitterDescription] = useState("");
  const [twitterImage, setTwitterImage] = useState("");
  const [tab, setTab] = useState<"general" | "social" | "advanced" | "schema">(
    "general",
  );
  // Guards the initial load: the effect re-runs when editor fields change,
  // and re-reading the stored metadata on every keystroke would overwrite
  // what the writer just typed.
  const metaLoadedFor = useRef<string | null>(null);

  // Load stored SEO metadata once per post.
  useEffect(() => {
    if (!postId) {
      metaLoadedFor.current = null;
      setKeyword("");
      setSeoTitle("");
      setSeoDescription("");
      setCanonicalUrl("");
      setRobotsNoindex(null);
      setRobotsNofollow(null);
      setOgType("");
      setTwitterTitle("");
      setTwitterDescription("");
      setTwitterImage("");
      setLoaded(true);
      return;
    }
    if (metaLoadedFor.current === postId) return;
    metaLoadedFor.current = postId;
    setLoaded(false);
    (async () => {
      try {
        const meta = await fetchSeoMeta("blog_post", postId);
        setKeyword(meta?.focusKeyword ?? "");
        setSeoTitle(meta?.title ?? "");
        setSeoDescription(meta?.description ?? "");
        setCanonicalUrl(meta?.canonicalUrl ?? "");
        setRobotsNoindex(meta?.robotsNoindex ?? null);
        setRobotsNofollow(meta?.robotsNofollow ?? null);
        setOgType(meta?.ogType ?? "");
        setTwitterTitle(meta?.twitterTitle ?? "");
        setTwitterDescription(meta?.twitterDescription ?? "");
        setTwitterImage(meta?.twitterImage ?? "");
      } catch {
        // A failed read must not block the editor; the panel starts blank
        // and saving will still work (the upsert creates the row).
        setKeyword("");
        setSeoTitle("");
        setSeoDescription("");
        setCanonicalUrl("");
        setRobotsNoindex(null);
        setRobotsNofollow(null);
        setOgType("");
        setTwitterTitle("");
        setTwitterDescription("");
        setTwitterImage("");
      } finally {
        setLoaded(true);
      }
    })();
  }, [postId]);

  const runAnalysis = useCallback(async () => {
    if (!keyword.trim()) {
      setAnalysis(null);
      return;
    }
    setAnalyzing(true);
    try {
      const result = await analyzeSeo({
        title: seoTitle.trim() || title,
        content,
        focusKeyword: keyword.trim(),
        slug,
        metaDescription: seoDescription.trim() || excerpt,
      });
      setAnalysis(result);
    } catch {
      // The analyzer is a read-only computation; a failure leaves the last
      // result on screen rather than blanking the panel.
    } finally {
      setAnalyzing(false);
    }
  }, [keyword, seoTitle, title, content, slug, seoDescription, excerpt]);

  // Re-analyze when the inputs settle. 800 ms keeps a typing writer from
  // firing a request per keystroke.
  useEffect(() => {
    if (!loaded || !keyword.trim()) return;
    const t = setTimeout(() => void runAnalysis(), 800);
    return () => clearTimeout(t);
  }, [loaded, runAnalysis, keyword]);

  const saveMeta = async () => {
    if (!postId) return;
    setSavingMeta(true);
    try {
      await upsertSeoMeta("blog_post", postId, {
        title: seoTitle.trim() || null,
        description: seoDescription.trim() || null,
        canonicalUrl: canonicalUrl.trim() || null,
        focusKeyword: keyword.trim() || null,
        robotsNoindex,
        robotsNofollow,
        ogType: ogType.trim() || null,
        twitterTitle: twitterTitle.trim() || null,
        twitterDescription: twitterDescription.trim() || null,
        twitterImage: twitterImage.trim() || null,
        // Persist the last computed score so the admin list's score column
        // can read it without re-running the analyzer per row.
        seoScore: analysis?.score ?? null,
      });
      toast({ title: "تنظیمات سئو ذخیره شد" });
    } catch {
      toast({
        title: "ذخیره سئو ناموفق بود",
        variant: "destructive",
      });
    } finally {
      setSavingMeta(false);
    }
  };

  const band = analysis && analysis.score !== null ? scoreBand(analysis.score) : null;
  const failedChecks: SeoCheckItem[] = useMemo(
    () => (analysis ? analysis.checklist.filter((c) => !c.passed).slice(0, 6) : []),
    [analysis],
  );

  if (!postId) {
    return (
      <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
        برای تنظیمات سئو، ابتدا نوشته را ذخیره کنید.
      </p>
    );
  }

  if (!loaded) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        در حال خواندن تنظیمات سئو...
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-2xl border border-border p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-bold">
          <Search className="h-4 w-4 text-emerald-600" />
          تنظیمات سئو
        </p>
        {band && (
          <Badge
            variant="outline"
            className={
              band.color === "green"
                ? "border-emerald-600 text-emerald-700"
                : band.color === "yellow"
                  ? "border-amber-500 text-amber-700"
                  : "border-red-500 text-red-700"
            }
          >
            {analyzing ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
            {analysis?.score} / 100 · {band.label}
          </Badge>
        )}
      </div>

      {/* Tabs: General / Social / Advanced — Rank Math's editor layout. */}
      <div className="flex gap-1 border-b border-border pb-2">
        {(
          [
            ["general", "عمومی"],
            ["social", "شبکه‌های اجتماعی"],
            ["advanced", "پیشرفته"],
            ["schema", "اسکیما"],
          ] as const
        ).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
              tab === key
                ? "bg-foreground/10 text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "general" && (
        <>
          <div className="grid gap-2">
            <Label htmlFor="seo-focus">کلمه کلیدی کانونی (Focus Keyword)</Label>
            <Input
              id="seo-focus"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="مثلاً: خرید یوسی پابجی"
            />
            <p className="text-[11px] text-muted-foreground">
              امتیاز سئو بر اساس این عبارت سنجیده می‌شود.
            </p>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="seo-title">عنوان سئو (SEO Title)</Label>
            <Input
              id="seo-title"
              value={seoTitle}
              onChange={(e) => setSeoTitle(e.target.value)}
              placeholder={title}
            />
            <p className="text-[11px] text-muted-foreground">
              اگر خالی بماند، عنوان نوشته استفاده می‌شود.
            </p>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="seo-description">توضیحات متا (Meta Description)</Label>
            <Textarea
              id="seo-description"
              value={seoDescription}
              onChange={(e) => setSeoDescription(e.target.value)}
              rows={3}
              placeholder={excerpt || "توضیح کوتاه برای نتایج جستجو..."}
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="seo-canonical">کنونیکال (Canonical URL)</Label>
            <Input
              id="seo-canonical"
              dir="ltr"
              value={canonicalUrl}
              onChange={(e) => setCanonicalUrl(e.target.value)}
              placeholder="خالی = آدرس خود مقاله"
            />
            <p className="text-[11px] text-muted-foreground">
              اگر خالی بماند، خودِ آدرس مقاله به‌عنوان کنونیکال استفاده می‌شود.
              برای محتوای کپی‌شده، آدرس نسخهٔ اصلی را این‌جا بگذارید.
            </p>
          </div>

          {analysis && failedChecks.length > 0 && (
            <div className="space-y-2 rounded-xl bg-muted/40 p-3">
              <p className="flex items-center gap-1.5 text-xs font-bold text-amber-700">
                <Sparkles className="h-3.5 w-3.5" />
                بهبودهای پیشنهادی
              </p>
              <ul className="space-y-1.5">
                {failedChecks.map((c, i) => (
                  <li key={i} className="flex items-start gap-1.5 text-[11px] leading-relaxed">
                    <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                    <span>
                      <span className="font-medium">{c.title}:</span> {c.message}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {tab === "social" && (
        <>
          <p className="text-[11px] text-muted-foreground">
            اگر خالی بمانند، مقادیر Open Graph و سپس فیلدهای نوشته استفاده می‌شوند.
          </p>
          <div className="grid gap-2">
            <Label htmlFor="seo-og-type">نوع Open Graph</Label>
            <Input
              id="seo-og-type"
              dir="ltr"
              value={ogType}
              onChange={(e) => setOgType(e.target.value)}
              placeholder="article"
            />
            <p className="text-[11px] text-muted-foreground">
              مثل article، website، product، video.other — خالی یعنی مقدار پیش‌فرض.
            </p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="seo-tw-title">عنوان توییتر</Label>
            <Input
              id="seo-tw-title"
              value={twitterTitle}
              onChange={(e) => setTwitterTitle(e.target.value)}
              placeholder={seoTitle || title}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="seo-tw-desc">توضیحات توییتر</Label>
            <Textarea
              id="seo-tw-desc"
              value={twitterDescription}
              onChange={(e) => setTwitterDescription(e.target.value)}
              rows={2}
              placeholder={seoDescription || excerpt}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="seo-tw-image">تصویر توییتر (URL)</Label>
            <Input
              id="seo-tw-image"
              dir="ltr"
              value={twitterImage}
              onChange={(e) => setTwitterImage(e.target.value)}
              placeholder="/uploads/media/..."
            />
          </div>
        </>
      )}

      {tab === "schema" && (
        <SchemaBuilder resourceType="blog_post" resourceId={postId} />
      )}

      {tab === "advanced" && (
        <>
          <div className="grid gap-3">
            <div className="grid gap-2">
              <Label htmlFor="seo-robots-index">ایندکس شدن</Label>
              <select
                id="seo-robots-index"
                value={robotsNoindex === null ? "default" : robotsNoindex ? "noindex" : "index"}
                onChange={(e) => {
                  const v = e.target.value;
                  setRobotsNoindex(v === "default" ? null : v === "noindex");
                }}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="default">پیش‌فرض سایت</option>
                <option value="index">ایندکس شود (index)</option>
                <option value="noindex">ایندکس نشود (noindex)</option>
              </select>
              <p className="text-[11px] text-muted-foreground">
                noindex این نوشته را از نتایج جستجو حذف می‌کند و از سایت‌مپ هم کنار می‌گذارد.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="seo-robots-follow">دنبال کردن لینک‌ها</Label>
              <select
                id="seo-robots-follow"
                value={
                  robotsNofollow === null ? "default" : robotsNofollow ? "nofollow" : "follow"
                }
                onChange={(e) => {
                  const v = e.target.value;
                  setRobotsNofollow(v === "default" ? null : v === "nofollow");
                }}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                <option value="default">پیش‌فرض سایت</option>
                <option value="follow">دنبال شود (follow)</option>
                <option value="nofollow">دنبال نشود (nofollow)</option>
              </select>
            </div>
          </div>
        </>
      )}

      <button
        type="button"
        onClick={() => void saveMeta()}
        disabled={savingMeta}
        className="rounded-md border border-input px-3 py-1.5 text-xs font-medium disabled:opacity-60"
      >
        {savingMeta ? "در حال ذخیره..." : "ذخیره تنظیمات سئو"}
      </button>
    </div>
  );
}
