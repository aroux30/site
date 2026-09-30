import apiClient from "./client";

// ── Invoicing (fiscal documents) admin API ──────────────────────────────────

export type InvoiceType = "invoice" | "credit_note";
export type InvoiceStatus = "draft" | "posted" | "paid" | "cancelled";

export interface InvoiceLine {
  id: string;
  position: number;
  product_name: string;
  sku: string | null;
  quantity: number;
  unit_price: number;
  total_price: number;
}

export interface Invoice {
  id: string;
  order_id: string;
  type: InvoiceType;
  status: InvoiceStatus;
  number: string | null;
  fiscal_period: string | null;
  issued_at: string | null;
  posted_at: string | null;
  paid_at: string | null;
  cancelled_at: string | null;
  cancel_reason: string | null;
  totals: {
    currency?: string;
    subtotal?: number;
    discount?: number;
    tax?: number;
    shipping?: number;
    total?: number;
  };
  customer: {
    name?: string | null;
    phone?: string | null;
    national_code?: string | null;
    province?: string | null;
    city?: string | null;
    address?: string | null;
    postal_code?: string | null;
  };
  hash: string | null;
  previous_hash: string | null;
  credit_for_id: string | null;
  credit_reason: string | null;
  has_archive: boolean;
  lines: InvoiceLine[];
  created_at: string | null;
}

export interface InvoiceList {
  items: Invoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface ChainBrokenLink {
  invoice_id: string;
  number: string | null;
  fiscal_period: string | null;
  type: string;
  previous_hash_ok: boolean;
  own_hash_ok: boolean;
}

export interface ChainVerification {
  valid: boolean;
  documents_checked: number;
  first_broken: ChainBrokenLink | null;
}

export const invoicingApi = {
  list: (params?: {
    status?: InvoiceStatus;
    fiscal_period?: string;
    type?: InvoiceType;
    page?: number;
    page_size?: number;
  }) => apiClient.get<InvoiceList>("/admin/invoices", { params }).then((r) => r.data),

  get: (id: string) => apiClient.get<Invoice>(`/admin/invoices/${id}`).then((r) => r.data),

  post: (id: string) =>
    apiClient.post<Invoice>(`/admin/invoices/${id}/post`).then((r) => r.data),

  cancel: (id: string, reason: string) =>
    apiClient.post<Invoice>(`/admin/invoices/${id}/cancel`, { reason }).then((r) => r.data),

  markPaid: (id: string) =>
    apiClient.post<Invoice>(`/admin/invoices/${id}/mark-paid`).then((r) => r.data),

  createDraftForOrder: (orderId: string) =>
    apiClient
      .post<Invoice>(`/admin/invoices/orders/${orderId}/create-draft`)
      .then((r) => r.data),

  verifyChain: (params?: { type?: InvoiceType; fiscal_period?: string }) =>
    apiClient
      .get<ChainVerification>("/admin/invoices/verify-chain", { params })
      .then((r) => r.data),

  downloadArchive: (id: string) =>
    apiClient
      .get(`/admin/invoices/${id}/archive`, { responseType: "blob" })
      .then((r) => r.data as Blob),
};
