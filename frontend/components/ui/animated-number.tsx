"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { cn, toPersianDigits } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  AnimatedNumber — smooth counter with IntersectionObserver trigger  */
/*  requestAnimationFrame + easeOutExpo curve.                        */
/* ------------------------------------------------------------------ */

const FA_FORMATTER = new Intl.NumberFormat("fa-IR");

function easeOutExpo(t: number): number {
  return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

export interface AnimatedNumberProps {
  value: number;
  /** Animation duration in ms (default 1000). */
  duration?: number;
  suffix?: string;
  prefix?: string;
  className?: string;
}

export function AnimatedNumber({
  value,
  duration = 1000,
  suffix = "",
  prefix = "",
  className,
}: AnimatedNumberProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const [display, setDisplay] = useState<string>(() =>
    FA_FORMATTER.format(value),
  );
  const prevValue = useRef(0);
  const hasAnimated = useRef(false);
  const rafId = useRef<number | null>(null);

  const animate = useCallback(
    (from: number, to: number) => {
      if (rafId.current != null) cancelAnimationFrame(rafId.current);

      const start = performance.now();

      const step = (now: number) => {
        const elapsed = now - start;
        const progress = Math.min(elapsed / duration, 1);
        const eased = easeOutExpo(progress);
        const current = Math.round(from + (to - from) * eased);

        setDisplay(FA_FORMATTER.format(current));

        if (progress < 1) {
          rafId.current = requestAnimationFrame(step);
        } else {
          rafId.current = null;
          prevValue.current = to;
        }
      };

      rafId.current = requestAnimationFrame(step);
    },
    [duration],
  );

  /* Trigger animation when element enters viewport. */
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting && !hasAnimated.current) {
          hasAnimated.current = true;
          const prefersReducedMotion =
            typeof window !== "undefined" &&
            typeof window.matchMedia === "function" &&
            window.matchMedia("(prefers-reduced-motion: reduce)").matches;
          if (prefersReducedMotion) {
            prevValue.current = value;
            setDisplay(FA_FORMATTER.format(value));
          } else {
            animate(0, value);
          }
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [value, animate]);

  /* Re-animate when value changes (only after first viewport entry). */
  useEffect(() => {
    if (!hasAnimated.current) return;
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) {
      prevValue.current = value;
      setDisplay(FA_FORMATTER.format(value));
    } else {
      animate(prevValue.current, value);
    }
  }, [value, animate]);

  /* Cleanup on unmount. */
  useEffect(() => {
    return () => {
      if (rafId.current != null) cancelAnimationFrame(rafId.current);
    };
  }, []);

  return (
    <span
      ref={ref}
      role="status"
      aria-live="polite"
      className={cn("tabular-nums", className)}
      dir="rtl"
    >
      {prefix ? toPersianDigits(prefix) : null}
      {display}
      {suffix ? toPersianDigits(suffix) : null}
    </span>
  );
}
