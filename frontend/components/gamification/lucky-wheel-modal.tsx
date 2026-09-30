"use client";

import React, { useState } from "react";

interface LuckyWheelModalProps {
  orderId: string;
  isOpen: boolean;
  onClose: () => void;
  onPrizeClaimed?: (prize: { title: string; value: number; type: string }) => void;
}

export function LuckyWheelModal({
  orderId,
  isOpen,
  onClose,
  onPrizeClaimed,
}: LuckyWheelModalProps) {
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState<{ title: string; message: string; value: number } | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSpin = async () => {
    if (spinning || result) return;
    setSpinning(true);
    setError(null);

    try {
      // Small artificial delay for spinning animation excitement
      const [res] = await Promise.all([
        fetch("/api/v1/gamification/gifts/lucky-wheel/spin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ order_id: orderId }),
        }),
        new Promise((resolve) => setTimeout(resolve, 2000)),
      ]);

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "خطا در چرخاندن گردونه");
      }

      setResult({
        title: data.prize_title,
        message: data.message,
        value: data.awarded_value,
      });

      if (onPrizeClaimed) {
        onPrizeClaimed({
          title: data.prize_title,
          value: data.awarded_value,
          type: data.prize_type,
        });
      }
    } catch (err: any) {
      setError(err.message || "امکان چرخاندن گردونه وجود ندارد");
    } finally {
      setSpinning(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" dir="rtl">
      <div className="relative w-full max-w-md rounded-3xl border border-amber-500/40 bg-neutral-900 p-6 text-center shadow-2xl shadow-amber-500/10">
        <h3 className="text-xl font-extrabold text-amber-400">گردونه شانس مشتریان</h3>
        <p className="mt-1 text-xs text-neutral-400">
          به پاس خرید موفق شما، یک شانس رایگان برای دریافت اعتبار یا کد تخفیف به شما تعلق گرفت!
        </p>

        {/* Visual Wheel Representation */}
        <div className="my-8 flex justify-center">
          <div
            className={`relative flex h-48 w-48 items-center justify-center rounded-full border-4 border-amber-500 bg-gradient-to-tr from-amber-600/30 via-yellow-500/20 to-amber-700/30 shadow-inner transition-transform duration-[2000ms] ${
              spinning ? "rotate-[720deg] scale-105" : ""
            }`}
          >
            <div className="absolute inset-2 rounded-full border border-dashed border-amber-400/40" />
            <span className="text-3xl">🎁</span>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-xl bg-rose-500/10 p-3 text-xs text-rose-400 font-medium">
            {error}
          </div>
        )}

        {result ? (
          <div className="mb-6 rounded-2xl bg-amber-500/10 p-4 border border-amber-500/30">
            <h4 className="text-base font-bold text-amber-300">{result.message}</h4>
            {result.value > 0 && (
              <p className="mt-1 text-xs text-neutral-300">
                مبلغ <span className="font-bold text-white">{result.value.toLocaleString("fa-IR")} ریال</span> به کیف‌پول شما واریز شد.
              </p>
            )}
            <button
              onClick={onClose}
              className="mt-4 w-full rounded-xl bg-amber-500 py-2.5 text-xs font-bold text-neutral-950 transition hover:bg-amber-400"
            >
              متوجه شدم، بستن پنجره
            </button>
          </div>
        ) : (
          <div className="flex gap-3">
            <button
              onClick={handleSpin}
              disabled={spinning}
              className="flex-1 rounded-xl bg-gradient-to-r from-amber-500 to-yellow-400 py-3 text-sm font-bold text-neutral-950 shadow-lg shadow-amber-500/20 transition hover:brightness-110 disabled:opacity-50"
            >
              {spinning ? "در حال چرخش..." : "شانست رو امتحان کن!"}
            </button>
            <button
              onClick={onClose}
              disabled={spinning}
              className="rounded-xl border border-neutral-700 px-4 py-3 text-xs text-neutral-400 transition hover:bg-neutral-800"
            >
              انصراف
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
