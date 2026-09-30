"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Canonical selectable card row (Phase 3 — Design System completion).
 *
 * Replaces the hand-rolled label+radio card rows (address picker, shipping
 * methods, payment methods, delivery slots in checkout) with one accessible
 * pattern: a native radio input for keyboard/screen-reader semantics, an
 * accent-colored control, and a visible focus ring on the card itself.
 */
export function RadioCard({
  name,
  value,
  checked,
  onChange,
  children,
  disabled = false,
  className,
}: {
  name: string;
  value: string;
  checked: boolean;
  onChange: () => void;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <label
      className={cn(
        "flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-all",
        checked
          ? "border-primary bg-primary/5 ring-1 ring-primary"
          : "border-border hover:border-border/80 hover:bg-muted/30",
        disabled && "pointer-events-none opacity-60",
        className
      )}
    >
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="mt-1 h-4 w-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      />
      {children}
    </label>
  );
}
