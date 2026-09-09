"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  BlogPost,
  BlogPostCategory,
  fetchBlogCategories,
  fetchBlogPosts,
} from "@/lib/api/blog";

export default function BlogPage() {
  const [posts, setPosts] = useState<BlogPost[]>([]);
  const [categories, setCategories] = useState<BlogPostCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [page, setPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(1);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    async function loadCategories() {
      const cats = await fetchBlogCategories();
      setCategories(cats);
    }
    loadCategories();
  }, []);

  useEffect(() => {
    async function loadPosts() {
      setIsLoading(true);
      const res = await fetchBlogPosts({
        category: selectedCategory === "all" ? undefined : selectedCategory,
        search: searchQuery || undefined,
        page,
        page_size: 6,
      });
      setPosts(res.items);
      setTotalPages(res.total_pages);
      setIsLoading(false);
    }
    loadPosts();
  }, [selectedCategory, searchQuery, page]);

  const featuredPost = posts[0];
  const regularPosts = posts.slice(1);

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

          {/* Search bar inside hero */}
          <div className="relative max-w-md">
            <Search className="absolute right-4 top-1/2 -translate-y-12 w-5 h-5 text-slate-400" />
            <Input
              type="text"
              placeholder="جستجو در میان صدها مقاله..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setPage(1);
              }}
              className="bg-white/10 border-white/20 text-white placeholder:text-slate-400 pr-12 pl-4 py-6 rounded-2xl focus:bg-white/15 focus:border-emerald-400"
            />
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
          <button
            key={cat.id}
            onClick={() => {
              setSelectedCategory(cat.slug);
              setPage(1);
            }}
            className={`px-5 py-2.5 rounded-full text-sm font-medium transition-all whitespace-nowrap ${
              selectedCategory === cat.slug
                ? "bg-emerald-600 text-white shadow-lg shadow-emerald-600/30"
                : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground"
            }`}
          >
            {cat.name}
          </button>
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
                  <Image
                    src={
                      featuredPost.cover_image_url ||
                      "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=1200"
                    }
                    alt={featuredPost.title}
                    fill
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
                    <Link href={`/blog/${featuredPost.slug}`}>
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
                    <Link href={`/blog/${featuredPost.slug}`}>
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
                    <Image
                      src={
                        post.cover_image_url ||
                        "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800"
                      }
                      alt={post.title}
                      fill
                      className="object-cover transition-transform duration-500 group-hover:scale-105"
                    />
                    {post.category && (
                      <div className="absolute top-3 right-3">
                        <Badge variant="secondary" className="bg-background/80 backdrop-blur-md text-xs font-semibold">
                          {post.category.name}
                        </Badge>
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
                    <Link href={`/blog/${post.slug}`}>
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
                    href={`/blog/${post.slug}`}
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
      )}
    </div>
  );
}
