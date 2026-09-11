import type { Metadata } from "next";
import {
  fetchProductBySlug,
  type ApiProductDetail,
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

function buildProductJsonLd(product: ApiProductDetail) {
  const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
  // Backend stores prices in Toman; Google structured data expects IRR.
  const priceRial = Math.round(product.min_price || 0) * 10;
  return {
    "@context": "https://schema.org",
    "@type": "Product",
    name: product.name,
    description: product.short_description || product.description || undefined,
    image: product.primary_image_url || undefined,
    sku: product.slug,
    brand: product.brand
      ? { "@type": "Brand", name: product.brand.name }
      : undefined,
    category: product.category?.name,
    offers: {
      "@type": "Offer",
      url: `${SITE_URL}/products/${product.slug}`,
      priceCurrency: "IRR",
      price: priceRial,
      availability: product.is_active
        ? "https://schema.org/InStock"
        : "https://schema.org/OutOfStock",
      itemCondition: "https://schema.org/NewCondition",
    },
  };
}

function buildBreadcrumbJsonLd(product: ApiProductDetail) {
  const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";
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
    return { title: "جزئیات محصول" };
  }

  const title = product.name;
  const description =
    product.short_description ||
    product.description?.slice(0, 160) ||
    "خرید با بهترین قیمت بازار، گارانتی رسمی و ارسال سریع.";

  return {
    title,
    description,
    alternates: { canonical: `/products/${slug}` },
    openGraph: {
      title,
      description,
      type: "website",
      images: product.primary_image_url
        ? [{ url: product.primary_image_url }]
        : undefined,
    },
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

  return (
    <>
      {product && (
        <>
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify(buildProductJsonLd(product)),
            }}
          />
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify(buildBreadcrumbJsonLd(product)),
            }}
          />
        </>
      )}
      {children}
    </>
  );
}
