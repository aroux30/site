"use client";

import { useRef, type KeyboardEvent } from "react";
import { cn } from "@/lib/utils";
import { Star } from "lucide-react";

/* ─────────────────────────────────────────────────────────────────────
 * StarRating — display + interactive star rating
 *
 * Usage:
 *   <StarRating value={4.3} />                          // display only
 *   <StarRating value={rating} onChange={setRating} />   // interactive
 *   <StarRating value={4.3} size="lg" showValue />       // with number
 * ────────────────────────────────────────────────────────────────── */

interface StarRatingProps {
  /** Current rating value (0–5, supports decimals for display) */
  value: number;
  /** Called with new rating (1–5) when a star is clicked — omit for read-only */
  onChange?: (value: number) => void;
  /** Visual size preset */
  size?: "xs" | "sm" | "md" | "lg";
  /** Show the numeric value next to stars */
  showValue?: boolean;
  /** Show the review count, e.g. "(۲۴ نظر)" */
  reviewCount?: number;
  className?: string;
}

const sizeMap = {
  xs: { star: "h-3 w-3", gap: "gap-0.5", text: "text-[11px]" },
  sm: { star: "h-3.5 w-3.5", gap: "gap-0.5", text: "text-xs" },
  md: { star: "h-4 w-4", gap: "gap-0.5", text: "text-sm" },
  lg: { star: "h-5 w-5", gap: "gap-1", text: "text-base" },
};

export function StarRating({
  value,
  onChange,
  size = "md",
  showValue = false,
  reviewCount,
  className,
}: StarRatingProps) {
  const safeValue =
    typeof value === "number" && !Number.isNaN(value)
      ? Math.min(5, Math.max(0, value))
      : 0;
  const s = sizeMap[size];
  const interactive = !!onChange;
  const starRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const selectedStar = Math.round(safeValue) || 1;

  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>, star: number) => {
    if (!interactive) return;
    let next: number | null = null;
    if (e.key === "ArrowLeft") {
      next = Math.min(5, star + 1);
    } else if (e.key === "ArrowRight") {
      next = Math.max(1, star - 1);
    } else if (e.key === "Home") {
      next = 1;
    } else if (e.key === "End") {
      next = 5;
    }
    if (next !== null) {
      e.preventDefault();
      onChange?.(next);
      starRefs.current[next - 1]?.focus();
    }
  };

  return (
    <div
      className={cn("inline-flex items-center", s.gap, className)}
      role={interactive ? "radiogroup" : "img"}
      aria-label={`امتیاز ${safeValue.toFixed(1)} از ۵`}
    >
      {[1, 2, 3, 4, 5].map((star) => {
        const fill = Math.min(1, Math.max(0, safeValue - (star - 1)));
        return (
          <button
            key={star}
            ref={(el) => {
              starRefs.current[star - 1] = el;
            }}
            type="button"
            disabled={!interactive}
            onClick={() => onChange?.(star)}
            onKeyDown={(e) => handleKeyDown(e, star)}
            className={cn(
              "relative shrink-0 text-muted-foreground/30",
              interactive &&
                "cursor-pointer transition-transform motion-safe:hover:scale-110 focus:outline-none focus:ring-1 focus:ring-primary/40 rounded-sm disabled:cursor-default"
            )}
            role={interactive ? "radio" : undefined}
            aria-checked={interactive ? star <= Math.round(safeValue) : undefined}
            aria-label={interactive ? `${star} ستاره` : undefined}
            tabIndex={interactive ? (star === selectedStar ? 0 : -1) : -1}
          >
            {/* Background (empty) star */}
            <Star className={cn(s.star)} strokeWidth={1.5} />
            {/* Filled overlay — clipped to the fractional width */}
            {fill > 0 && (
              <span
                className="absolute inset-0 overflow-hidden text-amber-400"
                style={{ width: `${fill * 100}%`, direction: "ltr" }}
              >
                <Star
                  className={cn(s.star, "fill-current")}
                  strokeWidth={1.5}
                />
              </span>
            )}
          </button>
        );
      })}

      {showValue && (
        <span
          className={cn(
            "font-bold tabular-nums text-foreground",
            s.text
          )}
        >
          {safeValue.toFixed(1)}
        </span>
      )}

      {typeof reviewCount === "number" && (
        <span className={cn("text-muted-foreground", s.text)}>
          ({reviewCount.toLocaleString("fa-IR")} نظر)
        </span>
      )}
    </div>
  );
}
