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
  dir?: "rtl" | "ltr" | "auto";
}

/**
 * AnimatedNumber — Smooth easing number counter using requestAnimationFrame & IntersectionObserver.
 * Completely lightweight, respects prefers-reduced-motion, supports dynamic value transitions,
 * and formats Persian numerals natively in RTL reading direction.
 */
export function AnimatedNumber({
  value,
  duration = 1200,
  className,
  prefix = "",
  suffix = "",
  formatPersian = true,
  dir,
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);
  const ref = useRef<HTMLSpanElement>(null);
  const prevValueRef = useRef(value);
  const inViewRef = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
    ) {
      setDisplayValue(value);
      prevValueRef.current = value;
      return;
    }

    const animateTransition = (fromVal: number, toVal: number) => {
      let startTime: number | null = null;
      const step = (timestamp: number) => {
        if (!startTime) startTime = timestamp;
        const progress = Math.min((timestamp - startTime) / duration, 1);
        const easeOutProgress = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(fromVal + (toVal - fromVal) * easeOutProgress);
        setDisplayValue(current);

        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          setDisplayValue(toVal);
          prevValueRef.current = toVal;
        }
      };
      requestAnimationFrame(step);
    };

    if (inViewRef.current) {
      if (prevValueRef.current !== value) {
        animateTransition(prevValueRef.current, value);
      }
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          inViewRef.current = true;
          animateTransition(0, value);
          observer.disconnect();
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
  const resolvedDir = dir ?? (formatPersian ? "rtl" : "ltr");

  return (
    <span
      ref={ref}
      className={cn("inline-block tabular-nums font-mono font-bold", className)}
      dir={resolvedDir}
    >
      {prefix}
      {finalStr}
      {suffix}
    </span>
  );
}
