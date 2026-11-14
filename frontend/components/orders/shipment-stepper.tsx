"use client";

import React from "react";
import {
  ShoppingCart,
  CreditCard,
  ClipboardCheck,
  CheckCircle2,
} from "lucide-react";
import {
  ORDER_PROGRESS_STEPS,
  ORDER_PROGRESS_LABELS,
  ORDER_PROGRESS_DESCRIPTIONS,
  resolveOrderProgress,
  getOrderStepIndex,
  type OrderProgressStage,
} from "@/lib/shipment-tracking";

export interface OrderProgressStepperProps {
  /** The raw backend order status (e.g. "pending", "processing", "completed"). */
  status: string;
}

const STEP_ICONS = [ShoppingCart, CreditCard, ClipboardCheck, CheckCircle2];

/**
 * Order progress stepper for the customer-facing tracking dialog.
 *
 * Shows 4 stages that map to the real order lifecycle:
 *   ثبت سفارش → تایید پرداخت → بررسی و پردازش → تکمیل سفارش
 *
 * Terminal statuses (canceled / refunded) are NOT shown here — the parent
 * dialog renders a dedicated banner for those cases.
 */
export function OrderProgressStepper({ status }: OrderProgressStepperProps) {
  const result = resolveOrderProgress(status);

  // Terminal statuses should be handled by the parent; if we reach here,
  // show the first step as a safe fallback.
  const activeStage: OrderProgressStage = result.isTerminal
    ? "ORDER_PLACED"
    : result.stage;
  const activeStepIndex = getOrderStepIndex(activeStage);

  return (
    <div className="space-y-6 rounded-2xl border border-border bg-card p-5" dir="rtl">
      {/* 4-Step Order Progress Stepper */}
      <div className="relative pt-2">
        {/* Progress line connecting steps */}
        <div className="absolute top-[calc(0.5rem+20px)] right-[calc(12.5%+20px)] left-[calc(12.5%+20px)] h-0.5 bg-border z-0" />
        <div
          className="absolute top-[calc(0.5rem+20px)] right-[calc(12.5%+20px)] h-0.5 bg-primary z-0 transition-all duration-500"
          style={{
            width:
              activeStepIndex === 0
                ? "0%"
                : `${(activeStepIndex / (ORDER_PROGRESS_STEPS.length - 1)) * 75}%`,
          }}
        />

        <div className="grid grid-cols-4 gap-2 relative z-10">
          {ORDER_PROGRESS_STEPS.map((step, idx) => {
            const Icon = STEP_ICONS[idx];
            const isCompleted = idx < activeStepIndex;
            const isCurrent = idx === activeStepIndex;

            return (
              <div key={step} className="flex flex-col items-center text-center space-y-2">
                <div
                  className={`relative flex h-10 w-10 items-center justify-center rounded-2xl border-2 transition-all ${
                    isCompleted
                      ? "border-emerald-500 bg-emerald-500 text-white shadow-sm"
                      : isCurrent
                      ? "border-primary bg-primary text-primary-foreground shadow-md ring-4 ring-primary/20"
                      : "border-border bg-muted text-muted-foreground/60"
                  }`}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    Icon && <Icon className="h-4 w-4" />
                  )}
                </div>

                <div>
                  <p
                    className={`text-xs font-bold leading-tight ${
                      isCurrent
                        ? "text-primary"
                        : isCompleted
                        ? "text-foreground"
                        : "text-muted-foreground"
                    }`}
                  >
                    {ORDER_PROGRESS_LABELS[step]}
                  </p>
                  {isCurrent && (
                    <span className="inline-block mt-0.5 text-[10px] font-medium text-primary/80">
                      وضعیت جاری
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Current status description */}
        <div className="mt-4 rounded-xl bg-muted/40 p-3 text-xs text-muted-foreground text-center">
          {ORDER_PROGRESS_DESCRIPTIONS[activeStage]}
        </div>
      </div>
    </div>
  );
}

// ── Legacy re-export ────────────────────────────────────────────────────

/** @deprecated Use OrderProgressStepper instead */
export const ShipmentStepper = OrderProgressStepper;

/** @deprecated Use OrderProgressStepperProps instead */
export type ShipmentStepperProps = OrderProgressStepperProps;
