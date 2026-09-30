"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Package,
  Users,
  ShoppingCart,
  BarChart3,
  Settings,
  Tag,
  FileText,
  ChevronLeft,
  Kanban,
  ClipboardCheck,
  CreditCard,
  Boxes,
  Shield,
  Wallet,
  Briefcase,
  Gift,
  Layout,
  Bell,
  Activity,
  PlugZap,
  AlertTriangle,
  Database,
  ArrowLeftRight,
  Webhook,
  ImageIcon,
  Percent,
  Factory,
  ClipboardList,
  ScrollText,
  Warehouse,
  BookOpen,
  CalendarCheck,
  Repeat,
  GitBranch,
  MapPin,
  FolderOpen,
  CalendarDays,
  ScanLine,
  Store,
  Tags,
  Coins,
  Star,
  PackageX,
  Search,
  Mail,
  Palette,
  Languages,
  Zap,
} from "lucide-react";
import { AdminAuthGuard } from "@/components/admin/admin-auth-guard";
import { AdminUserNav } from "@/components/admin/admin-user-nav";
import { AdminGlobalSearch } from "@/components/admin/global-search";
import { AdminTelemetryBadge } from "@/components/admin/admin-telemetry-badge";
import { AdminHelpDrawer } from "@/components/admin/help-drawer";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { cn } from "@/lib/utils";

/**
 * Admin sidebar entries. Exported so a test can assert that every admin route
 * is reachable: two routes shipped with no entry here and could only be opened
 * by typing the URL, which no amount of rendering tests would have caught.
 */
export const adminLinks = [
  { href: "/admin/dashboard", label: "داشبورد", icon: LayoutDashboard },
  { href: "/admin/approvals", label: "کارتابل تاییدها", icon: ClipboardCheck },
  { href: "/admin/products", label: "محصولات", icon: Package },
  { href: "/admin/orders", label: "سفارش‌ها", icon: ShoppingCart },
  { href: "/admin/invoices", label: "اسناد مالی", icon: FileText },
  { href: "/admin/tax", label: "موتور مالیات", icon: Percent },
  { href: "/admin/kanban", label: "میز کانبان سفارشات", icon: Kanban },
  { href: "/admin/tickets", label: "تیکت‌ها و پشتیبانی", icon: Bell },
  { href: "/admin/users", label: "کاربران", icon: Users },
  { href: "/admin/categories", label: "دسته‌بندی‌ها", icon: Tag },
  { href: "/admin/reports", label: "گزارش‌ها", icon: BarChart3 },
  { href: "/admin/pages", label: "صفحات", icon: FileText },
  { href: "/admin/blog", label: "وبلاگ", icon: FileText },
  { href: "/admin/settings", label: "تنظیمات", icon: Settings },
  // ── Marketplace & promotions ──
  { href: "/admin/vendors", label: "فروشندگان", icon: Store },
  { href: "/admin/discounts", label: "تخفیف‌ها", icon: Tags },
  { href: "/admin/cashback", label: "کش‌بک", icon: Coins },
  { href: "/admin/reviews", label: "بررسی نظرات", icon: Star },
  { href: "/admin/returns", label: "مرجوعی‌ها (RMA)", icon: PackageX },
  // ── Karta Platform Upgrade (New Modules) ──
  {
    href: "/admin/digital-inventory",
    label: "انبار کدهای دیجیتال",
    icon: CreditCard,
  },
  { href: "/admin/warehouses", label: "انبارها", icon: Warehouse },
  { href: "/admin/inventory-counts", label: "شمارش فیزیکی موجودی", icon: ClipboardCheck },
  { href: "/admin/inventory-transfers", label: "انتقال بین انبارها", icon: ArrowLeftRight },
  { href: "/admin/inventory-receipts", label: "دریافت کالا", icon: Boxes },
  { href: "/admin/procurement/suppliers", label: "تامین‌کننده‌ها", icon: Factory },
  { href: "/admin/procurement/pos", label: "سفارش‌های خرید", icon: ClipboardList },
  // ── Recurring subscriptions (اشتراک‌های دوره‌ای) ──
  { href: "/admin/subscriptions", label: "اشتراک‌های دوره‌ای", icon: Repeat },
  // ── Multi-step approval chains (زنجیره‌های تایید) ──
  { href: "/admin/approval-policies", label: "زنجیره‌های تایید", icon: GitBranch },
  // ── Pickup points (نقاط تحویل حضوری) ──
  { href: "/admin/pickup-points", label: "نقاط تحویل حضوری", icon: MapPin },
  // ── Inbound webhook receivers (گیرنده‌های ورودی) ──
  { href: "/admin/inbound-webhooks", label: "گیرنده‌های webhook", icon: Webhook },
  // ── Documents & attachments (اسناد و پیوست‌ها) ──
  { href: "/admin/documents", label: "اسناد و پیوست‌ها", icon: FolderOpen },
  // ── Wholesale pipeline (قیف فروش عمده) ──
  { href: "/admin/crm", label: "قیف فروش عمده", icon: Users },
  // ── Operational calendar (تقویم عملیاتی) ──
  { href: "/admin/calendar", label: "تقویم عملیاتی", icon: CalendarDays },
  // ── Barcode scanning station (ایستگاه اسکن) ──
  { href: "/admin/inventory-scan", label: "ایستگاه اسکن", icon: ScanLine },
  // ── Period comparison (مقایسه دوره‌ای) ──
  { href: "/admin/bi", label: "مقایسه دوره‌ای", icon: BarChart3 },
  // ── Accounting feed (دفتر روزنامه و کدینگ حسابها) ──
  {
    href: "/admin/accounting",
    label: "کدینگ حساب‌ها",
    icon: BookOpen,
  },
  {
    href: "/admin/accounting/journal",
    label: "دفتر روزنامه",
    icon: ScrollText,
  },
  {
    href: "/admin/accounting/periods",
    label: "بستن دوره مالی",
    icon: CalendarCheck,
  },
  { href: "/admin/anti-fraud", label: "ضدتقلب و هویت", icon: Shield },
  { href: "/admin/fintech", label: "پرداخت و کارت‌به‌کارت", icon: Wallet },
  { href: "/admin/b2b-reseller", label: "فروش سازمانی B2B", icon: Briefcase },
  { href: "/admin/pricing", label: "لیست‌های قیمت", icon: Tag },
  { href: "/admin/gamification", label: "کارت هدیه و گردونه شانس", icon: Gift },
  { href: "/admin/cms", label: "محتوا و منوساز", icon: Layout },
  { href: "/admin/themes", label: "پوسته‌ها", icon: Palette },
  { href: "/admin/translations", label: "مدیریت ترجمه‌ها", icon: Languages },
  { href: "/admin/newsletter", label: "خبرنامه", icon: Mail },
  { href: "/admin/content-types", label: "سازنده تایپ محتوا", icon: Database },
  { href: "/admin/widgets", label: "نواحی ویجت", icon: Layout },
  { href: "/admin/media", label: "کتابخانه رسانه", icon: ImageIcon },
  { href: "/admin/redirects", label: "ریدایرکت‌ها", icon: ArrowLeftRight },
  { href: "/admin/seo", label: "تحلیل سئو", icon: Search },
  { href: "/admin/webhooks", label: "وب‌هوک‌ها", icon: Webhook },
  { href: "/admin/content-transfer", label: "انتقال محتوا", icon: ArrowLeftRight },
  { href: "/admin/system-health", label: "سلامت سامانه", icon: Activity },
  { href: "/admin/privacy", label: "حریم خصوصی و GDPR", icon: Shield },
  { href: "/admin/rbac", label: "نقش‌ها و دسترسی‌ها", icon: Shield },
  // Automation rules (trigger → conditions → actions). The engine and its six
  // admin routes shipped with no sidebar entry, so the whole feature was
  // reachable only by typing the URL.
  { href: "/admin/automation", label: "قواعد خودکارسازی", icon: Zap },
  { href: "/admin/automation/dead-letters", label: "پیام‌های مردهٔ Outbox", icon: AlertTriangle },
  { href: "/admin/audit", label: "گزارش رویدادها", icon: ScrollText },
  { href: "/admin/plugins", label: "پلاگین‌ها و هوک‌ها", icon: Boxes },
  { href: "/admin/data-exchange", label: "ورود و خروج داده", icon: ArrowLeftRight },
  { href: "/admin/data-exchange/export", label: "خروجی داده", icon: Database },
  { href: "/admin/notices", label: "اعلانات زمان‌دار", icon: Bell },
  // ─ Operations & audit ─
  // These two routes existed with no way in: reachable only by typing the URL.
  { href: "/admin/exceptions", label: "مرکز عملیات و حسابرسی", icon: Activity },
  {
    href: "/admin/integrations",
    label: "قابلیت‌های یکپارچه‌سازی",
    icon: PlugZap,
  },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  return (
    <div className="flex min-h-screen">
      {/* Skip link: the sidebar is 60+ entries rendered before any content, so a
          keyboard user would otherwise tab through all of it on every page.
          Visually hidden until focused, which is the WordPress pattern. */}
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:absolute focus:right-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        پرش به محتوا
      </a>
      {/* Sidebar (desktop only — mobile gets a horizontal nav strip) */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-l border-border bg-card lg:flex">
        {/* Logo */}
        <div className="flex h-16 shrink-0 items-center border-b border-border px-6">
          <Link
            href="/admin/dashboard"
            prefetch={false}
            className="flex items-center gap-2"
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              ف
            </div>
            <span className="font-bold text-foreground">پنل مدیریت</span>
          </Link>
        </div>

        {/* Navigation — scrollable so it can never be overlapped */}
        <nav aria-label="ناوبری اصلی پنل مدیریت" className="flex-1 space-y-1 overflow-y-auto p-4">
          {adminLinks.map((link) => {
            // Exact match for a leaf, prefix match for a section, so opening
            // /admin/orders/123 still highlights "سفارش‌ها" rather than nothing.
            const active =
              pathname === link.href || pathname.startsWith(`${link.href}/`);
            return (
              <Link
                key={link.href}
                href={link.href}
                prefetch={false}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-muted hover:text-foreground",
                  active
                    ? "bg-muted font-semibold text-foreground"
                    : "text-muted-foreground"
                )}
              >
                <link.icon className="h-4 w-4" />
                {link.label}
              </Link>
            );
          })}
        </nav>

        {/* Back to Store */}
        <div className="shrink-0 border-t border-border p-4">
          <Link
            href="/"
            prefetch={false}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
            بازگشت به فروشگاه
          </Link>
        </div>
      </aside>

      {/* Main Content */}
      <div className="min-w-0 flex-1">
        {/* Top Bar */}
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-4 border-b border-border bg-background/95 px-4 backdrop-blur sm:px-6">
          <h2 className="hidden shrink-0 text-lg font-semibold text-foreground md:block">
            پنل مدیریت
          </h2>
          {/* Global search sits in the header so it is reachable from every
              admin screen — a support lookup must not require first knowing
              which page the record lives on. */}
          <AdminGlobalSearch />
          <div className="flex shrink-0 items-center gap-3">
            <AdminHelpDrawer />
            <AdminTelemetryBadge />
            <ThemeToggle />
            <AdminUserNav />
          </div>
        </header>

        {/* Mobile navigation strip: scrollable */}
        <nav className="flex gap-1 overflow-x-auto border-b border-border bg-card px-3 py-2 lg:hidden">
          {adminLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              prefetch={false}
              className="flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <link.icon className="h-3.5 w-3.5" />
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Page Content Guarded */}
        <main id="admin-content" tabIndex={-1} className="p-4 sm:p-6">
          <AdminAuthGuard>{children}</AdminAuthGuard>
        </main>
      </div>
    </div>
  );
}
