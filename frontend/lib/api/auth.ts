import apiClient from "./client";

// --- Types ---

export interface AuthSession {
  id: string;
  ip_address: string;
  user_agent: string;
  is_current: boolean;
  created_at: string;
  last_active_at: string;
}

export interface SecurityStatus {
  has_password: boolean;
  totp_enabled: boolean;
  passkey_count: number;
  active_sessions: number;
  last_password_change?: string;
}

export interface TotpSetupResponse {
  secret: string;
  qr_code_url?: string;
  otpauth_uri?: string;
  backup_codes: string[];
}

export interface CaptchaResponse {
  captcha_id: string;
  image_base64: string;
}

// --- API ---

export const authApi = {
  // --- Session management ---

  /** لاگ‌اوت از همه دستگاه‌ها */
  logoutAll: async (): Promise<void> => {
    await apiClient.post("/auth/logout-all");
  },

  /** تغییر رمز عبور */
  changePassword: async (data: {
    old_password?: string;
    current_password?: string;
    new_password: string;
  }): Promise<{ message: string }> => {
    const res = await apiClient.post<{ message: string }>("/auth/change-password", {
      old_password: data.old_password || data.current_password || "",
      new_password: data.new_password,
    });
    return res.data;
  },

  /** درخواست پیوند بازیابی رمز عبور.
   *  پاسخ سرور برای ایمیل ثبت‌شده و ثبت‌نشده یکسان است. */
  forgotPassword: async (email: string): Promise<{ message: string }> => {
    const res = await apiClient.post<{ message: string }>("/auth/forgot-password", { email });
    return res.data;
  },

  /** بازیابی با توکن و تعیین رمز جدید (همه نشست‌ها باطل می‌شوند). */
  resetPassword: async (data: {
    token: string;
    new_password: string;
  }): Promise<{ message: string }> => {
    const res = await apiClient.post<{ message: string }>("/auth/reset-password", data);
    return res.data;
  },

  /** تأیید ایمیل با توکن پیوند ارسالی (بدون نیاز به ورود). */
  confirmEmailVerification: async (
    token: string,
  ): Promise<{ verified: boolean; email: string }> => {
    const res = await apiClient.post<{ verified: boolean; email: string }>(
      "/auth/me/email/verify",
      { token },
    );
    return res.data;
  },

  /** ارسال دوبارهٔ پیوند تأیید ایمیل برای حساب واردشده. */
  resendEmailVerification: async (): Promise<{ message: string }> => {
    const res = await apiClient.post<{ message: string }>(
      "/auth/me/email/resend-verification",
    );
    return res.data;
  },

  /** لیست نشست‌های فعال */
  listSessions: async (): Promise<AuthSession[]> => {
    const res = await apiClient.get<AuthSession[] | { items: AuthSession[] }>("/auth/sessions");
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: AuthSession[] })?.items ?? [];
  },

  /** حذف یک نشست (لاگ‌اوت از دستگاه خاص) */
  deleteSession: async (sessionId: string): Promise<void> => {
    await apiClient.delete(`/auth/sessions/${sessionId}`);
  },

  /** وضعیت امنیتی حساب */
  getSecurityStatus: async (): Promise<SecurityStatus> => {
    const res = await apiClient.get<SecurityStatus>("/auth/security-status");
    return res.data;
  },

  // --- MFA: TOTP ---

  /** شروع فعال‌سازی TOTP (Google Authenticator) */
  setupTotp: async (): Promise<TotpSetupResponse> => {
    const res = await apiClient.post<TotpSetupResponse>("/auth/mfa/totp/setup");
    return res.data;
  },

  /** تأیید کد TOTP برای فعال‌سازی */
  verifyTotp: async (code: string): Promise<{ verified: boolean }> => {
    const res = await apiClient.post<{ verified: boolean }>("/auth/mfa/totp/verify", { code });
    return res.data;
  },

  /** غیرفعال‌سازی TOTP */
  disableTotp: async (code: string, password = ""): Promise<void> => {
    await apiClient.post("/auth/mfa/totp/disable", { code, password });
  },

  // --- Captcha ---

  /** دریافت تصویر کپچا */
  getCaptcha: async (): Promise<CaptchaResponse> => {
    const res = await apiClient.get<CaptchaResponse>("/auth/captcha/generate");
    return res.data;
  },

  /** بررسی پاسخ کپچا */
  verifyCaptcha: async (captchaId: string, answer: string): Promise<{ valid: boolean }> => {
    const res = await apiClient.post<{ valid: boolean }>("/auth/captcha/verify", {
      captcha_id: captchaId,
      answer,
    });
    return res.data;
  },
};

/* ── Application passwords (WordPress parity) ───────────────────────────────
 * A personal API client (phone app, script) authenticates with one of these
 * instead of the account password. The token is shown exactly once — only its
 * hash is stored — so the UI must warn before discarding it. */

export interface ApplicationPassword {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  is_active: boolean;
  last_used_at?: string | null;
  last_used_ip?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  created_at?: string | null;
}

export interface ApplicationPasswordCreated extends ApplicationPassword {
  token: string;
}

export const applicationPasswordsApi = {
  list: async (): Promise<ApplicationPassword[]> => {
    const { data } = await apiClient.get<ApplicationPassword[]>("/auth/application-passwords");
    return Array.isArray(data) ? data : [];
  },

  create: async (data: {
    name: string;
    scopes?: string[];
    expires_in_days?: number | null;
  }): Promise<ApplicationPasswordCreated> => {
    const { data: res } = await apiClient.post<ApplicationPasswordCreated>(
      "/auth/application-passwords",
      data,
    );
    return res;
  },

  revoke: async (id: string): Promise<ApplicationPassword> => {
    const { data } = await apiClient.delete<ApplicationPassword>(
      `/auth/application-passwords/${id}`,
    );
    return data;
  },

  revokeAll: async (): Promise<{ revoked: number }> => {
    const { data } = await apiClient.post<{ revoked: number }>(
      "/auth/application-passwords/revoke-all",
    );
    return data;
  },
};
