"use client";

/**
 * Permalink settings card — WordPress options-permalink.php parity.
 *
 * One screen, three site_options rows: permalink_structure (radio presets +
 * a custom field, exactly WP's «تنظیمات عمومی»), category_base and tag_base
 * (WP's «دلخواه» box). The saved structure drives the storefront's blog URLs
 * (lib/permalinks.ts + the routing middleware); the two bases rename the
 * blog taxonomy archives. Product and product-category URLs are fixed routes
 * of the store (/products/<slug>) and are shown as information, not settings.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Link2, Loader2, RefreshCw, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioCard } from "@/components/ui/radio-card";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import {
  DEFAULT_ROUTING,
  baseSegmentProblems,
  validateStructure,
} from "@/lib/permalinks";

/** WP's radio list, adapted to the structures this store's resolver supports. */
const PRESETS: Array<{ label: string; value: string; example: string }> = [
  {
    label: "پیش‌فرض فروشگاه",
    value: "/blog/%postname%/",
    example: "/blog/example-post/",
  },
  {
    label: "ماه و نام",
    value: "/%year%/%monthnum%/%postname%/",
    example: "/2026/05/example-post/",
  },
  {
    label: "روز، ماه و نام",
    value: "/%year%/%monthnum%/%day%/%postname%/",
    example: "/2026/05/24/example-post/",
  },
  {
    label: "عددی",
    value: "/archives/%post_id%",
    example: "/archives/123",
  },
  {
    label: "نام نوشته",
    value: "/%postname%/",
    example: "/example-post/",
  },
];

const CUSTOM = "__custom__";

export function PermalinkSettingsCard() {
  const { toast } = useToast();
  const [structure, setStructure] = useState(DEFAULT_ROUTING.permalink_structure);
  const [categoryBase, setCategoryBase] = useState(DEFAULT_ROUTING.category_base);
  const [tagBase, setTagBase] = useState(DEFAULT_ROUTING.tag_base);
  const [productBase, setProductBase] = useState(DEFAULT_ROUTING.product_base);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadFailed(false);
    try {
      const all = await siteOptionsApi.list();
      setStructure(all.permalink_structure || DEFAULT_ROUTING.permalink_structure);
      setCategoryBase(all.category_base ?? DEFAULT_ROUTING.category_base);
      setTagBase(all.tag_base ?? DEFAULT_ROUTING.tag_base);
      setProductBase(all.product_base || DEFAULT_ROUTING.product_base);
    } catch {
      setLoadFailed(true);
      toast({ title: "بارگذاری تنظیمات پیوند ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedRadio = useMemo(
    () => PRESETS.find((p) => p.value === structure)?.value ?? CUSTOM,
    [structure],
  );

  const structureErrors = useMemo(() => validateStructure(structure), [structure]);
  // The DEFAULT bases ("category"/"tag") are root-reserved words for other
  // reasons (the shop archive /category/<slug>), yet they are the canonical
  // blog defaults — `allow` whitelists each field's own default value.
  const categoryBaseErrors = useMemo(
    () => baseSegmentProblems(categoryBase, DEFAULT_ROUTING.category_base),
    [categoryBase],
  );
  const tagBaseErrors = useMemo(
    () => baseSegmentProblems(tagBase, DEFAULT_ROUTING.tag_base),
    [tagBase],
  );

  const productBaseErrors = useMemo(() => {
    const problems = baseSegmentProblems(productBase, DEFAULT_ROUTING.product_base);
    if (problems.length > 0) return problems;
    const v = productBase.trim().toLowerCase();
    if (!v || v === DEFAULT_ROUTING.product_base) return [];
    // /<base>/<slug> would be ambiguous — the taxonomy rewrite runs first.
    for (const [other, label] of [
      [categoryBase.trim().toLowerCase(), "پیشوند دسته‌بندی"],
      [tagBase.trim().toLowerCase(), "پیشوند برچسب"],
    ] as const) {
      if (other && other === v) {
        return [`پایهٔ کالا نمی‌تواند با ${label} یکی باشد؛ آدرس‌ها دوسگمنتی یکسان می‌شوند.`];
      }
    }
    return [];
  }, [productBase, categoryBase, tagBase]);

  // Same ambiguity, other direction: the category and tag archives share the
  // /<base>/<slug> shape, so the two bases must differ.
  const taxonomyClash = useMemo(() => {
    const cat = categoryBase.trim().toLowerCase();
    const tag = tagBase.trim().toLowerCase();
    return cat && tag && cat === tag
      ? "پیشوند دسته‌بندی و پیشوند برچسب نمی‌توانند یکی باشند."
      : null;
  }, [categoryBase, tagBase]);

  const canSave =
    structureErrors.length === 0 &&
    categoryBaseErrors.length === 0 &&
    tagBaseErrors.length === 0 &&
    productBaseErrors.length === 0 &&
    !taxonomyClash;

  const origin = typeof window === "undefined" ? "" : window.location.origin;

  const handleSave = async () => {
    if (!canSave) {
      toast({
        title: "تنظیمات پیوند معتبر نیست",
        description:
          structureErrors[0] ??
          categoryBaseErrors[0] ??
          tagBaseErrors[0] ??
          productBaseErrors[0] ??
          taxonomyClash ??
          undefined,
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      await Promise.all([
        siteOptionsApi.set("permalink_structure", structure),
        siteOptionsApi.set("category_base", categoryBase.trim() || null),
        siteOptionsApi.set("tag_base", tagBase.trim() || null),
        siteOptionsApi.set("product_base", productBase.trim() || DEFAULT_ROUTING.product_base),
      ]);
      toast({
        title: "پیوندهای یکتا ذخیره شد",
        description: "آدرس‌های تازه بلافاصله در فروشگاه و فید اعمال می‌شوند.",
      });
    } catch {
      toast({ title: "ذخیره پیوندهای یکتا ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <Card className="flex min-h-40 items-center justify-center p-6">
        <span className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          در حال بارگذاری تنظیمات پیوند…
        </span>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* ── تنظیمات عمومی (WP «Common settings») ─────────────────────────── */}
      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
          <h2 className="text-base font-bold">تنظیمات عمومی</h2>
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>

        {loadFailed && (
          <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
            بارگذاری ناموفق بود؛ قبل از ذخیره یک بار دیگر تلاش کنید تا مقادیر فعلی
            سرور خوانده شود.
          </p>
        )}

        <div className="space-y-2">
          {PRESETS.map((preset) => (
            <RadioCard
              key={preset.value}
              name="permalink_structure"
              value={preset.value}
              checked={selectedRadio === preset.value}
              onChange={() => setStructure(preset.value)}
            >
              <div className="min-w-0">
                <p className="text-sm font-medium">{preset.label}</p>
                <code className="mt-0.5 block text-xs text-muted-foreground" dir="ltr">
                  {origin}
                  <span className="text-foreground/80">{preset.example}</span>
                </code>
              </div>
            </RadioCard>
          ))}

          {/* ساختار سفارشی — WP's free-form field */}
          <RadioCard
            name="permalink_structure"
            value={CUSTOM}
            checked={selectedRadio === CUSTOM}
            onChange={() => setStructure("/blog/%year%/%monthnum%/%postname%/")}
          >
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">ساختار سفارشی</p>
              <Input
                value={structure}
                onChange={(e) => setStructure(e.target.value)}
                dir="ltr"
                className="mt-2 font-mono text-xs"
                placeholder="/blog/%year%/%postname%/"
                aria-label="ساختار سفارشی پیوند یکتا"
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                تگ‌های مجاز:{" "}
                <code dir="ltr">
                  %postname% %post_id% %year% %monthnum% %day% %category% %author%
                </code>
              </p>
              {structureErrors.length > 0 && (
                <ul className="mt-1.5 space-y-0.5">
                  {structureErrors.map((err) => (
                    <li key={err} className="text-[11px] text-destructive">
                      {err}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </RadioCard>
        </div>

        <p className="mt-4 text-[11px] leading-5 text-muted-foreground">
          با تغییر ساختار، آدرس نوشته‌های وبلاگ، فید RSS و نقشهٔ سایت از همین ساختار
          ساخته می‌شوند و مسیرهای قبلی <code dir="ltr">/blog/&lt;slug&gt;</code> همچنان
          به نوشتهٔ درست می‌رسند. ساختار «ساده» (<code dir="ltr">?p=123</code>) در این
          فروشگاه پشتیبانی نمی‌شود، و آدرس محصولات ثابت است:{" "}
          <code dir="ltr">/products/&lt;slug&gt;</code>
        </p>
      </Card>

      {/* ── دلخواه (WP «Optional») ───────────────────────────────────────── */}
      <Card className="p-6">
        <h2 className="mb-4 border-b border-border pb-3 text-base font-bold">دلخواه</h2>
        <p className="mb-4 text-xs text-muted-foreground">
          اگر می‌خواهید آدرس آرشیو دسته‌ها یا برچسب‌های وبلاگ پیشوند دیگری داشته باشد،
          آن را اینجا وارد کنید. مثلاً نوشتن «topic» آدرس دسته‌ها را به{" "}
          <code dir="ltr">/topic/&lt;slug&gt;</code> تغییر می‌دهد.
        </p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="category-base">پیشوند دسته‌بندی</Label>
            <Input
              id="category-base"
              value={categoryBase}
              onChange={(e) => setCategoryBase(e.target.value)}
              dir="ltr"
              className="font-mono text-xs"
              placeholder="category"
              aria-invalid={categoryBaseErrors.length > 0}
            />
            <p className="text-[11px] text-muted-foreground" dir="ltr">
              {origin}/{categoryBase.trim() || "category"}/…
            </p>
            {categoryBaseErrors.map((err) => (
              <p key={err} className="text-[11px] text-destructive">
                {err}
              </p>
            ))}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="tag-base">پیشوند برچسب</Label>
            <Input
              id="tag-base"
              value={tagBase}
              onChange={(e) => setTagBase(e.target.value)}
              dir="ltr"
              className="font-mono text-xs"
              placeholder="tag"
              aria-invalid={tagBaseErrors.length > 0}
            />
            <p className="text-[11px] text-muted-foreground" dir="ltr">
              {origin}/{tagBase.trim() || "tag"}/…
            </p>
            {tagBaseErrors.map((err) => (
              <p key={err} className="text-[11px] text-destructive">
                {err}
              </p>
            ))}
          </div>
        </div>
        {taxonomyClash && (
          <p className="mt-3 text-[11px] text-destructive">{taxonomyClash}</p>
        )}
      </Card>

      {/* ── پیوندهای یکتای کالا (WooCommerce «Product permalinks») ────────── */}
      <Card className="p-6">
        <h2 className="mb-4 border-b border-border pb-3 text-base font-bold">
          پیوندهای یکتای کالا
        </h2>
        <p className="mb-4 text-xs leading-5 text-muted-foreground">
          پایهٔ آدرس صفحات کالا و لیست فروشگاه. با انتخاب پایهٔ سفارشی، آدرس‌ها به
          شکل <code dir="ltr">/پایه/&lt;slug&gt;</code> در دسترس می‌شوند و مسیر اصلی{" "}
          <code dir="ltr">/products/&lt;slug&gt;</code> هم همیشه کار می‌کند.
        </p>
        <div className="space-y-2">
          <RadioCard
            name="product_base"
            value="products"
            checked={productBase.trim().toLowerCase() === DEFAULT_ROUTING.product_base}
            onChange={() => setProductBase(DEFAULT_ROUTING.product_base)}
          >
            <div>
              <p className="text-sm font-medium">پیش‌فرض فروشگاه</p>
              <code className="mt-0.5 block text-xs text-muted-foreground" dir="ltr">
                {origin}/products/example-product/
              </code>
            </div>
          </RadioCard>
          <RadioCard
            name="product_base"
            value="custom"
            checked={productBase.trim().toLowerCase() !== DEFAULT_ROUTING.product_base}
            onChange={() => setProductBase("shop")}
          >
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">پایهٔ سفارشی</p>
              <Input
                value={productBase}
                onChange={(e) => setProductBase(e.target.value)}
                dir="ltr"
                className="mt-2 font-mono text-xs"
                placeholder="shop"
                aria-label="پایهٔ سفارشی آدرس کالا"
                aria-invalid={productBaseErrors.length > 0}
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground" dir="ltr">
                {origin}/{productBase.trim() || "shop"}/example-product/
              </p>
              {productBaseErrors.map((err) => (
                <p key={err} className="text-[11px] text-destructive">
                  {err}
                </p>
              ))}
            </div>
          </RadioCard>
        </div>
      </Card>

      <div className="flex justify-end">
        <Button
          onClick={() => void handleSave()}
          disabled={saving || loadFailed || !canSave}
        >
          {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
          {saving ? "در حال ذخیره…" : "ذخیره پیوندهای یکتا"}
        </Button>
      </div>

      <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Link2 className="h-3.5 w-3.5" />
        معادل WordPress → تنظیمات ← پیوندهای یکتا (options-permalink.php)
      </p>
    </div>
  );
}
