// Product types
export interface Product {
  id: string;
  title: string;
  slug: string;
  description: string;
  shortDescription?: string;
  price: number;
  originalPrice?: number;
  images: string[];
  category: Category;
  brand?: string;
  sku: string;
  inStock: boolean;
  stockCount: number;
  rating: number;
  reviewCount: number;
  specifications?: Record<string, string>;
  tags?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface Category {
  id: string;
  name: string;
  slug: string;
  icon?: string;
  image?: string;
  parent?: Category;
  children?: Category[];
  productCount?: number;
}

export interface Review {
  id: string;
  userId: string;
  userName: string;
  productId: string;
  rating: number;
  title: string;
  body: string;
  pros?: string[];
  cons?: string[];
  isVerifiedPurchase: boolean;
  createdAt: string;
}

// User types
export interface User {
  id: string;
  firstName: string;
  lastName: string;
  email?: string;
  phone: string;
  avatar?: string;
  addresses: Address[];
  createdAt: string;
}

export interface Address {
  id: string;
  label: string;
  province: string;
  city: string;
  address: string;
  postalCode: string;
  recipientName: string;
  recipientPhone: string;
  isDefault: boolean;
}

// Order types
export interface Order {
  id: string;
  orderNumber: string;
  items: OrderItem[];
  status: OrderStatus;
  totalPrice: number;
  discountAmount: number;
  shippingCost: number;
  finalPrice: number;
  shippingAddress: Address;
  paymentMethod: PaymentMethod;
  trackingNumber?: string;
  createdAt: string;
  updatedAt: string;
}

export interface OrderItem {
  productId: string;
  title: string;
  price: number;
  quantity: number;
  image?: string;
  variant?: string;
}

export type OrderStatus =
  | "pending"
  | "confirmed"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled"
  | "returned";

export type PaymentMethod = "online" | "cod" | "wallet";

// API response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  message: string;
  code: string;
  details?: Record<string, string[]>;
}
