"use client";

import React from "react";
import { Card } from "@/components/ui/card";

/**
 * Skeleton Loader for Product Search Results Grid
 */
export function SearchResultsSkeleton({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-6" dir="rtl">
      {Array.from({ length: count }).map((_, idx) => (
        <Card
          key={idx}
          className="flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card p-4 animate-pulse space-y-4"
        >
          <div className="space-y-3">
            {/* Image Placeholder */}
            <div className="w-full h-48 rounded-xl bg-muted/60" />

            {/* Category & Title Placeholders */}
            <div className="space-y-2">
              <div className="h-3 w-1/4 rounded bg-muted/70" />
              <div className="h-4 w-5/6 rounded bg-muted/80" />
              <div className="h-4 w-3/5 rounded bg-muted/60" />
            </div>
          </div>

          {/* Price & Action Button Placeholder */}
          <div className="pt-3 border-t border-border/50 space-y-3">
            <div className="flex items-center justify-between">
              <div className="h-5 w-1/3 rounded bg-muted/80" />
              <div className="h-4 w-12 rounded bg-muted/60" />
            </div>
            <div className="h-9 w-full rounded-xl bg-muted/70" />
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Skeleton Loader for User Order History List
 */
export function OrderHistorySkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-4" dir="rtl">
      {Array.from({ length: count }).map((_, idx) => (
        <Card
          key={idx}
          className="rounded-2xl border border-border bg-card p-5 animate-pulse space-y-4"
        >
          {/* Order Header Placeholder */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-3">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-muted/80" />
              <div className="space-y-1.5">
                <div className="h-4 w-28 rounded bg-muted/80" />
                <div className="h-3 w-36 rounded bg-muted/60" />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <div className="h-8 w-24 rounded-lg bg-muted/70" />
              <div className="h-8 w-24 rounded-lg bg-muted/70" />
            </div>
          </div>

          {/* Items Row Placeholders */}
          <div className="space-y-3 pt-1">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="h-12 w-12 rounded-lg bg-muted/70" />
                <div className="space-y-1">
                  <div className="h-3.5 w-48 rounded bg-muted/80" />
                  <div className="h-3 w-20 rounded bg-muted/60" />
                </div>
              </div>
              <div className="h-4 w-24 rounded bg-muted/80" />
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}

/**
 * Skeleton Loader for Order Tracking & Shipment Stepper Details
 */
export function ShipmentTrackingSkeleton() {
  return (
    <div className="rounded-2xl border border-border bg-card p-5 animate-pulse space-y-6" dir="rtl">
      <div className="flex items-center justify-between border-b border-border/60 pb-3">
        <div className="h-4 w-32 rounded bg-muted/80" />
        <div className="h-6 w-40 rounded-lg bg-muted/70" />
      </div>

      <div className="grid grid-cols-4 gap-3 py-2">
        {Array.from({ length: 4 }).map((_, idx) => (
          <div key={idx} className="flex flex-col items-center space-y-2">
            <div className="h-10 w-10 rounded-2xl bg-muted/70" />
            <div className="h-3 w-16 rounded bg-muted/80" />
          </div>
        ))}
      </div>

      <div className="h-10 w-full rounded-xl bg-muted/50" />
    </div>
  );
}
