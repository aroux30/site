import type { UserAddress } from "./user";

export interface Order {
  id: string;
  orderNumber: string;
  userId: string;
  status: OrderStatus;
  paymentStatus: PaymentStatus;
  paymentMethod: PaymentMethod;

  // Items
  items: OrderItem[];

  // Pricing
  subtotal: number;
  shippingCost: number;
  discount: number;
  tax: number;
  total: number;

  // Coupon
  couponCode?: string;
  couponDiscount?: number;

  // Shipping
  shippingAddress: UserAddress;
  shippingMethod: string;
  trackingCode?: string;
  estimatedDelivery?: string;

  // Notes
  customerNote?: string;
  adminNote?: string;

  // Timestamps
  createdAt: string;
  updatedAt: string;
  paidAt?: string;
  shippedAt?: string;
  deliveredAt?: string;
  cancelledAt?: string;
}

export type OrderStatus =
  | "pending"
  | "confirmed"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled"
  | "returned"
  | "refunded";

export type PaymentStatus =
  | "pending"
  | "paid"
  | "failed"
  | "refunded"
  | "partially_refunded";

export type PaymentMethod =
  | "online"
  | "cod"
  | "wallet"
  | "bank_transfer";

export interface OrderItem {
  id: string;
  productId: string;
  productTitle: string;
  productImage?: string;
  variantId?: string;
  variantName?: string;
  sku: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  discount: number;
}

export interface CreateOrderRequest {
  addressId: string;
  shippingMethod: string;
  paymentMethod: PaymentMethod;
  couponCode?: string;
  customerNote?: string;
  items: Array<{
    productId: string;
    variantId?: string;
    quantity: number;
  }>;
}

export interface OrderStatusHistory {
  status: OrderStatus;
  note?: string;
  createdAt: string;
  createdBy?: string;
}

export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  pending: "در انتظار تأیید",
  confirmed: "تأیید شده",
  processing: "در حال پردازش",
  shipped: "ارسال شده",
  delivered: "تحویل داده شده",
  cancelled: "لغو شده",
  returned: "مرجوع شده",
  refunded: "بازپرداخت شده",
};

export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  pending: "در انتظار پرداخت",
  paid: "پرداخت شده",
  failed: "ناموفق",
  refunded: "بازپرداخت شده",
  partially_refunded: "بازپرداخت جزئی",
};
