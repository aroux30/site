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
  Users,
} from "lucide-react";
import { cn, toPersianDigits } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { UserAvatar } from "@/components/ui/user-avatar";
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
import { WidgetArea } from "@/components/layout/widget-area";
import { LiveSearchBar } from "@/components/search/live-search-bar";
import {
  fetchCategories,
  fetchSearchSuggestions,
  type ApiCategory,
  type SearchSuggestionItem,
} from "@/lib/api/services";
import { contentApi, singleTypesApi, type MenuItem } from "@/lib/api/content";
import { useSiteBranding } from "@/components/layout/site-branding-provider";

// Fallback nav only until the CMS menu tree (header_main location) loads from
// the API — editors can then change links from the admin panel without a deploy.
const fallbackNavigationLinks = [
  { href: "/", label: "صفحه اصلی" },
  { href: "/products", label: "محصولات" },
  { href: "/compare", label: "مقایسه کالاها" },
  { href: "/products?sort_by=price&sort_order=desc", label: "پرفروش‌ترین‌ها" },
  { href: "/blog", label: "مجله و بلاگ" },
  { href: "/about", label: "درباره ما" },
  { href: "/contact", label: "تماس با ما" },
];

export function Header() {
  const router = useRouter();
  const { siteName } = useSiteBranding();
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
  // Categories come only from the API — fabricated fallbacks would link
  // users to dead category pages on API failure.
  const [categories, setCategories] = useState<ApiCategory[]>([]);
  const [categoriesLoading, setCategoriesLoading] = useState(true);

  // CMS-driven navigation: null until the first fetch resolves, then either the
  // admin-managed menu tree or (on failure) the static fallback links.
  const [cmsMenu, setCmsMenu] = useState<MenuItem[] | null>(null);
  // The drawer has its own menu location. It used to re-render `header_main`,
  // so every item an editor added under the admin's "mobile_nav" location
  // appeared on no page at all — and mobile is the primary viewport here.
  const [mobileMenu, setMobileMenu] = useState<MenuItem[] | null>(null);

  // Single-type configs: announcement bar (homepage_config) and header CTA
  // (header_menu). Both default to off; an unreachable CMS hides them silently.
  const [announcement, setAnnouncement] = useState<{
    enabled: boolean;
    text: string;
    url: string;
  } | null>(null);
  const [headerCta, setHeaderCta] = useState<{
    label: string;
    url: string;
    visible: boolean;
  } | null>(null);

  useEffect(() => {
    setMounted(true);
    let cancelled = false;
    contentApi
      .getMenu("header_main")
      .then((items) => {
        if (!cancelled && items.length > 0) setCmsMenu(items);
      })
      .catch(() => {
        // Fallback links stay in place — an unreachable CMS must not break nav.
      });
    contentApi
      .getMenu("mobile_nav")
      .then((items) => {
        if (!cancelled && items.length > 0) setMobileMenu(items);
      })
      .catch(() => {
        // No mobile_nav menu configured — the drawer keeps the desktop tree.
      });
    singleTypesApi
      .getHomepageConfig()
      .then((res) => {
        if (!cancelled && res.value?.announcement_bar) setAnnouncement(res.value.announcement_bar);
      })
      .catch(() => {});
    singleTypesApi
      .getHeaderMenu()
      .then((res) => {
        if (!cancelled && res.value?.cta_button) setHeaderCta(res.value.cta_button);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const navigationLinks =
    cmsMenu?.map((item) => ({ href: item.url, label: item.title })) ??
    fallbackNavigationLinks;

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
        // Leave the list empty — an honest empty dropdown beats dead links
      } finally {
        if (!isCancelled) setCategoriesLoading(false);
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
    // /search, not /products: only the search page renders ContentResults, so
    // routing here silently dropped blog posts and CMS pages from every
    // header search. The products listing also has no content tab.
    router.push(`/search?q=${encodeURIComponent(query)}`);
  };

  const handleSuggestionClick = (item: SearchSuggestionItem) => {
    setShowSuggestions(false);
    setSearchOpen(false);
    if (item.product_id || item.slug) {
      // Route on the slug, not the id: /products/<uuid> renders 200 through the
      // by-id fallback but its canonical then points at the UUID, so every
      // suggestion click created a second indexable URL for one product.
      router.push(`/products/${item.slug || item.product_id}`);
    } else {
      setSearchQuery(item.text);
      router.push(`/search?q=${encodeURIComponent(item.text)}`);
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
    <>
    {/* Configured widget area (admin /admin/widgets). The `header_top` area was
        always editable in the admin but never mounted anywhere, so anything
        an operator put there was invisible. */}
    <div className="w-full border-b border-border bg-muted/40 px-4 py-3">
      <div className="container mx-auto">
        <WidgetArea area="header_top" />
      </div>
    </div>
    {/* Announcement bar from CMS homepage_config (admin /admin/cms) */}
    {announcement?.enabled && announcement.text ? (
      <div className="w-full bg-emerald-600 px-4 py-2 text-center text-xs font-semibold text-white">
        {announcement.url ? (
          <Link href={announcement.url} className="hover:underline">
            {announcement.text}
          </Link>
        ) : (
          announcement.text
        )}
      </div>
    ) : null}
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
          <div className="flex min-w-0 items-center gap-4">
            {/* `min-w-0` plus hidden text lets this cluster shrink below its
                intrinsic width. At 200% zoom the free-shipping sentence alone
                is wider than the viewport, and without shrink permission it
                pushed the whole bar — and every page with it — into
                horizontal scroll. */}
            <span className="hidden shrink min-w-0 truncate sm:inline sm:max-w-[14rem] font-medium">
              ارسال رایگان برای سفارش‌های بالای ۵۰۰,۰۰۰ تومان
            </span>
            <Link
              href="/rewards"
              className="flex min-w-0 shrink items-center gap-1.5 font-bold text-xs text-amber-950 bg-amber-300 hover:bg-amber-200 px-3 py-0.5 rounded-full shadow-xs transition-colors"
            >
              <Sparkles className="h-3.5 w-3.5 shrink-0 text-amber-900 animate-pulse" />
              <span className="min-w-0 truncate">گردونه شانس و جوایز</span>
            </Link>
          </div>
        </div>
      </div>

      {/* ===== Main Navigation Header ===== */}
      <div className="border-b border-border">
        <div className="container mx-auto px-4">
          {/* `min-w-0` on the row and its action cluster lets the flexible
              children shrink below their content width. Without it the icon
              cluster keeps its intrinsic width, the row exceeds the viewport
              at 320px, and every page gains horizontal scroll. */}
          <div className="flex h-16 min-w-0 items-center justify-between gap-2 md:h-20 md:gap-4">
            {/* Right Side: Logo (RTL) */}
            <Link href="/" className="flex shrink-0 items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-primary to-primary/80 text-xl font-black text-primary-foreground shadow-sm">
                ف
              </div>
              <div className="hidden flex-col sm:flex">
                <span className="text-lg font-bold leading-tight text-foreground">
                  {siteName}
                </span>
                <span className="text-[11px] text-muted-foreground">
                  ضمانت اصالت و بهترین قیمت
                </span>
              </div>
            </Link>

            {/* Center: Live Search Bar (Desktop) */}
            <div className="relative hidden flex-1 items-center justify-center px-6 lg:flex">
              <div className="w-full max-w-xl">
                <LiveSearchBar placeholder="جستجوی نام کالا، برند یا دسته‌بندی..." />
              </div>
            </div>

            {/* Left Side: Actions (RTL) */}
            <div className="flex min-w-0 shrink items-center gap-1 sm:gap-2">
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

              {/* Compare — a secondary action, hidden at the narrowest widths
                  where it would compete with search/cart for a 320px row and
                  push the cluster past the viewport edge. */}
              <Link href="/compare" className="hidden sm:inline-flex">
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
                      <UserAvatar
                        src={user.avatar_url}
                        name={userName}
                        size="md"
                      />
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
                      <Link href="/account/referrals" className="w-full flex items-center justify-between cursor-pointer">
                        <span>دعوت دوستان</span>
                        <Users className="h-4 w-4 text-muted-foreground" />
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
                      onClick={() => void logout()}
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
                // Let the icon button shrink with the cluster instead of
                // holding its nowrap width and pushing the row past the
                // viewport edge at large text sizes.
                className="min-w-0 lg:hidden"
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
            <div className="border-t border-border pb-3 pt-2 lg:hidden relative">
              <LiveSearchBar
                placeholder="جستجوی کالا، برند..."
                autoFocus
                onSearchSubmit={() => setSearchOpen(false)}
              />
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
                    {categoriesLoading ? (
                      <div className="space-y-1.5 px-2 py-1.5">
                        {[...Array(4)].map((_, i) => (
                          <div key={i} className="h-8 animate-pulse rounded-lg bg-muted" />
                        ))}
                      </div>
                    ) : categories.length === 0 ? (
                      <div className="px-3 py-4 text-xs text-muted-foreground">
                        دسته‌بندی‌ای در دسترس نیست
                      </div>
                    ) : (
                      categories.map((category) => (
                      <Link
                        key={category.id}
                        href={`/products?category_id=${category.id}&category_slug=${category.slug}`}
                        className="flex items-center justify-between rounded-lg px-3 py-2.5 text-sm text-foreground hover:bg-primary/10 hover:text-primary transition-colors"
                        onClick={() => setCategoriesOpen(false)}
                      >
                        <span>{category.name}</span>
                        <ArrowLeft className="h-3.5 w-3.5 opacity-60" />
                      </Link>
                    ))
                    )}
                  </div>
                </div>
              </div>

              {/* Separator */}
              <div className="h-5 w-px bg-border mx-2" />

              {/* Navigation Links — CMS parents with children render as dropdowns */}
              {cmsMenu
                ? cmsMenu.map((item) =>
                    item.children && item.children.length > 0 ? (
                      <DropdownMenu key={item.id}>
                        <DropdownMenuTrigger asChild>
                          <button className="flex items-center gap-1 rounded-lg px-3.5 py-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground">
                            {item.title}
                            <ChevronDown className="h-3.5 w-3.5" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="start" className="min-w-44">
                          {item.children.map((child) => (
                            <DropdownMenuItem key={child.id} asChild>
                              <Link href={child.url} prefetch={false}>
                                {child.title}
                              </Link>
                            </DropdownMenuItem>
                          ))}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    ) : (
                      <Link
                        key={item.id}
                        href={item.url}
                        prefetch={false}
                        className="rounded-lg px-3.5 py-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                      >
                        {item.title}
                      </Link>
                    ),
                  )
                : fallbackNavigationLinks.map((link) => (
                    <Link
                      key={link.href}
                      href={link.href}
                      prefetch={false}
                      className="rounded-lg px-3.5 py-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
                    >
                      {link.label}
                    </Link>
                  ))}

              {/* CMS-driven header CTA (header_menu single type) */}
              {headerCta?.visible && headerCta.url ? (
                <Link
                  href={headerCta.url}
                  className="rounded-lg bg-primary px-3.5 py-2 text-sm font-bold text-primary-foreground transition hover:bg-primary/90"
                >
                  {headerCta.label || "مشاهده"}
                </Link>
              ) : null}
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

    </header>

      {/* ===== Fixed overlays live OUTSIDE <header>: backdrop-blur on the sticky
          header becomes the containing block for fixed children and collapses
          them to the header's height instead of the viewport ===== */}

      {/* ===== Mobile Navigation Overlay ===== */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 top-0 z-40 bg-black/50 lg:hidden backdrop-blur-sm"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* ===== Mobile Navigation Drawer =====
          The drawer is anchored to the inline start edge and slides out along
          the inline axis, so it works identically in RTL and LTR. A closed
          drawer must be translated fully off-screen: `translate-x-full` moves
          toward +X, which in RTL is *into* the viewport, so the closed drawer
          stayed visible and added horizontal scroll to every page. */}
      <div
        aria-hidden={!mobileMenuOpen}
        // The closed drawer must be removed from the document's scrollable
        // area, not merely visually translated. In an RTL document a transform
        // does not shrink `scrollWidth`, so a drawer parked off-screen still
        // extends the page's scrollable width and produces horizontal scroll on
        // every route. `hidden` when closed is the only version that is
        // correct regardless of writing direction.
        className={cn(
          "fixed bottom-0 right-0 top-0 z-50 w-[310px] overflow-y-auto bg-background shadow-2xl transition-transform duration-300 ease-out lg:hidden",
          mobileMenuOpen ? "block translate-x-0" : "hidden",
        )}
        style={{ right: 0, left: "auto" }}
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
              {siteName}
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
                    void logout();
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
                {(mobileMenu
                  ? mobileMenu.map((item) => ({
                      href: item.url,
                      label: item.title,
                    }))
                  : navigationLinks
                ).map((link) => (
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
    </>
  );
}
