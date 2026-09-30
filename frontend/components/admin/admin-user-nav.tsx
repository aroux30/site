"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { LogOut, User as UserIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";

export function AdminUserNav() {
  const router = useRouter();
  const { user, logout } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      await logout({ redirectTo: null });
      router.replace("/login");
    } catch {
      router.replace("/login");
    }
  }, [logout, router]);

  // Real name only — never fall back to phone, or the header prints the
  // number twice and the avatar initial becomes "0".
  const realName =
    mounted && user
      ? [user.firstName, user.lastName].filter(Boolean).join(" ").trim() ||
        (user.name && !/^\d/.test(user.name) ? user.name : "") ||
        (user.fullName && !/^\d/.test(user.fullName) ? user.fullName : "")
      : "";
  const displayName = realName || "مدیر سیستم";
  const isSuper =
    mounted && user
      ? Boolean(user.is_superuser || user.roles?.includes("super_admin"))
      : false;
  const userPhone = mounted && user ? user.phone || "" : "";

  return (
    <div className="flex items-center gap-3" suppressHydrationWarning>
      {/* Desktop: name + role. Phone stays off this breakpoint. */}
      <div className="hidden sm:flex flex-col items-end" suppressHydrationWarning>
        <div className="flex items-center gap-1.5" suppressHydrationWarning>
          <span className="text-xs font-semibold text-foreground" suppressHydrationWarning>
            {displayName}
          </span>
          <Badge
            variant="outline"
            className="h-4 px-1 text-[10px] text-emerald-600 border-emerald-500/30"
            suppressHydrationWarning
          >
            {isSuper ? "سوپراَدمین" : "مدیر سیستم"}
          </Badge>
        </div>
      </div>

      {/* Mobile: phone only — the compact identity when name would overflow. */}
      {userPhone ? (
        <span
          className="sm:hidden text-[11px] font-mono text-muted-foreground"
          suppressHydrationWarning
        >
          {userPhone}
        </span>
      ) : null}

      <div
        className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-xs"
        suppressHydrationWarning
        aria-hidden
      >
        <UserIcon className="h-4 w-4" />
      </div>

      <Button
        variant="ghost"
        size="icon"
        onClick={handleLogout}
        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
        title="خروج از حساب مدیریت"
      >
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  );
}

export default AdminUserNav;
