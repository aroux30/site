"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface FilterSelectOption {
  value: string;
  label: string;
}

export interface FilterSelectProps {
  id: string;
  label: string;
  value: string;
  options: FilterSelectOption[];
  onChange: (value: string) => void;
  className?: string;
  disabled?: boolean;
}

/**
 * A native `<select>` styled to match the admin design system.
 *
 * The Radix select used elsewhere portals its menu and needs pointer/keyboard
 * choreography that a jsdom suite cannot drive honestly. Filter controls are a
 * place where the platform's own picker is also the better mobile experience,
 * so these views use the native control: it is keyboard- and screen-reader
 * accessible for free, and its value is assertable in tests.
 *
 * The visible `<label>` is bound by `htmlFor`, so the control is reachable and
 * named without relying on placeholder text.
 */
export const FilterSelect = React.forwardRef<HTMLSelectElement, FilterSelectProps>(
  function FilterSelect(
    { id, label, value, options, onChange, className, disabled },
    ref,
  ) {
    return (
      <div className={cn("space-y-1.5", className)}>
        <label
          htmlFor={id}
          className="block text-[11px] font-medium text-muted-foreground"
        >
          {label}
        </label>
        <select
          id={id}
          ref={ref}
          value={value}
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          className={cn(
            "h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-xs text-foreground",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    );
  },
);