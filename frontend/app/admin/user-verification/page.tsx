"use client";

/**
 * احراز کاربران — port of the WP plugin "user-verification-orders".
 *
 * Three tabs, like the plugin:
 *  - «کاربران»: search + verified filter + the tick itself (PATCH is_verified).
 *    Verified buyers' paid orders get the «در حال انجام (احراز شده)» lane.
 *  - «گزارش لاگ‌ها»: every verify/unverify flip (who, by whom, IP, when).
 *  - «تنظیمات»: master switch + Telegram notification credentials.
 *
 * RTL-native: the admin shell is RTL, so nothing here forces direction —
 * only phone/IP values are marked dir="ltr" (numbers must not flip).
 * Mobile: the user list switches to stacked cards below `sm`.
 */

import React, { useCallback, useEffect, useState } from "react";
import {
  BadgeCheck,
  Ban,
  CheckCircle2,
  Clock,
  ChevronLeft,
  ChevronRight,
  FileDown,
  Loader2,
  Search,
  Send,
  ShieldCheck,
  ShieldOff,
  UserCheck,
  UserX,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { JalaliDatePicker } from "@/components/ui/jalali-datepicker";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { formatJalali, formatJalaliDateTime } from "@/lib/date";
import { toPersianDigits } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { usersAdminApi, type AdminUser } from "@/lib/api/users";
import {
  exportVerificationLogs,
  fetchVerificationConfig,
  updateVerificationConfig,
  fetchVerificationLogs,
  type UserVerificationConfig,
  type VerificationLogItem,
} from "@/lib/api/user-verification-admin";
import { saveBlob } from "@/lib/api/data-exchange";

const USERS_PAGE_SIZE = 50;
const LOGS_PAGE_SIZE = 50;

const ROLE_LABELS: Record<string, string> = {
  super_admin: "مدیر کل",
  admin: "مدیر سیستم",
  editor: "سردبیر",
  author: "نویسنده",
  contributor: "مشارکت‌کننده",
  customer: "مشتری عادی",
};

function roleLabels(roles: string[] | undefined): string {
  if (!roles?.length) return ROLE_LABELS.customer ?? "مشتری عادی";
  return roles.map((r) => ROLE_LABELS[r] ?? r).join("، ");
}

function VerifiedBadge({ verified }: { verified: boolean }) {
  return verified ? (
    <Badge className="gap-1 border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
      <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
      احراز شده
    </Badge>
  ) : (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <ShieldOff className="h-3.5 w-3.5" aria-hidden />
      احراز نشده
    </Badge>
  );
}

function Pager({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (next: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <nav className="flex items-center justify-center gap-2" aria-label="صفحه‌بندی">
      <Button
        size="sm"
        variant="outline"
        disabled={page <= 1}
        onClick={() => onChange(page - 1)}
        aria-label="صفحه قبلی"
      >
        <ChevronRight className="h-4 w-4" aria-hidden />
        قبلی
      </Button>
      <span className="min-w-16 text-center text-sm text-muted-foreground">
        {toPersianDigits(page)} از {toPersianDigits(totalPages)}
      </span>
      <Button
        size="sm"
        variant="outline"
        disabled={page >= totalPages}
        onClick={() => onChange(page + 1)}
        aria-label="صفحه بعدی"
      >
        بعدی
        <ChevronLeft className="h-4 w-4" aria-hidden />
      </Button>
    </nav>
  );
}

export default function UserVerificationPage() {
  const { toast } = useToast();

  // ── config (settings tab) ──────────────────────────────────────────────
  const [config, setConfig] = useState<UserVerificationConfig | null>(null);
  const [savingConfig, setSavingConfig] = useState(false);

  const loadConfig = useCallback(async () => {
    try {
      setConfig(await fetchVerificationConfig());
    } catch {
      toast({ title: "خطا در دریافت تنظیمات", variant: "destructive" });
    }
  }, [toast]);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const saveConfig = async (patch: Partial<UserVerificationConfig>) => {
    if (!config) return;
    setSavingConfig(true);
    try {
      const next = await updateVerificationConfig({ ...config, ...patch });
      setConfig(next);
      toast({ title: "تنظیمات ذخیره شد" });
    } catch {
      toast({ title: "ذخیره تنظیمات ناموفق بود", variant: "destructive" });
    } finally {
      setSavingConfig(false);
    }
  };

  // ── users tab ──────────────────────────────────────────────────────────
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [verifiedFilter, setVerifiedFilter] = useState<"all" | "verified" | "unverified">("all");
  const [page, setPage] = useState(1);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 400);
    return () => clearTimeout(t);
  }, [search]);

  const loadUsers = useCallback(async () => {
    setLoadingUsers(true);
    try {
      const { items, total: t } = await usersAdminApi.listUsers({
        page,
        page_size: USERS_PAGE_SIZE,
        search: debouncedSearch || undefined,
        is_verified:
          verifiedFilter === "all" ? undefined : verifiedFilter === "verified",
      });
      setUsers(items);
      setTotal(t);
    } catch {
      toast({ title: "خطا در دریافت کاربران", variant: "destructive" });
    } finally {
      setLoadingUsers(false);
    }
  }, [page, debouncedSearch, verifiedFilter, toast]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  const toggleVerified = async (user: AdminUser) => {
    const id = String(user.id);
    if (pendingIds.has(id)) return;
    setPendingIds((s) => new Set(s).add(id));
    const next = !user.is_verified;
    try {
      await usersAdminApi.updateUser(id, { is_verified: next });
      setUsers((rows) =>
        rows.map((r) => (String(r.id) === id ? { ...r, is_verified: next } : r)),
      );
      toast({
        title: next ? "کاربر احراز شد" : "احراز کاربر لغو شد",
        description: next
          ? "سفارش‌های پرداخت‌شدهٔ این کاربر به وضعیت «در حال انجام (احراز شده)» منتقل می‌شوند."
          : undefined,
      });
    } catch {
      toast({ title: "تغییر وضعیت احراز ناموفق بود", variant: "destructive" });
    } finally {
      setPendingIds((s) => {
        const copy = new Set(s);
        copy.delete(id);
        return copy;
      });
    }
  };

  const userColumns: DataTableColumn<AdminUser>[] = [
    {
      key: "name",
      header: "کاربر",
      className: "",
      render: (u) => (
        <div>
          <div className="font-medium">
            {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
          </div>
          <div className="text-xs text-muted-foreground" dir="ltr">
            {u.phone}
          </div>
        </div>
      ),
    },
    {
      key: "roles",
      header: "نقش",
      className: "whitespace-nowrap",
      render: (u) => (
        <span className="text-xs text-muted-foreground">{roleLabels(u.roles)}</span>
      ),
    },
    {
      key: "verified",
      header: "وضعیت احراز",
      className: "whitespace-nowrap",
      render: (u) => <VerifiedBadge verified={Boolean(u.is_verified)} />,
    },
    {
      key: "account",
      header: "وضعیت حساب",
      className: "whitespace-nowrap",
      render: (u) =>
        u.pending_approval ? (
          <Badge variant="warning" className="gap-1 text-[10px]">
            <Clock className="h-3 w-3" aria-hidden />
            در انتظار تأیید
          </Badge>
        ) : u.is_active ? (
          <Badge variant="secondary" className="gap-1 text-[10px]">
            <CheckCircle2 className="h-3 w-3" aria-hidden />
            فعال
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1 text-[10px] text-muted-foreground">
            <Ban className="h-3 w-3" aria-hidden />
            غیرفعال
          </Badge>
        ),
    },
    {
      key: "last_login",
      header: "آخرین ورود",
      className: "whitespace-nowrap text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (u) => formatJalali(u.last_login),
    },
    {
      key: "created",
      header: "تاریخ ثبت‌نام",
      className: "whitespace-nowrap text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (u) => formatJalali(u.created_at),
    },
    {
      key: "action",
      header: "تغییر وضعیت",
      className: "whitespace-nowrap",
      render: (u) => {
        const busy = pendingIds.has(String(u.id));
        return (
          <Button
            size="sm"
            variant={u.is_verified ? "outline" : "default"}
            disabled={busy}
            onClick={() => void toggleVerified(u)}
            aria-label={u.is_verified ? "لغو احراز کاربر" : "احراز کاربر"}
            className="gap-1.5"
          >
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : u.is_verified ? (
              <UserX className="h-4 w-4" aria-hidden />
            ) : (
              <UserCheck className="h-4 w-4" aria-hidden />
            )}
            {u.is_verified ? "لغو احراز" : "احراز"}
          </Button>
        );
      },
    },
  ];

  // ── logs tab ───────────────────────────────────────────────────────────
  const [logs, setLogs] = useState<VerificationLogItem[]>([]);
  const [logsTotal, setLogsTotal] = useState(0);
  const [logsPage, setLogsPage] = useState(1);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [exportingLogs, setExportingLogs] = useState(false);
  const [logsSearch, setLogsSearch] = useState("");
  const [logsDateFrom, setLogsDateFrom] = useState("");
  const [logsDateTo, setLogsDateTo] = useState("");

  const [debouncedLogsSearch, setDebouncedLogsSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setDebouncedLogsSearch(logsSearch.trim()), 400);
    return () => clearTimeout(t);
  }, [logsSearch]);

  const logsFilters = useCallback(
    () => ({
      q: debouncedLogsSearch || null,
      date_from: logsDateFrom || null,
      date_to: logsDateTo || null,
    }),
    [debouncedLogsSearch, logsDateFrom, logsDateTo],
  );

  const loadLogs = useCallback(async () => {
    setLoadingLogs(true);
    try {
      const { items, total: t } = await fetchVerificationLogs({
        skip: (logsPage - 1) * LOGS_PAGE_SIZE,
        limit: LOGS_PAGE_SIZE,
        ...logsFilters(),
      });
      setLogs(items);
      setLogsTotal(t);
    } catch {
      toast({ title: "خطا در دریافت لاگ‌ها", variant: "destructive" });
    } finally {
      setLoadingLogs(false);
    }
  }, [logsPage, logsFilters, toast]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  const resetLogsPage = () => setLogsPage(1);

  const onExportLogs = async () => {
    setExportingLogs(true);
    try {
      const blob = await exportVerificationLogs(logsFilters());
      saveBlob(blob, `verification-logs-${new Date().toISOString().slice(0, 10)}.csv`);
      toast({ title: "خروجی آماده شد", description: "فایل CSV دانلود شد." });
    } catch {
      toast({
        title: "خطا",
        description: "تهیهٔ خروجی ناموفق بود.",
        variant: "destructive",
      });
    } finally {
      setExportingLogs(false);
    }
  };

  const logColumns: DataTableColumn<VerificationLogItem>[] = [
    {
      key: "user",
      header: "کاربر",
      className: "",
      render: (l) => (
        <span dir="ltr" className="text-sm font-medium">
          {l.user_phone ?? l.user_id}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      className: "whitespace-nowrap",
      render: (l) =>
        l.status ? (
          <Badge className="gap-1 border-emerald-300 bg-emerald-100 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300">
            <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
            احراز شد
          </Badge>
        ) : (
          <Badge variant="outline" className="gap-1">
            <ShieldOff className="h-3.5 w-3.5" aria-hidden />
            لغو احراز
          </Badge>
        ),
    },
    {
      key: "admin",
      header: "توسط (ادمین)",
      className: "whitespace-nowrap",
      render: (l) => (
        <span dir="ltr" className="text-sm">
          {l.admin_phone ?? "—"}
        </span>
      ),
    },
    {
      key: "ip",
      header: "IP",
      className: "whitespace-nowrap",
      hideOnMobile: true,
      render: (l) => (
        <span dir="ltr" className="text-sm text-muted-foreground">
          {l.ip_address ?? "—"}
        </span>
      ),
    },
    {
      key: "date",
      header: "تاریخ",
      className: "whitespace-nowrap",
      render: (l) => (
        <span className="text-sm text-muted-foreground">
          {l.created_at ? formatJalaliDateTime(l.created_at) : "—"}
        </span>
      ),
    },
  ];

  const totalPages = Math.max(1, Math.ceil(total / USERS_PAGE_SIZE));

  const filterOptions = [
    { value: "all", label: "همه" },
    { value: "verified", label: "احراز شده" },
    { value: "unverified", label: "احراز نشده" },
  ] as const;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
          <ShieldCheck className="h-6 w-6" aria-hidden />
        </div>
        <div>
          <h1 className="text-xl font-bold sm:text-2xl">احراز کاربران</h1>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            فقط سفارش‌های کاربران احرازشده وارد وضعیت «در حال انجام (احراز شده)»
            می‌شوند. احراز به صورت دستی و پس از تماس با مشتری انجام می‌گیرد.
          </p>
        </div>
      </div>

      <Tabs defaultValue="users">
        <TabsList className="w-full justify-start sm:w-auto">
          <TabsTrigger value="users" className="flex-1 sm:flex-none">
            مدیریت کاربران
          </TabsTrigger>
          <TabsTrigger value="logs" className="flex-1 sm:flex-none">
            گزارش لاگ‌ها
          </TabsTrigger>
          <TabsTrigger value="settings" className="flex-1 sm:flex-none">
            تنظیمات
          </TabsTrigger>
        </TabsList>

        {/* ── Users ─────────────────────────────────────────────────── */}
        <TabsContent value="users" className="space-y-4">
          {/* Filter bar: stacks on mobile, one row on sm+ */}
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
            <div className="relative w-full sm:w-72">
              <Search
                className="pointer-events-none absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden
              />
              <Input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="جستجو با شماره موبایل…"
                className="ps-9"
                aria-label="جستجوی کاربر"
              />
            </div>
            <div
              className="grid grid-cols-3 gap-1 rounded-lg bg-muted p-1 sm:flex sm:items-center"
              role="group"
              aria-label="فیلتر وضعیت احراز"
            >
              {filterOptions.map(({ value, label }) => (
                <Button
                  key={value}
                  size="sm"
                  variant={verifiedFilter === value ? "default" : "ghost"}
                  className="w-full sm:w-auto"
                  onClick={() => {
                    setVerifiedFilter(value);
                    setPage(1);
                  }}
                  aria-pressed={verifiedFilter === value}
                >
                  {label}
                </Button>
              ))}
            </div>
            <span className="text-xs text-muted-foreground">
              {toPersianDigits(total)} کاربر
            </span>
          </div>

          {/* Mobile: stacked cards. Desktop: table. */}
          <div className="space-y-3 sm:hidden">
            {loadingUsers ? (
              <div className="flex items-center justify-center gap-2 py-12 text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" aria-hidden />
                در حال بارگذاری…
              </div>
            ) : users.length === 0 ? (
              <p className="py-12 text-center text-sm text-muted-foreground">
                کاربری پیدا نشد.
              </p>
            ) : (
              users.map((u) => (
                <Card key={String(u.id)} className="p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate font-medium">
                        {[u.first_name, u.last_name].filter(Boolean).join(" ") || "—"}
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground" dir="ltr">
                        {u.phone}
                      </div>
                    </div>
                    <VerifiedBadge verified={Boolean(u.is_verified)} />
                  </div>
                  <Button
                    size="sm"
                    variant={u.is_verified ? "outline" : "default"}
                    disabled={pendingIds.has(String(u.id))}
                    onClick={() => void toggleVerified(u)}
                    className="mt-3 w-full gap-1.5"
                    aria-label={u.is_verified ? "لغو احراز کاربر" : "احراز کاربر"}
                  >
                    {pendingIds.has(String(u.id)) ? (
                      <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                    ) : u.is_verified ? (
                      <UserX className="h-4 w-4" aria-hidden />
                    ) : (
                      <UserCheck className="h-4 w-4" aria-hidden />
                    )}
                    {u.is_verified ? "لغو احراز" : "احراز کاربر"}
                  </Button>
                </Card>
              ))
            )}
          </div>
          <div className="hidden sm:block">
            <DataTable
              columns={userColumns}
              rows={users}
              rowKey={(u) => String(u.id)}
              loading={loadingUsers}
              emptyMessage="کاربری پیدا نشد."
              pageSize={USERS_PAGE_SIZE}
              tableLayout="fixed"
            />
          </div>

          <Pager page={page} totalPages={totalPages} onChange={setPage} />
        </TabsContent>

        {/* ── Logs ──────────────────────────────────────────────────── */}
        <TabsContent value="logs" className="space-y-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">گزارش لاگ‌های احراز</CardTitle>
              <CardDescription>
                هر تغییر وضعیت احراز ثبت می‌شود — چه کسی، توسط چه کسی، IP و زمان.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                <label className="block space-y-1.5">
                  <span className="text-muted-foreground block text-[11px] font-medium">
                    جستجو (شماره موبایل، IP)
                  </span>
                  <Input
                    value={logsSearch}
                    onChange={(e) => {
                      setLogsSearch(e.target.value);
                      resetLogsPage();
                    }}
                    placeholder="مثلاً ۰۹۱۲… یا 185.88…"
                  />
                </label>
                <label className="block space-y-1.5">
                  <span className="text-muted-foreground block text-[11px] font-medium">از تاریخ</span>
                  <JalaliDatePicker
                    value={logsDateFrom}
                    onChange={(value) => {
                      setLogsDateFrom(value);
                      resetLogsPage();
                    }}
                    placeholder="انتخاب تاریخ"
                  />
                </label>
                <label className="block space-y-1.5">
                  <span className="text-muted-foreground block text-[11px] font-medium">تا تاریخ</span>
                  <JalaliDatePicker
                    value={logsDateTo}
                    onChange={(value) => {
                      setLogsDateTo(value);
                      resetLogsPage();
                    }}
                    placeholder="انتخاب تاریخ"
                  />
                </label>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-muted-foreground text-xs">
                  {toPersianDigits(logsTotal)} رکورد مطابق فیلترها
                </span>
                <Button
                  variant="outline"
                  onClick={() => void onExportLogs()}
                  disabled={exportingLogs || logsTotal === 0}
                >
                  {exportingLogs ? (
                    <Loader2 className="me-2 h-4 w-4 animate-spin" />
                  ) : (
                    <FileDown className="me-2 h-4 w-4" />
                  )}
                  خروجی اکسل (CSV)
                </Button>
              </div>
            </CardContent>
          </Card>

          <DataTable
            columns={logColumns}
            rows={logs}
            rowKey={(l) => l.id}
            loading={loadingLogs}
            emptyMessage="هنوز احرازی ثبت نشده است."
            emptyDescription="با احراز اولین کاربر، لاگ‌ها اینجا ظاهر می‌شوند."
            pageSize={LOGS_PAGE_SIZE}
            serverTotal={logsTotal}
            onServerPageChange={(p) => setLogsPage(p)}
            columnVisibilityKey="verification-logs-columns"
            tableLayout="fixed"
          />
        </TabsContent>

        {/* ── Settings ──────────────────────────────────────────────── */}
        <TabsContent value="settings" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-600 dark:text-emerald-400" aria-hidden />
                تنظیمات احراز
              </CardTitle>
              <CardDescription>
                رفتار وضعیت «در حال انجام (احراز شده)» و اعلان تلگرام
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              {config === null ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                  در حال بارگذاری…
                </div>
              ) : (
                <>
                  <div className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="font-medium">فعال بودن وضعیت احراز شده</div>
                      <div className="mt-0.5 text-sm leading-6 text-muted-foreground">
                        اگر خاموش شود، همهٔ سفارش‌ها وارد وضعیت عادی «در حال انجام»
                        می‌شوند.
                      </div>
                    </div>
                    <Switch
                      checked={config.enabled}
                      disabled={savingConfig}
                      onCheckedChange={(v) => void saveConfig({ enabled: v })}
                      aria-label="فعال/غیرفعال کردن وضعیت احراز شده"
                      className="shrink-0 self-start sm:self-center"
                    />
                  </div>
                  <div className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="flex items-center gap-1.5 font-medium">
                        <Send className="h-4 w-4 text-muted-foreground" aria-hidden />
                        اعلان تلگرام
                      </div>
                      <div className="mt-0.5 text-sm leading-6 text-muted-foreground">
                        با هر احراز/لغو احراز، پیام به گروه تلگرام ارسال می‌شود.
                      </div>
                    </div>
                    <Switch
                      checked={config.telegram_notifications}
                      disabled={savingConfig}
                      onCheckedChange={(v) => void saveConfig({ telegram_notifications: v })}
                      aria-label="فعال/غیرفعال کردن اعلان تلگرام"
                      className="shrink-0 self-start sm:self-center"
                    />
                  </div>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium" htmlFor="uv-token">
                        توکن ربات تلگرام
                      </label>
                      <Input
                        id="uv-token"
                        dir="ltr"
                        className="text-start"
                        value={config.telegram_bot_token}
                        onChange={(e) =>
                          setConfig({ ...config, telegram_bot_token: e.target.value })
                        }
                        placeholder="خالی = ربات چت"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium" htmlFor="uv-chat">
                        شناسهٔ گروه (Chat ID)
                      </label>
                      <Input
                        id="uv-chat"
                        dir="ltr"
                        className="text-start"
                        value={config.telegram_chat_id}
                        onChange={(e) =>
                          setConfig({ ...config, telegram_chat_id: e.target.value })
                        }
                        placeholder="خالی = گروه چت"
                      />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <Button
                      disabled={savingConfig}
                      onClick={() =>
                        void saveConfig({
                          telegram_bot_token: config.telegram_bot_token,
                          telegram_chat_id: config.telegram_chat_id,
                        })
                      }
                      className={cn("gap-1.5", savingConfig && "opacity-80")}
                    >
                      {savingConfig && (
                        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
                      )}
                      ذخیره تنظیمات
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
