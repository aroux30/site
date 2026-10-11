"use client";

import React, { useState } from "react";
import {
  Package,
  Truck,
  MapPin,
  CheckCircle2,
  Copy,
  Check,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  SHIPMENT_STATUS_STEPS,
  SHIPMENT_STATUS_LABELS,
  SHIPMENT_STATUS_DESCRIPTIONS,
  getShipmentStepIndex,
  resolveShipmentStatus,
  type ShipmentStatus,
  type ShipmentTrackingEvent,
} from "@/lib/shipment-tracking";

export interface ShipmentStepperProps {
  trackingCode?: string | null;
  carrier?: string | null;
  status: string;
  events?: ShipmentTrackingEvent[];
}

const STEP_ICONS = [Package, Truck, MapPin, CheckCircle2];

export function ShipmentStepper({
  trackingCode,
  carrier = "پست",
  status,
  events,
}: ShipmentStepperProps) {
  const [copied, setCopied] = useState(false);

  const currentStatus: ShipmentStatus = resolveShipmentStatus(status);
  const activeStepIndex = getShipmentStepIndex(currentStatus);

  const handleCopyTrackingCode = () => {
    if (!trackingCode) return;
    navigator.clipboard.writeText(trackingCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 rounded-2xl border border-border bg-card p-5" dir="rtl">
      {/* Top Header: Carrier & Tracking Code */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <Truck className="h-5 w-5" />
          </div>
          <div>
            <span className="text-xs text-muted-foreground block">شرکت حمل‌ونقل:</span>
            <span className="text-sm font-bold text-foreground">
              {carrier || "پست"}
            </span>
          </div>
        </div>

        {trackingCode && (
          <div className="flex items-center gap-2 rounded-xl border border-border bg-muted/30 px-3 py-1.5 text-xs">
            <span className="text-muted-foreground">کد رهگیری مرسوله:</span>
            <span className="font-mono font-bold text-foreground" dir="ltr">
              {trackingCode}
            </span>
            <button
              type="button"
              onClick={handleCopyTrackingCode}
              className="text-muted-foreground hover:text-primary transition-colors p-1"
              title="کپی کد رهگیری"
            >
              {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
            </button>
          </div>
        )}
      </div>

      {/* 4-Step Stepper */}
      <div className="relative pt-2">
        <div className="grid grid-cols-4 gap-2">
          {SHIPMENT_STATUS_STEPS.map((step, idx) => {
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
                  {Icon && <Icon className="h-4 w-4" />}
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
                    {SHIPMENT_STATUS_LABELS[step]}
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
          {SHIPMENT_STATUS_DESCRIPTIONS[currentStatus]}
        </div>
      </div>

      {/* Detailed event log if provided */}
      {events && events.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-border/40">
          <span className="text-xs font-bold text-foreground block">سوابق رویدادهای پستی:</span>
          <div className="space-y-2 max-h-36 overflow-y-auto">
            {events.map((ev, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between text-xs rounded-lg border border-border/40 bg-background/50 p-2"
              >
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">
                    {SHIPMENT_STATUS_LABELS[ev.status]}
                  </Badge>
                  <span>{ev.description || ev.location}</span>
                </div>
                <span className="text-[11px] text-muted-foreground font-mono" dir="ltr">
                  {ev.timestamp}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
