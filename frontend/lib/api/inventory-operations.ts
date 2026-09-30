import apiClient from "./client";

export type StockCountStatus = "draft" | "counting" | "review" | "posted" | "cancelled";
export type StockCountScope = "full" | "category" | "product-list";
export type TransferStatus = "draft" | "shipped" | "received" | "cancelled";
export type ReceiptStatus = "draft" | "received" | "cancelled";

export interface OperationLine {
  product_variant_id: string;
  quantity: number;
}

export interface StockCountLine {
  id?: string;
  product_variant_id: string;
  system_qty: number;
  counted_qty: number | null;
  variance: number | null;
  note: string | null;
}

export interface StockCount {
  id: string;
  warehouse_id: string;
  status: StockCountStatus;
  scope: StockCountScope;
  scope_filter: Record<string, unknown>;
  started_at: string | null;
  posted_at: string | null;
  line_count: number;
  counted_line_count: number;
  variance_line_count: number;
  variance_quantity: number;
  created_at: string;
  updated_at: string;
  lines: StockCountLine[];
}

export interface WarehouseTransfer {
  id: string;
  from_warehouse_id: string;
  to_warehouse_id: string;
  status: TransferStatus;
  notes: string | null;
  shipped_at: string | null;
  received_at: string | null;
  created_at: string;
  updated_at: string;
  lines: Array<OperationLine & { id?: string }>;
}

export interface Receipt {
  id: string;
  warehouse_id: string;
  status: ReceiptStatus;
  notes: string | null;
  received_at: string | null;
  created_at: string;
  updated_at: string;
  lines: Array<OperationLine & { id?: string }>;
}

interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

const ADMIN_INVENTORY = "/admin/inventory";

function idempotencyKey(): string {
  return typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
    ? crypto.randomUUID()
    : `inventory-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export const inventoryOperationsApi = {
  listCounts: async (params?: { status?: StockCountStatus; page?: number }): Promise<Page<StockCount>> => {
    const response = await apiClient.get<Page<StockCount>>(`${ADMIN_INVENTORY}/counts`, { params });
    return response.data;
  },

  getCount: async (id: string): Promise<StockCount> => {
    const response = await apiClient.get<StockCount>(`${ADMIN_INVENTORY}/counts/${id}`);
    return response.data;
  },

  createCount: async (data: {
    warehouse_id?: string;
    scope: StockCountScope;
    scope_filter?: Record<string, unknown>;
  }): Promise<StockCount> => {
    const response = await apiClient.post<StockCount>(`${ADMIN_INVENTORY}/counts`, data);
    return response.data;
  },

  startCount: async (id: string): Promise<StockCount> => {
    const response = await apiClient.post<StockCount>(`${ADMIN_INVENTORY}/counts/${id}/start`);
    return response.data;
  },

  saveCountLines: async (
    id: string,
    lines: Array<{ product_variant_id: string; counted_qty: number; note?: string | null }>,
  ): Promise<StockCount> => {
    const response = await apiClient.put<StockCount>(`${ADMIN_INVENTORY}/counts/${id}/lines`, { lines });
    return response.data;
  },

  reviewCount: async (id: string): Promise<StockCount> => {
    const response = await apiClient.post<StockCount>(`${ADMIN_INVENTORY}/counts/${id}/review`);
    return response.data;
  },

  postCount: async (id: string): Promise<StockCount> => {
    const response = await apiClient.post<StockCount>(`${ADMIN_INVENTORY}/counts/${id}/post`);
    return response.data;
  },

  cancelCount: async (id: string): Promise<StockCount> => {
    const response = await apiClient.post<StockCount>(`${ADMIN_INVENTORY}/counts/${id}/cancel`);
    return response.data;
  },

  listTransfers: async (params?: { status?: TransferStatus; page?: number }): Promise<Page<WarehouseTransfer>> => {
    const response = await apiClient.get<Page<WarehouseTransfer>>(`${ADMIN_INVENTORY}/transfers`, { params });
    return response.data;
  },

  createTransfer: async (data: {
    from_warehouse_id: string;
    to_warehouse_id: string;
    lines: OperationLine[];
    notes?: string;
  }): Promise<WarehouseTransfer> => {
    const response = await apiClient.post<WarehouseTransfer>(`${ADMIN_INVENTORY}/transfers`, data, {
      headers: { "Idempotency-Key": idempotencyKey() },
    });
    return response.data;
  },

  shipTransfer: async (id: string): Promise<WarehouseTransfer> => {
    const response = await apiClient.post<WarehouseTransfer>(`${ADMIN_INVENTORY}/transfers/${id}/ship`);
    return response.data;
  },

  receiveTransfer: async (id: string): Promise<WarehouseTransfer> => {
    const response = await apiClient.post<WarehouseTransfer>(`${ADMIN_INVENTORY}/transfers/${id}/receive`);
    return response.data;
  },

  listReceipts: async (params?: { status?: ReceiptStatus; page?: number }): Promise<Page<Receipt>> => {
    const response = await apiClient.get<Page<Receipt>>(`${ADMIN_INVENTORY}/receipts`, { params });
    return response.data;
  },

  createReceipt: async (data: {
    warehouse_id?: string;
    lines: OperationLine[];
    notes?: string;
  }): Promise<Receipt> => {
    const response = await apiClient.post<Receipt>(`${ADMIN_INVENTORY}/receipts`, data);
    return response.data;
  },

  receiveReceipt: async (id: string): Promise<Receipt> => {
    const response = await apiClient.post<Receipt>(`${ADMIN_INVENTORY}/receipts/${id}/receive`);
    return response.data;
  },

  cancelReceipt: async (id: string): Promise<Receipt> => {
    const response = await apiClient.post<Receipt>(`${ADMIN_INVENTORY}/receipts/${id}/cancel`);
    return response.data;
  },
};

// ── Barcode scanning (ERP feature #26) ──────────────────────────────────────

export interface ResolvedScan {
  code: string;
  quantity: number;
  variant_id: string;
  sku: string;
  product_name: string;
  /** `ProductVariant.price` verbatim — Rial, like the DB column. Divide by 10 to show. */
  price_rial: number;
  on_hand: number;
  reserved: number;
  available: number;
  is_active: boolean;
  warnings: string[];
}

export interface ScanBatchResult {
  resolved: ResolvedScan[];
  unresolved: Array<{ code: string; reason: string; endpoint: string }>;
  total_scanned: number;
  resolved_count: number;
  unresolved_count: number;
}

export const inventoryScanApi = {
  /** حل یک دسته بارکد اسکن‌شده */
  resolve: async (payload: {
    codes: string[];
    warehouse_id?: string | null;
  }): Promise<ScanBatchResult> => {
    const res = await apiClient.post<ScanBatchResult>(
      "/admin/inventory/scan/resolve",
      payload,
    );
    return res.data;
  },

  /** حل یک بارکد (برای اسکن تک‌به‌تک) */
  resolveOne: async (code: string, warehouseId?: string | null): Promise<ResolvedScan> => {
    const res = await apiClient.get<ResolvedScan>(
      `/admin/inventory/scan/${encodeURIComponent(code)}`,
      { params: { warehouse_id: warehouseId } },
    );
    return res.data;
  },

  /** ایجاد رسید دریافت از اسکن‌ها */
  receive: async (payload: {
    codes: string[];
    warehouse_id?: string | null;
  }): Promise<{ receipt_id: string; line_count: number; unresolved: ScanBatchResult["unresolved"] }> => {
    const res = await apiClient.post("/admin/inventory/scan/receive", payload);
    return res.data;
  },
};
