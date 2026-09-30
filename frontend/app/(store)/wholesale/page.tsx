"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Building2,
  Send,
  CheckCircle,
  Loader2,
  AlertCircle,
  Percent,
  Truck,
  Headphones,
  CreditCard,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import apiClient from "@/lib/api/client";

/**
 * Wholesale inquiry form — the storefront half of the CRM pipeline.
 *
 * The CRM module and its public capture endpoint shipped with an admin board
 * and no way for a business to actually *reach* it; the funnel had an intake
 * nobody could walk into. This page is that door.
 *
 * It deliberately does not ask for a budget: a self-declared figure is
 * worthless and it is the field spammers fill first. Staff record the
 * estimate after a real conversation.
 */

const BENEFITS = [
  {
    icon: Percent,
    title: "قیمت‌گذاری پلکانی",
    text: "هرچه حجم خرید بیشتر، قیمت واحد پایین‌تر — بر اساس پله‌های تعریف‌شده.",
  },
  {
    icon: CreditCard,
    title: "خرید اعتباری",
    text: "امکان خرید با اعتبار پیش‌پرداخت و تسویه دوره‌ای برای همکاران فعال.",
  },
  {
    icon: Truck,
    title: "ارسال اختصاصی",
    text: "هماهنگی ارسال برای سفارش‌های حجیم و تحویل در محل کسب‌وکار.",
  },
  {
    icon: Headphones,
    title: "پشتیبانی اختصاصی",
    text: "کارشناس فروش سازمانی و پاسخ‌گویی مستقیم در ساعات کاری.",
  },
];

export default function WholesalePage() {
  const [form, setForm] = useState({
    contact_name: "",
    company_name: "",
    phone: "",
    email: "",
    message: "",
  });
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus("sending");
    setErrorMessage("");

    try {
      await apiClient.post("/crm/inquiries", {
        contact_name: form.contact_name.trim(),
        phone: form.phone.trim(),
        company_name: form.company_name.trim() || null,
        email: form.email.trim() || null,
        message: form.message.trim() || null,
      });
      setStatus("sent");
      setForm({ contact_name: "", company_name: "", phone: "", email: "", message: "" });
    } catch (err: unknown) {
      setStatus("error");
      const detail =
        typeof err === "object" && err !== null && "response" in err
          ? // The backend returns Persian messages; show them rather than a
            // generic failure string, because "شماره تماس الزامی است" tells the
            // user exactly what to fix.
            ((err as { response?: { data?: { detail?: string } } }).response?.data
              ?.detail ?? "")
          : "";
      setErrorMessage(detail || "ارسال درخواست انجام نشد. لطفاً دوباره تلاش کنید.");
    }
  };

  const isValid = form.contact_name.trim().length > 0 && form.phone.trim().length > 0;

  return (
    <div className="container mx-auto max-w-5xl px-4 py-12" dir="rtl">
      <div className="text-center max-w-3xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-semibold mb-4">
          <Building2 className="w-4 h-4" />
          فروش سازمانی و عمده
        </div>
        <h1 className="text-3xl md:text-4xl font-black text-foreground mb-4">
          خرید عمده برای کسب‌وکارها
        </h1>
        <p className="text-muted-foreground text-sm md:text-base leading-relaxed">
          اگر کسب‌وکار، فروشگاه یا شرکت شما به خرید حجمی نیاز دارد، فرم زیر را
          پر کنید. کارشناس فروش سازمانی در اولین فرصت کاری با شما تماس می‌گیرد و
          شرایط اختصاصی را اعلام می‌کند.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-12">
        {BENEFITS.map((b) => (
          <Card key={b.title} className="p-5 flex gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <b.icon className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm mb-1">{b.title}</h3>
              <p className="text-xs text-muted-foreground leading-relaxed">{b.text}</p>
            </div>
          </Card>
        ))}
      </div>

      {status === "sent" ? (
        <Card className="p-10 text-center max-w-2xl mx-auto">
          <CheckCircle className="w-14 h-14 text-emerald-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">درخواست شما ثبت شد</h2>
          <p className="text-sm text-muted-foreground mb-6 leading-relaxed">
            کارشناس فروش سازمانی در اولین فرصت کاری با شما تماس می‌گیرد. برای
            پیگیری سریع‌تر می‌توانید با پشتیبانی هم تماس بگیرید.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button variant="outline" onClick={() => setStatus("idle")}>
              ثبت درخواست دیگر
            </Button>
            <Link href="/products">
              <Button>مشاهده محصولات</Button>
            </Link>
          </div>
        </Card>
      ) : (
        <Card className="p-6 md:p-8 max-w-2xl mx-auto">
          <h2 className="text-lg font-bold mb-1">فرم درخواست همکاری</h2>
          <p className="text-xs text-muted-foreground mb-6">
            فیلدهای ستاره‌دار الزامی هستند.
          </p>

          <form onSubmit={submit} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="contact_name">نام و نام خانوادگی *</Label>
                <Input
                  id="contact_name"
                  value={form.contact_name}
                  onChange={(e) => setForm((f) => ({ ...f, contact_name: e.target.value }))}
                  required
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="company_name">نام کسب‌وکار / شرکت</Label>
                <Input
                  id="company_name"
                  value={form.company_name}
                  onChange={(e) => setForm((f) => ({ ...f, company_name: e.target.value }))}
                  className="mt-1"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="phone">شماره تماس *</Label>
                <Input
                  id="phone"
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  placeholder="۰۹۱۲۳۴۵۶۷۸۹"
                  required
                  dir="ltr"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="email">ایمیل</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))}
                  dir="ltr"
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="message">توضیح درخواست</Label>
              <Textarea
                id="message"
                value={form.message}
                onChange={(e) => setForm((f) => ({ ...f, message: e.target.value }))}
                rows={4}
                placeholder="نوع محصولات مورد نیاز، حجم تقریبی خرید و هر توضیح دیگری که کمک می‌کند."
                className="mt-1"
              />
            </div>

            {status === "error" && (
              <div className="flex items-start gap-2 rounded-lg bg-destructive/10 p-3 text-xs text-destructive">
                <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{errorMessage}</span>
              </div>
            )}

            <Button type="submit" disabled={!isValid || status === "sending"} className="w-full gap-2">
              {status === "sending" ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  در حال ارسال…
                </>
              ) : (
                <>
                  <Send className="w-4 h-4" />
                  ارسال درخواست
                </>
              )}
            </Button>

            <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
              اطلاعات شما فقط برای پیگیری همین درخواست استفاده می‌شود. برای
              پاسخ سریع‌تر، شماره تماس را کامل وارد کنید.
            </p>
          </form>
        </Card>
      )}
    </div>
  );
}
