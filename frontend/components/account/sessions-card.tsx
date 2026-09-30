"use client";

import { useState } from "react";

import { authApi, type AuthSession } from "@/lib/api/auth";
import { useAdminQuery } from "@/lib/api/admin-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const SESSIONS_QUERY_KEY = "account-sessions" as const;

/**
 * "Where am I signed in" — list every live session and let one be revoked.
 *
 * The endpoints and the typed client both existed and nothing in the UI called
 * them, so a customer who suspected someone else had their account had no way
 * to see it or cut it off — only the coarse "log out everywhere", which they
 * would have had to run on every suspicion, including their own phone.
 */
export function SessionsCard() {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    data: sessions,
    loading,
    error: loadError,
    reload,
  } = useAdminQuery<AuthSession[]>({
    queryKey: [SESSIONS_QUERY_KEY],
    queryFn: () => authApi.listSessions(),
    fallbackError: "دریافت فهرست نشست‌ها ناموفق بود",
  });

  const rows = sessions ?? [];

  async function revoke(session: AuthSession): Promise<void> {
    // Guard the one session the user is looking at: revoking it signs them
    // out of the tab they are reading this in, which reads as a bug rather
    // than a success.
    if (session.is_current) return;
    setBusyId(session.id);
    setError(null);
    try {
      await authApi.deleteSession(session.id);
      await reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "پایان دادن به این نشست ناموفق بود.",
      );
    } finally {
      setBusyId(null);
    }
  }

  async function revokeAllOthers(): Promise<void> {
    const others = rows.filter((s) => !s.is_current);
    if (others.length === 0) return;
    setError(null);
    try {
      for (const s of others) {
        await authApi.deleteSession(s.id);
      }
      await reload();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "پایان دادن به سایر نشست‌ها ناموفق بود.",
      );
    }
  }

  const otherCount = rows.filter((s) => !s.is_current).length;

  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">نشست‌های فعال</h3>
          <p className="mt-0.5 text-[11px] text-muted-foreground">
            هر دستگاهی که با حساب شما وارد شده باشد.
          </p>
        </div>
        {otherCount > 0 && (
          <Button
            size="sm"
            variant="outline"
            onClick={() => void revokeAllOthers()}
            disabled={loading}
          >
            پایان دادن به سایر نشست‌ها ({otherCount.toLocaleString("fa-IR")})
          </Button>
        )}
      </div>

      {error && (
        <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      {loadError ? (
        <p className="text-xs text-destructive">{loadError}</p>
      ) : loading ? (
        <p className="text-xs text-muted-foreground">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <p className="text-xs text-muted-foreground">نشست فعالی یافت نشد.</p>
      ) : (
        <ul className="divide-y divide-border">
          {rows.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between gap-3 py-2.5"
            >
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm" dir="auto">
                    {describeAgent(s.user_agent)}
                  </span>
                  {s.is_current && (
                    <Badge variant="secondary" className="shrink-0">
                      همین دستگاه
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
                className="shrink-0"
                disabled={s.is_current || busyId === s.id}
                onClick={() => void revoke(s)}
                title={
                  s.is_current
                    ? "نشست همین دستگاه قابل پایان دادن نیست"
                    : "پایان دادن به این نشست"
                }
              >
                {busyId === s.id ? "در حال انجام…" : "پایان دادن"}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
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
