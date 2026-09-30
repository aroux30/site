"use client";

import React, { useState } from "react";
import {
  Users,
  Search,
  Filter,
  Shield,
  UserCheck,
  UserX,
  Mail,
  Phone,
  Calendar,
  MoreVertical,
  CheckCircle2,
  XCircle,
  RefreshCw,
  Loader2,
  Download,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import {
  CreateUserButton,
  EditUserButton,
  UserDialog,
} from "@/components/admin/users/user-dialog";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";

const USERS_QUERY_KEY = "admin-users" as const;
const PAGE_SIZE = 50;

interface UserItem {
  id: string;
  phone: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  /** A user holds a set of roles, not one. The page used to read a singular
   *  `role` that the API never returned, so every row rendered "مشتری عادی"
   *  and the role filter matched nothing. */
  roles?: string[];
  role_slugs?: string[];
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}



export default function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  // Server-side paging. Without it the table showed the first 50 users and
  // nothing else, with no total to hint that anything was missing.
  const [page, setPage] = useState(1);
  // Create/edit dialog state. null user = create mode.
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [userBeingEdited, setUserBeingEdited] = useState<UserItem | null>(null);
  const openEditUser = (u: UserItem) => {
    setUserBeingEdited(u);
    setUserDialogOpen(true);
  };
  const openCreateUser = () => {
    setUserBeingEdited(null);
    setUserDialogOpen(true);
  };
  const [updatingUserId, setUpdatingUserId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  // GDPR data export (per-row download button)
  const [gdprBusyId, setGdprBusyId] = useState<string | null>(null);

  const {
    data,
    loading,
    error: loadErrorMessage,
    // Needed so a create/edit can refresh the list from the server rather
    // than guessing at the new row.
    reload: reloadUsers,
  } = useAdminQuery({
    // page and search are in the key: both are now server-side, so a stale
    // cache entry for page 1 would be served when the operator paged forward.
    queryKey: [USERS_QUERY_KEY, page, search.trim()],
    // The admin list lives on the users router: /api/v1/users/admin/users
    queryFn: async () => {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(PAGE_SIZE));
      // Server-side, not a client-side filter over one fixed page. The list
      // used to fetch `page=1&page_size=50` once and filter those 50 rows, so
      // past the fiftieth user the search box and the role filter silently
      // matched nobody, and the page showed no total so nothing looked cut.
      if (search.trim()) params.set("search", search.trim());
      const res = await apiClient.get(`/users/admin/users?${params.toString()}`);
      return {
        items: Array.isArray(res.data?.items) ? (res.data.items as UserItem[]) : [],
        total: typeof res.data?.total === "number" ? res.data.total : 0,
        totalPages:
          typeof res.data?.total_pages === "number" ? res.data.total_pages : 1,
      };
    },
    fallbackError: "دریافت فهرست کاربران ناموفق بود",
  });
  // Honest failure: an error state, never fabricated users. The old page used
  // a boolean; deriving it from the message keeps the same render branch.
  const loadError = loadErrorMessage !== null;
  const users: UserItem[] = data?.items ?? [];
  const totalUsers: number = data?.total ?? 0;
  const totalPages: number = Math.max(1, data?.totalPages ?? 1);
  const runMutation = useAdminMutation();

  const filteredUsers = users.filter((u) => {
    // Search is applied by the server now, so re-applying it here would only
    // ever narrow the current page further. The role filter still runs
    // client-side because the API has no role parameter.
    //
    // "customer" is the absence of any staff/vendor role, not a stored value —
    // matching it against the role list literally made the filter return nothing.
    const roles = u.roles ?? u.role_slugs ?? [];
    const matchesRole =
      roleFilter === "all" ||
      (roleFilter === "customer"
        ? !roles.includes("super_admin") && !roles.includes("vendor")
        : roles.includes(roleFilter));

    return matchesRole;
  });

  const toggleUserStatus = async (id: string, currentStatus: boolean) => {
    setUpdatingUserId(id);
    setActionError(null);
    const result = await runMutation(
      () => currentStatus
        // User is currently active -> block via POST /api/v1/users/admin/users/{id}/block
        ? apiClient.post(`/users/admin/users/${id}/block`)
        // User is currently blocked -> unblock via POST /api/v1/users/admin/users/{id}/unblock
        : apiClient.post(`/users/admin/users/${id}/unblock`),
      {
        fallbackError: "تغییر وضعیت کاربر با خطا مواجه شد.",
        invalidateKeys: [[USERS_QUERY_KEY]],
      },
    );
    if (!result.ok) setActionError(result.error);
    setUpdatingUserId(null);
  };

  // GDPR right of access: download everything stored for this user as JSON.
  const exportUserData = async (id: string) => {
    setGdprBusyId(id);
    try {
      const { privacyApi } = await import("@/lib/api/wp-parity");
      const data = await privacyApi.exportUser(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `user-data-${id.slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch {
      setActionError("خروجی گرفتن داده‌های کاربر ناموفق بود.");
    } finally {
      setGdprBusyId(null);
    }
  };

  const userColumns: DataTableColumn<UserItem>[] = [
    {
      key: "user",
      header: "کاربر",
      render: (u) => (
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary/10 font-bold text-primary">
            {u.first_name ? u.first_name[0] : "ک"}
          </div>
          <div>
            <div className="font-medium text-foreground">
              {u.first_name && u.last_name ? `${u.first_name} ${u.last_name}` : "کاربر بدون نام"}
            </div>
            <div
              className="font-mono text-[10px] text-muted-foreground"
              dir="ltr"
              title="شناسه کاربر (UUID)"
            >
              {u.id.slice(0, 8)}…
            </div>
            {u.email && <div className="text-xs text-muted-foreground">{u.email}</div>}
          </div>
        </div>
      ),
    },
    {
      key: "phone",
      header: "شماره تماس",
      className: "font-mono text-sm",
      render: (u) => toPersianDigits(u.phone),
    },
    {
      key: "role",
      header: "نقش",
      render: (u) => {
        const roles = u.roles ?? u.role_slugs ?? [];
        if (roles.includes("super_admin") || u.is_superuser) {
          return (
            <Badge variant="destructive" className="gap-1">
              <Shield className="h-3 w-3" /> مدیر کل
            </Badge>
          );
        }
        if (roles.includes("vendor")) {
          return <Badge variant="secondary">فروشنده</Badge>;
        }
        return (
          <Badge variant="outline">
            {roles.length ? roles.join("، ") : "مشتری عادی"}
          </Badge>
        );
      },
    },
    {
      key: "created",
      header: "تاریخ ثبت‌نام",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (u) =>
        u.created_at
          ? new Date(u.created_at).toLocaleDateString("fa-IR", {
              year: "numeric",
              month: "2-digit",
              day: "2-digit",
            })
          : "—",
    },
    {
      key: "status",
      header: "وضعیت حساب",
      render: (u) =>
        u.is_active ? (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
            <CheckCircle2 className="h-3.5 w-3.5" /> فعال
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-destructive">
            <XCircle className="h-3.5 w-3.5" /> مسدود
          </span>
        ),
    },
    {
      key: "actions",
      header: <span className="sr-only">عملیات</span>,
      className: "text-center",
      render: (u) => (
        <div className="flex items-center justify-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            disabled={updatingUserId === u.id}
            onClick={() => toggleUserStatus(u.id, u.is_active)}
            className="text-xs min-w-[80px]"
          >
            {updatingUserId === u.id ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : u.is_active ? (
              "مسدودسازی"
            ) : (
              "فعال‌سازی"
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={gdprBusyId === u.id}
            onClick={() => void exportUserData(u.id)}
            title="خروجی گرفتن داده‌های کاربر (GDPR)"
            aria-label="خروجی داده‌های کاربر"
          >
            {gdprBusyId === u.id ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Download className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </Button>
          <EditUserButton user={u} onClick={() => openEditUser(u)} />
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مدیریت کاربران</h1>
          <p className="text-sm text-muted-foreground">
            مشاهده، جستجو و مدیریت نقش و وضعیت حساب‌های کاربری
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="px-3 py-1 text-sm font-medium">
            مجموع کاربران: {toPersianDigits(users.length)}
          </Badge>
        </div>
      </div>

      {/* Filters Bar */}
      <Card className="p-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                // A filter change that keeps page 3 would show the new result
                // set's third page, which is usually empty.
                setPage(1);
              }}
              placeholder="جستجو با شماره موبایل، نام یا ایمیل..."
              className="ps-9"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="all">همه نقش‌ها</option>
              <option value="customer">مشتریان</option>
              <option value="super_admin">مدیران سیستم</option>
              <option value="vendor">فروشندگان</option>
            </select>
            <CreateUserButton onClick={openCreateUser} />
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <DataTable<UserItem>
        columns={userColumns}
        rows={filteredUsers}
        rowKey={(u) => u.id}
        loading={loading}
        error={loadError ? "خطا در دریافت کاربران. لطفاً صفحه را دوباره بارگذاری کنید." : null}
        emptyMessage="کاربری با این مشخصات یافت نشد."
      />

      {/* Paging is server-side, so the control has to exist: before this the
          table silently showed the first 50 rows and there was no total on
          screen to suggest more existed. */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {totalUsers.toLocaleString("fa-IR")} کاربر — صفحهٔ {page} از{" "}
            {totalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              قبلی
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              بعدی
            </Button>
          </div>
        </div>
      )}

      {/* Create / edit. The list is otherwise read-only apart from block and
          the GDPR export, so an operator had no way to onboard a staff
          account from the admin at all. */}
      <UserDialog
        user={userBeingEdited}
        open={userDialogOpen}
        onOpenChange={setUserDialogOpen}
        onSaved={() => void reloadUsers()}
      />
    </div>
  );
}
