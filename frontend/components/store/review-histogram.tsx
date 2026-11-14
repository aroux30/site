"use client";

import { cn } from "@/lib/utils";
import { StarRating } from "@/components/ui/star-rating";

/* ─────────────────────────────────────────────────────────────────────
 * ReviewHistogram — star distribution bar chart
 *
 * Matches backend RatingDistribution schema: { star_1..star_5 }
 *
 * Usage:
 *   <ReviewHistogram
 *     distribution={{ star_1: 3, star_2: 5, star_3: 12, star_4: 28, star_5: 52 }}
 *     averageRating={4.3}
 *     totalReviews={100}
 *   />
 * ────────────────────────────────────────────────────────────────── */

interface RatingDistribution {
  star_1: number;
  star_2: number;
  star_3: number;
  star_4: number;
  star_5: number;
}

interface ReviewHistogramProps {
  distribution: RatingDistribution;
  averageRating: number;
  totalReviews: number;
  /** Number of verified-purchase reviews */
  verifiedCount?: number;
  /** Called when a star row is clicked (for filtering reviews) */
  onFilterByStar?: (star: number) => void;
  className?: string;
}

export function ReviewHistogram({
  distribution,
  averageRating,
  totalReviews,
  verifiedCount,
  onFilterByStar,
  className,
}: ReviewHistogramProps) {
  const rows = [
    { star: 5, count: Number(distribution.star_5) || 0 },
    { star: 4, count: Number(distribution.star_4) || 0 },
    { star: 3, count: Number(distribution.star_3) || 0 },
    { star: 2, count: Number(distribution.star_2) || 0 },
    { star: 1, count: Number(distribution.star_1) || 0 },
  ];

  const maxCount = Math.max(...rows.map((r) => r.count), 1);

  return (
    <div
      className={cn(
        "rounded-2xl border border-border/60 bg-card p-5",
        className
      )}
    >
      {/* Header: big average + stars */}
      <div className="flex items-center gap-4 mb-5">
        <div className="text-center">
          <div className="text-4xl font-bold tabular-nums text-foreground">
            {(averageRating ?? 0).toFixed(1)}
          </div>
          <div className="text-xs text-muted-foreground mt-0.5">از ۵</div>
        </div>
        <div className="space-y-1">
          <StarRating value={averageRating} size="md" />
          <div className="text-xs text-muted-foreground">
            بر اساس {totalReviews.toLocaleString("fa-IR")} نظر
            {typeof verifiedCount === "number" && verifiedCount > 0 && (
              <span className="text-primary">
                {" "}
                · {verifiedCount.toLocaleString("fa-IR")} خرید تأییدشده
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Bar chart rows */}
      <div className="space-y-2">
        {rows.map(({ star, count }) => {
          const pct = totalReviews > 0 ? (count / totalReviews) * 100 : 0;
          const interactive = !!onFilterByStar && count > 0;
          return (
            <button
              key={star}
              type="button"
              disabled={!interactive}
              onClick={() => interactive && onFilterByStar?.(star)}
              className={cn(
                "flex w-full items-center gap-2 group",
                interactive &&
                  "cursor-pointer hover:bg-muted/50 -mx-2 px-2 py-0.5 rounded-lg transition-colors"
              )}
              aria-label={`${star} ستاره: ${count.toLocaleString("fa-IR")} نظر (${Math.round(pct)}٪)`}
            >
              {/* Star number */}
              <span className="w-4 text-xs font-medium tabular-nums text-muted-foreground text-center shrink-0">
                {star.toLocaleString("fa-IR")}
              </span>
              {/* Star icon */}
              <svg
                className="h-3 w-3 shrink-0 fill-amber-400 text-amber-400"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              {/* Bar */}
              <div className="flex-1 h-2 rounded-full bg-muted/60 overflow-hidden">
                <div
                  className={cn(
                    "h-full rounded-full transition-all duration-500 motion-reduce:transition-none",
                    star >= 4
                      ? "bg-emerald-500"
                      : star === 3
                        ? "bg-amber-400"
                        : "bg-red-400"
                  )}
                  style={{ width: `${((count || 0) / maxCount) * 100}%` }}
                />
              </div>
              {/* Count */}
              <span className="w-8 text-xs tabular-nums text-muted-foreground text-start shrink-0">
                {count.toLocaleString("fa-IR")}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
