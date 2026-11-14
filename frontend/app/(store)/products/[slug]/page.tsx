"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import Link from "next/link";
import Image from "next/image";
import {
  fetchCategoryCustomFields,
  fetchProductPricingTiers,
  fetchProductAddonFields,
  computeAddonTotalToman,
  validateSingleAddon,
  type ApiCategoryCustomField,
  type ApiPriceTier,
  type ApiProductAddonField,
  type AddonAnswers,
} from "@/lib/api/services";
import { ProductAddonsForm } from "@/components/store/product-addons-form";
import {
  validateSingleDynamicField,
  validateAllDynamicFields,
} from "@/lib/dynamic-fields";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import {
  Star,
  Heart,
  ShoppingCart,
  Truck,
  Shield,
  RotateCcw,
  Headphones,
  ChevronLeft,
  Minus,
  Plus,
  Check,
  Clock,
  Package,
  AlertCircle,
  MessageSquare,
  Send,
  Loader2,
  CheckCircle2,
  ArrowLeftRight,
  Box,
  Image as ImageIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { playAddToCartChime } from "@/lib/audio-effects";
import { AccessoryRail } from "@/components/store/accessory-rail";
import { VariationSwatches } from "@/components/store/variation-swatches";
import { StarRating } from "@/components/ui/star-rating";
import { ReviewHistogram } from "@/components/store/review-histogram";
import { RecentlyViewed, trackProductView } from "@/components/store/recently-viewed";
import { ClickSpark } from "@/components/ui/click-spark";
import { PulseHeart } from "@/components/ui/pulse-heart";
import { useCart } from "@/hooks/use-cart";
import { useAuth } from "@/hooks/use-auth";
import { useCompareStore } from "@/stores/compare-store";
import { useShopFeatures } from "@/hooks/use-shop-features";
import type { Product } from "@/types/product";
import {
  useProduct,
  useReviews,
  useSubmitReview,
  useToggleWishlist,
} from "@/lib/api/queries";
import {
  checkWishlistApi,
  type ApiProductDetail,
  type ApiProductVariant,
  type ApiReviewItem,
  type ApiReviewStats,
} from "@/lib/api/services";

// Dynamically load 3D Product Inspector on client side
const Product3DViewer = dynamic(
  () => import("@/components/3d/product-viewer-3d").then((mod) => mod.Product3DViewer),
  {
    ssr: false,
    loading: () => (
      <div className="h-[460px] w-full rounded-3xl border border-border bg-card/60 flex items-center justify-center">
        <div className="h-12 w-12 rounded-full border-4 border-primary border-t-transparent animate-spin" />
      </div>
    ),
  }
);

/* -------------------------------------------------------------------------- */
/*                               Fallback Data                                */
/* -------------------------------------------------------------------------- */

/* -------------------------------------------------------------------------- */
/*                               PDP Component                                */
/* -------------------------------------------------------------------------- */

export default function ProductDetailPage() {
  const params = useParams<{ slug: string }>();
  const slug = params?.slug || "";
  const { addToCart } = useCart();
  const { isAuthenticated, isLoading: isAuthLoading } = useAuth();
  const { isInCompare, toggleProduct } = useCompareStore();
  const shopFeatures = useShopFeatures();

  // ---------- TanStack Query: Product ----------
  const {
    data: fetchedProduct,
    isLoading: loading,
    isError: productError,
    refetch: refetchProduct,
  } = useProduct(slug);

  // No fabricated demo product: while loading we show skeletons, on failure
  // an error state, and a missing product never silently appears.
  const product: ApiProductDetail | undefined =
    fetchedProduct && fetchedProduct.name ? fetchedProduct : undefined;

  // Variant & Selection
  const [selectedVariantIndex, setSelectedVariantIndex] = useState(0);
  const [selectedImageIndex, setSelectedImageIndex] = useState(0);
  const [quantity, setQuantity] = useState(1);
  // Variation-swatch selection state: { attribute_slug: value_slug }. Kept in
  // lockstep with selectedVariantIndex — either can drive the other.
  const [swatchSelection, setSwatchSelection] = useState<
    Record<string, string>
  >({});
  const [addedToCartToast, setAddedToCartToast] = useState(false);
  const [addToCartError, setAddToCartError] = useState<string | null>(null);
  // A failed wishlist write must be reported, not silently flipped in the UI —
  // see handleToggleWishlist.
  const [wishlistError, setWishlistError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"gallery" | "3d">("gallery");

  // Sprint 1: tiered pricing + dynamic category fields
  const [tiers, setTiers] = useState<ApiPriceTier[]>([]);
  const [customFieldDefs, setCustomFieldDefs] = useState<ApiCategoryCustomField[]>([]);
  const [fieldAnswers, setFieldAnswers] = useState<Record<string, string>>({});
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // WooCommerce Product Add-ons parity: per-product addon fields (distinct
  // from category fields) with their own answers/errors/price total.
  const [addonDefs, setAddonDefs] = useState<ApiProductAddonField[]>([]);
  const [addonAnswers, setAddonAnswers] = useState<AddonAnswers>({});
  const [addonErrors, setAddonErrors] = useState<Record<string, string>>({});

  const handleAddonChange = (
    fieldKey: string,
    value: string | number | (string | number)[],
  ) => {
    setAddonAnswers((prev) => ({ ...prev, [fieldKey]: value }));
    const def = addonDefs.find((d) => d.field_key === fieldKey);
    const err = def ? validateSingleAddon(def, value) : null;
    setAddonErrors((prev) => {
      const next = { ...prev };
      if (err) next[fieldKey] = err;
      else delete next[fieldKey];
      return next;
    });
  };

  const addonTotalToman = product
    ? computeAddonTotalToman(addonDefs, addonAnswers, quantity)
    : 0;

  const handleFieldChange = (def: ApiCategoryCustomField, value: string) => {
    setFieldAnswers((prev) => ({ ...prev, [def.field_key]: value }));
    const err = validateSingleDynamicField(def, value);
    setFieldErrors((prev) => {
      const next = { ...prev };
      if (err) {
        next[def.field_key] = err;
      } else {
        delete next[def.field_key];
      }
      return next;
    });
  };

  const minQty = Math.max(1, product?.min_order_quantity ?? 1);
  const maxQty = Math.max(minQty, product?.max_order_quantity ?? 10);

  // Keep the stepper inside the server-side bounds when the product loads.
  useEffect(() => {
    if (product) {
      setQuantity(Math.max(minQty, Math.min(quantity, maxQty)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [product?.id, minQty, maxQty]);

  useEffect(() => {
    if (!product?.id) return;
    let cancelled = false;
    fetchProductPricingTiers(product.id).then((t) => {
      if (!cancelled) setTiers(t);
    });
    if (product.category_id) {
      fetchCategoryCustomFields(product.category_id).then((f) => {
        if (!cancelled) setCustomFieldDefs(f);
      });
    }
    fetchProductAddonFields(product.id).then((f) => {
      if (!cancelled) {
        setAddonDefs(f.filter((d) => d.field_type !== "file_upload"));
        // Reset stale answers when navigating between products.
        setAddonAnswers({});
        setAddonErrors({});
      }
    });
    return () => {
      cancelled = true;
    };
  }, [product?.id, product?.category_id]);

  // Track product view for RecentlyViewed shelf
  useEffect(() => {
    if (product) {
      trackProductView(product);
    }
  }, [product]);

  // Wishlist state
  const [isWishlisted, setIsWishlisted] = useState(false);
  const [wishlistLoading, setWishlistLoading] = useState(false);
  const toggleWishlistMutation = useToggleWishlist();

  // ---------- TanStack Query: Reviews ----------
  const {
    data: reviewsData,
    isLoading: reviewsLoading,
  } = useReviews(product?.id ?? ""); // disabled until a product loads

  const reviews: ApiReviewItem[] = reviewsData?.reviews ?? [];

  const reviewStats: ApiReviewStats =
    reviewsData?.stats ??
    ({ average_rating: 0, total_reviews: 0 } as unknown as ApiReviewStats);

  // ---------- TanStack Query: Submit Review Mutation ----------
  const submitReviewMutation = useSubmitReview();

  // Review Form
  const [formRating, setFormRating] = useState(5);
  const [formTitle, setFormTitle] = useState("");
  const [formBody, setFormBody] = useState("");
  const [formPros, setFormPros] = useState("");
  const [formCons, setFormCons] = useState("");
  const [reviewSubmitSuccess, setReviewSubmitSuccess] = useState(false);
  const [reviewSubmitError, setReviewSubmitError] = useState<string | null>(null);

  // Reset variant selection when product changes
  useEffect(() => {
    if (fetchedProduct?.variants && fetchedProduct.variants.length > 0) {
      setSelectedVariantIndex(0);
      setSwatchSelection({});
    }
  }, [fetchedProduct]);

  // Check wishlist status
  const checkWishlistStatus = useCallback(async (productId: string) => {
    if (!isAuthenticated) return;
    // Skip the request entirely when the module is off: it would be refused,
    // and firing a call that is guaranteed to fail turns a hidden feature into
    // a console error.
    if (!shopFeatures.wishlist) return;
    try {
      const status = await checkWishlistApi(productId);
      setIsWishlisted(status.in_wishlist);
    } catch {
      // Ignore if unauthenticated or endpoint error
    }
  }, [isAuthenticated, shopFeatures.wishlist]);

  useEffect(() => {
    if (product?.id) {
      checkWishlistStatus(product.id);
    }
  }, [product?.id, checkWishlistStatus]);

  // Selected variant derivation (below the not-found/error early returns).
  // Retired (is_active=false) variants stay in the list for order history —
  // the selector must never land on one by default, so an index pointing at
  // one resolves to the first ACTIVE variant instead.
  const currentVariant: ApiProductVariant | undefined = (() => {
    if (!product || !product.variants?.length) return undefined;
    const picked = product.variants[selectedVariantIndex];
    if (picked && picked.is_active) return picked;
    return product.variants.find((v) => v.is_active) ?? picked;
  })();

  // ── Variation swatches (woo-variation-swatches parity) ──────────────────
  const variationGroups = product?.variation_attributes ?? [];
  const hasVariationGroups =
    variationGroups.length > 0 &&
    variationGroups.some((g) => g.options.length > 1 || g.options.length === 1);

  // Effective selection: the explicit picks, seeded from the current variant
  // so a fresh page load shows every group's current value instead of blanks.
  const effectiveSelection: Record<string, string> = (() => {
    if (Object.keys(swatchSelection).length > 0) return swatchSelection;
    const attrs = currentVariant?.attributes;
    if (!attrs) return {};
    const seeded: Record<string, string> = {};
    for (const g of variationGroups) {
      const v = attrs[g.slug];
      if (v !== undefined && v !== null) seeded[g.slug] = String(v);
    }
    return seeded;
  })();

  const handleSwatchSelect = (groupSlug: string, optionSlug: string) => {
    if (!product) return;
    const next = { ...effectiveSelection, [groupSlug]: optionSlug };
    setSwatchSelection(next);
    // The swatches only enable combinations that some buyable variant
    // satisfies, so the first full match IS the shopper's pick.
    const idx = product.variants.findIndex((v) => {
      const attrs = v.attributes || {};
      return Object.entries(next).every(
        ([gSlug, vSlug]) => String(attrs[gSlug] ?? "") === vSlug,
      );
    });
    if (idx >= 0) setSelectedVariantIndex(idx);
  };

  // Auto-focus the gallery on the variant's own image (plugin behavior:
  // selecting a variation swaps the main product photo). A variant WITHOUT
  // its own image falls back to the product's primary photo — keeping the
  // previous variant's photo on screen read as if the new option shared it.
  useEffect(() => {
    if (!currentVariant || !product?.images?.length) return;
    const vImg = product.images.find((i) => i.variant_id === currentVariant.id);
    if (vImg) {
      const idx = product.images.findIndex((i) => i.id === vImg.id);
      if (idx >= 0) setSelectedImageIndex(idx);
      return;
    }
    // Fallback target = a PRODUCT-level photo (no variant scope). The
    // variant-scoped image is itself flagged is_primary, so searching by
    // that flag alone landed right back on the previous option's photo.
    const productLevelIdx = product.images.findIndex(
      (i) => !i.variant_id,
    );
    setSelectedImageIndex(productLevelIdx >= 0 ? productLevelIdx : 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentVariant?.id]);

  const currentPrice = currentVariant?.price ?? (product?.min_price || 0);
  const originalPrice =
    currentVariant?.compare_at_price ??
    (product?.max_price && product.max_price > currentPrice
      ? product.max_price
      : undefined);

  const discountPercent =
    originalPrice && originalPrice > currentPrice
      ? Math.round(((originalPrice - currentPrice) / originalPrice) * 100)
      : null;

  // Real availability (Odoo free_qty concept): prefer the live stock count
  // over the is_active flag — a variant can be active but out of stock.
  // WooCommerce parity: when the variant allows backorders, an empty stock
  // reads as "پیش‌خرید" (buyable), not "ناموجود".
  const isOnBackorder =
    currentVariant !== undefined &&
    currentVariant.available != null &&
    currentVariant.available <= 0 &&
    currentVariant.backorder_allowed === true;
  const isOutOfStock =
    currentVariant !== undefined
      ? currentVariant.available != null
        ? currentVariant.available <= 0 && !isOnBackorder
        : // Untracked (no ledger count): availability is the operator's
          // manual وضعیت عرضه on the product, not the absent count —
          // "outofstock" must render ناموجود, null alone never did.
          !currentVariant.is_active || product?.stock_status === "outofstock"
      : false;

  // Karta findPrice (client preview): unit price for the current quantity.
  // The pricing-tiers endpoint returns unit_price in Rial (the admin form
  // beside it is labelled "(ریال)"), while every other price on this page —
  // currentPrice and the cart store — is Toman. Convert at this boundary so
  // the tier value is never mixed with the Toman base price.
  const tierUnitPrice = useMemo(() => {
    const match = tiers.find(
      (t) => quantity >= t.from_qty && (t.to_qty === null || quantity <= t.to_qty)
    );
    return match ? Math.trunc(match.unit_price / 10) : null;
  }, [tiers, quantity]);

  const unitPriceForLine = tierUnitPrice ?? currentPrice;

  // Image list
  const displayImages = useMemo(() => {
    if (product?.images && product.images.length > 0) {
      return product.images.map((img) => img.url);
    }
    if (product?.primary_image_url) {
      return [product.primary_image_url];
    }
    return [];
  }, [product]);

  // Handle Add to Cart
  const handleAddToCart = async () => {
    if (!product) return;
    if (isOutOfStock) return;

    // Dynamic category fields validation: validate all fields and surface per-field errors
    let answeredFields: Record<string, string | number> | undefined = undefined;
    if (customFieldDefs.length > 0) {
      const validation = validateAllDynamicFields(customFieldDefs, fieldAnswers);
      if (!validation.isValid) {
        setFieldErrors(validation.errors);
        const firstErr = Object.values(validation.errors)[0];
        setFieldError(firstErr || "لطفاً خطاهای فیلدهای سفارشی را اصلاح کنید");
        return;
      }
      setFieldError(null);
      setFieldErrors({});
      answeredFields =
        Object.keys(validation.cleanedAnswers).length > 0
          ? validation.cleanedAnswers
          : undefined;
    }

    // Product add-ons: validate each definition; answers cross the cart
    // boundary with a "p:" prefix (checkout splits product add-ons from
    // category fields on that prefix).
    let answeredAddons: Record<string, string | number> | undefined = undefined;
    if (addonDefs.length > 0) {
      const errs: Record<string, string> = {};
      for (const def of addonDefs) {
        if (def.field_type === "heading") continue;
        const err = validateSingleAddon(def, addonAnswers[def.field_key]);
        if (err) errs[def.field_key] = err;
      }
      if (Object.keys(errs).length > 0) {
        setAddonErrors(errs);
        setFieldError("لطفاً فیلدهای سفارشی کالا را کامل کنید");
        return;
      }
      setAddonErrors({});
      const cleaned: Record<string, string | number> = {};
      for (const def of addonDefs) {
        if (def.field_type === "heading") continue;
        const v = addonAnswers[def.field_key];
        if (v === undefined || v === "" || v === null) continue;
        if (Array.isArray(v)) {
          if (v.length > 0) cleaned[def.field_key] = v.join("، ");
        } else {
          cleaned[def.field_key] = v;
        }
      }
      if (Object.keys(cleaned).length > 0) {
        answeredAddons = cleaned;
      }
    }

    let variantTitle = "";
    if (currentVariant?.attributes) {
      variantTitle = Object.entries(currentVariant.attributes)
        .map(([k, v]) => `${k}: ${v}`)
        .join(" | ");
    }

    try {
      await addToCart({
        productId: product.id,
        variantId: currentVariant?.id,
        title: product.name,
        slug: product.slug,
        price: unitPriceForLine,
        originalPrice,
        image: displayImages[0],
        variant: variantTitle || currentVariant?.sku || undefined,
        customFields:
          answeredFields || answeredAddons
            ? {
                ...(answeredFields || {}),
                ...Object.fromEntries(
                  Object.entries(answeredAddons || {}).map(([k, v]) => [`p:${k}`, v]),
                ),
              }
            : undefined,
      });
    } catch (err: unknown) {
      // The store already rolled the optimistic line back — surface why
      // instead of faking a success badge (QA B19: insufficient stock).
      setAddToCartError(
        (err as { message?: string })?.message || "افزودن کالا به سبد ناموفق بود.",
      );
      setTimeout(() => setAddToCartError(null), 4000);
      return;
    }

    playAddToCartChime();
    setAddToCartError(null);
    setAddedToCartToast(true);
    setTimeout(() => setAddedToCartToast(false), 2200);
  };

  // Handle Wishlist Toggle
  const handleToggleWishlist = async () => {
    if (!product) return;
    setWishlistLoading(true);
    setWishlistError(null);
    try {
      await toggleWishlistMutation.mutateAsync({
        productId: product.id,
        isWishlisted,
      });
      setIsWishlisted(!isWishlisted);
    } catch {
      // Do NOT flip the state here. The button's label and icon both read from
      // `isWishlisted`, so flipping on failure told the customer the item was
      // saved to their wishlist when the server had rejected it — and the next
      // page load then silently contradicted it. Leave the state as the server
      // last confirmed it and report the failure instead.
      setWishlistError("ذخیره در علاقه‌مندی‌ها ناموفق بود؛ لطفاً دوباره تلاش کنید.");
    } finally {
      setWishlistLoading(false);
    }
  };

  const inCompare = isInCompare(product?.id ?? "");

  const handleToggleCompare = () => {
    if (!product) return;
    const productForCompare: Product = {
      id: product.id,
      title: product.name,
      slug: product.slug,
      description: product.description || "",
      shortDescription: product.short_description || undefined,
      price: currentPrice,
      originalPrice: originalPrice || undefined,
      sku: currentVariant?.sku || product.id,
      stock: isOutOfStock ? 0 : 10,
      isActive: product.is_active,
      isFeatured: product.is_featured,
      images: (product.images || []).map((img, idx) => ({
        id: img.id || `img-${idx}`,
        url: img.url,
        alt: img.alt_text || product.name,
        order: img.position || idx + 1,
      })),
      thumbnail: product.primary_image_url || product.images?.[0]?.url,
      categoryId: product.category_id || product.category?.id || "cat-default",
      category: product.category
        ? {
            id: product.category.id,
            name: product.category.name,
            slug: product.category.slug,
          }
        : undefined,
      brandId: product.brand_id || product.brand?.id,
      brand: product.brand
        ? {
            id: product.brand.id,
            name: product.brand.name,
            slug: product.brand.slug,
          }
        : undefined,
      tags: (product.tags || []).map((t) => t.name),
      variants: [],
      attributes: (product.product_attributes || []).map((pa) => ({
        name: pa.attribute_name || "ویژگی",
        value: pa.attribute_value || "",
      })),
      type: product.product_type || product.category?.name || "کالای دیجیتال",
      weight: currentVariant?.weight ? `${currentVariant.weight} گرم` : undefined,
      // No reviews means no rating claim — a fabricated 4.7 followed the
      // product into the compare table, where it read as fact.
      rating: reviewStats.total_reviews > 0 ? reviewStats.average_rating : 0,
      reviewCount: reviewStats.total_reviews,
      createdAt: product.created_at || new Date().toISOString(),
      updatedAt: product.updated_at || new Date().toISOString(),
    };

    toggleProduct(productForCompare);
  };

  // Submit Review Form
  const handleReviewSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!product) return;
    if (!formBody.trim()) {
      setReviewSubmitError("لطفاً متن نظر خود را وارد کنید.");
      return;
    }

    setReviewSubmitError(null);

    const prosList = formPros
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    const consList = formCons
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    try {
      await submitReviewMutation.mutateAsync({
        product_id: product.id,
        rating: formRating,
        title: formTitle.trim() || undefined,
        body: formBody.trim(),
        pros: prosList.length > 0 ? prosList : undefined,
        cons: consList.length > 0 ? consList : undefined,
      });

      setReviewSubmitSuccess(true);
      // The success notice stays until the shopper leaves the page: the
      // review enters moderation (pending) and does NOT appear in the list
      // below — a 4-second flash read as "nothing happened" and the shopper
      // retried into a confusing duplicate-review error (live-reported).
      setFormTitle("");
      setFormBody("");
      setFormPros("");
      setFormCons("");
      setFormRating(5);
    } catch (err) {
      // The submit failed — say WHY, honestly, and keep the form so they can
      // act on it. Never fake a success here.
      const status =
        (err as { response?: { status?: number } })?.response?.status ?? 0;
      setReviewSubmitError(
        status === 409
          ? "شما قبلاً برای این کالا دیدگاه ثبت کرده‌اید؛ پس از تایید، همین‌جا نمایش داده می‌شود."
          : status === 401
            ? "برای ثبت دیدگاه ابتدا وارد حساب کاربری خود شوید."
            : "ثبت دیدگاه انجام نشد. لطفاً دوباره تلاش کنید یا بعداً مراجعه کنید.",
      );
    } finally {
      setTimeout(() => setReviewSubmitError(null), 12000);
    }
  };

  // Unified guard: while loading → skeleton; API failure → error + retry;
  // unknown slug → not-found. After this block `product` is defined.
  if (!product) {
    if (productError && !loading) {
      return (
        <div className="container mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center py-16 text-center">
          <Package className="mb-3 h-16 w-16 text-destructive/40" />
          <h1 className="mb-1 text-lg font-bold text-foreground">
            خطا در دریافت محصول
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            ارتباط با سرور برقرار نشد. لطفاً دوباره تلاش کنید.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => refetchProduct()}>تلاش مجدد</Button>
            <Button asChild variant="outline">
              <Link href="/products">بازگشت به محصولات</Link>
            </Button>
          </div>
        </div>
      );
    }

    if (!loading) {
      return (
        <div className="container mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center py-16 text-center">
          <Package className="mb-3 h-16 w-16 text-muted-foreground/40" />
          <h1 className="mb-1 text-lg font-bold text-foreground">
            محصول مورد نظر یافت نشد
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            ممکن است این محصول حذف شده یا آدرس آن اشتباه باشد.
          </p>
          <Button asChild>
            <Link href="/products">مشاهده محصولات</Link>
          </Button>
        </div>
      );
    }

    return (
      <div className="container mx-auto px-4 py-10 space-y-10">
        <Skeleton className="h-6 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
          <Skeleton className="aspect-square w-full rounded-3xl" />
          <div className="space-y-4">
            <Skeleton className="h-8 w-4/5" />
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-10 w-1/2" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-12 w-full rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* ------------------------------------------------------------------ */}
      {/*  Breadcrumbs                                                       */}
      {/* ------------------------------------------------------------------ */}
      <nav className="mb-6 flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground" aria-label="مسیر دسته‌بندی محصول">
        <Link href="/" className="hover:text-primary transition-colors">
          صفحه اصلی
        </Link>
        {product.category ? (
          <>
            {product.category.parent_name && (
              <>
                <ChevronLeft className="h-3.5 w-3.5" />
                <Link
                  href={`/products?category_id=${product.category.parent_id}`}
                  className="hover:text-primary transition-colors"
                >
                  {product.category.parent_name}
                </Link>
              </>
            )}
            <ChevronLeft className="h-3.5 w-3.5" />
            <Link
              href={`/products?category_id=${product.category.id}`}
              className="hover:text-primary transition-colors"
            >
              {product.category.name}
            </Link>
          </>
        ) : (
          <>
            <ChevronLeft className="h-3.5 w-3.5" />
            <Link href="/products" className="hover:text-primary transition-colors">
              محصولات
            </Link>
          </>
        )}
        <ChevronLeft className="h-3.5 w-3.5" />
        <span className="text-foreground font-medium line-clamp-1">
          {product.name}
        </span>
      </nav>

      {/* ------------------------------------------------------------------ */}
      {/*  Main Product Section: Gallery & Details                           */}
      {/* ------------------------------------------------------------------ */}
      <div className="mb-16 grid grid-cols-1 gap-10 lg:grid-cols-12">
        {/* Left / Gallery Column (RTL: Starts from Right) */}
        <div className="lg:col-span-6 space-y-4">
          {/* View Mode Toggle: 2D Gallery vs 3D Interactive Model */}
          <div className="flex items-center justify-between rounded-2xl border border-border bg-muted/40 p-1.5 backdrop-blur-sm">
            <div className="flex items-center gap-1.5">
              <Button
                type="button"
                size="sm"
                variant={viewMode === "gallery" ? "default" : "ghost"}
                onClick={() => setViewMode("gallery")}
                className="h-8 rounded-xl px-3 text-xs gap-1.5 font-bold"
              >
                <ImageIcon className="h-3.5 w-3.5" />
                <span>گالری تصاویر</span>
              </Button>
              <Button
                type="button"
                size="sm"
                variant={viewMode === "3d" ? "default" : "ghost"}
                onClick={() => setViewMode("3d")}
                className="h-8 rounded-xl px-3 text-xs gap-1.5 font-bold"
              >
                <Box className="h-3.5 w-3.5 text-emerald-500" />
                <span>مدل سه‌بعدی ۳۶۰° (3D)</span>
                <Badge className="bg-emerald-500 text-white text-[9px] px-1.5 py-0 h-4">جدید</Badge>
              </Button>
            </div>
            <span className="text-[11px] text-muted-foreground pe-2 hidden sm:inline">
              قابلیت بازرسی کامل ۳۶۰ درجه
            </span>
          </div>

          {viewMode === "3d" ? (
            <Product3DViewer title={product.name} />
          ) : (
            <>
              {/* Main Selected Image */}
              <div className="relative aspect-square overflow-hidden rounded-3xl border border-border bg-card p-6 shadow-sm">
                {displayImages[selectedImageIndex] ? (
                  <Image
                    src={displayImages[selectedImageIndex]}
                    alt={product.name}
                    fill
                    priority
                    sizes="(max-width: 1024px) 100vw, 50vw"
                    className="object-contain"
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center">
                    <Package className="h-32 w-32 text-muted-foreground/30" />
                  </div>
                )}

                {/* Discount Badge */}
                {discountPercent && discountPercent > 0 && (
                  <Badge
                    variant="destructive"
                    className="absolute top-4 right-4 rounded-full px-3 py-1 text-xs font-black shadow-md"
                  >
                    {toPersianDigits(discountPercent)}٪ تخفیف
                  </Badge>
                )}

                {/* Action Buttons on Image */}
                <div className="absolute top-4 left-4 flex items-center gap-2">
                  {/* Compare Button */}
                  {shopFeatures.compare && (
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleToggleCompare}
                      className={`h-10 w-10 rounded-2xl bg-background/80 backdrop-blur hover:bg-background border-border shadow-sm transition-all ${
                        inCompare
                          ? "border-primary bg-primary/10 text-primary"
                          : "text-muted-foreground hover:text-primary"
                      }`}
                      aria-label={inCompare ? "حذف از لیست مقایسه" : "افزودن به لیست مقایسه"}
                      title={inCompare ? "حذف از مقایسه" : "مقایسه محصول"}
                    >
                      <ArrowLeftRight className="h-5 w-5" />
                    </Button>
                  )}

                  {/* Wishlist Button */}
                  {shopFeatures.wishlist && (
                    <Button
                      variant="outline"
                      size="icon"
                      onClick={handleToggleWishlist}
                      disabled={wishlistLoading}
                      className="h-10 w-10 rounded-2xl bg-background/80 backdrop-blur hover:bg-background border-border shadow-sm"
                      aria-label="افزودن به علاقه‌مندی‌ها"
                    >
                      <Heart
                        className={`h-5 w-5 transition-colors ${
                          isWishlisted
                            ? "fill-red-500 text-red-500"
                            : "text-muted-foreground hover:text-red-500"
                        }`}
                      />
                    </Button>
                  )}
                </div>
              </div>

              {/* Thumbnail Selector Strip */}
              {displayImages.length > 1 && (
                <div className="flex gap-3 overflow-x-auto pb-2">
                  {displayImages.map((imgUrl, idx) => (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => setSelectedImageIndex(idx)}
                      className={`relative h-20 w-20 flex-shrink-0 overflow-hidden rounded-2xl border-2 p-1.5 transition-all ${
                        selectedImageIndex === idx
                          ? "border-primary ring-2 ring-primary/20 shadow-sm"
                          : "border-border hover:border-muted-foreground/50 opacity-70 hover:opacity-100"
                      }`}
                    >
                      <Image
                        src={imgUrl}
                        alt=""
                        width={72}
                        height={72}
                        className="h-full w-full object-contain"
                      />
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>

        {/* Right / Product Info & Actions Column */}
        <div className="lg:col-span-6 flex flex-col space-y-6">
          {/* Brand & Category badges */}
          <div className="flex flex-wrap items-center gap-2">
            {product.brand && (
              <Badge variant="secondary" className="rounded-lg text-xs">
                برند: {product.brand.name}
              </Badge>
            )}
            {product.category && (
              <Link href={`/products?category_id=${product.category.id}`}>
                <Badge variant="outline" className="rounded-lg text-xs hover:bg-muted cursor-pointer transition-colors">
                  دسته: {product.category.name}
                </Badge>
              </Link>
            )}
            {product.is_featured && (
              <Badge className="bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs">
                کالای برگزیده
              </Badge>
            )}
          </div>

          {/* Title */}
          <h1 className="text-xl sm:text-2xl lg:text-3xl font-black text-foreground leading-relaxed">
            {product.name}
          </h1>

          {/* Ratings & Reviews summary.
              A product with zero reviews shows no number at all. The old
              `average_rating || 4.7` printed a fabricated 4.7 next to
              "(بر اساس ۰ نظر ثبت‌شده)" — telling every customer a brand-new
              product had a great score. No reviews means no rating claim. */}
          <div className="flex items-center gap-3 text-xs sm:text-sm">
            {reviewStats.total_reviews > 0 ? (
              <>
                <div className="flex items-center gap-1 text-amber-500 font-bold">
                  <Star className="h-4 w-4 fill-amber-400" />
                  <span>{toPersianDigits(reviewStats.average_rating.toFixed(1))}</span>
                </div>
                <span className="text-muted-foreground">
                  (بر اساس {toPersianDigits(reviewStats.total_reviews)} نظر ثبت‌شده)
                </span>
              </>
            ) : (
              <span className="text-muted-foreground">هنوز نظری ثبت نشده است</span>
            )}
          </div>

          <Separator />

          {/* Short description */}
          {product.short_description && (
            <p className="text-sm text-muted-foreground leading-relaxed">
              {product.short_description}
            </p>
          )}

          {/* Variant Selector — swatch groups (woo-variation-swatches
              parity) when the product defines variation attributes; a legacy
              flat button list otherwise. A single variant with no attributes
              has nothing to choose and renders neither. */}
          {product.variants &&
          (product.variants.length > 1 ||
            product.variants.some(
              (v) => v.attributes && Object.keys(v.attributes).length > 0,
            )) ? (
            hasVariationGroups ? (
              <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
                <VariationSwatches
                  groups={variationGroups}
                  variants={product.variants}
                  selected={effectiveSelection}
                  onOptionSelect={handleSwatchSelect}
                />
              </div>
            ) : (
              <div className="space-y-3 rounded-2xl border border-border bg-card p-4 shadow-sm">
                <span className="text-xs font-bold text-foreground block">
                  انتخاب مشخصات و مدل کالا:
                </span>
                <div className="flex flex-wrap gap-2">
                  {product.variants.map((variant, idx) => {
                    const isSelected = selectedVariantIndex === idx;
                    const label = variant.attributes
                      ? Object.values(variant.attributes).join(" - ")
                      : variant.sku;

                    return (
                      <button
                        key={variant.id}
                        type="button"
                        onClick={() => setSelectedVariantIndex(idx)}
                        className={`relative flex items-center gap-2 rounded-xl border-2 px-3 py-2 text-xs font-semibold transition-all ${
                          isSelected
                            ? "border-primary bg-primary/10 text-primary shadow-sm"
                            : "border-border hover:border-muted-foreground text-foreground"
                        } ${!variant.is_active ? "opacity-50" : ""}`}
                      >
                        {isSelected && <Check className="h-3.5 w-3.5" />}
                        <span>{label}</span>
                        {!variant.is_active && (
                          <span className="text-[10px] text-red-500 font-normal">
                            (ناموجود)
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </div>
            )
          ) : null}

          {/* SKU & inventory availability — always shown, independent of the
              selector card. SKU is optional (owner directive), so the code
              line renders only when a code exists; the English "N/A" fallback
              never appears in a Persian UI. */}
          <div className="flex items-center justify-between text-xs text-muted-foreground rounded-2xl border border-border/60 bg-muted/20 px-4 py-2.5">
            {currentVariant?.sku ? (
              <span>
                شناسه کالا (SKU):{" "}
                <span className="font-mono font-medium text-foreground">
                  {currentVariant.sku}
                </span>
              </span>
            ) : (
              <span />
            )}
            <span
              className={`font-semibold ${
                isOutOfStock
                  ? "text-red-500"
                  : isOnBackorder
                    ? "text-amber-600"
                    : "text-emerald-600"
              }`}
            >
              {isOutOfStock
                ? "اتمام موجودی در انبار"
                : isOnBackorder
                  ? "آماده‌ی پیش‌خرید"
                  : "موجود در انبار"}
            </span>
          </div>

          {/* Price Box — the visual anchor of the buy decision */}
          <div className="rounded-2xl border border-primary/25 bg-card p-5 shadow-sm space-y-2">
            <div className="flex items-baseline justify-between gap-3">
              <div className="space-y-1">
                <span className="block text-xs font-medium text-muted-foreground">
                  قیمت نهایی برای شما:
                </span>
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl sm:text-3xl font-black text-foreground">
                    {formatPrice(currentPrice)}
                  </span>
                </div>
              </div>
              <div className="flex flex-col items-end gap-1.5">
                {originalPrice && (
                  <span className="text-sm line-through text-muted-foreground">
                    {formatPrice(originalPrice)}
                  </span>
                )}
                {discountPercent && discountPercent > 0 && (
                  <span className="rounded-lg bg-success/10 px-2 py-0.5 text-[11px] font-bold text-success border border-success/20">
                    سود شما: {toPersianDigits(discountPercent)}٪
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Quantity Stepper & Min/Max Qty Constraints */}
          <div className="space-y-4">
            <div className="space-y-2">
              <div className="flex items-center gap-4">
                <span className="text-xs font-bold text-foreground">تعداد:</span>
                <div className="flex items-center gap-2 rounded-xl border border-border p-1">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-lg"
                    disabled={quantity <= minQty || isOutOfStock}
                    onClick={() => setQuantity((q) => Math.max(minQty, q - 1))}
                  >
                    <Minus className="h-3.5 w-3.5" />
                  </Button>
                  <span className="w-8 text-center text-sm font-bold font-mono">
                    {toPersianDigits(quantity)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-lg"
                    disabled={quantity >= maxQty || isOutOfStock}
                    onClick={() => setQuantity((q) => Math.min(maxQty, q + 1))}
                  >
                    <Plus className="h-3.5 w-3.5" />
                  </Button>
                </div>
                {(minQty > 1 || (product?.max_order_quantity && maxQty < 999)) && (
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {minQty > 1 && <span>حداقل: {toPersianDigits(minQty)}</span>}
                    {minQty > 1 && maxQty < 999 && <span>|</span>}
                    {maxQty < 999 && <span>حداکثر: {toPersianDigits(maxQty)}</span>}
                  </div>
                )}
              </div>

              {/* Boundary Alerts */}
              {quantity < minQty && (
                <p className="text-xs font-medium text-amber-600">
                  حداقل تعداد سفارش این محصول {toPersianDigits(minQty)} عدد است.
                </p>
              )}
              {quantity > maxQty && (
                <p className="text-xs font-medium text-amber-600">
                  حداکثر تعداد سفارش این محصول {toPersianDigits(maxQty)} عدد است.
                </p>
              )}
            </div>

            {/* Karta findPrice: volume tier preview (server is authoritative) */}
            {tierUnitPrice !== null && (
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3 text-sm">
                <span className="font-bold text-emerald-600">
                  قیمت واحد با تخفیف تیراژ: {formatPrice(tierUnitPrice)}
                </span>
                <span className="ms-2 text-xs text-muted-foreground">
                  مجموع {toPersianDigits(quantity)} عدد: {formatPrice(unitPriceForLine * quantity)}
                </span>
                {currentPrice > tierUnitPrice && (
                  <span className="ms-2 inline-block rounded-md bg-emerald-500/10 px-1.5 py-0.5 text-[11px] font-bold text-emerald-700">
                    {toPersianDigits(Math.round(((currentPrice - tierUnitPrice) / currentPrice) * 100))}٪ تخفیف تیراژ
                  </span>
                )}
              </div>
            )}
            {tiers.length > 0 && (
              <div className="rounded-xl border border-border p-3 text-xs">
                <p className="mb-2 font-bold">قیمت‌گذاری پلکانی:</p>
                <ul className="space-y-1.5">
                  {tiers.map((t) => {
                    const isActive = quantity >= t.from_qty && (t.to_qty === null || quantity <= t.to_qty);
                    return (
                      <li
                        key={t.id}
                        dir="rtl"
                        className={`flex items-center justify-between rounded-lg px-2.5 py-1.5 transition-colors ${
                          isActive
                            ? "border border-emerald-500/40 bg-emerald-500/10 font-bold text-emerald-700 dark:text-emerald-400"
                            : "text-muted-foreground hover:bg-muted/30"
                        }`}
                      >
                        <span>
                          {t.to_qty === null
                            ? `${toPersianDigits(t.from_qty)} عدد و بالاتر`
                            : `${toPersianDigits(t.from_qty)} تا ${toPersianDigits(t.to_qty)} عدد`}
                          {isActive && <span className="ms-1.5 text-[10px] text-emerald-600 font-bold">(فعال)</span>}
                        </span>
                        <span className={isActive ? "text-emerald-700 font-bold" : "text-foreground"}>
                          {formatPrice(t.unit_price)}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {/* Karta categoryFields: dynamic order inputs */}
            {customFieldDefs.length > 0 && (
              <div className="space-y-3 rounded-xl border border-border p-4">
                <p className="text-sm font-bold">اطلاعات سفارش‌ساز:</p>
                {customFieldDefs.map((def) => {
                  const error = fieldErrors[def.field_key];
                  return (
                    <div key={def.id} className="space-y-1">
                      <label className="text-xs text-muted-foreground">
                        {def.label}
                        {def.is_required && <span className="text-red-500"> *</span>}
                      </label>
                      {def.field_type === "select" ? (
                        <select
                          className={`w-full rounded-lg border bg-background px-3 py-2 text-sm transition-colors ${
                            error ? "border-red-500 focus:ring-red-500" : "border-border"
                          }`}
                          value={fieldAnswers[def.field_key] ?? ""}
                          onChange={(e) => handleFieldChange(def, e.target.value)}
                          onBlur={(e) => handleFieldChange(def, e.target.value)}
                        >
                          <option value="">انتخاب کنید…</option>
                          {(def.options_json ?? []).map((opt) => (
                            <option key={opt} value={opt}>
                              {opt}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type={def.field_type === "number" ? "number" : "text"}
                          className={`w-full rounded-lg border bg-background px-3 py-2 text-sm transition-colors ${
                            error ? "border-red-500 focus:ring-red-500" : "border-border"
                          }`}
                          value={fieldAnswers[def.field_key] ?? ""}
                          onChange={(e) => handleFieldChange(def, e.target.value)}
                          onBlur={(e) => handleFieldChange(def, e.target.value)}
                        />
                      )}
                      {error && (
                        <p className="text-xs font-medium text-red-500">{error}</p>
                      )}
                    </div>
                  );
                })}
                {fieldError && (
                  <p className="text-xs font-bold text-red-500">{fieldError}</p>
                )}
              </div>
            )}

            {/* WooCommerce Product Add-ons parity: per-product addon fields */}
            {addonDefs.length > 0 && (
              <div className="space-y-3 rounded-xl border border-border p-4">
                <p className="text-sm font-bold">فیلدهای سفارشی این کالا:</p>
                <ProductAddonsForm
                  fields={addonDefs}
                  answers={addonAnswers}
                  errors={addonErrors}
                  quantity={quantity}
                  onChange={handleAddonChange}
                />
                {addonTotalToman > 0 && (
                  <p className="text-xs text-muted-foreground" dir="rtl">
                    جمع هزینه فیلدهای سفارشی این کالا:{" "}
                    <span className="font-bold text-foreground">
                      {formatPrice(addonTotalToman)}
                    </span>{" "}
                    تومان
                  </p>
                )}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3">
              <ClickSpark className="flex-1 inline-flex">
                <Button
                  size="lg"
                  disabled={isOutOfStock}
                  onClick={handleAddToCart}
                  className="w-full gap-2 rounded-2xl h-12 text-base font-bold shadow-md transition-all"
                  variant={addedToCartToast ? "secondary" : "default"}
                >
                  {addedToCartToast ? (
                    <>
                      <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                      <span className="text-emerald-600">
                        به سبد خرید اضافه شد!
                      </span>
                    </>
                  ) : isOutOfStock ? (
                    <span>در حال حاضر ناموجود است</span>
                  ) : (
                    <>
                      <ShoppingCart className="h-5 w-5" />
                      <span>افزودن به سبد خرید</span>
                    </>
                  )}
                </Button>
              </ClickSpark>

              {shopFeatures.wishlist && (
                <Button
                  variant="outline"
                  size="lg"
                  onClick={handleToggleWishlist}
                  disabled={wishlistLoading}
                  className={`gap-2 rounded-2xl h-12 border-2 ${
                    isWishlisted
                      ? "border-destructive/40 text-destructive hover:bg-destructive/10"
                      : "border-border text-foreground hover:bg-muted"
                  }`}
                >
                  <PulseHeart
                    active={isWishlisted}
                    size="sm"
                    className="pointer-events-none"
                  />
                  <span className="text-xs font-semibold">
                    {isWishlisted ? "حذف از لیست علاقه‌مندی" : "افزودن به علاقه‌مندی"}
                  </span>
                </Button>
              )}

              {shopFeatures.compare && (
                <Button
                  variant="outline"
                  size="lg"
                  onClick={handleToggleCompare}
                  className={`gap-2 rounded-2xl h-12 border-2 transition-all ${
                    inCompare
                      ? "border-primary bg-primary/10 text-primary hover:bg-primary/20"
                      : "border-border text-foreground hover:bg-muted"
                  }`}
                >
                  <ArrowLeftRight className="h-5 w-5" />
                  <span className="text-xs font-semibold">
                    {inCompare ? "حذف از مقایسه" : "مقایسه کالا"}
                  </span>
                </Button>
              )}
            </div>

            {/* In-compare notice banner */}
            {inCompare && shopFeatures.compare && (
              <div className="flex items-center justify-between rounded-2xl bg-primary/10 border border-primary/20 px-4 py-2.5 text-xs text-primary">
                <span className="font-semibold flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                  این کالا در لیست مقایسه شما قرار دارد
                </span>
                <Link
                  href="/compare"
                  className="font-bold underline flex items-center gap-1 hover:opacity-80 transition-opacity"
                >
                  <span>مشاهده صفحه مقایسه</span>
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Link>
              </div>
            )}
          </div>

            {/* Guarantees Box */}
            <div className="grid grid-cols-2 gap-2 pt-2 sm:grid-cols-4 text-center">
              <div className="rounded-xl border border-border p-2.5">
                <Truck className="mx-auto h-5 w-5 text-primary mb-1" />
                <span className="text-[11px] font-medium text-foreground block">
                  تحویل فوری
                </span>
              </div>
              <div className="rounded-xl border border-border p-2.5">
                <Shield className="mx-auto h-5 w-5 text-primary mb-1" />
                <span className="text-[11px] font-medium text-foreground block">
                  ضمانت اصالت
                </span>
              </div>
              <div className="rounded-xl border border-border p-2.5">
                <RotateCcw className="mx-auto h-5 w-5 text-primary mb-1" />
                <span className="text-[11px] font-medium text-foreground block">
                  ۷ روز بازگشت
                </span>
              </div>
              <div className="rounded-xl border border-border p-2.5">
                <Headphones className="mx-auto h-5 w-5 text-primary mb-1" />
                <span className="text-[11px] font-medium text-foreground block">
                  پشتیبانی ۲۴/۷
                </span>
              </div>
            </div>

            {/* Iranian E-Commerce Delivery Slot Banner */}
            <div className="rounded-2xl border border-primary/25 bg-primary/5 p-3.5 flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/15 text-primary">
                <Truck className="h-5 w-5" />
              </div>
              <div className="text-xs">
                <span className="font-bold text-foreground block">
                  امکان انتخاب بازه زمانی تحویل (صبح، عصر، شب)
                </span>
              </div>
            </div>
          </div>
        </div>

      {/* Cross-sell accessories (Odoo website_sale concept) */}
      {product && (
        <AccessoryRail
          productId={product.id}
          title="کالاهای مکمل"
          className="mb-16"
        />
      )}

      {/* ------------------------------------------------------------------ */}
      {/*  Tabs: Description / Technical Specs / Reviews                     */}
      {/* ------------------------------------------------------------------ */}
      <section className="mb-16">
        <Tabs defaultValue="specs" className="w-full">
          <TabsList className="mb-6 w-full justify-start gap-2 rounded-2xl bg-muted/60 p-1.5 h-auto flex-wrap border border-border">
            <TabsTrigger
              value="specs"
              className="rounded-xl px-5 py-2.5 text-xs sm:text-sm font-semibold"
            >
              مشخصات فنی کالا
            </TabsTrigger>
            <TabsTrigger
              value="description"
              className="rounded-xl px-5 py-2.5 text-xs sm:text-sm font-semibold"
            >
              معرفی و نقد تخصصی
            </TabsTrigger>
            <TabsTrigger
              value="reviews"
              className="rounded-xl px-5 py-2.5 text-xs sm:text-sm font-semibold"
            >
              نظرات کاربران ({reviewsLoading ? "..." : toPersianDigits(reviews.length)})
            </TabsTrigger>
          </TabsList>

          {/* Technical Specs Tab */}
          <TabsContent value="specs">
            <Card className="overflow-hidden rounded-3xl border border-border p-6">
              <h3 className="text-base font-bold text-foreground mb-4">
                جدول مشخصات فنی
              </h3>
              {product.product_attributes &&
              product.product_attributes.length > 0 ? (
                <div className="divide-y divide-border border border-border rounded-2xl overflow-hidden">
                  {product.product_attributes.map((attr, idx) => (
                    <div
                      key={attr.id || idx}
                      className={`grid grid-cols-1 sm:grid-cols-3 gap-2 px-5 py-3.5 text-xs sm:text-sm ${
                        idx % 2 === 0 ? "bg-muted/40" : "bg-card"
                      }`}
                    >
                      <span className="font-semibold text-foreground">
                        {attr.attribute_name || "مشخصه"}
                      </span>
                      <span className="sm:col-span-2 text-muted-foreground leading-relaxed">
                        {attr.attribute_value}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-muted-foreground">
                  مشخصات فنی خاصی برای این محصول ثبت نشده است.
                </p>
              )}
            </Card>
          </TabsContent>

          {/* Description Tab */}
          <TabsContent value="description">
            <Card className="rounded-3xl border border-border p-6 sm:p-8">
              <h3 className="text-base font-bold text-foreground mb-4">
                توضیحات تکمیلی محصول
              </h3>
              <div className="text-sm text-foreground/90 leading-8 space-y-4">
                {product.description ? (
                  product.description.split("\n\n").map((para, i) => (
                    <p key={i}>{para}</p>
                  ))
                ) : (
                  <p>{product.short_description || "توضیحاتی ثبت نشده است."}</p>
                )}
              </div>
            </Card>
          </TabsContent>

          {/* Reviews & Submission Form Tab */}
          <TabsContent value="reviews">
            <div className="space-y-8">
              {/* Review Statistics Summary Box.
                  With zero reviews nothing here is a rating claim: no number,
                  no stars, no fabricated 80/20 distribution. The old code
                  printed 4.7 and a "80% five-star" bar chart for a product
                  with no reviews at all. */}
              <Card className="rounded-3xl border border-border p-6">
                {/* Honesty rule: stats render only with approved reviews; a
                    shopper's OWN pending review (in `reviews`, invisible to
                    stats) gets the acknowledgment note — never a fabricated
                    ۰.۰ «از ۰ نظر» block. */}
                {reviewStats.total_reviews > 0 && reviewStats.distribution ? (
                  <ReviewHistogram
                    distribution={reviewStats.distribution}
                    averageRating={reviewStats.average_rating}
                    totalReviews={reviewStats.total_reviews}
                    verifiedCount={reviewStats.verified_count}
                    className="border-0 p-0 shadow-none bg-transparent"
                  />
                ) : reviews.length > 0 ? (
                  /* Own pending review exists (stats count approved only) —
                     acknowledge it instead of the "no reviews" notice. */
                  <p className="text-center text-sm text-muted-foreground">
                    دیدگاه شما ثبت شد و پس از تایید، در همین بخش نمایش داده می‌شود.
                  </p>
                ) : (
                  <p className="text-center text-sm text-muted-foreground">
                    هنوز نظری برای این کالا ثبت نشده است. اولین نفری باشید که تجربه‌اش را می‌نویسد.
                  </p>
                )}
              </Card>

              {/* Review Submission Form — authenticated shoppers only. The
                  backend rejects guest submissions with 401, and showing the
                  full form to a signed-out visitor meant they filled it in,
                  hit «ثبت» and nothing visibly happened (live-reported). */}
              <Card className="rounded-3xl border border-border p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <MessageSquare className="h-5 w-5 text-primary" />
                  <h3 className="text-base font-bold text-foreground">
                    ثبت نظر و تجربه شما درباره این کالا
                  </h3>
                </div>

                {isAuthLoading ? null : !isAuthenticated ? (
                  <div className="flex flex-col items-center gap-3 py-6 text-center">
                    <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary">
                      <MessageSquare className="h-5 w-5" />
                    </div>
                    <p className="text-sm text-muted-foreground max-w-sm">
                      برای ثبت دیدگاه درباره این کالا، ابتدا وارد حساب کاربری خود شوید.
                    </p>
                    <Link
                      href={`/login?redirect=/products/${slug}`}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2 text-xs font-bold text-primary-foreground hover:bg-primary/90 transition-colors"
                    >
                      ورود به حساب کاربری
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                ) : (
                <>
                {reviewSubmitSuccess && (
                  <div className="flex items-center gap-2 rounded-xl bg-success/10 text-success border border-success/20 p-3 text-xs">
                    <CheckCircle2 className="h-4 w-4" />
                    <span>نظر شما با موفقیت ثبت گردید و پس از تایید منتشر خواهد شد.</span>
                  </div>
                )}

                {reviewSubmitError && (
                  <div className="flex items-center gap-2 rounded-xl bg-destructive/10 text-destructive border border-destructive/20 p-3 text-xs">
                    <AlertCircle className="h-4 w-4" />
                    <span>{reviewSubmitError}</span>
                  </div>
                )}

                <form onSubmit={handleReviewSubmit} className="space-y-4">
                  {/* Rating Selector */}
                  <div>
                    <span className="block text-xs font-semibold text-foreground mb-2">
                      امتیاز شما به کالا:
                    </span>
                    <StarRating
                      value={formRating}
                      onChange={setFormRating}
                      size="lg"
                    />
                  </div>

                  {/* Title */}
                  <div>
                    <label className="block text-xs font-semibold text-foreground mb-1">
                      عنوان نظر (اختیاری):
                    </label>
                    <Input
                      type="text"
                      placeholder="خلاصه تجربه شما در چند کلمه..."
                      value={formTitle}
                      onChange={(e) => setFormTitle(e.target.value)}
                      className="rounded-xl text-xs"
                    />
                  </div>

                  {/* Body */}
                  <div>
                    <label className="block text-xs font-semibold text-foreground mb-1">
                      متن نظر شما *:
                    </label>
                    <Textarea
                      placeholder="نقاط قوت، نقاط ضعف، نحوه عملکرد و نظر کلی خود را بنویسید..."
                      rows={4}
                      value={formBody}
                      onChange={(e) => setFormBody(e.target.value)}
                      className="rounded-xl text-xs"
                      required
                    />
                  </div>

                  {/* Pros & Cons */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-emerald-600 mb-1">
                        نقاط قوت (هر مورد در یک خط):
                      </label>
                      <Textarea
                        placeholder="مثلاً: کیفیت ساخت بالا&#10;سرعت پردازش عالی"
                        rows={3}
                        value={formPros}
                        onChange={(e) => setFormPros(e.target.value)}
                        className="rounded-xl text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-red-500 mb-1">
                        نقاط ضعف (هر مورد در یک خط):
                      </label>
                      <Textarea
                        placeholder="مثلاً: قیمت بالا&#10;شارژر داخل جعبه نیست"
                        rows={3}
                        value={formCons}
                        onChange={(e) => setFormCons(e.target.value)}
                        className="rounded-xl text-xs"
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={submitReviewMutation.isPending}
                    className="gap-2 rounded-xl text-xs px-6"
                  >
                    {submitReviewMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                    <span>ثبت و ارسال نظر</span>
                  </Button>
                </form>
                </>
                )}
              </Card>

              {/* Reviews List */}
              <div className="space-y-4">
                <h3 className="text-base font-bold text-foreground">
                  نظرات کاربران
                </h3>
                {reviewsLoading ? (
                  <div className="space-y-3">
                    <Skeleton className="h-24 w-full rounded-3xl" />
                    <Skeleton className="h-24 w-full rounded-3xl" />
                  </div>
                ) : (
                  reviews.map((rev) => (
                    <Card key={rev.id} className="rounded-3xl border border-border p-5 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary font-bold text-xs">
                            {(rev.user.display_name || "ک").charAt(0)}
                          </div>
                          <div>
                            <span className="text-xs font-bold text-foreground block">
                              {rev.user.display_name || "کاربر ناشناس"}
                            </span>
                            {rev.is_verified_purchase && (
                              <span className="text-[10px] text-emerald-600 font-medium">
                                خریدار تاییدشده
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Own-review moderation state: the backend returns a
                            shopper's own pending review to them only — badge
                            it so "no visible change after submit" never reads
                            as a lost review. */}
                        {rev.status === "pending" && (
                          <Badge
                            variant="secondary"
                            className="text-[10px] font-bold gap-1 bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/30"
                          >
                            <Clock className="h-3 w-3" />
                            در انتظار تایید
                          </Badge>
                        )}

                        {/* Star rating */}
                        <div className="flex items-center gap-1 text-amber-400">
                          {Array.from({ length: 5 }).map((_, i) => (
                            <Star
                              key={i}
                              className={`h-3.5 w-3.5 ${
                                i < rev.rating
                                  ? "fill-amber-400"
                                  : "text-muted-foreground/30"
                              }`}
                            />
                          ))}
                        </div>
                      </div>

                      {rev.title && (
                        <h4 className="text-sm font-bold text-foreground">
                          {rev.title}
                        </h4>
                      )}

                      <p className="text-xs sm:text-sm text-foreground/85 leading-relaxed">
                        {rev.body}
                      </p>

                      {/* Pros and Cons */}
                      {((rev.pros && rev.pros.length > 0) ||
                        (rev.cons && rev.cons.length > 0)) && (
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2 text-xs">
                          {rev.pros && rev.pros.length > 0 && (
                            <div className="space-y-1">
                              <span className="font-bold text-success">
                                نقاط قوت:
                              </span>
                              <ul className="space-y-0.5 ps-2">
                                {rev.pros.map((p, idx) => (
                                  <li key={idx} className="flex items-center gap-1 text-muted-foreground">
                                    <Plus className="h-3 w-3 text-emerald-500" />
                                    <span>{p}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {rev.cons && rev.cons.length > 0 && (
                            <div className="space-y-1">
                              <span className="font-bold text-destructive">
                                نقاط ضعف:
                              </span>
                              <ul className="space-y-0.5 ps-2">
                                {rev.cons.map((c, idx) => (
                                  <li key={idx} className="flex items-center gap-1 text-muted-foreground">
                                    <Minus className="h-3 w-3 text-red-400" />
                                    <span>{c}</span>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </Card>
                  ))
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </section>

      {/* Recently Viewed Products */}
      {product && (
        <RecentlyViewed excludeId={product.id} className="mb-16" />
      )}

      {/* Trust & Authenticity Strip */}
      <section aria-label="تضمین‌های خرید" className="mb-16">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { icon: Truck, title: "ارسال سریع سراسری", desc: "تحویل ۱ تا ۳ روز کاری" },
            { icon: Shield, title: "ضمانت اصالت ۱۰۰٪", desc: "گارانتی رسمی شرکتی" },
            { icon: RotateCcw, title: "۷ روز مهلت بازگشت", desc: "بدون قید و شرط" },
            { icon: Headphones, title: "پشتیبانی ۲۴/۷", desc: "مشاوره تخصصی خرید" },
          ].map((item) => (
            <div
              key={item.title}
              className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-sm transition-shadow hover:shadow-md"
            >
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <item.icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs font-bold text-foreground sm:text-sm">{item.title}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground sm:text-xs">{item.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Add-to-cart failure toast (QA B19) */}
      {addToCartError && (
        <div
          role="alert"
          className="fixed bottom-20 inset-x-4 z-50 mx-auto max-w-md rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-center text-sm font-medium text-destructive shadow-lg backdrop-blur-md lg:bottom-6"
        >
          {addToCartError}
        </div>
      )}

      {/* Wishlist write failure — the same feedback, because a rejected save
          must not look like a successful one. */}
      {wishlistError && (
        <div
          role="alert"
          className="fixed bottom-20 inset-x-4 z-50 mx-auto max-w-md rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-center text-sm font-medium text-destructive shadow-lg backdrop-blur-md lg:bottom-6"
        >
          {wishlistError}
        </div>
      )}

      {/* Sticky Mobile Add-To-Cart Bar (Digikala & Tier S standard) */}
      <div className="fixed bottom-0 inset-x-0 z-40 lg:hidden border-t border-border bg-background/95 backdrop-blur-md p-3 px-4 shadow-xl">
        <div className="flex items-center justify-between gap-4">
          <div className="flex flex-col">
            <span className="text-[11px] text-muted-foreground line-clamp-1 max-w-[150px]">
              {product.name}
            </span>
            <span className="text-sm font-black text-primary">
              {formatPrice(currentPrice)}
            </span>
          </div>
          <Button
            size="default"
            onClick={handleAddToCart}
            disabled={isOutOfStock}
            className="flex-1 max-w-[200px] gap-2 rounded-xl font-bold shadow-md"
          >
            {addedToCartToast ? (
              <>
                <Check className="h-4 w-4 text-success" />
                <span className="text-xs">در سبد خرید شما</span>
              </>
            ) : (
              <>
                <ShoppingCart className="h-4 w-4" />
                <span className="text-xs">افزودن به سبد</span>
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
