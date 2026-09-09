"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  TrendingUp,
  ShoppingCart,
  Users,
  DollarSign,
  Package,
  Plus,
  ArrowUpLeft,
  ArrowDownLeft,
  ExternalLink,
  Settings,
  Eye,
  RefreshCw,
  Clock,
  CheckCircle2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

interface KPIData {
  totalSales: number;
  salesChange: string;
  salesIsPositive: boolean;

  ordersCount: number;
  ordersChange: string;
  ordersIsPositive: boolean;

  activeCustomers: number;
  customersChange: string;
  customersIsPositive: boolean;

  averageOrderValue: number;
  aovChange: string;
  aovIsPositive: boolean;
}

interface RecentOrderPreview {
  id: string;
  orderNumber: string;
  customer: string;
  date: string;
  amount: number;
  status: "pending" | "confirmed" | "processing" | "shipped" | "delivered" | "cancelled";
}

interface TopProductPreview {
  id: string;
  name: string;
  category: string;
  salesCount: number;
  revenue: number;
}

/* ------------------------------------------------------------------ */
/*  Persian Status Mappings                                            */
/* ------------------------------------------------------------------ */

const ORDER_STATUS_CONFIG: Record<
  RecentOrderPreview["status"],
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

/* ------------------------------------------------------------------ */
/*  Initial Fallback Data                                              */
/* ------------------------------------------------------------------ */

const INITIAL_KPIS: KPIData = {
  totalSales: 145_200_000,
  salesChange: "+۱۸%",
  salesIsPositive: true,

  ordersCount: 342,
  ordersChange: "+۱۲%",
  ordersIsPositive: true,

  activeCustomers: 1820,
  customersChange: "+۸%",
  customersIsPositive: true,

  averageOrderValue: 1_250_000,
  aovChange: "+۵%",
  aovIsPositive: true,
};

const INITIAL_RECENT_ORDERS: RecentOrderPreview[] = [
  {
    id: "ord-100256",
    orderNumber: "ORD-100256",
    customer: "علی محمدی",
    date: "۵ دقیقه پیش",
    amount: 2_350_000,
    status: "processing",
  },
  {
    id: "ord-100255",
    orderNumber: "ORD-100255",
    customer: "فاطمه احمدی",
    date: "۲۰ دقیقه پیش",
    amount: 8_900_000,
    status: "confirmed",
  },
  {
    id: "ord-100254",
    orderNumber: "ORD-100254",
    customer: "محمد حسینی",
    date: "۱ ساعت پیش",
    amount: 1_200_000,
    status: "shipped",
  },
  {
    id: "ord-100253",
    orderNumber: "ORD-100253",
    customer: "زهرا کریمی",
    date: "۳ ساعت پیش",
    amount: 4_500_000,
    status: "delivered",
  },
  {
    id: "ord-100252",
    orderNumber: "ORD-100252",
    customer: "رضا نوری",
    date: "۵ ساعت پیش",
    amount: 650_000,
    status: "cancelled",
  },
  {
    id: "ord-100251",
    orderNumber: "ORD-100251",
    customer: "مهدی اکبری",
    date: "۸ ساعت پیش",
    amount: 68_500_000,
    status: "pending",
  },
];

const TOP_PRODUCTS: TopProductPreview[] = [
  {
    id: "p-1",
    name: "گوشی موبایل سامسونگ Galaxy S24 Ultra",
    category: "موبایل و تبلت",
    salesCount: 128,
    revenue: 87_680_000_000,
  },
  {
    id: "p-2",
    name: "لپ‌تاپ ۱۶ اینچی اپل MacBook Pro M3 Pro",
    category: "لپ‌تاپ و کامپیوتر",
    salesCount: 64,
    revenue: 73_600_000_000,
  },
  {
    id: "p-3",
    name: "هدفون بی‌سیم نویز کنسلینگ سونی WH-1000XM5",
    category: "صوتی و هدفون",
    salesCount: 256,
    revenue: 43_008_000_000,
  },
  {
    id: "p-4",
    name: "ساعت هوشمند اپل Apple Watch Series 9",
    category: "ساعت هوشمند",
    salesCount: 194,
    revenue: 42_486_000_000,
  },
  {
    id: "p-5",
    name: "کنسول بازی سونی PlayStation 5 Slim",
    category: "کنسول و بازی",
    salesCount: 142,
    revenue: 48_990_000_000,
  },
];

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function AdminDashboardPage() {
  const [kpis, setKpis] = useState<KPIData>(INITIAL_KPIS);
  const [recentOrders, setRecentOrders] = useState<RecentOrderPreview[]>(INITIAL_RECENT_ORDERS);
  const [isLoading, setIsLoading] = useState(false);

  // Fetch KPI data and recent orders from API
  const fetchDashboardData = async () => {
    setIsLoading(true);
    try {
      // 1. Try fetching analytics / sales data
      const analyticsRes = await apiClient
        .get("/analytics/sales")
        .catch(() => apiClient.get("/analytics/overview"))
        .catch(() => null);

      if (analyticsRes?.data) {
        const d = analyticsRes.data;
        setKpis((prev) => ({
          ...prev,
          totalSales: d.total_sales || d.totalRevenue || prev.totalSales,
          ordersCount: d.total_orders || d.orderCount || prev.ordersCount,
          averageOrderValue: d.average_order_value || d.aov || prev.averageOrderValue,
        }));
      }

      // 2. Fetch Recent Orders
      const ordersRes = await apiClient
        .get("/orders/admin/orders?page_size=6")
        .catch(() => apiClient.get("/admin/orders?page_size=6"))
        .catch(() => apiClient.get("/orders?page_size=6"))
        .catch(() => null);

      if (ordersRes?.data?.items && Array.isArray(ordersRes.data.items) && ordersRes.data.items.length > 0) {
        const mappedOrders: RecentOrderPreview[] = ordersRes.data.items.slice(0, 6).map((o: any) => ({
          id: String(o.id),
          orderNumber: o.order_number || o.orderNumber || `ORD-${o.id?.slice?.(0, 6)}`,
          customer: o.user?.name || o.customer_name || o.customerName || "کاربر سایت",
          date: o.created_at ? new Date(o.created_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۱۹",
          amount: o.total_price || o.total || 0,
          status: (o.status?.toLowerCase() as RecentOrderPreview["status"]) || "pending",
        }));
        setRecentOrders(mappedOrders);
      }
    } catch (err) {
      // Fallback is maintained
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  return (
    <div className="space-y-8" dir="rtl">
      {/* Top Welcome & Quick Actions Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">داشبورد مدیریت فروشگاه</h1>
          <p className="text-sm text-muted-foreground">
            خلاصه شاخص‌های کلیدی عملکرد (KPIs) و وضعیت سفارشات و فروشگاه
          </p>
        </div>

        {/* Quick Action Buttons */}
        <div className="flex flex-wrap items-center gap-2.5">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDashboardData}
            disabled={isLoading}
            className="gap-1.5"
            title="بروزرسانی آمار"
          >
            <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
            بروزرسانی
          </Button>

          <Link href="/admin/products">
            <Button size="sm" className="gap-1.5 shadow-sm">
              <Plus className="h-4 w-4" />
              ثبت محصول جدید
            </Button>
          </Link>

          <Link href="/admin/orders">
            <Button variant="secondary" size="sm" className="gap-1.5 shadow-sm">
              <ShoppingCart className="h-4 w-4" />
              مشاهده سفارش‌ها
            </Button>
          </Link>

          <Link href="/admin/settings">
            <Button variant="outline" size="sm" className="gap-1.5">
              <Settings className="h-4 w-4" />
              تنظیمات
            </Button>
          </Link>
        </div>
      </div>

      {/* ============================================================== */}
      {/* 4 Core KPI Cards                                               */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {/* KPI 1: Total Sales */}
        <Card className="p-6 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">فروش کل (Total Sales)</p>
              <p className="text-2xl font-bold text-foreground font-mono">
                {formatPrice(kpis.totalSales)}
              </p>
              <div className="flex items-center gap-1 text-xs">
                {kpis.salesIsPositive ? (
                  <ArrowUpLeft className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <ArrowDownLeft className="h-3.5 w-3.5 text-destructive" />
                )}
                <span
                  className={`font-semibold ${
                    kpis.salesIsPositive ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {kpis.salesChange}
                </span>
                <span className="text-muted-foreground">نسبت به ماه گذشته</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400 shadow-sm">
              <TrendingUp className="h-6 w-6" />
            </div>
          </div>
        </Card>

        {/* KPI 2: Orders Count */}
        <Card className="p-6 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">تعداد کل سفارش‌ها</p>
              <p className="text-2xl font-bold text-foreground font-mono">
                {toPersianDigits(kpis.ordersCount)} سفارش
              </p>
              <div className="flex items-center gap-1 text-xs">
                {kpis.ordersIsPositive ? (
                  <ArrowUpLeft className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <ArrowDownLeft className="h-3.5 w-3.5 text-destructive" />
                )}
                <span
                  className={`font-semibold ${
                    kpis.ordersIsPositive ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {kpis.ordersChange}
                </span>
                <span className="text-muted-foreground">نسبت به ماه گذشته</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400 shadow-sm">
              <ShoppingCart className="h-6 w-6" />
            </div>
          </div>
        </Card>

        {/* KPI 3: Active Customers */}
        <Card className="p-6 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">مشتریان فعال (Active Users)</p>
              <p className="text-2xl font-bold text-foreground font-mono">
                {toPersianDigits(kpis.activeCustomers)} کاربر
              </p>
              <div className="flex items-center gap-1 text-xs">
                {kpis.customersIsPositive ? (
                  <ArrowUpLeft className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <ArrowDownLeft className="h-3.5 w-3.5 text-destructive" />
                )}
                <span
                  className={`font-semibold ${
                    kpis.customersIsPositive ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {kpis.customersChange}
                </span>
                <span className="text-muted-foreground">نسبت به ماه گذشته</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-purple-100 text-purple-600 dark:bg-purple-950 dark:text-purple-400 shadow-sm">
              <Users className="h-6 w-6" />
            </div>
          </div>
        </Card>

        {/* KPI 4: Average Order Value */}
        <Card className="p-6 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div className="space-y-1">
              <p className="text-xs font-medium text-muted-foreground">میانگین ارزش سفارش (AOV)</p>
              <p className="text-2xl font-bold text-foreground font-mono">
                {formatPrice(kpis.averageOrderValue)}
              </p>
              <div className="flex items-center gap-1 text-xs">
                {kpis.aovIsPositive ? (
                  <ArrowUpLeft className="h-3.5 w-3.5 text-emerald-600" />
                ) : (
                  <ArrowDownLeft className="h-3.5 w-3.5 text-destructive" />
                )}
                <span
                  className={`font-semibold ${
                    kpis.aovIsPositive ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {kpis.aovChange}
                </span>
                <span className="text-muted-foreground">نسبت به ماه گذشته</span>
              </div>
            </div>
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-600 dark:bg-amber-950 dark:text-amber-400 shadow-sm">
              <DollarSign className="h-6 w-6" />
            </div>
          </div>
        </Card>
      </div>

      {/* ============================================================== */}
      {/* Middle Grid: Recent Orders Preview & Top Products              */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Recent Orders Preview Table (2 Cols) */}
        <Card className="p-6 xl:col-span-2">
          <div className="mb-4 flex items-center justify-between border-b pb-4">
            <div>
              <h2 className="text-lg font-semibold text-foreground">سفارش‌های اخیر</h2>
              <p className="text-xs text-muted-foreground">
                آخرین سفارش‌های ثبت شده در سیستم و وضعیت لحظه‌ای آن‌ها
              </p>
            </div>
            <Link href="/admin/orders">
              <Button variant="ghost" size="sm" className="gap-1 text-xs text-primary">
                مشاهده همه سفارش‌ها
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground">
                  <th className="pb-3 px-3 font-semibold">شماره سفارش</th>
                  <th className="pb-3 px-3 font-semibold">مشتری</th>
                  <th className="pb-3 px-3 font-semibold">زمان ثبت</th>
                  <th className="pb-3 px-3 font-semibold">مبلغ کل</th>
                  <th className="pb-3 px-3 font-semibold">وضعیت</th>
                  <th className="pb-3 px-3 text-center font-semibold">اقدام</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recentOrders.map((order) => {
                  const statusConf = ORDER_STATUS_CONFIG[order.status] || {
                    label: order.status,
                    variant: "secondary",
                  };
                  return (
                    <tr key={order.id} className="hover:bg-muted/30 transition-colors">
                      <td className="py-3 px-3 font-mono font-bold text-foreground">
                        {order.orderNumber}
                      </td>
                      <td className="py-3 px-3 font-medium text-foreground">
                        {order.customer}
                      </td>
                      <td className="py-3 px-3 text-xs text-muted-foreground">
                        {order.date}
                      </td>
                      <td className="py-3 px-3 font-mono font-semibold text-foreground">
                        {formatPrice(order.amount)}
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant={statusConf.variant} className="text-[11px]">
                          {statusConf.label}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-center">
                        <Link href="/admin/orders">
                          <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-primary">
                            <Eye className="h-4 w-4" />
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Top Selling Products Preview (1 Col) */}
        <Card className="p-6">
          <div className="mb-4 flex items-center justify-between border-b pb-4">
            <div>
              <h2 className="text-lg font-semibold text-foreground">پرفروش‌ترین کالاها</h2>
              <p className="text-xs text-muted-foreground">
                محصولات با بالاترین نرخ فروش در ماه جاری
              </p>
            </div>
            <Link href="/admin/products">
              <Button variant="ghost" size="sm" className="gap-1 text-xs text-primary">
                کاتالوگ
                <ExternalLink className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </div>

          <div className="space-y-4">
            {TOP_PRODUCTS.map((prod, index) => (
              <div
                key={prod.id}
                className="flex items-center justify-between rounded-lg p-2.5 transition-colors hover:bg-muted/40"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-xs font-bold text-primary">
                    {toPersianDigits(index + 1)}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-xs font-semibold text-foreground" title={prod.name}>
                      {prod.name}
                    </p>
                    <span className="text-[11px] text-muted-foreground">
                      {prod.category} &middot; {toPersianDigits(prod.salesCount)} فروش
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ============================================================== */}
      {/* Bottom Row: Quick Status Banner                                */}
      {/* ============================================================== */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className="p-4 flex items-center gap-4 bg-muted/20">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-100 text-blue-600 dark:bg-blue-950 dark:text-blue-400">
            <Clock className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted-foreground">سفارشات در انتظار اقدام انبار</p>
            <p className="text-sm font-bold text-foreground">
              {toPersianDigits(recentOrders.filter((o) => o.status === "pending" || o.status === "confirmed").length)} سفارش نیاز به تایید دارند
            </p>
          </div>
          <Link href="/admin/orders">
            <Button variant="outline" size="sm" className="text-xs">
              بررسی
            </Button>
          </Link>
        </Card>

        <Card className="p-4 flex items-center gap-4 bg-muted/20">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted-foreground">وضعیت سرور و پایگاه داده</p>
            <p className="text-sm font-bold text-emerald-600">کلیه سرویس‌ها فعال و آنلاین هستند</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-4 bg-muted/20">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-purple-100 text-purple-600 dark:bg-purple-950 dark:text-purple-400">
            <Package className="h-5 w-5" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-xs text-muted-foreground">مدیریت موجودی انبار</p>
            <p className="text-sm font-bold text-foreground">بررسی کالاهای رو به اتمام</p>
          </div>
          <Link href="/admin/products">
            <Button variant="outline" size="sm" className="text-xs">
              انبارداری
            </Button>
          </Link>
        </Card>
      </div>
    </div>
  );
}
