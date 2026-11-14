"use client";

import {
  useCallback,
  useEffect,
  useRef,
  type MouseEvent,
  type ReactNode,
  type CSSProperties,
} from "react";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  ClickSpark — burst of particles at the click point                */
/*  CSS-only animation; no framer-motion. Accessible: purely visual.  */
/* ------------------------------------------------------------------ */

const PARTICLE_COUNT = 8;
const ANIMATION_MS = 400;

/** Pre-computed unit-circle directions for 8 particles (45° apart). */
const DIRECTIONS: ReadonlyArray<{ dx: number; dy: number }> = Array.from(
  { length: PARTICLE_COUNT },
  (_, i) => {
    const angle = (Math.PI * 2 * i) / PARTICLE_COUNT;
    return { dx: Math.cos(angle), dy: Math.sin(angle) };
  },
);

export interface ClickSparkProps {
  children: ReactNode;
  className?: string;
  /** Radial travel distance in px (default 24). */
  radius?: number;
}

export function ClickSpark({
  children,
  className,
  radius = 24,
}: ClickSparkProps) {
  const containerRef = useRef<HTMLSpanElement>(null);
  const timeoutsRef = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  const dotsRef = useRef<Set<HTMLSpanElement>>(new Set());

  useEffect(() => {
    const timeouts = timeoutsRef.current;
    const dots = dotsRef.current;
    return () => {
      for (const id of timeouts) {
        clearTimeout(id);
      }
      timeouts.clear();
      for (const dot of dots) {
        dot.remove();
      }
      dots.clear();
    };
  }, []);

  const handleClick = useCallback(
    (e: MouseEvent<HTMLSpanElement>) => {
      if (
        typeof window !== "undefined" &&
        window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches
      ) {
        return;
      }

      const container = containerRef.current;
      if (!container) return;

      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      for (const dir of DIRECTIONS) {
        const dot = document.createElement("span");
        dot.setAttribute("aria-hidden", "true");

        const style: Partial<CSSStyleDeclaration> = {
          position: "absolute",
          left: `${x}px`,
          top: `${y}px`,
          width: "3px",
          height: "3px",
          borderRadius: "50%",
          backgroundColor: "hsl(var(--primary))",
          pointerEvents: "none",
          zIndex: "50",
          transform: "translate(-50%, -50%) scale(1)",
          opacity: "1",
          transition: `transform ${ANIMATION_MS}ms ease-out, opacity ${ANIMATION_MS}ms ease-out`,
        };

        Object.assign(dot.style, style);
        container.appendChild(dot);
        dotsRef.current.add(dot);

        // Force layout so the transition triggers from the initial position.
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        dot.offsetWidth;

        const tx = dir.dx * radius;
        const ty = dir.dy * radius;
        dot.style.transform = `translate(calc(-50% + ${tx}px), calc(-50% + ${ty}px)) scale(0)`;
        dot.style.opacity = "0";

        const timeoutId = setTimeout(() => {
          timeoutsRef.current.delete(timeoutId);
          dotsRef.current.delete(dot);
          dot.remove();
        }, ANIMATION_MS);
        timeoutsRef.current.add(timeoutId);
      }
    },
    [radius],
  );

  return (
    <span
      ref={containerRef}
      onClick={handleClick}
      className={cn("relative inline-flex", className)}
      style={{ WebkitTapHighlightColor: "transparent" } as CSSProperties}
    >
      {children}
    </span>
  );
}
