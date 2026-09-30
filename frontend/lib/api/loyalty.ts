import apiClient from "./client";

// --- Types ---

export interface LoyaltyAccount {
  points_balance: number;
  total_earned: number;
  total_redeemed: number;
  tier: string;
  tier_progress?: number;
}

export interface LoyaltyTransaction {
  id?: number | string;
  transaction_id?: string;
  type?: "earn" | "redeem" | "expire" | "adjustment" | string;
  points?: number;
  points_changed?: number;
  balance_after?: number;
  new_balance?: number;
  description?: string;
  order_id?: number | string;
  created_at?: string;
}

export interface LoyaltyTier {
  name: string;
  min_points: number;
  multiplier: number;
  benefits: string[];
}

// --- API ---

export const loyaltyApi = {
  /** دریافت حساب وفاداری */
  getAccount: async (): Promise<LoyaltyAccount> => {
    const res = await apiClient.get<LoyaltyAccount>("/loyalty");
    return res.data;
  },

  /** تاریخچه تراکنش‌های امتیاز */
  getTransactions: async (page = 1, pageSize = 20): Promise<{ items: LoyaltyTransaction[]; total: number }> => {
    const skip = Math.max(0, (page - 1) * pageSize);
    const res = await apiClient.get<{ items: LoyaltyTransaction[]; total: number }>(
      "/loyalty/transactions",
      { params: { skip, limit: pageSize, page, page_size: pageSize } },
    );
    return res.data;
  },

  /** کسب امتیاز (فراخوانی معمولاً از سمت بک‌اند بعد از خرید — ادمین) */
  earnPoints: async (data: {
    user_id: number;
    points: number;
    description: string;
    order_id?: number;
  }): Promise<LoyaltyTransaction> => {
    const res = await apiClient.post<LoyaltyTransaction>("/loyalty/earn", data);
    return res.data;
  },

  /** استفاده از امتیاز */
  redeemPoints: async (points: number, description?: string): Promise<LoyaltyTransaction> => {
    const res = await apiClient.post<LoyaltyTransaction>("/loyalty/redeem", {
      points,
      description,
    });
    return res.data;
  },

  /** سطوح وفاداری */
  getTiers: async (): Promise<LoyaltyTier[]> => {
    const res = await apiClient.get<LoyaltyTier[] | { items: LoyaltyTier[] }>("/loyalty/tiers");
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: LoyaltyTier[] })?.items ?? [];
  },
};
