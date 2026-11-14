"use client";

import { Heart } from "lucide-react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  PulseHeart — animated wishlist toggle                             */
/*  CSS transition only; no framer-motion.                            */
/* ------------------------------------------------------------------ */

const SIZE_MAP = {
  sm: 16,
  md: 20,
  lg: 28,
} as const;

export interface PulseHeartProps {
  active: boolean;
  onToggle?: () => void;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function PulseHeart({
  active,
  onToggle,
  size = "md",
  className,
}: PulseHeartProps) {
  const px = SIZE_MAP[size];

  const content = (
    <Heart
      size={px}
      className={cn(
        "transition-colors duration-200",
        active
          ? "fill-red-500 text-red-500"
          : "fill-none text-muted-foreground",
      )}
    />
  );

  const sharedClasses = cn(
    "inline-flex items-center justify-center rounded-full p-1.5",
    "transition-transform duration-300 ease-out",
    onToggle && "hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background cursor-pointer",
    active && "scale-bounce pulse-heart-active",
    className,
  );

  if (onToggle) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label={
          active ? "حذف از علاقه‌مندی‌ها" : "افزودن به علاقه‌مندی‌ها"
        }
        aria-pressed={active}
        className={sharedClasses}
      >
        {content}
      </button>
    );
  }

  return (
    <span className={sharedClasses} aria-hidden="true">
      {content}
    </span>
  );
}
