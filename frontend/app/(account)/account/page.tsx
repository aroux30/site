"use client";

import { useState } from "react";
import Link from "next/link";
import {
  User,
  Package,
  MapPin,
  Heart,
  Settings,
  LogOut,
  Edit3,
  Trash2,
  Plus,
  ShoppingBag,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "@/components/ui/tabs";
import { formatPrice } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  Sample data                                                        */
/* ------------------------------------------------------------------ */

const orders = [
  {
    id: "ORD-1001",
    date: "۱۴۰۳/۰۶/۱۵",
    items: "۲ کالا",
    total: 15_000_000,
    status: "تحویل شده",
    badgeVariant: "success" as const,
  },
  {
    id: "ORD-1002",
    date: "۱۴۰۳/۰۶/۲۰",
    items: "۱ کالا",
    total: 9_800_000,
    status: "در حال ارسال",
    badgeVariant: "info" as const,
  },
  {
    id: "ORD-1003",
    date: "۱۴۰۳/۰۶/۲۵",
    items: "۳ کالا",
    total: 3_135_000,
    status: "در انتظار پرداخت",
    badgeVariant: "warning" as const,
  },
];

const addresses = [
  {
    id: 1,
    title: "خانه",
    recipient: "علی محمدی",
    phone: "۰۹۱۲۳۴۵۶۷۸۹",
    address: "تهران، خیابان ولیعصر، کوچه بهار، پلاک ۱۲، واحد ۳",
    postalCode: "۱۲۳۴۵۶۷۸۹۰",
    isDefault: true,
  },
  {
    id: 2,
    title: "محل کار",
    recipient: "علی محمدی",
    phone: "۰۹۱۲۳۴۵۶۷۸۹",
    address: "تهران، میدان ونک، خیابان ملاصدرا، برج آسمان، طبقه ۵",
    postalCode: "۱۹۸۷۶۵۴۳۲۱",
    isDefault: false,
  },
];

const wishlistProducts = [
  {
    id: "1",
    title: "گوشی موبایل سامسونگ گلکسی A54",
    price: 12_500_000,
    originalPrice: 14_000_000,
    inStock: true,
  },
  {
    id: "2",
    title: "هدفون بی‌سیم سونی WH-1000XM5",
    price: 9_800_000,
    originalPrice: 11_000_000,
    inStock: true,
  },
  {
    id: "3",
    title: "ساعت هوشمند شیائومی Band 8",
    price: 2_500_000,
    originalPrice: 2_800_000,
    inStock: false,
  },
  {
    id: "4",
    title: "لپ‌تاپ ایسوس VivoBook 15",
    price: 32_000_000,
    originalPrice: null,
    inStock: true,
  },
];

/* ------------------------------------------------------------------ */
/*  Sidebar nav items                                                  */
/* ------------------------------------------------------------------ */

const sidebarNav = [
  { key: "profile", label: "اطلاعات حساب", icon: User },
  { key: "orders", label: "سفارش‌ها", icon: Package },
  { key: "addresses", label: "آدرس‌ها", icon: MapPin },
  { key: "wishlist", label: "علاقه‌مندی‌ها", icon: Heart },
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export default function AccountPage() {
  const [activeTab, setActiveTab] = useState("profile");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-foreground">حساب کاربری</h1>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        {/* ---- Desktop sidebar ---- */}
        <aside className="hidden lg:block">
          <Card className="p-4">
            {/* User avatar & name */}
            <div className="mb-4 flex items-center gap-3 border-b border-border pb-4">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary">
                <User className="h-7 w-7" />
              </div>
              <div>
                <p className="font-semibold text-foreground">علی محمدی</p>
                <p className="text-sm text-muted-foreground">
                  ali@example.com
                </p>
              </div>
            </div>

            {/* Navigation */}
            <nav className="space-y-1">
              {sidebarNav.map((item) => (
                <button
                  key={item.key}
                  onClick={() => setActiveTab(item.key)}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                    activeTab === item.key
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </button>
              ))}

              <Separator className="my-2" />

              <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                <Settings className="h-4 w-4" />
                تنظیمات
              </button>
              <button className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10">
                <LogOut className="h-4 w-4" />
                خروج از حساب
              </button>
            </nav>
          </Card>
        </aside>

        {/* ---- Main content ---- */}
        <div className="lg:col-span-3">
          {/* Mobile tabs */}
          <Tabs
            value={activeTab}
            onValueChange={setActiveTab}
            className="w-full"
          >
            <TabsList className="mb-6 flex w-full lg:hidden">
              {sidebarNav.map((item) => (
                <TabsTrigger
                  key={item.key}
                  value={item.key}
                  className="flex-1 gap-1.5 text-xs sm:text-sm"
                >
                  <item.icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{item.label}</span>
                </TabsTrigger>
              ))}
            </TabsList>

            {/* ---------- Tab 1: Profile ---------- */}
            <TabsContent value="profile" forceMount className={activeTab !== "profile" ? "hidden" : ""}>
              <Card className="p-6">
                <h2 className="mb-6 text-lg font-semibold text-foreground">
                  اطلاعات حساب
                </h2>
                <form className="space-y-5">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="fullName">نام و نام خانوادگی</Label>
                      <Input
                        id="fullName"
                        defaultValue="علی محمدی"
                        placeholder="نام کامل"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="email">ایمیل</Label>
                      <Input
                        id="email"
                        type="email"
                        defaultValue="ali@example.com"
                        placeholder="ایمیل"
                        dir="ltr"
                        className="text-left"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <Label htmlFor="phone">شماره موبایل</Label>
                      <Input
                        id="phone"
                        defaultValue="09123456789"
                        placeholder="09123456789"
                        dir="ltr"
                        className="text-left"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="nationalId">کد ملی</Label>
                      <Input
                        id="nationalId"
                        placeholder="کد ملی"
                        dir="ltr"
                        className="text-left"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="birthday">تاریخ تولد</Label>
                    <Input
                      id="birthday"
                      placeholder="مثال: ۱۳۷۵/۰۱/۰۱"
                    />
                  </div>

                  <Separator />

                  <div className="flex justify-end">
                    <Button type="button">ذخیره تغییرات</Button>
                  </div>
                </form>
              </Card>
            </TabsContent>

            {/* ---------- Tab 2: Orders ---------- */}
            <TabsContent value="orders" forceMount className={activeTab !== "orders" ? "hidden" : ""}>
              <Card className="p-6">
                <h2 className="mb-6 text-lg font-semibold text-foreground">
                  سفارش‌ها
                </h2>

                <div className="space-y-4">
                  {orders.map((order) => (
                    <div
                      key={order.id}
                      className="flex flex-col gap-4 rounded-lg border border-border p-4 sm:flex-row sm:items-center sm:justify-between"
                    >
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                          <Package className="h-5 w-5 text-muted-foreground" />
                        </div>
                        <div>
                          <p className="font-medium text-foreground">
                            سفارش {order.id}
                          </p>
                          <p className="text-sm text-muted-foreground">
                            {order.date} &middot; {order.items}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <Badge variant={order.badgeVariant}>
                          {order.status}
                        </Badge>
                        <span className="font-semibold text-foreground">
                          {formatPrice(order.total)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </TabsContent>

            {/* ---------- Tab 3: Addresses ---------- */}
            <TabsContent value="addresses" forceMount className={activeTab !== "addresses" ? "hidden" : ""}>
              <Card className="p-6">
                <div className="mb-6 flex items-center justify-between">
                  <h2 className="text-lg font-semibold text-foreground">
                    آدرس‌ها
                  </h2>
                  <Button variant="outline" size="sm">
                    <Plus className="ml-2 h-4 w-4" />
                    افزودن آدرس
                  </Button>
                </div>

                <div className="space-y-4">
                  {addresses.map((addr) => (
                    <div
                      key={addr.id}
                      className="rounded-lg border border-border p-4"
                    >
                      <div className="mb-3 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4 text-primary" />
                          <span className="font-medium text-foreground">
                            {addr.title}
                          </span>
                          {addr.isDefault && (
                            <Badge variant="secondary">پیش‌فرض</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <button className="text-muted-foreground transition-colors hover:text-foreground">
                            <Edit3 className="h-4 w-4" />
                          </button>
                          <button className="text-muted-foreground transition-colors hover:text-destructive">
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                      <p className="mb-1 text-sm text-foreground">
                        {addr.address}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        گیرنده: {addr.recipient} &middot; {addr.phone}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        کد پستی: {addr.postalCode}
                      </p>
                    </div>
                  ))}
                </div>
              </Card>
            </TabsContent>

            {/* ---------- Tab 4: Wishlist ---------- */}
            <TabsContent value="wishlist" forceMount className={activeTab !== "wishlist" ? "hidden" : ""}>
              <Card className="p-6">
                <h2 className="mb-6 text-lg font-semibold text-foreground">
                  علاقه‌مندی‌ها
                </h2>

                {wishlistProducts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12">
                    <Heart className="mb-4 h-12 w-12 text-muted-foreground" />
                    <p className="mb-2 text-lg font-medium text-foreground">
                      لیست علاقه‌مندی‌ها خالی است
                    </p>
                    <p className="mb-6 text-muted-foreground">
                      محصولات مورد علاقه خود را اضافه کنید.
                    </p>
                    <Link href="/products">
                      <Button variant="outline">مشاهده محصولات</Button>
                    </Link>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {wishlistProducts.map((product) => (
                      <div
                        key={product.id}
                        className="flex gap-4 rounded-lg border border-border p-4"
                      >
                        <div className="flex h-20 w-20 flex-shrink-0 items-center justify-center rounded-lg bg-muted">
                          <ShoppingBag className="h-8 w-8 text-muted-foreground" />
                        </div>
                        <div className="flex flex-1 flex-col justify-between">
                          <div>
                            <h3 className="mb-1 text-sm font-medium text-foreground">
                              {product.title}
                            </h3>
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-bold text-primary">
                                {formatPrice(product.price)}
                              </span>
                              {product.originalPrice && (
                                <span className="text-xs text-muted-foreground line-through">
                                  {formatPrice(product.originalPrice)}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="mt-2 flex items-center justify-between">
                            <Badge
                              variant={
                                product.inStock ? "success" : "secondary"
                              }
                            >
                              {product.inStock ? "موجود" : "ناموجود"}
                            </Badge>
                            <button className="text-muted-foreground transition-colors hover:text-destructive">
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </div>
  );
}
