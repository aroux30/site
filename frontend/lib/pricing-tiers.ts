import type { ApiPriceTier } from "./api/services";

export interface TierPriceCalculation {
  unitPrice: number;
  activeTier: ApiPriceTier | null;
  totalPrice: number;
  savingsAmount: number;
  savingsPercent: number;
}

export interface QuantityValidationResult {
  isValid: boolean;
  error: string | null;
}

/**
 * Finds the unit price for a given quantity across volume discount tiers.
 */
export function calculateTierPrice(
  tiers: ApiPriceTier[],
  quantity: number,
  basePrice: number
): TierPriceCalculation {
  const match = tiers.find(
    (t) => quantity >= t.from_qty && (t.to_qty === null || quantity <= t.to_qty)
  ) ?? null;

  const unitPrice = match ? match.unit_price : basePrice;
  const totalPrice = unitPrice * quantity;
  const baseTotal = basePrice * quantity;
  const savingsAmount = Math.max(0, baseTotal - totalPrice);
  const savingsPercent = basePrice > 0 ? Math.round(((basePrice - unitPrice) / basePrice) * 100) : 0;

  return {
    unitPrice,
    activeTier: match,
    totalPrice,
    savingsAmount,
    savingsPercent,
  };
}

/**
 * Validates order quantity against product-level min and max limits.
 */
export function validateOrderQuantity(
  quantity: number,
  minQty: number = 1,
  maxQty: number = 999
): QuantityValidationResult {
  if (isNaN(quantity) || quantity <= 0) {
    return {
      isValid: false,
      error: "تعداد سفارش باید یک عدد مثبت باشد.",
    };
  }

  if (quantity < minQty) {
    return {
      isValid: false,
      error: `حداقل تعداد مجاز برای سفارش این محصول ${minQty} عدد است.`,
    };
  }

  if (quantity > maxQty) {
    return {
      isValid: false,
      error: `حداکثر تعداد مجاز برای سفارش این محصول ${maxQty} عدد است.`,
    };
  }

  return {
    isValid: true,
    error: null,
  };
}
