"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileText, Newspaper, AlertTriangle, Loader2 } from "lucide-react";

import {
  searchContent,
  contentHref,
  type ContentSearchResult,
} from "@/lib/api/services";

interface Props {
  query: string;
}

/** Blog posts and CMS pages matching the query.
 *
 * `/search` only indexes the product catalogue, so searching for a support
 * article or a returns policy returned nothing at all — a reader looking for
 * the site's own content was told it did not exist. This surfaces the
 * content results above the product grid.
 *
 * Hidden entirely when there are no hits, so a product-only search is
 * unchanged.
 */
export default function ContentResults({ query }: Props) {
  const [results, setResults] = useState<ContentSearchResult[]>([]);
  const [total, setTotal] = useState(0);
  const [degraded, setDegraded] = useState(false);
  const [didYouMean, setDidYouMean] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const normalized = query.trim();

  useEffect(() => {
    if (normalized.length < 2) {
      setResults([]);
      setTotal(0);
      return;
    }
    let cancelled = false;
    setLoading(true);
    searchContent({ q: normalized, size: 6 })
      .then((res) => {
        if (cancelled) return;
        setResults(res.results ?? []);
        setTotal(res.total ?? 0);
        setDegraded(res.degraded === true);
        setDidYouMean(res.did_you_mean ?? null);
      })
      .catch(() => {
        // Content search is additive: if it fails, the product results below
        // are still worth showing, so this stays silent.
        if (!cancelled) setResults([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [normalized]);

  if (normalized.length < 2) return null;
  if (!loading && results.length === 0) return null;

  return (
    <section className="mb-8 rounded-2xl border border-border bg-card p-5" dir="rtl">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-base font-bold text-foreground">
          <Newspaper className="h-4 w-4" />
          مطالب و صفحات
          {total > 0 && <span className="text-xs font-normal text-muted-foreground">({total})</span>}
        </h2>
        {loading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
      </div>

      {degraded && (
        <p className="mb-3 flex items-center gap-1.5 rounded-lg bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
          <AlertTriangle className="h-3.5 w-3.5" />
          جستجوی پیشرفته در دسترس نیست؛ نتایج بر اساس تطبیق سادهٔ متن است.
        </p>
      )}

      {didYouMean && (
        <p className="mb-3 text-xs text-muted-foreground">
          آیا منظورتان{" "}
          <Link
            href={`/search?q=${encodeURIComponent(didYouMean)}`}
            className="text-primary underline"
          >
            {didYouMean}
          </Link>{" "}
          بود؟
        </p>
      )}

      <ul className="flex flex-col gap-3">
        {results.map((hit) => (
          <li key={`${hit.type}-${hit.id}`}>
            <Link
              href={contentHref(hit)}
              className="flex items-start gap-2.5 rounded-xl border border-border/60 p-3 transition-colors hover:border-primary/50 hover:bg-muted/40"
            >
              <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="min-w-0">
                <span className="block text-sm font-medium text-foreground">{hit.title}</span>
                {hit.excerpt && (
                  <span className="mt-1 line-clamp-2 block text-xs leading-relaxed text-muted-foreground">
                    {hit.excerpt}
                  </span>
                )}
                <span className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <span>{hit.type === "page" ? "صفحه" : "مقاله"}</span>
                  {hit.category && <span>· {hit.category}</span>}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
