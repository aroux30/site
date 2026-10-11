import apiClient from "./client";

// --- Types ---
//
// Every amount at this boundary is an integer **Rial** (the backend stores and
// transports Rial per ADR-012). Convert to Toman at the presentation layer
// with `Math.trunc(rial / 10)` before calling formatPrice — never here.

export interface WalletFeatures {
  /** Master switch — when false the whole wallet surface is hidden. */
  enabled: boolean;
  deposit: boolean;
  withdraw: boolean;
  transfer: boolean;
}

export interface Wallet {
  id?: string;
  user_id?: string;
  balance: number;
  is_active: boolean;
  /** Which capabilities are enabled; a missing field means enabled. */
  features?: WalletFeatures;
}

export type WalletTransactionType =
  | "credit"
  | "debit"
  | "refund"
  | "cashback"
  | "bonus"
  | "withdrawal"
  | "adjustment"
  | "transfer_out"
  | "transfer_in"
  | "withdrawal_hold"
  | "withdrawal_reversal";

export interface WalletTransaction {
  id: string;
  wallet_id?: string;
  type: WalletTransactionType;
  /** Signed Rial: positive is a credit, negative a debit. */
  amount: number;
  balance_after: number;
  reference_type?: string | null;
  reference_id?: string | null;
  description?: string | null;
  created_at: string;
}

export interface WalletTransactionsResponse {
  items: WalletTransaction[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface TopupRequest {
  /** Rial amount. The backend expects Rial, not Toman. */
  amount: number;
  provider?: string;
  idempotency_key?: string;
}

export interface TopupResponse {
  id?: string | number;
  payment_id?: string | number;
  gateway_url?: string | null;
  payment_url?: string | null;
  status?: string;
  amount?: number;
}

export interface TransferRequest {
  /** Recipient's Iranian mobile number (normalized server-side). */
  recipient_phone: string;
  /** Rial amount. */
  amount: number;
  note?: string;
  idempotency_key?: string;
}

export interface WalletTransfer {
  id: string;
  from_user_id: string;
  to_user_id: string;
  amount: number;
  fee: number;
  journal_entry_id?: string | null;
  note?: string | null;
  created_at: string;
}

export type WithdrawalStatus = "pending_review" | "approved" | "rejected" | "paid";

export interface WalletWithdrawal {
  id: string;
  user_id: string;
  amount: number;
  status: WithdrawalStatus;
  iban?: string | null;
  card_number?: string | null;
  account_holder_name?: string | null;
  reviewed_at?: string | null;
  admin_notes?: string | null;
  payout_reference?: string | null;
  paid_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface WithdrawalCreateRequest {
  /** Rial amount. */
  amount: number;
  iban?: string;
  card_number?: string;
  account_holder_name?: string;
  idempotency_key?: string;
}

export interface WalletWithdrawalList {
  items: WalletWithdrawal[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

// --- API ---

export const walletApi = {
  /** دریافت موجودی کیف پول */
  getWallet: async (): Promise<Wallet> => {
    const res = await apiClient.get<Wallet>("/wallet");
    return res.data;
  },

  /** لیست تراکنش‌های کیف پول */
  getTransactions: async (page = 1, pageSize = 20): Promise<WalletTransactionsResponse> => {
    const res = await apiClient.get<WalletTransactionsResponse>("/wallet/transactions", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },

  /** واریز مستقیم (فقط محیط توسعه؛ در تولید ۴۰۳ می‌شود) */
  deposit: async (amount: number): Promise<WalletTransaction> => {
    const res = await apiClient.post<WalletTransaction>("/wallet/deposit", {
      amount: Math.trunc(amount),
    });
    return res.data;
  },

  /** شارژ کیف پول از درگاه پرداخت. مقدار به ریال است. */
  topup: async (data: TopupRequest): Promise<TopupResponse> => {
    const res = await apiClient.post<TopupResponse>("/wallet/topup", {
      amount: Math.trunc(data.amount),
      provider: data.provider ?? "zarinpal",
      idempotency_key: data.idempotency_key,
    });
    return res.data;
  },

  /** انتقال به کیف پول کاربر دیگر (بر اساس شماره موبایل). مقدار به ریال است. */
  transfer: async (data: TransferRequest): Promise<WalletTransfer> => {
    const res = await apiClient.post<WalletTransfer>("/wallet/transfer", {
      recipient_phone: data.recipient_phone,
      amount: Math.trunc(data.amount),
      note: data.note,
      idempotency_key: data.idempotency_key,
    });
    return res.data;
  },

  /** ثبت درخواست برداشت. مقدار به ریال است. */
  createWithdrawal: async (data: WithdrawalCreateRequest): Promise<WalletWithdrawal> => {
    const res = await apiClient.post<WalletWithdrawal>("/wallet/withdrawals", {
      amount: Math.trunc(data.amount),
      iban: data.iban,
      card_number: data.card_number,
      account_holder_name: data.account_holder_name,
      idempotency_key: data.idempotency_key,
    });
    return res.data;
  },

  /** لیست درخواست‌های برداشت کاربر */
  listWithdrawals: async (page = 1, pageSize = 20): Promise<WalletWithdrawalList> => {
    const res = await apiClient.get<WalletWithdrawalList>("/wallet/withdrawals", {
      params: { page, page_size: pageSize },
    });
    return res.data;
  },
};
