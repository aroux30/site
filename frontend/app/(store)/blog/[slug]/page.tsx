import { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import { notFound } from "next/navigation";
import {
  Calendar,
  Clock,
  Eye,
  Share2,
  User,
  ArrowRight,
  Bookmark,
  ChevronRight,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { fetchBlogPostBySlug, fallbackPosts } from "@/lib/api/blog";

interface BlogPostPageProps {
  params: Promise<{
    slug: string;
  }>;
}

export async function generateMetadata({
  params,
}: BlogPostPageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchBlogPostBySlug(slug);

  if (!post) {
    return {
      title: "مقاله یافت نشد",
    };
  }

  return {
    title: `${post.title} | وبلاگ تخصصی`,
    description: post.excerpt || post.title,
    openGraph: {
      title: post.title,
      description: post.excerpt || post.title,
      type: "article",
      publishedTime: post.published_at,
      images: post.cover_image_url ? [post.cover_image_url] : [],
    },
    alternates: {
      canonical: `/blog/${post.slug}`,
    },
  };
}

export default async function BlogPostDetailPage({
  params,
}: BlogPostPageProps) {
  const { slug } = await params;
  const post = await fetchBlogPostBySlug(slug);

  if (!post) {
    notFound();
  }

  // Generate JSON-LD Structured Data
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    image: post.cover_image_url,
    datePublished: post.published_at || post.created_at,
    dateModified: post.updated_at || post.created_at,
    author: {
      "@type": "Person",
      name: post.author_name || "تیم تحریریه",
    },
    publisher: {
      "@type": "Organization",
      name: "فروشگاه اینترنتی ایرانیان",
      logo: {
        "@type": "ImageObject",
        url: "https://example.com/logo.png",
      },
    },
  };

  return (
    <>
      {/* Article JSON-LD Structured Data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ // nosemgrep: typescript.react.security.audit.react-dangerouslysetinnerhtml.react-dangerouslysetinnerhtml
          // Payload is JSON.stringify output with '<' escaped, so no HTML can
          // terminate the script tag; the content is generated server-side
          // from trusted fields only (never raw user input).
          __html: JSON.stringify(jsonLd).replace(/</g, "\u003c"),
        }}
      />

      <article className="container mx-auto px-4 py-10 max-w-4xl">
        {/* Breadcrumb Navigation */}
        <nav className="flex items-center gap-2 text-xs md:text-sm text-muted-foreground mb-8">
          <Link href="/" className="hover:text-foreground transition-colors">
            خانه
          </Link>
          <ChevronRight className="w-3.5 h-3.5 rtl:rotate-180" />
          <Link href="/blog" className="hover:text-foreground transition-colors">
            وبلاگ
          </Link>
          {post.category && (
            <>
              <ChevronRight className="w-3.5 h-3.5 rtl:rotate-180" />
              <Link
                href={`/blog?category=${post.category.slug}`}
                className="hover:text-foreground transition-colors"
              >
                {post.category.name}
              </Link>
            </>
          )}
        </nav>

        {/* Header Title Section */}
        <header className="mb-10">
          {post.category && (
            <Badge className="bg-emerald-600 text-white font-bold px-3 py-1 mb-4 text-xs">
              {post.category.name}
            </Badge>
          )}
          <h1 className="text-3xl md:text-5xl font-black leading-tight mb-6">
            {post.title}
          </h1>

          <div className="flex flex-wrap items-center justify-between gap-4 py-4 border-y border-border text-sm text-muted-foreground">
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2">
                <User className="w-4 h-4 text-emerald-600" />
                <span className="font-medium text-foreground">
                  {post.author_name || "تیم تحریریه"}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Clock className="w-4 h-4" />
                <span>{post.reading_time || 5} دقیقه مطالعه</span>
              </div>
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4" />
                <span>{post.view_count} بازدید</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" className="gap-2 text-xs">
                <Share2 className="w-3.5 h-3.5" />
                اشتراک‌گذاری
              </Button>
            </div>
          </div>
        </header>

        {/* Featured Cover Image */}
        {post.cover_image_url && (
          <div className="relative w-full h-[320px] md:h-[480px] rounded-3xl overflow-hidden mb-12 shadow-2xl border border-border">
            <Image
              src={post.cover_image_url}
              alt={post.title}
              fill
              priority
              className="object-cover"
            />
          </div>
        )}

        {/* Excerpt Lead */}
        {post.excerpt && (
          <div className="p-6 bg-muted/40 rounded-2xl border-r-4 border-emerald-600 text-lg leading-relaxed font-medium mb-10 text-muted-foreground">
            {post.excerpt}
          </div>
        )}

        {/* Main Article Body */}
        <div className="prose prose-lg dark:prose-invert max-w-none mb-16 leading-relaxed space-y-6 text-foreground/90">
          {post.content ? (
            post.content.split("\n\n").map((para, i) => {
              if (para.startsWith("## ")) {
                return (
                  <h2 key={i} className="text-2xl font-bold mt-8 mb-4">
                    {para.replace("## ", "")}
                  </h2>
                );
              }
              if (para.startsWith("### ")) {
                return (
                  <h3 key={i} className="text-xl font-bold mt-6 mb-3 text-emerald-600 dark:text-emerald-400">
                    {para.replace("### ", "")}
                  </h3>
                );
              }
              return (
                <p key={i} className="text-base md:text-lg leading-loose">
                  {para}
                </p>
              );
            })
          ) : (
            <p>متن مقاله به زودی بارگذاری می‌شود.</p>
          )}
        </div>

        {/* Author Bio Box */}
        <div className="p-8 rounded-3xl bg-card border border-border mb-16 shadow-sm flex items-center gap-6">
          <div className="w-16 h-16 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-600 shrink-0">
            <User className="w-8 h-8" />
          </div>
          <div>
            <h4 className="font-bold text-lg mb-1">{post.author_name || "تیم تحریریه"}</h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              نویسنده و کارشناس ارشد بررسی سخت‌افزار و راهنمای خرید فناوری در فروشگاه اینترنتی ایرانیان.
            </p>
          </div>
        </div>

        {/* Related Posts */}
        {post.related_posts && post.related_posts.length > 0 && (
          <section className="pt-10 border-t border-border">
            <h3 className="text-2xl font-bold mb-8">مقالات مرتبط پیشنهادی</h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {post.related_posts.map((rel) => (
                <Card
                  key={rel.id}
                  className="group overflow-hidden rounded-2xl border-border bg-card hover:shadow-lg transition-all"
                >
                  <div className="relative w-full h-40 overflow-hidden">
                    <Image
                      src={
                        rel.cover_image_url ||
                        "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600"
                      }
                      alt={rel.title}
                      fill
                      className="object-cover group-hover:scale-105 transition-transform duration-500"
                    />
                  </div>
                  <CardContent className="p-5">
                    <Link href={`/blog/${rel.slug}`}>
                      <h4 className="font-bold text-sm leading-snug line-clamp-2 group-hover:text-emerald-600 transition-colors">
                        {rel.title}
                      </h4>
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          </section>
        )}
      </article>
    </>
  );
}
