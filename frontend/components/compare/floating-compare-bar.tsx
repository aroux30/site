"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeftRight,
  X,
  Trash2,
  ChevronUp,
  ChevronDown,
  Package,
} from "lucide-react";
import { useCompareStore, MAX_COMPARE_PRODUCTS } from "@/stores/compare-store";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";

export function FloatingCompareBar() {
  const pathname = usePathname();
  const { products, removeProduct, clearCompare } = useCompareStore();
  const [mounted, setMounted] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Do not render before mount, or if no products, or on the compare page itself
  if (!mounted || products.length === 0 || pathname === "/compare") {
    return null;
  }

  return (
    <aside
      aria-label="نوار مقایسه سریع"
      className="fixed bottom-4 left-1/2 -translate-x-1/2 z-40 w-[94%] max-w-2xl transition-all duration-300 ease-in-out"
    >
      <div className="overflow-hidden rounded-2xl border border-primary/30 bg-background/95 backdrop-blur-md shadow-2xl ring-1 ring-black/5 dark:ring-white/10">
        {/* Header Strip */}
        <div className="flex items-center justify-between bg-primary/10 px-4 py-2 border-b border-border/50">
          <div className="flex items-center gap-2">
            <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <ArrowLeftRight className="h-3.5 w-3.5" />
            </div>
            <span className="text-xs sm:text-sm font-bold text-foreground">
              لیست مقایسه کالاها
            </span>
            <Badge variant="secondary" className="text-[10px] font-bold px-1.5 py-0">
              {toPersianDigits(products.length)} از {toPersianDigits(MAX_COMPARE_PRODUCTS)}
            </Badge>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg text-muted-foreground hover:text-foreground"
              onClick={() => setCollapsed(!collapsed)}
              aria-label={collapsed ? "نمایش نوار" : "جمع کردن نوار"}
            >
              {collapsed ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 rounded-lg text-muted-foreground hover:text-destructive"
              onClick={clearCompare}
              aria-label="پاک کردن همه"
              title="پاک کردن همه"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Content (Collapsible) */}
        {!collapsed && (
          <div className="p-3 sm:p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
            {/* Products Thumbnails Preview */}
            <div className="flex items-center gap-2.5 overflow-x-auto w-full sm:w-auto py-1">
              {products.map((product) => (
                <div
                  key={product.id}
                  className="group relative flex-shrink-0 h-12 w-12 rounded-xl border border-border bg-muted/30 p-1 flex items-center justify-center"
                >
                  {product.thumbnail || product.images?.[0]?.url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={product.thumbnail || product.images?.[0]?.url}
                      alt={product.title}
                      className="max-h-full max-w-full object-contain"
                    />
                  ) : (
                    <Package className="h-5 w-5 text-muted-foreground" />
                  )}

                  {/* Remove pill button */}
                  <button
                    type="button"
                    onClick={() => removeProduct(product.id)}
                    className="absolute -top-1.5 -right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-sm opacity-90 hover:opacity-100 transition-opacity"
                    title="حذف"
                    aria-label={`حذف ${product.title}`}
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                </div>
              ))}

              {/* Empty placeholder slots */}
              {Array.from({ length: MAX_COMPARE_PRODUCTS - products.length }).map(
                (_, i) => (
                  <div
                    key={i}
                    className="hidden sm:flex flex-shrink-0 h-12 w-12 rounded-xl border border-dashed border-border/80 items-center justify-center text-[10px] text-muted-foreground/60 select-none"
                  >
                    +{toPersianDigits(i + 1 + products.length)}
                  </div>
                ),
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
              <Link href="/compare" className="w-full sm:w-auto">
                <Button
                  size="sm"
                  className="w-full sm:w-auto rounded-xl gap-2 font-bold shadow-md px-5"
                >
                  <ArrowLeftRight className="h-4 w-4" />
                  <span>مشاهده مقایسه ({toPersianDigits(products.length)})</span>
                </Button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
