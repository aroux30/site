"use client";

import { useEffect, useRef } from "react";
import { useInView, useMotionValue, useSpring } from "framer-motion";
import { cn, toPersianDigits } from "@/lib/utils";

interface NumberTickerProps {
  value: number;
  direction?: "up" | "down";
  className?: string;
  delay?: number; // seconds
  decimalPlaces?: number;
  persianDigits?: boolean;
}

export function NumberTicker({
  value,
  direction = "up",
  delay = 0,
  className,
  decimalPlaces = 0,
  persianDigits = true,
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionValue = useMotionValue(direction === "down" ? value : 0);
  const springValue = useSpring(motionValue, {
    damping: 60,
    stiffness: 100,
  });
  const isInView = useInView(ref, { once: true, margin: "0px" });

  useEffect(() => {
    if (isInView) {
      setTimeout(() => {
        motionValue.set(direction === "down" ? 0 : value);
      }, delay * 1000);
    }
  }, [motionValue, isInView, delay, value, direction]);

  useEffect(
    () =>
      springValue.on("change", (latest) => {
        if (ref.current) {
          const formattedNumber = Intl.NumberFormat("en-US", {
            minimumFractionDigits: decimalPlaces,
            maximumFractionDigits: decimalPlaces,
          }).format(Number(latest.toFixed(decimalPlaces)));

          ref.current.textContent = persianDigits
            ? toPersianDigits(formattedNumber)
            : formattedNumber;
        }
      }),
    [springValue, decimalPlaces, persianDigits]
  );

  return (
    <span
      className={cn(
        "inline-block tabular-nums text-foreground tracking-wider",
        className
      )}
      ref={ref}
    >
      {persianDigits ? toPersianDigits(0) : "0"}
    </span>
  );
}
