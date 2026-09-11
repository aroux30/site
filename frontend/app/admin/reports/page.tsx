"use client";

import React, { useState } from "react";
import {
  BarChart3,
  TrendingUp,
  Download,
  Calendar,
  DollarSign,
  ShoppingCart,
  Users,
  CreditCard,
  Printer,
  FileText,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { formatPrice, toPersianDigits } from "@/lib/utils";

export default function AdminReportsPage() {
  const [dateRange, setDateRange] = useState("30d");

  const metrics = {
    grossSales: 845_200_000,
    netSales: 760_680_000,
    taxCollected: 76_068_000,
    shippingFees: 8_452_000,
    ordersCount: 428,
    averageOrderValue: 1_974_700,
    refundsCount: 4,
    refundedAmount: 7_800_000,
  };

  const salesByCategory = [
    { name: "کالای دیجیتال و موبایل", share: "58%", revenue: 490_216_000 },
    { name: "لپ‌تاپ و تجهیزات کامپیوتر", share: "24%", revenue: 202_848_000 },
    { name: "خانه و آشپزخانه", share: "11%", revenue: 92_972_000 },
    { name: "مد و پوشاک", share: "7%", revenue: 59_164_000 },
  ];

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
          <Button size="sm" className="gap-2">
            <Download className="h-4 w-4" /> خروجی اکسل
          </Button>
        </div>
      </div>

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
          <div className="mt-1 flex items-center gap-1 text-xs text-emerald-600">
            <TrendingUp className="h-3.5 w-3.5" /> +۱۸.۴٪ نسبت به دوره قبل
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
            نرخ تسویه موفق: {toPersianDigits("96.2")}%
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
            محاسبه بر اساس سفارشات نهایی
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
            آماده ارسال به سامانه مودیان
          </div>
        </Card>
      </div>

      {/* Breakdown by Category */}
      <Card className="p-6">
        <h3 className="text-base font-bold text-foreground">سهم فروش به تفکیک دسته‌بندی</h3>
        <p className="mb-4 text-xs text-muted-foreground">درصد مشارکت هر گروه کالایی در درآمد کل فروشگاه</p>

        <div className="space-y-4">
          {salesByCategory.map((cat, i) => (
            <div key={i} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-foreground">{cat.name}</span>
                <span className="font-mono text-xs text-muted-foreground">
                  {formatPrice(cat.revenue)} ({toPersianDigits(cat.share)})
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className="h-full rounded-full bg-primary"
                  style={{ width: cat.share }}
                />
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
