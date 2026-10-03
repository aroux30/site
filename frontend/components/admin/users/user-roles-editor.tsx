"use client";

/**
 * Assign and remove roles for one user.
 *
 * P0 "کاربران: UI انتساب نقش به کاربر". The routes (`/rbac/admin/users/{id}/roles`)
 * and the typed client (`assignUserRoles`, `removeUserRoles`, `getUserRoles`) both
 * existed with **zero callers** — a complete, working feature that no operator
 * could reach. The users page could override a single permission on a user, but
 * not give them a role, which is the thing an operator actually reaches for: a
 * role is a named bundle, and a per-user permission override is a scalpel.
 *
 * Split into a role column and a permission column, with a checkbox per role,
 * because the two grant different things and conflating them is how a store ends
 * up with an account that has every permission and no role, or a role that
 * cannot do anything because its one overridden permission was denied.
 *
 * Saves on change, per role, rather than behind a Save button. A role assignment
 * is a single self-contained action, and a dialog-level Save would make an
 * operator think the change is pending when it is not. The failure path is
 * explicit: a rejected save restores the checkbox and says so, because a role
 * list that looks correct and is not is how the wrong person keeps admin for a
 * month.
 */

import { useCallback, useEffect, useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { useToast } from "@/components/ui/use-toast";
import { rbacApi, type Role } from "@/lib/api/rbac";

interface UserRolesProps {
  // `string | number` because that is what `AdminUser.id` is, and the rest of the
  // users admin (`updateUser`, `blockUser`) already accepts both. Narrowing here
  // would have meant a cast at the call site for no gain.
  userId: string | number;
  /** Disabled while the account is being created — there is no id yet. */
  disabled?: boolean;
}

export function UserRolesEditor({ userId, disabled }: UserRolesProps) {
  const [all, setAll] = useState<Role[]>([]);
  const [assigned, setAssigned] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const { toast } = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [roles, mine] = await Promise.all([
        rbacApi.listRoles(),
        rbacApi.getUserRoles(userId),
      ]);
      setAll(roles);
      setAssigned(new Set(mine.roles.map((r) => r.id)));
    } catch {
      // Said plainly rather than shown as an empty list: "this user has no roles"
      // and "we could not read the roles" look identical otherwise, and the first
      // is a fact an operator might act on.
      toast({
        title: "خواندن نقش‌ها ناموفق بود",
        description: "فهرست نقش‌های این کاربر بارگذاری نشد.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [userId, toast]);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }
    void load();
  }, [userId, load]);

  const toggle = async (role: Role, next: boolean) => {
    setBusy(role.id);
    const before = new Set(assigned);
    // Optimistic: the checkbox moves, then the request confirms. Rolled back on
    // failure below, so a rejected save never leaves a role that is not there
    // looking like one that is.
    setAssigned(next ? new Set([...before, role.id]) : new Set([...before].filter((id) => id !== role.id)));
    try {
      if (next) {
        await rbacApi.assignUserRoles(userId, [role.id]);
      } else {
        await rbacApi.removeUserRoles(userId, [role.id]);
      }
    } catch {
      setAssigned(before);
      toast({
        title: next ? "اعطای نقش ناموفق بود" : "لغو نقش ناموفق بود",
        description: next
          ? `نقش «${role.name}» به کاربر اعطا نشد و وضعیت قبلی بازگردانده شد.`
          : `نقش «${role.name}» لغو نشد و وضعیت قبلی بازگردانده شد.`,
        variant: "destructive",
      });
    } finally {
      setBusy(null);
    }
  };

  if (!userId || disabled) {
    return (
      <p className="text-xs text-muted-foreground">
        نقش‌ها پس از ایجاد حساب قابل تنظیم هستند.
      </p>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        در حال بارگذاری نقش‌ها...
      </div>
    );
  }

  if (!all.length) {
    return (
      <p className="text-xs text-muted-foreground">
        هیچ نقشی تعریف نشده است. ابتدا از بخش مدیریت نقش‌ها یک نقش بسازید.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5" />
        نقش‌های کاربر
        <Badge variant="secondary" className="text-[10px]">
          {assigned.size}
        </Badge>
      </div>
      <ul className="space-y-1.5">
        {all.map((role) => {
          const on = assigned.has(role.id);
          const saving = busy === role.id;
          return (
            <li
              key={role.id}
              className="flex items-start gap-2.5 rounded-md border border-border/60 px-2.5 py-2"
            >
              <Checkbox
                id={`role-${role.id}`}
                checked={on}
                disabled={saving}
                onCheckedChange={(checked) => void toggle(role, !!checked)}
                className="mt-0.5"
              />
              <label htmlFor={`role-${role.id}`} className="min-w-0 flex-1 cursor-pointer">
                <span className="flex items-center gap-1.5 text-xs font-medium">
                  {role.name}
                  {role.is_system && (
                    <Badge variant="outline" className="text-[9px]">
                      سیستمی
                    </Badge>
                  )}
                </span>
                {role.description && (
                  <span className="mt-0.5 block text-[11px] leading-relaxed text-muted-foreground">
                    {role.description}
                  </span>
                )}
              </label>
              {saving && <Loader2 className="mt-0.5 h-3.5 w-3.5 animate-spin text-muted-foreground" />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
