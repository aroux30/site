"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Search,
  ShoppingCart,
  User,
  Heart,
  Menu,
  X,
  ChevronDown,
  Phone,
  MapPin,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useCartStore } from "@/stores/cart-store";

const navigationLinks = [
  { href: "/", label: "صفحه اصلی" },
  { href: "/products", label: "محصولات" },
  { href: "/products?sale=true", label: "تخفیف‌ها" },
  { href: "/about", label: "درباره ما" },
  { href: "/contact", label: "تماس با ما" },
];

const categoryLinks = [
  { href: "/products?category=electronics", label: "الکترونیک" },
  { href: "/products?category=phones", label: "موبایل و تبلت" },
  { href: "/products?category=laptops", label: "لپ‌تاپ و کامپیوتر" },
  { href: "/products?category=clothing", label: "پوشاک" },
  { href: "/products?category=home", label: "خانه و آشپزخانه" },
  { href: "/products?category=beauty", label: "زیبایی و سلامت" },
  { href: "/products?category=sports", label: "ورزش و سفر" },
  { href: "/products?category=books", label: "کتاب و لوازم‌التحریر" },
];

export function Header() {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [categoriesOpen, setCategoriesOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  const totalItems = useCartStore((state) => state.totalItems);

  const handleScroll = useCallback(() => {
    setScrolled(window.scrollY > 10);
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Close mobile menu on route change / resize
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 1024) {
        setMobileMenuOpen(false);
        setSearchOpen(false);
      }
    };
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (mobileMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileMenuOpen]);

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60",
        scrolled && "shadow-md",
      )}
    >
      {/* ===== Top Bar ===== */}
      <div className="border-b border-border bg-primary text-primary-foreground">
        <div className="container mx-auto flex items-center justify-between px-4 py-1.5">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-xs">
              <Phone className="h-3 w-3" />
              <span dir="ltr" className="tracking-wide">
                ۰۲۱-۱۲۳۴۵۶۷۸
              </span>
            </div>
            <div className="hidden items-center gap-1.5 text-xs sm:flex">
              <MapPin className="h-3 w-3" />
              <span>تهران، خیابان ولیعصر</span>
            </div>
          </div>
          <span className="text-xs font-medium">
            ارسال رایگان برای سفارش‌های بالای ۵۰۰ هزار تومان
          </span>
        </div>
      </div>

      {/* ===== Main Header ===== */}
      <div className="border-b border-border">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between gap-4 md:h-[72px]">
            {/* Right Side: Logo (RTL) */}
            <Link href="/" className="flex shrink-0 items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-lg font-black text-primary-foreground shadow-sm">
                ف
              </div>
              <div className="hidden flex-col sm:flex">
                <span className="text-lg font-bold leading-tight text-foreground">
                  فروشگاه آنلاین
                </span>
                <span className="text-[10px] text-muted-foreground">
                  خرید آسان و مطمئن
                </span>
              </div>
            </Link>

            {/* Center: Search Bar (Desktop) */}
            <div className="hidden flex-1 items-center justify-center px-8 lg:flex">
              <div className="relative w-full max-w-xl">
                <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="جستجوی محصولات..."
                  className="h-11 w-full rounded-xl border-2 border-border bg-muted/40 pr-10 text-sm transition-colors focus:border-primary focus:bg-background"
                />
              </div>
            </div>

            {/* Left Side: Actions (RTL) */}
            <div className="flex items-center gap-1">
              {/* Mobile Search Toggle */}
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setSearchOpen(!searchOpen)}
                aria-label="جستجو"
              >
                <Search className="h-5 w-5" />
              </Button>

              {/* User Account */}
              <Link href="/account">
                <Button
                  variant="ghost"
                  size="icon"
                  className="group relative hidden sm:flex"
                  aria-label="حساب کاربری"
                >
                  <User className="h-5 w-5 transition-colors group-hover:text-primary" />
                  <span className="pointer-events-none absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
                    حساب کاربری
                  </span>
                </Button>
              </Link>

              {/* Wishlist */}
              <Link href="/account/favorites">
                <Button
                  variant="ghost"
                  size="icon"
                  className="group relative hidden sm:flex"
                  aria-label="علاقه‌مندی‌ها"
                >
                  <Heart className="h-5 w-5 transition-colors group-hover:text-red-500" />
                  <span className="pointer-events-none absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
                    علاقه‌مندی‌ها
                  </span>
                </Button>
              </Link>

              {/* Cart */}
              <Link href="/cart">
                <Button
                  variant="ghost"
                  size="icon"
                  className="group relative"
                  aria-label="سبد خرید"
                >
                  <ShoppingCart className="h-5 w-5 transition-colors group-hover:text-primary" />
                  {totalItems > 0 && (
                    <Badge className="absolute -left-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full p-0 text-[10px]">
                      {totalItems > 99 ? "۹۹+" : totalItems}
                    </Badge>
                  )}
                  <span className="pointer-events-none absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background opacity-0 shadow-lg transition-opacity group-hover:opacity-100">
                    سبد خرید
                  </span>
                </Button>
              </Link>

              {/* Mobile Menu Toggle */}
              <Button
                variant="ghost"
                size="icon"
                className="lg:hidden"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                aria-label="منو"
              >
                {mobileMenuOpen ? (
                  <X className="h-5 w-5" />
                ) : (
                  <Menu className="h-5 w-5" />
                )}
              </Button>
            </div>
          </div>

          {/* Mobile Search (expandable) */}
          {searchOpen && (
            <div className="border-t border-border pb-3 pt-2 lg:hidden">
              <div className="relative">
                <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="جستجوی محصولات..."
                  className="h-10 w-full rounded-lg pr-10"
                  autoFocus
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ===== Desktop Navigation Bar ===== */}
      <nav className="hidden border-b border-border bg-background lg:block">
        <div className="container mx-auto px-4">
          <div className="flex items-center gap-1">
            {/* Categories Dropdown */}
            <div
              className="group relative"
              onMouseEnter={() => setCategoriesOpen(true)}
              onMouseLeave={() => setCategoriesOpen(false)}
            >
              <button
                className={cn(
                  "flex items-center gap-1.5 rounded-lg px-3 py-3 text-sm font-semibold transition-colors",
                  "text-primary hover:bg-primary/5",
                )}
                onClick={() => setCategoriesOpen(!categoriesOpen)}
                aria-expanded={categoriesOpen}
                aria-haspopup="true"
              >
                <Menu className="h-4 w-4" />
                <span>دسته‌بندی‌ها</span>
                <ChevronDown
                  className={cn(
                    "h-3 w-3 transition-transform duration-200",
                    categoriesOpen && "rotate-180",
                  )}
                />
              </button>

              {/* Categories Dropdown Panel */}
              <div
                className={cn(
                  "absolute right-0 top-full z-50 min-w-[220px] rounded-xl border border-border bg-card p-2 shadow-xl transition-all duration-200",
                  categoriesOpen
                    ? "visible translate-y-0 opacity-100"
                    : "invisible -translate-y-2 opacity-0",
                )}
              >
                {categoryLinks.map((category) => (
                  <Link
                    key={category.href}
                    href={category.href}
                    className="block rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-primary/5 hover:text-primary"
                    onClick={() => setCategoriesOpen(false)}
                  >
                    {category.label}
                  </Link>
                ))}
              </div>
            </div>

            {/* Separator */}
            <div className="h-5 w-px bg-border" />

            {/* Navigation Links */}
            {navigationLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "rounded-lg px-3 py-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                  link.href === "/products?sale=true" &&
                    "text-red-500 hover:text-red-600",
                )}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>

      {/* ===== Mobile Navigation Overlay ===== */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 top-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* ===== Mobile Navigation Drawer (slide-in from right for RTL) ===== */}
      <div
        className={cn(
          "fixed bottom-0 right-0 top-0 z-50 w-[300px] overflow-y-auto bg-background shadow-2xl transition-transform duration-300 ease-out lg:hidden",
          mobileMenuOpen ? "translate-x-0" : "translate-x-full",
        )}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-border px-4 py-4">
          <Link
            href="/"
            className="flex items-center gap-2"
            onClick={() => setMobileMenuOpen(false)}
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-base font-black text-primary-foreground">
              ف
            </div>
            <span className="text-lg font-bold text-foreground">
              فروشگاه آنلاین
            </span>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileMenuOpen(false)}
            aria-label="بستن منو"
          >
            <X className="h-5 w-5" />
          </Button>
        </div>

        {/* Drawer Content */}
        <div className="px-4 py-4">
          {/* Mobile Account/Wishlist Links */}
          <div className="mb-4 flex items-center gap-2 sm:hidden">
            <Link
              href="/account"
              className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              onClick={() => setMobileMenuOpen(false)}
            >
              <User className="h-4 w-4" />
              حساب من
            </Link>
            <Link
              href="/account/favorites"
              className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              onClick={() => setMobileMenuOpen(false)}
            >
              <Heart className="h-4 w-4" />
              علاقه‌مندی‌ها
            </Link>
          </div>

          {/* Nav Links */}
          <div className="mb-4">
            <h3 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              منو
            </h3>
            <nav>
              <ul className="space-y-0.5">
                {navigationLinks.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className={cn(
                        "block rounded-lg px-3 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-accent",
                        link.href === "/products?sale=true" &&
                          "text-red-500 hover:text-red-600",
                      )}
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>

          {/* Category Links */}
          <div>
            <h3 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              دسته‌بندی‌ها
            </h3>
            <ul className="space-y-0.5">
              {categoryLinks.map((category) => (
                <li key={category.href}>
                  <Link
                    href={category.href}
                    className="block rounded-lg px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    {category.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="border-t border-border px-4 py-4">
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Phone className="h-4 w-4" />
            <span dir="ltr">۰۲۱-۱۲۳۴۵۶۷۸</span>
          </div>
        </div>
      </div>
    </header>
  );
}
