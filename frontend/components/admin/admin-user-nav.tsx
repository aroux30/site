"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";

export function AdminUserNav() {
  const router = useRouter();
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    try {
      // redirectTo: null keeps navigation here — the admin logout must land on
      // /login, not the default post-logout home redirect.
      await logout({ redirectTo: null });
      router.replace("/login");
    } catch {
      router.replace("/login");
    }
  };

  const displayName = user?.fullName || user?.firstName || user?.name || user?.phone || "مدیر سیستم";
  const isSuper = user?.is_superuser || user?.roles?.includes("super_admin");

  return (
    <div className="flex items-center gap-3">
      <div className="hidden sm:flex flex-col items-end">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-semibold text-foreground">{displayName}</span>
          <Badge variant="outline" className="h-4 px-1 text-[10px] text-emerald-600 border-emerald-500/30">
            {isSuper ? "سوپراَدمین" : "مدیر سیستم"}
          </Badge>
        </div>
        <span className="text-[10px] text-muted-foreground font-mono">{user?.phone || ""}</span>
      </div>

      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-xs">
        {displayName[0] || "م"}
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
