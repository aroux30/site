"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
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
  LogOut,
  Package,
  Layers,
  ArrowLeft,
  Loader2,
  Gift,
  Sparkles,
  ArrowLeftRight,
} from "lucide-react";
import { cn, toPersianDigits } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAuth } from "@/hooks/use-auth";
import { useCart } from "@/hooks/use-cart";
import { useCompareStore } from "@/stores/compare-store";
import { CartDrawer } from "@/components/cart/cart-drawer";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import {
  fetchCategories,
  fetchSearchSuggestions,
  type ApiCategory,
  type SearchSuggestionItem,
} from "@/lib/api/services";

const navigationLinks = [
  { href: "/", label: "صفحه اصلی" },
  { href: "/products", label: "محصولات" },
  { href: "/compare", label: "مقایسه کالاها" },
  { href: "/products?sort_by=price&sort_order=desc", label: "پرفروش‌ترین‌ها" },
  { href: "/blog", label: "مجله و بلاگ" },
  { href: "/about", label: "درباره ما" },
  { href: "/contact", label: "تماس با ما" },
];

const fallbackCategories: ApiCategory[] = [
  { id: "cat-electronics", name: "الکترونیک و دیجیتال", slug: "electronics", is_active: true },
  { id: "cat-phones", name: "موبایل و تبلت", slug: "phones", is_active: true },
  { id: "cat-laptops", name: "لپ‌تاپ و کامپیوتر", slug: "laptops", is_active: true },
  { id: "cat-clothing", name: "مد و پوشاک", slug: "clothing", is_active: true },
  { id: "cat-home", name: "خانه و آشپزخانه", slug: "home", is_active: true },
  { id: "cat-beauty", name: "زیبایی و سلامت", slug: "beauty", is_active: true },
  { id: "cat-sports", name: "ورزش و سفر", slug: "sports", is_active: true },
  { id: "cat-books", name: "کتاب و لوازم‌التحریر", slug: "books", is_active: true },
];

export function Header() {
  const router = useRouter();
  const { user, isAuthenticated, logout } = useAuth();
  const { totalItems } = useCart();
  const { products: compareProducts } = useCompareStore();
  const compareCount = compareProducts.length;

  const [mounted, setMounted] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [categoriesOpen, setCategoriesOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [cartDrawerOpen, setCartDrawerOpen] = useState(false);

  // Live search state
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<SearchSuggestionItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const desktopSearchRef = useRef<HTMLDivElement>(null);
  const mobileSearchRef = useRef<HTMLDivElement>(null);

  // Categories state
  const [categories, setCategories] = useState<ApiCategory[]>(fallbackCategories);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Fetch real categories from API
  useEffect(() => {
    let isCancelled = false;
    async function loadCategories() {
      try {
        const response = await fetchCategories({ is_active: true, page_size: 20 });
        if (!isCancelled && response.items && response.items.length > 0) {
          setCategories(response.items);
        }
      } catch {
        // Keep fallback categories silently
      }
    }
    loadCategories();
    return () => {
      isCancelled = true;
    };
  }, []);

  // Debounced live suggestions
  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (!trimmed || trimmed.length < 2) {
      setSuggestions([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    const timer = setTimeout(async () => {
      try {
        const response = await fetchSearchSuggestions(trimmed, 6);
        setSuggestions(response.suggestions || []);
      } catch {
        // Generate contextual suggestions fallback if backend search is offline
        setSuggestions([
          { text: trimmed },
          { text: `${trimmed} اصل` },
          { text: `${trimmed} ارزان` },
        ]);
      } finally {
        setIsSearching(false);
      }
    }, 280);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Handle click outside of search suggestions
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        desktopSearchRef.current &&
        !desktopSearchRef.current.contains(e.target as Node) &&
        mobileSearchRef.current &&
        !mobileSearchRef.current.contains(e.target as Node)
      ) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSearchSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    const query = searchQuery.trim();
    if (!query) return;
    setShowSuggestions(false);
    setSearchOpen(false);
    router.push(`/products?q=${encodeURIComponent(query)}`);
  };

  const handleSuggestionClick = (item: SearchSuggestionItem) => {
    setShowSuggestions(false);
    setSearchOpen(false);
    if (item.product_id) {
      router.push(`/products/${item.product_id}`);
    } else {
      setSearchQuery(item.text);
      router.push(`/products?q=${encodeURIComponent(item.text)}`);
    }
  };

  const handleScroll = useCallback(() => {
    setScrolled(window.scrollY > 10);
  }, []);

  useEffect(() => {
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [handleScroll]);

  // Close mobile menu on resize
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

  // User display helpers
  const userName =
    user?.fullName ||
    (user?.first_name || user?.last_name
      ? `${user?.first_name || ""} ${user?.last_name || ""}`.trim()
      : null) ||
    user?.phone ||
    "کاربر عزیز";

  const userInitial = userName.charAt(0).toUpperCase() || "ک";

  return (
    <header
      className={cn(
        "sticky top-0 z-50 w-full bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80 transition-shadow",
        scrolled && "shadow-md",
      )}
    >
      {/* ===== Top Info Bar ===== */}
      <div className="border-b border-border bg-primary text-primary-foreground">
        <div className="container mx-auto flex items-center justify-between px-4 py-1.5 text-xs">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <Phone className="h-3 w-3" />
              <span dir="ltr" className="font-sans font-bold tabular-nums tracking-normal">
                ۰۲۱-۸۸۸۸۹۹۹۹
              </span>
            </div>
            <div className="hidden items-center gap-1.5 sm:flex">
              <MapPin className="h-3 w-3" />
              <span>ارسال سریع و مطمئن به سراسر ایران</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden sm:inline font-medium">
              ارسال رایگان برای سفارش‌های بالای ۵۰۰,۰۰۰ تومان
            </span>
            <Link
              href="/rewards"
              className="flex items-center gap-1.5 font-bold text-xs text-amber-950 bg-amber-300 hover:bg-amber-200 px-3 py-0.5 rounded-full shadow-xs transition-colors"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-900 animate-pulse" />
              <span>گردونه شانس و جوایز</span>
            </Link>
          </div>
        </div>
      </div>

      {/* ===== Main Navigation Header ===== */}
      <div className="border-b border-border">
        <div className="container mx-auto px-4">
          <div className="flex h-16 items-center justify-between gap-4 md:h-20">
            {/* Right Side: Logo (RTL) */}
            <Link href="/" className="flex shrink-0 items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-primary/80 text-xl font-black text-primary-foreground shadow-sm">
                ف
              </div>
              <div className="hidden flex-col sm:flex">
                <span className="text-lg font-bold leading-tight text-foreground">
                  فروشگاه آنلاین
                </span>
                <span className="text-[11px] text-muted-foreground">
                  ضمانت اصالت و بهترین قیمت
                </span>
              </div>
            </Link>

            {/* Center: Live Search Bar (Desktop) */}
            <div
              ref={desktopSearchRef}
              className="relative hidden flex-1 items-center justify-center px-6 lg:flex"
            >
              <form
                onSubmit={handleSearchSubmit}
                className="relative w-full max-w-xl"
              >
                <Search className="absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="جستجوی نام کالا، برند یا دسته بندی..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setShowSuggestions(true);
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  className="h-11 w-full rounded-xl border-2 border-border bg-muted/40 pr-10 pl-10 text-sm transition-colors focus:border-primary focus:bg-background"
                />
                {isSearching && (
                  <Loader2 className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
                )}
              </form>

              {/* Suggestions Dropdown */}
              {showSuggestions && searchQuery.trim().length >= 2 && (
                <div className="absolute top-full mt-2 w-full max-w-xl rounded-xl border border-border bg-card p-2 shadow-2xl z-50 animate-in fade-in-0 zoom-in-95">
                  <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground">
                    پیشنهادات جستجو
                  </div>
                  <ul className="space-y-1">
                    {suggestions.length > 0 ? (
                      suggestions.map((item, idx) => (
                        <li key={idx}>
                          <button
                            type="button"
                            onClick={() => handleSuggestionClick(item)}
                            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-start text-sm hover:bg-muted/70 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              {item.image_url ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                  src={item.image_url}
                                  alt=""
                                  className="h-7 w-7 rounded object-cover"
                                />
                              ) : (
                                <Package className="h-4 w-4 text-muted-foreground" />
                              )}
                              <span className="text-foreground">{item.text}</span>
                            </div>
                            <ArrowLeft className="h-3.5 w-3.5 text-muted-foreground" />
                          </button>
                        </li>
                      ))
                    ) : (
                      <li className="px-3 py-2 text-xs text-muted-foreground">
                        موردی یافت نشد. برای جستجوی دقیق کلید Enter را بزنید.
                      </li>
                    )}
                  </ul>
                  <div className="mt-2 border-t border-border pt-1.5">
                    <button
                      type="button"
                      onClick={() => handleSearchSubmit()}
                      className="flex w-full items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium text-primary hover:bg-primary/10 transition-colors"
                    >
                      <span>مشاهده همه نتایج برای «{searchQuery}»</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Left Side: Actions (RTL) */}
            <div className="flex items-center gap-2">
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

              {/* Compare */}
              <Link href="/compare" className="inline-flex">
                <Button
                  variant="ghost"
                  size="icon"
                  className="group relative"
                  aria-label="مقایسه کالاها"
                >
                  <ArrowLeftRight className="h-5 w-5 transition-colors group-hover:text-primary" />
                  {mounted && compareCount > 0 && (
                    <Badge className="absolute -left-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] font-bold text-primary-foreground shadow-sm">
                      {toPersianDigits(compareCount)}
                    </Badge>
                  )}
                  <span className="pointer-events-none absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background opacity-0 shadow-lg transition-opacity group-hover:opacity-100 z-50">
                    مقایسه کالاها
                  </span>
                </Button>
              </Link>

              {/* Wishlist */}
              <Link href="/account/favorites" className="hidden sm:inline-flex">
                <Button
                  variant="ghost"
                  size="icon"
                  className="group relative"
                  aria-label="علاقه‌مندی‌ها"
                >
                  <Heart className="h-5 w-5 transition-colors group-hover:text-red-500" />
                  <span className="pointer-events-none absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background opacity-0 shadow-lg transition-opacity group-hover:opacity-100 z-50">
                    علاقه‌مندی‌ها
                  </span>
                </Button>
              </Link>

              {/* Cart Drawer Trigger Button */}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCartDrawerOpen(true)}
                className="group relative"
                aria-label="سبد خرید"
              >
                <ShoppingCart className="h-5 w-5 transition-colors group-hover:text-primary" />
                {mounted && totalItems > 0 && (
                  <Badge className="absolute -left-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1 text-[11px] font-bold text-primary-foreground shadow-sm">
                    {totalItems > 99 ? "۹۹+" : toPersianDigits(totalItems)}
                  </Badge>
                )}
                <span className="pointer-events-none absolute -bottom-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md bg-foreground px-2 py-1 text-[10px] text-background opacity-0 shadow-lg transition-opacity group-hover:opacity-100 z-50">
                  سبد خرید
                </span>
              </Button>

              {/* Dark / Light Mode Switcher */}
              <ThemeToggle />

              {/* User Account or Login Button */}
              {mounted && isAuthenticated && user ? (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      className="flex items-center gap-2 rounded-xl px-2 sm:px-3 hover:bg-muted"
                    >
                      <Avatar className="h-8 w-8 border border-border">
                        <AvatarImage
                          src={user.avatar_url || undefined}
                          alt={userName}
                        />
                        <AvatarFallback className="bg-primary/10 text-primary font-bold text-xs">
                          {userInitial}
                        </AvatarFallback>
                      </Avatar>
                      <span className="hidden text-sm font-medium text-foreground sm:inline-block max-w-[110px] truncate">
                        {userName}
                      </span>
                      <ChevronDown className="h-3.5 w-3.5 text-muted-foreground hidden sm:block" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="start" className="w-56 text-right">
                    <DropdownMenuLabel className="font-normal">
                      <div className="flex flex-col space-y-1">
                        <p className="text-sm font-semibold leading-none">{userName}</p>
                        <p className="text-xs text-muted-foreground font-mono">
                          {user.email || user.phone}
                        </p>
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <Link href="/account" className="w-full flex items-center justify-between cursor-pointer">
                        <span>حساب کاربری</span>
                        <User className="h-4 w-4 text-muted-foreground" />
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/account/orders" className="w-full flex items-center justify-between cursor-pointer">
                        <span>سفارش‌های من</span>
                        <Package className="h-4 w-4 text-muted-foreground" />
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/account/favorites" className="w-full flex items-center justify-between cursor-pointer">
                        <span>علاقه‌مندی‌ها</span>
                        <Heart className="h-4 w-4 text-muted-foreground" />
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link href="/rewards" className="w-full flex items-center justify-between cursor-pointer text-primary font-semibold">
                        <span>گردونه شانس و جوایز</span>
                        <Sparkles className="h-4 w-4 text-primary" />
                      </Link>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      onClick={() => logout()}
                      className="text-red-500 hover:text-red-600 cursor-pointer flex items-center justify-between"
                    >
                      <span>خروج از حساب کاربری</span>
                      <LogOut className="h-4 w-4" />
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              ) : (
                <Link href="/login">
                  <Button
                    variant="outline"
                    size="sm"
                    className="gap-2 rounded-xl border-primary/40 font-medium text-primary hover:bg-primary hover:text-primary-foreground transition-all"
                  >
                    <User className="h-4 w-4" />
                    <span className="hidden sm:inline">ورود / ثبت‌نام</span>
                  </Button>
                </Link>
              )}

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

          {/* Mobile Search Expandable Bar */}
          {searchOpen && (
            <div
              ref={mobileSearchRef}
              className="border-t border-border pb-3 pt-2 lg:hidden relative"
            >
              <form onSubmit={handleSearchSubmit} className="relative">
                <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="search"
                  placeholder="جستجوی کالا، برند..."
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setShowSuggestions(true);
                  }}
                  className="h-10 w-full rounded-lg pr-10 text-sm"
                  autoFocus
                />
              </form>

              {/* Mobile Suggestions */}
              {showSuggestions && searchQuery.trim().length >= 2 && (
                <div className="mt-2 rounded-xl border border-border bg-card p-2 shadow-lg">
                  <ul className="space-y-1">
                    {suggestions.map((item, idx) => (
                      <li key={idx}>
                        <button
                          type="button"
                          onClick={() => handleSuggestionClick(item)}
                          className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-start text-sm hover:bg-muted"
                        >
                          <span className="text-foreground">{item.text}</span>
                          <ArrowLeft className="h-3.5 w-3.5 text-muted-foreground" />
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ===== Desktop Categories & Nav Links Bar ===== */}
      <nav className="hidden border-b border-border bg-background lg:block">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1">
              {/* Real Categories Dropdown */}
              <div
                className="group relative"
                onMouseEnter={() => setCategoriesOpen(true)}
                onMouseLeave={() => setCategoriesOpen(false)}
              >
                <button
                  className={cn(
                    "flex items-center gap-2 rounded-lg px-3.5 py-3 text-sm font-semibold transition-colors",
                    "text-primary hover:bg-primary/5",
                  )}
                  onClick={() => setCategoriesOpen(!categoriesOpen)}
                  aria-expanded={categoriesOpen}
                  aria-haspopup="true"
                >
                  <Layers className="h-4 w-4 text-primary" />
                  <span>دسته‌بندی کالاها</span>
                  <ChevronDown
                    className={cn(
                      "h-3.5 w-3.5 transition-transform duration-200",
                      categoriesOpen && "rotate-180",
                    )}
                  />
                </button>

                {/* Real Categories Dropdown Panel */}
                <div
                  className={cn(
                    "absolute right-0 top-full z-50 w-72 rounded-xl border border-border bg-card p-2 shadow-2xl transition-all duration-200",
                    categoriesOpen
                      ? "visible translate-y-0 opacity-100"
                      : "invisible -translate-y-2 opacity-0",
                  )}
                >
                  <div className="px-3 py-1.5 text-xs font-semibold text-muted-foreground">
                    همه دسته‌بندی‌ها
                  </div>
                  <div className="max-h-[380px] overflow-y-auto space-y-0.5">
                    {categories.map((category) => (
                      <Link
                        key={category.id}
                        href={`/products?category_id=${category.id}&category_slug=${category.slug}`}
                        className="flex items-center justify-between rounded-lg px-3 py-2.5 text-sm text-foreground hover:bg-primary/10 hover:text-primary transition-colors"
                        onClick={() => setCategoriesOpen(false)}
                      >
                        <span>{category.name}</span>
                        <ArrowLeft className="h-3.5 w-3.5 opacity-60" />
                      </Link>
                    ))}
                  </div>
                </div>
              </div>

              {/* Separator */}
              <div className="h-5 w-px bg-border mx-2" />

              {/* Navigation Links */}
              {navigationLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="rounded-lg px-3.5 py-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                >
                  {link.label}
                </Link>
              ))}
            </div>

            {/* Subtle Rewards / Spin Wheel Banner Link */}
            <Link
              href="/rewards"
              className="flex items-center gap-2 rounded-xl bg-gradient-to-l from-amber-500/15 via-primary/10 to-amber-500/5 px-3 py-1.5 text-xs font-bold text-foreground border border-amber-500/30 hover:border-amber-500/60 hover:bg-amber-500/20 transition-all shadow-xs group"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-500 group-hover:scale-110 transition-transform animate-pulse" />
              <span>گردونه شانس و باشگاه جوایز</span>
              <span className="rounded-md bg-amber-500 px-1.5 py-0.5 text-[10px] font-black text-amber-950">
                رایگان
              </span>
            </Link>
          </div>
        </div>
      </nav>

      {/* ===== Mobile Navigation Overlay ===== */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 top-0 z-40 bg-black/50 lg:hidden backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* ===== Mobile Navigation Drawer (RTL: Slide-in from right) ===== */}
      <div
        className={cn(
          "fixed bottom-0 right-0 top-0 z-50 w-[310px] overflow-y-auto bg-background shadow-2xl transition-transform duration-300 ease-out lg:hidden",
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
          {/* User Status in Mobile Menu */}
          <div className="mb-4 rounded-xl border border-border bg-muted/40 p-3">
            {mounted && isAuthenticated && user ? (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-10 w-10 border border-border">
                    <AvatarImage src={user.avatar_url || undefined} alt={userName} />
                    <AvatarFallback className="bg-primary text-primary-foreground font-bold">
                      {userInitial}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-bold text-foreground">{userName}</p>
                    <p className="text-xs text-muted-foreground">{user.phone}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => {
                    logout();
                    setMobileMenuOpen(false);
                  }}
                  title="خروج"
                  className="text-red-500 hover:text-red-600"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            ) : (
              <Link
                href="/login"
                className="flex items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-semibold text-primary-foreground"
                onClick={() => setMobileMenuOpen(false)}
              >
                <User className="h-4 w-4" />
                ورود یا ثبت‌نام
              </Link>
            )}
          </div>

          {/* Mobile Rewards Banner */}
          <Link
            href="/rewards"
            className="mb-4 flex items-center justify-between rounded-xl bg-gradient-to-r from-amber-500/15 via-primary/10 to-amber-500/15 border border-amber-500/30 p-3 text-sm font-bold text-foreground hover:bg-amber-500/25 transition-all"
            onClick={() => setMobileMenuOpen(false)}
          >
            <div className="flex items-center gap-2.5">
              <Gift className="h-5 w-5 text-amber-500" />
              <span>باشگاه جوایز و گردونه شانس</span>
            </div>
            <Badge className="bg-amber-500 text-amber-950 text-[10px] px-2 py-0.5 font-black">
              چرخش رایگان
            </Badge>
          </Link>

          {/* Navigation Links */}
          <div className="mb-4">
            <h3 className="mb-2 px-3 text-xs font-bold text-muted-foreground uppercase tracking-wider">
              منوی اصلی
            </h3>
            <nav>
              <ul className="space-y-1">
                {navigationLinks.map((link) => (
                  <li key={link.href}>
                    <Link
                      href={link.href}
                      className="flex items-center justify-between rounded-lg px-3 py-2 text-sm font-medium text-foreground hover:bg-accent transition-colors"
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <span>{link.label}</span>
                      {link.href === "/compare" && mounted && compareCount > 0 && (
                        <Badge className="h-5 px-1.5 text-[11px] font-bold">
                          {toPersianDigits(compareCount)}
                        </Badge>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>

          {/* Real Categories Links */}
          <div>
            <h3 className="mb-2 px-3 text-xs font-bold text-muted-foreground uppercase tracking-wider">
              دسته‌بندی کالاها
            </h3>
            <ul className="space-y-1 max-h-[300px] overflow-y-auto">
              {categories.map((category) => (
                <li key={category.id}>
                  <Link
                    href={`/products?category_id=${category.id}&category_slug=${category.slug}`}
                    className="flex items-center justify-between rounded-lg px-3 py-2 text-sm text-foreground hover:bg-accent transition-colors"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span>{category.name}</span>
                    <ArrowLeft className="h-3.5 w-3.5 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="border-t border-border px-4 py-4 text-xs text-muted-foreground flex items-center justify-between">
          <span>پشتیبانی تلفنی</span>
          <span dir="ltr" className="font-sans font-bold tabular-nums">
            ۰۲۱-۸۸۸۸۹۹۹۹
          </span>
        </div>
      </div>

      {/* Slide-over Interactive Cart Drawer */}
      <CartDrawer
        isOpen={cartDrawerOpen}
        onClose={() => setCartDrawerOpen(false)}
      />
    </header>
  );
}
