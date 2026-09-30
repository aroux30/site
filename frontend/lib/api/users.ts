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
  created_at: string;
  last_login?: string;
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

  deleteUser: async (userId: string | number): Promise<void> => {
    await apiClient.delete(`/users/admin/users/${userId}`);
  },

  restoreUser: async (userId: string | number): Promise<void> => {
    await apiClient.post(`/users/admin/users/${userId}/restore`);
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
