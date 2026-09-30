"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, X, AlertTriangle, Loader2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  adminSearchApi,
  type AdminSearchResult,
  type SearchHit,
} from "@/lib/api/admin-search";
import { toPersianDigits } from "@/lib/utils";

/** Debounce for keystrokes: long enough to skip mid-word queries, short
 *  enough that a finished word feels instant. */
const DEBOUNCE_MS = 250;

/** The minimum the backend accepts; matching it here avoids a pointless
 *  request that would just come back with a note. */
const MIN_TERM_LENGTH = 2;

export function AdminGlobalSearch() {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [term, setTerm] = useState("");
  const [result, setResult] = useState<AdminSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);

  // A flattened list in render order — keyboard navigation walks this, so it
  // must match exactly what the eye sees.
  const flatHits: SearchHit[] = result
    ? Object.values(result.groups).flat()
    : [];

  // Debounced search: every keystroke firing a request would put five
  // queries in flight for one word and render whichever answered last.
  useEffect(() => {
    const trimmed = term.trim();
    if (trimmed.length < MIN_TERM_LENGTH) {
      setResult(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    const handle = setTimeout(() => {
      adminSearchApi
        .search({ q: trimmed, per_type_limit: 5 })
        .then((res) => {
          setResult(res);
          setActiveIndex(0);
        })
        .catch(() => setResult(null))
        .finally(() => setLoading(false));
    }, DEBOUNCE_MS);
    return () => clearTimeout(handle);
  }, [term]);

  // Click-outside closes the panel; without it the results overlay stays on
  // screen while the operator works on something else.
  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  // Ctrl/Cmd-K focuses the box, the shortcut operators already have in their
  // fingers from every other tool.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  const go = useCallback(
    (hit: SearchHit | undefined) => {
      if (!hit) return;
      setOpen(false);
      setTerm("");
      setResult(null);
      router.push(hit.url);
    },
    [router],
  );

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
      inputRef.current?.blur();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(flatHits.length - 1, 0)));
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (event.key === "Enter") {
      event.preventDefault();
      go(flatHits[activeIndex]);
    }
  };

  const showPanel = open && term.trim().length >= MIN_TERM_LENGTH;

  return (
    <div ref={containerRef} className="relative w-full max-w-md">
      <div className="relative">
        <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={term}
          onChange={(e) => {
            setTerm(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder="جست‌وجو: شماره سفارش، تلفن، نام، SKU… (Ctrl+K)"
          className="ps-9 pe-9"
          aria-label="جست‌وجوی سراسری"
        />
        {loading && (
          <Loader2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        )}
        {!loading && term && (
          <button
            type="button"
            onClick={() => {
              setTerm("");
              setResult(null);
              inputRef.current?.focus();
            }}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            aria-label="پاک کردن"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {showPanel && (
        <div className="absolute z-50 mt-1 max-h-96 w-full overflow-y-auto rounded-md border border-border bg-card shadow-lg">
          {result?.note && (
            <p className="p-3 text-xs text-muted-foreground">{result.note}</p>
          )}

          {result && result.total === 0 && !result.note && (
            <p className="p-3 text-xs text-muted-foreground">نتیجه‌ای یافت نشد</p>
          )}

          {result &&
            Object.entries(result.errors).map(([entity, error]) => (
              <div
                key={entity}
                className="flex items-start gap-2 border-b border-border p-2 text-[11px] text-amber-600 last:border-0"
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                <span>
                  جست‌وجو در «{entity}» ممکن نشد — نتیجه ناقص است
                  <span className="ms-1 text-muted-foreground">({error})</span>
                </span>
              </div>
            ))}

          {result &&
            Object.entries(result.groups).map(([entity, hits]) => {
              if (hits.length === 0) return null;
              return (
                <div key={entity} className="border-b border-border last:border-0">
                  <p className="bg-muted/40 px-3 py-1 text-[10px] font-medium text-muted-foreground">
                    {hits[0]?.entity_label ?? entity} —{" "}
                    {toPersianDigits(String(hits.length))}
                  </p>
                  {hits.map((hit) => {
                    const index = flatHits.indexOf(hit);
                    return (
                      <button
                        key={`${hit.entity_type}-${hit.entity_id}`}
                        type="button"
                        onMouseEnter={() => setActiveIndex(index)}
                        onClick={() => go(hit)}
                        className={cn(
                          "flex w-full items-center justify-between gap-2 px-3 py-2 text-right text-sm transition-colors",
                          index === activeIndex ? "bg-muted" : "hover:bg-muted/60",
                        )}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate">{hit.title}</span>
                          {hit.subtitle && (
                            <span
                              className="block truncate font-mono text-[10px] text-muted-foreground"
                              dir="ltr"
                            >
                              {hit.subtitle}
                            </span>
                          )}
                        </span>
                        {hit.status && (
                          <Badge variant="outline" className="shrink-0 text-[10px]">
                            {hit.status}
                          </Badge>
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}
