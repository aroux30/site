import Link from "next/link";
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
  Shield,
  Wallet,
  Briefcase,
  Gift,
  Layout,
  Bell,
} from "lucide-react";
import { AdminAuthGuard } from "@/components/admin/admin-auth-guard";
import { AdminUserNav } from "@/components/admin/admin-user-nav";

const adminLinks = [
  { href: "/admin/dashboard", label: "داشبورد", icon: LayoutDashboard },
  { href: "/admin/approvals", label: "کارتابل تاییدها", icon: ClipboardCheck },
  { href: "/admin/products", label: "محصولات", icon: Package },
  { href: "/admin/orders", label: "سفارش‌ها", icon: ShoppingCart },
  { href: "/admin/kanban", label: "میز کانبان سفارشات", icon: Kanban },
  { href: "/admin/users", label: "کاربران", icon: Users },
  { href: "/admin/categories", label: "دسته‌بندی‌ها", icon: Tag },
  { href: "/admin/reports", label: "گزارش‌ها", icon: BarChart3 },
  { href: "/admin/pages", label: "صفحات", icon: FileText },
  { href: "/admin/settings", label: "تنظیمات", icon: Settings },
  // ── Karta Platform Upgrade (New Modules) ──
  { href: "/admin/digital-inventory", label: "انبار کدهای دیجیتال", icon: CreditCard },
  { href: "/admin/anti-fraud", label: "ضدتقلب و هویت", icon: Shield },
  { href: "/admin/fintech", label: "پرداخت و کارت‌به‌کارت", icon: Wallet },
  { href: "/admin/b2b-reseller", label: "فروش سازمانی B2B", icon: Briefcase },
  { href: "/admin/gamification", label: "کارت هدیه و گردونه شانس", icon: Gift },
  { href: "/admin/cms", label: "محتوا و منوساز", icon: Layout },
  { href: "/admin/notices", label: "اعلانات زمان‌دار", icon: Bell },
];

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AdminAuthGuard>
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <aside className="sticky top-0 h-screen w-64 border-l border-border bg-card">
          {/* Logo */}
          <div className="flex h-16 items-center border-b border-border px-6">
            <Link href="/admin/dashboard" className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
                ف
              </div>
              <span className="font-bold text-foreground">پنل مدیریت</span>
            </Link>
          </div>

          {/* Navigation */}
          <nav className="space-y-1 p-4">
            {adminLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <link.icon className="h-4 w-4" />
                {link.label}
              </Link>
            ))}
          </nav>

          {/* Back to Store */}
          <div className="absolute bottom-4 right-4 left-4">
            <Link
              href="/"
              className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <ChevronLeft className="h-4 w-4" />
              بازگشت به فروشگاه
            </Link>
          </div>
        </aside>

        {/* Main Content */}
        <div className="flex-1">
          {/* Top Bar */}
          <header className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-border bg-background/95 px-6 backdrop-blur">
            <h2 className="text-lg font-semibold text-foreground">پنل مدیریت</h2>
            <AdminUserNav />
          </header>

          {/* Page Content */}
          <main className="p-6">{children}</main>
        </div>
      </div>
    </AdminAuthGuard>
  );
}
