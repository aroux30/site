"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  TrendingUp,
  Download,
  DollarSign,
  ShoppingCart,
  CreditCard,
  Printer,
  FileText,
  AlertCircle,
  Package,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";

interface ReportMetrics {
  grossSales: number;
  ordersCount: number;
  averageOrderValue: number;
  taxCollected: number;
}

interface BestSellerProduct {
  name: string;
  revenue: number;
  quantity: number;
  share: string;
}

const INITIAL_METRICS: ReportMetrics = {
  grossSales: 0,
  ordersCount: 0,
  averageOrderValue: 0,
  taxCollected: 0,
};

function getDateRangeBounds(range: string): { start: string; end: string } {
  const now = new Date();
  const end = now.toISOString().split("T")[0]!;
  let days = 30;
  if (range === "7d") days = 7;
  else if (range === "30d") days = 30;
  else if (range === "90d") days = 90;
  else if (range === "365d") days = 365;

  const startDate = new Date(now.getTime() - days * 24 * 60 * 60 * 1000);
  const start = startDate.toISOString().split("T")[0]!;
  return { start, end };
}

export default function AdminReportsPage() {
  const [dateRange, setDateRange] = useState("30d");
  const [metrics, setMetrics] = useState<ReportMetrics>(INITIAL_METRICS);
  const [bestSellers, setBestSellers] = useState<BestSellerProduct[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchReportData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { start, end } = getDateRangeBounds(dateRange);
      const [salesRes, productsRes] = await Promise.allSettled([
        apiClient.get(`/analytics/sales?start_date=${start}&end_date=${end}`),
        apiClient.get(`/analytics/products?start_date=${start}&end_date=${end}&limit=5`),
      ]);

      let totalSales = 0;
      let orderCount = 0;
      let aov = 0;

      if (salesRes.status === "fulfilled" && salesRes.value.data) {
        const d = salesRes.value.data;
        totalSales = Number(d.total_sales) || 0;
        orderCount = Number(d.order_count) || 0;
        aov = Number(d.average_order_value) || 0;
      }

      setMetrics({
        grossSales: totalSales,
        ordersCount: orderCount,
        averageOrderValue: aov,
        taxCollected: Math.round(totalSales * 0.1),
      });

      if (
        productsRes.status === "fulfilled" &&
        Array.isArray(productsRes.value.data?.best_sellers)
      ) {
        const raw = productsRes.value.data.best_sellers;
        const totalTopRevenue = raw.reduce(
          (sum: number, p: { total_revenue?: number }) => sum + (Number(p.total_revenue) || 0),
          0,
        );
        const mapped: BestSellerProduct[] = raw.map(
          (p: { product_name?: string; total_revenue?: number; total_sold?: number }) => {
            const rev = Number(p.total_revenue) || 0;
            const pct =
              totalTopRevenue > 0
                ? Math.round((rev / totalTopRevenue) * 100)
                : 0;
            return {
              name: p.product_name || "محصول",
              revenue: rev,
              quantity: Number(p.total_sold) || 0,
              share: `${pct}%`,
            };
          },
        );
        setBestSellers(mapped);
      } else {
        setBestSellers([]);
      }
    } catch (err: unknown) {
      setError(
        (err as { message?: string })?.message ||
          "خطا در دریافت داده‌های گزارش",
      );
    } finally {
      setIsLoading(false);
    }
  }, [dateRange]);

  useEffect(() => {
    fetchReportData();
  }, [fetchReportData]);

  const handleExportCsv = () => {
    const rows = [
      ["شاخص", "مقدار"],
      ["فروش ناخالص کل (ریال)", String(metrics.grossSales)],
      ["تعداد سفارشات", String(metrics.ordersCount)],
      ["میانگین ارزش سفارش (AOV)", String(metrics.averageOrderValue)],
      ["مالیات بر ارزش افزوده (ریال)", String(metrics.taxCollected)],
      [],
      ["کالاهای پرفروش", "درآمد (ریال)", "تعداد", "سهم"],
      ...bestSellers.map((b) => [b.name, String(b.revenue), String(b.quantity), b.share]),
    ];
    const csvContent =
      "data:text/csv;charset=utf-8,\uFEFF" +
      rows.map((e) => e.join(",")).join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `sales-report-${dateRange}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">گزارش‌های جامع مالی و فروش</h1>
          <p className="text-sm text-muted-foreground">
            بررسی درآمد کل، عملکرد دسته‌ها، مالیات بر ارزش افزوده و شاخص‌های فروش
          </p>
        </div>

        <div className="flex items-center gap-2">
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-xs"
          >
            <option value="7d">۷ روز گذشته</option>
            <option value="30d">۳۰ روز گذشته</option>
            <option value="90d">فصل جاری</option>
            <option value="365d">یک سال گذشته</option>
          </select>
          <Button variant="outline" size="sm" className="gap-2" onClick={() => window.print()}>
            <Printer className="h-4 w-4" /> چاپ
          </Button>
          <Button size="sm" className="gap-2" onClick={handleExportCsv}>
            <Download className="h-4 w-4" /> خروجی اکسل (CSV)
          </Button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {error}
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">فروش ناخالص کل</span>
            <DollarSign className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">
            {formatPrice(metrics.grossSales)}
          </div>
          <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            داده‌های واقعی بر اساس سفارش‌های نهایی
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">تعداد کل سفارشات</span>
            <ShoppingCart className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">
            {toPersianDigits(metrics.ordersCount)} سفارش
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            ثبت‌شده در بازه انتخابی
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">میانگین مبلغ هر سفارش (AOV)</span>
            <CreditCard className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">
            {formatPrice(metrics.averageOrderValue)}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            محاسبه خودکار از سرور
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center justify-between text-muted-foreground">
            <span className="text-xs font-medium">مالیات بر ارزش افزوده (۱۰٪)</span>
            <FileText className="h-4 w-4 text-primary" />
          </div>
          <div className="mt-2 text-2xl font-bold text-foreground">
            {formatPrice(metrics.taxCollected)}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            محاسبه مالیاتی بر اساس فروش ناخالص
          </div>
        </Card>
      </div>

      {/* Breakdown by Top Products */}
      <Card className="p-6">
        <h3 className="text-base font-bold text-foreground">محصولات پرفروش در این بازه</h3>
        <p className="mb-4 text-xs text-muted-foreground">
          پرفروش‌ترین کالاها بر اساس حجم درآمد و تعداد فروش
        </p>

        {bestSellers.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-center text-muted-foreground">
            <Package className="mb-2 h-10 w-10 text-muted-foreground/30" />
            <p className="text-sm">هنوز داده‌ای برای کالاهای پرفروش در این بازه ثبت نشده است.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {bestSellers.map((prod, i) => (
              <div key={i} className="space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="font-medium text-foreground">{prod.name}</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {formatPrice(prod.revenue)} ({toPersianDigits(prod.share)})
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: prod.share }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
