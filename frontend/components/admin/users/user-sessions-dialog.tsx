"use client";

/**
 * What can access an account, for an operator to cut off.
 *
 * Two surfaces with one question behind them — "this customer says somebody
 * else is in their account":
 *
 * * **sessions** (P1 "کاربران: مدیریت نشست‌های دیگر کاربران از پنل") — the
 *   self-service "where am I signed in" card existed; an operator could
 *   neither see the sessions nor end any of them.
 * * **application passwords** (P2 "REST: مدیریت Application Password کاربر
 *   دیگر") — the same gap for API credentials. A leaked token used to end
 *   with "ask the user to revoke it themselves", which is the thing the
 *   customer is reporting they cannot do.
 *
 * Both sections refetch after a revoke rather than dropping the row locally:
 * a session or credential that vanishes from the server's list is the only
 * proof it actually ended. The credentials section renders metadata only —
 * the server never returns secret material, so there is none to show.
 */

import { useCallback, useEffect, useState } from "react";
import { KeyRound, Loader2, LogOut } from "lucide-react";

import {
  usersAdminApi,
  type AdminApplicationPassword,
  type AdminUser,
  type AdminUserSession,
} from "@/lib/api/users";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Props {
  /** The account whose access to show. null closes the dialog. */
  user: AdminUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UserSessionsDialog({ user, open, onOpenChange }: Props) {
  const [sessions, setSessions] = useState<AdminUserSession[]>([]);
  const [appPasswords, setAppPasswords] = useState<AdminApplicationPassword[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [appBusyId, setAppBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      // Both reads in parallel; a failure of one must not blank the other.
      const [sessionRows, appRows] = await Promise.all([
        usersAdminApi.listUserSessions(user.id),
        usersAdminApi.listUserApplicationPasswords(user.id),
      ]);
      setSessions(sessionRows);
      setAppPasswords(appRows);
    } catch {
      // An unreadable list must not render as "nothing here": those are
      // different facts and an operator would act on the wrong one.
      setError("دریافت اطلاعات دسترسی ناموفق بود.");
      setSessions([]);
      setAppPasswords([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    if (open && user) void load();
  }, [open, user, load]);

  async function revoke(sessionId: string): Promise<void> {
    if (!user) return;
    setBusyId(sessionId);
    setError(null);
    try {
      await usersAdminApi.revokeUserSession(user.id, sessionId);
      // Refetch rather than drop the row locally: the server is the one that
      // knows the session is gone, and a local removal would look identical if
      // the request had silently failed.
      await load();
    } catch {
      setError("پایان دادن به این نشست ناموفق بود.");
    } finally {
      setBusyId(null);
    }
  }

  async function revokeAppPassword(appPasswordId: string): Promise<void> {
    if (!user) return;
    setAppBusyId(appPasswordId);
    setError(null);
    try {
      await usersAdminApi.revokeUserApplicationPassword(user.id, appPasswordId);
      await load();
    } catch {
      setError("لغو رمز برنامه ناموفق بود.");
    } finally {
      setAppBusyId(null);
    }
  }

  const label = user
    ? user.first_name && user.last_name
      ? `${user.first_name} ${user.last_name}`
      : user.phone
    : "";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>دسترسی‌های حساب</DialogTitle>
          <DialogDescription>
            نشست‌های فعال و رمزهای برنامه‌ی حساب «{label}». پایان دادن به یک
            نشست یا لغو یک رمز، بلافاصله همان دسترسی را قطع می‌کند.
          </DialogDescription>
        </DialogHeader>

        {error && (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
            {error}
          </p>
        )}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            در حال بارگذاری نشست‌ها...
          </div>
        ) : sessions.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            نشست فعالی یافت نشد.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {sessions.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-2.5">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm" dir="auto">
                      {describeAgent(s.user_agent)}
                    </span>
                    {s.device_info && (
                      <Badge variant="outline" className="shrink-0 text-[10px]">
                        {s.device_info}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground" dir="ltr">
                    {s.ip_address || "—"} ·{" "}
                    {s.created_at
                      ? new Date(s.created_at).toLocaleString("fa-IR")
                      : "—"}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="shrink-0 text-destructive"
                  disabled={busyId === s.id}
                  onClick={() => void revoke(s.id)}
                  title="پایان دادن به این نشست"
                >
                  {busyId === s.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <>
                      <LogOut className="h-3.5 w-3.5" />
                      <span className="ms-1">پایان دادن</span>
                    </>
                  )}
                </Button>
              </li>
            ))}
          </ul>
        )}

        {!loading && sessions.length > 0 && (
          <p className="text-[11px] text-muted-foreground">
            {toPersianDigits(sessions.length)} نشست فعال.
          </p>
        )}

        {/* API credentials. Metadata only — the server's admin response has
            no field for the secret or its hash, so there is nothing here that
            could leak one. A revoked row stays listed (greyed) so the panel
            tells the whole story rather than looking like it was never made. */}
        {!loading && (
          <div className="border-t border-border pt-3">
            <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              <KeyRound className="h-3.5 w-3.5" />
              رمزهای برنامه (دسترسی API)
              {appPasswords.filter((p) => p.is_active && !p.revoked_at).length > 0 && (
                <Badge variant="secondary" className="text-[10px]">
                  {toPersianDigits(
                    appPasswords.filter((p) => p.is_active && !p.revoked_at).length,
                  )}
                </Badge>
              )}
            </div>
            {appPasswords.length === 0 ? (
              <p className="text-xs text-muted-foreground">
                این حساب رمز برنامه‌ای ندارد.
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {appPasswords.map((p) => {
                  const live = p.is_active && !p.revoked_at;
                  return (
                    <li
                      key={p.id}
                      className="flex items-center justify-between gap-3 py-2.5"
                    >
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm">{p.name}</span>
                          {!live && (
                            <Badge variant="outline" className="shrink-0 text-[10px]">
                              لغو‌شده
                            </Badge>
                          )}
                        </div>
                        <p className="mt-0.5 text-[11px] text-muted-foreground" dir="ltr">
                          {p.token_prefix}… ·{" "}
                          {p.last_used_at
                            ? `آخرین استفاده ${new Date(p.last_used_at).toLocaleDateString("fa-IR")}`
                            : "هنوز استفاده نشده"}
                          {p.expires_at
                            ? ` · انقضا ${new Date(p.expires_at).toLocaleDateString("fa-IR")}`
                            : " · بدون انقضا"}
                        </p>
                      </div>
                      {live && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="shrink-0 text-destructive"
                          disabled={appBusyId === p.id}
                          onClick={() => void revokeAppPassword(p.id)}
                          title="لغو این رمز برنامه"
                        >
                          {appBusyId === p.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <>
                              <KeyRound className="h-3.5 w-3.5" />
                              <span className="ms-1">لغو</span>
                            </>
                          )}
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** A short human label for a user-agent string, never the raw blob. */
function describeAgent(ua: string | null | undefined): string {
  if (!ua) return "دستگاه ناشناس";
  const s = ua.toLowerCase();
  const platform = /android/.test(s)
    ? "Android"
    : /iphone|ipad|ios/.test(s)
      ? "iOS"
      : /windows/.test(s)
        ? "Windows"
        : /mac os|macintosh/.test(s)
          ? "macOS"
          : /linux/.test(s)
            ? "Linux"
            : "دستگاه ناشناس";
  const browser = /edg\//.test(s)
    ? "Edge"
    : /chrome|crios/.test(s)
      ? "Chrome"
      : /firefox|fxios/.test(s)
        ? "Firefox"
        : /safari/.test(s)
          ? "Safari"
          : "";
  return browser ? `${browser} روی ${platform}` : platform;
}
