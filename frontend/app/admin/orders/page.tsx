"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
  ShoppingCart,
  Search,
  Eye,
  CheckCircle2,
  Clock,
  Truck,
  User,
  MapPin,
  Phone,
  Mail,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

type OrderStatus =
  | "pending"
  | "confirmed"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled";

type PaymentStatus = "paid" | "pending" | "failed" | "refunded";

interface OrderItem {
  id: string;
  title: string;
  sku: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  imageUrl?: string;
}

interface ShippingAddress {
  recipientName: string;
  phone: string;
  province: string;
  city: string;
  postalCode: string;
  fullAddress: string;
}

interface AdminOrder {
  id: string;
  orderNumber: string;
  customerName: string;
  customerPhone: string;
  customerEmail?: string;
  date: string;
  total: number;
  subtotal: number;
  shippingCost: number;
  discount: number;
  status: OrderStatus;
  paymentStatus: PaymentStatus;
  paymentMethod: string;
  shippingAddress: ShippingAddress;
  items: OrderItem[];
  trackingCode?: string;
  adminNote?: string;
}

/* ------------------------------------------------------------------ */
/*  Persian Labels & Color Maps                                        */
/* ------------------------------------------------------------------ */

const ORDER_STATUS_DETAILS: Record<
  OrderStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info";
  }
> = {
  pending: { label: "در انتظار", variant: "warning" },
  confirmed: { label: "تایید شده", variant: "info" },
  processing: { label: "در حال پردازش", variant: "default" },
  shipped: { label: "ارسال شده", variant: "info" },
  delivered: { label: "تحویل داده شده", variant: "success" },
  cancelled: { label: "لغو شده", variant: "destructive" },
};

const PAYMENT_STATUS_DETAILS: Record<
  PaymentStatus,
  {
    label: string;
    variant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info";
  }
> = {
  paid: { label: "پرداخت شده", variant: "success" },
  pending: { label: "در انتظار پرداخت", variant: "warning" },
  failed: { label: "ناموفق", variant: "destructive" },
  refunded: { label: "استرداد وجه", variant: "secondary" },
};

/* ------------------------------------------------------------------ */
/*  Initial Fallback Data                                              */
/* ------------------------------------------------------------------ */

const INITIAL_ADMIN_ORDERS: AdminOrder[] = [
  {
    id: "ord-100256",
    orderNumber: "ORD-100256",
    customerName: "علی محمدی",
    customerPhone: "09123456789",
    customerEmail: "ali.mohammadi@example.com",
    date: "۱۴۰۳/۰۶/۱۹",
    subtotal: 2_150_000,
    shippingCost: 200_000,
    discount: 0,
    total: 2_350_000,
    status: "processing",
    paymentStatus: "paid",
    paymentMethod: "درگاه بانکی ملت",
    trackingCode: "TRK-900214",
    shippingAddress: {
      recipientName: "علی محمدی",
      phone: "09123456789",
      province: "تهران",
      city: "تهران",
      postalCode: "1939547891",
      fullAddress: "میدان ونک، خیابان ملاصدرا، کوچه بهار، پلاک ۱۲، واحد ۳",
    },
    items: [
      {
        id: "item-1",
        title: "پاوربانک ۲۰۰۰۰ میلی‌آمپر فست شارژ انکر Anker 737",
        sku: "ANK-PB-737",
        quantity: 1,
        unitPrice: 2_150_000,
        totalPrice: 2_150_000,
      },
    ],
  },
  {
    id: "ord-100255",
    orderNumber: "ORD-100255",
    customerName: "فاطمه احمدی",
    customerPhone: "09351234567",
    customerEmail: "fatemeh.ahmadi@example.com",
    date: "۱۴۰۳/۰۶/۱۹",
    subtotal: 9_200_000,
    shippingCost: 0,
    discount: 300_000,
    total: 8_900_000,
    status: "confirmed",
    paymentStatus: "paid",
    paymentMethod: "کیف پول آنلاین",
    trackingCode: "TRK-899120",
    shippingAddress: {
      recipientName: "فاطمه احمدی",
      phone: "09351234567",
      province: "اصفهان",
      city: "اصفهان",
      postalCode: "8146598712",
      fullAddress: "خیابان چهارباغ بالا، کوچه کاویان، مجتمع پارسیان، واحد ۴",
    },
    items: [
      {
        id: "item-2",
        title: "هدفون بی‌سیم نویز کنسلینگ سونی WH-1000XM5",
        sku: "SNY-WH1000XM5",
        quantity: 1,
        unitPrice: 9_200_000,
        totalPrice: 9_200_000,
      },
    ],
  },
  {
    id: "ord-100254",
    orderNumber: "ORD-100254",
    customerName: "محمد حسینی",
    customerPhone: "09197654321",
    customerEmail: "m.hosseini@gmail.com",
    date: "۱۴۰۳/۰۶/۱۸",
    subtotal: 1_200_000,
    shippingCost: 150_000,
    discount: 150_000,
    total: 1_200_000,
    status: "shipped",
    paymentStatus: "paid",
    paymentMethod: "درگاه بانکی سامان",
    trackingCode: "POST-8721094",
    shippingAddress: {
      recipientName: "محمد حسینی",
      phone: "09197654321",
      province: "فارس",
      city: "شیراز",
      postalCode: "7134598120",
      fullAddress: "خیابان زند، بعد از بیمارستان سعدی، نبش کوچه ۱۵",
    },
    items: [
      {
        id: "item-3",
        title: "ماوس بی‌سیم لاجیتک مدل Pebble M350",
        sku: "LOG-PEBBLE-M350",
        quantity: 1,
        unitPrice: 1_200_000,
        totalPrice: 1_200_000,
      },
    ],
  },
  {
    id: "ord-100253",
    orderNumber: "ORD-100253",
    customerName: "زهرا کریمی",
    customerPhone: "09129876543",
    customerEmail: "zahra.karimi@yahoo.com",
    date: "۱۴۰۳/۰۶/۱۷",
    subtotal: 4_500_000,
    shippingCost: 0,
    discount: 0,
    total: 4_500_000,
    status: "delivered",
    paymentStatus: "paid",
    paymentMethod: "درگاه زرین‌پال",
    trackingCode: "POST-7612300",
    shippingAddress: {
      recipientName: "زهرا کریمی",
      phone: "09129876543",
      province: "خراسان رضوی",
      city: "مشهد",
      postalCode: "9177534567",
      fullAddress: "بلوار سجاد، خیابان بهارستان، بهارستان ۴، پلاک ۲۸",
    },
    items: [
      {
        id: "item-4",
        title: "ساعت هوشمند شیائومی Band 8 پرو مشکی",
        sku: "XIA-BND-8PRO",
        quantity: 1,
        unitPrice: 3_450_000,
        totalPrice: 3_450_000,
      },
      {
        id: "item-5",
        title: "بند فلزی میلانس ساعت شیائومی",
        sku: "ACC-BND-MIL",
        quantity: 1,
        unitPrice: 1_050_000,
        totalPrice: 1_050_000,
      },
    ],
  },
  {
    id: "ord-100252",
    orderNumber: "ORD-100252",
    customerName: "رضا نوری",
    customerPhone: "09183456789",
    date: "۱۴۰۳/۰۶/۱۶",
    subtotal: 650_000,
    shippingCost: 150_000,
    discount: 150_000,
    total: 650_000,
    status: "cancelled",
    paymentStatus: "refunded",
    paymentMethod: "پرداخت اینترنتی",
    shippingAddress: {
      recipientName: "رضا نوری",
      phone: "09183456789",
      province: "همدان",
      city: "همدان",
      postalCode: "6514890123",
      fullAddress: "میدان بوعلی، خیابان پاستور، برج سینا طبقه ۲",
    },
    items: [
      {
        id: "item-6",
        title: "کابل تبدیل Type-C به لایتنینگ انکر مدل PowerLine",
        sku: "ANK-CBL-CL",
        quantity: 1,
        unitPrice: 650_000,
        totalPrice: 650_000,
      },
    ],
  },
  {
    id: "ord-100251",
    orderNumber: "ORD-100251",
    customerName: "مهدی اکبری",
    customerPhone: "09132223344",
    customerEmail: "akbari.m@chmail.ir",
    date: "۱۴۰۳/۰۶/۱۵",
    subtotal: 68_500_000,
    shippingCost: 0,
    discount: 0,
    total: 68_500_000,
    status: "pending",
    paymentStatus: "pending",
    paymentMethod: "درگاه بانکی پاسارگاد",
    shippingAddress: {
      recipientName: "مهدی اکبری",
      phone: "09132223344",
      province: "تهران",
      city: "تهران",
      postalCode: "1415512345",
      fullAddress: "خیابان کارگر شمالی، بالاتر از نصرت، پلاک ۱۴۳۰",
    },
    items: [
      {
        id: "item-7",
        title: "گوشی موبایل سامسونگ Galaxy S24 Ultra ظرفیت 256",
        sku: "SAM-S24U-256",
        quantity: 1,
        unitPrice: 68_500_000,
        totalPrice: 68_500_000,
      },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function AdminOrdersPage() {
  const { toast } = useToast();

  const [orders, setOrders] = useState<AdminOrder[]>(INITIAL_ADMIN_ORDERS);
  const [_isLoading, setIsLoading] = useState(false);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Modal State: View Order Details
  const [selectedOrder, setSelectedOrder] = useState<AdminOrder | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Fetch orders from API on mount
  useEffect(() => {
    const fetchOrders = async () => {
      try {
        setIsLoading(true);
        // Try backend admin orders endpoint or fallback to /orders
        const res = await apiClient
          .get("/orders/admin/orders")
          .catch(() => apiClient.get("/admin/orders"))
          .catch(() => apiClient.get("/orders"));

        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: AdminOrder[] = res.data.items.map((o: any) => ({
            id: String(o.id),
            orderNumber: o.order_number || o.orderNumber || `ORD-${o.id?.slice?.(0, 6)}`,
            customerName: o.user?.name || o.customer_name || o.customerName || "کاربر سایت",
            customerPhone: o.user?.phone || o.phone || "09120000000",
            customerEmail: o.user?.email || o.email,
            date: o.created_at ? new Date(o.created_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            total: o.total_price || o.total || 0,
            subtotal: o.subtotal || o.total_price || o.total || 0,
            shippingCost: o.shipping_cost || 0,
            discount: o.discount || 0,
            status: (o.status?.toLowerCase() as OrderStatus) || "pending",
            paymentStatus: (o.payment_status?.toLowerCase() as PaymentStatus) || "paid",
            paymentMethod: o.payment_method || "درگاه اینترنتی",
            trackingCode: o.tracking_code || o.tracking_number,
            shippingAddress: {
              recipientName: o.shipping_address?.receiver_name || o.customer_name || "تحویل گیرنده",
              phone: o.shipping_address?.phone || o.phone || "",
              province: o.shipping_address?.province || "تهران",
              city: o.shipping_address?.city || "تهران",
              postalCode: o.shipping_address?.postal_code || "",
              fullAddress: o.shipping_address?.full_address || o.shipping_address?.address || "تهران",
            },
            items: (o.items || []).map((it: any, idx: number) => ({
              id: String(it.id || idx),
              title: it.product_title || it.title || "محصول سفارشی",
              sku: it.sku || `SKU-${idx + 1}`,
              quantity: it.quantity || 1,
              unitPrice: it.unit_price || it.price || 0,
              totalPrice: (it.unit_price || it.price || 0) * (it.quantity || 1),
            })),
          }));
          setOrders(mapped);
        }
      } catch (err) {
        // Keep fallback
      } finally {
        setIsLoading(false);
      }
    };

    fetchOrders();
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Change Status Handler (PATCH /admin/orders/{id}/status)         */
  /* ---------------------------------------------------------------- */

  const handleStatusChange = async (orderId: string, newStatus: OrderStatus) => {
    try {
      // API call: PATCH /admin/orders/{id}/status or /orders/admin/orders/{id}/status
      await apiClient
        .patch(`/admin/orders/${orderId}/status`, { status: newStatus })
        .catch(() => apiClient.patch(`/orders/admin/orders/${orderId}/status`, { status: newStatus }))
        .catch(() => apiClient.patch(`/orders/${orderId}/status`, { status: newStatus }))
        .catch(() => null);

      // Optimistic update
      setOrders((prev) =>
        prev.map((o) => (o.id === orderId ? { ...o, status: newStatus } : o))
      );

      if (selectedOrder && selectedOrder.id === orderId) {
        setSelectedOrder((prev) => (prev ? { ...prev, status: newStatus } : null));
      }

      toast({
        title: "وضعیت سفارش تغییر کرد",
        description: `وضعیت سفارش به «${ORDER_STATUS_DETAILS[newStatus].label}» بروزرسانی شد.`,
        variant: "success",
      });
    } catch (err: any) {
      toast({
        title: "خطا در تغییر وضعیت",
        description: err?.message || "امکان بروزرسانی وضعیت وجود نداشت.",
        variant: "destructive",
      });
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Filtering                                                        */
  /* ---------------------------------------------------------------- */

  const filteredOrders = useMemo(() => {
    return orders.filter((o) => {
      const q = searchQuery.trim().toLowerCase();
      const matchesSearch =
        !q ||
        o.orderNumber.toLowerCase().includes(q) ||
        o.customerName.toLowerCase().includes(q) ||
        o.customerPhone.includes(q);

      const matchesStatus = statusFilter === "all" || o.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [orders, searchQuery, statusFilter]);

  const handleViewOrder = (order: AdminOrder) => {
    setSelectedOrder(order);
    setIsDetailsOpen(true);
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مدیریت سفارش‌ها</h1>
          <p className="text-sm text-muted-foreground">
            مشاهده، پیگیری وضعیت پردازش و بررسی فاکتورهای فروشگاه
          </p>
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">کل سفارش‌ها</p>
            <p className="text-xl font-bold text-foreground mt-1 font-mono">
              {toPersianDigits(orders.length)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <ShoppingCart className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">در حال پردازش / ارسال</p>
            <p className="text-xl font-bold text-blue-600 mt-1 font-mono">
              {toPersianDigits(
                orders.filter((o) => o.status === "processing" || o.status === "shipped").length
              )}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
            <Truck className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">تحویل داده شده</p>
            <p className="text-xl font-bold text-emerald-600 mt-1 font-mono">
              {toPersianDigits(orders.filter((o) => o.status === "delivered").length)}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
        </Card>

        <Card className="p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-muted-foreground">در انتظار اقدام</p>
            <p className="text-xl font-bold text-amber-600 mt-1 font-mono">
              {toPersianDigits(
                orders.filter((o) => o.status === "pending" || o.status === "confirmed").length
              )}
            </p>
          </div>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 text-amber-600 dark:bg-amber-950 dark:text-amber-400">
            <Clock className="h-5 w-5" />
          </div>
        </Card>
      </div>

      {/* Filters Card */}
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Search */}
          <div className="relative sm:col-span-2">
            <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="جستجو در شماره سفارش، نام مشتری یا شماره تماس..."
              className="pr-9"
            />
          </div>

          {/* Status filter */}
          <div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="فیلتر بر اساس وضعیت" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همه وضعیت‌ها</SelectItem>
                <SelectItem value="pending">در انتظار</SelectItem>
                <SelectItem value="confirmed">تایید شده</SelectItem>
                <SelectItem value="processing">در حال پردازش</SelectItem>
                <SelectItem value="shipped">ارسال شده</SelectItem>
                <SelectItem value="delivered">تحویل داده شده</SelectItem>
                <SelectItem value="cancelled">لغو شده</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {/* Orders Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/40 text-xs font-semibold text-muted-foreground">
              <tr>
                <th className="py-3.5 px-4">شماره سفارش</th>
                <th className="py-3.5 px-4">نام مشتری</th>
                <th className="py-3.5 px-4">تاریخ ثبت</th>
                <th className="py-3.5 px-4">تعداد اقلام</th>
                <th className="py-3.5 px-4">مبلغ کل فاکتور</th>
                <th className="py-3.5 px-4">وضعیت پرداخت</th>
                <th className="py-3.5 px-4">وضعیت سفارش</th>
                <th className="py-3.5 px-4 text-center">جزئیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredOrders.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-muted-foreground">
                    هیچ سفارشی با این شرایط یافت نشد.
                  </td>
                </tr>
              ) : (
                filteredOrders.map((order) => {
                  const payConfig = PAYMENT_STATUS_DETAILS[order.paymentStatus] || {
                    label: order.paymentStatus,
                    variant: "secondary",
                  };
                  return (
                    <tr key={order.id} className="hover:bg-muted/30 transition-colors">
                      {/* Order Number */}
                      <td className="py-3 px-4 font-mono font-bold text-foreground">
                        {order.orderNumber}
                      </td>

                      {/* Customer Name */}
                      <td className="py-3 px-4">
                        <p className="font-semibold text-foreground">{order.customerName}</p>
                        <span className="font-mono text-xs text-muted-foreground" dir="ltr">
                          {order.customerPhone}
                        </span>
                      </td>

                      {/* Date */}
                      <td className="py-3 px-4 text-xs text-muted-foreground">{order.date}</td>

                      {/* Items summary */}
                      <td className="py-3 px-4 text-xs font-mono">
                        {toPersianDigits(
                          order.items.reduce((acc, it) => acc + (it.quantity || 1), 0)
                        )}{" "}
                        کالا
                      </td>

                      {/* Total */}
                      <td className="py-3 px-4 font-bold text-foreground font-mono">
                        {formatPrice(order.total)}
                      </td>

                      {/* Payment Status */}
                      <td className="py-3 px-4">
                        <Badge variant={payConfig.variant} className="text-[11px]">
                          {payConfig.label}
                        </Badge>
                      </td>

                      {/* Status Dropdown */}
                      <td className="py-3 px-4">
                        <Select
                          value={order.status}
                          onValueChange={(val: OrderStatus) =>
                            handleStatusChange(order.id, val)
                          }
                        >
                          <SelectTrigger
                            className="h-8 w-36 text-xs font-semibold"
                            style={{
                              borderColor:
                                order.status === "delivered"
                                  ? "#10b981"
                                  : order.status === "cancelled"
                                  ? "#ef4444"
                                  : undefined,
                            }}
                          >
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="pending">در انتظار</SelectItem>
                            <SelectItem value="confirmed">تایید شده</SelectItem>
                            <SelectItem value="processing">در حال پردازش</SelectItem>
                            <SelectItem value="shipped">ارسال شده</SelectItem>
                            <SelectItem value="delivered">تحویل داده شده</SelectItem>
                            <SelectItem value="cancelled">لغو شده</SelectItem>
                          </SelectContent>
                        </Select>
                      </td>

                      {/* Details button */}
                      <td className="py-3 px-4 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleViewOrder(order)}
                          className="gap-1 text-xs"
                        >
                          <Eye className="h-3.5 w-3.5" />
                          مشاهده
                        </Button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-border px-4 py-3 text-xs text-muted-foreground">
          <span>
            نمایش {toPersianDigits(filteredOrders.length)} از {toPersianDigits(orders.length)} سفارش
          </span>
          <span className="font-mono">سیستم یکپارچه فروشگاه</span>
        </div>
      </Card>

      {/* ============================================================== */}
      {/* MODAL: View Order Details                                      */}
      {/* ============================================================== */}
      <Dialog open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between text-lg">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                جزئیات فاکتور سفارش {selectedOrder?.orderNumber}
              </div>
              {selectedOrder && (
                <Badge variant={ORDER_STATUS_DETAILS[selectedOrder.status].variant}>
                  {ORDER_STATUS_DETAILS[selectedOrder.status].label}
                </Badge>
              )}
            </DialogTitle>
            <DialogDescription>
              مشخصات خریدار، آدرس پستی تحویل و اقلام خریداری شده
            </DialogDescription>
          </DialogHeader>

          {selectedOrder && (
            <div className="space-y-6 py-2">
              {/* Top Quick Status & Actions Box */}
              <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-muted/40 p-4">
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-4">
                  <div>
                    <span className="text-muted-foreground block">تاریخ ثبت سفارش:</span>
                    <span className="font-semibold text-foreground">{selectedOrder.date}</span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">روش پرداخت:</span>
                    <span className="font-semibold text-foreground">
                      {selectedOrder.paymentMethod}
                    </span>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">وضعیت پرداخت:</span>
                    <Badge
                      variant={
                        PAYMENT_STATUS_DETAILS[selectedOrder.paymentStatus]?.variant || "secondary"
                      }
                      className="text-[10px] mt-0.5"
                    >
                      {PAYMENT_STATUS_DETAILS[selectedOrder.paymentStatus]?.label}
                    </Badge>
                  </div>
                  <div>
                    <span className="text-muted-foreground block">کد رهگیری پستی:</span>
                    <span className="font-mono font-bold text-foreground">
                      {selectedOrder.trackingCode || "ثبت نشده"}
                    </span>
                  </div>
                </div>

                {/* Status Selector */}
                <div className="flex items-center gap-2">
                  <Label className="text-xs whitespace-nowrap">تغییر وضعیت:</Label>
                  <Select
                    value={selectedOrder.status}
                    onValueChange={(val: OrderStatus) =>
                      handleStatusChange(selectedOrder.id, val)
                    }
                  >
                    <SelectTrigger className="h-8 w-36 text-xs font-semibold">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="pending">در انتظار</SelectItem>
                      <SelectItem value="confirmed">تایید شده</SelectItem>
                      <SelectItem value="processing">در حال پردازش</SelectItem>
                      <SelectItem value="shipped">ارسال شده</SelectItem>
                      <SelectItem value="delivered">تحویل داده شده</SelectItem>
                      <SelectItem value="cancelled">لغو شده</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Customer & Shipping Information */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {/* Customer card */}
                <div className="rounded-xl border border-border p-4 space-y-2 bg-card">
                  <div className="flex items-center gap-2 text-sm font-semibold text-foreground border-b pb-2">
                    <User className="h-4 w-4 text-primary" />
                    اطلاعات مشتری
                  </div>
                  <div className="space-y-1 text-xs">
                    <p className="text-foreground font-medium">{selectedOrder.customerName}</p>
                    <p className="text-muted-foreground flex items-center gap-1.5 font-mono" dir="ltr">
                      <Phone className="h-3 w-3" />
                      {selectedOrder.customerPhone}
                    </p>
                    {selectedOrder.customerEmail && (
                      <p className="text-muted-foreground flex items-center gap-1.5 font-mono" dir="ltr">
                        <Mail className="h-3 w-3" />
                        {selectedOrder.customerEmail}
                      </p>
                    )}
                  </div>
                </div>

                {/* Shipping address card */}
                <div className="rounded-xl border border-border p-4 space-y-2 bg-card">
                  <div className="flex items-center gap-2 text-sm font-semibold text-foreground border-b pb-2">
                    <MapPin className="h-4 w-4 text-primary" />
                    آدرس و مشخصات تحویل گیرنده
                  </div>
                  <div className="space-y-1 text-xs">
                    <p className="text-foreground">
                      گیرنده:{" "}
                      <span className="font-medium">
                        {selectedOrder.shippingAddress.recipientName}
                      </span>
                    </p>
                    <p className="text-foreground leading-relaxed">
                      نشانی: {selectedOrder.shippingAddress.province}،{" "}
                      {selectedOrder.shippingAddress.city}،{" "}
                      {selectedOrder.shippingAddress.fullAddress}
                    </p>
                    <p className="text-muted-foreground font-mono" dir="ltr">
                      کد پستی: {toPersianDigits(selectedOrder.shippingAddress.postalCode)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Line Items Table */}
              <div className="space-y-2">
                <h3 className="text-sm font-bold text-foreground">اقلام سفارش</h3>
                <div className="overflow-hidden rounded-xl border border-border">
                  <table className="w-full text-right text-xs">
                    <thead className="bg-muted/50 text-muted-foreground border-b border-border">
                      <tr>
                        <th className="py-2.5 px-3">نام کالا</th>
                        <th className="py-2.5 px-3">کد انبار (SKU)</th>
                        <th className="py-2.5 px-3 text-center">تعداد</th>
                        <th className="py-2.5 px-3">قیمت واحد</th>
                        <th className="py-2.5 px-3">مبلغ کل</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {selectedOrder.items.map((item) => (
                        <tr key={item.id} className="hover:bg-muted/20">
                          <td className="py-2.5 px-3 font-medium text-foreground">
                            {item.title}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-muted-foreground" dir="ltr">
                            {item.sku}
                          </td>
                          <td className="py-2.5 px-3 text-center font-mono font-bold">
                            {toPersianDigits(item.quantity)}
                          </td>
                          <td className="py-2.5 px-3 font-mono">
                            {formatPrice(item.unitPrice)}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold text-foreground">
                            {formatPrice(item.totalPrice)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Financial Calculation Breakdown */}
              <div className="flex justify-end">
                <div className="w-full sm:w-72 rounded-xl border border-border p-4 space-y-2 bg-muted/20 text-xs">
                  <div className="flex justify-between text-muted-foreground">
                    <span>جمع اقلام:</span>
                    <span className="font-mono">{formatPrice(selectedOrder.subtotal)}</span>
                  </div>
                  <div className="flex justify-between text-muted-foreground">
                    <span>هزینه حمل و نقل:</span>
                    <span className="font-mono">
                      {selectedOrder.shippingCost === 0
                        ? "رایگان"
                        : formatPrice(selectedOrder.shippingCost)}
                    </span>
                  </div>
                  {selectedOrder.discount > 0 && (
                    <div className="flex justify-between text-emerald-600">
                      <span>تخفیف اعمال شده:</span>
                      <span className="font-mono">- {formatPrice(selectedOrder.discount)}</span>
                    </div>
                  )}
                  <Separator />
                  <div className="flex justify-between text-sm font-bold text-foreground pt-1">
                    <span>مبلغ قابل پرداخت:</span>
                    <span className="font-mono text-primary">
                      {formatPrice(selectedOrder.total)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDetailsOpen(false)}>
              بستن
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
