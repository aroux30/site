"use client";

import React, { Fragment, useState, useEffect } from "react";
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
  Printer,
  CheckSquare,
  Square,
  AlertTriangle,
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
import { useAdminQuery } from "@/lib/api/admin-query";

const ORDERS_QUERY_KEY = "admin-orders" as const;
const PAGE_SIZE = 50;
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { ShipmentStepper } from "@/components/orders/shipment-stepper";
import { adminBulkApi } from "@/lib/api/bulk-operations";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

// Must match the backend OrderStatus enum exactly (snake_case values)
type OrderStatus =
  | "pending"
  | "confirmed"
  | "processing"
  | "packing"
  | "on_hold"
  | "shipped"
  | "delivered"
  | "completed"
  | "canceled"
  | "returned"
  | "refunded"
  | "partially_refunded";

type PaymentStatus = "paid" | "pending" | "failed" | "refunded";

interface OrderItem {
  id: string;
  title: string;
  sku: string;
  quantity: number;
  unitPrice: number;
  totalPrice: number;
  imageUrl?: string;
  /** Karta categoryFields answers captured at checkout (Sprint 1.7) */
  customFields?: string[];
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
  itemsCount: number;
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
  packing: { label: "در حال بسته‌بندی", variant: "default" },
  on_hold: { label: "معلق", variant: "warning" },
  shipped: { label: "ارسال شده", variant: "info" },
  delivered: { label: "تحویل داده شده", variant: "success" },
  completed: { label: "تکمیل شده", variant: "success" },
  canceled: { label: "لغو شده", variant: "destructive" },
  returned: { label: "مرجوع شده", variant: "outline" },
  refunded: { label: "بازگشت وجه کامل", variant: "secondary" },
  partially_refunded: { label: "بازگشت وجه جزئی", variant: "secondary" },
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

export default function AdminOrdersPage() {
  const { toast } = useToast();


  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  // Server-side paging — the endpoint already accepted page/page_size and
  // nothing sent them, so the table only ever showed the first page.
  const [page, setPage] = useState(1);

  // Modal State: View Order Details
  const [selectedOrder, setSelectedOrder] = useState<AdminOrder | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Orders, mapped once. The mapper used to invent six facts on a missing
  // field — a date ("۱۴۰۳/۰۶/۰۱"), a customer name ("کاربر سایت"), a payment
  // method, a province, a city, a full address, and an order-item SKU. On an
  // ops screen those read as real data. Missing values are now "—" so an
  // absent field is visibly absent.
  const {
    data: ordersData,
    loading: isLoading,
    error: ordersError,
    reload: loadOrders,
  } = useAdminQuery({
    queryKey: [ORDERS_QUERY_KEY, page, statusFilter, searchQuery.trim()],
    queryFn: async () => {
      // Server-side paging. This used to call the list endpoint with no
      // parameters at all, so the API applied its own default page size and
      // the admin table silently showed only that first page — an order past
      // it was invisible with nothing on screen to suggest it existed.
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("page_size", String(PAGE_SIZE));
      if (statusFilter && statusFilter !== "all") {
        params.set("status", statusFilter);
      }
      if (searchQuery.trim()) params.set("search", searchQuery.trim());
      const res = await apiClient.get(`/orders/admin/orders?${params.toString()}`);
      const meta = res.data?.meta ?? {};
      if (!res.data?.items || !Array.isArray(res.data.items))
        return { items: [] as AdminOrder[], total: 0, totalPages: 1 };
      const items = res.data.items.map((o: any): AdminOrder => ({
        id: String(o.id),
        orderNumber: o.order_number || o.orderNumber || `ORD-${o.id?.slice?.(0, 6)}`,
        customerName: o.user?.name || o.customer_name || o.customerName || "—",
        customerPhone: o.customer_phone || o.user?.phone || "",
        customerEmail: o.user?.email || o.email,
        date: o.created_at ? new Date(o.created_at).toLocaleDateString("fa-IR") : "—",
        total: Math.trunc((o.total_price || o.total || 0) / 10),
        subtotal: Math.trunc((o.subtotal || o.total_price || o.total || 0) / 10),
        shippingCost: Math.trunc((o.shipping_cost || 0) / 10),
        discount: Math.trunc((o.discount || 0) / 10),
        status: (o.status?.toLowerCase() as OrderStatus) || "pending",
        paymentStatus: (o.payment_status?.toLowerCase() as PaymentStatus) || "paid",
        paymentMethod: o.payment_method || "—",
        trackingCode: o.tracking_code || o.tracking_number,
        shippingAddress: {
          recipientName: o.shipping_address?.receiver_name || o.customer_name || "—",
          phone: o.shipping_address?.phone || o.phone || "",
          province: o.shipping_address?.province || "—",
          city: o.shipping_address?.city || "—",
          postalCode: o.shipping_address?.postal_code || "",
          fullAddress: o.shipping_address?.full_address || o.shipping_address?.address || "—",
        },
        itemsCount:
          typeof o.items_count === "number"
            ? o.items_count
            : (o.items || []).reduce((acc: number, it: any) => acc + (it.quantity || 1), 0),
        items: (o.items || []).map((it: any, idx: number) => ({
          id: String(it.id || idx),
          title: it.product_title || it.title || "—",
          sku: it.sku || "—",
          quantity: it.quantity || 1,
          unitPrice: Math.trunc((it.unit_price || it.price || 0) / 10),
          totalPrice: Math.trunc(((it.unit_price || it.price || 0) * (it.quantity || 1)) / 10),
          customFields: (it.custom_fields && typeof it.custom_fields === "object")
            ? Object.entries(it.custom_fields as Record<string, unknown>).map(
                ([k, v]) => `${k}: ${String(v)}`
              )
            : undefined,
        })),
      }));
      return {
        items,
        total: typeof meta.total === "number" ? meta.total : items.length,
        totalPages: Math.max(1, Number(meta.total_pages ?? 1) || 1),
      };
    },
    // No fabricated fallback data: surface the failure honestly.
    fallbackError: "خطا در دریافت سفارش‌ها از سرور. لطفاً صفحه را دوباره بارگذاری کنید.",
  });
  const orders: AdminOrder[] = ordersData?.items ?? [];
  const ordersTotal: number = ordersData?.total ?? 0;
  const ordersTotalPages: number = ordersData?.totalPages ?? 1;
  const fetchError = ordersError !== null;

  /* ---------------------------------------------------------------- */
  /*  Change Status Handler (PATCH /admin/orders/{id}/status)         */
  /* ---------------------------------------------------------------- */

  const handleStatusChange = async (orderId: string, newStatus: OrderStatus) => {
    try {
      await apiClient.patch(`/orders/admin/orders/${orderId}/status`, {
        status: newStatus,
      });

      // The status change is committed server-side; invalidating the query
      // refetches the authoritative row rather than guessing its new shape.
      await loadOrders();

      if (selectedOrder && selectedOrder.id === orderId) {
        setSelectedOrder((prev) => (prev ? { ...prev, status: newStatus } : null));
      }

      toast({
        title: "وضعیت سفارش تغییر کرد",
        description: `وضعیت سفارش به «${ORDER_STATUS_DETAILS[newStatus].label}» بروزرسانی شد.`,
        variant: "success",
      });
    } catch (err: unknown) {
      const errorData = (err as { response?: { data?: { error_code?: string; detail?: string } } })?.response?.data;
      const errorCode = errorData?.error_code;

      let errorDesc = errorData?.detail || (err as { message?: string })?.message || "امکان بروزرسانی وضعیت وجود نداشت.";
      if (errorCode === "INVALID_SHIPMENT_TRANSITION") {
        errorDesc = "تغییر وضعیت مرسوله پستی نامعتبر است؛ توالی وضعیت‌ها باید به ترتیب در انتظار، تحویل به پست، در مسیر و سپس تحویل نهایی باشد";
      } else if (errorCode === "WEBHOOK_TIMESTAMP_EXPIRED") {
        errorDesc = "درخواست وب‌هوک خارج از بازه مجاز ۵ دقیقه‌ای است";
      }

      toast({
        title: "خطا در تغییر وضعیت",
        description: errorDesc,
        variant: "destructive",
      });
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Filtering                                                        */
  /* ---------------------------------------------------------------- */

  // Search and status are applied by the server now, so re-applying them here
  // would only narrow the current page a second time. The previous version
  // fetched an unparameterised list and filtered those rows in the browser,
  // which is why an order past the API's default page size could never be
  // found by any search.
  const filteredOrders = orders;

  /* ---------------------------------------------------------------- */
  /*  Bulk selection                                                   */
  /* ---------------------------------------------------------------- */

  // A bulk status change moves money and stock, so the selection is CLEARED
  // rather than carried across a page/filter change: a selection that
  // survives a filter swap targets orders the operator cannot see, and the
  // consequence here is a refund, not a mislabelled row.
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  // Orders the server rejected, with the reason — a partial run has to say
  // which orders did not move and why, not just "done".
  const [bulkRejected, setBulkRejected] = useState<
    { orderNumber: string; detail: string }[] | null
  >(null);

  React.useEffect(() => {
    setSelected(new Set());
  }, [ordersData]);

  // A filter change hides rows without changing `ordersData`, so the
  // selection is reconciled against the visible set here too.
  React.useEffect(() => {
    const visible = new Set(filteredOrders.map((o) => o.id));
    setSelected((prev) => {
      const next = new Set([...prev].filter((id) => visible.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [filteredOrders]);

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const allVisibleSelected =
    filteredOrders.length > 0 && filteredOrders.every((o) => selected.has(o.id));

  const toggleSelectAllVisible = () => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (allVisibleSelected) filteredOrders.forEach((o) => next.delete(o.id));
      else filteredOrders.forEach((o) => next.add(o.id));
      return next;
    });
  };

  /**
   * Bulk status change. The backend validates every order on its own, so a
   * run can be partially applied — a `failed > 0` here means those orders
   * really did NOT move. The toast reports the split, and the rejected list
   * is kept on screen until the operator dismisses it.
   */
  const runBulkStatus = async (newStatus: OrderStatus) => {
    if (selected.size === 0) return;
    const label = ORDER_STATUS_DETAILS[newStatus].label;
    const warning =
      newStatus === "canceled"
        ? " لغو سفارش، موجودی انبار را بازمی‌گرداند و وجه پرداخت‌شده را به کیف پول مشتری برمی‌گرداند."
        : "";
    if (
      !confirm(
        `${toPersianDigits(String(selected.size))} سفارش به «${label}» تغییر وضعیت داده شود؟${warning}`,
      )
    )
      return;

    setBulkBusy(true);
    setBulkRejected(null);
    try {
      const ids = [...selected];
      const result = await adminBulkApi.bulkUpdateOrderStatus(ids, newStatus);
      if (result.failed > 0) {
        setBulkRejected(
          result.items
            .filter((i) => !i.success)
            .map((i) => ({
              orderNumber: i.order_number ?? i.order_id.slice(0, 8),
              detail: i.detail ?? i.error_code ?? "نامشخص",
            })),
        );
        toast({
          title: "انجام شد با خطا",
          description: `موفق: ${toPersianDigits(String(result.succeeded))} — ناموفق: ${toPersianDigits(String(result.failed))}`,
          variant: "destructive",
        });
      } else {
        toast({
          title: `وضعیت ${toPersianDigits(String(result.succeeded))} سفارش تغییر کرد`,
          description: label,
          variant: "success",
        });
      }
      setSelected(new Set());
      await loadOrders();
    } catch (err: unknown) {
      const errorData = (err as { response?: { data?: { detail?: string } } })?.response?.data;
      toast({
        title: "عملیات گروهی ناموفق بود",
        description: errorData?.detail || (err as { message?: string })?.message,
        variant: "destructive",
      });
    } finally {
      setBulkBusy(false);
    }
  };

  const handleViewOrder = (order: AdminOrder) => {
    setSelectedOrder(order);
    setIsDetailsOpen(true);
  };

  const handlePrintInvoice = (orderId: string) => {
    // The invoice endpoint authenticates from the access_token HttpOnly
    // cookie, which the browser attaches to this same-origin request
    // automatically. The token must never be read from JS or placed in the
    // URL: that would defeat HttpOnly and leak the credential into browser
    // history, nginx access logs, and any Referer sent by the opened page.
    window.open(`/api/v1/orders/${orderId}/invoice`, "_blank");
  };

  const orderColumns: DataTableColumn<AdminOrder>[] = [
    {
      key: "select",
      header: "",
      className: "w-10",
      render: (o) => (
        <button
          onClick={() => toggleSelect(o.id)}
          aria-label={selected.has(o.id) ? "برداشتن انتخاب" : "انتخاب"}
          className="text-muted-foreground hover:text-foreground"
        >
          {selected.has(o.id) ? (
            <CheckSquare className="h-4 w-4 text-primary" />
          ) : (
            <Square className="h-4 w-4" />
          )}
        </button>
      ),
    },
    {
      key: "number",
      header: "شماره سفارش",
      className: "font-mono font-bold text-foreground",
      render: (o) => o.orderNumber,
    },
    {
      key: "customer",
      header: "نام مشتری",
      render: (o) => (
        <div>
          <p className="font-semibold text-foreground">{o.customerName}</p>
          <span className="font-mono text-xs text-muted-foreground" dir="ltr">
            {o.customerPhone}
          </span>
        </div>
      ),
    },
    {
      key: "date",
      header: "تاریخ ثبت",
      className: "text-xs text-muted-foreground",
      hideOnMobile: true,
      render: (o) => o.date,
    },
    {
      key: "items",
      header: "تعداد اقلام",
      className: "text-xs font-mono",
      hideOnMobile: true,
      render: (o) => <>{toPersianDigits(o.itemsCount)} کالا</>,
    },
    {
      key: "total",
      header: "مبلغ کل فاکتور",
      className: "font-bold text-foreground font-mono",
      render: (o) => formatPrice(o.total),
    },
    {
      key: "payment",
      header: "وضعیت پرداخت",
      render: (o) => {
        const payConfig = PAYMENT_STATUS_DETAILS[o.paymentStatus] || {
          label: o.paymentStatus,
          variant: "secondary",
        };
        return (
          <Badge variant={payConfig.variant} className="text-[11px]">
            {payConfig.label}
          </Badge>
        );
      },
    },
    {
      key: "status",
      header: "وضعیت سفارش",
      render: (o) => (
        <Select
          value={o.status}
          onValueChange={(val: OrderStatus) => handleStatusChange(o.id, val)}
        >
          <SelectTrigger
            className="h-8 w-36 text-xs font-semibold"
            style={{
              borderColor:
                o.status === "delivered"
                  ? "#10b981"
                  : o.status === "canceled"
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
            <SelectItem value="canceled">لغو شده</SelectItem>
          </SelectContent>
        </Select>
      ),
    },
    {
      key: "actions",
      header: <span className="sr-only">عملیات</span>,
      className: "text-center",
      render: (o) => (
        <div className="flex items-center justify-center gap-1.5">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handlePrintInvoice(o.id)}
            className="gap-1 text-xs text-primary border-primary/30 hover:bg-primary/10"
            title="مشاهده و چاپ فاکتور رسمی"
          >
            <Printer className="h-3.5 w-3.5" />
            فاکتور رسمی
          </Button>
          <Button variant="ghost" size="sm" onClick={() => handleViewOrder(o)} className="gap-1 text-xs">
            <Eye className="h-3.5 w-3.5" />
            مشاهده
          </Button>
        </div>
      ),
    },
  ];

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
              onChange={(e) => {
                setSearchQuery(e.target.value);
                // Keep a filter change from stranding the operator on page 4
                // of a result set that now has two pages.
                setPage(1);
              }}
              placeholder="جستجو در شماره سفارش، نام مشتری یا شماره تماس..."
              className="ps-9"
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
                <SelectItem value="canceled">لغو شده</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </Card>

      {/* Bulk actions — the status moves offered here are the same ones the
          per-row selector offers, so the bulk bar cannot reach a transition
          the single-order path would refuse. Cancellation is included because
          it goes through the same service (restock + wallet refund); the
          confirm dialog spells that out. */}
      {selected.size > 0 && (
        <Card className="p-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {toPersianDigits(String(selected.size))} سفارش انتخاب شده:
            </span>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkStatus("confirmed")}>
              تایید شده
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkStatus("processing")}>
              در حال پردازش
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkStatus("shipped")}>
              ارسال شده
            </Button>
            <Button size="sm" variant="outline" disabled={bulkBusy} onClick={() => runBulkStatus("delivered")}>
              تحویل داده شده
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={bulkBusy}
              onClick={() => runBulkStatus("canceled")}
            >
              لغو
            </Button>
            <Button size="sm" variant="ghost" disabled={bulkBusy} onClick={() => setSelected(new Set())}>
              لغو انتخاب
            </Button>
          </div>
        </Card>
      )}

      {/* Rejected orders from the last bulk run. Kept on screen (not just in
          a toast) because "7 of 10 did not move" is only actionable with the
          per-order reason next to it. */}
      {bulkRejected && bulkRejected.length > 0 && (
        <div
          role="alert"
          className="rounded-2xl border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm"
        >
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 font-semibold text-destructive">
              <AlertTriangle className="h-4 w-4" />
              {toPersianDigits(String(bulkRejected.length))} سفارش تغییر وضعیت نیافت
            </span>
            <Button variant="ghost" size="sm" onClick={() => setBulkRejected(null)}>
              بستن
            </Button>
          </div>
          <ul className="mt-2 space-y-1 text-xs text-destructive">
            {bulkRejected.map((r) => (
              <li key={r.orderNumber}>
                <span className="font-mono">{r.orderNumber}</span> — {r.detail}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Orders Table */}
      <div className="flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleSelectAllVisible}
          disabled={filteredOrders.length === 0}
          className="text-xs text-muted-foreground"
        >
          {allVisibleSelected ? "برداشتن انتخاب همه" : "انتخاب همه نمایش‌داده‌شده‌ها"}
        </Button>
      </div>
      <DataTable<AdminOrder>
        columns={orderColumns}
        rows={filteredOrders}
        rowKey={(o) => o.id}
        error={fetchError ? "خطا در دریافت سفارش‌ها از سرور. لطفاً صفحه را دوباره بارگذاری کنید." : null}
        emptyMessage="هیچ سفارشی با این شرایط یافت نشد."
      />

      {/* Server-side paging needs a control: without one the table showed the
          API's default first page and nothing signalled that more existed. */}
      {ordersTotalPages > 1 && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {ordersTotal.toLocaleString("fa-IR")} سفارش — صفحهٔ {page} از{" "}
            {ordersTotalPages}
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1 || isLoading}
              onClick={() => {
                setPage((p) => Math.max(1, p - 1));
                setSelected(new Set<string>());
              }}
            >
              قبلی
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= ordersTotalPages || isLoading}
              onClick={() => {
                setPage((p) => Math.min(ordersTotalPages, p + 1));
                // A selection carried across a page change would target rows
                // the operator can no longer see.
                setSelected(new Set<string>());
              }}
            >
              بعدی
            </Button>
          </div>
        </div>
      )}

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
                      <SelectItem value="canceled">لغو شده</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* 4-Step Shipment Stepper (Sprint 3 Phase 2) */}
              <ShipmentStepper
                orderId={selectedOrder.id}
                trackingCode={selectedOrder.trackingCode}
                carrier="شرکت ملی پست ایران (پیشتاز)"
                status={selectedOrder.status}
                deliveredAt={selectedOrder.status === "delivered" ? selectedOrder.date : null}
                showRmaAction={false}
              />

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
                        <Fragment key={item.id}>
                        <tr className="hover:bg-muted/20">
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
                        {item.customFields && item.customFields.length > 0 && (
                          <tr className="bg-muted/10">
                            <td colSpan={5} className="py-1.5 px-3 text-xs text-muted-foreground">
                              <span className="font-bold">اطلاعات سفارش‌ساز: </span>
                              {item.customFields.join(" | ")}
                            </td>
                          </tr>
                        )}
                        </Fragment>
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

          <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-between items-center gap-2">
            <Button variant="outline" onClick={() => setIsDetailsOpen(false)}>
              بستن
            </Button>
            {selectedOrder && (
              <Button
                variant="default"
                onClick={() => handlePrintInvoice(selectedOrder.id)}
                className="gap-2"
              >
                <Printer className="h-4 w-4" />
                چاپ فاکتور رسمی
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
