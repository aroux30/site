import { Card } from "@/components/ui/card";
import {
  ShoppingCart,
  Users,
  Package,
  TrendingUp,
  ArrowUpLeft,
  ArrowDownLeft,
} from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "داشبورد مدیریت",
};

const overviewStats = [
  {
    label: "فروش امروز",
    value: "۱۲,۵۰۰,۰۰۰ تومان",
    change: "+۱۲%",
    isPositive: true,
    icon: TrendingUp,
    color: "text-emerald-600 bg-emerald-50",
  },
  {
    label: "سفارش‌های جدید",
    value: "۲۴",
    change: "+۸%",
    isPositive: true,
    icon: ShoppingCart,
    color: "text-blue-600 bg-blue-50",
  },
  {
    label: "کاربران جدید",
    value: "۱۸",
    change: "-۳%",
    isPositive: false,
    icon: Users,
    color: "text-purple-600 bg-purple-50",
  },
  {
    label: "محصولات فعال",
    value: "۱,۲۴۶",
    change: "+۵%",
    isPositive: true,
    icon: Package,
    color: "text-orange-600 bg-orange-50",
  },
];

const recentOrders = [
  {
    id: "ORD-100256",
    customer: "علی محمدی",
    amount: "۲,۳۵۰,۰۰۰ تومان",
    status: "در انتظار پرداخت",
    statusColor: "text-yellow-600 bg-yellow-50",
    date: "۵ دقیقه پیش",
  },
  {
    id: "ORD-100255",
    customer: "فاطمه احمدی",
    amount: "۸,۹۰۰,۰۰۰ تومان",
    status: "پرداخت شده",
    statusColor: "text-green-600 bg-green-50",
    date: "۱۵ دقیقه پیش",
  },
  {
    id: "ORD-100254",
    customer: "محمد حسینی",
    amount: "۱,۲۰۰,۰۰۰ تومان",
    status: "در حال ارسال",
    statusColor: "text-blue-600 bg-blue-50",
    date: "۳۰ دقیقه پیش",
  },
  {
    id: "ORD-100253",
    customer: "زهرا کریمی",
    amount: "۴,۵۰۰,۰۰۰ تومان",
    status: "تحویل داده شده",
    statusColor: "text-green-600 bg-green-50",
    date: "۱ ساعت پیش",
  },
  {
    id: "ORD-100252",
    customer: "رضا نوری",
    amount: "۶۵۰,۰۰۰ تومان",
    status: "لغو شده",
    statusColor: "text-red-600 bg-red-50",
    date: "۲ ساعت پیش",
  },
];

const topProducts = [
  { name: "گوشی سامسونگ گلکسی A54", sales: 128, revenue: "۱.۶ میلیارد تومان" },
  { name: "لپ‌تاپ ایسوس VivoBook", sales: 64, revenue: "۲.۰ میلیارد تومان" },
  { name: "هدفون سونی WH-1000XM5", sales: 256, revenue: "۲.۵ میلیارد تومان" },
  { name: "ساعت هوشمند شیائومی", sales: 312, revenue: "۷۸۰ میلیون تومان" },
  { name: "تبلت اپل iPad Air", sales: 89, revenue: "۲.۱ میلیارد تومان" },
];

export default function AdminDashboardPage() {
  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">داشبورد</h1>
        <p className="text-muted-foreground">
          نمای کلی عملکرد فروشگاه
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {overviewStats.map((stat) => (
          <Card key={stat.label} className="p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">{stat.label}</p>
                <p className="mt-1 text-2xl font-bold text-foreground">
                  {stat.value}
                </p>
                <div className="mt-1 flex items-center gap-1">
                  {stat.isPositive ? (
                    <ArrowUpLeft className="h-3 w-3 text-green-500" />
                  ) : (
                    <ArrowDownLeft className="h-3 w-3 text-red-500" />
                  )}
                  <span
                    className={`text-xs font-medium ${stat.isPositive ? "text-green-500" : "text-red-500"}`}
                  >
                    {stat.change}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    نسبت به دیروز
                  </span>
                </div>
              </div>
              <div className={`rounded-xl p-3 ${stat.color}`}>
                <stat.icon className="h-6 w-6" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Recent Orders */}
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            سفارش‌های اخیر
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-3 text-right font-medium text-muted-foreground">
                    شماره
                  </th>
                  <th className="pb-3 text-right font-medium text-muted-foreground">
                    مشتری
                  </th>
                  <th className="pb-3 text-right font-medium text-muted-foreground">
                    مبلغ
                  </th>
                  <th className="pb-3 text-right font-medium text-muted-foreground">
                    وضعیت
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recentOrders.map((order) => (
                  <tr key={order.id} className="hover:bg-muted/50">
                    <td className="py-3 font-medium text-foreground">
                      {order.id}
                    </td>
                    <td className="py-3 text-muted-foreground">
                      {order.customer}
                    </td>
                    <td className="py-3 text-foreground">{order.amount}</td>
                    <td className="py-3">
                      <span
                        className={`rounded-full px-2 py-1 text-xs font-medium ${order.statusColor}`}
                      >
                        {order.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Top Products */}
        <Card className="p-6">
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            محصولات پرفروش
          </h2>
          <div className="space-y-4">
            {topProducts.map((product, index) => (
              <div
                key={product.name}
                className="flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-muted text-sm font-medium text-muted-foreground">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {product.name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {product.sales} فروش
                    </p>
                  </div>
                </div>
                <span className="text-sm font-medium text-foreground">
                  {product.revenue}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
