"use client";

import { useState } from "react";
import { CheckCircle2, Database, Search, Sparkles, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { UnavailableValue } from "@/components/admin/async-state";
import { useAdminMutation } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";
import {
  analyzeSeo,
  fetchSeoMeta,
  upsertSeoMeta,
  type SeoAnalysis,
  type SeoGradeColor,
  type SeoMeta,
} from "@/lib/api/seo";

/**
 * Resource types the metadata API understands. The backend accepts these
 * spellings and generates defaults from the domain model when a resource has
 * no metadata row yet, so an operator can load the generated version, adjust
 * it, and save.
 */
const RESOURCE_TYPES = [
  { value: "product", label: "کالا" },
  { value: "category", label: "دسته‌بندی" },
  { value: "blog_post", label: "نوشته وبلاگ" },
];

const EMPTY_META = {
  title: "",
  description: "",
  canonicalUrl: "",
  ogTitle: "",
  ogDescription: "",
  ogImage: "",
  schemaMarkup: "",
};

/**
 * SEO scoring tool (admin).
 *
 * Runs the backend's 0–100 scoring engine against a draft — the same engine
 * behind Rank Math / Yoast-style checks, tuned for Persian text. Two things
 * this page is explicit about, because getting either wrong would mislead an
 * editor:
 *
 * 1. The engine is a PURE function. It reads no database and saves nothing.
 *    The score describes the text in the boxes, not the live page, and is not
 *    stored — re-running it later does not show a history.
 * 2. Nothing here publishes or edits content. It is a checker you run BEFORE
 *    saving elsewhere; the page says so rather than implying a save.
 */

const GRADE_TONE: Record<SeoGradeColor, string> = {
  green: "text-emerald-700 dark:text-emerald-400",
  yellow: "text-amber-700 dark:text-amber-400",
  red: "text-destructive",
};

const GRADE_BAR: Record<SeoGradeColor, string> = {
  green: "bg-emerald-500",
  yellow: "bg-amber-500",
  red: "bg-destructive",
};

const EMPTY_FORM = {
  title: "",
  focusKeyword: "",
  slug: "",
  metaDescription: "",
  content: "",
  imagesCount: "",
  internalLinksCount: "",
};

export default function AdminSeoPage() {
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [analysis, setAnalysis] = useState<SeoAnalysis | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const runMutation = useAdminMutation();

  // ── Metadata tab ──
  const [resourceType, setResourceType] = useState("product");
  const [resourceId, setResourceId] = useState("");
  const [meta, setMeta] = useState({ ...EMPTY_META });
  const [metaLoaded, setMetaLoaded] = useState(false);
  const [metaError, setMetaError] = useState<string | null>(null);
  const [metaNote, setMetaNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadMeta = async () => {
    setMetaError(null);
    setMetaNote(null);
    if (!resourceId.trim()) {
      setMetaError("شناسه منبع (UUID) الزامی است.");
      return;
    }
    setBusy(true);
    const result = await runMutation(
      () => fetchSeoMeta(resourceType, resourceId.trim()),
      { fallbackError: "دریافت فراداده سئو ناموفق بود" },
    );
    if (result.ok) {
      const loaded: SeoMeta | null = result.data;
      if (loaded) {
        setMeta({
          title: loaded.title ?? "",
          description: loaded.description ?? "",
          canonicalUrl: loaded.canonicalUrl ?? "",
          ogTitle: loaded.ogTitle ?? "",
          ogDescription: loaded.ogDescription ?? "",
          ogImage: loaded.ogImage ?? "",
          schemaMarkup: loaded.schemaMarkup
            ? JSON.stringify(loaded.schemaMarkup, null, 2)
            : "",
        });
        setMetaNote(
          "مقادیر بارگذاری‌شده ممکن است مقادیر پیش‌فرض تولیدشده توسط سرور باشند، نه رکورد ذخیره‌شده. تنها با ذخیره‌کردن، رکورد ایجاد می‌شود.",
        );
      } else {
        // No metadata row for this resource yet.
        setMeta({ ...EMPTY_META });
        setMetaNote(
          "برای این منبع هنوز فراداده‌ای ثبت نشده است؛ سرور مقادیر پیش‌فرض را از خود منبع تولید می‌کند.",
        );
      }
      setMetaLoaded(true);
    } else {
      setMetaError(result.error);
      setMetaLoaded(false);
    }
    setBusy(false);
  };

  const saveMeta = async () => {
    setMetaError(null);
    setMetaNote(null);

    // The schema field is JSON-LD. Sending malformed JSON would be rejected by
    // the server, so it is parsed here where the operator can be told exactly
    // what is wrong with it.
    let schemaMarkup: Record<string, unknown> | null = null;
    if (meta.schemaMarkup.trim()) {
      try {
        const parsed = JSON.parse(meta.schemaMarkup);
        if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
          setMetaError("ساختار JSON باید یک شیء باشد، نه آرایه یا مقدار ساده.");
          return;
        }
        schemaMarkup = parsed as Record<string, unknown>;
      } catch {
        setMetaError("ساختار JSON معتبر نیست؛ پیش از ذخیره آن را اصلاح کنید.");
        return;
      }
    }

    setBusy(true);
    const result = await runMutation(
      () =>
        upsertSeoMeta(resourceType, resourceId.trim(), {
          title: meta.title.trim() || null,
          description: meta.description.trim() || null,
          canonicalUrl: meta.canonicalUrl.trim() || null,
          ogTitle: meta.ogTitle.trim() || null,
          ogDescription: meta.ogDescription.trim() || null,
          ogImage: meta.ogImage.trim() || null,
          schemaMarkup,
        }),
      { fallbackError: "ذخیره فراداده سئو ناموفق بود" },
    );
    if (result.ok) {
      setMetaNote("فراداده سئو ذخیره شد.");
    } else {
      setMetaError(result.error);
    }
    setBusy(false);
  };

  const run = async () => {
    setFormError(null);

    // The engine scores whatever it is given, so an empty submission would
    // return a confidently-worded report about nothing. Require the two fields
    // every check depends on.
    if (!form.title.trim()) {
      setFormError("عنوان سئو الزامی است؛ ارزیابی بر پایه آن انجام می‌شود.");
      return;
    }
    if (!form.content.trim()) {
      setFormError("متن محتوا الزامی است؛ بیشترین سهم امتیاز به محتوا تعلق دارد.");
      return;
    }

    setRunning(true);
    const result = await runMutation(
      () =>
        analyzeSeo({
          title: form.title,
          content: form.content,
          focusKeyword: form.focusKeyword,
          slug: form.slug,
          metaDescription: form.metaDescription,
          imagesCount: form.imagesCount.trim()
            ? Number.parseInt(form.imagesCount, 10)
            : null,
          internalLinksCount: form.internalLinksCount.trim()
            ? Number.parseInt(form.internalLinksCount, 10)
            : null,
        }),
      { fallbackError: "اجرای تحلیل سئو ناموفق بود" },
    );
    if (result.ok) {
      setAnalysis(result.data);
    } else {
      setFormError(result.error);
      // A failed run must not leave a stale report on screen looking current.
      setAnalysis(null);
    }
    setRunning(false);
  };

  const passed = analysis?.checklist.filter((c) => c.passed).length ?? 0;
  const total = analysis?.checklist.length ?? 0;

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Search className="h-5 w-5 text-primary" />
            تحلیل و فراداده سئو
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            امتیازدهی ۰ تا ۱۰۰ روی متن پیش از انتشار، و ثبت فراداده سئو
            (canonical، Open Graph و داده ساختاریافته) برای هر کالا، دسته‌بندی یا
            نوشته.
          </p>
        </div>
      </section>

      <Tabs defaultValue="analyze" dir="rtl">
        <TabsList>
          <TabsTrigger value="analyze">تحلیل امتیاز</TabsTrigger>
          <TabsTrigger value="metadata">فراداده منبع</TabsTrigger>
        </TabsList>

        <TabsContent value="metadata" className="space-y-4">
          <div
            role="note"
            className="flex items-start gap-2.5 rounded-lg border border-amber-500/40 bg-amber-500/5 p-3 text-[11px] leading-relaxed text-amber-800 dark:text-amber-300"
          >
            <Database className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              این بخش برخلاف تب تحلیل، <span className="font-bold">ذخیره</span>{" "}
              می‌کند و روی صفحه عمومی همان منبع اثر می‌گذارد.
            </span>
          </div>

          <Card className="space-y-4 p-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label htmlFor="meta-type">نوع منبع</Label>
                <select
                  id="meta-type"
                  className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={resourceType}
                  onChange={(e) => setResourceType(e.target.value)}
                >
                  {RESOURCE_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label htmlFor="meta-id">شناسه منبع (UUID)</Label>
                <Input
                  id="meta-id"
                  value={resourceId}
                  onChange={(e) => setResourceId(e.target.value)}
                  dir="ltr"
                  className="font-mono"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" disabled={busy} onClick={() => void loadMeta()}>
                {busy ? "..." : "بارگذاری فراداده"}
              </Button>
              <Button disabled={busy || !metaLoaded} onClick={() => void saveMeta()}>
                ذخیره
              </Button>
            </div>

            {metaError && (
              <p role="alert" className="text-sm text-destructive">
                {metaError}
              </p>
            )}
            {metaNote && (
              <p role="status" className="text-[11px] leading-5 text-muted-foreground">
                {metaNote}
              </p>
            )}
          </Card>

          <Card className="space-y-4 p-4">
            <div className="space-y-1.5">
              <Label htmlFor="meta-title">عنوان سئو</Label>
              <Input
                id="meta-title"
                value={meta.title}
                onChange={(e) => setMeta({ ...meta, title: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="meta-desc">توضیح متا</Label>
              <Textarea
                id="meta-desc"
                rows={2}
                value={meta.description}
                onChange={(e) => setMeta({ ...meta, description: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="meta-canonical">نشانی کانونیکال</Label>
              <Input
                id="meta-canonical"
                value={meta.canonicalUrl}
                onChange={(e) => setMeta({ ...meta, canonicalUrl: e.target.value })}
                dir="ltr"
                className="font-mono"
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="meta-og-title">عنوان Open Graph</Label>
                <Input
                  id="meta-og-title"
                  value={meta.ogTitle}
                  onChange={(e) => setMeta({ ...meta, ogTitle: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="meta-og-image">تصویر Open Graph</Label>
                <Input
                  id="meta-og-image"
                  value={meta.ogImage}
                  onChange={(e) => setMeta({ ...meta, ogImage: e.target.value })}
                  dir="ltr"
                  className="font-mono"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="meta-og-desc">توضیح Open Graph</Label>
              <Textarea
                id="meta-og-desc"
                rows={2}
                value={meta.ogDescription}
                onChange={(e) =>
                  setMeta({ ...meta, ogDescription: e.target.value })
                }
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="meta-schema">
                داده ساختاریافته (JSON-LD)
              </Label>
              <Textarea
                id="meta-schema"
                rows={8}
                value={meta.schemaMarkup}
                onChange={(e) =>
                  setMeta({ ...meta, schemaMarkup: e.target.value })
                }
                dir="ltr"
                className="font-mono text-xs"
                placeholder='{"@context": "https://schema.org", "@type": "Product"}'
              />
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="analyze" className="space-y-6">
          <div
            role="note"
            className="flex items-start gap-2.5 rounded-lg border border-blue-500/30 bg-blue-500/5 p-3 text-[11px] leading-relaxed text-blue-900 dark:text-blue-200"
          >
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span>
              این ابزار فقط <span className="font-bold">تحلیل</span> می‌کند: هیچ
              محتوایی ذخیره، ویرایش یا منتشر نمی‌شود و امتیاز در سرور نگه‌داری
              نمی‌گردد. گزارش، توصیف متن همین فرم است؛ برای اعمال تغییرات از صفحه
              ویرایش همان محتوا استفاده کنید.
            </span>
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card className="space-y-4 p-4">
          <div className="space-y-1.5">
            <Label htmlFor="seo-title">عنوان سئو</Label>
            <Input
              id="seo-title"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="seo-keyword">کلمه کلیدی کانونی</Label>
            <Input
              id="seo-keyword"
              value={form.focusKeyword}
              onChange={(e) => setForm({ ...form, focusKeyword: e.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="seo-slug">اسلاگ / نشانی</Label>
            <Input
              id="seo-slug"
              value={form.slug}
              onChange={(e) => setForm({ ...form, slug: e.target.value })}
              dir="ltr"
              className="font-mono"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="seo-meta">توضیح متا</Label>
            <Textarea
              id="seo-meta"
              rows={2}
              value={form.metaDescription}
              onChange={(e) =>
                setForm({ ...form, metaDescription: e.target.value })
              }
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="seo-content">متن محتوا</Label>
            <Textarea
              id="seo-content"
              rows={10}
              value={form.content}
              onChange={(e) => setForm({ ...form, content: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="seo-images">تعداد تصاویر</Label>
              <Input
                id="seo-images"
                type="number"
                min="0"
                value={form.imagesCount}
                onChange={(e) =>
                  setForm({ ...form, imagesCount: e.target.value })
                }
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="seo-links">تعداد پیوندها</Label>
              <Input
                id="seo-links"
                type="number"
                min="0"
                value={form.internalLinksCount}
                onChange={(e) =>
                  setForm({ ...form, internalLinksCount: e.target.value })
                }
                dir="ltr"
              />
            </div>
          </div>

          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}

          <div className="flex gap-2">
            <Button onClick={() => void run()} disabled={running}>
              {running ? "در حال تحلیل..." : "تحلیل سئو"}
            </Button>
            <Button
              variant="outline"
              disabled={running}
              onClick={() => {
                setForm({ ...EMPTY_FORM });
                setAnalysis(null);
                setFormError(null);
              }}
            >
              پاک کردن فرم
            </Button>
          </div>
        </Card>

        <div className="space-y-4">
          {!analysis ? (
            <Card className="flex min-h-[200px] flex-col items-center justify-center p-8 text-center">
              <Search className="mb-3 h-10 w-10 opacity-30" aria-hidden="true" />
              <p className="text-sm text-muted-foreground">
                برای مشاهده امتیاز، فرم را پر کنید و «تحلیل سئو» را بزنید.
              </p>
            </Card>
          ) : (
            <>
              <Card className="space-y-2 p-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-xs text-muted-foreground">امتیاز کل</span>
                  <span
                    className={`text-3xl font-bold ${GRADE_TONE[analysis.gradeColor]}`}
                  >
                    {analysis.score === null ? (
                      <UnavailableValue reason="امتیاز گزارش نشد." />
                    ) : (
                      toPersianDigits(String(analysis.score))
                    )}
                  </span>
                </div>
                {analysis.score !== null && (
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={`h-full ${GRADE_BAR[analysis.gradeColor]}`}
                      style={{ width: `${analysis.score}%` }}
                    />
                  </div>
                )}
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                  <span>
                    وضعیت:{" "}
                    <span className={`font-bold ${GRADE_TONE[analysis.gradeColor]}`}>
                      {analysis.grade}
                    </span>
                  </span>
                  {analysis.wordCount !== null && (
                    <span>
                      تعداد کلمات: {toPersianDigits(String(analysis.wordCount))}
                    </span>
                  )}
                  {analysis.keywordDensity !== null && (
                    <span>
                      چگالی کلمه کلیدی:{" "}
                      {toPersianDigits(analysis.keywordDensity.toFixed(2))}٪
                    </span>
                  )}
                  {total > 0 && (
                    <span>
                      بررسی‌های موفق: {toPersianDigits(`${passed} از ${total}`)}
                    </span>
                  )}
                </div>
              </Card>

              {analysis.recommendations.length > 0 && (
                <Card className="space-y-2 p-4">
                  <h3 className="text-sm font-bold">پیشنهادهای بهبود</h3>
                  <ul className="space-y-1 text-xs leading-6 text-muted-foreground">
                    {analysis.recommendations.map((rec) => (
                      <li key={rec} className="flex gap-2">
                        <span className="text-primary">•</span>
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              <Card className="p-0">
                <h3 className="border-b border-border px-4 py-3 text-sm font-bold">
                  چک‌لیست بررسی‌ها
                </h3>
                {analysis.checklist.length === 0 ? (
                  <p className="p-4 text-xs text-muted-foreground">
                    موتور تحلیل هیچ بررسی‌ای بازنگرداند؛ این به‌معنای نبود ایراد
                    نیست، بلکه نبود گزارش است.
                  </p>
                ) : (
                  <ul className="divide-y divide-border/60">
                    {analysis.checklist.map((item) => (
                      <li
                        key={item.title}
                        className="flex items-start gap-2.5 px-4 py-3"
                      >
                        {item.passed ? (
                          <CheckCircle2
                            className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400"
                            aria-hidden="true"
                          />
                        ) : (
                          <XCircle
                            className="mt-0.5 h-4 w-4 shrink-0 text-destructive"
                            aria-hidden="true"
                          />
                        )}
                        <div className="min-w-0 space-y-0.5">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-medium text-foreground">
                              {item.title}
                            </span>
                            {item.category && (
                              <Badge variant="outline" className="text-[10px]">
                                {item.category}
                              </Badge>
                            )}
                            {item.points !== null && (
                              <span className="font-mono text-[10px] text-muted-foreground">
                                {toPersianDigits(String(item.points))}
                                {item.maxPoints !== null
                                  ? ` / ${toPersianDigits(String(item.maxPoints))}`
                                  : ""}
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] leading-5 text-muted-foreground">
                            {item.message}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            </>
          )}
          </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
