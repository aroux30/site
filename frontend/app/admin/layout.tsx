"use client";

import Link from "next/link";
import { ChevronLeft } from "lucide-react";

import { AdminAuthGuard } from "@/components/admin/admin-auth-guard";
import { AdminUserNav } from "@/components/admin/admin-user-nav";
import { AdminGlobalSearch } from "@/components/admin/global-search";
import { AdminTelemetryBadge } from "@/components/admin/admin-telemetry-badge";
import { AdminHelpDrawer } from "@/components/admin/help-drawer";
import { AdminNotices } from "@/components/admin/admin-notices";
import { AdminMobileNav, AdminSidebarNav } from "@/components/admin/admin-nav";
import { ThemeToggle } from "@/components/layout/theme-toggle";

/**
 * The admin shell.
 *
 * The navigation used to live here as a flat 44-item `adminLinks` array
 * rendered twice (desktop sidebar + mobile horizontal strip) — every module
 * appended wherever the previous one stopped, no categories, duplicated
 * icons, and the data-exchange parent/child rows both highlighted at once.
 *
 * The structure now lives in `lib/admin-nav.ts` (grouped, collapsible) and is
 * rendered by `components/admin/admin-nav.tsx`; this file keeps only the
 * chrome: skip link, sidebar frame, header, and content.
 */
export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen">
      {/* Skip link: the sidebar renders many entries before any content, so a
          keyboard user would otherwise tab through all of it on every page.
          Visually hidden until focused, which is the WordPress pattern. */}
      <a
        href="#admin-content"
        className="sr-only focus:not-sr-only focus:absolute focus:right-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        پرش به محتوا
      </a>
      {/* Sidebar (desktop only — mobile gets a drawer in the header) */}
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
        <nav
          aria-label="ناوبری اصلی پنل مدیریت"
          className="flex-1 overflow-y-auto p-4"
        >
          <AdminSidebarNav />
        </nav>

        {/* Back to Store */}
        <div className="shrink-0 border-t border-border p-4">
          <Link
            href="/"
            prefetch={false}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
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
          <div className="flex min-w-0 items-center gap-3">
            {/* Mobile: the same grouped nav in a drawer. The old horizontal
                strip rendered all 44 links in a scroll row, which was
                unusable on a phone and had no grouping at all. */}
            <AdminMobileNav />
            <h2 className="hidden shrink-0 text-lg font-semibold text-foreground md:block">
              پنل مدیریت
            </h2>
          </div>
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

        {/* Page Content Guarded */}
        <main id="admin-content" tabIndex={-1} className="p-4 sm:p-6">
          {/* Persistent notices, above the page rather than over it: an
              operator has to be able to read one without losing the screen they
              were on, and the toast that already existed could not do that. */}
          <AdminNotices className="mb-4" />
          <AdminAuthGuard>{children}</AdminAuthGuard>
        </main>
      </div>
    </div>
  );
}
