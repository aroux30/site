"use client";

import React, { useState } from "react";

export function ShaparakEmergencyNotice() {
  const [mobile, setMobile] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mobile.trim() || mobile.length < 10) return;

    setLoading(true);
    try {
      // Register lead to receive SMS notification once gateways are restored (Karta Offline.php)
      await fetch("/api/v1/notifications/notices/sms/dispatch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mobile: mobile.trim(),
          text: "شماره شما در صف اطلاع‌رسانی رفع اختلال درگاه‌های شاپرک ثبت شد.",
        }),
      });
      setSubmitted(true);
    } catch (err) {
      console.error("Lead capture failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-6 text-right" dir="rtl">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400 font-bold">
          !
        </div>
        <div className="space-y-2">
          <h4 className="text-base font-bold text-amber-400">
            اختلال موقت در سوئیچ شاپرک و درگاه‌های بانکی
          </h4>
          <p className="text-xs leading-relaxed text-neutral-300">
            با توجه به اعلام بانک مرکزی و اختلال موقت در درگاه‌های پرداخت آنلاین، در صورت عدم موفقیت در
            پرداخت، می‌توانید از گزینه «کارت به کارت دستی» استفاده کرده یا شماره موبایل خود را وارد نمایید
            تا به محض برطرف شدن مشکل، از طریق پیامک به شما اطلاع دهیم.
          </p>

          {!submitted ? (
            <form onSubmit={handleSubmit} className="mt-4 flex flex-wrap items-center gap-3">
              <input
                type="tel"
                placeholder="شماره موبایل (مثال: ۰۹۱۲۳۴۵۶۷۸۹)"
                value={mobile}
                onChange={(e) => setMobile(e.target.value)}
                className="rounded-xl border border-neutral-700 bg-neutral-900 px-4 py-2 text-xs text-white placeholder-neutral-500 focus:border-amber-500 focus:outline-none"
                dir="ltr"
              />
              <button
                type="submit"
                disabled={loading}
                className="rounded-xl bg-amber-500 px-4 py-2 text-xs font-semibold text-neutral-950 transition hover:bg-amber-400 disabled:opacity-50"
              >
                {loading ? "در حال ثبت..." : "به من اطلاع بده"}
              </button>
            </form>
          ) : (
            <div className="mt-3 rounded-lg bg-amber-500/10 p-2 text-xs font-medium text-amber-300">
              ✓ شماره شما با موفقیت ثبت شد. به محض رفع اختلال شاپرک، پیامک اطلاع‌رسانی ارسال خواهد شد.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
