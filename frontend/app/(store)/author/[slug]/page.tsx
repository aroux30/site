"use client";

/** Author archive (WordPress parity: /author/<slug>).
 *
 * The permalink structure accepts %author% and links here; before this page
 * existed every such link 404'd. The slug is stable (users.author_slug), so a
 * profile rename never breaks an archive URL.
 */
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowRight, Loader2, User as UserIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { fetchAuthorArchive } from "@/lib/api/blog";
import type { BlogPost } from "@/lib/api/blog";
import { postHref } from "@/lib/permalinks";
import { useRoutingConfig } from "@/lib/use-routing";
import { toPersianDigits } from "@/lib/utils";

const PAGE_SIZE = 10;

export default function AuthorArchivePage() {
  const { toast } = useToast();
  const router = useRouter();
  const params = useParams<{ slug: string }>();
  const slug = params?.slug ?? "";
  const routing = useRoutingConfig();

  const [author, setAuthor] = useState<{
    slug: string;
    name: string;
    bio?: string | null;
    avatar_url?: string | null;
    post_count: number;
  } | null>(null);
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);

  const load = useCallback(
    async (targetPage: number, signal?: AbortSignal) => {
      setLoading(true);
      try {
        const res = await fetchAuthorArchive(slug, targetPage, PAGE_SIZE);
        setAuthor(res.author);
        setPosts(res.posts.items);
        setTotalPages(res.posts.total_pages);
        setPage(res.posts.page);
      } catch {
        // A missing slug is a 404, not an error toast: the archive is a
        // destination a crawler may have guessed.
        if (!signal?.aborted) router.replace("/blog");
      } finally {
        setLoading(false);
      }
    },
    [slug, router],
  );

  useEffect(() => {
    if (!slug) return;
    const controller = new AbortController();
    void load(1, controller.signal);
    return () => controller.abort();
  }, [slug, load]);

  if (loading) {
    return (
      <div className="container flex min-h-[40vh] items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!author) return null;

  return (
    <div className="container py-10" dir="rtl">
      <nav className="mb-6 text-sm text-muted-foreground">
        <Link href="/blog" className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowRight className="h-4 w-4" />
          وبلاگ
        </Link>
      </nav>

      <header className="mb-8 flex items-start gap-4">
        {author.avatar_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={author.avatar_url}
            alt={author.name}
            className="h-16 w-16 rounded-full object-cover"
          />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
            <UserIcon className="h-7 w-7 text-muted-foreground" />
          </div>
        )}
        <div>
          <h1 className="text-2xl font-bold">{author.name}</h1>
          <p className="text-sm text-muted-foreground">
            {toPersianDigits(author.post_count)} نوشته
          </p>
          {author.bio && <p className="mt-2 max-w-2xl text-sm">{author.bio}</p>}
        </div>
      </header>

      {posts.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            این نویسنده هنوز نوشته‌ای منتشر نکرده است.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {posts.map((post) => (
            <Card key={post.id} className="overflow-hidden">
              <CardContent className="p-5">
                {post.category && (
                  <p className="mb-2 text-xs text-muted-foreground">{post.category.name}</p>
                )}
                <h2 className="mb-2 text-lg font-semibold leading-snug">
                  <Link
                    href={postHref(routing.permalink_structure, {
                      slug: post.slug,
                      id: post.id,
                      published_at: post.published_at,
                      category_slug: post.category?.slug ?? null,
                      author_slug: post.author_slug ?? null,
                    })}
                    className="hover:text-primary"
                  >
                    {post.title}
                  </Link>
                </h2>
                {post.excerpt && (
                  <p className="line-clamp-3 text-sm text-muted-foreground">{post.excerpt}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-8 flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1 || loading}
            onClick={() => void load(page - 1)}
          >
            قبلی
          </Button>
          <span className="text-sm text-muted-foreground">
            {toPersianDigits(page)} از {toPersianDigits(totalPages)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages || loading}
            onClick={() => void load(page + 1)}
          >
            بعدی
          </Button>
        </div>
      )}
    </div>
  );
}
