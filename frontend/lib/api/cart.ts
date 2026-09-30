import apiClient from "./client";

// --- Types ---

export interface CartItem {
  id: string | number;
  variant_id: string | number;
  product_id?: string | number;
  product_title?: string;
  variant_title?: string;
  price?: number;
  quantity: number;
  image_url?: string;
  max_quantity?: number;
}

export interface Cart {
  items: CartItem[];
  item_count: number;
  subtotal: number;
  coupon_code?: string;
  coupon_discount?: number;
}

export interface AddCartItemRequest {
  variant_id: string | number;
  quantity: number;
}

export interface UpdateCartItemRequest {
  quantity: number;
}

export interface CartValidation {
  valid: boolean;
  is_valid?: boolean;
  errors: string[];
  issues?: string[];
  unavailable_items?: Array<string | number>;
  cart?: unknown;
}

// --- API ---

export const cartApi = {
  /** دریافت سبد خرید فعلی */
  getCart: async (): Promise<Cart> => {
    const res = await apiClient.get<Cart>("/cart");
    return res.data;
  },

  /** افزودن آیتم به سبد */
  addItem: async (data: AddCartItemRequest): Promise<Cart> => {
    const res = await apiClient.post<Cart>("/cart/items", data);
    return res.data;
  },

  /** بروزرسانی تعداد آیتم */
  updateItem: async (itemId: number | string, data: UpdateCartItemRequest): Promise<Cart> => {
    const res = await apiClient.patch<Cart>(`/cart/items/${itemId}`, data);
    return res.data;
  },

  /** حذف آیتم از سبد */
  deleteItem: async (itemId: number | string): Promise<Cart> => {
    const res = await apiClient.delete<Cart>(`/cart/items/${itemId}`);
    return res.data;
  },

  /** ادغام سبد مهمان با سبد کاربر بعد از لاگین */
  mergeCarts: async (guestSessionId: string): Promise<Cart> => {
    const res = await apiClient.post<Cart>("/cart/merge", { guest_session_id: guestSessionId });
    return res.data;
  },

  /** اعتبارسنجی سبد (موجودی، قیمت‌ها، محدودیت‌ها) */
  validateCart: async (): Promise<CartValidation> => {
    const res = await apiClient.post<any>("/cart/validate");
    const raw = res.data;
    return {
      valid: raw?.valid ?? raw?.is_valid ?? true,
      is_valid: raw?.is_valid ?? raw?.valid ?? true,
      errors: raw?.errors ?? raw?.issues ?? [],
      issues: raw?.issues ?? raw?.errors ?? [],
      unavailable_items: raw?.unavailable_items ?? [],
      cart: raw?.cart,
    };
  },

  /** بازیابی سبد رهاشده از لینک بازیابی (توکن تک‌منظوره) */
  recoverCart: async (token: string): Promise<{ cart: Cart; recovered: boolean }> => {
    const res = await apiClient.post<{ cart: Cart; recovered: boolean }>(
      `/cart/recover?token=${encodeURIComponent(token)}`,
    );
    return res.data;
  },
};
