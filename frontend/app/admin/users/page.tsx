"use client";

import React, { useEffect, useState } from "react";
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
  KeyRound,
  Trash2,
  RotateCcw,
  MonitorSmartphone,
  Clock,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import { usersAdminApi } from "@/lib/api/users";
import { DeleteUserDialog } from "@/components/admin/users/delete-user-dialog";
import { UserSessionsDialog } from "@/components/admin/users/user-sessions-dialog";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import {
  CreateUserButton,
  EditUserButton,
  UserDialog,
} from "@/components/admin/users/user-dialog";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { rbacApi, type Role } from "@/lib/api/rbac";
import type { BulkAction } from "@/components/admin/list-engine";

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
  /** True while the account waits for an operator's approval. */
  pending_approval?: boolean;
  created_at: string;
  /** Set on a soft-deleted account. The row offers restore instead of delete
   *  when this is present. */
  deleted_at?: string | null;
}



export default function AdminUsersPage() {
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  // Soft-deleted accounts are hidden by default. Turning this on is the restore
  // view: the delete path had shipped without one, so a soft-deleted user could
  // never be found again — the restore endpoint existed with no way to reach it.
  const [showDeleted, setShowDeleted] = useState(false);
  // The approval queue. With `registration_approval_required` on, new accounts
  // are held pending; without this filter an operator could not find them among
  // every other row, so the setting would silently lock signups out.
  const [showPending, setShowPending] = useState(false);
  const [approvalBusyId, setApprovalBusyId] = useState<string | null>(null);
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
  // Admin-initiated password reset. Its own busy id rather than reusing the
  // export one, so clicking one button does not grey out the other on the same
  // row — they are independent operations that happen to sit next to each other.
  const [resetBusyId, setResetBusyId] = useState<string | null>(null);
  // Restore of a soft-deleted account. Its own busy id for the same reason.
  const [restoreBusyId, setRestoreBusyId] = useState<string | null>(null);
  // Success notices live separately from errors: "sent, check the inbox" and
  // "failed" are different answers and an operator must not have to tell which
  // one a banner means.
  const [notice, setNotice] = useState<string | null>(null);
  // Which account is open in the delete dialog, and which one to refetch.
  // Held as an id rather than the row so the dialog cannot render against
  // a list that has already refetched and replaced the object.
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  // Which account's sessions are open. Held as an id, like the delete target,
  // so a refetch cannot leave the dialog rendering against a replaced object.
  const [sessionsTargetId, setSessionsTargetId] = useState<string | null>(null);

  const {
    data,
    loading,
    error: loadErrorMessage,
    // Needed so a create/edit can refresh the list from the server rather
    // than guessing at the new row.
    reload: reloadUsers,
  } = useAdminQuery({
    // page, search and role are all in the key: each is server-side now, so a
    // stale cache entry for one combination would be served for another.
    queryKey: [USERS_QUERY_KEY, page, search.trim(), roleFilter, showDeleted, showPending],
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
      // The role filter too. It ran client-side because the API had no role
      // parameter, so "show me the vendors" answered with the vendors *on this
      // page* — the operator paged to find the rest. "customer" is the absence
      // of a staff/vendor role, which the server does not store; it maps to no
      // role param and is narrowed below, since the server has no "none of
      // these roles" clause.
      if (roleFilter !== "all" && roleFilter !== "customer") {
        params.set("role", roleFilter);
      }
      if (showDeleted) params.set("include_deleted", "true");
      // The approval queue, server-side like every other filter on this page.
      if (showPending) params.set("pending_approval", "true");
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
  // Resolved from the loaded rows rather than held as the row object: after a
  // refetch the held object is a stale copy, and the dialog would then show a
  // name that no longer matches the list behind it.
  const userBeingDeleted =
    deleteTargetId === null
      ? null
      : (data?.items ?? []).find((u) => String(u.id) === deleteTargetId) ?? null;
  const userWhoseSessions =
    sessionsTargetId === null
      ? null
      : (data?.items ?? []).find((u) => String(u.id) === sessionsTargetId) ?? null;

  const totalPages: number = Math.max(1, data?.totalPages ?? 1);
  const runMutation = useAdminMutation();

  // Only "customer" needs narrowing here, and only because it is defined by the
  // *absence* of a role — the server has no clause for that, and sending
  // role=customer would match the literal role that no one holds. Every other
  // value went to the server, so this filter is a no-op for them.
  const filteredUsers =
    roleFilter === "customer"
      ? users.filter((u) => {
          const roles = u.roles ?? u.role_slugs ?? [];
          return !roles.includes("super_admin") && !roles.includes("vendor");
        })
      : users;

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

  /**
   * Ask the backend to email a reset link to this account.
   *
   * The server's `sent` is surfaced rather than assumed. An account with no
   * address, or one that only ever signed in with an OTP and has no password to
   * reset, gets a truthful "nothing was sent" — and an operator told "done"
   * would go on watching an inbox for a message that was never written.
   */
  const sendPasswordReset = async (id: string) => {
    setResetBusyId(id);
    setActionError(null);
    try {
      const res = await usersAdminApi.sendPasswordReset(id);
      if (res.sent) {
        setNotice("پیوند بازنشانی رمز عبور به کاربر ارسال شد.");
      } else {
        setNotice(res.detail);
      }
    } catch {
      setActionError("ارسال پیوند بازنشانی رمز ناموفق بود.");
    } finally {
      setResetBusyId(null);
    }
  };

  const restoreUser = async (id: string) => {
    setRestoreBusyId(id);
    setActionError(null);
    setNotice(null);
    try {
      await usersAdminApi.restoreUser(id);
      setNotice("کاربر بازگردانی شد.");
      await reloadUsers();
    } catch {
      setActionError("بازگردانی کاربر ناموفق بود.");
    } finally {
      setRestoreBusyId(null);
    }
  };

  /**
   * Approve or reject a pending registration.
   *
   * Approving admits the account; rejecting marks it inactive, which the
   * existing unblock action can reverse. Both refetch so the row reflects the
   * server rather than a local guess.
   */
  const decideApproval = async (id: string, approve: boolean) => {
    setApprovalBusyId(id);
    setActionError(null);
    setNotice(null);
    try {
      if (approve) {
        await usersAdminApi.approveUser(id);
        setNotice("حساب تأیید شد.");
      } else {
        await usersAdminApi.rejectUser(id);
        setNotice("حساب رد شد. در صورت نیاز می‌توانید آن را فعال کنید.");
      }
      await reloadUsers();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "تغییر وضعیت تأیید ناموفق بود.",
      );
    } finally {
      setApprovalBusyId(null);
    }
  };

  // ── Bulk operations ──────────────────────────────────────────────────────
  // The role a "change role" bulk action targets. Loaded lazily (on first
  // selection) rather than on page load: most operator sessions never run a
  // bulk role change, and it is a second request the list does not need.
  const [bulkRoles, setBulkRoles] = useState<Role[]>([]);
  const [bulkRoleSlug, setBulkRoleSlug] = useState("");
  useEffect(() => {
    void rbacApi
      .listRoles()
      .then((roles) => {
        setBulkRoles(roles);
        setBulkRoleSlug((current) => current || roles[0]?.slug || "");
      })
      // Silent on failure: the other bulk actions still work, and a toast for a
      // picker that is empty until a role is chosen would be noise. The select
      // renders a hint when the list is empty.
      .catch(() => setBulkRoles([]));
  }, []);

  /**
   * Run one bulk action and report its real outcome.
   *
   * The server returns per-account results because the guards still run per
   * account; this surfaces the split rather than claiming success, so an
   * operator who selected 20 and had 3 refused learns that from the banner
   * instead of from a list that quietly still contains them.
   */
  const runBulk = async (
    action: "block" | "unblock" | "delete" | "restore" | "set_role",
    targets: UserItem[],
  ): Promise<boolean> => {
    setActionError(null);
    setNotice(null);
    try {
      const res = await usersAdminApi.bulkUsers(
        action,
        targets.map((u) => u.id),
        action === "set_role" ? { role_slug: bulkRoleSlug } : undefined,
      );
      if (res.failed > 0) {
        setActionError(
          `${toPersianDigits(res.ok)} مورد انجام شد، ${toPersianDigits(res.failed)} مورد انجام نشد.`,
        );
      } else {
        setNotice(`${toPersianDigits(res.ok)} مورد انجام شد.`);
      }
      await reloadUsers();
      return res.failed === 0;
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "عملیات گروهی ناموفق بود.",
      );
      return false;
    }
  };

  const bulkActions: BulkAction<UserItem>[] = [
    {
      id: "set_role",
      label: "تغییر نقش",
      onRun: (rows) => runBulk("set_role", rows),
    },
    {
      id: "block",
      label: "مسدودسازی",
      onRun: (rows) => runBulk("block", rows),
    },
    {
      id: "unblock",
      label: "فعال‌سازی",
      onRun: (rows) => runBulk("unblock", rows),
    },
    {
      id: "delete",
      label: "حذف",
      variant: "destructive",
      // Destructive, so WordPress-style confirmation is mandatory. The wording
      // names the consequence the operator cannot see: the delete is soft, and
      // it ends every session the account holds.
      confirm: (rows) =>
        `${toPersianDigits(rows.length)} حساب حذف شود؟ حساب‌ها نرم حذف می‌شوند و می‌توان بعداً بازگردانی کرد، اما نشست‌های فعالشان بسته می‌شود.`,
      onRun: (rows) => runBulk("delete", rows),
    },
  ];

  // The destination role for "تغییر نقش", rendered beside the buttons rather
  // than inside one — a form control nested in a button is invalid HTML and
  // clicking it would also trigger the button.
  const bulkControls = (
    <label className="flex items-center gap-1.5 text-xs text-muted-foreground">
      نقش مقصد:
      <select
        value={bulkRoleSlug}
        onChange={(e) => setBulkRoleSlug(e.target.value)}
        className="h-7 rounded border border-input bg-background px-1.5 text-xs"
        aria-label="نقش مقصد برای تغییر گروهی"
      >
        {bulkRoles.length === 0 && <option value="">بدون نقش</option>}
        {bulkRoles.map((r) => (
          <option key={r.id} value={r.slug}>
            {r.name}
          </option>
        ))}
      </select>
    </label>
  );

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
        u.pending_approval ? (
          // Pending is its own state, not "blocked": the account was never
          // admitted, and the row offers approve/reject rather than block.
          <Badge variant="warning" className="gap-1 text-[10px]">
            <Clock className="h-3 w-3" /> در انتظار تأیید
          </Badge>
        ) : u.is_active ? (
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
          {/* A pending account gets approve/reject instead of block/unblock:
              it was never admitted, so "block" would describe the wrong
              action and write the wrong audit entry. */}
          {u.pending_approval ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                disabled={approvalBusyId === u.id}
                onClick={() => void decideApproval(u.id, true)}
                className="text-xs text-emerald-600 min-w-[64px]"
              >
                {approvalBusyId === u.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  "تأیید"
                )}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={approvalBusyId === u.id}
                onClick={() => void decideApproval(u.id, false)}
                className="text-xs text-destructive min-w-[64px]"
              >
                رد
              </Button>
            </>
          ) : (
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
          )}
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
          <Button
            variant="ghost"
            size="sm"
            disabled={resetBusyId === u.id}
            onClick={() => void sendPasswordReset(u.id)}
            title="ارسال پیوند بازنشانی رمز عبور به این کاربر"
            aria-label="ارسال پیوند بازنشانی رمز عبور"
          >
            {resetBusyId === u.id ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <KeyRound className="h-3.5 w-3.5 text-muted-foreground" />
            )}
          </Button>
          {/* Sessions. Self-service "sign out everywhere" existed; an operator
              handling a stolen-account ticket had no way to see or cut a
              session on somebody else's account. */}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSessionsTargetId(String(u.id))}
            title="مشاهدهٔ نشست‌های فعال این کاربر"
            aria-label="نشست‌های فعال کاربر"
          >
            <MonitorSmartphone className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
          {/* A deleted row offers restore, not delete. The delete endpoint
              shipped with a client method and a route and no restore button, so
              a soft-deleted account was unreachable — the second half of the
              feature was missing while every layer of the first half existed. */}
          {u.deleted_at ? (
            <Button
              variant="ghost"
              size="sm"
              disabled={restoreBusyId === u.id}
              onClick={() => void restoreUser(u.id)}
              title="بازگردانی کاربر"
              aria-label="بازگردانی کاربر"
            >
              {restoreBusyId === u.id ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RotateCcw className="h-3.5 w-3.5 text-emerald-600" />
              )}
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setDeleteTargetId(String(u.id))}
              title="حذف کاربر"
              aria-label="حذف کاربر"
            >
              <Trash2 className="h-3.5 w-3.5 text-destructive/70" />
            </Button>
          )}
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

      {/* Operation feedback. `actionError` was already being set by every row
          action and rendered nowhere, so a failed GDPR export or a failed reset
          looked exactly like a slow one — the operator's only signal was a
          spinner that stopped. Notices are separate from errors because "sent,
          check the inbox" and "failed" are different answers. */}
      {(actionError || notice) && (
        <div
          role="status"
          aria-live="polite"
          className={
            actionError
              ? "rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive"
              : "rounded-md border border-border/60 bg-muted/40 px-3 py-2 text-xs text-muted-foreground"
          }
        >
          {actionError ?? notice}
          <button
            type="button"
            className="ms-3 underline underline-offset-2"
            onClick={() => {
              setActionError(null);
              setNotice(null);
            }}
          >
            بستن
          </button>
        </div>
      )}

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
              onChange={(e) => {
                setRoleFilter(e.target.value);
                // Same reason as the search box: a new filter on page 3 lands
                // on an empty page of a shorter result set.
                setPage(1);
              }}
              className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="all">همه نقش‌ها</option>
              <option value="customer">مشتریان</option>
              <option value="super_admin">مدیران سیستم</option>
              <option value="vendor">فروشندگان</option>
            </select>
            {/* The restore view. Without it a soft-deleted account vanished
                from the panel with no way back to it. */}
            <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap text-sm">
              <input
                type="checkbox"
                checked={showDeleted}
                onChange={(e) => {
                  setShowDeleted(e.target.checked);
                  setPage(1);
                }}
                className="h-4 w-4 rounded border-input"
              />
              حذف‌شده‌ها
            </label>
            {/* The approval queue. With registration approval on, this is how
                an operator finds the accounts waiting on them. */}
            <label className="flex cursor-pointer items-center gap-1.5 whitespace-nowrap text-sm">
              <input
                type="checkbox"
                checked={showPending}
                onChange={(e) => {
                  setShowPending(e.target.checked);
                  setPage(1);
                }}
                className="h-4 w-4 rounded border-input"
              />
              در انتظار تأیید
            </label>
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
        // Bulk operations. WordPress's users list has had multi-select since
        // forever; here an operator had to block fifty spam accounts one row at
        // a time. Selection is over the rows on screen (the server page), which
        // is what the select-all checkbox promises.
        selectable
        bulkActions={bulkActions}
        bulkControls={bulkControls}
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
      <DeleteUserDialog
        user={userBeingDeleted ?? null}
        open={deleteTargetId !== null}
        onOpenChange={(o) => {
          if (!o) setDeleteTargetId(null);
        }}
        onDeleted={() => reloadUsers()}
      />
      <UserSessionsDialog
        user={userWhoseSessions ?? null}
        open={sessionsTargetId !== null}
        onOpenChange={(o) => {
          if (!o) setSessionsTargetId(null);
        }}
      />
    </div>
  );
}
