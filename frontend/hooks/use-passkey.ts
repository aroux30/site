"use client";

import { useState, useCallback, useEffect } from "react";
import { startRegistration, startAuthentication } from "@simplewebauthn/browser";

interface UsePasskeyReturn {
  isSupported: boolean;
  isLoading: boolean;
  error: string | null;
  registerPasskey: () => Promise<boolean>;
  authenticateWithPasskey: () => Promise<boolean>;
}

export function usePasskey(): UsePasskeyReturn {
  const [isSupported, setIsSupported] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined" && window.PublicKeyCredential) {
      setIsSupported(true);
    }
  }, []);

  const registerPasskey = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setError("دستگاه یا مرورگر شما از کلیدهای عبور (Passkey) پشتیبانی نمی‌کند.");
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch registration options challenge from backend
      const optionsRes = await fetch("/api/v1/auth/mfa/passkey/register/options", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!optionsRes.ok) {
        throw new Error("خطا در دریافت تنظیمات رجیستریشن از سرور");
      }

      const options = await optionsRes.json();

      // 2. Prompt browser authenticator (Fingerprint, Face ID, YubiKey)
      const regResponse = await startRegistration({ optionsJSON: options });

      // 3. Send response back for cryptographic verification
      const verifyRes = await fetch("/api/v1/auth/mfa/passkey/register/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(regResponse),
      });

      if (!verifyRes.ok) {
        throw new Error("تایید امنیتی کلید عبور با خطا مواجه شد.");
      }

      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "خطای ناشناخته در ثبت کلید عبور";
      setError(msg);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported]);

  const authenticateWithPasskey = useCallback(async (): Promise<boolean> => {
    if (!isSupported) {
      setError("دستگاه یا مرورگر شما از کلیدهای عبور پشتیبانی نمی‌کند.");
      return false;
    }

    setIsLoading(true);
    setError(null);

    try {
      const optionsRes = await fetch("/api/v1/auth/mfa/passkey/login/options", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!optionsRes.ok) {
        throw new Error("خطا در برقراری ارتباط برای ورود با کلید عبور");
      }

      const options = await optionsRes.json();
      const authResponse = await startAuthentication({ optionsJSON: options });

      const verifyRes = await fetch("/api/v1/auth/mfa/passkey/login/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(authResponse),
      });

      if (!verifyRes.ok) {
        throw new Error("احراز هویت بیومتریک ناموفق بود.");
      }

      return true;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "خطا در احراز هویت با کلید عبور";
      setError(msg);
      return false;
    } finally {
      setIsLoading(false);
    }
  }, [isSupported]);

  return {
    isSupported,
    isLoading,
    error,
    registerPasskey,
    authenticateWithPasskey,
  };
}
