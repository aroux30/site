import apiClient from "./client";

// --- Types ---

export interface UserAddress {
  id: string | number;
  title?: string;
  province: string;
  city: string;
  district?: string | null;
  postal_code: string;
  full_address?: string;
  address_line?: string;
  recipient_name?: string;
  recipient_phone?: string;
  receiver_name?: string;
  phone?: string;
  is_default: boolean;
}

export interface AdminUser {
  id: string | number;
  phone: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  is_active: boolean;
  is_blocked?: boolean;
  is_deleted?: boolean;
  /** The public nickname, when set. */
  display_name?: string | null;
  /** True while the account waits for an operator's approval. */
  pending_approval?: boolean;
  created_at: string;
  last_login?: string;
}

/** One live session on an account, as the admin panel sees it. Note there is
 *  no `is_current`: an operator is never signed in as the account they are
 *  looking at, so every row here belongs to somebody else. */
export interface AdminUserSession {
  id: string;
  ip_address: string | null;
  user_agent: string | null;
  device_info: string | null;
  created_at: string | null;
  expires_at: string | null;
  is_revoked: boolean;
}

/** An account's API credential, as an operator sees it. No secret material:
 *  the server's admin response model has no field for the hash or the
 *  one-time plaintext, so nothing here could render one. */
export interface AdminApplicationPassword {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  is_active: boolean;
  last_used_at: string | null;
  last_used_ip: string | null;
  expires_at: string | null;
  revoked_at: string | null;
  created_at: string | null;
}

export interface TrustProfile {
  user_id: string | number;
  shahkar_verified: boolean;
  bank_card_verified?: boolean;
  trust_level?: "none" | "basic" | "verified" | "trusted";
  delivery_policy?: string;
  is_trusted?: boolean;
  risk_score?: number;
  delayed_delivery_enabled?: boolean;
}

export interface BankCard {
  id: string | number;
  card_number_masked?: string;
  card_pan_masked?: string;
  iban?: string;
  holder_name?: string;
  bank_name?: string;
  is_verified: boolean;
  created_at: string;
}

// --- API (user) ---

export const usersApi = {
  // --- Addresses ---

  listAddresses: async (): Promise<UserAddress[]> => {
    const res = await apiClient.get<UserAddress[] | { items: UserAddress[] }>("/users/me/addresses");
    const raw = res.data;
    const items = Array.isArray(raw) ? raw : (raw as { items?: UserAddress[] })?.items ?? [];
    return items.map((a) => ({
      ...a,
      address_line: a.address_line || a.full_address || "",
      full_address: a.full_address || a.address_line || "",
    }));
  },

  createAddress: async (
    data: Omit<UserAddress, "id" | "is_default"> & {
      title?: string;
      full_address?: string;
      address_line?: string;
      is_default?: boolean;
    },
  ): Promise<UserAddress> => {
    const payload = {
      title: data.title || "آدرس من",
      province: data.province,
      city: data.city,
      district: data.district || null,
      postal_code: data.postal_code,
      full_address: data.full_address || data.address_line || "",
      is_default: data.is_default ?? false,
    };
    const res = await apiClient.post<UserAddress>("/users/me/addresses", payload);
    return res.data;
  },

  updateAddress: async (
    addressId: string | number,
    data: Partial<UserAddress>,
  ): Promise<UserAddress> => {
    const payload: Record<string, unknown> = { ...data };
    if (data.address_line && !data.full_address) {
      payload.full_address = data.address_line;
    }
    const res = await apiClient.patch<UserAddress>(`/users/me/addresses/${addressId}`, payload);
    return res.data;
  },

  deleteAddress: async (addressId: string | number): Promise<void> => {
    await apiClient.delete(`/users/me/addresses/${addressId}`);
  },

  // --- KYC ---

  verifyShahkar: async (data: {
    national_id?: string;
    national_code?: string;
    phone?: string;
    mobile?: string;
  }): Promise<{ verified: boolean; message: string }> => {
    const res = await apiClient.post<{ verified: boolean; message: string }>(
      "/users/kyc/shahkar/verify",
      {
        national_code: data.national_code || data.national_id || "",
        mobile: data.mobile || data.phone,
      },
    );
    return res.data;
  },

  getTrustProfile: async (): Promise<TrustProfile> => {
    const res = await apiClient.get<TrustProfile>("/users/kyc/trust-profile");
    return res.data;
  },

  registerBankCard: async (data: {
    card_number: string;
    iban?: string;
  }): Promise<BankCard> => {
    const res = await apiClient.post<BankCard>("/users/kyc/bank-cards", data);
    return res.data;
  },

  listBankCards: async (): Promise<BankCard[]> => {
    const res = await apiClient.get<BankCard[] | { items: BankCard[] }>("/users/kyc/bank-cards");
    const raw = res.data;
    const items = Array.isArray(raw) ? raw : (raw as { items?: BankCard[] })?.items ?? [];
    return items.map((c) => ({
      ...c,
      card_number_masked: c.card_number_masked || c.card_pan_masked || "",
    }));
  },

  verifyCardMatch: async (data: {
    card_number?: string;
    payment_card_pan?: string;
    national_id?: string;
  }): Promise<{ matched: boolean; message: string }> => {
    const res = await apiClient.post<{ matched: boolean; message: string }>(
      "/users/kyc/bank-cards/verify-match",
      {
        payment_card_pan: data.payment_card_pan || data.card_number || "",
      },
    );
    return res.data;
  },

  getDeliveryPolicy: async (): Promise<{ policy: string; restrictions: string[] }> => {
    const res = await apiClient.get<{ policy: string; restrictions: string[] }>(
      "/users/kyc/delivery-policy",
    );
    return res.data;
  },
};

// --- API (admin) ---

export const usersAdminApi = {
  listUsers: async (params?: {
    page?: number;
    page_size?: number;
    search?: string;
    is_active?: boolean;
    /** Server-side role filter, by slug. Absent means every role. */
    role?: string;
    /** Include soft-deleted accounts — the restore view. */
    include_deleted?: boolean;
  }): Promise<{ items: AdminUser[]; total: number }> => {
    const res = await apiClient.get<{ items: AdminUser[]; total: number }>("/users/admin/users", { params });
    return res.data;
  },

  getUser: async (userId: string | number): Promise<AdminUser> => {
    const res = await apiClient.get<AdminUser>(`/users/admin/users/${userId}`);
    return res.data;
  },

  createUser: async (data: {
    phone: string;
    email?: string;
    first_name?: string;
    last_name?: string;
    password: string;
    /** Roles to grant at creation, by slug. The server assigns them in the
     *  same transaction, so a staff account is born with its role rather than
     *  as a customer that must then be fixed. */
    role_slugs?: string[];
  }): Promise<AdminUser> => {
    const res = await apiClient.post<AdminUser>("/users/admin/users", data);
    return res.data;
  },

  updateUser: async (userId: string | number, data: Partial<AdminUser>): Promise<AdminUser> => {
    const res = await apiClient.patch<AdminUser>(`/users/admin/users/${userId}`, data);
    return res.data;
  },

  blockUser: async (userId: string | number, reason?: string): Promise<void> => {
    await apiClient.post(`/users/admin/users/${userId}/block`, { reason });
  },

  unblockUser: async (userId: string | number): Promise<void> => {
    await apiClient.post(`/users/admin/users/${userId}/unblock`);
  },

  /**
   * Soft-delete a user, optionally handing their authored content to a successor.
   *
   * `reassign_to` is a query parameter, not a body: the route is a DELETE, and
   * FastAPI will not read a JSON body off one. The response is the reassignment
   * report rather than a 204, because the outcome the operator cannot see — seven
   * columns null out — is the one that matters.
   */
  deleteUser: async (
    userId: string | number,
    options?: { reassign_to?: string },
  ): Promise<{ owned_before: Record<string, number>; reassigned: Record<string, number>; summary: string }> => {
    const res = await apiClient.delete<{
      owned_before: Record<string, number>;
      reassigned: Record<string, number>;
      summary: string;
    }>(`/users/admin/users/${userId}`, { params: options });
    return res.data;
  },

  /**
   * What a user owns, before anyone decides who inherits it.
   *
   * A read: an operator asking what a delete would cost must not change
   * anything by asking.
   */
  previewReassignment: async (userId: string | number): Promise<{
    owned: Record<string, number>;
    total: number;
    summary: string;
  }> => {
    const res = await apiClient.get<{
      owned: Record<string, number>;
      total: number;
      summary: string;
    }>(`/users/admin/users/${userId}/reassign-content`);
    return res.data;
  },

  /**
   * Email a password-reset link to a user, at an operator's request.
   *
   * Returns the server's answer rather than `void`, because the server has one
   * worth having: an account with no address or no password to reset gets
   * `sent: false`, and an operator who saw a plain success would go on watching
   * an inbox for a message that was never written.
   */
  sendPasswordReset: async (userId: string | number): Promise<{ sent: boolean; detail: string }> => {
    const res = await apiClient.post<{ sent: boolean; detail: string }>(
      `/users/admin/users/${userId}/password-reset`,
    );
    return res.data;
  },

  restoreUser: async (userId: string | number): Promise<void> => {
    await apiClient.post(`/users/admin/users/${userId}/restore`);
  },

  /** Admit an account held by `registration_approval_required`. */
  approveUser: async (userId: string | number): Promise<void> => {
    await apiClient.post(`/users/admin/users/${userId}/approve`);
  },

  /** Refuse a pending account; reversible via unblock. */
  rejectUser: async (userId: string | number): Promise<void> => {
    await apiClient.post(`/users/admin/users/${userId}/reject`);
  },

  /** Every live session an account holds, for an operator to review or cut. */
  listUserSessions: async (userId: string | number): Promise<AdminUserSession[]> => {
    const res = await apiClient.get<AdminUserSession[]>(
      `/users/admin/users/${userId}/sessions`,
    );
    return res.data;
  },

  revokeUserSession: async (
    userId: string | number,
    sessionId: string,
  ): Promise<void> => {
    await apiClient.delete(`/users/admin/users/${userId}/sessions/${sessionId}`);
  },

  /**
   * A target account's application passwords (API credentials).
   *
   * Metadata only — the server never returns secret material, so there is no
   * token field to render even if a page tried.
   */
  listUserApplicationPasswords: async (
    userId: string | number,
  ): Promise<AdminApplicationPassword[]> => {
    const res = await apiClient.get<AdminApplicationPassword[]>(
      `/users/admin/users/${userId}/application-passwords`,
    );
    return res.data;
  },

  /** Revoke one credential on a target account, at an operator's request. */
  revokeUserApplicationPassword: async (
    userId: string | number,
    appPasswordId: string,
  ): Promise<AdminApplicationPassword> => {
    const res = await apiClient.delete<AdminApplicationPassword>(
      `/users/admin/users/${userId}/application-passwords/${appPasswordId}`,
    );
    return res.data;
  },

  /**
   * One action over many accounts.
   *
   * Returns the per-account outcomes rather than a bare success, because the
   * guards still run per account: an operator who selected twenty accounts and
   * cannot touch three of them (self, a superuser, the last admin) must see
   * "17 done, 3 refused", not "20 done".
   */
  bulkUsers: async (
    action: "block" | "unblock" | "delete" | "restore" | "set_role",
    ids: Array<string | number>,
    options?: { role_slug?: string },
  ): Promise<{
    action: string;
    ok: number;
    failed: number;
    total: number;
    results: Array<{ id: string; ok: boolean; error: string | null }>;
  }> => {
    const res = await apiClient.post(`/users/admin/users/bulk`, {
      action,
      ids,
      ...options,
    });
    return res.data;
  },

  listFailedAttempts: async (params?: {
    page?: number;
  }): Promise<{ items: Array<Record<string, unknown>>; total: number }> => {
    const res = await apiClient.get<{ items: Array<Record<string, unknown>>; total: number }>(
      "/users/admin/security/failed-attempts",
      { params },
    );
    return res.data;
  },

  listTrustProfiles: async (params?: {
    page?: number;
  }): Promise<{ items: TrustProfile[]; total: number }> => {
    const res = await apiClient.get<{ items: TrustProfile[]; total: number }>(
      "/users/admin/kyc/trust-profiles",
      { params },
    );
    return res.data;
  },
};
