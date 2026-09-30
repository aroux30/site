import Link from "next/link";
import sanitizeHtml from "sanitize-html";
import { Sparkles } from "lucide-react";
import { BentoGrid, BentoCard } from "@/components/ui/bento-grid";
import { ProductQuickCard } from "@/components/home/product-quick-card";
import { HeroInteractive, HeroActions } from "@/components/home/hero-interactive";
import type { ContentBlock } from "@/lib/api/content";
import type { ApiProduct } from "@/lib/api/services";

/**
 * Renders CMS homepage blocks (content module) in position order.
 *
 * The backend defines six BlockType values; each maps to an existing home
 * component. The admin supplies `config` per block from the CMS panel — the
 * renderer never invents content for a block that has no config.
 *
 * Any error or missing config for a block renders nothing for THAT block
 * (never a fabricated card), while the rest of the blocks still render.
 */

type Config = Record<string, unknown>;

function SliderBlock({ config }: { config: Config }) {
  const title = typeof config.title === "string" ? config.title : null;
  const subtitle = typeof config.subtitle === "string" ? config.subtitle : "";
  return (
    <section className="relative overflow-hidden pt-6 pb-12 lg:pt-10 lg:pb-16 bg-gradient-to-b from-emerald-500/5 via-background to-background">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-12 items-center">
          <div className="lg:col-span-7 space-y-6 text-center lg:text-right">
            <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>پلتفرم مدرن ایکامرس ایران</span>
            </div>
            {title && (
              <h1 className="text-3xl sm:text-4xl lg:text-6xl font-black text-foreground tracking-tight leading-[1.2]">
                {title}
              </h1>
            )}
            {subtitle && (
              <p className="text-muted-foreground text-sm sm:text-base lg:text-lg max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                {subtitle}
              </p>
            )}
            <HeroActions />
          </div>
          <div className="lg:col-span-5 flex justify-center">
            <HeroInteractive />
          </div>
        </div>
      </div>
    </section>
  );
}

function CategoryGridBlock({ config }: { config: Config }) {
  const items = Array.isArray(config.items) ? config.items : [];
  if (items.length === 0) return null;
  return (
    <section className="py-14 sm:py-20">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        <BentoGrid className="grid-cols-1 md:grid-cols-3 gap-6">
          {items.map((raw: unknown, i: number) => {
            const item = raw as { name?: string; slug?: string; description?: string };
            if (!item?.slug || !item?.name) return null;
            return (
              <BentoCard
                key={i}
                name={item.name}
                className={i % 4 === 0 || i % 4 === 3 ? "md:col-span-2 bg-card border-border/80" : "md:col-span-1 bg-card border-border/80"}
                description={item.description ?? ""}
                href={`/products?category=${encodeURIComponent(item.slug)}`}
                cta="مشاهده محصولات"
              />
            );
          })}
        </BentoGrid>
      </div>
    </section>
  );
}

function FeaturedProductsBlock({ config }: { config: Config }) {
  const products = Array.isArray(config.products) ? (config.products as ApiProduct[]) : [];
  if (products.length === 0) return null;
  return (
    <section className="py-14 sm:py-20">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
          {products.map((product) => (
            <ProductQuickCard key={product.id} product={product} featured={product.is_featured} />
          ))}
        </div>
      </div>
    </section>
  );
}

function DiscountCarouselBlock({ config }: { config: Config }) {
  const items = Array.isArray(config.items) ? config.items : [];
  if (items.length === 0) return null;
  return (
    <section className="py-14 sm:py-20">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        <div className="flex gap-4 overflow-x-auto pb-4 no-scrollbar">
          {items.map((raw: unknown, i: number) => {
            const item = raw as { title?: string; href?: string; image_url?: string };
            if (!item?.href) return null;
            return (
              <Link
                key={i}
                href={item.href}
                className="min-w-[220px] rounded-2xl border border-border bg-card p-5 shadow-sm hover:shadow-lg transition"
              >
                {item.title && <span className="font-bold text-foreground text-sm">{item.title}</span>}
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function BannerGridBlock({ config }: { config: Config }) {
  const items = Array.isArray(config.items) ? config.items : [];
  if (items.length === 0) return null;
  return (
    <section className="py-6">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {items.map((raw: unknown, i: number) => {
            const item = raw as { title?: string; subtitle?: string; href?: string; cta_label?: string };
            if (!item?.href) return null;
            return (
              <Link key={i} href={item.href} className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-emerald-900 via-slate-900 to-slate-950 p-8 border border-emerald-500/30 text-white shadow-xl hover:shadow-2xl transition">
                {item.title && <h3 className="text-xl font-black">{item.title}</h3>}
                {item.subtitle && <p className="text-sm text-slate-200 mt-2">{item.subtitle}</p>}
                {item.cta_label && <span className="mt-4 inline-block text-xs font-bold text-emerald-300">{item.cta_label}</span>}
              </Link>
            );
          })}
        </div>
      </div>
    </section>
  );
}

function HtmlCustomBlock({ config }: { config: Config }) {
  const html = typeof config.html === "string" ? config.html : "";
  if (!html.trim()) return null;
  return (
    <section className="py-14">
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl prose dark:prose-invert max-w-none">
        <div
          dangerouslySetInnerHTML={{
            __html: sanitizeHtml(html, {
              allowedTags: sanitizeHtml.defaults.allowedTags.concat(["img"]),
              allowedAttributes: {
                ...sanitizeHtml.defaults.allowedAttributes,
                img: ["src", "alt", "width", "height"],
              },
            }),
          }}
        />
      </div>
    </section>
  );
}

export function BlockRenderer({ block }: { block: ContentBlock }) {
  const config = (block.config ?? {}) as Config;
  switch (block.block_type) {
    case "slider":
      return <SliderBlock config={config} />;
    case "category_grid":
      return <CategoryGridBlock config={config} />;
    case "featured_products":
      return <FeaturedProductsBlock config={config} />;
    case "discount_carousel":
      return <DiscountCarouselBlock config={config} />;
    case "banner_grid":
      return <BannerGridBlock config={config} />;
    case "html_custom":
      return <HtmlCustomBlock config={config} />;
    default:
      return null;
  }
}
