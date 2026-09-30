/**
 * RMA & Return Request Domain Types and Validation (Sprint 3)
 */

export type ReturnReason =
  | "DEFECTIVE"
  | "WRONG_ITEM"
  | "NOT_AS_DESCRIBED"
  | "CHANGED_MIND"
  | "OTHER"
  | "defective"
  | "wrong_item"
  | "not_as_described"
  | "changed_mind"
  | "customer_remorse"
  | "damaged_in_shipping"
  | "other";

export type ReturnStatus =
  | "REQUESTED"
  | "UNDER_REVIEW"
  | "APPROVED"
  | "REJECTED"
  | "REFUNDED"
  | "requested"
  | "under_review"
  | "approved"
  | "rejected"
  | "received"
  | "inspected"
  | "refunded"
  | "replaced"
  | "closed";

export const RETURN_REASONS: readonly ReturnReason[] = [
  "DEFECTIVE",
  "WRONG_ITEM",
  "NOT_AS_DESCRIBED",
  "CHANGED_MIND",
  "OTHER",
  "defective",
  "wrong_item",
  "not_as_described",
  "changed_mind",
  "customer_remorse",
  "damaged_in_shipping",
  "other",
] as const;

export const RETURN_STATUSES: readonly ReturnStatus[] = [
  "REQUESTED",
  "UNDER_REVIEW",
  "APPROVED",
  "REJECTED",
  "REFUNDED",
  "requested",
  "under_review",
  "approved",
  "rejected",
  "received",
  "inspected",
  "refunded",
  "replaced",
  "closed",
] as const;

export const RETURN_REASON_LABELS: Record<string, string> = {
  DEFECTIVE: "معیوب / خرابی فیزیکی",
  defective: "معیوب / خرابی فیزیکی",
  WRONG_ITEM: "ارسال کالای مغایر",
  wrong_item: "ارسال کالای مغایر",
  NOT_AS_DESCRIBED: "عدم تطابق با مشخصات سایت",
  not_as_described: "عدم تطابق با مشخصات سایت",
  CHANGED_MIND: "انصراف از خرید در مهلت قانونی (۷ روز)",
  changed_mind: "انصراف از خرید در مهلت قانونی (۷ روز)",
  OTHER: "سایر دلایل",
  other: "سایر دلایل",
  customer_remorse: "انصراف مشتری",
  damaged_in_shipping: "آسیب‌دیدگی در حمل و نقل",
};

export const RETURN_STATUS_LABELS: Record<string, string> = {
  REQUESTED: "ثبت‌شده / در انتظار بررسی",
  requested: "ثبت‌شده / در انتظار بررسی",
  UNDER_REVIEW: "در حال بررسی کارشناسی",
  under_review: "در حال بررسی کارشناسی",
  APPROVED: "تایید شده",
  approved: "تایید شده",
  REJECTED: "رد شده",
  rejected: "رد شده",
  REFUNDED: "مبلغ استرداد شد",
  refunded: "مبلغ استرداد شد",
  received: "دریافت‌شده در انبار",
  inspected: "کارشناسی و بازرسی‌شده",
  replaced: "تعویض و جایگزین‌شده",
  closed: "بسته‌شده",
};

export interface ReturnEligibilityResult {
  isEligible: boolean;
  daysRemaining: number;
  error: string | null;
}

export interface ReturnRequestItem {
  itemId: string;
  quantity: number;
  reason: ReturnReason;
  description: string;
  proofImageUrl?: string | null;
}

export interface ReturnRequestPayload {
  orderId: string;
  items: ReturnRequestItem[];
}

export interface ReturnValidationResult {
  isValid: boolean;
  errors: Record<string, string>;
}

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

/**
 * Evaluates whether an order is eligible for RMA return.
 * Criteria: order status must be 'delivered', and delivery date must be within 7 days.
 */
export function checkReturnEligibility(
  orderStatus: string,
  deliveredAt: string | Date | null | undefined,
  now: Date = new Date()
): ReturnEligibilityResult {
  const normStatus = (orderStatus || "").toLowerCase();
  if (normStatus !== "delivered") {
    return {
      isEligible: false,
      daysRemaining: 0,
      error: "فقط سفارش‌های تحویل‌شده امکان ثبت درخواست بازگشت دارند.",
    };
  }

  if (!deliveredAt) {
    return {
      isEligible: false,
      daysRemaining: 0,
      error: "تاریخ تحویل سفارش مشخص نیست.",
    };
  }

  const deliveryDate = new Date(deliveredAt);
  if (isNaN(deliveryDate.getTime())) {
    return {
      isEligible: false,
      daysRemaining: 0,
      error: "تاریخ تحویل نامعتبر است.",
    };
  }

  const elapsedMs = now.getTime() - deliveryDate.getTime();
  if (elapsedMs < 0) {
    // Delivery date is in the future
    return {
      isEligible: true,
      daysRemaining: 7,
      error: null,
    };
  }

  if (elapsedMs > SEVEN_DAYS_MS) {
    return {
      isEligible: false,
      daysRemaining: 0,
      error: "مهلت قانونی ۷ روزه بازگشت کالا برای این سفارش به پایان رسیده است.",
    };
  }

  const remainingMs = SEVEN_DAYS_MS - elapsedMs;
  const daysRemaining = Math.max(1, Math.ceil(remainingMs / (24 * 60 * 60 * 1000)));

  return {
    isEligible: true,
    daysRemaining,
    error: null,
  };
}

/**
 * Validates RMA return request payload before submitting to backend.
 */
export function validateReturnRequest(
  payload: ReturnRequestPayload
): ReturnValidationResult {
  const errors: Record<string, string> = {};

  if (!payload.orderId || !payload.orderId.trim()) {
    errors.orderId = "شناسه سفارش الزامی است.";
  }

  if (!payload.items || payload.items.length === 0) {
    errors.items = "حداقل انتخاب یک کالا برای مرجوعی الزامی است.";
    return { isValid: false, errors };
  }

  payload.items.forEach((item, idx) => {
    const prefix = `items.${idx}`;
    if (!item.itemId || !item.itemId.trim()) {
      errors[`${prefix}.itemId`] = "شناسه کالای مرجوعی مشخص نیست.";
    }

    if (!item.quantity || item.quantity <= 0) {
      errors[`${prefix}.quantity`] = "تعداد کالای مرجوعی باید حداقل ۱ باشد.";
    }

    if (!RETURN_REASONS.includes(item.reason)) {
      errors[`${prefix}.reason`] = "دلیل انتخاب‌شده برای بازگشت کالا نامعتبر است.";
    }

    const desc = (item.description || "").trim();
    if (!desc || desc.length < 5) {
      errors[`${prefix}.description`] = "لطفاً توضیحات علت مرجوعی را حداقل در ۵ کاراکتر بنویسید.";
    }
  });

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}
