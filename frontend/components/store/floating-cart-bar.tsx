"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ShoppingBag, ArrowLeft, X, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCart } from "@/hooks/use-cart";
import { formatPrice, toPersianDigits } from "@/lib/utils";

export function FloatingCartBar() {
  const pathname = usePathname();
  const { totalItems, subtotal } = useCart();
  const [mounted, setMounted] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isPdp = Boolean(pathname?.startsWith("/products/") && pathname.split("/").filter(Boolean).length >= 2);
  const isExcluded =
    pathname?.startsWith("/checkout") ||
    pathname?.startsWith("/cart") ||
    pathname?.startsWith("/rewards") ||
    pathname?.startsWith("/compare") ||
    pathname?.startsWith("/favorites") ||
    pathname?.startsWith("/faq") ||
    pathname?.startsWith("/contact") ||
    pathname?.startsWith("/about") ||
    pathname?.startsWith("/terms") ||
    isPdp;

  if (!mounted || totalItems <= 0 || dismissed || isExcluded) {
    return null;
  }

  return (
    <aside
      aria-label="سبد خرید شناور"
      className="pointer-events-auto w-full animate-in fade-in slide-in-from-bottom-5 duration-300"
    >
      <div className="flex items-center justify-between gap-3 rounded-2xl border border-emerald-500/30 bg-background/95 p-3 sm:p-4 shadow-2xl backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="relative flex h-10 w-10 sm:h-12 sm:w-12 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <ShoppingBag className="h-5 w-5 sm:h-6 sm:w-6" />
            <span className="absolute -top-1 -start-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 text-[10px] font-bold text-white shadow">
              {toPersianDigits(totalItems)}
            </span>
          </div>
          <div>
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>مبلغ سبد خرید:</span>
            </div>
            <div className="text-sm sm:text-base font-black text-foreground">
              {formatPrice(subtotal)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Link href="/checkout">
            <Button
              size="sm"
              className="h-9 sm:h-10 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs sm:text-sm px-3.5 sm:px-5 gap-1.5 shadow-md"
            >
              <span>تکمیل خرید</span>
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            title="بستن موقت"
            aria-label="بستن نوار سبد شناور"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    </aside>
  );
}
