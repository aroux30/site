import apiClient from "./client";

export type PurchaseOrderStatus =
  | "draft"
  | "sent"
  | "partially_received"
  | "received"
  | "closed"
  | "cancelled";

export interface Supplier {
  id: string;
  name: string;
  code: string;
  contact_info: Record<string, unknown>;
  payment_terms_days: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderLine {
  id: string;
  product_variant_id: string;
  position: number;
  qty_ordered: number;
  qty_received: number;
  qty_outstanding: number;
  unit_price_rial: number;
  tax_basis_points: number;
  line_total_rial: number;
  note: string | null;
}

export interface PurchaseOrder {
  id: string;
  supplier_id: string;
  supplier_name: string | null;
  supplier_code: string | null;
  number: string | null;
  status: PurchaseOrderStatus;
  warehouse_id: string | null;
  expected_at: string | null;
  notes: string | null;
  sent_at: string | null;
  closed_at: string | null;
  cancelled_at: string | null;
  subtotal_rial: number;
  tax_rial: number;
  total_rial: number;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  lines: PurchaseOrderLine[];
  receipt_ids: string[];
}

export interface SuggestedPOLine {
  variant_id: string;
  warehouse_id: string;
  available: number;
  min_quantity: number;
  suggested_qty: number;
  unit_price_rial: number;
}

export interface SuggestedPOGroup {
  supplier_id: string | null;
  supplier_name: string | null;
  lines: SuggestedPOLine[];
}

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

const ADMIN = "/admin/procurement";

function idempotencyKey(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `po-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export const procurementApi = {
  // Suppliers
  listSuppliers: async (params?: {
    is_active?: boolean;
    search?: string;
    page?: number;
  }): Promise<Page<Supplier>> => {
    const response = await apiClient.get<Page<Supplier>>(`${ADMIN}/suppliers`, { params });
    return response.data;
  },

  createSupplier: async (data: {
    name: string;
    code: string;
    contact_info?: Record<string, unknown>;
    payment_terms_days?: number;
    is_active?: boolean;
  }): Promise<Supplier> => {
    const response = await apiClient.post<Supplier>(`${ADMIN}/suppliers`, data);
    return response.data;
  },

  updateSupplier: async (
    id: string,
    data: Partial<{
      name: string;
      code: string;
      contact_info: Record<string, unknown>;
      payment_terms_days: number;
      is_active: boolean;
    }>,
  ): Promise<Supplier> => {
    const response = await apiClient.patch<Supplier>(`${ADMIN}/suppliers/${id}`, data);
    return response.data;
  },

  setPreferredVariant: async (
    supplierId: string,
    data: { variant_id: string; supplier_sku?: string; last_unit_price_rial?: number },
  ): Promise<void> => {
    await apiClient.post(`${ADMIN}/suppliers/${supplierId}/preferred-variant`, data);
  },

  // Purchase orders
  listPOs: async (params?: {
    status?: PurchaseOrderStatus;
    supplier_id?: string;
    page?: number;
  }): Promise<Page<PurchaseOrder>> => {
    const response = await apiClient.get<Page<PurchaseOrder>>(`${ADMIN}/pos`, { params });
    return response.data;
  },

  getPO: async (id: string): Promise<PurchaseOrder> => {
    const response = await apiClient.get<PurchaseOrder>(`${ADMIN}/pos/${id}`);
    return response.data;
  },

  createPO: async (data: {
    supplier_id: string;
    lines: Array<{
      product_variant_id: string;
      qty_ordered: number;
      unit_price_rial: number;
      tax_basis_points?: number;
      note?: string;
    }>;
    expected_at?: string;
    notes?: string;
    warehouse_id?: string;
  }): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`${ADMIN}/pos`, data);
    return response.data;
  },

  sendPO: async (id: string): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`${ADMIN}/pos/${id}/send`);
    return response.data;
  },

  receivePO: async (
    id: string,
    lines: Array<{ line_id: string; quantity: number }>,
    notes?: string,
  ): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`${ADMIN}/pos/${id}/receive`, {
      lines,
      notes: notes || undefined,
    });
    return response.data;
  },

  closePO: async (id: string): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`${ADMIN}/pos/${id}/close`);
    return response.data;
  },

  cancelPO: async (id: string): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`${ADMIN}/pos/${id}/cancel`);
    return response.data;
  },

  // Suggestions
  suggestPOs: async (): Promise<{ groups: SuggestedPOGroup[] }> => {
    const response = await apiClient.get<{ groups: SuggestedPOGroup[] }>(`${ADMIN}/pos/suggest`);
    return response.data;
  },

  createPOFromSuggestions: async (data: {
    supplier_id: string;
    variant_ids?: string[];
    notes?: string;
  }): Promise<PurchaseOrder> => {
    const response = await apiClient.post<PurchaseOrder>(`${ADMIN}/pos/suggest`, {
      ...data,
      idempotency_key: idempotencyKey(),
    });
    return response.data;
  },
};
