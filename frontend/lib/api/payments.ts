import apiClient from "./client";

// --- Types ---

export interface PaymentMethod {
  id: string;
  name: string;
  provider: string;
  type: "gateway" | "card_to_card" | "wallet";
  is_active: boolean;
  icon_url?: string;
  min_amount?: number;
  max_amount?: number;
}

export interface Payment {
  id: number | string;
  order_id: number | string;
  amount: number;
  status: "pending" | "processing" | "completed" | "failed" | "refunded" | "expired" | string;
  method?: string;
  provider: string;
  gateway_ref?: string;
  authority?: string;
  payment_url?: string;
  gateway_url?: string;
  created_at: string;
  updated_at: string;
}

export interface CardReceipt {
  id: number | string;
  payment_id?: number | string;
  order_id: number | string;
  card_last_four?: string;
  source_card_last4?: string;
  reference_number?: string;
  tracking_code?: string;
  amount: number;
  image_url?: string;
  receipt_image_url?: string;
  status: "pending" | "approved" | "rejected" | string;
  submitted_at?: string;
  reviewed_at?: string;
  created_at?: string;
}

export interface PaymentGateway {
  provider_key: string;
  name: string;
  is_active: boolean;
  supports_refund: boolean;
}

export interface DirectInvoice {
  id: number;
  amount: number;
  description: string;
  status: "pending" | "paid" | "expired";
  payment_url: string;
  created_at: string;
  expires_at: string;
}

// --- API (user) ---

export const paymentsApi = {
  /** لیست روش‌های پرداخت فعال */
  getMethods: async (): Promise<PaymentMethod[]> => {
    const res = await apiClient.get<{ items: PaymentMethod[] }>("/payments/methods");
    return res.data.items ?? res.data as unknown as PaymentMethod[];
  },

  /** ایجاد پرداخت جدید */
  createPayment: async (orderId: number, method: string, provider?: string): Promise<Payment> => {
    const res = await apiClient.post<Payment>("/payments", {
      order_id: orderId,
      method,
      provider,
    });
    return res.data;
  },

  /** دریافت اطلاعات یک پرداخت */
  getPayment: async (paymentId: number): Promise<Payment> => {
    const res = await apiClient.get<Payment>(`/payments/${paymentId}`);
    return res.data;
  },

  /** دریافت پرداخت کارت‌به‌کارت مرتبط با سفارش */
  getOrderCardTransfer: async (orderId: number): Promise<Payment> => {
    const res = await apiClient.get<Payment>(`/payments/by-order/${orderId}`);
    return res.data;
  },

  /** ارسال رسید کارت‌به‌کارت */
  submitCardReceipt: async (paymentId: number, data: FormData): Promise<CardReceipt> => {
    const res = await apiClient.post<CardReceipt>(
      `/payments/${paymentId}/card-receipt`,
      data,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return res.data;
  },

  /** تأیید پرداخت (بازگشت از درگاه) */
  verifyPayment: async (paymentId: number, queryParams?: Record<string, string>): Promise<Payment> => {
    const res = await apiClient.post<Payment>(`/payments/${paymentId}/verify`, queryParams);
    return res.data;
  },

  /** درخواست استرداد */
  refundPayment: async (paymentId: number | string, amount?: number, reason?: string): Promise<Payment> => {
    const payload = {
      payment_id: String(paymentId),
      amount: amount ?? 0,
      reason: reason || undefined,
    };
    const res = await apiClient.post<Payment>(`/payments/${paymentId}/refund`, payload);
    return res.data;
  },

  // --- Card2Card receipts (fintech) ---

  /** ارسال رسید کارت‌به‌کارت (مسیر فین‌تک) */
  submitFintechReceipt: async (data: FormData): Promise<CardReceipt> => {
    const res = await apiClient.post<CardReceipt>(
      "/payments/fintech/card2card/receipts",
      data,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return res.data;
  },

  /** رسیدهای مرتبط با یک سفارش */
  getOrderReceipts: async (orderId: number): Promise<CardReceipt[]> => {
    const res = await apiClient.get<CardReceipt[] | { items: CardReceipt[] }>(
      `/payments/fintech/card2card/orders/${orderId}/receipts`,
    );
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: CardReceipt[] })?.items ?? [];
  },

  // --- Gateways ---

  /** لیست درگاه‌های پرداخت فعال */
  listGateways: async (): Promise<PaymentGateway[]> => {
    const res = await apiClient.get<PaymentGateway[] | { items: PaymentGateway[] }>("/payments/fintech/gateways");
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: PaymentGateway[] })?.items ?? [];
  },

  // --- Direct invoices ---

  /** ایجاد فاکتور پرداخت مستقیم */
  createInvoice: async (amount: number, description: string): Promise<DirectInvoice> => {
    const res = await apiClient.post<DirectInvoice>("/payments/fintech/direct-invoices", {
      amount: Math.trunc(amount),
      description,
    });
    return res.data;
  },

  /** دریافت اطلاعات فاکتور */
  getInvoice: async (invoiceId: number): Promise<DirectInvoice> => {
    const res = await apiClient.get<DirectInvoice>(`/payments/fintech/direct-invoices/${invoiceId}`);
    return res.data;
  },

  /** ترجمه کد خطای درگاه به پیام فارسی */
  translateError: async (errorCode: string, provider: string): Promise<string> => {
    const res = await apiClient.post<{ message: string }>("/payments/fintech/errors/translate", {
      error_code: errorCode,
      provider,
    });
    return res.data.message;
  },
};

// --- Saved cards / tokenization (payments upgrade v1) ---

export interface SavedPaymentMethod {
  id: string;
  provider: string;
  masked_pan?: string | null;
  last4?: string | null;
  expiry_jalali?: string | null;
  card_holder_name?: string | null;
  bank_name?: string | null;
  status: "active" | "revoked" | "expired" | "failed";
  is_default: boolean;
  is_active: boolean;
  last_used_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface TokenizeCardResult {
  success: boolean;
  provider: string;
  requires_redirect: boolean;
  redirect_url?: string | null;
  saved_method?: SavedPaymentMethod | null;
  error_code?: string | null;
  error_message?: string | null;
}

// --- Installments ---

export interface InstallmentScheduleEntry {
  due_date_jalali: string;
  due_date?: string | null;
  amount_rial: number;
  status: string;
  paid_at?: string | null;
  is_prepayment: boolean;
}

export interface InstallmentPlan {
  id: string;
  order_id: string;
  user_id: string;
  provider: string;
  total_rial: number;
  num_installments: number;
  first_installment_rial: number;
  remaining_rial: number;
  schedule: InstallmentScheduleEntry[];
  status: "pending" | "active" | "completed" | "canceled" | "defaulted";
  next_due_date?: string | null;
  paid_count: number;
  created_at: string;
  updated_at: string;
}

export interface InstallmentOption {
  num_installments: number;
  first_installment_rial: number;
  monthly_installment_rial: number;
  remaining_rial: number;
  schedule: InstallmentScheduleEntry[];
}

export interface InstallmentOptions {
  provider: string;
  supported: boolean;
  order_total_rial: number;
  months: number[];
  options: InstallmentOption[];
}

// --- Split tender ---

export interface PaymentAllocation {
  id: string;
  order_id: string;
  payment_id: string;
  amount_rial: number;
  provider: string;
  status: "pending" | "processing" | "succeeded" | "failed" | "refunded" | "partially_refunded";
  is_completing: boolean;
  settled_at?: string | null;
  refunded_rial: number;
  failure_reason?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderAllocationSummary {
  order_id: string;
  order_total_rial: number;
  paid_amount_rial: number;
  pending_amount_rial: number;
  remaining_amount_rial: number;
  is_fully_paid: boolean;
  allocations: PaymentAllocation[];
}

export interface SplitTenderRequest {
  order_id: string;
  slices: Array<{
    provider: string;
    amount_rial: number;
    description?: string;
    idempotency_key?: string;
  }>;
}

export interface SplitTenderResponse {
  order_id: string;
  payments: Payment[];
  allocations: PaymentAllocation[];
  redirect_url?: string | null;
  summary: OrderAllocationSummary;
}

/** Saved cards, installment plans, and split tender (payments upgrade v1). */
export const paymentsV1Api = {
  /** لیست کارت‌های ذخیره‌شده */
  listSavedMethods: async (includeInactive = false): Promise<SavedPaymentMethod[]> => {
    const res = await apiClient.get<{ items: SavedPaymentMethod[]; total: number } | SavedPaymentMethod[]>(
      "/payments/saved-methods",
      { params: { include_inactive: includeInactive } },
    );
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: SavedPaymentMethod[] })?.items ?? [];
  },

  /** ثبت و ذخیره یک کارت در درگاه */
  tokenizeCard: async (provider: string): Promise<TokenizeCardResult> => {
    const res = await apiClient.post<TokenizeCardResult>("/payments/saved-methods", {
      provider,
    });
    return res.data;
  },

  /** حذف (ابطال) کارت ذخیره‌شده */
  deleteSavedMethod: async (methodId: string): Promise<SavedPaymentMethod> => {
    const res = await apiClient.delete<SavedPaymentMethod>(
      `/payments/saved-methods/${methodId}`,
    );
    return res.data;
  },

  /** تعیین کارت پیش‌فرض */
  setDefaultSavedMethod: async (methodId: string): Promise<SavedPaymentMethod> => {
    const res = await apiClient.post<SavedPaymentMethod>(
      `/payments/saved-methods/${methodId}/default`,
    );
    return res.data;
  },

  // --- Installments ---

  /** گزینه‌های اقساطی برای یک سفارش */
  getInstallmentOptions: async (
    orderId: string,
    provider: string,
  ): Promise<InstallmentOptions> => {
    const res = await apiClient.get<InstallmentOptions>("/payments/installments/options", {
      params: { order_id: orderId, provider },
    });
    return res.data;
  },

  /** ایجاد طرح اقساطی */
  createInstallmentPlan: async (payload: {
    order_id: string;
    provider: string;
    num_installments: number;
    first_installment_rial: number;
  }): Promise<InstallmentPlan> => {
    const res = await apiClient.post<InstallmentPlan>("/payments/installments", payload);
    return res.data;
  },

  /** لیست طرح‌های اقساطی من */
  listInstallmentPlans: async (): Promise<InstallmentPlan[]> => {
    const res = await apiClient.get<{ items: InstallmentPlan[]; total: number } | InstallmentPlan[]>(
      "/payments/installments",
    );
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: InstallmentPlan[] })?.items ?? [];
  },

  /** طرح اقساطی یک سفارش */
  getOrderInstallmentPlan: async (orderId: string): Promise<InstallmentPlan | null> => {
    const res = await apiClient.get<InstallmentPlan | null>(
      `/payments/installments/orders/${orderId}`,
    );
    return res.data;
  },

  // --- Split tender ---

  /** پرداخت ترکیبی (کیف پول + درگاه) */
  payWithSplit: async (payload: SplitTenderRequest): Promise<SplitTenderResponse> => {
    const res = await apiClient.post<SplitTenderResponse>("/payments/split", payload);
    return res.data;
  },

  /** سهم‌های پرداخت یک سفارش */
  getOrderAllocations: async (orderId: string): Promise<OrderAllocationSummary> => {
    const res = await apiClient.get<OrderAllocationSummary>(
      `/payments/orders/${orderId}/allocations`,
    );
    return res.data;
  },
};

// --- API (admin) ---

export const paymentsAdminApi = {
  /** تأیید پرداخت (ادمین) */
  approvePayment: async (paymentId: number): Promise<Payment> => {
    const res = await apiClient.post<Payment>(`/payments/admin/${paymentId}/approve`);
    return res.data;
  },

  /** رد پرداخت (ادمین) */
  rejectPayment: async (paymentId: number, reason?: string): Promise<Payment> => {
    const res = await apiClient.post<Payment>(`/payments/admin/${paymentId}/reject`, { reason });
    return res.data;
  },

  /** لیست رسیدهای کارت‌به‌کارت (ادمین) */
  listReceipts: async (page = 1, status?: string): Promise<{ items: CardReceipt[]; total: number }> => {
    const res = await apiClient.get<CardReceipt[] | { items: CardReceipt[]; total?: number }>(
      "/payments/fintech/admin/card2card/receipts",
      { params: { page, status } },
    );
    const raw = res.data;
    const items = Array.isArray(raw) ? raw : (raw as { items?: CardReceipt[] })?.items ?? [];
    return { items, total: (raw as { total?: number })?.total ?? items.length };
  },

  /** بررسی رسید کارت‌به‌کارت (ادمین) */
  reviewReceipt: async (
    receiptId: number | string,
    action: "approve" | "reject",
    reason?: string,
  ): Promise<CardReceipt> => {
    const res = await apiClient.post<CardReceipt>(
      `/payments/fintech/admin/card2card/receipts/${receiptId}/review`,
      { is_approved: action === "approve", admin_notes: reason || null },
    );
    return res.data;
  },

  /** تنظیمات درگاه (ادمین) */
  configureGateway: async (providerKey: string, config: Record<string, unknown>): Promise<PaymentGateway> => {
    const res = await apiClient.put<PaymentGateway>(
      `/payments/fintech/admin/gateways/${providerKey}`,
      config,
    );
    return res.data;
  },
};
