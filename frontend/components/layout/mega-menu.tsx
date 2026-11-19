"use client";

import { useState, useRef, useEffect, useMemo, useId } from "react";
import Link from "next/link";
import { RemoteImage } from "@/components/shared/remote-image";
import { cn, toPersianDigits } from "@/lib/utils";
import { ChevronLeft, LayoutGrid } from "lucide-react";
import type { ApiCategory } from "@/lib/api/services";

/* ─────────────────────────────────────────────────────────────────────
 * MegaMenu — multi-column category navigation dropdown
 *
 * Designed to be placed inside the header nav bar. Shows a grid of
 * top-level categories; hovering a category reveals its children
 * in a flyout panel.
 *
 * Usage:
 *   <MegaMenu categories={categories} />
 *
 * The component is RTL-native (uses start/end, not left/right).
 * ────────────────────────────────────────────────────────────────── */

interface MegaMenuProps {
  categories: ApiCategory[];
  className?: string;
  triggerClassName?: string;
  icon?: React.ReactNode;
  label?: string;
}

export function MegaMenu({
  categories,
  className,
  triggerClassName,
  icon,
  label = "دسته‌بندی کالاها",
}: MegaMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [focusSection, setFocusSection] = useState<"top" | "sub">("top");
  const [focusedIndex, setFocusedIndex] = useState<number>(0);
  const [subFocusedIndex, setSubFocusedIndex] = useState<number>(0);

  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const topLevelRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const subCategoryRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const panelId = useId();

  // Clear timeout on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  // Build parent→children map (memoized)
  // Note: Only 2 levels are currently supported (topLevel -> direct children).
  // Deeper descendants (depth >= 2) under children are not rendered in this flyout.
  const { topLevel, childrenMap } = useMemo(() => {
    const top = categories.filter(
      (c) => !c.parent_id && c.is_active !== false
    );
    const map = new Map<string, ApiCategory[]>();
    for (const cat of categories) {
      if (cat.parent_id && cat.is_active !== false) {
        const siblings = map.get(cat.parent_id) || [];
        siblings.push(cat);
        map.set(cat.parent_id, siblings);
      }
    }
    return { topLevel: top, childrenMap: map };
  }, [categories]);

  // Pre-seed activeCategory to first top-level item if unset
  const effectiveActive = activeCategory ?? topLevel[0]?.id ?? null;

  const activeChildren = effectiveActive
    ? childrenMap.get(effectiveActive) || []
    : [];
  const activeCat = effectiveActive
    ? topLevel.find((c) => c.id === effectiveActive)
    : null;

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
        setActiveCategory(null);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape & return focus to trigger
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setActiveCategory(null);
        triggerRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  // Sync keyboard focus to DOM elements
  useEffect(() => {
    if (!open) return;
    if (focusSection === "top") {
      topLevelRefs.current[focusedIndex]?.focus();
    } else {
      subCategoryRefs.current[subFocusedIndex]?.focus();
    }
  }, [open, focusSection, focusedIndex, subFocusedIndex]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        setOpen(true);
        setFocusSection("top");
        setFocusedIndex(0);
      }
      return;
    }

    if (focusSection === "top") {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = (focusedIndex + 1) % topLevel.length;
        setFocusedIndex(next);
        if (topLevel[next]) setActiveCategory(topLevel[next].id);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = (focusedIndex - 1 + topLevel.length) % topLevel.length;
        setFocusedIndex(prev);
        if (topLevel[prev]) setActiveCategory(topLevel[prev].id);
      } else if (e.key === "ArrowLeft") {
        // In RTL, ArrowLeft moves into the children / subcategory flyout (on the left)
        if (activeChildren.length > 0) {
          e.preventDefault();
          setFocusSection("sub");
          setSubFocusedIndex(0);
        }
      }
    } else if (focusSection === "sub") {
      if (e.key === "ArrowRight") {
        // In RTL, ArrowRight moves back to top-level category list (on the right)
        e.preventDefault();
        setFocusSection("top");
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        setSubFocusedIndex((prev) => (prev + 1) % activeChildren.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSubFocusedIndex(
          (prev) => (prev - 1 + activeChildren.length) % activeChildren.length
        );
      }
    }
  };

  const handleMouseEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setOpen(true);
  };

  const handleMouseLeave = () => {
    timeoutRef.current = setTimeout(() => {
      setOpen(false);
      setActiveCategory(null);
    }, 200);
  };

  if (topLevel.length === 0) return null;

  return (
    <div
      ref={menuRef}
      className={cn("relative", className)}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Trigger */}
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(!open)}
        onKeyDown={handleKeyDown}
        className={cn(
          "flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold transition-colors motion-reduce:transition-none",
          open
            ? "bg-primary text-primary-foreground"
            : "bg-muted/60 text-foreground hover:bg-muted",
          triggerClassName
        )}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-label="باز کردن منوی دسته‌بندی کالاها"
        aria-controls={open ? panelId : undefined}
      >
        {icon ?? <LayoutGrid className="h-4 w-4" />}
        <span>{label}</span>
      </button>

      {/* Dropdown panel */}
      {open && (
        <div
          id={panelId}
          className="absolute top-full start-0 z-50 mt-1 flex rounded-2xl border border-border/60 bg-card shadow-2xl overflow-hidden max-w-[calc(100vw-2rem)]"
          role="menu"
          aria-label="منوی دسته‌بندی کالاها"
          onKeyDown={handleKeyDown}
        >
          {/* Category list (right side in RTL) */}
          <div className="w-56 shrink-0 border-e border-border/60 bg-muted/20 py-2 max-h-[28rem] overflow-y-auto">
            {topLevel.map((cat, idx) => (
              <Link
                key={cat.id}
                ref={(el) => {
                  topLevelRefs.current[idx] = el;
                }}
                href={`/category/${cat.slug}`}
                onMouseEnter={() => {
                  setActiveCategory(cat.id);
                  setFocusedIndex(idx);
                }}
                onClick={() => {
                  setOpen(false);
                  setActiveCategory(null);
                }}
                className={cn(
                  "flex w-full items-center justify-between gap-2 px-4 py-2.5 text-sm transition-colors motion-reduce:transition-none",
                  effectiveActive === cat.id
                    ? "bg-primary/10 text-primary font-bold"
                    : "text-foreground hover:bg-muted/50"
                )}
                role="menuitem"
                tabIndex={open && focusSection === "top" && focusedIndex === idx ? 0 : -1}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  {cat.image_url && (
                    <div className="h-7 w-7 shrink-0 rounded-lg overflow-hidden bg-muted/30">
                      <RemoteImage
                        src={cat.image_url}
                        alt={cat.name}
                        sizes="28px"
                        className="object-cover"
                      />
                    </div>
                  )}
                  <span className="truncate">{cat.name}</span>
                </div>
                {childrenMap.has(cat.id) && (
                  <ChevronLeft className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                )}
              </Link>
            ))}
          </div>

          {/* Subcategory flyout (left side in RTL) */}
          <div className="w-80 p-5 max-h-[28rem] overflow-y-auto">
            {activeCat ? (
              <div>
                {/* Category header */}
                <Link
                  href={`/category/${activeCat.slug}`}
                  onClick={() => {
                    setOpen(false);
                    setActiveCategory(null);
                  }}
                  className="flex items-center gap-2 text-base font-bold text-primary hover:underline underline-offset-4 mb-4"
                >
                  همه‌ی {activeCat.name}
                  <ChevronLeft className="h-4 w-4" />
                </Link>

                {activeChildren.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2">
                    {activeChildren.map((child, idx) => (
                      <Link
                        key={child.id}
                        ref={(el) => {
                          subCategoryRefs.current[idx] = el;
                        }}
                        href={`/category/${child.slug}`}
                        onClick={() => {
                          setOpen(false);
                          setActiveCategory(null);
                        }}
                        className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-foreground hover:bg-muted/50 transition-colors motion-reduce:transition-none"
                        role="menuitem"
                        tabIndex={open && focusSection === "sub" && subFocusedIndex === idx ? 0 : -1}
                      >
                        {child.image_url && (
                          <div className="h-6 w-6 shrink-0 rounded-md overflow-hidden bg-muted/30">
                            <RemoteImage
                              src={child.image_url}
                              alt={child.name}
                              sizes="24px"
                              className="object-cover"
                            />
                          </div>
                        )}
                        <span className="truncate">{child.name}</span>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <div className="py-4 text-center space-y-3">
                    <p className="text-xs text-muted-foreground">
                      مشاهده تمامی محصولات دسته‌بندی «{activeCat.name}»
                    </p>
                    <Link
                      href={`/category/${activeCat.slug}`}
                      onClick={() => {
                        setOpen(false);
                        setActiveCategory(null);
                      }}
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-primary/10 text-primary hover:bg-primary hover:text-primary-foreground text-xs font-bold transition-colors shadow-xs"
                    >
                      <span>ورود به {activeCat.name}</span>
                      <ChevronLeft className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                <p>
                  {toPersianDigits(topLevel.length)} دسته‌بندی — روی هر کدام بروید
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
