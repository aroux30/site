import apiClient from "./client";

// --- Types ---

export interface ShippingMethod {
  id: number;
  name: string;
  provider: string;
  price: number;
  estimated_days_min: number;
  estimated_days_max: number;
  is_active: boolean;
}

export interface ShippingQuoteRequest {
  address_id?: number | string;
  province?: string;
  city?: string;
  weight_grams?: number;
  weight?: number;
  items?: Array<{ variant_id: number | string; quantity: number }>;
}

export interface ShippingQuote {
  method_id: number | string;
  method_name: string;
  price: number;
  estimated_days_min: number;
  estimated_days_max: number;
}

export type DeliveryType = "home" | "cash_on_delivery";

export interface Shipment {
  id: number | string;
  order_id: number | string;
  tracking_code?: string;
  provider?: string;
  method_id?: string;
  quantity?: number;
  status:
    | "pending"
    | "processing"
    | "shipped"
    | "in_transit"
    | "delivered"
    | "returned"
    | "cancelled"
    | string;
  shipped_at?: string;
  delivered_at?: string;
  items?: Array<{ variant_id: number | string; quantity: number }>;
  // -- Shipping upgrade v1 (ERP #32) --
  delivery_type?: DeliveryType;
  cod_amount_rial?: number | null;
  cod_collected_at?: string | null;
  cancelled_at?: string | null;
  cancelled_reason?: string | null;
  label_url?: string | null;
}

export interface TrackingInfo {
  tracking_code: string;
  provider: string;
  status: string;
  events: Array<{
    timestamp: string;
    status: string;
    location?: string;
    description?: string;
  }>;
}

// --- API (user) ---

export const shippingApi = {
  /** لیست روش‌های ارسال فعال */
  getMethods: async (): Promise<ShippingMethod[]> => {
    const res = await apiClient.get<ShippingMethod[] | { items: ShippingMethod[] }>("/shipping/methods");
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: ShippingMethod[] })?.items ?? [];
  },

  /** محاسبه نرخ ارسال بر اساس آدرس و آیتم‌ها */
  getQuote: async (data: ShippingQuoteRequest): Promise<ShippingQuote[]> => {
    const payload = {
      province: data.province || "تهران",
      weight: data.weight ?? ((data.weight_grams ?? 1000) / 1000),
    };
    const res = await apiClient.post<{ quotes?: ShippingQuote[] } | ShippingQuote[]>("/shipping/quote", payload);
    const raw = res.data;
    if (Array.isArray(raw)) return raw;
    return (raw as { quotes?: ShippingQuote[] })?.quotes ?? [];
  },

  /** مرسوله‌های مرتبط با یک سفارش */
  getOrderShipments: async (orderId: number | string): Promise<Shipment[]> => {
    const res = await apiClient.get<Shipment[] | { items: Shipment[] }>(`/shipping/orders/${orderId}/shipments`);
    const raw = res.data;
    return Array.isArray(raw) ? raw : (raw as { items?: Shipment[] })?.items ?? [];
  },

  /** رهگیری مرسوله */
  trackShipment: async (trackingCode: string): Promise<TrackingInfo> => {
    const res = await apiClient.get<TrackingInfo>(`/shipping/track/${trackingCode}`);
    return res.data;
  },
};

// --- API (admin) ---

export const shippingAdminApi = {
  /** ایجاد مرسوله جدید */
  createShipment: async (data: {
    order_id: number | string;
    method_id?: string;
    tracking_code?: string;
    provider?: string;
    items: Array<{ variant_id: number | string; quantity: number }>;
  }): Promise<Shipment> => {
    const payload = {
      order_id: data.order_id,
      method_id: data.method_id || data.provider,
      tracking_code: data.tracking_code,
      items: data.items,
    };
    const res = await apiClient.post<Shipment>("/shipping/admin/shipments", payload);
    return res.data;
  },

  /** بروزرسانی وضعیت مرسوله */
  updateShipment: async (shipmentId: number, data: Partial<Shipment>): Promise<Shipment> => {
    const res = await apiClient.patch<Shipment>(`/shipping/admin/shipments/${shipmentId}`, data);
    return res.data;
  },

  /** لغو مرسوله پیش از تحویل به پست (دلیل الزامی است) */
  cancelShipment: async (shipmentId: string, reason: string): Promise<Shipment> => {
    const res = await apiClient.post<Shipment>(
      `/shipping/admin/shipments/${shipmentId}/cancel`,
      { reason },
    );
    return res.data;
  },

  /** ثبت تسویه وجه پرداخت در محل (idempotent) */
  markCodCollected: async (shipmentId: string): Promise<Shipment> => {
    const res = await apiClient.post<Shipment>(
      `/shipping/admin/shipments/${shipmentId}/cod-collected`,
      {},
    );
    return res.data;
  },
};
