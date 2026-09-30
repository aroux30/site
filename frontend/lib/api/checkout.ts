import apiClient from "./client";

// --- Types ---

export interface CheckoutItem {
  variant_id: string | number;
  quantity: number;
}

export interface CheckoutQuoteRequest {
  cart_id?: string;
  address_id?: string;
  shipping_method_id?: string;
  coupon_code?: string | null;
  items?: CheckoutItem[];
  shipping_address_id?: string | number;
  use_wallet_balance?: boolean;
}

export interface CheckoutQuoteResponse {
  subtotal: number;
  discount_amount: number;
  shipping_cost: number;
  tax: number;
  tax_amount?: number;
  total: number;
  payable_amount?: number;
  coupon_applied?: boolean;
  wallet_deduction?: number;
  is_valid?: boolean;
  validation_errors?: string[];
  items?: unknown[];
}

export interface CreateOrderRequest {
  cart_id: string;
  address_id: string;
  shipping_method_id: string;
  payment_method: "gateway" | "wallet" | "card_to_card" | string;
  idempotency_key?: string;
  coupon_code?: string | null;
  notes?: string | null;
  customer_note?: string;
  item_fields?: Record<string, Record<string, string | number>> | null;
  gateway_provider?: string;
  items?: CheckoutItem[];
  shipping_address_id?: string | number;
}

export interface CreateOrderResponse {
  order_id: string | number;
  order_number: string;
  status?: string;
  subtotal?: number;
  shipping_cost?: number;
  discount_amount?: number;
  tax?: number;
  total?: number;
  payable_amount?: number;
  payment_url?: string | null;
  requires_action?: boolean;
  created_at?: string;
}

// --- API ---

export const checkoutApi = {
  /** محاسبه ارقام سبد: جمع، تخفیف، مالیات، ارسال، قابل پرداخت */
  calculateQuote: async (data: CheckoutQuoteRequest): Promise<CheckoutQuoteResponse> => {
    const payload = {
      cart_id: data.cart_id,
      address_id: data.address_id || (data.shipping_address_id ? String(data.shipping_address_id) : undefined),
      shipping_method_id: data.shipping_method_id ? String(data.shipping_method_id) : undefined,
      coupon_code: data.coupon_code || null,
    };
    const res = await apiClient.post<CheckoutQuoteResponse>("/checkout/quote", payload);
    const quote = res.data;
    if (quote) {
      if (quote.tax_amount === undefined && quote.tax !== undefined) quote.tax_amount = quote.tax;
      if (quote.payable_amount === undefined && quote.total !== undefined) quote.payable_amount = quote.total;
      if (quote.is_valid === undefined) quote.is_valid = true;
    }
    return quote;
  },

  /** اعتبارسنجی نهایی موجودی و شرایط خرید قبل از پرداخت */
  validateCheckout: async (data: CheckoutQuoteRequest): Promise<{ valid: boolean; errors: string[] }> => {
    const payload = {
      cart_id: data.cart_id,
      address_id: data.address_id || (data.shipping_address_id ? String(data.shipping_address_id) : undefined),
      shipping_method_id: data.shipping_method_id ? String(data.shipping_method_id) : undefined,
      coupon_code: data.coupon_code || null,
    };
    const res = await apiClient.post<{ is_valid?: boolean; valid?: boolean; issues?: string[]; errors?: string[] }>("/checkout/validate", payload);
    return {
      valid: res.data.valid ?? res.data.is_valid ?? true,
      errors: res.data.errors ?? res.data.issues ?? [],
    };
  },

  /** ثبت سفارش و دریافت لینک پرداخت */
  createOrder: async (data: CreateOrderRequest): Promise<CreateOrderResponse> => {
    const payload = {
      cart_id: data.cart_id,
      address_id: data.address_id || (data.shipping_address_id ? String(data.shipping_address_id) : undefined),
      shipping_method_id: data.shipping_method_id ? String(data.shipping_method_id) : undefined,
      payment_method: data.payment_method,
      idempotency_key: data.idempotency_key || (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `ord-${Date.now()}`),
      coupon_code: data.coupon_code || null,
      notes: data.notes || data.customer_note || null,
      item_fields: data.item_fields || null,
    };
    const res = await apiClient.post<CreateOrderResponse>("/checkout/create-order", payload);
    const order = res.data;
    if (order && order.payable_amount === undefined && order.total !== undefined) {
      order.payable_amount = order.total;
    }
    return order;
  },
};
