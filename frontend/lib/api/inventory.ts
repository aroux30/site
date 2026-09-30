import apiClient from "./client";

// --- Types ---

export interface InventoryItem {
  variant_id: number;
  product_id: number;
  product_title: string;
  variant_title: string;
  sku: string;
  quantity: number;
  reserved: number;
  available: number;
  low_stock_threshold?: number;
}

export interface StockAdjustment {
  variant_id?: number | string;
  quantity?: number;
  quantity_change?: number;
  type?: "received" | "sold" | "returned" | "adjusted" | "damaged" | "reserved" | "release" | string;
  notes?: string;
  reason?: string;
  reference?: string;
  reference_id?: string;
}

export interface StockTransaction {
  id: number | string;
  variant_id: number | string;
  type: string;
  quantity_change?: number;
  quantity_after?: number;
  reason?: string;
  reference_id?: string;
  created_at?: string;
}

// --- Digital inventory ---

export interface DigitalCard {
  id: number | string;
  product_id: number | string;
  code?: string;
  pin?: string;
  file_url?: string;
  status: "available" | "reserved" | "delivered" | "revoked" | "expired" | "sold";
  order_id?: number | string;
  viewed_at?: string;
  reading_at?: string;
  created_at: string;
}

export interface PricingTier {
  id: number | string;
  product_id: number | string;
  min_quantity: number;
  max_quantity?: number;
  from_qty?: number;
  to_qty?: number;
  price: number;
  unit_price?: number;
}

// --- API ---

export const inventoryApi = {
  /** لیست موجودی */
  listInventory: async (params?: {
    page?: number;
    page_size?: number;
    search?: string;
  }): Promise<{ items: InventoryItem[]; total: number }> => {
    const res = await apiClient.get<{ items: InventoryItem[]; total: number }>("/inventory", { params });
    return res.data;
  },

  /** موجودی‌های کم */
  getLowStock: async (): Promise<InventoryItem[]> => {
    const res = await apiClient.get<InventoryItem[] | { items: InventoryItem[] }>("/inventory/low-stock");
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: InventoryItem[] })?.items ?? [];
  },

  /** موجودی یک واریانت */
  getVariantInventory: async (variantId: number): Promise<InventoryItem> => {
    const res = await apiClient.get<InventoryItem>(`/inventory/${variantId}`);
    return res.data;
  },

  /** تنظیم دستی موجودی */
  adjustStock: async (variantId: number | string, data: Omit<StockAdjustment, "variant_id">): Promise<StockTransaction> => {
    const payload = {
      quantity: data.quantity ?? data.quantity_change ?? 0,
      type: data.type ?? "adjusted",
      notes: data.notes ?? data.reason,
      reference_id: data.reference_id ?? data.reference,
    };
    const res = await apiClient.post<StockTransaction>(`/inventory/${variantId}/adjust`, payload);
    return res.data;
  },

  /** تاریخچه تراکنش‌های موجودی */
  getTransactions: async (variantId: number, page = 1): Promise<{ items: StockTransaction[]; total: number }> => {
    const res = await apiClient.get<{ items: StockTransaction[]; total: number }>(
      `/inventory/${variantId}/transactions`,
      { params: { page } },
    );
    return res.data;
  },

  // --- Digital ---

  /** کارت‌های دیجیتال یک سفارش (پس از خرید) */
  getOrderCards: async (orderId: number): Promise<DigitalCard[]> => {
    const res = await apiClient.get<DigitalCard[] | { items: DigitalCard[] }>(`/inventory/digital/orders/${orderId}/cards`);
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: DigitalCard[] })?.items ?? [];
  },

  /** علامت‌زدن کارت به‌عنوان مشاهده‌شده */
  markCardViewed: async (cardId: number): Promise<void> => {
    await apiClient.post(`/inventory/digital/cards/${cardId}/viewed`);
  },

  /** دانلود فایل کارت دیجیتال */
  downloadCardFile: async (cardId: number): Promise<Blob> => {
    const res = await apiClient.get(`/inventory/digital/cards/${cardId}/file`, {
      responseType: "blob",
    });
    return res.data as Blob;
  },

  /** محاسبه قیمت بر اساس تعداد (tiered pricing) */
  calculateDigitalPrice: async (productId: number, quantity = 1): Promise<{ price: number; total: number }> => {
    const res = await apiClient.get<{ price: number; total: number }>(
      `/inventory/digital/products/${productId}/price`,
      { params: { quantity } },
    );
    return res.data;
  },

  /** آپلود فایل دیجیتال (ادمین) */
  uploadFileAsset: async (data: FormData): Promise<{ file_url: string }> => {
    const res = await apiClient.post<{ file_url: string }>("/inventory/digital/file-assets", data, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return res.data;
  },

  /** ایجاد کارت‌های فایلی (ادمین) */
  createFileCards: async (data: {
    product_id: number;
    file_urls: string[];
  }): Promise<{ created_count: number }> => {
    const res = await apiClient.post<{ created_count: number }>("/inventory/digital/cards/file", data);
    return res.data;
  },

  /** ویرایش دسته‌ای کارت‌ها (ادمین) */
  batchEditCards: async (data: {
    card_ids: number[];
    status?: string;
    product_id?: number;
  }): Promise<{ updated_count: number }> => {
    const res = await apiClient.patch<{ updated_count: number }>("/inventory/digital/cards/batch", data);
    return res.data;
  },

  /** بازتولید کلید کارت‌ها (ادمین) */
  rekeyCards: async (data: { product_id: number }): Promise<{ rekeyed_count: number }> => {
    const res = await apiClient.post<{ rekeyed_count: number }>("/inventory/digital/rekey", data);
    return res.data;
  },

  /** لیست کارت‌های دیجیتال (ادمین) */
  listCards: async (params?: {
    page?: number;
    product_id?: number;
    status?: string;
  }): Promise<{ items: DigitalCard[]; total: number }> => {
    const res = await apiClient.get<{ items: DigitalCard[]; total: number }>("/inventory/digital/cards", { params });
    return res.data;
  },

  /** ایجاد کارت تکی (ادمین) */
  createSingleCard: async (data: {
    product_id: number | string;
    code?: string;
    pin?: string;
    serial_number?: string | null;
  }): Promise<DigitalCard> => {
    const payload = {
      product_id: data.product_id,
      pin: data.pin || data.code || "",
      serial_number: data.serial_number ?? null,
    };
    const res = await apiClient.post<DigitalCard>("/inventory/digital/cards", payload);
    return res.data;
  },

  /** واردات انبوه کارت (ادمین) */
  bulkImport: async (data: FormData): Promise<{ imported_count: number; errors: string[] }> => {
    const res = await apiClient.post<{ imported_count: number; errors: string[] }>(
      "/inventory/digital/cards/import",
      data,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return res.data;
  },

  /** ایجاد سطح قیمت‌گذاری (ادمین) */
  createPriceTier: async (data: Omit<PricingTier, "id">): Promise<PricingTier> => {
    const payload = {
      product_id: data.product_id,
      from_qty: data.from_qty ?? data.min_quantity,
      to_qty: data.to_qty ?? data.max_quantity ?? null,
      unit_price: data.unit_price ?? Math.trunc(data.price),
    };
    const res = await apiClient.post<PricingTier>("/inventory/digital/pricing-tiers", payload);
    return res.data;
  },

  /** سطوح قیمت‌گذاری یک محصول */
  getPriceTiers: async (productId: number): Promise<PricingTier[]> => {
    const res = await apiClient.get<PricingTier[] | { items: PricingTier[] }>(
      `/inventory/digital/products/${productId}/pricing-tiers`,
    );
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: PricingTier[] })?.items ?? [];
  },
};
