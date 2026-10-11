"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronDown, ChevronLeft, Menu } from "lucide-react";

import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  adminNavGroups,
  dashboardLink,
  findActiveGroupId,
  isNavItemActive,
  isPathUnderItem,
  type AdminNavItem,
} from "@/lib/admin-nav";
import { cn } from "@/lib/utils";

/**
 * Grouped admin navigation.
 *
 * Structure and behavior choices, each answering a failure of the old flat
 * 44-item list:
 *
 *  - Groups collapse (one open at a time). The flat list pushed 44 rows into
 *    the operator's view on every page; now the sidebar shows the dashboard
 *    plus seven area headers, with only the current area expanded.
 *  - The group containing the current page opens itself, and the operator's
 *    manual choice is remembered in localStorage — landing on a page whose
 *    parent group is closed is the "where am I?" failure this prevents.
 *  - On mobile the 44-link horizontal strip is replaced by a drawer with the
 *    same grouped nav, closed automatically after a navigation.
 *
 * Active-state coloring keeps the same-token pair (bg-foreground/10 +
 * text-foreground) from the 2026-10-04 contrast fix — mixing two different
 * tokens is what made the active item invisible under the site's inline theme.
 */

const OPEN_GROUP_STORAGE_KEY = "admin-nav-open-group";

export function AdminSidebarNav({
  onNavigate,
}: {
  /** Called after a nav link is clicked (the mobile drawer closes itself). */
  onNavigate?: () => void;
} = {}) {
  const pathname = usePathname();
  const [openGroupId, setOpenGroupId] = React.useState<string | null>(() =>
    findActiveGroupId(pathname),
  );

  // Auto-open the group containing the current page; on the dashboard (no
  // active group) the operator's stored choice wins.
  React.useEffect(() => {
    const activeGroup = findActiveGroupId(pathname);
    if (activeGroup) {
      setOpenGroupId(activeGroup);
      return;
    }
    try {
      const stored = window.localStorage.getItem(OPEN_GROUP_STORAGE_KEY);
      if (stored) setOpenGroupId(stored);
    } catch {
      // Storage blocked (private mode / disabled cookies): groups still
      // toggle, they just don't persist.
    }
  }, [pathname]);

  function toggleGroup(id: string) {
    const next = openGroupId === id ? null : id;
    setOpenGroupId(next);
    try {
      if (next) window.localStorage.setItem(OPEN_GROUP_STORAGE_KEY, next);
      else window.localStorage.removeItem(OPEN_GROUP_STORAGE_KEY);
    } catch {
      // Storage blocked: the toggle still works for this session.
    }
  }

  return (
    <div className="space-y-1">
      <NavLink
        item={dashboardLink}
        active={isNavItemActive(pathname, dashboardLink)}
        onNavigate={onNavigate}
      />

      {adminNavGroups.map((group) => {
        const open = openGroupId === group.id;
        const hasActivePage = group.items.some((item) =>
          isPathUnderItem(pathname, item),
        );
        const panelId = `admin-nav-group-${group.id}`;
        return (
          <div key={group.id}>
            <button
              type="button"
              onClick={() => toggleGroup(group.id)}
              aria-expanded={open}
              aria-controls={panelId}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-foreground/5 hover:text-foreground",
                hasActivePage ? "text-foreground" : "text-muted-foreground",
              )}
            >
              <group.icon className="h-4 w-4 shrink-0" />
              <span className="flex-1 text-start">{group.label}</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 shrink-0 transition-transform duration-200",
                  open && "rotate-180",
                )}
              />
            </button>

            {/* grid-rows 0fr→1fr animates height without measuring it. The
                closed panel is `inert` so its links are not keyboard-focusable
                while they are visually clipped. */}
            <div
              id={panelId}
              inert={!open}
              className={cn(
                "grid transition-[grid-template-rows] duration-200 ease-out",
                open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
              )}
            >
              <div className="overflow-hidden">
                <div className="mt-1 space-y-1 ps-3">
                  {group.items.map((item) => (
                    <NavItemRow
                      key={item.href}
                      item={item}
                      pathname={pathname}
                      onNavigate={onNavigate}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function NavItemRow({
  item,
  pathname,
  onNavigate,
}: {
  item: AdminNavItem;
  pathname: string;
  onNavigate?: () => void;
}) {
  return (
    <>
      <NavLink
        item={item}
        active={isNavItemActive(pathname, item)}
        onNavigate={onNavigate}
      />
      {item.children?.length ? (
        <div className="ms-4 space-y-1 border-s border-border/70 ps-2">
          {item.children.map((child) => (
            <NavLink
              key={child.href}
              item={child}
              active={isNavItemActive(pathname, child)}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      ) : null}
    </>
  );
}

function NavLink({
  item,
  active,
  onNavigate,
}: {
  item: AdminNavItem;
  active: boolean;
  onNavigate?: () => void;
}) {
  return (
    <Link
      href={item.href}
      prefetch={false}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        // Same-token pair: the tint is --foreground at 5–10% and the label is
        // --foreground itself, so the two can never invert against each other
        // (see the 2026-10-04 dark-on-dark contrast incident).
        "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors hover:bg-foreground/5 hover:text-foreground",
        active
          ? "bg-foreground/10 font-semibold text-foreground"
          : "text-muted-foreground",
      )}
    >
      <item.icon className="h-4 w-4 shrink-0" />
      {item.label}
    </Link>
  );
}

/** The mobile drawer: a menu button plus the same grouped nav in a Sheet. */
export function AdminMobileNav() {
  const [open, setOpen] = React.useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          aria-label="باز کردن منوی مدیریت"
          className="flex h-9 w-9 items-center justify-center rounded-md border border-border text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="flex w-72 max-w-[85vw] flex-col gap-0 p-0 sm:max-w-sm"
      >
        <SheetHeader className="border-b border-border p-4 text-start">
          <SheetTitle className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              ف
            </span>
            پنل مدیریت
          </SheetTitle>
        </SheetHeader>

        <nav
          aria-label="ناوبری اصلی پنل مدیریت"
          className="flex-1 overflow-y-auto p-3"
        >
          <AdminSidebarNav onNavigate={() => setOpen(false)} />
        </nav>

        <div className="shrink-0 border-t border-border p-3">
          <Link
            href="/"
            prefetch={false}
            className="flex items-center gap-2 rounded-lg border border-border px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
          >
            <ChevronLeft className="h-4 w-4" />
            بازگشت به فروشگاه
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
