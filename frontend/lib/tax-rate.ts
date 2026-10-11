/** The single configured VAT rate, read from the public settings endpoint.
 *
 * Owner decision 2026-10-09: one field, one rate. The admin settings field
 * (store.shipping_tax.tax_rate_percent) is the only authority; the cart,
 * checkout and order paths all derive from it. This module keeps the
 * client-side estimate in step with what the server will charge, so the
 * review step can no longer disagree with the gateway amount.
 */
import { useEffect, useState } from "react";

import apiClient from "@/lib/api/client";

/** Must match the backend fallback (tax_rate_service.DEFAULT_TAX_RATE_PERCENT). */
export const DEFAULT_TAX_RATE_PERCENT = 9;

let cached: number | null = null;
let inflight: Promise<number> | null = null;

export async function fetchTaxRatePercent(): Promise<number> {
  if (cached !== null) return cached;
  if (!inflight) {
    inflight = apiClient
      .get<{ tax_rate_percent: number }>("/settings/public/tax-rate")
      .then((r) => {
        const value = Number(r.data?.tax_rate_percent);
        cached = Number.isFinite(value) && value >= 0 && value <= 100
          ? value
          : DEFAULT_TAX_RATE_PERCENT;
        return cached;
      })
      .catch(() => DEFAULT_TAX_RATE_PERCENT)
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}

/** React hook: the configured rate, starting from the default until loaded. */
export function useTaxRatePercent(): number {
  const [rate, setRate] = useState<number>(cached ?? DEFAULT_TAX_RATE_PERCENT);
  useEffect(() => {
    let alive = true;
    void fetchTaxRatePercent().then((r) => {
      if (alive) setRate(r);
    });
    return () => {
      alive = false;
    };
  }, []);
  return rate;
}
