import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { safeJsonLd } from "@/lib/safe-json-ld";
import { siteOrigin } from "@/lib/site-url";
import {
  fetchProductBySlug,
  fetchReviewStats,
  fetchSchemaOverride,
  type ApiProductDetail,
  type ApiReviewStats,
} from "@/lib/api/services";

// Server-side lookup for metadata + structured data. A failed fetch must
// never break rendering, so every failure resolves to null.
async function getProduct(slug: string): Promise<ApiProductDetail | null> {
  try {
    return await fetchProductBySlug(slug);
  } catch {
    return null;
  }
}

/**
 * Real review stats for the AggregateRating node.
 *
 * Google penalises rating markup that does not match what the page shows, so
 * the JSON-LD must come from the same review data the page renders — and a
 * product with zero reviews must carry NO AggregateRating at all (the old
 * `|| 4.7` fallback told Google every product scored 4.7, which is a
 * structured-data violation, not just a display bug).
 */
async function getReviewStats(product: ApiProductDetail): Promise<ApiReviewStats | null> {
  try {
    const stats = await fetchReviewStats(product.id);
    if (!stats || !stats.total_reviews || stats.total_reviews <= 0) return null;
    return stats;
  } catch {
    return null;
  }
}

function buildProductJsonLd(product: ApiProductDetail, stats: ApiReviewStats | null) {
  // siteOrigin() reads NEXT_PUBLIC_SITE_URL → SITE_URL → localhost, the same
  // resolver the sitemaps and JSON-LD use — a deployment that configures only
  // SITE_URL must not get localhost URLs in its structured data.
  const SITE_URL = siteOrigin();
  // Backend stores prices in Toman; Google structured data expects IRR.
  const priceRial = Math.round(product.min_price || 0) * 10;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.short_description || product.description || undefined,
    // Absolute URL: the backend stores a site-relative path
    // (`/uploads/media/…`) and schema.org requires a full URL — a relative
    // image value invalidates the Product rich result.
    image: product.primary_image_url
      ? `${SITE_URL}${product.primary_image_url}`
      : undefined,
    sku: product.slug,
    brand: product.brand
      ? { "@type": "Brand", name: product.brand.name }
      : undefined,
    category: product.category?.name,
    // Only real reviews earn a rating node; zero reviews → the key is absent.
    ...(stats
      ? {
          aggregateRating: {
            "@type": "AggregateRating",
            ratingValue: Number(stats.average_rating.toFixed(1)),
            reviewCount: stats.total_reviews,
            bestRating: 5,
            worstRating: 1,
          },
        }
      : {}),
    offers: {
      "@type": "Offer",
      url: `${SITE_URL}/products/${product.slug}`,
      priceCurrency: "IRR",
      price: priceRial,
      availability: product.is_active
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
      itemCondition: "https://schema.org/NewCondition",
      // Digital goods have no shipping; Google wants the delivery method on
      // the offer so a downloadable product is not read as a shipped parcel.
      ...(product.product_type === "digital"
        ? { deliveryMethod: "https://schema.org/OnlineDelivery" }
        : {}),
    },
  };
}

function buildBreadcrumbJsonLd(product: ApiProductDetail) {
  const SITE_URL = siteOrigin();
  return {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "صفحه اصلی", item: SITE_URL },
      {
        "@type": "ListItem",
        position: 2,
        name: "محصولات",
        item: `${SITE_URL}/products`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: product.name,
        item: `${SITE_URL}/products/${product.slug}`,
      },
    ],
  };
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const product = await getProduct(slug);

  if (!product) {
    // Soft-404 fix. This used to return `{ title: "جزئیات محصول" }` with
    // HTTP 200 for a slug that does not exist — a classic soft 404: Google
    // indexes "an empty product page" at unlimited made-up URLs and burns
    // crawl budget on them.
    //
    // This metadata function must NOT trigger the 404 itself: aborting the
    // render here means Next emits a 404 document with NO title at all
    // (verified live). The 404 status comes from the default layout below,
    // which runs after metadata; this function's job is to describe the
    // error page honestly.
    return {
      title: "محصول مورد نظر یافت نشد",
      robots: { index: false, follow: true },
    };
  }

  // The operator's SEO overrides win over derived values — the whole point of
  // the seo_title/seo_description columns, which existed on the model and the
  // API since the beginning but nothing on the storefront ever read (the
  // admin's SEO edits silently never reached the page).
  //
  // The fallbacks carry the slug: live audit (2026-10-10) found 5,146
  // products sharing 15 distinct names and one identical description — only
  // the slug is unique (count(DISTINCT slug) = 5146). Until the owner
  // writes real copy, the code appended to the name keeps every page's
  // title/description unique. Writing real copy replaces this automatically
  // (the operator fields win).
  const title = product.seo_title || `${product.name} (کد ${product.slug})`;
  const description =
    product.seo_description ||
    product.short_description ||
    product.description?.slice(0, 160) ||
    `خرید ${product.name} (کد ${product.slug}) با بهترین قیمت بازار، گارانتی رسمی و ارسال سریع.`;

  return {
    title,
    description,
    alternates: {
      // The resolved product's slug, never the route segment: this page also
      // serves /products/<uuid> through a by-id fallback, and canonicalising
      // to the raw param would have declared the UUID address canonical.
      canonical: `/products/${product.slug}`,
    },
    openGraph: {
      title,
      description,
      type: "website",
      // og:url — the product's own canonical address. It was missing: the
      // tag set title/images but not the URL a share points at (same gap
      // the list pages had).
      url: `/products/${product.slug}`,
      images: product.primary_image_url
        ? [{ url: product.primary_image_url }]
        : undefined,
    },
    // The operator's keywords, when set; omitted rather than fabricated.
    ...(product.meta_keywords
      ? { keywords: product.meta_keywords.split(",").map((k) => k.trim()).filter(Boolean) }
      : {}),
  };
}

export default async function ProductSlugLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = await getProduct(slug);
  // A missing product must be a REAL 404. This layout is a server component,
  // so `notFound()` here sets the HTTP status — the page body is a client
  // component and can only render a "not found" screen while still
  // answering 200, which is a soft 404 (Google indexes made-up product URLs
  // forever). The page body's own not-found screen stays as the fallback
  // for client-side navigations, where the status is already settled.
  if (!product) {
    notFound();
  }
  // Real review stats gate the AggregateRating node; null means "no rating
  // claim", never a fabricated one.
  const stats = await getReviewStats(product);
  // The operator's schema override, when stored (the editor's schema
  // builder writes it). Present → replaces the built-in Product node
  // (Rank Math semantics); absent → the built-in node renders unchanged.
  const schemaOverride = await fetchSchemaOverride("product", product.id);

  return (
    <>
      {product && (
        <>
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: safeJsonLd(
                schemaOverride ?? buildProductJsonLd(product, stats),
              ),
            }}
          />
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: safeJsonLd(buildBreadcrumbJsonLd(product)),
            }}
          />
        </>
      )}
      {children}
    </>
  );
}
