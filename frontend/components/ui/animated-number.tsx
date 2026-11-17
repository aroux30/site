"use client";

import { useEffect, useRef, useState } from "react";
import { cn, toPersianDigits } from "@/lib/utils";

export interface AnimatedNumberProps {
  value: number;
  duration?: number; // duration in ms (default 1200)
  className?: string;
  prefix?: string;
  suffix?: string;
  formatPersian?: boolean;
}

/**
 * AnimatedNumber — Smooth easing number counter using requestAnimationFrame & IntersectionObserver.
 * Completely lightweight, respects prefers-reduced-motion, and formats Persian numerals natively.
 */
export function AnimatedNumber({
  value,
  duration = 1200,
  className,
  prefix = "",
  suffix = "",
  formatPersian = true,
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const animatedRef = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ) {
      setDisplayValue(value);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting && !animatedRef.current) {
          animatedRef.current = true;
          let startTime: number | null = null;
          const startValue = 0;
          const endValue = value;

          const step = (timestamp: number) => {
            if (!startTime) startTime = timestamp;
            const progress = Math.min((timestamp - startTime) / duration, 1);
            // Ease-out cubic formula
            const easeOutProgress = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(startValue + (endValue - startValue) * easeOutProgress);
            setDisplayValue(current);

            if (progress < 1) {
              requestAnimationFrame(step);
            } else {
              setDisplayValue(endValue);
            }
          };

          requestAnimationFrame(step);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [value, duration]);

  const formattedStr = displayValue.toLocaleString("en-US");
  const finalStr = formatPersian ? toPersianDigits(formattedStr) : formattedStr;

  return (
    <span
      ref={ref}
      className={cn("inline-block tabular-nums font-mono font-bold", className)}
      dir="ltr"
    >
      {prefix}
      {finalStr}
      {suffix}
    </span>
  );
}
