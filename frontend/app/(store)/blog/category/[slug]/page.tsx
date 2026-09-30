import { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, BookOpen, Tag } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { RemoteImage } from "@/components/shared/remote-image";
import { archiveHref, postHref } from "@/lib/permalinks";
import { getRoutingConfig } from "@/lib/routing";
import {
  fetchBlogCategories,
  fetchBlogPosts,
  type BlogPost,
  type BlogPostCategory,
} from "@/lib/api/blog";

interface Props {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

const PAGE_SIZE = 12;

async function findCategory(slug: string): Promise<BlogPostCategory | null> {
  try {
    const categories = await fetchBlogCategories();
    return categories.find((c) => c.slug === slug) ?? null;
  } catch {
    // A category service outage is not "this category does not exist";
    // rethrowing lets error.tsx offer a retry instead of a false 404.
    throw new Error("category lookup failed");
  }
}

/**
 * Category archive.
 *
 * The storefront's category filter historically lived only in a query string
 * (`/blog?category=…`), which is not a crawlable URL. This route gives each
 * category its own address so sitemap entries point somewhere real.
 */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const category = await findCategory(slug);
  if (!category) return { title: "دسته یافت نشد" };

  return {
    title: `${category.name} | وبلاگ`,
    description: `مقالات دسته ${category.name}`,
    alternates: {
      canonical: `/blog/category/${category.slug}`,
      // Per-archive feed, so a reader can follow one category. The generator
      // exists and the archive page was the only thing missing to advertise it.
      types: {
        "application/rss+xml": [
          { url: `/blog/feed/rss/category/${category.slug}`, title: category.name },
        ],
      },
    },
  };
}

export default async function BlogCategoryPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, Number(pageParam) || 1);

  // Admin permalink settings shape the post/pagination links this archive
  // renders; the archive's own route stays canonical at /blog/category/<slug>.
  const routing = await getRoutingConfig();

  const category = await findCategory(slug);
  if (!category) notFound();

  let posts: BlogPost[] = [];
  let totalPages = 1;
  try {
    const res = await fetchBlogPosts({
      category: category.slug,
      page,
      page_size: PAGE_SIZE,
    });
    posts = res.items;
    totalPages = res.total_pages;
  } catch {
    // Rendered by error.tsx so an outage never reads as "no articles".
    throw new Error("failed to load category posts");
  }

  return (
    <div className="container mx-auto max-w-5xl px-4 py-10" dir="rtl">
      <nav className="mb-6 flex items-center gap-2 text-xs text-muted-foreground">
        <Link href="/" className="transition-colors hover:text-foreground">
          خانه
        </Link>
        <span>/</span>
        <Link href="/blog" className="transition-colors hover:text-foreground">
          وبلاگ
        </Link>
        <span>/</span>
        <span className="text-foreground">{category.name}</span>
      </nav>

      <header className="mb-8">
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <BookOpen className="h-6 w-6 text-primary" />
          {category.name}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {posts.length > 0
            ? `مقالات این دسته`
            : `هنوز مقاله‌ای در این دسته منتشر نشده است`}
        </p>
      </header>

      {posts.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            محتوایی برای نمایش وجود ندارد
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((post) => (
            <Link
              key={post.id}
              href={postHref(routing.permalink_structure, {
                slug: post.slug,
                id: post.id,
                published_at: post.published_at,
                category_slug: post.category?.slug ?? null,
                author_slug: post.author_slug ?? null,
              })}
              className="group"
            >
              <Card className="h-full overflow-hidden transition-shadow hover:shadow-md">
                {post.cover_image_url && (
                  <RemoteImage
                    src={post.cover_image_url}
                    alt={post.title}
                    sizes="(max-width: 640px) 100vw, 33vw"
                    className="h-40 w-full object-cover"
                  />
                )}
                <CardContent className="p-4">
                  <h2 className="line-clamp-2 text-sm font-bold group-hover:text-primary">
                    {post.title}
                  </h2>
                  {post.excerpt && (
                    <p className="mt-2 line-clamp-3 text-xs text-muted-foreground">
                      {post.excerpt}
                    </p>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-3">
          {page > 1 && (
            <Button asChild variant="outline" size="sm">
              <Link href={`${archiveHref(routing, "category", category.slug)}?page=${page - 1}`}>قبلی</Link>
            </Button>
          )}
          <span className="text-xs text-muted-foreground">
            صفحه {page} از {totalPages}
          </span>
          {page < totalPages && (
            <Button asChild variant="outline" size="sm">
              <Link href={`${archiveHref(routing, "category", category.slug)}?page=${page + 1}`}>
                بعدی
                <ArrowRight className="ms-1 h-3.5 w-3.5" />
              </Link>
            </Button>
          )}
        </div>
      )}

      <div className="mt-10 text-center">
        <Button asChild variant="ghost" size="sm">
          <Link href="/blog">
            <Tag className="ms-1 h-3.5 w-3.5" />
            همه مقالات
          </Link>
        </Button>
      </div>
    </div>
  );
}
