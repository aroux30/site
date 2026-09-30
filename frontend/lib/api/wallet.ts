import apiClient from "./client";

// --- Types ---

export interface Wallet {
  id?: string;
  user_id?: string;
  balance: number;
  currency?: string;
  is_active: boolean;
}

export interface WalletTransaction {
  id: number | string;
  type: "deposit" | "withdraw" | "purchase" | "refund" | "cashback" | "topup" | string;
  amount: number;
  balance_after: number;
  description?: string | null;
  created_at?: string;
  reference_id?: string | null;
}

export interface WalletTransactionsResponse {
  items: WalletTransaction[];
  total: number;
  page?: number;
  page_size?: number;
}

export interface TopupRequest {
  amount: number;
  gateway_provider?: string;
}

export interface TopupResponse {
  id?: string | number;
  payment_id?: string | number;
  gateway_url?: string | null;
  payment_url?: string | null;
  status?: string;
  amount?: number;
}

// --- API ---

export const walletApi = {
  /** دریافت موجودی کیف پول */
  getWallet: async (): Promise<Wallet> => {
    const res = await apiClient.get<Wallet>("/wallet");
    return {
      ...res.data,
      currency: res.data.currency || "تومان",
    };
  },

  /** لیست تراکنش‌های کیف پول */
  getTransactions: async (page = 1, pageSize = 20): Promise<WalletTransactionsResponse> => {
    const res = await apiClient.get<WalletTransactionsResponse>("/wallet/transactions", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },

  /** واریز مستقیم (ادمین) */
  deposit: async (amount: number, description: string): Promise<WalletTransaction> => {
    const res = await apiClient.post<WalletTransaction>("/wallet/deposit", {
      amount: Math.trunc(amount),
      description,
    });
    return res.data;
  },

  /** شارژ کیف پول از درگاه */
  topup: async (data: TopupRequest): Promise<TopupResponse> => {
    const res = await apiClient.post<any>("/wallet/topup", {
      amount: Math.trunc(data.amount),
      gateway_provider: data.gateway_provider,
    });
    const raw = res.data;
    const paymentUrl = raw.gateway_url || raw.payment_url || "";
    return {
      ...raw,
      id: raw.id || raw.payment_id,
      payment_id: raw.payment_id || raw.id,
      gateway_url: paymentUrl,
      payment_url: paymentUrl,
    };
  },

  /** برداشت از کیف پول */
  withdraw: async (amount: number, description?: string): Promise<WalletTransaction> => {
    const res = await apiClient.post<WalletTransaction>("/wallet/withdraw", {
      amount: Math.trunc(amount),
      description,
    });
    return res.data;
  },
};
