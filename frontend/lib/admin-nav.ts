import {
  Activity,
  ArrowLeftRight,
  BadgePercent,
  Banknote,
  BarChart3,
  BellRing,
  Boxes,
  CalendarDays,
  ChartLine,
  CircleDollarSign,
  CircleHelp,
  ClipboardCheck,
  Coins,
  Cog,
  FileDown,
  FileSearch,
  FileText,
  FolderTree,
  Gift,
  Headphones,
  Images,
  Landmark,
  Layout,
  LayoutDashboard,
  Link2,
  LayoutGrid,
  Mail,
  Megaphone,
  MessagesSquare,
  Newspaper,
  Package,
  Paintbrush,
  PanelsTopLeft,
  PlugZap,
  ScrollText,
  Search,
  Send,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Signpost,
  Sparkles,
  Star,
  Store,
  TrendingUp,
  Unlink,
  Type,
  UserPlus,
  Users,
  UsersRound,
  Wallet,
  Zap,
  type LucideIcon,
  Eye,
  ImageIcon,
  Route,
  MapPin,
  Brain,
} from "lucide-react";

/**
 * The admin sidebar structure — one grouped source of truth.
 *
 * The menu grew one entry at a time for two years, so it shipped as a flat
 * 44-item list where each new module was appended wherever the last one
 * stopped: the tax engine sat between orders and tickets, three different
 * "data movement" entries used the same icon (data-exchange, its export
 * sub-page, and content-transfer — the last removed on 2026-10-07 because
 * data-exchange covers everything it did), and nothing carried a category.
 * Operators could not find anything without the Ctrl+K search.
 *
 * This file replaces that with eight areas (a standalone dashboard plus seven
 * collapsible groups). Rules for keeping it sane:
 *
 *  - Every route under `app/admin/` (except the documented exceptions in
 *    `tests/admin-nav-reachability.test.ts`) must appear here, or it is
 *    reachable only by typing the URL — the exact failure that shipped
 *    `/admin/exceptions` and `/admin/integrations` invisible.
 *  - `children` is for a sub-page that belongs to a parent (rendered indented
 *    under it). The active-state helpers below make sure only one of the two
 *    rows highlights at a time.
 *  - Icons must not repeat within a group: a duplicated glyph is what made
 *    the old flat list unreadable.
 */
export interface AdminNavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Sub-entries rendered indented under this item (e.g. a parent page's export view). */
  children?: AdminNavItem[];
}

export interface AdminNavGroup {
  id: string;
  label: string;
  icon: LucideIcon;
  items: AdminNavItem[];
}

/** The dashboard sits alone, above the groups — it is the most-visited page. */
export const dashboardLink: AdminNavItem = {
  href: "/admin/dashboard",
  label: "داشبورد",
  icon: LayoutDashboard,
};

export const adminNavGroups: AdminNavGroup[] = [
  {
    id: "store",
    label: "فروشگاه",
    icon: Store,
    items: [
      // Categories come first (owner order 2026-10-24): a category is the
      // parent a product is filed under, so the menu reads in definition
      // order — دسته‌بندی‌ها then محصولات.
      { href: "/admin/categories", label: "دسته‌بندی‌ها", icon: FolderTree },
      { href: "/admin/products", label: "محصولات", icon: Package },
      // «سفارش‌ها» and «میز کانبان سفارشات» were merged into one page on
      // 2026-10-10 (owner order: one menu, one page, list/board views). The
      // old /admin/kanban route still exists as a redirect to
      // /admin/orders?view=board, so it is deliberately NOT a nav entry —
      // see UNLINKED_BY_DESIGN in tests/admin-nav-reachability.test.ts.
      { href: "/admin/orders", label: "سفارش‌ها", icon: ShoppingCart },
      // Telegram order notifications — ported from WP plugin (tgnotif module)
      { href: "/admin/telegram-notify", label: "اطلاع‌رسانی تلگرام", icon: Send },
      {
        href: "/admin/digital-inventory",
        label: "انبار کدهای دیجیتال",
        icon: Boxes,
      },
      // USD→Toman price updater (Nobitex), ported from the owner's WordPress
      // plugin. It edits product prices, so it lives with the products.
      { href: "/admin/currency", label: "به‌روزرسانی قیمت دلاری", icon: CircleDollarSign },
      { href: "/admin/reviews", label: "بررسی نظرات", icon: Star },
    ],
  },
  {
    id: "customers",
    label: "مشتریان",
    icon: UsersRound,
    items: [
      { href: "/admin/users", label: "کاربران", icon: Users },
      { href: "/admin/user-verification", label: "احراز کاربران", icon: ShieldCheck },
      { href: "/admin/tickets", label: "تیکت‌ها و پشتیبانی", icon: Headphones },
      { href: "/admin/chat", label: "گفتگوی زنده", icon: MessagesSquare },
    ],
  },
  {
    id: "marketing",
    label: "بازاریابی",
    icon: Megaphone,
    items: [
      { href: "/admin/discounts", label: "تخفیف‌ها", icon: BadgePercent },
      { href: "/admin/cashback", label: "کش‌بک", icon: Coins },
      { href: "/admin/gamification", label: "کارت هدیه و گردونه شانس", icon: Gift },
      { href: "/admin/referrals", label: "دعوت دوستان", icon: UserPlus },
    ],
  },
  {
    id: "finance",
    label: "مالی",
    icon: Landmark,
    items: [
      { href: "/admin/fintech", label: "پرداخت و کارت‌به‌کارت", icon: Wallet },
      { href: "/admin/wallet", label: "کیف پول‌ها", icon: Banknote },
    ],
  },
  {
    id: "content",
    label: "محتوا",
    icon: Layout,
    items: [
      { href: "/admin/blog", label: "وبلاگ", icon: Newspaper },
      { href: "/admin/pages", label: "صفحات", icon: FileText },
      // FAQ owns a section (owner decision 2026-11-04): it is page content —
      // the /faq storefront page and the [faq] shortcode consume it — not a
      // piece of the layout builder's dashboard.
      { href: "/admin/faq", label: "سوالات متداول", icon: CircleHelp },
      { href: "/admin/cms", label: "محتوا و منوساز", icon: PanelsTopLeft },
      { href: "/admin/widgets", label: "نواحی ویجت", icon: LayoutGrid },
      { href: "/admin/media", label: "کتابخانه رسانه", icon: Images },
      { href: "/admin/themes", label: "تم‌ها و استایل", icon: Paintbrush },
      { href: "/admin/forms", label: "فرم‌های دریافتی", icon: Mail },
      // «ریدایرکت‌ها» و «تحلیل سئو» در ۲۰۲۶-۱۰-۰۹ به گروه اختصاصی «سئو»
      // منتقل شدند (دستور مالک: منوی سئو مثل Rank Math). تحلیل سئوی مستقل
      // حذف شد؛ موتور امتیازدهی داخل ویرایشگر هر نوشته است.
      // «سازنده تایپ محتوا» (content-types) was removed on 2026-10-09 per owner
      // decision: the store is an e-commerce platform; standard blog and CMS pages
      // suffice, dynamic content-type builders are unused.
      // «انتقال محتوا» (content-transfer) was removed on 2026-10-07. It
      // exported only CMS pages + FAQs as JSON, while «ورود و خروج داده»
      // (data-exchange) covers those two entities plus five more, with
      // CSV/XLSX upload and the WordPress WXR import. The owner's order:
      // the JSON file format is not needed — data-exchange replaces it.
      // «قالب‌های ایمیل» (email-templates) was removed on 2026-10-07 with the
      // rest of the email feature: the store is phone-first, and there are no
      // transactional emails left to edit.
    ],
  },
  {
    // The dedicated SEO area (owner request 2026-10-09: "یک منو و منو ها و
    // زیر منو براش بساز مثل رنک مث"). It owns the site-wide SEO surface:
    // the dashboard, the 404 monitor, redirect rules, and the global
    // settings. Per-content SEO stays where the content is — the blog
    // editor's SEO panel — so this group never grows a second editing form
    // for the same fields.
    id: "seo",
    label: "سئو",
    icon: Search,
    items: [
      { href: "/admin/seo", label: "داشبورد سئو", icon: LayoutDashboard },
      // Titles & Meta (Rank Math parity): default templates per content type.
      { href: "/admin/seo/titles-meta", label: "عنوان و توضیحات پیش‌فرض", icon: Type },
      // Search visibility (WordPress `blog_public`): the single write path for
      // the noindex switch. It used to live in Settings → General and again in
      // Settings → Content; both now link here instead of duplicating it.
      { href: "/admin/seo/visibility", label: "نمایش در موتورهای جست‌وجو", icon: Eye },
      // Image SEO (Rank Math parity): auto alt/title/caption at upload.
      { href: "/admin/seo/image", label: "سئوی تصویر", icon: ImageIcon },
      // Breadcrumbs (Rank Math parity): trail + BreadcrumbList structured data.
      { href: "/admin/seo/breadcrumbs", label: "مسیر صفحه (Breadcrumbs)", icon: Route },
      // Instant Indexing (Rank Math parity): IndexNow on publish.
      { href: "/admin/seo/indexing", label: "ایندکس فوری", icon: Zap },
      // Local SEO (Rank Math parity): LocalBusiness JSON-LD profile.
      { href: "/admin/seo/local", label: "سئوی محلی", icon: MapPin },
      // Content AI (Rank Math parity): meta suggestions via a configured LLM.
      { href: "/admin/seo/content-ai", label: "هوش مصنوعی محتوا", icon: Brain },
      { href: "/admin/seo/link-counter", label: "شمارش لینک‌ها", icon: Link2 },
      { href: "/admin/seo/link-genius", label: "نابغهٔ لینک (Link Genius)", icon: Sparkles },
      { href: "/admin/seo/link-audit", label: "بررسی لینک‌های شکسته", icon: Unlink },
      { href: "/admin/seo/status", label: "وضعیت و ابزارها", icon: ClipboardCheck },
      { href: "/admin/seo/404", label: "مانیتور ۴۰۴", icon: FileSearch },
      { href: "/admin/redirects", label: "ریدایرکت‌ها", icon: Signpost },
      { href: "/admin/seo/settings", label: "تنظیمات سئو", icon: Settings },
    ],
  },
  {
    id: "analytics",
    label: "گزارش‌ها و تحلیل",
    icon: TrendingUp,
    items: [
      { href: "/admin/reports", label: "گزارش‌ها", icon: BarChart3 },
      { href: "/admin/bi", label: "مقایسه دوره‌ای", icon: ChartLine },
      { href: "/admin/calendar", label: "تقویم عملیاتی", icon: CalendarDays },
    ],
  },
  {
    id: "system",
    label: "سیستم",
    icon: Cog,
    items: [
      {
        href: "/admin/settings",
        label: "تنظیمات",
        icon: Settings,
        // WordPress keeps URL structure on its own screen (options-
        // permalink.php) under Settings; same place here.
        children: [
          { href: "/admin/settings/permalink", label: "پیوندهای یکتا", icon: Link2 },
        ],
      },
      { href: "/admin/rbac", label: "نقش‌ها و دسترسی‌ها", icon: ShieldCheck },
      // Automation rules (trigger → conditions → actions). The engine and its
      // six admin routes shipped with no sidebar entry, so the whole feature
      // was reachable only by typing the URL.
      { href: "/admin/automation", label: "قواعد خودکارسازی", icon: Zap },
      { href: "/admin/audit", label: "گزارش رویدادها", icon: ScrollText },
      { href: "/admin/system-health", label: "سلامت سامانه", icon: Activity },
      {
        href: "/admin/data-exchange",
        label: "ورود و خروج داده",
        icon: ArrowLeftRight,
        // The export view is a sub-page of the data-exchange screen. It used
        // to be a second top-level row with the same icon, and both rows
        // highlighted at once because the parent's prefix match caught the
        // child's URL.
        children: [
          { href: "/admin/data-exchange/export", label: "خروجی داده", icon: FileDown },
        ],
      },
      { href: "/admin/notices", label: "اعلانات زمان‌دار", icon: BellRing },
      {
        href: "/admin/integrations",
        label: "قابلیت‌های یکپارچه‌سازی",
        icon: PlugZap,
      },
    ],
  },
];

/** Flat view of every entry (including children) — kept for the route ↔ nav
 *  reachability test, which asserts both directions against the filesystem. */
export const adminLinks: AdminNavItem[] = [
  dashboardLink,
  ...adminNavGroups.flatMap((group) =>
    group.items.flatMap((item) =>
      item.children ? [item, ...item.children] : [item],
    ),
  ),
];

function matchesPath(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * True when `item` should render as the current page. A parent with an active
 * child stays unhighlighted, so /admin/data-exchange/export lights exactly
 * one row (the child) instead of two.
 */
export function isNavItemActive(pathname: string, item: AdminNavItem): boolean {
  if (!matchesPath(pathname, item.href)) return false;
  return !item.children?.some((child) => matchesPath(pathname, child.href));
}

/** True when the pathname is this item's own page or any of its children's. */
export function isPathUnderItem(pathname: string, item: AdminNavItem): boolean {
  return (
    matchesPath(pathname, item.href) ||
    Boolean(item.children?.some((child) => matchesPath(pathname, child.href)))
  );
}

/** The id of the group that owns the current page, or null (e.g. dashboard). */
export function findActiveGroupId(pathname: string): string | null {
  for (const group of adminNavGroups) {
    if (group.items.some((item) => isPathUnderItem(pathname, item))) {
      return group.id;
    }
  }
  return null;
}
