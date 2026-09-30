"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  BookOpen,
  Calendar,
  Clock,
  Eye,
  Search,
  Sparkles,
  Tag,
  TrendingUp,
  User,
  ArrowLeft,
  ChevronRight,
  ChevronLeft,
  Rss,
  MessageSquare,
  Images,
  Video,
  CalendarDays,
} from "lucide-react";

import { WidgetArea } from "@/components/layout/widget-area";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState } from "@/components/shared/page-state";
import { RemoteImage } from "@/components/shared/remote-image";
import {
  BlogPost,
  BlogPostCategory,
  BlogTag,
  fetchBlogCategories,
  fetchBlogPosts,
  fetchBlogTags,
} from "@/lib/api/blog";
import { archiveHref, dateArchiveHref, postHref } from "@/lib/permalinks";
import { useRoutingConfig } from "@/lib/use-routing";

export default function BlogPage() {
  // Customised permalink structure/base changes the URLs the list links to;
  // an unconfigured install keeps the canonical /blog/... paths.
  const routing = useRoutingConfig();
  const postLink = (post: BlogPost) =>
    postHref(routing.permalink_structure, {
      slug: post.slug,
      id: post.id,
      published_at: post.published_at,
      category_slug: post.category?.slug ?? null,
      author_slug: post.author_slug ?? null,
    });
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [categories, setCategories] = useState<BlogPostCategory[]>([]);
  const [tags, setTags] = useState<BlogTag[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [loadError, setLoadError] = useState<boolean>(false);

  useEffect(() => {
    async function loadCategories() {
      try {
        const cats = await fetchBlogCategories();
        setCategories(cats);
      } catch {
        // Category tabs degrade to "همه دسته‌ها" only; the post list still
        // shows its own explicit error below — no silent empty chrome.
      }
    }
    async function loadTags() {
      try {
        const t = await fetchBlogTags();
        setTags(t);
      } catch {
        // Tags are optional chrome; a tag outage must not hide the post list.
      }
    }
    loadCategories();
    loadTags();
  }, []);

  const loadPosts = useCallback(async () => {
    setIsLoading(true);
    setLoadError(false);
    try {
      const res = await fetchBlogPosts({
        category: selectedCategory === "all" ? undefined : selectedCategory,
        tag: selectedTag || undefined,
        search: searchQuery || undefined,
        page,
        page_size: 6,
      });
      setPosts(res.items);
      setTotalPages(res.total_pages);
    } catch {
      // A failed fetch is NOT an empty blog — show the error state so the
      // user can retry instead of believing there are no articles.
      setLoadError(true);
      setPosts([]);
    } finally {
      setIsLoading(false);
    }
  }, [selectedCategory, selectedTag, searchQuery, page]);

  useEffect(() => {
    loadPosts();
  }, [loadPosts]);

  const featuredPost = posts[0];
  const regularPosts = posts.slice(1);

  // Years that actually have posts, newest first. Derived from the loaded
  // page rather than fetched separately, so the link list costs no request.
  // Falls back to the current year so the row is never empty on a fresh blog.
  const archiveYears = Array.from(
    new Set(
      posts
        .map((p) => (p.published_at ? new Date(p.published_at).getFullYear() : null))
        .filter((y): y is number => typeof y === "number" && !Number.isNaN(y)),
    ),
  ).sort((a, b) => b - a);
  if (archiveYears.length === 0) archiveYears.push(new Date().getFullYear());

  return (
    <div className="container mx-auto px-4 py-12 max-w-7xl">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-emerald-900 via-teal-900 to-slate-950 p-8 md:p-14 mb-12 text-white shadow-2xl border border-emerald-800/40">
        <div className="absolute top-0 left-0 -translate-x-12 -translate-y-12 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 max-w-3xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-medium mb-4 border border-emerald-500/30">
            <Sparkles className="w-3.5 h-3.5" />
            مجله تخصصی فناوری و راهنمای خرید
          </div>
          <h1 className="text-3xl md:text-5xl font-black mb-4 leading-tight">
            آخرین مقالات، اخبار و تحلیل‌های دنیای گجت‌ها
          </h1>
          <p className="text-slate-300 text-base md:text-lg leading-relaxed mb-8">
            بررسی تخصصی جدیدترین تلفن‌های هوشمند، لپ‌تاپ‌ها، ترفندهای کاربردی و راهنمای خرید برای انتخاب هوشمندانه‌ترین محصول بازار
          </p>

          {/* Search bar inside hero + RSS */}
          <div className="flex flex-wrap items-center gap-3 max-w-lg">
            <div className="relative flex-1 min-w-[240px]">
              <Search className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <Input
                type="text"
                placeholder="جستجو در میان صدها مقاله..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="bg-white/10 border-white/20 text-white placeholder:text-slate-400 ps-12 pe-4 py-6 rounded-2xl focus:bg-white/15 focus:border-emerald-400"
              />
            </div>
            <Button
              variant="outline"
              asChild
              className="bg-white/10 hover:bg-white/20 text-white border-white/20 rounded-2xl h-[50px] px-4 gap-2"
            >
              <a href="/api/v1/blog/feed/rss" target="_blank" rel="noopener noreferrer">
                <Rss className="w-4 h-4 text-amber-400" />
                خوراک RSS
              </a>
            </Button>
          </div>
        </div>
      </div>

      {/* Category Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-4 mb-10 no-scrollbar border-b border-border">
        <button
          onClick={() => {
            setSelectedCategory("all");
            setPage(1);
          }}
          className={`px-5 py-2.5 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
            selectedCategory === "all"
              ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/30"
              : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
          }`}
        >
          همه دسته‌ها
        </button>
        {categories.map((cat) => (
          <Link
            key={cat.id}
            href={archiveHref(routing, "category", cat.slug)}
            className={`px-5 py-2.5 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
              selectedCategory === cat.slug
                ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/30"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            }`}
          >
            {cat.name}
          </Link>
        ))}
      </div>

      {/* Tag filter chips */}
      {tags.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-10">
          <span className="text-xs text-muted-foreground inline-flex items-center gap-1">
            <Tag className="w-3.5 h-3.5" /> برچسب‌ها:
          </span>
          {selectedTag && (
            <button
              onClick={() => {
                setSelectedTag(null);
                setPage(1);
              }}
              className="rounded-full bg-emerald-600 px-3 py-1 text-xs font-medium text-white shadow"
            >
              حذف فیلتر ×
            </button>
          )}
          {tags.map((tag) => (
            <Link
              key={tag.id}
              href={archiveHref(routing, "tag", tag.slug)}
              className={`rounded-full border px-3 py-1 text-xs transition-all ${
                selectedTag === tag.slug
                  ? "border-emerald-600 bg-emerald-600/10 font-medium text-emerald-600"
                  : "border-border bg-muted/50 text-muted-foreground hover:border-emerald-500/40 hover:text-foreground"
              }`}
            >
              #{tag.name}
              {typeof tag.post_count === "number" && tag.post_count > 0
                ? ` (${tag.post_count})`
                : ""}
            </Link>
          ))}
        </div>
      )}

      {/* Date archive. Without this link the whole /blog/archive tree was
          reachable only by typing the URL — the same unreachability the admin
          nav guard exists to prevent, on the storefront side. */}
      <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
        <CalendarDays className="h-3.5 w-3.5" />
        <span>آرشیو زمانی:</span>
        {archiveYears.map((y) => (
          <Link
            key={y}
            href={dateArchiveHref(y)}
            className="rounded-full border border-border px-2.5 py-0.5 transition-colors hover:border-emerald-500/40 hover:text-foreground"
          >
            {y}
          </Link>
        ))}
      </div>

      {/* Content Section */}
      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {[1, 2, 3, 4, 5, 6].map((n) => (
            <div
              key={n}
              className="rounded-2xl border border-border bg-card p-4 space-y-4 animate-pulse"
            >
              <div className="w-full h-48 bg-muted rounded-xl" />
              <div className="h-6 bg-muted rounded w-3/4" />
              <div className="h-4 bg-muted rounded w-full" />
              <div className="h-4 bg-muted rounded w-2/3" />
            </div>
          ))}
        </div>
      ) : loadError ? (
        <ErrorState
          title="دریافت مقالات ناموفق بود"
          description="ارتباط با سرور برقرار نشد. لطفاً دوباره تلاش کنید."
          onRetry={loadPosts}
        />
      ) : posts.length === 0 ? (
        <div className="text-center py-20 bg-muted/30 rounded-3xl border border-border">
          <BookOpen className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h3 className="text-xl font-bold mb-2">مقاله‌ای با این مشخصات یافت نشد</h3>
          <p className="text-muted-foreground text-sm">
            لطفاً عبارت دیگری را جستجو کنید یا دسته‌بندی دیگری انتخاب نمایید.
          </p>
        </div>
      ) : (
        <div className="space-y-12">
          {/* Featured Post (Hero Article) */}
          {featuredPost && page === 1 && !searchQuery && selectedCategory === "all" && (
            <div className="group relative rounded-3xl overflow-hidden border border-border bg-card shadow-xl transition-all duration-300 hover:shadow-2xl">
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-0">
                <div className="relative lg:col-span-7 h-72 lg:h-[450px] overflow-hidden">
                  <RemoteImage
                    src={featuredPost.cover_image_url}
                    alt={featuredPost.title}
                    sizes="(max-width: 1024px) 100vw, 58vw"
                    className="object-cover transition-transform duration-700 group-hover:scale-105"
                  />
                  <div className="absolute top-4 right-4 z-10">
                    <Badge className="bg-emerald-600 text-white font-bold px-3 py-1.5 shadow-md">
                      مقاله ویژه
                    </Badge>
                  </div>
                </div>
                <div className="lg:col-span-5 p-8 lg:p-12 flex flex-col justify-between">
                  <div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mb-4">
                      {featuredPost.category && (
                        <span className="text-emerald-600 dark:text-emerald-400 font-semibold">
                          {featuredPost.category.name}
                        </span>
                      )}
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {featuredPost.reading_time || 5} دقیقه مطالعه
                      </span>
                    </div>
                    <Link href={postLink(featuredPost)}>
                      <h2 className="text-2xl lg:text-3xl font-black leading-snug mb-4 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                        {featuredPost.title}
                      </h2>
                    </Link>
                    <p className="text-muted-foreground text-sm leading-relaxed line-clamp-3 mb-6">
                      {featuredPost.excerpt}
                    </p>
                  </div>

                  <div className="pt-6 border-t border-border flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <User className="w-4 h-4 text-emerald-600" />
                      <span>{featuredPost.author_name || "تیم تحریریه"}</span>
                    </div>
                    <Link href={postLink(featuredPost)}>
                      <Button variant="ghost" size="sm" className="gap-2 text-emerald-600 hover:text-emerald-700">
                        ادامه مطلب
                        <ArrowLeft className="w-4 h-4" />
                      </Button>
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Blog body + the configured `sidebar` widget area.
              The area was editable in /admin/widgets but mounted nowhere, so
              anything an operator put there was invisible. The grid collapses
              to a single column when the area is empty, so an unconfigured
              install looks exactly as it did. */}
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            <div className="lg:col-span-3">
          {/* Grid of Regular Posts */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {(page === 1 && !searchQuery && selectedCategory === "all"
              ? regularPosts
              : posts
            ).map((post) => (
              <Card
                key={post.id}
                className="group overflow-hidden rounded-2xl border-border bg-card transition-all duration-300 hover:shadow-xl hover:-translate-y-1 flex flex-col justify-between"
              >
                <div>
                  <div className="relative w-full h-48 overflow-hidden">
                    <RemoteImage
                      src={post.cover_image_url}
                      alt={post.title}
                      sizes="(max-width: 768px) 100vw, 33vw"
                      className="object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    <div className="absolute top-3 right-3 flex items-center gap-1.5 flex-wrap">
                      {post.is_featured && (
                        <Badge className="bg-amber-500 hover:bg-amber-600 text-white text-[10px] px-2 py-0.5 shadow-sm font-bold gap-1">
                          <Sparkles className="w-3 h-3" /> ویژه
                        </Badge>
                      )}
                      {post.category && (
                        <Badge variant="secondary" className="bg-background/80 backdrop-blur-md text-xs font-semibold">
                          {post.category.name}
                        </Badge>
                      )}
                    </div>
                    {post.post_format && post.post_format !== "standard" && (
                      <div className="absolute bottom-3 left-3">
                        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white backdrop-blur-sm">
                          {post.post_format === "gallery" && <Images className="w-3.5 h-3.5" />}
                          {post.post_format === "video" && <Video className="w-3.5 h-3.5" />}
                        </span>
                      </div>
                    )}
                  </div>
                  <CardContent className="p-6">
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mb-3">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" />
                        {post.reading_time || 5} دقیقه
                      </span>
                      <span>•</span>
                      <span className="flex items-center gap-1">
                        <Eye className="w-3.5 h-3.5" />
                        {post.view_count} بازدید
                      </span>
                    </div>
                    <Link href={postLink(post)}>
                      <h3 className="font-bold text-lg leading-snug line-clamp-2 mb-3 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                        {post.title}
                      </h3>
                    </Link>
                    <p className="text-muted-foreground text-sm leading-relaxed line-clamp-3">
                      {post.excerpt}
                    </p>
                  </CardContent>
                </div>

                <div className="px-6 pb-6 pt-2 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
                  <span>{post.author_name || "تیم تحریریه"}</span>
                  <Link
                    href={postLink(post)}
                    className="text-emerald-600 dark:text-emerald-400 font-semibold inline-flex items-center gap-1 hover:underline"
                  >
                    مطالعه مقاله
                    <ArrowLeft className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </Card>
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-8">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="gap-1"
              >
                <ChevronRight className="w-4 h-4" />
                صفحه قبل
              </Button>
              <span className="text-sm text-muted-foreground px-4">
                صفحه {page} از {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="gap-1"
              >
                صفحه بعد
                <ChevronLeft className="w-4 h-4" />
              </Button>
            </div>
          )}
            </div>

            {/* Configured sidebar widgets. Renders nothing when unconfigured. */}
            <aside className="hidden lg:block">
              <WidgetArea area="sidebar" />
            </aside>
          </div>
        </div>
      )}
    </div>
  );
}
