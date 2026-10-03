"use client";

/**
 * WebAuthn passkey enrollment and login.
 *
 * P1 "کاربران: پاسکی". This hook previously called four endpoints that did
 * not exist (register/verify, login/options, login/verify) and surfaced a
 * 404 as a user-facing error — every call was a stub. The backend now
 * verifies real attestations and assertions against stored public keys, so
 * the hook drives the real ceremony:
 *
 *   register: options → browser prompt → verify (server stores the key)
 *   login:    options → browser prompt → verify (server checks the signature)
 */

import { useState, useCallback, useEffect } from "react";
import { startRegistration, startAuthentication } from "@simplewebauthn/browser";

import apiClient from "@/lib/api/client";

export interface PasskeyCredential {
  id: string;
  credential_id: string;
  name: string | null;
  created_at: string | null;
  last_used_at: string | null;
}

interface UsePasskeyReturn {
  isSupported: boolean;
  isLoading: boolean;
  error: string | null;
  /** Enroll a passkey for the signed-in account. */
  registerPasskey: (name?: string) => Promise<boolean>;
  /** Sign in with a passkey for the given phone. */
  authenticateWithPasskey: (phone: string) => Promise<boolean>;
  /** The account's registered passkeys, for a management list. */
  listCredentials: () => Promise<PasskeyCredential[]>;
  /** Revoke one passkey by its row id. */
  revokeCredential: (id: string) => Promise<boolean>;
}

function errorMessage(err: unknown, fallback: string): string {
  const msg = (
    err as { response?: { data?: { error?: { message?: string }; detail?: string } } }
  )?.response?.data;
  return msg?.error?.message || msg?.detail || fallback;
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

  const registerPasskey = useCallback(
    async (name?: string): Promise<boolean> => {
      if (!isSupported) {
        setError("دستگاه یا مرورگر شما از کلیدهای عبور (Passkey) پشتیبانی نمی‌کند.");
        return false;
      }

      setIsLoading(true);
      setError(null);
      try {
        // 1. Registration options; the server stores the challenge it hands out.
        const { data: options } = await apiClient.post(
          "/auth/mfa/passkey/register/options",
        );

        // 2. Prompt the authenticator (fingerprint, Face ID, security key).
        const attResponse = await startRegistration({ optionsJSON: options });

        // 3. Send the attestation back for verification and storage. The name
        //    is carried alongside so the revocation list is readable.
        await apiClient.post("/auth/mfa/passkey/register/verify", {
          ...attResponse,
          name: name || null,
        });
        return true;
      } catch (err) {
        // A cancelled prompt is not an error worth a red banner; anything
        // else is reported with the server's own message where there is one.
        if ((err as Error)?.name === "NotAllowedError") {
          setError("ثبت کلید عبور لغو شد.");
        } else {
          setError(errorMessage(err, "ثبت کلید عبور ناموفق بود."));
        }
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [isSupported],
  );

  const authenticateWithPasskey = useCallback(
    async (phone: string): Promise<boolean> => {
      if (!isSupported) {
        setError("دستگاه یا مرورگر شما از کلیدهای عبور (Passkey) پشتیبانی نمی‌کند.");
        return false;
      }

      setIsLoading(true);
      setError(null);
      try {
        const { data: options } = await apiClient.post(
          "/auth/mfa/passkey/login/options",
          { phone },
        );
        const assertion = await startAuthentication({ optionsJSON: options });
        await apiClient.post("/auth/mfa/passkey/login/verify", {
          phone,
          credential: assertion,
        });
        return true;
      } catch (err) {
        if ((err as Error)?.name === "NotAllowedError") {
          setError("ورود با کلید عبور لغو شد.");
        } else {
          setError(errorMessage(err, "ورود با کلید عبور ناموفق بود."));
        }
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [isSupported],
  );

  const listCredentials = useCallback(async (): Promise<PasskeyCredential[]> => {
    const { data } = await apiClient.get<PasskeyCredential[]>(
      "/auth/mfa/passkey/credentials",
    );
    return data;
  }, []);

  const revokeCredential = useCallback(async (id: string): Promise<boolean> => {
    try {
      await apiClient.delete(`/auth/mfa/passkey/credentials/${id}`);
      return true;
    } catch (err) {
      setError(errorMessage(err, "حذف کلید عبور ناموفق بود."));
      return false;
    }
  }, []);

  return {
    isSupported,
    isLoading,
    error,
    registerPasskey,
    authenticateWithPasskey,
    listCredentials,
    revokeCredential,
  };
}
