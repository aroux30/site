"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import {
  Kanban,
  RefreshCw,
  Search,
  Clock,
  AlertTriangle,
  ChevronLeft,
  XCircle,
  Eye,
  Copy,
  Check,
  Phone,
  User,
  Package,
  CheckCircle2,
  MapPin,
  Mail,
  FileText,
  AlertCircle,
  X,
  ShoppingBag,
  Layers,
  CircleDollarSign,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { formatPrice, toPersianDigits, cn } from "@/lib/utils";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

type KanbanStatus =
  | "pending"
  | "confirmed"
  | "processing"
  | "packing"
  | "shipped"
  | "delivered"
  | "canceled";

interface OrderItemDetail {
  id: string;
  title: string;
  sku: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  imageUrl?: string;
}

interface ShippingAddressDetail {
  recipientName: string;
  phone: string;
  province: string;
  city: string;
  postalCode: string;
  fullAddress: string;
}

interface KanbanOrder {
  id: string;
  orderNumber: string;
  customerName: string;
  customerPhone: string;
  customerEmail?: string;
  createdAt: string; // ISO date string
  subtotal: number;
  shippingCost: number;
  discount: number;
  total: number;
  status: KanbanStatus;
  paymentStatus: "paid" | "pending" | "failed" | "refunded";
  paymentMethod: string;
  shippingAddress: ShippingAddressDetail;
  items: OrderItemDetail[];
  trackingCode?: string;
  adminNote?: string;
}

interface KanbanColumnConfig {
  id: KanbanStatus;
  title: string;
  subtitle: string;
  nextStatus?: KanbanStatus;
  nextActionLabel?: string;
  allowCancel: boolean;
  color: {
    indicator: string; // CSS bg class for top indicator bar
    badge: string;     // badge class
    accent: string;    // text color
    bgMuted: string;   // light tinted background for column header
    border: string;    // border class
    headerBorder: string;
    button: string;    // Action button theme
  };
}

/* ------------------------------------------------------------------ */
/*  Kanban Columns Pipeline Configuration                             */
/* ------------------------------------------------------------------ */

const PIPELINE_COLUMNS: KanbanColumnConfig[] = [
  {
    id: "pending",
    title: "جدید / در انتظار",
    subtitle: "در انتظار بررسی و تایید مالی",
    nextStatus: "confirmed",
    nextActionLabel: "تایید سفارش",
    allowCancel: true,
    color: {
      indicator: "bg-amber-500",
      badge: "bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300 border-amber-300 dark:border-amber-800",
      accent: "text-amber-600 dark:text-amber-400",
      bgMuted: "bg-amber-500/5 dark:bg-amber-950/20",
      border: "border-amber-200/80 dark:border-amber-800/40",
      headerBorder: "border-t-amber-500",
      button: "bg-amber-500 hover:bg-amber-600 text-white dark:bg-amber-600 dark:hover:bg-amber-700",
    },
  },
  {
    id: "confirmed",
    title: "تایید شده",
    subtitle: "آماده واگذاری به انبار",
    nextStatus: "processing",
    nextActionLabel: "شروع پردازش",
    allowCancel: true,
    color: {
      indicator: "bg-blue-500",
      badge: "bg-blue-100 text-blue-800 dark:bg-blue-950/70 dark:text-blue-300 border-blue-300 dark:border-blue-800",
      accent: "text-blue-600 dark:text-blue-400",
      bgMuted: "bg-blue-500/5 dark:bg-blue-950/20",
      border: "border-blue-200/80 dark:border-blue-800/40",
      headerBorder: "border-t-blue-500",
      button: "bg-blue-500 hover:bg-blue-600 text-white dark:bg-blue-600 dark:hover:bg-blue-700",
    },
  },
  {
    id: "processing",
    title: "در حال پردازش",
    subtitle: "جمع‌آوری اقلام از انبار مرکزی",
    nextStatus: "packing",
    nextActionLabel: "انتقال به بسته‌بندی",
    allowCancel: false,
    color: {
      indicator: "bg-indigo-500",
      badge: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950/70 dark:text-indigo-300 border-indigo-300 dark:border-indigo-800",
      accent: "text-indigo-600 dark:text-indigo-400",
      bgMuted: "bg-indigo-500/5 dark:bg-indigo-950/20",
      border: "border-indigo-200/80 dark:border-indigo-800/40",
      headerBorder: "border-t-indigo-500",
      button: "bg-indigo-500 hover:bg-indigo-600 text-white dark:bg-indigo-600 dark:hover:bg-indigo-700",
    },
  },
  {
    id: "packing",
    title: "در حال بسته‌بندی",
    subtitle: "پک نهایی و درج برچسب پستی",
    nextStatus: "shipped",
    nextActionLabel: "تحویل به پست / ارسال",
    allowCancel: false,
    color: {
      indicator: "bg-purple-500",
      badge: "bg-purple-100 text-purple-800 dark:bg-purple-950/70 dark:text-purple-300 border-purple-300 dark:border-purple-800",
      accent: "text-purple-600 dark:text-purple-400",
      bgMuted: "bg-purple-500/5 dark:bg-purple-950/20",
      border: "border-purple-200/80 dark:border-purple-800/40",
      headerBorder: "border-t-purple-500",
      button: "bg-purple-500 hover:bg-purple-600 text-white dark:bg-purple-600 dark:hover:bg-purple-700",
    },
  },
  {
    id: "shipped",
    title: "تحویل به پست / ارسال شده",
    subtitle: "در مسیر تحویل به نشانی مشتری",
    nextStatus: "delivered",
    nextActionLabel: "ثبت تحویل داده شده",
    allowCancel: false,
    color: {
      indicator: "bg-cyan-500",
      badge: "bg-cyan-100 text-cyan-800 dark:bg-cyan-950/70 dark:text-cyan-300 border-cyan-300 dark:border-cyan-800",
      accent: "text-cyan-600 dark:text-cyan-400",
      bgMuted: "bg-cyan-500/5 dark:bg-cyan-950/20",
      border: "border-cyan-200/80 dark:border-cyan-800/40",
      headerBorder: "border-t-cyan-500",
      button: "bg-cyan-600 hover:bg-cyan-700 text-white dark:bg-cyan-600 dark:hover:bg-cyan-700",
    },
  },
  {
    id: "delivered",
    title: "تحویل داده شده",
    subtitle: "تکمیل شده و تحویل به گیرنده",
    nextStatus: undefined,
    nextActionLabel: undefined,
    allowCancel: false,
    color: {
      indicator: "bg-emerald-500",
      badge: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border-emerald-300 dark:border-emerald-800",
      accent: "text-emerald-600 dark:text-emerald-400",
      bgMuted: "bg-emerald-500/5 dark:bg-emerald-950/20",
      border: "border-emerald-200/80 dark:border-emerald-800/40",
      headerBorder: "border-t-emerald-500",
      button: "bg-emerald-600 hover:bg-emerald-700 text-white",
    },
  },
];

/* ------------------------------------------------------------------ */
/*  Helpers: Staleness & Persian Relative Time                         */
/* ------------------------------------------------------------------ */

/**
 * Checks if an order is stale: older than 24 hours in pending or processing.
 */
function checkIsOrderStale(order: KanbanOrder): boolean {
  if (order.status !== "pending" && order.status !== "processing") {
    return false;
  }
  const createdTime = new Date(order.createdAt).getTime();
  if (isNaN(createdTime)) return false;
  const elapsedMs = Date.now() - createdTime;
  return elapsedMs >= 24 * 60 * 60 * 1000;
}

/**
 * Calculates hours elapsed for an order.
 */
function getElapsedHours(isoString: string): number {
  const createdTime = new Date(isoString).getTime();
  if (isNaN(createdTime)) return 0;
  return Math.max(0, Math.floor((Date.now() - createdTime) / (1000 * 60 * 60)));
}

/**
 * Format relative Persian time.
 */
function formatPersianRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "نامشخص";

  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHours = Math.floor(diffMin / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSec < 60) return "چند لحظه پیش";
  if (diffMin < 60) return `${toPersianDigits(diffMin)} دقیقه پیش`;
  if (diffHours < 24) return `${toPersianDigits(diffHours)} ساعت پیش`;
  if (diffDays === 1) return "دیروز";
  if (diffDays < 7) return `${toPersianDigits(diffDays)} روز پیش`;
  if (diffDays < 30) return `${toPersianDigits(Math.floor(diffDays / 7))} هفته پیش`;

  return date.toLocaleDateString("fa-IR");
}

/**
 * Format full Persian date.
 */
function formatPersianFullDate(isoString: string): string {
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "نامشخص";
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/* ------------------------------------------------------------------ */
/*  Initial Fallback Mock Data                                         */
/* ------------------------------------------------------------------ */

const hoursAgo = (hours: number): string => {
  return new Date(Date.now() - hours * 3600 * 1000).toISOString();
};

const INITIAL_KANBAN_ORDERS: KanbanOrder[] = [
  // 1. Pending (Fresh)
  {
    id: "ord-kanban-1",
    orderNumber: "ORD-20260909-1082",
    customerName: "سارا ابراهیمی",
    customerPhone: "09123456789",
    customerEmail: "sara.ebrahimi@example.com",
    createdAt: hoursAgo(3.5), // 3.5 hours ago
    subtotal: 3_450_000,
    shippingCost: 150_000,
    discount: 0,
    total: 3_600_000,
    status: "pending",
    paymentStatus: "paid",
    paymentMethod: "درگاه سامان",
    shippingAddress: {
      recipientName: "سارا ابراهیمی",
      phone: "09123456789",
      province: "تهران",
      city: "تهران",
      postalCode: "1415698741",
      fullAddress: "بلوار کشاورز، خیابان وصال شیرازی، پلاک ۴۲، واحد ۸",
    },
    items: [
      {
        id: "item-101",
        title: "هندزفری بی‌سیم کیو‌سی‌وای T13 ANC",
        sku: "QCY-T13-ANC",
        quantity: 2,
        unitPrice: 1_250_000,
        totalPrice: 2_500_000,
      },
      {
        id: "item-102",
        title: "پایه نگهدارنده گوشی و تبلت باسئوس",
        sku: "BAS-HLD-01",
        quantity: 1,
        unitPrice: 950_000,
        totalPrice: 950_000,
      },
    ],
  },
  // 2. Pending (STALE: > 24 hours!)
  {
    id: "ord-kanban-2",
    orderNumber: "ORD-20260907-9812",
    customerName: "مهدی اکبری",
    customerPhone: "09132223344",
    customerEmail: "m.akbari@chmail.ir",
    createdAt: hoursAgo(38), // 38 hours ago -> STALE!
    subtotal: 68_500_000,
    shippingCost: 0,
    discount: 1_500_000,
    total: 67_000_000,
    status: "pending",
    paymentStatus: "pending",
    paymentMethod: "فیش بانکی / پایا",
    shippingAddress: {
      recipientName: "مهدی اکبری",
      phone: "09132223344",
      province: "اصفهان",
      city: "اصفهان",
      postalCode: "8198745612",
      fullAddress: "خیابان نظر میانی، کوچه آسیاب، مجتمع نگین، واحد ۲",
    },
    items: [
      {
        id: "item-103",
        title: "گوشی موبایل سامسونگ Galaxy S24 Ultra ظرفیت 256",
        sku: "SAM-S24U-256",
        quantity: 1,
        unitPrice: 68_500_000,
        totalPrice: 68_500_000,
      },
    ],
  },
  // 3. Confirmed
  {
    id: "ord-kanban-3",
    orderNumber: "ORD-20260909-3410",
    customerName: "فاطمه احمدی",
    customerPhone: "09351234567",
    customerEmail: "fatemeh.ahmadi@gmail.com",
    createdAt: hoursAgo(6),
    subtotal: 8_900_000,
    shippingCost: 0,
    discount: 200_000,
    total: 8_700_000,
    status: "confirmed",
    paymentStatus: "paid",
    paymentMethod: "کیف پول آنلاین",
    shippingAddress: {
      recipientName: "فاطمه احمدی",
      phone: "09351234567",
      province: "تهران",
      city: "تهران",
      postalCode: "1939547891",
      fullAddress: "میدان ونک، خیابان ملاصدرا، کوچه بهار، پلاک ۱۲، واحد ۳",
    },
    items: [
      {
        id: "item-104",
        title: "ساعت هوشمند شیائومی Band 8 پرو مشکی",
        sku: "XIA-BND-8PRO",
        quantity: 1,
        unitPrice: 4_500_000,
        totalPrice: 4_500_000,
      },
      {
        id: "item-105",
        title: "هدفون بلوتوثی انکر Soundcore Life P2i",
        sku: "ANK-LIFE-P2I",
        quantity: 1,
        unitPrice: 4_400_000,
        totalPrice: 4_400_000,
      },
    ],
  },
  // 4. Confirmed (Second order)
  {
    id: "ord-kanban-4",
    orderNumber: "ORD-20260908-7721",
    customerName: "کیان میرزایی",
    customerPhone: "09128889900",
    createdAt: hoursAgo(18),
    subtotal: 4_120_000,
    shippingCost: 180_000,
    discount: 0,
    total: 4_300_000,
    status: "confirmed",
    paymentStatus: "paid",
    paymentMethod: "درگاه ملت",
    shippingAddress: {
      recipientName: "کیان میرزایی",
      phone: "09128889900",
      province: "البرز",
      city: "کرج",
      postalCode: "3145678912",
      fullAddress: "گوهردشت، بلوار رستاخیز، خیابان نهم غربی، پلاک ۵",
    },
    items: [
      {
        id: "item-106",
        title: "ماوس بی‌سیم لاجیتک مدل Pebble M350",
        sku: "LOG-PEBBLE-M350",
        quantity: 2,
        unitPrice: 1_200_000,
        totalPrice: 2_400_000,
      },
      {
        id: "item-107",
        title: "پد ماوس گیمینگ طبی سایز بزرگ",
        sku: "PAD-GAME-XL",
        quantity: 1,
        unitPrice: 1_720_000,
        totalPrice: 1_720_000,
      },
    ],
  },
  // 5. Processing (STALE: > 24 hours!)
  {
    id: "ord-kanban-5",
    orderNumber: "ORD-20260908-5431",
    customerName: "علی محمدی",
    customerPhone: "09121112233",
    customerEmail: "ali.mohammadi@example.com",
    createdAt: hoursAgo(29), // 29 hours ago -> STALE!
    subtotal: 15_200_000,
    shippingCost: 0,
    discount: 500_000,
    total: 14_700_000,
    status: "processing",
    paymentStatus: "paid",
    paymentMethod: "درگاه پاسارگاد",
    shippingAddress: {
      recipientName: "علی محمدی",
      phone: "09121112233",
      province: "فارس",
      city: "شیراز",
      postalCode: "7134598120",
      fullAddress: "خیابان زند، بعد از بیمارستان سعدی، نبش کوچه ۱۵",
    },
    items: [
      {
        id: "item-108",
        title: "هارد اکسترنال وسترن دیجیتال My Passport ۲ ترابایت",
        sku: "WD-PASSPORT-2TB",
        quantity: 2,
        unitPrice: 5_600_000,
        totalPrice: 11_200_000,
      },
      {
        id: "item-109",
        title: "کابل تبدیل Type-C به HDMI باسئوس 4K",
        sku: "BAS-TYPEC-HDMI",
        quantity: 2,
        unitPrice: 2_000_000,
        totalPrice: 4_000_000,
      },
    ],
  },
  // 6. Processing (Fresh)
  {
    id: "ord-kanban-6",
    orderNumber: "ORD-20260909-6612",
    customerName: "پریسا صادقی",
    customerPhone: "09367778899",
    createdAt: hoursAgo(8),
    subtotal: 2_350_000,
    shippingCost: 150_000,
    discount: 0,
    total: 2_500_000,
    status: "processing",
    paymentStatus: "paid",
    paymentMethod: "درگاه بانکی ملت",
    shippingAddress: {
      recipientName: "پریسا صادقی",
      phone: "09367778899",
      province: "گیلان",
      city: "رشت",
      postalCode: "4198745632",
      fullAddress: "بلوار دیلمان، مجتمع تجاری آفرینش، واحد ۱۲",
    },
    items: [
      {
        id: "item-110",
        title: "پاوربانک ۲۰۰۰۰ میلی‌آمپر فست شارژ انکر Anker 737",
        sku: "ANK-PB-737",
        quantity: 1,
        unitPrice: 2_350_000,
        totalPrice: 2_350_000,
      },
    ],
  },
  // 7. Packing
  {
    id: "ord-kanban-7",
    orderNumber: "ORD-20260909-4029",
    customerName: "امیرحسین رستمی",
    customerPhone: "09194445566",
    createdAt: hoursAgo(11),
    subtotal: 5_600_000,
    shippingCost: 200_000,
    discount: 300_000,
    total: 5_500_000,
    status: "packing",
    paymentStatus: "paid",
    paymentMethod: "درگاه سامان",
    shippingAddress: {
      recipientName: "امیرحسین رستمی",
      phone: "09194445566",
      province: "تهران",
      city: "تهران",
      postalCode: "1145698712",
      fullAddress: "خیابان شریعتی، بالاتر از پل رومی، کوچه رضایی، پلاک ۷",
    },
    items: [
      {
        id: "item-111",
        title: "اسپیکر بلوتوثی قابل حمل جی‌بی‌ال Go 4",
        sku: "JBL-GO-4",
        quantity: 2,
        unitPrice: 2_800_000,
        totalPrice: 5_600_000,
      },
    ],
  },
  // 8. Shipped
  {
    id: "ord-kanban-8",
    orderNumber: "ORD-20260908-2190",
    customerName: "محمد حسینی",
    customerPhone: "09197654321",
    createdAt: hoursAgo(30),
    subtotal: 1_200_000,
    shippingCost: 150_000,
    discount: 150_000,
    total: 1_200_000,
    status: "shipped",
    paymentStatus: "paid",
    paymentMethod: "درگاه ملت",
    trackingCode: "POST-8721094",
    shippingAddress: {
      recipientName: "محمد حسینی",
      phone: "09197654321",
      province: "خراسان رضوی",
      city: "مشهد",
      postalCode: "9177534567",
      fullAddress: "بلوار سجاد، خیابان بهارستان، بهارستان ۴، پلاک ۲۸",
    },
    items: [
      {
        id: "item-112",
        title: "کابل لایتنینگ انکر PowerLine Select",
        sku: "ANK-CBL-SEL",
        quantity: 1,
        unitPrice: 1_200_000,
        totalPrice: 1_200_000,
      },
    ],
  },
  // 9. Delivered
  {
    id: "ord-kanban-9",
    orderNumber: "ORD-20260907-1102",
    customerName: "زهرا کریمی",
    customerPhone: "09129876543",
    createdAt: hoursAgo(52),
    subtotal: 4_500_000,
    shippingCost: 0,
    discount: 0,
    total: 4_500_000,
    status: "delivered",
    paymentStatus: "paid",
    paymentMethod: "زرین‌پال",
    trackingCode: "POST-7612300",
    shippingAddress: {
      recipientName: "زهرا کریمی",
      phone: "09129876543",
      province: "آذربایجان شرقی",
      city: "تبریز",
      postalCode: "5145698741",
      fullAddress: "خیابان ولیعصر، فلکه شریعتی، مجتمع میلاد، واحد ۵",
    },
    items: [
      {
        id: "item-113",
        title: "شارژر دیواری ۶۵ وات انکر GaNPrime",
        sku: "ANK-GAN-65W",
        quantity: 1,
        unitPrice: 4_500_000,
        totalPrice: 4_500_000,
      },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Main Kanban Board Component                                       */
/* ------------------------------------------------------------------ */

export default function AdminKanbanPage() {
  const { toast } = useToast();

  const [orders, setOrders] = useState<KanbanOrder[]>(INITIAL_KANBAN_ORDERS);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date>(new Date());

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [showOnlyStale, setShowOnlyStale] = useState(false);

  // Modals & Action States
  const [selectedOrder, setSelectedOrder] = useState<KanbanOrder | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  const [cancelTargetOrder, setCancelTargetOrder] = useState<KanbanOrder | null>(null);
  const [cancelReason, setCancelReason] = useState("درخواست مشتری");
  const [isCanceling, setIsCanceling] = useState(false);

  const [updatingOrderId, setUpdatingOrderId] = useState<string | null>(null);
  const [copiedOrderId, setCopiedOrderId] = useState<string | null>(null);

  /* ------------------------------------------------------------------ */
  /*  Fetch Orders from API                                             */
  /* ------------------------------------------------------------------ */

  const fetchOrdersFromApi = useCallback(async (isManual = false) => {
    try {
      setIsRefreshing(true);
      // Attempt backend endpoints
      const res = await apiClient
        .get("/admin/orders?page_size=100")
        .catch(() => apiClient.get("/orders/admin/orders?page_size=100"))
        .catch(() => apiClient.get("/orders?page_size=100"));

      if (res?.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
        const mappedOrders: KanbanOrder[] = res.data.items.map((raw: any, index: number) => {
          const rawStatus = (raw.status || "pending").toLowerCase();
          let status: KanbanStatus = "pending";
          if (["pending", "confirmed", "processing", "packing", "shipped", "delivered", "canceled"].includes(rawStatus)) {
            status = rawStatus as KanbanStatus;
          }

          const items: OrderItemDetail[] = (raw.items || []).map((it: any, idx: number) => ({
            id: String(it.id || idx),
            title: it.product_title || it.title || "محصول فروشگاه",
            sku: it.sku || `SKU-${idx + 1}`,
            quantity: it.quantity || 1,
            unitPrice: it.unit_price || it.price || 0,
            totalPrice: (it.unit_price || it.price || 0) * (it.quantity || 1),
          }));

          return {
            id: String(raw.id || `order-${index}`),
            orderNumber: raw.order_number || raw.orderNumber || `ORD-20260909-${1000 + index}`,
            customerName: raw.user?.name || raw.customer_name || raw.customerName || "کاربر فروشگاه",
            customerPhone: raw.user?.phone || raw.customer_phone || raw.phone || "09120000000",
            customerEmail: raw.user?.email || raw.email,
            createdAt: raw.created_at || raw.createdAt || new Date().toISOString(),
            subtotal: raw.subtotal || raw.total || 0,
            shippingCost: raw.shipping_cost || 0,
            discount: raw.discount_amount || raw.discount || 0,
            total: raw.total || raw.total_price || 0,
            status,
            paymentStatus: raw.payment_status || "paid",
            paymentMethod: raw.payment_method || "درگاه اینترنتی",
            trackingCode: raw.tracking_code || raw.tracking_number,
            shippingAddress: {
              recipientName: raw.shipping_address?.receiver_name || raw.shipping_address_snapshot?.recipient_name || raw.customer_name || "تحویل‌گیرنده",
              phone: raw.shipping_address?.phone || raw.phone || "09120000000",
              province: raw.shipping_address?.province || "تهران",
              city: raw.shipping_address?.city || "تهران",
              postalCode: raw.shipping_address?.postal_code || "",
              fullAddress: raw.shipping_address?.full_address || raw.shipping_address?.address || "نشانی ثبت شده در پروفایل",
            },
            items: items.length > 0 ? items : [
              {
                id: `default-it-${index}`,
                title: "اقلام فاکتور سفارش",
                sku: "SKU-GEN",
                quantity: raw.item_count || 1,
                unitPrice: raw.total || 0,
                totalPrice: raw.total || 0,
              },
            ],
          };
        });

        setOrders(mappedOrders);
        if (isManual) {
          toast({
            title: "بروزرسانی زنده انجام شد",
            description: `${toPersianDigits(mappedOrders.length)} سفارش با موفقیت از سرور دریافت گردید.`,
            variant: "success",
          });
        }
      } else {
        // Empty response from API: keep realistic fallback mock data
        if (isManual) {
          toast({
            title: "داده‌های میز کانبان همگام شد",
            description: "لیست سفارشات بر اساس پایپ‌لاین به‌روز است.",
          });
        }
      }
      setLastRefreshed(new Date());
    } catch {
      // Backend not running or error: fallback remains active
      if (isManual) {
        toast({
          title: "وضعیت آفلاین / پیش‌فرض",
          description: "اتصال به پایگاه داده برقرار نشد، داده‌های نمایشی حفظ گردیدند.",
        });
      }
    } finally {
      setIsRefreshing(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchOrdersFromApi();
  }, [fetchOrdersFromApi]);

  /* ------------------------------------------------------------------ */
  /*  Forward Action: PATCH /admin/orders/{id}/status                   */
  /* ------------------------------------------------------------------ */

  const handleAdvanceStatus = async (order: KanbanOrder, nextStatus: KanbanStatus) => {
    setUpdatingOrderId(order.id);
    try {
      // API call to PATCH /admin/orders/{id}/status
      await apiClient
        .patch(`/admin/orders/${order.id}/status`, { status: nextStatus })
        .catch(() =>
          apiClient.patch(`/orders/admin/orders/${order.id}/status`, {
            status: nextStatus,
          })
        )
        .catch(() =>
          apiClient.patch(`/orders/${order.id}/status`, { status: nextStatus })
        )
        .catch(() => null);

      // Optimistic state update
      setOrders((prev) =>
        prev.map((o) => (o.id === order.id ? { ...o, status: nextStatus } : o))
      );

      const targetCol = PIPELINE_COLUMNS.find((c) => c.id === nextStatus);
      toast({
        title: "وضعیت سفارش ارتقا یافت",
        description: `سفارش ${order.orderNumber} با موفقیت به مرحله «${targetCol?.title || nextStatus}» انتقال یافت.`,
        variant: "success",
      });

      if (selectedOrder && selectedOrder.id === order.id) {
        setSelectedOrder((prev) => (prev ? { ...prev, status: nextStatus } : null));
      }
    } catch (err: any) {
      toast({
        title: "خطا در تغییر وضعیت",
        description: err?.message || "امکان انتقال وضعیت سفارش در سرور وجود نداشت.",
        variant: "destructive",
      });
    } finally {
      setUpdatingOrderId(null);
    }
  };

  /* ------------------------------------------------------------------ */
  /*  Cancel Action: State Machine Guarded                              */
  /* ------------------------------------------------------------------ */

  const handleConfirmCancel = async () => {
    if (!cancelTargetOrder) return;
    setIsCanceling(true);

    try {
      await apiClient
        .patch(`/admin/orders/${cancelTargetOrder.id}/status`, {
          status: "canceled",
          notes: cancelReason,
        })
        .catch(() =>
          apiClient.patch(
            `/orders/admin/orders/${cancelTargetOrder.id}/status`,
            { status: "canceled", notes: cancelReason }
          )
        )
        .catch(() => null);

      setOrders((prev) =>
        prev.map((o) =>
          o.id === cancelTargetOrder.id ? { ...o, status: "canceled" } : o
        )
      );

      toast({
        title: "سفارش لغو گردید",
        description: `سفارش شماره ${cancelTargetOrder.orderNumber} با علت «${cancelReason}» لغو شد.`,
        variant: "default",
      });

      setCancelTargetOrder(null);
    } catch (err: any) {
      toast({
        title: "خطا در لغو سفارش",
        description: err?.message || "امکان لغو سفارش وجود نداشت.",
        variant: "destructive",
      });
    } finally {
      setIsCanceling(false);
    }
  };

  /* ------------------------------------------------------------------ */
  /*  Copy Order Number Helper                                          */
  /* ------------------------------------------------------------------ */

  const handleCopyOrderNumber = (e: React.MouseEvent, orderNumber: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(orderNumber);
    setCopiedOrderId(orderNumber);
    setTimeout(() => setCopiedOrderId(null), 2000);
  };

  /* ------------------------------------------------------------------ */
  /*  Filtered Orders & Stats Computation                              */
  /* ------------------------------------------------------------------ */

  const filteredOrders = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return orders.filter((o) => {
      // Exclude canceled from kanban columns
      if (o.status === "canceled") return false;

      const matchesQuery =
        !q ||
        o.orderNumber.toLowerCase().includes(q) ||
        o.customerName.toLowerCase().includes(q) ||
        o.customerPhone.includes(q);

      if (!matchesQuery) return false;

      if (showOnlyStale) {
        return checkIsOrderStale(o);
      }

      return true;
    });
  }, [orders, searchQuery, showOnlyStale]);

  // Overall pipeline metrics
  const stats = useMemo(() => {
    const activeOrders = orders.filter((o) => o.status !== "canceled");
    const staleOrders = activeOrders.filter((o) => checkIsOrderStale(o));
    const totalPipelineValue = activeOrders.reduce((sum, o) => sum + o.total, 0);
    const deliveredCount = orders.filter((o) => o.status === "delivered").length;

    return {
      activeCount: activeOrders.length,
      staleCount: staleOrders.length,
      totalPipelineValue,
      deliveredCount,
    };
  }, [orders]);

  return (
    <div className="space-y-6" dir="rtl">
      {/* ───────────────────────────────────────────────────────────── */}
      {/* Page Header                                                   */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary shadow-sm ring-1 ring-primary/20">
              <Kanban className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                میز کانبان سفارشات
              </h1>
              <p className="text-xs text-muted-foreground sm:text-sm">
                خط پردازش و تکمیل سفارشات (Fulfillment Pipeline) با قابلیت انتقال وضعیت و پایش تاخیرها
              </p>
            </div>
          </div>
        </div>

        {/* Top Action Controls */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3">
          <span className="text-[11px] text-muted-foreground hidden sm:inline">
            آخرین همگام‌سازی:{" "}
            <span className="font-mono">
              {toPersianDigits(
                lastRefreshed.toLocaleTimeString("fa-IR", {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })
              )}
            </span>
          </span>

          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchOrdersFromApi(true)}
            disabled={isRefreshing}
            className="gap-2 border-border text-xs font-medium shadow-sm transition-all hover:bg-muted"
          >
            <RefreshCw
              className={cn(
                "h-3.5 w-3.5 text-primary",
                isRefreshing && "animate-spin text-primary"
              )}
            />
            <span>{isRefreshing ? "در حال دریافت..." : "بروزرسانی زنده"}</span>
          </Button>

          <Link href="/admin/orders">
            <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground hover:text-foreground">
              <FileText className="h-3.5 w-3.5" />
              <span>نمای جدول</span>
            </Button>
          </Link>
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* KPI Overview Strip                                             */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 sm:gap-4">
        {/* Total in Pipeline */}
        <Card className="p-3.5 sm:p-4 border-border/80 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground">کل سفارشات در گردش</span>
            <p className="text-xl font-bold font-mono text-foreground">
              {toPersianDigits(stats.activeCount)} <span className="text-xs font-normal text-muted-foreground">سفارش</span>
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Layers className="h-5 w-5" />
          </div>
        </Card>

        {/* Stale Orders Warning KPI */}
        <Card
          className={cn(
            "p-3.5 sm:p-4 border-border/80 shadow-sm flex items-center justify-between cursor-pointer transition-all",
            stats.staleCount > 0
              ? "border-amber-500/50 bg-amber-50/40 dark:bg-amber-950/20 ring-1 ring-amber-500/30"
              : ""
          )}
          onClick={() => setShowOnlyStale((prev) => !prev)}
          title="کلیک برای فیلتر سفارش‌های دارای تاخیر"
        >
          <div className="space-y-1">
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-medium text-amber-700 dark:text-amber-400">
                سفارشات معوق (+۲۴ ساعت)
              </span>
              {stats.staleCount > 0 && (
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500"></span>
                </span>
              )}
            </div>
            <p className="text-xl font-bold font-mono text-amber-600 dark:text-amber-400">
              {toPersianDigits(stats.staleCount)}{" "}
              <span className="text-xs font-normal text-amber-600/80">مورد بحرانی</span>
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 text-amber-600 dark:bg-amber-950 dark:text-amber-400">
            <AlertTriangle className="h-5 w-5" />
          </div>
        </Card>

        {/* Delivered Orders */}
        <Card className="p-3.5 sm:p-4 border-border/80 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground">تحویل موفق</span>
            <p className="text-xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
              {toPersianDigits(stats.deliveredCount)}{" "}
              <span className="text-xs font-normal text-muted-foreground">سفارش</span>
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </Card>

        {/* Total Pipeline Monetary Value */}
        <Card className="p-3.5 sm:p-4 border-border/80 shadow-sm flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-muted-foreground">ارزش کل پایپ‌لاین</span>
            <p className="text-sm font-bold font-mono text-foreground sm:text-base">
              {formatPrice(stats.totalPipelineValue)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
            <CircleDollarSign className="h-5 w-5" />
          </div>
        </Card>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* Filter & Search Bar                                           */}
      {/* ───────────────────────────────────────────────────────────── */}
      <Card className="p-3 sm:p-4 border-border/80 shadow-sm bg-card/60 backdrop-blur">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Search Bar */}
          <div className="relative flex-1">
            <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو در شناسه سفارش، نام مشتری یا تلفن تماس..."
              className="pr-9 text-xs sm:text-sm h-9 bg-background/80"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute left-3 top-2.5 text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Quick Filter Buttons */}
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={showOnlyStale ? "default" : "outline"}
              size="sm"
              onClick={() => setShowOnlyStale((v) => !v)}
              className={cn(
                "h-9 gap-1.5 text-xs transition-all",
                showOnlyStale
                  ? "bg-amber-600 hover:bg-amber-700 text-white"
                  : "border-border text-muted-foreground hover:text-foreground"
              )}
            >
              <AlertTriangle className="h-3.5 w-3.5" />
              <span>فقط سفارش‌های معوق (+۲۴ ساعت)</span>
              {stats.staleCount > 0 && (
                <Badge
                  variant="secondary"
                  className={cn(
                    "mr-1 h-5 px-1.5 text-[10px] font-mono",
                    showOnlyStale ? "bg-white/20 text-white" : "bg-amber-100 text-amber-800"
                  )}
                >
                  {toPersianDigits(stats.staleCount)}
                </Badge>
              )}
            </Button>

            {(searchQuery || showOnlyStale) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setSearchQuery("");
                  setShowOnlyStale(false);
                }}
                className="h-9 gap-1 text-xs text-muted-foreground hover:text-destructive"
              >
                <X className="h-3.5 w-3.5" />
                <span>حذف فیلترها</span>
              </Button>
            )}
          </div>
        </div>

        {/* Active Alert Banner if any orders are stale */}
        {stats.staleCount > 0 && !showOnlyStale && (
          <div className="mt-3 flex items-center justify-between rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
            <div className="flex items-center gap-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 animate-pulse" />
              <span>
                توجه: <strong>{toPersianDigits(stats.staleCount)}</strong> سفارش بیش از ۲۴ ساعت در مراحل انتظار یا پردازش معطل مانده‌اند و نیازمند پیگیری فوری هستند.
              </span>
            </div>
            <button
              onClick={() => setShowOnlyStale(true)}
              className="text-[11px] font-bold underline hover:text-amber-900 dark:hover:text-amber-100"
            >
              مشاهده موارد معوق
            </button>
          </div>
        )}
      </Card>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* Visual Kanban Fulfillment Board (6 Columns)                    */}
      {/* ───────────────────────────────────────────────────────────── */}
      <div className="overflow-x-auto pb-6">
        <div className="flex min-w-[1720px] gap-4 items-start">
          {PIPELINE_COLUMNS.map((col) => {
            const columnOrders = filteredOrders.filter((o) => o.status === col.id);
            const columnTotalValue = columnOrders.reduce((acc, o) => acc + o.total, 0);
            const columnStaleCount = columnOrders.filter(checkIsOrderStale).length;

            return (
              <div
                key={col.id}
                className="flex-1 flex flex-col rounded-2xl border border-border/80 bg-muted/20 shadow-sm overflow-hidden"
              >
                {/* Column Top Indicator Line */}
                <div className={cn("h-1.5 w-full", col.color.indicator)} />

                {/* Column Header */}
                <div className={cn("p-3.5 border-b border-border/60", col.color.bgMuted)}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2">
                      <span className={cn("h-2.5 w-2.5 rounded-full", col.color.indicator)} />
                      <h3 className="text-sm font-bold text-foreground">{col.title}</h3>
                    </div>

                    <div className="flex items-center gap-1.5">
                      {columnStaleCount > 0 && (
                        <Badge
                          variant="destructive"
                          className="h-5 px-1.5 text-[10px] font-mono gap-1 animate-pulse"
                          title={`${toPersianDigits(columnStaleCount)} سفارش معوق`}
                        >
                          <AlertTriangle className="h-2.5 w-2.5" />
                          {toPersianDigits(columnStaleCount)}
                        </Badge>
                      )}
                      <Badge
                        variant="outline"
                        className={cn("h-5 px-2 text-[11px] font-mono font-bold", col.color.badge)}
                      >
                        {toPersianDigits(columnOrders.length)}
                      </Badge>
                    </div>
                  </div>

                  {/* Subtitle & Column Sum */}
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span className="truncate max-w-[160px]">{col.subtitle}</span>
                    <span className="font-mono text-foreground/80 font-medium">
                      {formatPrice(columnTotalValue)}
                    </span>
                  </div>
                </div>

                {/* Column Cards Container */}
                <div className="p-3 space-y-3 min-h-[500px] flex-1 flex flex-col">
                  {columnOrders.length === 0 ? (
                    <div className="flex-1 flex flex-col items-center justify-center rounded-xl border border-dashed border-border/70 p-6 text-center text-muted-foreground/60">
                      <ShoppingBag className="h-8 w-8 mb-2 stroke-[1.25] text-muted-foreground/40" />
                      <p className="text-xs">سفارشی در این ستون نیست</p>
                      <span className="text-[10px] text-muted-foreground/50 mt-0.5">
                        جریان تکمیل آماده دریافت سفارش
                      </span>
                    </div>
                  ) : (
                    columnOrders.map((order) => {
                      const isStale = checkIsOrderStale(order);
                      const elapsedHours = getElapsedHours(order.createdAt);
                      const isUpdating = updatingOrderId === order.id;

                      return (
                        <div
                          key={order.id}
                          className={cn(
                            "group relative rounded-xl border bg-card p-3.5 shadow-sm transition-all duration-200 hover:shadow-md",
                            isStale
                              ? "border-amber-500 ring-2 ring-amber-500/40 bg-gradient-to-b from-amber-50/40 to-transparent dark:from-amber-950/20 dark:to-transparent"
                              : "border-border/80 hover:border-primary/40"
                          )}
                        >
                          {/* Stale Alert Header Badge */}
                          {isStale && (
                            <div className="mb-2 flex items-center justify-between rounded-lg bg-amber-500/15 px-2.5 py-1 text-[11px] font-semibold text-amber-700 dark:text-amber-300 border border-amber-500/30">
                              <span className="flex items-center gap-1.5">
                                <AlertTriangle className="h-3.5 w-3.5 text-amber-600 animate-bounce" />
                                <span>هشدار تاخیر بیش از ۲۴ ساعت</span>
                              </span>
                              <span className="font-mono text-[10px] bg-amber-500/20 px-1.5 py-0.5 rounded">
                                {toPersianDigits(elapsedHours)}h+
                              </span>
                            </div>
                          )}

                          {/* Card Header: Order Number & Relative Time */}
                          <div className="flex items-start justify-between gap-2 mb-2">
                            <div className="flex items-center gap-1.5">
                              <span className="font-mono text-xs font-bold text-foreground">
                                {order.orderNumber}
                              </span>
                              <button
                                type="button"
                                onClick={(e) => handleCopyOrderNumber(e, order.orderNumber)}
                                className="text-muted-foreground/70 hover:text-foreground transition-colors p-0.5"
                                title="کپی شماره سفارش"
                              >
                                {copiedOrderId === order.orderNumber ? (
                                  <Check className="h-3 w-3 text-emerald-600" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            </div>

                            {/* Relative Time Badge */}
                            <div
                              className="flex items-center gap-1 text-[11px] text-muted-foreground whitespace-nowrap"
                              title={formatPersianFullDate(order.createdAt)}
                            >
                              <Clock className="h-3 w-3 text-muted-foreground/70" />
                              <span>{formatPersianRelativeTime(order.createdAt)}</span>
                            </div>
                          </div>

                          {/* Customer Information */}
                          <div className="space-y-1 rounded-lg bg-muted/40 p-2.5 mb-2.5 text-xs">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-1.5 font-medium text-foreground">
                                <User className="h-3.5 w-3.5 text-primary/80" />
                                <span className="truncate max-w-[140px]">{order.customerName}</span>
                              </div>
                              <span className="text-[10px] text-muted-foreground">
                                {order.shippingAddress.city}
                              </span>
                            </div>

                            <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
                              <span className="flex items-center gap-1 font-mono" dir="ltr">
                                <Phone className="h-3 w-3 text-muted-foreground/60" />
                                {toPersianDigits(order.customerPhone)}
                              </span>
                              <span className="text-[10px] text-emerald-600 font-medium">
                                {order.paymentStatus === "paid" ? "پرداخت شده" : "در انتظار پرداخت"}
                              </span>
                            </div>
                          </div>

                          {/* Order Metadata: Items count & Grand Total */}
                          <div className="flex items-center justify-between pt-1 pb-2.5 border-b border-border/60 text-xs">
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Package className="h-3.5 w-3.5 text-muted-foreground/70" />
                              <span className="font-mono">
                                {toPersianDigits(
                                  order.items.reduce((s, it) => s + (it.quantity || 1), 0)
                                )}{" "}
                                قلم کالا
                              </span>
                            </div>

                            <div className="font-bold text-foreground font-mono text-sm">
                              {formatPrice(order.total)}
                            </div>
                          </div>

                          {/* Card Footer Actions: Details, Cancel, Forward */}
                          <div className="mt-3 flex items-center justify-between gap-1.5">
                            {/* View Details Button */}
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setSelectedOrder(order);
                                setIsDetailsOpen(true);
                              }}
                              className="h-8 px-2.5 text-[11px] gap-1 border-border/70 hover:bg-muted font-medium"
                              title="مشاهده فاکتور و اقلام"
                            >
                              <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                              <span>جزئیات</span>
                            </Button>

                            <div className="flex items-center gap-1.5">
                              {/* Cancel Button (guarded by state machine: pending & confirmed) */}
                              {col.allowCancel && (
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setCancelTargetOrder(order)}
                                  disabled={isUpdating}
                                  className="h-8 px-2 text-[11px] text-destructive/80 hover:text-destructive hover:bg-destructive/10"
                                  title="لغو سفارش"
                                >
                                  <XCircle className="h-3.5 w-3.5" />
                                  <span className="hidden sm:inline">لغو</span>
                                </Button>
                              )}

                              {/* Forward Action Button */}
                              {col.nextStatus && col.nextActionLabel ? (
                                <Button
                                  type="button"
                                  size="sm"
                                  onClick={() => handleAdvanceStatus(order, col.nextStatus!)}
                                  disabled={isUpdating}
                                  className={cn(
                                    "h-8 px-3 text-[11px] gap-1 shadow-sm font-semibold transition-transform active:scale-95",
                                    col.color.button
                                  )}
                                >
                                  {isUpdating ? (
                                    <RefreshCw className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <>
                                      <span>{col.nextActionLabel}</span>
                                      <ChevronLeft className="h-3 w-3" />
                                    </>
                                  )}
                                </Button>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 font-medium px-2 py-1 bg-emerald-50 dark:bg-emerald-950/40 rounded-lg">
                                  <CheckCircle2 className="h-3.5 w-3.5" />
                                  تکمیل شد
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* MODAL: View Order Details                                      */}
      {/* ───────────────────────────────────────────────────────────── */}
      <Dialog open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between text-base sm:text-lg">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                <span>جزئیات و اقلام سفارش {selectedOrder?.orderNumber}</span>
              </div>
              {selectedOrder && (
                <Badge
                  variant="outline"
                  className={cn(
                    "font-medium text-xs",
                    PIPELINE_COLUMNS.find((c) => c.id === selectedOrder.status)?.color.badge
                  )}
                >
                  {PIPELINE_COLUMNS.find((c) => c.id === selectedOrder.status)?.title ||
                    selectedOrder.status}
                </Badge>
              )}
            </DialogTitle>
            <DialogDescription>
              اطلاعات خریدار، نشانی پستی تحویل، فاکتور مالی و اقلام سبد خرید
            </DialogDescription>
          </DialogHeader>

          {selectedOrder && (
            <div className="space-y-5 py-2">
              {/* Quick Status Bar */}
              <div className="grid grid-cols-2 gap-3 rounded-xl border border-border/80 bg-muted/40 p-3.5 text-xs sm:grid-cols-4">
                <div>
                  <span className="text-muted-foreground block mb-0.5">تاریخ ثبت سفارش:</span>
                  <span className="font-semibold text-foreground font-mono">
                    {formatPersianFullDate(selectedOrder.createdAt)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block mb-0.5">روش پرداخت:</span>
                  <span className="font-semibold text-foreground">
                    {selectedOrder.paymentMethod}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block mb-0.5">وضعیت پرداخت:</span>
                  <span className="font-semibold text-emerald-600">
                    {selectedOrder.paymentStatus === "paid" ? "پرداخت تایید شده" : "در انتظار پرداخت"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block mb-0.5">کد رهگیری پستی:</span>
                  <span className="font-mono font-bold text-foreground">
                    {selectedOrder.trackingCode || "هنوز صادر نشده"}
                  </span>
                </div>
              </div>

              {/* Customer & Address cards */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="rounded-xl border border-border p-3.5 space-y-2 bg-card">
                  <div className="flex items-center gap-2 text-xs font-bold text-foreground border-b pb-2">
                    <User className="h-4 w-4 text-primary" />
                    مشخصات مشتری
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <p className="font-medium text-foreground">{selectedOrder.customerName}</p>
                    <p className="text-muted-foreground flex items-center gap-1.5 font-mono" dir="ltr">
                      <Phone className="h-3 w-3" />
                      {toPersianDigits(selectedOrder.customerPhone)}
                    </p>
                    {selectedOrder.customerEmail && (
                      <p className="text-muted-foreground flex items-center gap-1.5 font-mono" dir="ltr">
                        <Mail className="h-3 w-3" />
                        {selectedOrder.customerEmail}
                      </p>
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-border p-3.5 space-y-2 bg-card">
                  <div className="flex items-center gap-2 text-xs font-bold text-foreground border-b pb-2">
                    <MapPin className="h-4 w-4 text-primary" />
                    نشانی تحویل گیرنده
                  </div>
                  <div className="space-y-1.5 text-xs">
                    <p className="text-foreground">
                      گیرنده:{" "}
                      <span className="font-medium">
                        {selectedOrder.shippingAddress.recipientName}
                      </span>
                    </p>
                    <p className="text-foreground leading-relaxed">
                      {selectedOrder.shippingAddress.province}، {selectedOrder.shippingAddress.city}،{" "}
                      {selectedOrder.shippingAddress.fullAddress}
                    </p>
                    {selectedOrder.shippingAddress.postalCode && (
                      <p className="text-muted-foreground font-mono" dir="ltr">
                        کد پستی: {toPersianDigits(selectedOrder.shippingAddress.postalCode)}
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Order Items Table */}
              <div className="space-y-2">
                <h4 className="text-xs font-bold text-foreground">اقلام فاکتور خرید</h4>
                <div className="overflow-hidden rounded-xl border border-border">
                  <table className="w-full text-right text-xs">
                    <thead className="bg-muted/60 text-muted-foreground border-b border-border">
                      <tr>
                        <th className="py-2.5 px-3">عنوان محصول</th>
                        <th className="py-2.5 px-3">کد انبار (SKU)</th>
                        <th className="py-2.5 px-3 text-center">تعداد</th>
                        <th className="py-2.5 px-3">قیمت واحد</th>
                        <th className="py-2.5 px-3 text-left">مجموع</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {selectedOrder.items.map((item) => (
                        <tr key={item.id} className="hover:bg-muted/20">
                          <td className="py-2.5 px-3 font-medium text-foreground">{item.title}</td>
                          <td className="py-2.5 px-3 font-mono text-muted-foreground" dir="ltr">
                            {item.sku}
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono font-bold">
                            {toPersianDigits(item.quantity)}
                          </td>
                          <td className="py-2.5 px-3 font-mono">{formatPrice(item.unitPrice)}</td>
                          <td className="py-2.5 px-3 font-mono font-bold text-left">
                            {formatPrice(item.totalPrice)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Financial Calculation */}
              <div className="flex justify-end">
                <div className="w-full sm:w-72 rounded-xl border border-border/80 p-3.5 space-y-2 bg-muted/20 text-xs">
                  <div className="flex justify-between text-muted-foreground">
                    <span>جمع اقلام:</span>
                    <span className="font-mono">{formatPrice(selectedOrder.subtotal)}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>هزینه ارسال:</span>
                    <span className="font-mono">
                      {selectedOrder.shippingCost === 0
                        ? "رایگان"
                        : formatPrice(selectedOrder.shippingCost)}
                    </span>
                  </div>
                  {selectedOrder.discount > 0 && (
                    <div className="flex justify-between text-emerald-600">
                      <span>تخفیف:</span>
                      <span className="font-mono">- {formatPrice(selectedOrder.discount)}</span>
                    </div>
                  )}
                  <Separator />
                  <div className="flex justify-between text-sm font-bold text-foreground pt-1">
                    <span>مبلغ کل فاکتور:</span>
                    <span className="font-mono text-primary">
                      {formatPrice(selectedOrder.total)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button variant="outline" onClick={() => setIsDetailsOpen(false)}>
              بستن
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ───────────────────────────────────────────────────────────── */}
      {/* MODAL: Cancel Order Confirmation                              */}
      {/* ───────────────────────────────────────────────────────────── */}
      <Dialog
        open={Boolean(cancelTargetOrder)}
        onOpenChange={(open) => !open && setCancelTargetOrder(null)}
      >
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertCircle className="h-5 w-5" />
              لغو سفارش {cancelTargetOrder?.orderNumber}
            </DialogTitle>
            <DialogDescription>
              آیا از لغو این سفارش اطمینان دارید؟ این عملیات قابل بازگشت نخواهد بود و وضعیت سفارش به
              «لغو شده» تغییر می‌یابد.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <label className="font-medium text-foreground block">دلیل لغو سفارش:</label>
            <Select value={cancelReason} onValueChange={setCancelReason}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="درخواست مشتری">درخواست مشتری</SelectItem>
                <SelectItem value="عدم تایید یا خطای تراکنش بانکی">عدم تایید یا خطای تراکنش بانکی</SelectItem>
                <SelectItem value="کسری موجودی در انبار">کسری موجودی در انبار</SelectItem>
                <SelectItem value="ثبت اطلاعات نادرست تماس یا آدرس">ثبت اطلاعات نادرست تماس یا آدرس</SelectItem>
                <SelectItem value="انصراف پیش از پردازش">انصراف پیش از پردازش</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => setCancelTargetOrder(null)}
              disabled={isCanceling}
            >
              انصراف
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmCancel}
              disabled={isCanceling}
              className="gap-1.5"
            >
              {isCanceling ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <XCircle className="h-3.5 w-3.5" />
              )}
              <span>تایید لغو سفارش</span>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
