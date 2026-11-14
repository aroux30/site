"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  TextLoop — rotating promotional taglines with crossfade           */
/*  CSS animations only; no framer-motion.                            */
/* ------------------------------------------------------------------ */

export interface TextLoopProps {
  texts: string[];
  /** Interval between rotations in ms (default 3000). */
  interval?: number;
  className?: string;
}

export function TextLoop({
  texts,
  interval = 3000,
  className,
}: TextLoopProps) {
  const [index, setIndex] = useState(0);
  const [visible, setVisible] = useState(true);
  const [paused, setPaused] = useState(false);
  const [mounted, setMounted] = useState(false);

  const textsLength = texts?.length ?? 0;

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (textsLength <= 1 || paused) return;

    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    const timer = setInterval(() => {
      setVisible(false);
      timeoutId = setTimeout(() => {
        setIndex((prev) => (prev + 1) % textsLength);
        setVisible(true);
      }, 150);
    }, interval);

    return () => {
      clearInterval(timer);
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [textsLength, interval, paused]);

  if (textsLength === 0) return null;

  const currentText = texts[index % texts.length] ?? "";

  return (
    <div
      className={cn("relative overflow-hidden text-start", className)}
      aria-live={mounted ? "polite" : "off"}
      dir="rtl"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <span
        className={cn(
          "inline-block whitespace-nowrap motion-safe:transition-all motion-safe:duration-150 motion-safe:ease-in-out",
          visible
            ? "motion-safe:translate-y-0 opacity-100"
            : "motion-safe:translate-y-1 opacity-0",
        )}
      >
        {currentText}
      </span>

      {/* Invisible sizer: keeps height stable regardless of text. */}
      <span className="invisible block h-0 overflow-hidden" aria-hidden="true">
        {texts[0] ?? ""}
      </span>
    </div>
  );
}
