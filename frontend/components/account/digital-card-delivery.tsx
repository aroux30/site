"use client";

import React, { useState } from "react";

export interface DeliveredCard {
  id: string;
  serial_number?: string | null;
  pin: string;
  delivery_type: "unique" | "shared" | "file";
  file_download_url?: string | null;
  delivered_at?: string | null;
  reading_at?: string | null;
}

interface DigitalCardDeliveryProps {
  orderNumber: string;
  cards: DeliveredCard[];
  onCardViewed?: (cardId: string) => void;
}

export function DigitalCardDelivery({
  orderNumber,
  cards,
  onCardViewed,
}: DigitalCardDeliveryProps) {
  const [revealedCards, setRevealedCards] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Toggle reveal and trigger the legal viewing audit API
  const handleToggleReveal = async (card: DeliveredCard) => {
    const isCurrentlyRevealed = revealedCards[card.id];
    const nextState = !isCurrentlyRevealed;

    setRevealedCards((prev) => ({ ...prev, [card.id]: nextState }));

    // If revealing for the first time, send legal reading confirmation
    if (nextState && !card.reading_at && onCardViewed) {
      try {
        await fetch(`/api/v1/inventory/digital/cards/${card.id}/viewed`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        onCardViewed(card.id);
      } catch (err) {
        console.error("Failed to mark card as viewed:", err);
      }
    }
  };

  const handleCopy = (card: DeliveredCard) => {
    navigator.clipboard.writeText(card.pin);
    setCopiedId(card.id);
    setTimeout(() => setCopiedId(null), 2500);
  };

  const handleDownloadTxt = () => {
    const lines = [
      `فاکتور سفارش: ${orderNumber}`,
      `تاریخ دریافت: ${new Date().toLocaleDateString("fa-IR")}`,
      "------------------------------------------",
      ...cards.map(
        (c, i) =>
          `${i + 1}. پین کد: ${c.pin}${c.serial_number ? ` | شماره سریال: ${c.serial_number}` : ""}`
      ),
      "------------------------------------------",
      "از خرید شما متشکریم.",
    ];

    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `License_${orderNumber}.txt`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-950/10 p-6 text-right" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-emerald-500/20 pb-4">
        <div>
          <h3 className="text-lg font-bold text-emerald-400">کدهای لایسنس و دسترسی دیجیتال</h3>
          <p className="mt-1 text-xs text-neutral-400">
            برای مشاهده و کپی، روی دکمه نمایش یا آیکون کپی کلیک فرمایید.
          </p>
        </div>
        <button
          onClick={handleDownloadTxt}
          className="rounded-xl border border-emerald-500/40 bg-emerald-500/10 px-4 py-2 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/20"
        >
          دانلود فایل متنی (TXT)
        </button>
      </div>

      <div className="mt-6 space-y-4">
        {cards.map((card, index) => {
          const isRevealed = revealedCards[card.id];
          const isCopied = copiedId === card.id;

          return (
            <div
              key={card.id}
              className="flex flex-col gap-3 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4 transition md:flex-row md:items-center md:justify-between"
            >
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-neutral-800 text-xs text-neutral-300">
                    {index + 1}
                  </span>
                  {card.serial_number && (
                    <span className="text-xs text-neutral-400">
                      سریال: <span className="font-mono text-neutral-300">{card.serial_number}</span>
                    </span>
                  )}
                  {card.delivery_type === "file" && (
                    <span className="rounded bg-sky-950 px-2 py-0.5 text-[10px] text-sky-400">
                      فایل دانلودی
                    </span>
                  )}
                </div>

                <div className="pt-2 font-mono text-base tracking-widest text-white">
                  {isRevealed ? (
                    <span className="select-all text-emerald-400 font-bold">{card.pin}</span>
                  ) : (
                    <span className="text-neutral-500">••••-••••-••••-••••</span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleToggleReveal(card)}
                  className="rounded-lg bg-neutral-800 px-3 py-1.5 text-xs text-neutral-300 transition hover:bg-neutral-700"
                >
                  {isRevealed ? "مخفی‌سازی" : "نمایش کد"}
                </button>

                <button
                  onClick={() => handleCopy(card)}
                  disabled={!isRevealed}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                    !isRevealed
                      ? "cursor-not-allowed bg-neutral-800/40 text-neutral-600"
                      : isCopied
                      ? "bg-emerald-600 text-white"
                      : "bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30"
                  }`}
                >
                  {isCopied ? "کپی شد!" : "کپی پین"}
                </button>

                {card.file_download_url && (
                  <a
                    href={card.file_download_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-lg bg-sky-500/20 px-3 py-1.5 text-xs font-medium text-sky-300 transition hover:bg-sky-500/30"
                  >
                    دانلود فایل
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
