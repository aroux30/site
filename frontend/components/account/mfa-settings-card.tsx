"use client";

import { useState } from "react";
import { ShieldCheck, ShieldOff, Loader2, KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";

interface MfaSetupResult {
  secret: string;
  otpauth_uri: string;
}

/**
 * TOTP MFA management card: shows the current status and exposes the
 * server-backed enroll / disable flows. The secret only gates logins after
 * a successful code confirmation on the backend.
 */
export function MfaSettingsCard({
  enabled,
  onChanged,
}: {
  enabled: boolean;
  onChanged: () => void;
}) {
  const { toast } = useToast();
  const [busy, setBusy] = useState(false);
  const [setup, setSetup] = useState<MfaSetupResult | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirming, setConfirming] = useState(false);

  const startSetup = async () => {
    setBusy(true);
    try {
      const res = await apiClient.post<MfaSetupResult>("/auth/mfa/totp/setup");
      setSetup(res.data);
      setCode("");
    } catch {
      toast({
        title: "خطا در شروع راه‌اندازی",
        description: "لطفاً دوباره تلاش کنید.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    if (!/^\d{6}$/.test(code.trim())) {
      toast({
        title: "کد نامعتبر",
        description: "کد ۶ رقمی اپلیکیشن احراز هویت را وارد کنید.",
        variant: "destructive",
      });
      return;
    }
    setConfirming(true);
    try {
      await apiClient.post("/auth/mfa/totp/verify", { code: code.trim() });
      toast({
        title: "ورود دو مرحله‌ای فعال شد",
        description: "از این پس هنگام ورود، کد اپلیکیشن احراز هویت لازم است.",
        variant: "success",
      });
      setSetup(null);
      setCode("");
      onChanged();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data
          ?.error?.message || "کد تأیید نشد. دوباره تلاش کنید.";
      toast({ title: "خطا", description: msg, variant: "destructive" });
    } finally {
      setConfirming(false);
    }
  };

  const disable = async () => {
    if (!/^\d{6}$/.test(code.trim()) || !password) {
      toast({
        title: "اطلاعات ناقص",
        description: "کد فعلی و رمز عبور برای غیرفعال‌سازی الزامی است.",
        variant: "destructive",
      });
      return;
    }
    setConfirming(true);
    try {
      await apiClient.post("/auth/mfa/totp/disable", {
        code: code.trim(),
        password,
      });
      toast({
        title: "ورود دو مرحله‌ای غیرفعال شد",
        variant: "success",
      });
      setCode("");
      setPassword("");
      onChanged();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data
          ?.error?.message || "غیرفعال‌سازی انجام نشد.";
      toast({ title: "خطا", description: msg, variant: "destructive" });
    } finally {
      setConfirming(false);
    }
  };

  return (
    <div className="rounded-2xl border border-border bg-card p-5 space-y-4">
      <div className="flex items-center gap-2">
        {enabled ? (
          <ShieldCheck className="h-5 w-5 text-emerald-600" />
        ) : (
          <ShieldOff className="h-5 w-5 text-muted-foreground" />
        )}
        <h3 className="text-sm font-bold text-foreground">ورود دو مرحله‌ای (TOTP)</h3>
        <span
          className={`ms-auto rounded-full px-2 py-0.5 text-[11px] font-semibold ${
            enabled
              ? "bg-emerald-500/10 text-emerald-600"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {enabled ? "فعال" : "غیرفعال"}
        </span>
      </div>

      {!enabled && !setup && (
        <>
          <p className="text-xs text-muted-foreground leading-relaxed">
            با فعال‌سازی ورود دو مرحله‌ای، علاوه بر رمز عبور، کد ۶ رقمی اپلیکیشن احراز هویت
            (Google Authenticator، Authy و…) نیز برای ورود لازم است.
          </p>
          <Button size="sm" onClick={startSetup} disabled={busy} className="gap-2">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
            فعال‌سازی
          </Button>
        </>
      )}

      {setup && !enabled && (
        <div className="space-y-3">
          <div className="rounded-xl bg-muted/40 p-3 space-y-2" dir="ltr">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Secret (manual entry)
            </div>
            <code className="block break-all font-mono text-xs">{setup.secret}</code>
            <div className="pt-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              otpauth URI
            </div>
            <code className="block break-all font-mono text-[10px] text-muted-foreground">
              {setup.otpauth_uri}
            </code>
          </div>
          <p className="text-xs text-muted-foreground">
            این کلید را در اپلیکیشن احراز هویت ثبت کنید، سپس کد ۶ رقمی فعلی را وارد نمایید.
          </p>
          <div className="space-y-2">
            <Label htmlFor="mfa-code" className="text-xs font-medium">
              کد ۶ رقمی
            </Label>
            <Input
              id="mfa-code"
              dir="ltr"
              inputMode="numeric"
              maxLength={6}
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className="text-center font-mono text-lg tracking-[0.4em]"
            />
          </div>
          <div className="flex gap-2">
            <Button size="sm" onClick={confirm} disabled={confirming} className="gap-2">
              {confirming && <Loader2 className="h-4 w-4 animate-spin" />}
              تأیید و فعال‌سازی
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                setSetup(null);
                setCode("");
              }}
            >
              انصراف
            </Button>
          </div>
        </div>
      )}

      {enabled && (
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            برای غیرفعال‌سازی، کد فعلی اپلیکیشن و رمز عبور خود را وارد کنید.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="mfa-disable-code" className="text-xs font-medium">
                کد فعلی
              </Label>
              <Input
                id="mfa-disable-code"
                dir="ltr"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                className="text-center font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="mfa-disable-password" className="text-xs font-medium">
                رمز عبور
              </Label>
              <Input
                id="mfa-disable-password"
                type="password"
                dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
            </div>
          </div>
          <Button
            size="sm"
            variant="destructive"
            onClick={disable}
            disabled={confirming}
            className="gap-2"
          >
            {confirming && <Loader2 className="h-4 w-4 animate-spin" />}
            غیرفعال‌سازی
          </Button>
        </div>
      )}
    </div>
  );
}
