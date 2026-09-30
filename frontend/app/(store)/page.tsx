import type { Metadata } from "next";
import Link from "next/link";
import {
  Truck,
  Shield,
  RotateCcw,
  Headphones,
  ChevronLeft,
  Zap,
  Sparkles,
  CreditCard,
  AlertCircle,
  PackageSearch,
} from "lucide-react";
import { BentoGrid, BentoCard } from "@/components/ui/bento-grid";
import { Marquee } from "@/components/ui/marquee";
import { NumberTicker } from "@/components/ui/number-ticker";
import { HeroInteractive, HeroActions } from "@/components/home/hero-interactive";
import { ProductQuickCard } from "@/components/home/product-quick-card";
import { ErrorState } from "@/components/shared/page-state";
import { BlockRenderer } from "@/components/home/block-renderer";
import { TrustBadgesSection } from "@/components/shared/trust-badges";
import { contentApi, type ContentBlock } from "@/lib/api/content";
import { apiInternalUrl } from "@/lib/api/server-base";
import cleanHtml from "@/lib/sanitize-html";
import type { ApiProduct, ApiCategory } from "@/lib/api/services";

const DEFAULT_HOME_METADATA: Metadata = {
  title: "فروشگاه آنلاین ایرانیان | خرید آسان، مطمئن و با ضمانت اصالت",
  description:
    "مرجع تخصصی خرید انواع گوشی‌های هوشمند، لپ‌تاپ، لوازم جانبی و تجهیزات دیجیتال با گارانتی رسمی، ارسال رایگان و پرداخت امن شتاب.",
  openGraph: {
    title: "فروشگاه آنلاین ایرانیان",
    description: "مرجع تخصصی خرید تجهیزات دیجیتال با گارانتی رسمی و ارسال رایگان سراسری.",
    type: "website",
  },
};

/* ------------------------------------------------------------------ */
/*  Server-side catalog fetches (ISR, 5 min)                           */
/*                                                                      */
/*  SSRF guard: the target comes exclusively from operator              */
/*  configuration (build/runtime env), never from user input. Only      */
/*  absolute http(s) URLs are honored.                                  */
/*                                                                      */
/*  Errors are surfaced as explicit Persian error states; nothing       */
/*  collapses silently to an empty array or a fabricated fallback.      */
/* ------------------------------------------------------------------ */

type FetchResult<T> = { ok: true; data: T } | { ok: false };

function apiBase(): string | null {
  const base = apiInternalUrl();
  if (!/^https?:\/\//i.test(base)) return null;
  return base;
}

async function fetchFeaturedProducts(): Promise<FetchResult<ApiProduct[]>> {
  const base = apiBase();
  if (!base) return { ok: false };
  try {
    const res = await fetch(
      `${base}/catalog/products?is_featured=true&is_active=true&page_size=6`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { ok: false };
    const data = (await res.json()) as { items?: ApiProduct[] };
    return { ok: true, data: data.items ?? [] };
  } catch {
    return { ok: false };
  }
}

async function fetchActiveCategories(): Promise<FetchResult<ApiCategory[]>> {
  const base = apiBase();
  if (!base) return { ok: false };
  try {
    const res = await fetch(
      `${base}/catalog/categories?is_active=true&page_size=4`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { ok: false };
    const data = (await res.json()) as { items?: ApiCategory[] };
    return { ok: true, data: data.items ?? [] };
  } catch {
    return { ok: false };
  }
}

async function fetchActiveProductCount(): Promise<FetchResult<number>> {
  const base = apiBase();
  if (!base) return { ok: false };
  try {
    const res = await fetch(
      `${base}/catalog/products?is_active=true&page_size=1`,
      { next: { revalidate: 300 } },
    );
    if (!res.ok) return { ok: false };
    const data = (await res.json()) as { meta?: { total?: number } };
    return { ok: true, data: data.meta?.total ?? 0 };
  } catch {
    return { ok: false };
  }
}

interface StaticFrontPage {
  title: string;
  slug: string;
  body_html: string;
  excerpt: string | null;
  seo_title: string | null;
  seo_description: string | null;
}

/**
 * WordPress "static front page": when the operator selects a CMS page, "/"
 * serves it instead of the built-in home. The backend resolves the slug
 * (and checks the page is still published); any failure — unset, deleted,
 * or an API outage — returns null and the default home renders, because a
 * stale pointer must never blank the storefront.
 */
async function fetchStaticFrontPage(): Promise<StaticFrontPage | null> {
  const base = apiBase();
  if (!base) return null;
  try {
    const resolved = await fetch(`${base}/settings/public/front-page`, {
      next: { revalidate: 300 },
    });
    if (!resolved.ok) return null;
    const { slug } = (await resolved.json()) as { slug: string | null };
    if (!slug) return null;
    const pageRes = await fetch(
      `${base}/content/pages/${encodeURIComponent(slug)}`,
      { next: { revalidate: 300 } },
    );
    if (!pageRes.ok) return null;
    return (await pageRes.json()) as StaticFrontPage;
  } catch {
    return null;
  }
}

export async function generateMetadata(): Promise<Metadata> {
  const frontPage = await fetchStaticFrontPage();
  if (!frontPage) return DEFAULT_HOME_METADATA;
  return {
    title: frontPage.seo_title || frontPage.title,
    description: frontPage.seo_description || frontPage.excerpt || undefined,
    openGraph: {
      title: frontPage.seo_title || frontPage.title,
      description: frontPage.seo_description || frontPage.excerpt || undefined,
      type: "article",
    },
  };
}

export default async function HomePage() {
  // WordPress "static front page" wins over everything: the operator chose
  // this page as "/", so it renders as-is (same article shell as any other
  // CMS page). Null — unset, unpublished, or an outage — falls through to
  // the homepage blocks / default rendering below.
  const frontPage = await fetchStaticFrontPage();
  if (frontPage) {
    return (
      <article className="mx-auto max-w-3xl px-4 py-10">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-foreground">{frontPage.title}</h1>
          {frontPage.excerpt ? (
            <p className="mt-3 text-muted-foreground">{frontPage.excerpt}</p>
          ) : null}
        </header>
        <div
          className="cms-content max-w-none leading-8 text-foreground [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-bold [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-semibold [&_p]:my-4 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:ps-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:ps-6 [&_a]:text-primary [&_a]:underline [&_img]:my-4 [&_img]:rounded-lg [&_blockquote]:border-s-4 [&_blockquote]:border-primary/30 [&_blockquote]:ps-4 [&_blockquote]:text-muted-foreground"
          // body_html is editor-authored, but an admin account is not an XSS
          // license — sanitize before dangerouslySetInnerHTML.
          dangerouslySetInnerHTML={{ __html: cleanHtml(frontPage.body_html) }}
        />
      </article>
    );
  }

  const [featured, categories, productCount] = await Promise.all([
    fetchFeaturedProducts(),
    fetchActiveCategories(),
    fetchActiveProductCount(),
  ]);

  // CMS-driven homepage: if the admin has configured homepage blocks in the
  // content module, they win. Errors or an empty block list fall back to the
  // default FE-09 rendering below — the home page never crashes or goes blank.
  let blocks: ContentBlock[] = [];
  try {
    blocks = await contentApi.getHomepageBlocks();
  } catch {
    blocks = [];
  }
  if (blocks.length > 0) {
    return (
      <div className="flex flex-col min-h-screen">
        {blocks.map((block) => (
          <BlockRenderer key={block.id} block={block} />
        ))}
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* ── 1. Hero Section (SSR Shell + Client 3D Island) ── */}
      <section className="relative overflow-hidden pt-6 pb-12 lg:pt-10 lg:pb-16 bg-gradient-to-b from-emerald-500/5 via-background to-background">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
            {/* Left Content (Text + CTAs) */}
            <div className="lg:col-span-7 space-y-6 text-center lg:text-right">
              <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                <span>پلتفرم مدرن ایکامرس ایران • تجربه خرید هوشمند</span>
              </div>

              <h1 className="text-3xl sm:text-4xl lg:text-6xl font-black text-foreground tracking-tight leading-[1.2]">
                تجربه خریدی <span className="text-emerald-600 dark:text-emerald-400">سریع، مطمئن</span> و فراتر از انتظار
              </h1>

              <p className="text-muted-foreground text-sm sm:text-base lg:text-lg max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                دسترسی مستقیم به برترین پرچمداران دیجیتال، گجت‌های هوشمند و لوازم جانبی اورجینال با ارسال اکسپرس، ضمانت اصالت ۱۰۰٪ و درگاه‌های امن بانکی و کریپتو.
              </p>

              {/* Client Action Buttons Island */}
              <HeroActions />

              {/* Real catalog counter — only when the API answered */}
              {productCount.ok && productCount.data > 0 && (
                <div className="pt-6 border-t border-border/60 max-w-lg mx-auto lg:mx-0 flex justify-center lg:justify-start">
                  <div>
                    <div className="text-2xl lg:text-3xl font-black text-foreground">
                      <NumberTicker value={productCount.data} className="text-foreground" />
                    </div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      کالای فعال در فروشگاه
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Right Content (Client 3D Island) */}
            <div className="lg:col-span-5 flex justify-center">
              <HeroInteractive />
            </div>
          </div>
        </div>
      </section>

      {/* ── 2. Value Propositions Marquee ── */}
      <div className="py-4 border-y border-border/60 bg-muted/20">
        <Marquee pauseOnHover className="[--duration:25s]">
          <div className="flex items-center gap-12 text-sm font-semibold text-muted-foreground px-4">
            <span className="flex items-center gap-2">
              <Truck className="w-4 h-4 text-emerald-500" />
              ارسال فوق‌سریع به سراسر ایران
            </span>
            <span className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-500" />
              ضمانت اصالت ۱۰۰٪ کالاها
            </span>
            <span className="flex items-center gap-2">
              <RotateCcw className="w-4 h-4 text-emerald-500" />
              ۷ روز فرصت تست و بازگشت
            </span>
            <span className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-emerald-500" />
              پرداخت امن از درگاه‌های شتاب و تتر
            </span>
            <span className="flex items-center gap-2">
              <Headphones className="w-4 h-4 text-emerald-500" />
              مشاوره و پشتیبانی ۲۴/۷
            </span>
          </div>
        </Marquee>
      </div>

      {/* ── 3. Featured Categories (real catalog data) ── */}
      <section className="py-14 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-10 gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2">
                <Sparkles className="w-3.5 h-3.5" />
                دسته‌بندی‌های فروشگاه
              </div>
              <h2 className="heading-display">کاوش بر اساس دسته‌بندی</h2>
            </div>
            <Link
              href="/products"
              className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 hover:underline inline-flex items-center gap-1"
            >
              مشاهده تمامی دسته‌ها
              <ChevronLeft className="w-4 h-4" />
            </Link>
          </div>

          {!categories.ok ? (
            <ErrorState
              title="دریافت دسته‌بندی‌ها ممکن نشد"
              description="ارتباط با سرور برقرار نشد. لطفاً صفحه را دوباره بارگذاری کنید."
              action={
                <Link
                  href="/"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-destructive/30 px-4 py-2 text-sm font-semibold text-destructive hover:bg-destructive/10"
                >
                  بارگذاری مجدد
                </Link>
              }
            />
          ) : categories.data.length > 0 ? (
            <BentoGrid className="grid-cols-1 md:grid-cols-3 gap-6">
              {categories.data.map((cat, i) => (
                <BentoCard
                  key={cat.id}
                  name={cat.name}
                  className={
                    i % 4 === 0 || i % 4 === 3
                      ? "md:col-span-2 bg-card border-border/80"
                      : "md:col-span-1 bg-card border-border/80"
                  }
                  Icon={PackageSearch}
                  description={cat.description ?? ""}
                  href={`/products?category=${encodeURIComponent(cat.slug)}`}
                  cta="مشاهده محصولات"
                />
              ))}
            </BentoGrid>
          ) : null}
        </div>
      </section>

      {/* ── 4. Featured Products Grid (real catalog data) ── */}
      <section className="py-14 sm:py-20">
        <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
          <div className="flex flex-col sm:flex-row sm:items-end justify-between mb-10 gap-4">
            <div>
              <div className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-600 dark:text-emerald-400 mb-2">
                <Zap className="w-3.5 h-3.5" />
                کالاهای منتخب پرچمدار
              </div>
              <h2 className="heading-display">پرفروش‌ترین‌های این هفته</h2>
            </div>
            <Link
              href="/products"
              className="text-xs sm:text-sm font-semibold text-emerald-600 dark:text-emerald-400 hover:underline inline-flex items-center gap-1"
            >
              مشاهده تمام کالاها
              <ChevronLeft className="w-4 h-4" />
            </Link>
          </div>

          {!featured.ok ? (
            <ErrorState
              title="دریافت محصولات ممکن نشد"
              description="ارتباط با سرور برقرار نشد. لطفاً صفحه را دوباره بارگذاری کنید."
              action={
                <Link
                  href="/"
                  className="inline-flex items-center gap-1.5 rounded-xl border border-destructive/30 px-4 py-2 text-sm font-semibold text-destructive hover:bg-destructive/10"
                >
                  بارگذاری مجدد
                </Link>
              }
            />
          ) : featured.data.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
              {featured.data.map((product) => (
                <ProductQuickCard
                  key={product.id}
                  product={product}
                  featured={product.is_featured}
                />
              ))}
            </div>
          ) : (
            <ErrorState
              title="فعلاً محصول منتخبی ثبت نشده است"
              description="به‌زودی کالاهای منتخب جدید اضافه می‌شوند."
              className="border-border bg-muted/20 [&_h3]:text-foreground [&_svg]:text-muted-foreground"
            />
          )}
        </div>
      </section>

      {/* ── 5. Enterprise Trust & Guarantees Section ── */}
      <TrustBadgesSection />
    </div>
  );
}
