import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { RemoteImage } from "@/components/shared/remote-image";
import {
  fetchCustomTaxonomyTerms,
  fetchCustomTaxonomyTermPosts,
  type CustomTaxonomyTerm,
} from "@/lib/api/blog";

/** Posts in one term of a custom taxonomy.
 *
 *  The sibling of `blog/tag/[slug]`, which does the same for the built-in tag
 *  taxonomy. Separate rather than shared because the two are filtered
 *  differently: `fetchBlogPosts({ tag })` speaks the built-in vocabulary, and a
 *  custom term's id means nothing there — an archive that reused it would
 *  render the wrong posts under the right heading.
 *
 *  Filtered server-side, on purpose. Paging the whole blog and filtering on the
 *  page looks the same and stops being right as soon as the blog has more posts
 *  than fit in one page.
 */

export const revalidate = 120;

const PAGE_SIZE = 12;

interface Props {
  params: Promise<{ taxonomy: string; slug: string }>;
  searchParams: Promise<{ page?: string }>;
}

async function loadTerm(
  taxonomy: string,
  slug: string,
): Promise<{ terms: CustomTaxonomyTerm[]; term: CustomTaxonomyTerm } | null> {
  // A taxonomy whose slug was retired answers 404 or 500. Either way this page
  // has nothing to show, and a thrown error would take the whole storefront's
  // error reporting with it for one missing archive.
  const terms = await fetchCustomTaxonomyTerms(taxonomy).catch(() => null);
  if (terms === null) return null;
  const term = terms.find((t) => t.slug === slug);
  return term ? { terms, term } : null;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { taxonomy, slug } = await params;
  const found = await loadTerm(taxonomy, slug).catch(() => null);
  if (!found) return { title: "یافت نشد" };
  return {
    title: found.term.name,
    description: found.term.description ?? undefined,
    alternates: { canonical: `/${taxonomy}/${slug}` },
  };
}

export default async function CustomTaxonomyTermPage({
  params,
  searchParams,
}: Props) {
  const { taxonomy, slug } = await params;
  const { page: pageParam } = await searchParams;
  const page = Math.max(1, Number.parseInt(pageParam ?? "1", 10) || 1);

  const found = await loadTerm(taxonomy, slug);
  if (!found) notFound();
  const { terms, term } = found;

  const data = await fetchCustomTaxonomyTermPosts(
    taxonomy,
    slug,
    page,
    PAGE_SIZE,
  ).catch(() => null);
  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 0;

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8" dir="rtl">
      <nav className="mb-4 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground">
          خانه
        </Link>
        <span className="mx-1">/</span>
        <Link href={`/${taxonomy}`} className="hover:text-foreground">
          {terms[0]?.name ?? taxonomy}
        </Link>
        <span className="mx-1">/</span>
        <span>{term.name}</span>
      </nav>

      <header className="mb-6">
        <h1 className="text-2xl font-bold">{term.name}</h1>
        {term.description && (
          <p className="mt-2 text-sm text-muted-foreground">
            {term.description}
          </p>
        )}
      </header>

      {items.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-sm text-muted-foreground">
            در این دسته هنوز نوشته‌ای منتشر نشده است.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((post) => (
            <Link
              key={post.id}
              href={`/blog/${post.slug}`}
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
            <Link
              href={`/${taxonomy}/${slug}?page=${page - 1}`}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
            >
              قبلی
            </Link>
          )}
          <span className="text-xs text-muted-foreground">
            صفحه {page} از {totalPages}
          </span>
          {page < totalPages && (
            <Link
              href={`/${taxonomy}/${slug}?page=${page + 1}`}
              className="rounded-md border border-border px-4 py-2 text-sm hover:bg-muted"
            >
              بعدی
            </Link>
          )}
        </div>
      )}
    </div>
  );
}