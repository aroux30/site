"use client";

/**
 * Admin bar — the strip WordPress shows on the front end to anyone who can
 * reach the admin.
 *
 * Why it exists for a store: the editor writes a product description, opens the
 * page to check the result, and the only way back to that one product's admin
 * screen is to type the URL. The bar makes "I am looking at the thing I just
 * changed" a link rather than a memory test.
 *
 * It is admin-only by construction, not by hiding: the links here are the ones
 * a shopkeeper needs most, and every one of them is behind its own permission
 * check on the server. Someone who reaches the front end without those
 * permissions simply does not see the bar.
 *
 * It is fixed to the top and `AdminBarSpacer` reserves the same 36px above the
 * header, so the bar cannot cover it. The spacer is a component rather than a
 * constant padding because the «بدون نوار» preview collapses both together.
 */

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard,
  Package,
  ShoppingCart,
  Users,
  FileText,
  Settings,
  Plus,
  Pencil,
  ExternalLink,
} from "lucide-react";

import { useAuth } from "@/hooks/use-auth";
import { useAuthStore } from "@/stores/auth-store";
import type { User } from "@/types/user";
import { usePendingCommentCount } from "@/hooks/use-pending-comment-count";
import { useAdminBarHidden } from "@/hooks/use-admin-bar-hidden";
import { cn, toPersianDigits } from "@/lib/utils";

/** Height of the bar, in px. `AdminBarSpacer` reserves the same number. */
export const ADMIN_BAR_HEIGHT = 36;

/**
 * The admin screen that edits the thing at this storefront URL, or null.
 *
 * WordPress's core admin-bar affordance is "Edit Page" / "Edit Post" for the
 * object you are looking at — the bar here had only generic navigation, so an
 * operator checking a change still had to find the object by hand. This maps
 * the URL shape to the editor that owns it:
 *
 *   /blog/<slug>      -> /admin/blog?search=<slug>
 *   /products/<slug>  -> /admin/products?search=<slug>
 *   /<slug>           -> /admin/pages?search=<slug>
 *
 * Search rather than a deep link to the editor dialog: the admin pages take a
 * search param today, and a link that lands on the list with the object found
 * is honest — a guessed editor URL that 404s is worse than one extra click.
 */
function editTargetFor(pathname: string): { href: string; label: string } | null {
  const segments = pathname.split("/").filter(Boolean);
  if (segments.length === 0) return null;
  const first = segments[0];
  const second = segments[1];
  if (!first) return null;

  if (first === "blog" && second) {
    // The blog list searches title/excerpt/content, not slug. A slug is the
    // slugified title ("my-first-post"), so replacing the dashes with spaces
    // searches the words the title actually holds — a whole-string slug
    // search would match nothing and land the operator on an empty list.
    const words = second.replace(/-/g, " ");
    return { href: `/admin/blog?search=${encodeURIComponent(words)}`, label: "ویرایش نوشته" };
  }
  if (first === "products" && second) {
    return {
      href: `/admin/products?search=${encodeURIComponent(second)}`,
      label: "ویرایش محصول",
    };
  }
  // A bare top-level slug is a CMS page. Storefront routes that are not pages
  // are enumerated so the link does not appear on the cart, checkout, etc.
  const RESERVED = new Set([
    "blog", "products", "cart", "checkout", "login", "register", "account",
    "privacy", "about", "contact", "faq", "compare", "favorites", "payment",
    "search", "sitemap.xml", "robots.txt",
    "oembed", "uploads", "api",
  ]);
  if (segments.length === 1 && !RESERVED.has(first)) {
    return { href: `/admin/pages?search=${encodeURIComponent(first)}`, label: "ویرایش برگه" };
  }
  return null;
}

interface AdminBarProps {
  className?: string;
}

/** True when the bar actually renders on this page.
 *
 * The bar and the space reserved for it must agree exactly, or one of the two
 * lies: a bar with no room covers the header, and room with no bar is a dead
 * strip at the top of every visitor's page. This is the single place that
 * decides, so the two cannot drift apart the way two independent `if`s did.
 *
 * Auth does drive it, deliberately. The bar shows for a signed-in admin and
 * nothing else, so the space belongs to that same condition: a visitor must not
 * carry 36px of blank admin chrome. Signing in or out moves the content by
 * 36px, which is the bar arriving or leaving — not a glitch.
 *
 * Auth state arrives as an argument rather than from `useAuth()` here. Every
 * `useAuth()` call site fires its own `/auth/me` on mount and the hook has no
 * in-flight dedup, so a hook that mounted its own would add a third request to
 * every storefront page load to answer a question the bar already answers.
 */
function adminBarVisible(
  user: User | null,
  isLoading: boolean,
  isAuthenticated: boolean,
  pathname: string | null,
  barHidden: boolean,
): boolean {
  if (isLoading || !isAuthenticated || user?.role !== "admin") return false;
  if (barHidden) return false;
  // Inside the admin the bar is redundant — the sidebar is right there — and it
  // would double up with the admin's own chrome.
  if (pathname?.startsWith("/admin")) return false;

  return true;
}

/**
 * The reserved room for the fixed bar, as a component so the preview flag can
 * collapse it in the same tab.
 *
 * It used to be an unconditional `paddingTop` on the store layout, which was
 * right for the two states it knew about (signed-in admin / everyone else) and
 * wrong for both of the others: every signed-out visitor carried an empty 36px
 * strip above the header, and with the bar hidden the preview carried the same
 * dead strip. It now reserves exactly when the bar is there.
 *
 * Auth state is read from the shared store rather than through `useAuth()`:
 * both components sit in the same client tree and share one Zustand store, so
 * the answer here is the same one `AdminBar` computes — with no extra request.
 */
export function AdminBarSpacer() {
  const { user, isLoading, isAuthenticated } = useAuthStore();
  const pathname = usePathname();
  const barHidden = useAdminBarHidden();

  if (
    !adminBarVisible(user, isLoading, isAuthenticated, pathname, barHidden)
  ) {
    return null;
  }
  return <div aria-hidden style={{ height: ADMIN_BAR_HEIGHT }} />;
}

export function AdminBar({ className }: AdminBarProps) {
  const { user, isLoading, isAuthenticated } = useAuth();
  const { pending: pendingCommentCount } = usePendingCommentCount();
  const pathname = usePathname();
  const barHidden = useAdminBarHidden();
  const visible = adminBarVisible(
    user,
    isLoading,
    isAuthenticated,
    pathname,
    barHidden,
  );
  // The link must carry the URL the operator is actually looking at, with
  // `nobar=1` added — computed after mount because it reads `window.location`,
  // which does not exist during the server render. Until then the href points
  // at the pathname alone (still correct as a plain link; right-click-copy on
  // the first paint just omits the flag).
  const [previewHref, setPreviewHref] = useState<string>(pathname || "/");

  useEffect(() => {
    try {
      const url = new URL(window.location.href);
      url.searchParams.set("nobar", "1");
      setPreviewHref(url.pathname + url.search + url.hash);
    } catch {
      // Keep the pathname-only fallback.
    }
  }, [pathname]);

  if (!visible) return null;

  const editTarget = pathname ? editTargetFor(pathname) : null;

  return (
    <div
      className={cn(
        "fixed inset-x-0 top-0 z-50 h-9 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/80",
        className,
      )}
      style={{ height: ADMIN_BAR_HEIGHT }}
    >
      <div className="container mx-auto flex h-full items-center gap-1 overflow-x-auto px-4 text-xs">
        <Link
          href="/admin"
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 font-semibold text-foreground hover:bg-muted"
        >
          <LayoutDashboard className="h-3.5 w-3.5 text-emerald-600" />
          مدیریت فروشگاه
        </Link>

        <span className="mx-1 h-4 w-px shrink-0 bg-border" />

        {/* The four an operator reaches for while looking at a page. */}
        <Link
          href="/admin/products"
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Package className="h-3.5 w-3.5" />
          محصولات
        </Link>
        <Link
          href="/admin/orders"
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <ShoppingCart className="h-3.5 w-3.5" />
          سفارش‌ها
        </Link>
        <Link
          href="/admin/users"
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Users className="h-3.5 w-3.5" />
          کاربران
        </Link>
        <Link
          href="/admin/blog"
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <FileText className="h-3.5 w-3.5" />
          {/* Named exactly as the admin sidebar names it — the panel calls this
              section «وبلاگ». The bar called it «محتوا», which is not any other
              section's name: «صفحات» (CMS pages) and «محتوا و منوساز» (content
              builder) are two separate sidebar entries, so «محتوا» named
              neither of them and left the operator guessing. */}
          وبلاگ
          {/* The awaiting-mod bubble: an unanswered comment is a customer
              waiting, and nothing else in the panel says one is there. */}
          {pendingCommentCount !== null && pendingCommentCount > 0 && (
            <span
              className="rounded-full bg-amber-500 px-1.5 text-[10px] font-bold leading-4 text-white"
              title={`${pendingCommentCount} دیدگاه در انتظار بررسی`}
            >
              {toPersianDigits(String(pendingCommentCount))}
            </span>
          )}
        </Link>

        <span className="mx-1 h-4 w-px shrink-0 bg-border" />

        {/* There is no /admin/products/new route — adding a product is a dialog
            on the products page. A link to the page that does not exist would
            404, which is worse than not offering it. */}
        <Link
          href="/admin/products?new=1"
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950/20"
        >
          <Plus className="h-3.5 w-3.5" />
          افزودن محصول
        </Link>

        {/* Contextual edit: the admin screen that owns whatever this page is.
            Rendered only when the URL names an object — WordPress shows "Edit
            Page" here, and a link on the cart or checkout would be a link to
            nothing. */}
        {editTarget && (
          <Link
            href={editTarget.href}
            className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 font-medium text-amber-700 hover:bg-amber-50 dark:text-amber-400 dark:hover:bg-amber-950/20"
          >
            <Pencil className="h-3.5 w-3.5" />
            {editTarget.label}
          </Link>
        )}

        {/* Always last and always at the far end, so it is the one link that is
            in the same place on every page width. */}
        <Link
          href="/admin/settings"
          className="ms-auto flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        >
          <Settings className="h-3.5 w-3.5" />
          تنظیمات
        </Link>
        <a
          href={previewHref}
          target="_blank"
          rel="noreferrer"
          className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          title="مشاهده همین صفحه بدون نوار مدیریت"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          بدون نوار
        </a>
      </div>
    </div>
  );
}
