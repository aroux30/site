"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Home,
  LayoutGrid,
  ShoppingBag,
  Heart,
  User,
} from "lucide-react";
import { useCartStore } from "@/stores/cart-store";
import { cn, toPersianDigits } from "@/lib/utils";

export function MobileBottomNav() {
  const pathname = usePathname();
  const totalItems = useCartStore((state) => state.totalItems);

  // Hide on admin routes, checkout flow, or product detail page where sticky buy bar takes precedence
  if (
    pathname.startsWith("/admin") ||
    pathname === "/checkout" ||
    (pathname.startsWith("/products/") && pathname !== "/products")
  ) {
    return null;
  }

  const navItems = [
    {
      label: "خانه",
      href: "/",
      icon: Home,
      isActive: pathname === "/",
    },
    {
      label: "محصولات",
      href: "/products",
      icon: LayoutGrid,
      isActive: pathname.startsWith("/products"),
    },
    {
      label: "سبد خرید",
      href: "/cart",
      icon: ShoppingBag,
      isActive: pathname === "/cart",
      badge: totalItems > 0 ? totalItems : null,
    },
    {
      label: "علاقه‌مندی",
      href: "/favorites",
      icon: Heart,
      isActive: pathname === "/favorites" || pathname === "/account/favorites",
    },
    {
      label: "حساب من",
      href: "/account",
      icon: User,
      isActive: pathname.startsWith("/account") || pathname === "/login" || pathname === "/register",
    },
  ];

  return (
    <nav
      aria-label="ناوبری موبایل"
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-background/95 backdrop-blur-lg border-t border-border/80 shadow-[0_-4px_20px_rgba(0,0,0,0.08)] px-2 py-1.5 transition-transform duration-300"
    >
      <div className="grid grid-cols-5 items-center justify-around">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = item.isActive;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex flex-col items-center justify-center py-1 px-1 rounded-xl transition-all duration-200 select-none relative group",
                active
                  ? "text-emerald-600 dark:text-emerald-400 font-bold"
                  : "text-muted-foreground hover:text-foreground font-medium"
              )}
            >
              <div className="relative">
                <Icon
                  className={cn(
                    "w-5 h-5 transition-transform duration-200 group-active:scale-90",
                    active && "stroke-[2.5]"
                  )}
                />
                {item.badge !== null && (
                  <span className="absolute -top-1.5 -right-2.5 min-w-[18px] h-[18px] flex items-center justify-center rounded-full bg-emerald-600 text-white text-[10px] font-black px-1 shadow-sm animate-in zoom-in-50">
                    {toPersianDigits(String(item.badge))}
                  </span>
                )}
              </div>
              <span
                className={cn(
                  "text-[10px] mt-1 tracking-tight truncate max-w-full",
                  active ? "font-bold text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"
                )}
              >
                {item.label}
              </span>
              {active && (
                <span className="absolute bottom-0 w-1 h-1 rounded-full bg-emerald-600 dark:bg-emerald-400" />
              )}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
