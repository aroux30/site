"use client";

import React, { useState } from "react";
import { Shield, Plus, RefreshCw, Trash2, Users, KeyRound, X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  rbacApi,
  type OverrideEffect,
  type Permission,
  type PermissionOverride,
  type Role,
} from "@/lib/api/rbac";
import { capabilitiesApi } from "@/lib/api/wp-parity";
import { usersAdminApi, type AdminUser } from "@/lib/api/users";
import { toPersianDigits } from "@/lib/utils";
import { useAdminQuery } from "@/lib/api/admin-query";

const RBAC_QUERY_KEY = "admin-rbac" as const;
const USER_SEARCH_KEY = "admin-rbac-user-search" as const;

/**
 * RBAC administration (WordPress roles/capabilities parity).
 * The backend and typed client existed since Phase 5, but neither had a UI —
 * roles/permissions could only be managed through the API.
 */
export default function AdminRbacPage() {
  const { toast } = useToast();

  // create-role dialog
  const [roleOpen, setRoleOpen] = useState(false);
  const [roleName, setRoleName] = useState("");
  const [roleSlug, setRoleSlug] = useState("");
  const [roleDesc, setRoleDesc] = useState("");
  const [roleSaving, setRoleSaving] = useState(false);

  // permission-assignment dialog
  const [permRole, setPermRole] = useState<Role | null>(null);
  const [permSelected, setPermSelected] = useState<Set<string>>(new Set());
  const [permSaving, setPermSaving] = useState(false);

  // per-user permission-override dialog (WordPress add_cap/remove_cap parity).
  // Kept as a dialog rather than an inline panel because the page is organised
  // around roles, and an override is a per-user exception to a role — the same
  // relationship the page already shows as a dialog for role permissions.
  const [overrideOpen, setOverrideOpen] = useState(false);
  const [overrideUser, setOverrideUser] = useState<AdminUser | null>(null);
  const [overrideQuery, setOverrideQuery] = useState("");
  const [overrides, setOverrides] = useState<PermissionOverride[]>([]);
  const [overridesLoading, setOverridesLoading] = useState(false);
  const [overrideBusy, setOverrideBusy] = useState<string | null>(null);

  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [RBAC_QUERY_KEY],
    queryFn: async () => {
      const [r, p, c] = await Promise.allSettled([
        rbacApi.listRoles(),
        rbacApi.listPermissions(),
        capabilitiesApi.list(),
      ]);
      const permissions = p.status === "fulfilled" ? p.value : [];
      // WordPress capability names per role. This is the projection the
      // backend derives from each role's assigned permissions, so a role
      // created here shows up without any extra wiring.
      const capabilities = c.status === "fulfilled" ? c.value.roles : {};
      if (r.status !== "fulfilled") return { roles: [], permissions, capabilities };
      // The list endpoint omits permissions; hydrate each role from the
      // detail endpoint so the table can show its capability chips.
      const detailed = await Promise.allSettled(r.value.map((role) => rbacApi.getRole(role.id)));
      const roles = r.value.map((role, i) => {
        const d = detailed[i];
        return d && d.status === "fulfilled"
          ? { ...role, ...d.value }
          : { ...role, permissions: [] };
      });
      return { roles, permissions, capabilities };
    },
    fallbackError: "بارگذاری نقشها ناموفق بود",
  });
  const roles: Role[] = data?.roles ?? [];
  const permissions: Permission[] = data?.permissions ?? [];
  const capabilities: Record<string, string[]> = data?.capabilities ?? {};

  // User picker for the override dialog. Only queried while the dialog is open:
  // the override screen is the one place this page needs the user list, and the
  // users endpoint is a paged admin read that has no business running on every
  // RBAC page load.
  const {
    data: userSearch,
    loading: usersLoading,
  } = useAdminQuery({
    queryKey: [USER_SEARCH_KEY, overrideQuery.trim()],
    queryFn: () =>
      usersAdminApi.listUsers({
        search: overrideQuery.trim() || undefined,
        page: 1,
        page_size: 20,
      }),
    fallbackError: "جستجوی کاربران ناموفق بود",
    enabled: !!overrideUser,
  });
  const userResults: AdminUser[] = userSearch?.items ?? [];

  const createRole = async () => {
    if (!roleName.trim() || !roleSlug.trim()) {
      toast({ title: "خطا", description: "نام و نامک نقش الزامی است", variant: "destructive" });
      return;
    }
    if (!/^[a-z][a-z0-9_-]{1,99}$/.test(roleSlug.trim())) {
      toast({ title: "خطا", description: "نامک باید با حروف کوچک لاتین شروع شود", variant: "destructive" });
      return;
    }
    setRoleSaving(true);
    try {
      await rbacApi.createRole({
        name: roleName.trim(),
        slug: roleSlug.trim(),
        description: roleDesc.trim() || undefined,
      });
      toast({ title: "نقش ساخته شد" });
      setRoleOpen(false);
      setRoleName("");
      setRoleSlug("");
      setRoleDesc("");
      void load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
      toast({ title: "خطا", description: detail ?? "ایجاد نقش ناموفق بود", variant: "destructive" });
    } finally {
      setRoleSaving(false);
    }
  };

  const deleteRole = async (role: Role) => {
    if (role.is_system) {
      toast({ title: "غیرمجاز", description: "نقش‌های سیستمی حذف نمی‌شوند", variant: "destructive" });
      return;
    }
    if (!confirm(`نقش «${role.name}» حذف شود؟`)) return;
    try {
      await rbacApi.deleteRole(role.id);
      void load();
    } catch {
      toast({ title: "خطا", description: "حذف نقش ناموفق بود", variant: "destructive" });
    }
  };

  const openPermissions = (role: Role) => {
    setPermRole(role);
    setPermSelected(new Set(role.permissions.map((p) => p.id)));
  };

  const savePermissions = async () => {
    if (!permRole) return;
    setPermSaving(true);
    try {
      const current = new Set(permRole.permissions.map((p) => p.id));
      const next = permSelected;
      const toAdd = [...next].filter((id) => !current.has(id));
      const toRemove = [...current].filter((id) => !next.has(id));
      if (toAdd.length) await rbacApi.assignPermissions(permRole.id, toAdd);
      if (toRemove.length) await rbacApi.removePermissions(permRole.id, toRemove);
      toast({
        title: "ذخیره شد",
        description: `${toPersianDigits(String(toAdd.length))} افزوده، ${toPersianDigits(String(toRemove.length))} حذف`,
      });
      setPermRole(null);
      void load();
    } catch {
      toast({ title: "خطا", description: "ذخیره دسترسی‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setPermSaving(false);
    }
  };

  const togglePerm = (id: string) => {
    setPermSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const openOverrides = async (user: AdminUser) => {
    setOverrideUser(user);
    setOverridesLoading(true);
    try {
      const res = await rbacApi.listPermissionOverrides(String(user.id));
      setOverrides(res.items);
    } catch {
      // A failed read must not read as "this user has no overrides" — that is
      // the same silent-empty bug the products page had.
      setOverrides([]);
      toast({
        title: "خطا",
        description: "دریافت استثناهای مجوز کاربر ناموفق بود",
        variant: "destructive",
      });
    } finally {
      setOverridesLoading(false);
    }
  };

  /**
   * Grant or deny one permission for the open user, then reload.
   *
   * The override row is an upsert keyed on (user, permission), so this same
   * call flips an existing grant into a deny. The buttons show the effect they
   * will *produce*, not the effect currently stored, so an operator never has
   * to reason about which button is the "fix" one.
   */
  const setOverride = async (permission: string, effect: OverrideEffect) => {
    if (!overrideUser) return;
    setOverrideBusy(permission);
    try {
      await rbacApi.setPermissionOverride(String(overrideUser.id), permission, effect);
      toast({
        title: effect === "grant" ? "مجوز اعطا شد" : "مجوز منع شد",
        description: permission,
      });
      const res = await rbacApi.listPermissionOverrides(String(overrideUser.id));
      setOverrides(res.items);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
      toast({ title: "خطا", description: detail ?? "اعمال استثنا ناموفق بود", variant: "destructive" });
    } finally {
      setOverrideBusy(null);
    }
  };

  const revokeOverride = async (permission: string) => {
    if (!overrideUser) return;
    setOverrideBusy(permission);
    try {
      await rbacApi.revokePermissionOverride(String(overrideUser.id), permission);
      toast({ title: "استثنا برداشته شد", description: permission });
      const res = await rbacApi.listPermissionOverrides(String(overrideUser.id));
      setOverrides(res.items);
    } catch {
      toast({ title: "خطا", description: "برداشتن استثنا ناموفق بود", variant: "destructive" });
    } finally {
      setOverrideBusy(null);
    }
  };

  /**
   * Remove a permission from the catalog.
   *
   * Refused outright for a permission any role still holds: deleting it would
   * silently strip that capability from every holder, and the request would
   * succeed. The guard is here rather than in the API because the API cannot
   * tell the difference between "unused" and "in use" without the same lookup.
   */
  const deletePermission = async (permission: Permission) => {
    const holders = roles.filter((r) => r.permissions.some((p) => p.id === permission.id));
    if (holders.length > 0) {
      toast({
        title: "غیرمجاز",
        description: `این مجوز به ${toPersianDigits(String(holders.length))} نقش داده شده است؛ ابتدا آن را از نقش‌ها بردارید`,
        variant: "destructive",
      });
      return;
    }
    if (!confirm(`مجوز «${permission.slug}» حذف شود؟`)) return;
    try {
      await rbacApi.deletePermission(permission.id);
      toast({ title: "مجوز حذف شد" });
      void load();
    } catch {
      toast({ title: "خطا", description: "حذف مجوز ناموفق بود", variant: "destructive" });
    }
  };

  // group permissions by their resource prefix ("admin:access" → "admin")
  const grouped = permissions.reduce<Record<string, Permission[]>>((acc, p) => {
    const group = (p.slug ?? p.resource ?? "other").split(":")[0] || "other";
    (acc[group] ??= []).push(p);
    return acc;
  }, {});

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            نقش‌ها و دسترسی‌ها (RBAC)
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            مدیریت نقش‌ها و مجوزهای دقیق به سبک WordPress capabilities
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setOverrideOpen(true);
              setOverrideUser(null);
              setOverrideQuery("");
              setOverrides([]);
            }}
          >
            <KeyRound className="h-4 w-4 ms-2" />
            استثنای مجوز کاربر
          </Button>
          <Button size="sm" onClick={() => setRoleOpen(true)}>
            <Plus className="h-4 w-4 ms-1" />
            نقش جدید
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-3">
          {roles.map((role) => (
            <Card key={role.id} className="p-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-sm">{role.name}</p>
                    {role.is_system && <Badge variant="secondary" className="text-xs">سیستمی</Badge>}
                    <Badge variant="outline" className="text-xs">
                      <Users className="h-3 w-3 ms-1" />
                      {toPersianDigits(String(role.user_count ?? 0))}
                    </Badge>
                  </div>
                  {role.description && (
                    <p className="mt-1 text-xs text-muted-foreground">{role.description}</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {role.permissions.slice(0, 8).map((p) => (
                      <Badge key={p.id} variant="outline" className="text-[10px] font-mono" dir="ltr">
                        {p.slug}
                      </Badge>
                    ))}
                    {role.permissions.length > 8 && (
                      <Badge variant="outline" className="text-[10px]">
                        +{toPersianDigits(String(role.permissions.length - 8))}
                      </Badge>
                    )}
                    {role.permissions.length === 0 && (
                      <span className="text-xs text-muted-foreground">بدون مجوز</span>
                    )}
                  </div>
                  {/* WordPress capability names implied by the permissions
                      above. Derived server-side from the RBAC tables, so a
                      role defined at runtime appears here identically. */}
                  {(capabilities[role.slug] ?? []).length > 0 && (
                    <div className="mt-2 border-t border-border pt-2">
                      <p className="mb-1 text-[10px] text-muted-foreground">
                        قابلیت‌های وردپرس
                      </p>
                      <div className="flex flex-wrap gap-1">
                        {(capabilities[role.slug] ?? []).map((cap) => (
                          <Badge key={cap} variant="secondary" className="text-[10px] font-mono" dir="ltr">
                            {cap}
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => openPermissions(role)}>
                    مدیریت دسترسی‌ها
                  </Button>
                  {!role.is_system && (
                    <Button size="sm" variant="ghost" onClick={() => deleteRole(role)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* create role */}
      <Dialog open={roleOpen} onOpenChange={setRoleOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>نقش جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="role-name">نام نقش</Label>
              <Input id="role-name" value={roleName} onChange={(e) => setRoleName(e.target.value)} placeholder="نویسنده" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="role-slug">نامک (لاتین)</Label>
              <Input id="role-slug" dir="ltr" value={roleSlug} onChange={(e) => setRoleSlug(e.target.value)} placeholder="editor" />
            </div>
            <div className="space-y-2">
              <Label>توضیح</Label>
              <Input value={roleDesc} onChange={(e) => setRoleDesc(e.target.value)} placeholder="دسترسی محدود برای تولید محتوا" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRoleOpen(false)}>انصراف</Button>
            <Button onClick={createRole} disabled={roleSaving}>
              {roleSaving ? "در حال ساخت..." : "ساخت"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* permission matrix */}
      <Dialog open={!!permRole} onOpenChange={() => setPermRole(null)}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle>دسترسی‌های نقش «{permRole?.name}»</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-3">
            {Object.entries(grouped).map(([group, perms]) => (
              <div key={group} className="space-y-1.5">
                <p className="text-xs font-semibold text-muted-foreground font-mono" dir="ltr">
                  {group}
                </p>
                <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                  {perms.map((p) => (
                    // A div, not a label: the delete button below is an
                    // interactive control, and nesting one inside a label
                    // makes clicking it also toggle the checkbox.
                    <div
                      key={p.id}
                      className="flex items-center gap-2 rounded border p-2 text-xs hover:bg-muted/50"
                    >
                      <input
                        type="checkbox"
                        checked={permSelected.has(p.id)}
                        onChange={() => togglePerm(p.id)}
                        className="cursor-pointer"
                      />
                      <label
                        className="flex-1 cursor-pointer font-mono"
                        dir="ltr"
                        onClick={() => togglePerm(p.id)}
                      >
                        {p.slug}
                      </label>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                        title={`حذف مجوز ${p.slug}`}
                        onClick={() => deletePermission(p)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPermRole(null)}>انصراف</Button>
            <Button onClick={savePermissions} disabled={permSaving}>
              {permSaving ? "در حال ذخیره..." : "ذخیره دسترسی‌ها"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Per-user permission overrides (WordPress add_cap/remove_cap) */}
      <Dialog
        open={overrideOpen}
        onOpenChange={(open) => {
          setOverrideOpen(open);
          if (!open) setOverrideUser(null);
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle>
              {overrideUser
                ? `استثناهای مجوز — ${overrideUser.phone}`
                : "انتخاب کاربر برای استثنای مجوز"}
            </DialogTitle>
          </DialogHeader>

          {!overrideUser ? (
            <div className="space-y-3 py-3">
              <div className="space-y-2">
                <Label htmlFor="override-search">جستجوی کاربر</Label>
                <Input
                  id="override-search"
                  value={overrideQuery}
                  onChange={(e) => setOverrideQuery(e.target.value)}
                  placeholder="شماره، ایمیل یا نام"
                  dir="ltr"
                />
              </div>
              {usersLoading ? (
                <div className="flex justify-center py-6">
                  <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : userResults.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">
                  کاربری یافت نشد
                </p>
              ) : (
                <div className="space-y-1">
                  {userResults.map((u) => (
                    <button
                      key={String(u.id)}
                      type="button"
                      onClick={() => void openOverrides(u)}
                      className="flex w-full items-center justify-between rounded border p-2 text-xs hover:bg-muted/50"
                    >
                      <span className="font-mono" dir="ltr">{u.phone}</span>
                      <span className="text-muted-foreground">
                        {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-4 py-3">
              <Card className="border-primary/40 bg-primary/5 p-3">
                <div className="flex items-start gap-2 text-xs text-muted-foreground">
                  <KeyRound className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <p>
                    <strong className="font-medium text-foreground">منع</strong>{" "}
                    بر مجوزهای نقش‌های این کاربر غلبه می‌کند؛{" "}
                    <strong className="font-medium text-foreground">اعطا</strong>{" "}
                    مجوزی را بدون نقش اضافه می‌کند. هر دو بر همهٔ نقش‌ها مقدم‌اند.
                  </p>
                </div>
              </Card>

              {overridesLoading ? (
                <div className="flex justify-center py-6">
                  <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : (
                <>
                  {overrides.length > 0 && (
                    <div className="space-y-1">
                      <p className="text-xs font-semibold text-muted-foreground">
                        استثناهای فعلی
                      </p>
                      {overrides.map((o) => (
                        <div
                          key={o.id}
                          className="flex items-center justify-between rounded border p-2 text-xs"
                        >
                          <span className="font-mono" dir="ltr">{o.permission}</span>
                          <div className="flex items-center gap-1">
                            <Badge
                              variant={o.effect === "deny" ? "destructive" : "default"}
                              className="text-[10px]"
                            >
                              {o.effect === "deny" ? "منع" : "اعطا"}
                            </Badge>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 w-6 p-0 text-destructive hover:text-destructive"
                              title="برداشتن استثنا"
                              disabled={overrideBusy === o.permission}
                              onClick={() => void revokeOverride(o.permission)}
                            >
                              <X className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-muted-foreground">
                      اعطا یا منع مجوز
                    </p>
                    <div className="max-h-72 space-y-2 overflow-y-auto">
                      {Object.entries(grouped).map(([group, perms]) => (
                        <div key={group} className="space-y-1">
                          <p className="text-[10px] font-mono text-muted-foreground" dir="ltr">
                            {group}
                          </p>
                          <div className="grid grid-cols-1 gap-1 sm:grid-cols-2">
                            {perms.map((p) => {
                              const current = overrides.find(
                                (o) => o.permission === p.slug,
                              );
                              return (
                                <div
                                  key={p.id}
                                  className="flex items-center justify-between gap-1 rounded border p-1.5 text-[11px]"
                                >
                                  <span className="truncate font-mono" dir="ltr">
                                    {p.slug}
                                  </span>
                                  <div className="flex shrink-0 items-center gap-1">
                                    <Button
                                      variant={current?.effect === "grant" ? "default" : "ghost"}
                                      size="sm"
                                      className="h-6 px-2 text-[10px]"
                                      disabled={overrideBusy === p.slug}
                                      onClick={() => void setOverride(p.slug, "grant")}
                                    >
                                      اعطا
                                    </Button>
                                    <Button
                                      variant={current?.effect === "deny" ? "destructive" : "ghost"}
                                      size="sm"
                                      className="h-6 px-2 text-[10px]"
                                      disabled={overrideBusy === p.slug}
                                      onClick={() => void setOverride(p.slug, "deny")}
                                    >
                                      منع
                                    </Button>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                if (overrideUser) setOverrideUser(null);
                else setOverrideOpen(false);
              }}
            >
              {overrideUser ? "تغییر کاربر" : "بستن"}
            </Button>
            {overrideUser && (
              <Button variant="ghost" onClick={() => setOverrideOpen(false)}>
                پایان
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
