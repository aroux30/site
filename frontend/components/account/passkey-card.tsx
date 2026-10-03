"use client";

/**
 * Manage passkeys (WebAuthn credentials) for the signed-in account.
 *
 * P1 "کاربران: پاسکی". The backend had a challenge generator and the frontend
 * hook called four endpoints that did not exist — every call 404'd. Both sides
 * are now real: this card is the consumer the hook was missing, and the server
 * verifies attestations and assertions against stored public keys.
 *
 * Registration is one tap (the authenticator does the work); revocation lists
 * each credential so a lost device can be cut off without disabling the rest.
 */

import { useCallback, useEffect, useState } from "react";
import { Fingerprint, KeyRound, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { usePasskey, type PasskeyCredential } from "@/hooks/use-passkey";

export function PasskeyCard() {
  const { toast } = useToast();
  const {
    isSupported,
    isLoading,
    registerPasskey,
    listCredentials,
    revokeCredential,
  } = usePasskey();

  const [credentials, setCredentials] = useState<PasskeyCredential[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setCredentials(await listCredentials());
    } catch {
      // An unreadable list must not render as "no passkeys": those are
      // different facts and the user would re-register a device they hold.
      setLoadError("دریافت فهرست کلیدهای عبور ناموفق بود.");
    } finally {
      setLoading(false);
    }
  }, [listCredentials]);

  useEffect(() => {
    void load();
  }, [load]);

  async function add() {
    const ok = await registerPasskey(name.trim() || undefined);
    if (ok) {
      toast({
        title: "کلید عبور ثبت شد",
        description: "از این پس می‌توانید بدون رمز عبور با این دستگاه وارد شوید.",
        variant: "success",
      });
      setName("");
      await load();
    } else {
      // The hook holds the reason; surface it rather than a generic failure.
      toast({
        title: "ثبت کلید عبور ناموفق بود",
        description: "دوباره تلاش کنید یا از رمز عبور استفاده کنید.",
        variant: "destructive",
      });
    }
  }

  async function remove(id: string) {
    setRevokingId(id);
    try {
      const ok = await revokeCredential(id);
      if (ok) {
        toast({ title: "کلید عبور حذف شد", variant: "success" });
        await load();
      } else {
        toast({ title: "حذف کلید عبور ناموفق بود", variant: "destructive" });
      }
    } finally {
      setRevokingId(null);
    }
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-center gap-2">
        <Fingerprint className="h-5 w-5 text-primary" />
        <h3 className="text-sm font-bold text-foreground">کلید عبور (Passkey)</h3>
        {credentials.length > 0 && (
          <span className="ms-auto rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-600">
            {credentials.length.toLocaleString("fa-IR")} کلید
          </span>
        )}
      </div>

      {!isSupported ? (
        <p className="text-xs text-muted-foreground leading-relaxed">
          مرورگر یا دستگاه شما از کلید عبور پشتیبانی نمی‌کند. با دستگاه یا مرورگر
          جدیدتر می‌توانید بدون رمز عبور وارد شوید.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground leading-relaxed">
            با کلید عبور، به‌جای رمز عبور با اثر انگشت، چهره یا کلید امنیتی وارد
            می‌شوید. کلید خصوصی روی دستگاه شما می‌ماند و به سرور فرستاده نمی‌شود.
          </p>

          {loadError && (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {loadError}
            </p>
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              در حال بارگذاری...
            </div>
          ) : credentials.length > 0 ? (
            <ul className="divide-y divide-border/60">
              {credentials.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm">{c.name || "کلید بدون نام"}</p>
                    <p className="text-[11px] text-muted-foreground">
                      ثبت: {c.created_at ? new Date(c.created_at).toLocaleDateString("fa-IR") : "—"}
                      {c.last_used_at
                        ? ` · آخرین استفاده: ${new Date(c.last_used_at).toLocaleDateString("fa-IR")}`
                        : " · هنوز استفاده نشده"}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="shrink-0 text-destructive"
                    disabled={revokingId === c.id}
                    onClick={() => void remove(c.id)}
                    title="حذف این کلید عبور"
                  >
                    {revokingId === c.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-xs text-muted-foreground">هنوز کلید عبوری ثبت نشده است.</p>
          )}

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="نام دستگاه (اختیاری) — مثلاً «لپ‌تاپ من»"
              maxLength={100}
              disabled={isLoading}
              className="sm:flex-1"
            />
            <Button size="sm" onClick={() => void add()} disabled={isLoading} className="gap-2">
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <KeyRound className="h-4 w-4" />
              )}
              افزودن کلید عبور
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
