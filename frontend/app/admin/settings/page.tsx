"use client";

import React, { useState } from "react";
import {
  Settings,
  Store,
  CreditCard,
  Truck,
  FileText,
  Save,
  CheckCircle2,
  Bell,
  Lock,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

export default function AdminSettingsPage() {
  const [saved, setSaved] = useState(false);

  // Form State
  const [storeName, setStoreName] = useState("فروشگاه اینترنتی آنلاین");
  const [supportPhone, setSupportPhone] = useState("021-88889999");
  const [supportEmail, setSupportEmail] = useState("support@site.com");
  const [taxRate, setTaxRate] = useState("10");
  const [freeShippingThreshold, setFreeShippingThreshold] = useState("10000000"); // 1M Toman (10M Rial)
  const [defaultShippingFee, setDefaultShippingFee] = useState("500000"); // 50K Toman
  const [zarinpalEnabled, setZarinpalEnabled] = useState(true);
  const [c2cEnabled, setC2cEnabled] = useState(true);
  const [walletEnabled, setWalletEnabled] = useState(true);
  const [cryptoEnabled, setCryptoEnabled] = useState(true);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">تنظیمات کلی فروشگاه</h1>
          <p className="text-sm text-muted-foreground">
            پیکربندی هویت تجاری، درگاه‌های پرداخت، مالیات و هزینه‌های ارسال
          </p>
        </div>
      </div>

      {saved && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-600">
          <CheckCircle2 className="h-4 w-4" /> تنظیمات با موفقیت ذخیره شدند.
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* General Store Identity */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <Store className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">مشخصات عمومی فروشگاه</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>نام فروشگاه</Label>
              <Input
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                placeholder="عنوان برند فروشگاه"
              />
            </div>
            <div className="space-y-2">
              <Label>شماره تماس پشتیبانی مشتریان</Label>
              <Input
                value={supportPhone}
                onChange={(e) => setSupportPhone(e.target.value)}
                placeholder="۰۲۱-۸۸۸۸۹۹۹۹"
              />
            </div>
            <div className="space-y-2">
              <Label>ایمیل ارتباط با ما</Label>
              <Input
                value={supportEmail}
                onChange={(e) => setSupportEmail(e.target.value)}
                placeholder="info@site.com"
              />
            </div>
            <div className="space-y-2">
              <Label>واحد پول رسمی سیستم</Label>
              <Input value="ریال ایران (نمایش در فرانت: تومان)" disabled className="bg-muted" />
            </div>
          </div>
        </Card>

        {/* Financial & Tax Settings */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <FileText className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">مالیات و حمل و نقل</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>نرخ مالیات بر ارزش افزوده (درصد)</Label>
              <Input
                type="number"
                value={taxRate}
                onChange={(e) => setTaxRate(e.target.value)}
                placeholder="10"
              />
              <p className="text-xs text-muted-foreground">طبق قانون مالیات بر ارزش افزوده ایران (۱۰٪)</p>
            </div>
            <div className="space-y-2">
              <Label>حداقل سفارش برای ارسال رایگان (ریال)</Label>
              <Input
                value={freeShippingThreshold}
                onChange={(e) => setFreeShippingThreshold(e.target.value)}
                placeholder="10000000"
              />
              <p className="text-xs text-muted-foreground">معادل ۱٬۰۰۰٬۰۰۰ تومان</p>
            </div>
            <div className="space-y-2">
              <Label>هزینه پیش‌فرض ارسال عادی (ریال)</Label>
              <Input
                value={defaultShippingFee}
                onChange={(e) => setDefaultShippingFee(e.target.value)}
                placeholder="500000"
              />
              <p className="text-xs text-muted-foreground">معادل ۵۰٬۰۰۰ تومان</p>
            </div>
          </div>
        </Card>

        {/* Payment Methods Toggle */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <CreditCard className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">روش‌های پرداخت فعال برای مشتریان</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">درگاه بانکی زرین‌پال (شاپرک)</div>
                <div className="text-xs text-muted-foreground">پذیرش کارت‌های عضو شتاب</div>
              </div>
              <input
                type="checkbox"
                checked={zarinpalEnabled}
                onChange={(e) => setZarinpalEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">کارت به کارت با بارگذاری فیش</div>
                <div className="text-xs text-muted-foreground">نیاز به تایید دستی مدیریت در پنل</div>
              </div>
              <input
                type="checkbox"
                checked={c2cEnabled}
                onChange={(e) => setC2cEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">پرداخت با کیف پول داخلی</div>
                <div className="text-xs text-muted-foreground">کسر آنی از موجودی حساب کاربر</div>
              </div>
              <input
                type="checkbox"
                checked={walletEnabled}
                onChange={(e) => setWalletEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">درگاه ارزی و رمزارز (NowPayments)</div>
                <div className="text-xs text-muted-foreground">پذیرش تتر (USDT)، بیت‌کوین و اتریوم</div>
              </div>
              <input
                type="checkbox"
                checked={cryptoEnabled}
                onChange={(e) => setCryptoEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>
          </div>
        </Card>

        {/* Submit */}
        <div className="flex justify-end">
          <Button type="submit" className="gap-2 px-8">
            <Save className="h-4 w-4" /> ذخیره تنظیمات
          </Button>
        </div>
      </form>
    </div>
  );
}
