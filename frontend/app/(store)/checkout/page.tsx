"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  MapPin,
  Truck,
  CreditCard,
  CheckCircle2,
  AlertCircle,
  Plus,
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  ShoppingBag,
  Wallet,
  Clock,
  Loader2,
  Check,
  X,
  FileText,
  Tag,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { requiresPaymentSession, resolvePaymentFlow } from "@/lib/payment-routing";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useCart } from "@/hooks/use-cart";
import { useToast } from "@/components/ui/use-toast";
import { RadioCard } from "@/components/ui/radio-card";
import { Textarea } from "@/components/ui/textarea";
import { useAuthStore } from "@/stores/auth-store";
import type { ApiAddress } from "@/types/user";
import apiClient from "@/lib/api/client";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { triggerCelebrationCannons } from "@/components/ui/confetti";
import { EmptyState, ErrorState, PageLoader } from "@/components/shared/page-state";
import { LuckyWheelModal } from "@/components/gamification/lucky-wheel-modal";
import {
  getAvailableDeliverySlots,
  validatePostalCode,
  formatPostalCode,
  type DeliverySlot,
} from "@/lib/iranian-commerce";

// --- Types ---

interface ShippingOption {
  method_id: string;
  name: string;
  slug: string;
  provider?: string | null;
  estimated_days_min: number;
  estimated_days_max: number;
  price: number; // in Toman
  is_free: boolean;
}

interface PaymentMethod {
  provider: string;
  name: string;
  name_fa: string;
  is_enabled: boolean;
  icon?: string | null;
  description?: string | null;
}

interface InstallmentOptionUI {
  num_installments: number;
  first_installment_rial: number;
  monthly_installment_rial: number;
  remaining_rial: number;
}

interface CreateOrderResponse {
  order_id: string;
  order_number: string;
  status: string;
  subtotal: number;
  shipping_cost: number;
  discount_amount: number;
  tax: number;
  total: number;
  payment_url?: string | null;
  created_at: string;
}

/** Authoritative totals from POST /checkout/quote (amounts in Rials). */
interface ServerQuote {
  subtotal: number;
  shipping_cost: number;
  discount_amount: number;
  tax: number;
  total: number;
  coupon_applied?: string | null;
}

type CheckoutStep = "address" | "shipping" | "payment" | "review" | "confirmation";

const STEPS: { key: CheckoutStep; label: string; icon: typeof MapPin }[] = [
  { key: "address", label: "آدرس تحویل", icon: MapPin },
  { key: "shipping", label: "روش ارسال", icon: Truck },
  { key: "payment", label: "روش پرداخت", icon: CreditCard },
  { key: "review", label: "بازبینی و پرداخت", icon: CheckCircle2 },
];

/** Gateway durations offered for installment checkout. Mirrors the backend
 *  capability report (mock provider); a real credit-contract gateway replaces
 *  this list, and providers whose public API cannot sell installments never
 *  appear here. */
const INSTALLMENT_MONTHS: number[] = [2, 4, 6, 12];

/**
 * Integer-Rial installment breakdown using the server's exact rule: the
 * prepayment is 10% rounded DOWN, the remainder is split evenly, and the
 * LAST installment carries the division remainder — so
 * ``first + (n-1) * monthly`` reconstructs the total exactly.
 */
function installmentBreakdown(totalRial: number, months: number): {
  firstRial: number;
  monthlyRial: number;
} {
  if (totalRial <= 0 || months < 2) return { firstRial: 0, monthlyRial: 0 };
  const firstRial = Math.max(1, Math.floor((totalRial * 10) / 100));
  const remaining = totalRial - firstRial;
  const monthlyRial = Math.floor(remaining / (months - 1));
  return { firstRial, monthlyRial };
}

const IRAN_PROVINCES = [
  "تهران",
  "خراسان رضوی",
  "اصفهان",
  "فارس",
  "خوزستان",
  "آذربایجان شرقی",
  "مازندران",
  "گیلان",
  "البرز",
  "قم",
  "کرمان",
  "یزد",
  "آذربایجان غربی",
  "قزوین",
  "زنجان",
  "گلستان",
  "همدان",
  "کرمانشاه",
  "لرستان",
  "بوشهر",
  "هرمزگان",
  "مرکزی",
  "اردبیل",
  "کردستان",
  "سمنان",
  "سیستان و بلوچستان",
  "ایلام",
  "کهگیلویه و بویراحمد",
  "خراسان جنوبی",
  "خراسان شمالی",
  "چهارمحال و بختیاری",
];

export default function CheckoutPage() {
  const router = useRouter();
  const {
    items,
    cartId,
    totalItems,
    subtotal,
    couponCode,
    couponDiscount,
    clearCart,
    applyCoupon,
    removeCoupon,
    fetchCart,
    isLoading: cartIsLoading,
  } = useCart();

  const { isAuthenticated, user, isLoading: authLoading } = useAuthStore();

  // Navigation & Step State
  const { toast } = useToast();
  const [currentStep, setCurrentStep] = useState<CheckoutStep>("address");

  // Step 1: Addresses
  const [addresses, setAddresses] = useState<ApiAddress[]>([]);
  const [selectedAddressId, setSelectedAddressId] = useState<string>("");
  const [loadingAddresses, setLoadingAddresses] = useState(false);
  const [isAddressModalOpen, setIsAddressModalOpen] = useState(false);
  const [savingAddress, setSavingAddress] = useState(false);
  const [addressForm, setAddressForm] = useState({
    title: "منزل",
    province: "تهران",
    city: "تهران",
    district: "",
    postal_code: "",
    full_address: "",
    is_default: false,
  });
  const [addressFormError, setAddressFormError] = useState<string | null>(null);

  // Step 2: Shipping
  const [shippingOptions, setShippingOptions] = useState<ShippingOption[]>([]);
  const [selectedShippingMethodId, setSelectedShippingMethodId] = useState<string>("");
  const [loadingShipping, setLoadingShipping] = useState(false);
  const [shippingError, setShippingError] = useState<string | null>(null);

  // Step 3: Payment
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<string>("zarinpal");
  const [loadingPaymentMethods, setLoadingPaymentMethods] = useState(false);
  const [customerNotes, setCustomerNotes] = useState("");

  // Payments upgrade v1: split tender (wallet + gateway) and installments.
  const [walletBalanceRials, setWalletBalanceRials] = useState<number>(0);
  const [splitEnabled, setSplitEnabled] = useState(false);
  const [installmentOptions, setInstallmentOptions] = useState<InstallmentOptionUI[]>([]);
  const [selectedInstallment, setSelectedInstallment] = useState<string>("");

  // Card-to-card checkout hands off to /checkout/card-transfer, which owns the
  // receipt form and re-fetches the payment server-side; no state is needed
  // here beyond the redirect.

  // Step 4: Review & Idempotency
  const [idempotencyKey, setIdempotencyKey] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const isSubmittingRef = useRef(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  // Server-authoritative quote for the review step (audit R2): fetched when
  // the user advances from payment to review, so the totals the user
  // confirms — and the pay button label — can never be silently stale.
  const [serverQuote, setServerQuote] = useState<ServerQuote | null>(null);
  const [quoteError, setQuoteError] = useState<string | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);

  // Step 5: Confirmed Order Result
  const [completedOrder, setCompletedOrder] = useState<CreateOrderResponse | null>(null);
  const [wheelModalOpen, setWheelModalOpen] = useState(false);

  // Delivery Slots State (Iranian Commerce UX)
  const deliverySlots = useMemo(() => getAvailableDeliverySlots(), []);
  const [selectedSlotId, setSelectedSlotId] = useState<string>("slot-1");
  const selectedSlot = useMemo(
    () => deliverySlots.find((s) => s.id === selectedSlotId) || null,
    [deliverySlots, selectedSlotId]
  );

  // Trigger celebration confetti on order confirmation
  useEffect(() => {
    if (currentStep === "confirmation") {
      triggerCelebrationCannons();
    }
  }, [currentStep]);

  // Coupon inline
  const [inputCoupon, setInputCoupon] = useState("");
  const [couponLoading, setCouponLoading] = useState(false);
  const [couponError, setCouponError] = useState<string | null>(null);

  // Initialize Idempotency Key (Standard UUID for server-side deduplication)
  const refreshIdempotencyKey = useCallback(() => {
    const key =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : "ord-" + Math.random().toString(36).substring(2, 11) + "-" + Date.now().toString(36);
    setIdempotencyKey(key);
  }, []);

  useEffect(() => {
    refreshIdempotencyKey();
  }, [refreshIdempotencyKey]);

  // Auth Guard: redirect if not logged in
  useEffect(() => {
    if (!authLoading && !isAuthenticated) {
      router.replace("/login?redirect=/checkout");
    }
  }, [authLoading, isAuthenticated, router]);

  // Initial cart sync on mount
  useEffect(() => {
    if (isAuthenticated) {
      fetchCart();
    }
  }, [isAuthenticated, fetchCart]);

  // Fetch Addresses on Mount
  const loadAddresses = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      setLoadingAddresses(true);
      const response = await apiClient.get<ApiAddress[]>("/users/me/addresses");
      const list = response.data || [];
      setAddresses(list);

      if (list.length > 0) {
        const defaultAddr = list.find((a) => a.is_default) || list[0];
        if (defaultAddr) {
          setSelectedAddressId(defaultAddr.id);
        }
      }
    } catch (err) {
      if (process.env.NODE_ENV === "development") {
        console.warn("Could not fetch addresses:", err);
      }
    } finally {
      setLoadingAddresses(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadAddresses();
  }, [loadAddresses]);

  // Load Shipping Methods when address or subtotal changes
  const selectedAddress = useMemo(() => {
    return addresses.find((a) => a.id === selectedAddressId) || null;
  }, [addresses, selectedAddressId]);

  const loadShippingQuotes = useCallback(
    async (province: string) => {
      // Never invent rates: a failed or empty quote surfaces an explicit
      // Persian error and blocks progression until the user retries.
      setShippingError(null);
      setShippingOptions([]);
      setSelectedShippingMethodId("");
      try {
        setLoadingShipping(true);
        // The shipping API is Rial-denominated: subtotal is Toman here, so
        // the boundary conversion is ×10 on the way out and ÷10 on display.
        const subtotalRials = subtotal * 10;

        const response = await apiClient.post<{
          methods: Array<{
            method_id: string;
            name: string;
            slug: string;
            provider?: string | null;
            estimated_days_min: number;
            estimated_days_max: number;
            price: number;
            is_free: boolean;
          }>;
        }>("/shipping/quote", {
          province,
          weight: 1.5,
          order_amount: subtotalRials,
        });

        if (response.data && Array.isArray(response.data.methods) && response.data.methods.length > 0) {
          const mapped: ShippingOption[] = response.data.methods.map((m) => ({
            method_id: m.method_id,
            name: m.name,
            slug: m.slug,
            provider: m.provider,
            estimated_days_min: m.estimated_days_min,
            estimated_days_max: m.estimated_days_max,
            price: Math.round(m.price / 10), // Rial → Toman at the display boundary
            is_free: m.is_free,
          }));
          setShippingOptions(mapped);
          if (mapped[0]) {
            setSelectedShippingMethodId(mapped[0].method_id);
          }
        } else {
          setShippingError("برای این مقصد در حال حاضر روش ارسال فعالی ثبت نشده است.");
        }
      } catch (err) {
        if (process.env.NODE_ENV === "development") {
          console.warn("Shipping quote API failed:", err);
        }
        setShippingError("دریافت هزینهٔ ارسال ناموفق بود. لطفاً دوباره تلاش کنید.");
      } finally {
        setLoadingShipping(false);
      }
    },
    [subtotal],
  );

  useEffect(() => {
    if (selectedAddress) {
      loadShippingQuotes(selectedAddress.province);
    }
  }, [selectedAddress, loadShippingQuotes]);

  // Payments upgrade v1: the wallet balance drives the split-tender offer
  // ("pay 120,000 from wallet, the rest by gateway"). Best-effort: a failed
  // read hides the option rather than blocking checkout.
  const loadSplitAndInstallmentData = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const walletRes = await apiClient.get<{ balance: number }>("/wallet");
      setWalletBalanceRials(Math.max(0, walletRes.data?.balance ?? 0));
    } catch {
      setWalletBalanceRials(0);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void loadSplitAndInstallmentData();
  }, [loadSplitAndInstallmentData]);

  // Load Payment Methods on Mount
  const loadPaymentMethods = useCallback(async () => {
    try {
      setLoadingPaymentMethods(true);
      const response = await apiClient.get<{ methods: PaymentMethod[] }>("/payments/methods");
      if (response.data && Array.isArray(response.data.methods)) {
        const active = response.data.methods.filter((m) => m.is_enabled);
        setPaymentMethods(active);
        const firstActive = active[0];
        if (firstActive) {
          setSelectedPaymentMethod(firstActive.provider);
        }
      } else {
        fallbackPaymentMethods();
      }
    } catch (err) {
      if (process.env.NODE_ENV === "development") {
        console.warn("Payment methods API failed, using fallback:", err);
      }
      fallbackPaymentMethods();
    } finally {
      setLoadingPaymentMethods(false);
    }
  }, []);

  const fallbackPaymentMethods = () => {
    const methods: PaymentMethod[] = [
      {
        provider: "zarinpal",
        name: "Zarinpal",
        name_fa: "درگاه پرداخت امن زرین‌پال",
        is_enabled: true,
        icon: "zarinpal",
        description: "پرداخت اینترنتی با کلیه کارت‌های عضو شبکه شتاب",
      },
      {
        provider: "idpay",
        name: "IDPay",
        name_fa: "درگاه پرداخت آی‌دی‌پی",
        is_enabled: true,
        icon: "idpay",
        description: "پرداخت آنلاین و مطمئن از طریق شاپرک",
      },
      {
        provider: "wallet",
        name: "Wallet",
        name_fa: "کیف پول اختصاصی",
        is_enabled: true,
        icon: "wallet",
        description: "پرداخت از موجودی کیف پول حساب کاربری",
      },
      // NOTE: no mock gateway in the fallback list — a simulator must never
      // be selectable on real checkout when the methods API fails.
    ];
    setPaymentMethods(methods);
    setSelectedPaymentMethod("zarinpal");
  };

  useEffect(() => {
    loadPaymentMethods();
  }, [loadPaymentMethods]);

  // Handle Adding New Address
  const handleSaveAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddressFormError(null);

    if (!addressForm.full_address || addressForm.full_address.trim().length < 5) {
      setAddressFormError("آدرس کامل باید حداقل ۵ حرف باشد.");
      return;
    }

    if (!validatePostalCode(addressForm.postal_code.trim())) {
      setAddressFormError("کد پستی معتبر نیست؛ باید ۱۰ رقم عددی و با الگوی رسمی پست ایران باشد.");
      return;
    }

    try {
      setSavingAddress(true);
      const response = await apiClient.post<ApiAddress>("/users/me/addresses", {
        title: addressForm.title.trim() || "منزل",
        province: addressForm.province,
        city: addressForm.city.trim() || addressForm.province,
        district: addressForm.district?.trim() || null,
        postal_code: addressForm.postal_code.trim(),
        full_address: addressForm.full_address.trim(),
        is_default: addressForm.is_default,
      });

      const newAddr = response.data;
      setAddresses((prev) => [newAddr, ...prev]);
      setSelectedAddressId(newAddr.id);
      setIsAddressModalOpen(false);
      setAddressForm({
        title: "منزل",
        province: "تهران",
        city: "تهران",
        district: "",
        postal_code: "",
        full_address: "",
        is_default: false,
      });
    } catch (err: unknown) {
      const msg = (err as { message?: string })?.message || "خطا در ثبت آدرس جدید. لطفاً مجدداً تلاش کنید.";
      setAddressFormError(msg);
    } finally {
      setSavingAddress(false);
    }
  };

  // Selected shipping cost
  const selectedShipping = useMemo(() => {
    return shippingOptions.find((s) => s.method_id === selectedShippingMethodId) || null;
  }, [shippingOptions, selectedShippingMethodId]);

  const shippingCost = selectedShipping ? (selectedShipping.is_free ? 0 : selectedShipping.price) : 0;
  // VAT mirrors the server formula (TaxService: 10% of subtotal − discount,
  // computed in Rials) — QA B25: the gateway used to charge a tax amount the
  // UI never showed.
  const taxAmount = Math.round((Math.max(subtotal - couponDiscount, 0) * 10 * 1000) / 10000 / 10);
  const grandTotal = Math.max(0, subtotal - couponDiscount + shippingCost + taxAmount);

  // Display totals (Toman): the server quote wins once it exists — client
  // estimates are only shown while the quote has not been fetched yet
  // (address/shipping steps).
  const quoteTotalToman = serverQuote ? serverQuote.total / 10 : null;
  const displaySubtotal = serverQuote ? serverQuote.subtotal / 10 : subtotal;
  const displayDiscount = serverQuote ? serverQuote.discount_amount / 10 : couponDiscount;
  const displayShipping = serverQuote ? serverQuote.shipping_cost / 10 : shippingCost;
  const displayTax = serverQuote ? serverQuote.tax / 10 : taxAmount;
  const displayTotal = quoteTotalToman ?? grandTotal;
  // Surface a visible notice when the authoritative total differs from the
  // client estimate (price/coupon/shipping changed mid-checkout).
  const quoteChanged = quoteTotalToman !== null && Math.abs(quoteTotalToman - grandTotal) > 1;

  // Handle Apply Coupon Inline
  const handleInlineCoupon = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputCoupon.trim()) return;
    setCouponLoading(true);
    setCouponError(null);
    const res = await applyCoupon(inputCoupon);
    setCouponLoading(false);
    if (!res.success) {
      setCouponError(res.message);
    } else {
      setInputCoupon("");
    }
  };

  // Handle Step Progression
  const handleNextFromAddress = () => {
    if (!selectedAddressId) {
      toast({
        title: "آدرس تحویل انتخاب نشده است",
        description: "لطفاً یک آدرس انتخاب کنید یا آدرس جدیدی اضافه نمایید.",
        variant: "destructive",
      });
      return;
    }
    setCurrentStep("shipping");
  };

  const handleNextFromShipping = () => {
    if (!selectedShippingMethodId) {
      toast({
        title: "روش ارسال انتخاب نشده است",
        description: "برای ادامه، یکی از روش‌های ارسال را انتخاب کنید.",
        variant: "destructive",
      });
      return;
    }
    setCurrentStep("payment");
  };

  const handleNextFromPayment = async () => {
    if (!selectedPaymentMethod) {
      toast({
        title: "روش پرداخت انتخاب نشده است",
        description: "برای ادامه، یکی از روش‌های پرداخت را انتخاب کنید.",
        variant: "destructive",
      });
      return;
    }

    // Fetch the authoritative server quote before the review step (audit
    // R2). If the quote cannot be obtained, the user stays on the payment
    // step — payment must never be confirmed against unverified totals.
    setQuoteLoading(true);
    setQuoteError(null);
    try {
      let effectiveCartId = cartId;
      if (!effectiveCartId) {
        const cartRes = await apiClient.get<{ id: string }>("/cart");
        effectiveCartId = cartRes.data?.id;
      }
      const res = await apiClient.post<ServerQuote>("/checkout/quote", {
        cart_id: effectiveCartId,
        address_id: selectedAddressId,
        shipping_method_id: selectedShippingMethodId,
        coupon_code: couponCode || null,
      });
      setServerQuote(res.data);
      setCurrentStep("review");
    } catch (err: unknown) {
      setQuoteError(
        (err as { message?: string })?.message ||
          "محاسبه مبلغ نهایی با خطا مواجه شد. لطفاً دوباره تلاش کنید.",
      );
    } finally {
      setQuoteLoading(false);
    }
  };

  // Final Order Submission (POST /checkout/create-order)
  const handleCreateOrderAndPay = async () => {
    if (isSubmitting || isSubmittingRef.current) return;

    if (!selectedAddressId || !selectedShippingMethodId || !selectedPaymentMethod) {
      setSubmitError("اطلاعات سفارش ناقص است. لطفاً مراحل را مجدداً بررسی کنید.");
      return;
    }

    isSubmittingRef.current = true;
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      // Ensure we have a valid cart ID from backend; if not, fetch or fallback
      let effectiveCartId = cartId;
      if (!effectiveCartId) {
        const cartRes = await apiClient.get<{ id: string }>("/cart");
        effectiveCartId = cartRes.data?.id;
      }

      const customerNoteWithSlot = [
        customerNotes.trim() || null,
        selectedSlot
          ? `بازه تحویل: ${selectedSlot.dayName} (${selectedSlot.dateStr}) — ${selectedSlot.timeRange}`
          : null,
      ]
        .filter(Boolean)
        .join(" | ");

      // Sprint 1.7: attach dynamic category-field answers keyed by the
      // backend cart item id; the server re-validates against the
      // category definitions before creating the order.
      const itemFields: Record<string, Record<string, string | number>> = {};
      for (const item of items) {
        if (item.id && item.customFields && Object.keys(item.customFields).length > 0) {
          itemFields[item.id] = item.customFields;
        }
      }

      const payload = {
        cart_id: effectiveCartId,
        address_id: selectedAddressId,
        shipping_method_id: selectedShippingMethodId,
        coupon_code: couponCode || null,
        payment_method: selectedPaymentMethod,
        idempotency_key: idempotencyKey,
        notes: customerNoteWithSlot || null,
        item_fields: Object.keys(itemFields).length > 0 ? itemFields : null,
      };

      const response = await apiClient.post<CreateOrderResponse>(
        "/checkout/create-order",
        payload,
        {
          headers: {
            "Idempotency-Key": idempotencyKey,
          },
        },
      );

      const orderData = response.data;
      setCompletedOrder(orderData);

      // The cart is converted server-side inside create_order (same
      // transaction), so once the order exists the payment MUST be set up
      // before we let the UI claim success — otherwise a payment-create
      // failure leaves the customer on a "سفارش با موفقیت ثبت شد" screen for
      // an order that has no payment row and no way to retry it. Each branch
      // below advances to confirmation only after its payment step succeeds;
      // on failure we stay on the review step, where the error banner and its
      // "تلاش مجدد" button are rendered, and reuse the same order + idempotency
      // key (re-running create-order with a fresh key would hit the already
      // converted cart and fail).

      // Check if redirect payment URL was returned directly
      if (orderData.payment_url) {
        setCurrentStep("confirmation");
        await clearCart();
        window.location.href = orderData.payment_url;
        return;
      }

      // Card-to-card is an offline transfer: no gateway session exists and the
      // order is NOT paid yet. Register the pending payment server-side (which
      // stamps the merchant card details and a `C2C-…` authority onto it) and
      // then show the receipt form. Without this the order looked paid while
      // no payment row existed and the customer had no way to submit a slip.
      const flow = resolvePaymentFlow(selectedPaymentMethod);
      if (flow === "card_transfer") {
        try {
          await apiClient.post("/payments", {
            order_id: orderData.order_id,
            provider: selectedPaymentMethod,
            amount: orderData.total, // Rials — the server revalidates against the order total
            idempotency_key: idempotencyKey,
          });

          // Send the customer to the canonical receipt page. It is the URL the
          // provider advertises as the gateway URL, so the in-checkout and
          // resume journeys stay one screen with one implementation — and the
          // page re-fetches the payment, so nothing is trusted from here.
          setCurrentStep("confirmation");
          await clearCart();
          router.push(`/checkout/card-transfer?order_id=${orderData.order_id}`);
        } catch (payErr) {
          const payMsg = (payErr as { message?: string })?.message;
          setSubmitError(
            payMsg ||
              "ثبت پرداخت کارت به کارت با خطا مواجه شد. سفارش شما ثبت شده است؛ از بخش سفارش‌ها می‌توانید دوباره تلاش کنید."
          );
        }
        return;
      }

      // Installments (payments upgrade v1): the gateway's credit product
      // settles the order; this application records the schedule and moves
      // only the prepayment. The plan is created first so the prepayment
      // payment can reference it (the server derives the amount from the
      // plan, never from the client).
      if (selectedInstallment && !splitEnabled) {
        const months = parseInt(selectedInstallment, 10);
        const breakdown = installmentBreakdown(orderData.total, months);
        try {
          const planRes = await apiClient.post<{ id: string }>("/payments/installments", {
            order_id: orderData.order_id,
            provider: selectedPaymentMethod,
            num_installments: months,
            first_installment_rial: breakdown.firstRial,
          });

          const payRes = await apiClient.post<{ gateway_url?: string | null }>(
            `/payments/installments/${planRes.data.id}/first-payment`,
            null,
            {
              params: { idempotency_key: `${idempotencyKey}-i` },
            },
          );

          if (payRes.data?.gateway_url) {
            setCurrentStep("confirmation");
            await clearCart();
            window.location.href = payRes.data.gateway_url;
            return;
          }
        } catch (payErr) {
          const payMsg = (payErr as { message?: string })?.message;
          setSubmitError(
            payMsg ||
              "ایجاد طرح اقساطی با خطا مواجه شد. سفارش شما ثبت شده است؛ از بخش سفارش‌ها می‌توانید ادامه دهید."
          );
          return;
        }

        setCurrentStep("confirmation");
        await clearCart();
        return;
      }

      // Split tender (payments upgrade v1): the wallet covers what it can and
      // the gateway takes the remainder, as two allocations of one order. The
      // server revalidates the slices against the order total and settles the
      // wallet slice inside the same transaction.
      if (splitEnabled && walletBalanceRials > 0 && orderData.total > 0) {
        const walletPart = Math.min(walletBalanceRials, orderData.total);
        const gatewayPart = orderData.total - walletPart;
        try {
          const slices: Array<{ provider: string; amount_rial: number; idempotency_key?: string }> =
            [{ provider: "wallet", amount_rial: walletPart, idempotency_key: `${idempotencyKey}-w` }];
          if (gatewayPart > 0) {
            slices.push({
              provider: selectedPaymentMethod,
              amount_rial: gatewayPart,
              idempotency_key: `${idempotencyKey}-g`,
            });
          }

          const splitRes = await apiClient.post<{
            redirect_url?: string | null;
          }>("/payments/split", { order_id: orderData.order_id, slices });

          if (splitRes.data?.redirect_url) {
            setCurrentStep("confirmation");
            await clearCart();
            window.location.href = splitRes.data.redirect_url;
            return;
          }
          // Wallet covered the whole order — nothing left to redirect to.
        } catch (payErr) {
          const payMsg = (payErr as { message?: string })?.message;
          setSubmitError(
            payMsg ||
              "پرداخت ترکیبی با خطا مواجه شد. سفارش شما ثبت شده است؛ از بخش سفارش‌ها می‌توانید پرداخت را تکمیل کنید."
          );
          return;
        }

        setCurrentStep("confirmation");
        await clearCart();
        return;
      }

      // Initiate a gateway session for online providers; wallet completes
      // in-page through the server-authoritative verify call (the server
      // debits the wallet and confirms the order in one transaction).
      if (requiresPaymentSession(selectedPaymentMethod)) {
        try {
          const payRes = await apiClient.post<{
            id: string;
            authority?: string | null;
            gateway_url?: string | null;
          }>("/payments", {
            order_id: orderData.order_id,
            provider: selectedPaymentMethod,
            amount: orderData.total, // Rials — the server revalidates against the order total
            idempotency_key: idempotencyKey,
          });

          if (selectedPaymentMethod === "wallet") {
            await apiClient.post(`/payments/${payRes.data?.id}/verify`, {
              authority: payRes.data?.authority ?? "",
              status: "OK",
            });
          } else if (payRes.data?.gateway_url) {
            setCurrentStep("confirmation");
            await clearCart();
            window.location.href = payRes.data.gateway_url;
            return;
          }
        } catch (payErr) {
          const payMsg = (payErr as { message?: string })?.message;
          setSubmitError(
            payMsg ||
              "پرداخت با خطا مواجه شد. سفارش شما ثبت شده است؛ از بخش سفارش‌ها می‌توانید پرداخت را تکمیل کنید."
          );
          return;
        }
      }

      // Wallet confirmed in-page / COD / confirmed without gateway
      setCurrentStep("confirmation");
      await clearCart();
    } catch (err: unknown) {
      console.error("Order creation failed:", err);
      const apiMsg =
        (err as { message?: string })?.message ||
        "ثبت سفارش با خطا مواجه شد. لطفاً دوباره تلاش کنید.";
      setSubmitError(apiMsg);
      // Generate a fresh idempotency key in case of recoverable conflict
      refreshIdempotencyKey();
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  // Empty Cart State — also waits for the cart to hydrate and stays hidden
  // once an order exists (post-payment confirmation must never be replaced
  // by the empty-cart screen).
  if (
    !authLoading &&
    !cartIsLoading &&
    !completedOrder &&
    items.length === 0 &&
    currentStep !== "confirmation"
  ) {
    return (
      <div className="container-page py-16">
        <Card className="mx-auto max-w-lg p-8 text-center border-border shadow-sm">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-primary/10 text-primary">
            <ShoppingBag className="h-10 w-10" />
          </div>
          <h1 className="mb-2 text-xl font-bold text-foreground">
            سبد خرید شما برای تسویه حساب خالی است
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            ابتدا محصولات مورد نظر خود را به سبد خرید اضافه کنید و سپس به این صفحه بازگردید.
          </p>
          <Link href="/products">
            <Button size="lg">مشاهده و انتخاب محصولات</Button>
          </Link>
        </Card>
      </div>
    );
  }

  // Loading Auth State
  if (authLoading) {
    return (
      <div className="container-page py-24 text-center">
        <PageLoader message="در حال بارگذاری اطلاعات حساب کاربری..." />
      </div>
    );
  }

  // Confirmation Success View
  if (currentStep === "confirmation" && completedOrder) {
    return (
      <div className="container-page py-12">
        <Card className="mx-auto max-w-2xl overflow-hidden border-emerald-500/30 p-8 text-center shadow-lg">
          <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
            <Check className="h-10 w-10 stroke-[3]" />
          </div>

          <h1 className="mb-2 text-2xl font-extrabold text-foreground">
            سفارش شما با موفقیت ثبت شد!
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            از خرید شما سپاسگزاریم. سفارش شما در صف بررسی و آماده‌سازی قرار گرفت.
          </p>

          <div className="mb-8 rounded-xl border border-border bg-muted/30 p-5 text-right space-y-3">
            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <span className="text-sm text-muted-foreground">شماره سفارش:</span>
              <span className="font-mono text-base font-bold text-primary" dir="ltr">
                {completedOrder.order_number}
              </span>
            </div>

            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <span className="text-sm text-muted-foreground">مبلغ کل پرداخت شده:</span>
              <span className="font-bold text-foreground">
                {formatPrice(Math.round(completedOrder.total / 10))}
              </span>
            </div>

            <div className="flex items-center justify-between border-b border-border/60 pb-3">
              <span className="text-sm text-muted-foreground">وضعیت سفارش:</span>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-600 border-emerald-500/20">
                در حال پردازش
              </Badge>
            </div>

            {selectedAddress && (
              <div className="pt-1 text-xs text-muted-foreground leading-relaxed">
                <span className="font-medium text-foreground">آدرس تحویل: </span>
                {selectedAddress.province}، {selectedAddress.city}، {selectedAddress.full_address}
              </div>
            )}
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
            <Button
              size="lg"
              className="w-full sm:w-auto bg-gradient-to-r from-amber-500 to-yellow-400 text-neutral-950 hover:brightness-110"
              onClick={() => setWheelModalOpen(true)}
            >
              🎁 گردونه شانس — جایزه‌ی این خرید
            </Button>
            <Link href="/account/orders">
              <Button size="lg" className="w-full sm:w-auto">
                پیگیری و مشاهده سفارش‌ها
              </Button>
            </Link>
            <Link href="/products">
              <Button variant="outline" size="lg" className="w-full sm:w-auto">
                ادامه خرید از فروشگاه
              </Button>
            </Link>
          </div>
        </Card>

        {/* Server-authoritative post-order lucky wheel (Karta try_gifts) */}
        <LuckyWheelModal
          orderId={completedOrder.order_id}
          isOpen={wheelModalOpen}
          onClose={() => setWheelModalOpen(false)}
        />
      </div>
    );
  }

  return (
    <div className="container-page py-8">
      {/* Header & Steps Breadcrumb */}
      <div className="mb-8">
        <h1 className="mb-6 text-2xl font-extrabold text-foreground">تکمیل و پرداخت سفارش</h1>

        {/* Multi-Step Indicator */}
        <div className="relative mx-auto max-w-3xl">
          <div className="flex items-center justify-between">
            {STEPS.map((step, idx) => {
              const Icon = step.icon;
              const stepIndex = STEPS.findIndex((s) => s.key === currentStep);
              const isPassed = stepIndex > idx;
              const isCurrent = step.key === currentStep;

              return (
                <div key={step.key} className="flex flex-1 items-center">
                  <div className="flex flex-col items-center gap-1.5 flex-1 text-center">
                    <button
                      type="button"
                      onClick={() => {
                        // Allow navigating to earlier completed steps
                        if (isPassed) setCurrentStep(step.key);
                      }}
                      disabled={!isPassed}
                      className={`flex h-11 w-11 items-center justify-center rounded-full transition-all duration-200 ${
                        isCurrent
                          ? "bg-primary text-primary-foreground ring-4 ring-primary/20 shadow-md scale-105"
                          : isPassed
                          ? "bg-primary/20 text-primary hover:bg-primary/30 cursor-pointer"
                          : "bg-muted text-muted-foreground cursor-not-allowed"
                      }`}
                    >
                      {isPassed ? (
                        <Check className="h-5 w-5 stroke-[2.5]" />
                      ) : (
                        <Icon className="h-5 w-5" />
                      )}
                    </button>
                    <span
                      className={`text-xs ${
                        isCurrent
                          ? "font-bold text-foreground"
                          : isPassed
                          ? "font-medium text-primary"
                          : "text-muted-foreground"
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>

                  {idx < STEPS.length - 1 && (
                    <div
                      className={`h-0.5 flex-1 transition-colors ${
                        stepIndex > idx ? "bg-primary" : "bg-border"
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Main Checkout Layout */}
      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Active Step Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* ══════════════════════════════════════════════════════════════ */}
          {/* STEP 1: SHIPPING ADDRESS                                      */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {currentStep === "address" && (
            <Card className="p-6 shadow-sm border-border">
              <div className="mb-6 flex flex-col justify-between gap-2 sm:flex-row sm:items-center border-b border-border pb-4">
                <div>
                  <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                    <MapPin className="h-5 w-5 text-primary" />
                    <span>انتخاب آدرس تحویل سفارش</span>
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    سفارش شما به آدرس انتخابی زیر ارسال خواهد شد.
                  </p>
                </div>

                <Button
                  size="sm"
                  onClick={() => {
                    setAddressFormError(null);
                    setIsAddressModalOpen(true);
                  }}
                  className="gap-1 text-xs self-start sm:self-auto"
                >
                  <Plus className="h-4 w-4" />
                  <span>افزودن آدرس جدید</span>
                </Button>
              </div>

              {loadingAddresses ? (
                <PageLoader message="در حال دریافت لیست آدرس‌ها..." className="min-h-0 py-12" />
              ) : addresses.length === 0 ? (
                <div className="rounded-xl border border-dashed border-border p-8 text-center">
                  <MapPin className="mx-auto mb-3 h-10 w-10 text-muted-foreground/60" />
                  <p className="mb-4 text-sm font-medium text-foreground">
                    هیچ آدرسی در حساب کاربری شما ثبت نشده است.
                  </p>
                  <Button
                    onClick={() => {
                      setAddressFormError(null);
                      setIsAddressModalOpen(true);
                    }}
                    className="gap-1.5"
                  >
                    <Plus className="h-4 w-4" />
                    <span>افزودن اولین آدرس</span>
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  {addresses.map((addr) => {
                    const isSelected = addr.id === selectedAddressId;
                    return (
                      <RadioCard
                        key={addr.id}
                        name="address"
                        value={addr.id}
                        checked={isSelected}
                        onChange={() => setSelectedAddressId(addr.id)}
                      >

                        <div className="flex-1 space-y-1 text-sm">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-foreground">
                              {addr.title || "آدرس تحویل"}
                            </span>
                            {addr.is_default && (
                              <Badge variant="outline" className="text-[10px] bg-primary/10 text-primary border-primary/20">
                                پیش‌فرض
                              </Badge>
                            )}
                          </div>

                          <p className="text-foreground leading-relaxed">
                            {addr.province}، {addr.city}
                            {addr.district ? `، منطقه ${addr.district}` : ""}، {addr.full_address}
                          </p>

                          <div className="flex items-center gap-4 text-xs text-muted-foreground pt-1">
                            <span>
                              کد پستی:{" "}
                              <span className="font-mono text-foreground" dir="ltr">
                                {toPersianDigits(addr.postal_code)}
                              </span>
                            </span>
                            {user?.phone && (
                              <span>
                                گیرنده: {user.fullName || user.firstName || "کاربر"} ({toPersianDigits(user.phone)})
                              </span>
                            )}
                          </div>
                        </div>
                      </RadioCard>
                    );
                  })}
                </div>
              )}

              <div className="mt-8 flex justify-end border-t border-border pt-4">
                <Button
                  onClick={handleNextFromAddress}
                  disabled={!selectedAddressId}
                  size="lg"
                  className="gap-2 px-6"
                >
                  <span>ادامه و انتخاب روش ارسال</span>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          )}

          {/* ══════════════════════════════════════════════════════════════ */}
          {/* STEP 2: SHIPPING METHOD                                       */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {currentStep === "shipping" && (
            <Card className="p-6 shadow-sm border-border">
              <div className="mb-6 border-b border-border pb-4">
                <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                  <Truck className="h-5 w-5 text-primary" />
                  <span>انتخاب شیوه ارسال کالا</span>
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  ارسال به مقصد:{" "}
                  <strong className="text-foreground">
                    {selectedAddress ? `${selectedAddress.province}، ${selectedAddress.city}` : "مقصد انتخابی"}
                  </strong>
                </p>
              </div>

              {loadingShipping ? (
                <PageLoader message="در حال استعلام هزینه‌ها و روش‌های ارسال..." className="min-h-0 py-12" />
              ) : shippingError ? (
                <ErrorState
                  title="استعلام هزینهٔ ارسال"
                  description={shippingError}
                  onRetry={() => {
                    if (selectedAddress) {
                      loadShippingQuotes(selectedAddress.province);
                    }
                  }}
                />
              ) : shippingOptions.length === 0 ? (
                <EmptyState
                  title="روش ارسالی یافت نشد"
                  description="برای این مقصد در حال حاضر روش ارسال فعالی ثبت نشده است."
                />
              ) : (
                <div className="space-y-3">
                  {shippingOptions.map((opt) => {
                    const isSelected = opt.method_id === selectedShippingMethodId;
                    return (
                      <RadioCard
                        key={opt.method_id}
                        name="shippingMethod"
                        value={opt.method_id}
                        checked={isSelected}
                        onChange={() => setSelectedShippingMethodId(opt.method_id)}
                        className="items-center justify-between"
                      >
                        <div className="flex items-center gap-3">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-foreground">{opt.name}</span>
                              {opt.is_free && (
                                <Badge className="bg-emerald-500 text-white text-[10px]">
                                  رایگان
                                </Badge>
                              )}
                            </div>

                            <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                              <Clock className="h-3 w-3" />
                              <span>
                                زمان تقریبی تحویل: {toPersianDigits(opt.estimated_days_min)} الی{" "}
                                {toPersianDigits(opt.estimated_days_max)} روز کاری
                              </span>
                            </p>
                          </div>
                        </div>

                        <div className="text-left font-bold text-sm">
                          {opt.is_free || opt.price === 0 ? (
                            <span className="text-emerald-600 dark:text-emerald-400">رایگان</span>
                          ) : (
                            <span className="text-foreground">{formatPrice(opt.price)}</span>
                          )}
                        </div>
                      </RadioCard>
                    );
                  })}
                </div>
              )}

              {/* Delivery Time Slot Picker (Iranian Commerce UX) */}
              <div className="mt-6 border-t border-border pt-4">
                <label className="mb-2.5 block text-xs font-bold text-foreground flex items-center gap-1.5">
                  <Clock className="h-4 w-4 text-primary" />
                  <span>انتخاب بازه زمانی تحویل سفارش:</span>
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                  {deliverySlots.map((slot) => {
                    const isSlotSelected = selectedSlotId === slot.id;
                    return (
                      <RadioCard
                        key={slot.id}
                        name="deliverySlot"
                        value={slot.id}
                        checked={isSlotSelected}
                        onChange={() => setSelectedSlotId(slot.id)}
                        className="items-center justify-between p-3 text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <div>
                            <span className="text-foreground">{slot.dayName} ({slot.dateStr})</span>
                            <span className="block text-muted-foreground font-normal mt-0.5">{slot.timeRange}</span>
                          </div>
                        </div>
                        {slot.isExpress && (
                          <Badge variant="outline" className="text-[10px] text-amber-600 border-amber-300">
                            تحویل اکسپرس
                          </Badge>
                        )}
                      </RadioCard>
                    );
                  })}
                </div>
              </div>

              <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
                <Button
                  variant="outline"
                  onClick={() => setCurrentStep("address")}
                  className="gap-1.5"
                >
                  <ArrowRight className="h-4 w-4" />
                  <span>بازگشت به آدرس</span>
                </Button>

                <Button
                  onClick={handleNextFromShipping}
                  disabled={!selectedShippingMethodId || loadingShipping || !!shippingError}
                  size="lg"
                  className="gap-2 px-6"
                >
                  <span>ادامه و انتخاب روش پرداخت</span>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </div>
            </Card>
          )}

          {/* ══════════════════════════════════════════════════════════════ */}
          {/* STEP 3: PAYMENT METHOD                                        */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {currentStep === "payment" && (
            <Card className="p-6 shadow-sm border-border">
              <div className="mb-6 border-b border-border pb-4">
                <h2 className="text-lg font-bold text-foreground flex items-center gap-2">
                  <CreditCard className="h-5 w-5 text-primary" />
                  <span>انتخاب شیوه پرداخت</span>
                </h2>
                <p className="text-xs text-muted-foreground mt-0.5">
                  پرداخت‌ها از طریق درگاه‌های شاپرکی امن و دارای گواهی SSL انجام می‌شوند.
                </p>
              </div>

              {loadingPaymentMethods ? (
                <PageLoader message="در حال دریافت درگاه‌های پرداخت فعال..." className="min-h-0 py-12" />
              ) : (
                <div className="space-y-3">
                  {paymentMethods.map((pm) => {
                    const isSelected = pm.provider === selectedPaymentMethod;
                    return (
                      <RadioCard
                        key={pm.provider}
                        name="paymentMethod"
                        value={pm.provider}
                        checked={isSelected}
                        onChange={() => setSelectedPaymentMethod(pm.provider)}
                        className="items-center justify-between"
                      >
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted border border-border/80">
                              {pm.provider === "wallet" ? (
                                <Wallet className="h-5 w-5 text-primary" />
                              ) : pm.provider === "mock" ? (
                                <ShieldCheck className="h-5 w-5 text-emerald-600" />
                              ) : (
                                <CreditCard className="h-5 w-5 text-primary" />
                              )}
                            </div>

                            <div>
                              <div className="font-bold text-foreground">{pm.name_fa || pm.name}</div>
                              <p className="text-xs text-muted-foreground mt-0.5">
                                {pm.description || "پرداخت اینترنتی امن شاپرک"}
                              </p>
                            </div>
                          </div>
                        </div>

                        {isSelected && (
                          <Badge variant="outline" className="bg-primary/10 text-primary border-primary/30 text-xs">
                            انتخاب شده
                          </Badge>
                        )}
                      </RadioCard>
                    );
                  })}
                </div>
              )}

              {/* Split tender: wallet + gateway (payments upgrade v1) */}
              {walletBalanceRials > 0 && (
                <div className="mt-5 rounded-2xl border border-border/80 bg-muted/20 p-4">
                  <label className="flex cursor-pointer items-start gap-3">
                    <input
                      type="checkbox"
                      checked={splitEnabled}
                      onChange={(e) => setSplitEnabled(e.target.checked)}
                      className="mt-0.5 h-4 w-4 accent-primary"
                    />
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-foreground flex items-center gap-1.5">
                        <Wallet className="h-4 w-4 text-primary" />
                        پرداخت ترکیبی: کیف پول + درگاه
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">
                        موجودی کیف پول شما: {formatPrice(Math.trunc(walletBalanceRials / 10))}
                      </p>
                      {splitEnabled && (
                        <div className="mt-2 space-y-1 text-xs">
                          <p className="text-muted-foreground">
                            از کیف پول:{" "}
                            <span className="font-bold text-foreground">
                              {formatPrice(
                                Math.trunc(
                                  Math.min(walletBalanceRials, Math.trunc(displayTotal * 10)) / 10,
                                ),
                              )}
                            </span>
                          </p>
                          <p className="text-muted-foreground">
                            مانده قابل پرداخت از درگاه:{" "}
                            <span className="font-bold text-foreground">
                              {formatPrice(
                                Math.trunc(
                                  Math.max(
                                    0,
                                    Math.trunc(displayTotal * 10) - walletBalanceRials,
                                  ) / 10,
                                ),
                              )}
                            </span>
                          </p>
                          <p className="text-[11px] text-muted-foreground/80">
                            مبلغ کیف پول در همان لحظه از موجودی شما کسر می‌شود؛ اگر پرداخت درگاهی
                            ناتمام بماند سفارش ثبت شده و از بخش سفارش‌ها قابل تکمیل است.
                          </p>
                        </div>
                      )}
                    </div>
                  </label>
                </div>
              )}

              {/* Installments (payments upgrade v1). The durations come from
                  the gateway's capability; the breakdown uses the same
                  integer-Rial rule as the server (remainder on the LAST
                  installment) so the preview equals the stored schedule. */}
              {INSTALLMENT_MONTHS.length > 0 && (
                <div className="mt-5 rounded-2xl border border-border/80 bg-muted/20 p-4">
                  <p className="mb-1 text-sm font-semibold text-foreground">پرداخت اقساطی</p>
                  <p className="mb-3 text-[11px] text-muted-foreground">
                    پیش‌پرداخت همین حالا پرداخت می‌شود؛ اقساط باقی‌مانده طبق قرارداد درگاه دریافت
                    می‌شود.
                  </p>
                  <div className="space-y-2">
                    <label
                      className={`flex cursor-pointer items-center gap-2 rounded-lg border p-3 text-xs transition-colors ${
                        selectedInstallment === "" ? "border-primary/50 bg-primary/5" : "border-border"
                      }`}
                    >
                      <input
                        type="radio"
                        name="installment-plan"
                        checked={selectedInstallment === ""}
                        onChange={() => setSelectedInstallment("")}
                        className="h-3.5 w-3.5 accent-primary"
                      />
                      <span className="font-semibold text-foreground">پرداخت یکجا (بدون قسط)</span>
                    </label>
                    {INSTALLMENT_MONTHS.map((months) => {
                      const breakdown = installmentBreakdown(
                        Math.trunc(displayTotal * 10),
                        months,
                      );
                      const key = String(months);
                      const isChosen = selectedInstallment === key;
                      return (
                        <label
                          key={key}
                          className={`flex cursor-pointer items-center justify-between rounded-lg border p-3 text-xs transition-colors ${
                            isChosen ? "border-primary/50 bg-primary/5" : "border-border"
                          }`}
                        >
                          <span className="flex items-center gap-2">
                            <input
                              type="radio"
                              name="installment-plan"
                              checked={isChosen}
                              onChange={() => setSelectedInstallment(key)}
                              className="h-3.5 w-3.5 accent-primary"
                            />
                            <span className="font-semibold text-foreground">
                              {toPersianDigits(months)} قسط
                            </span>
                          </span>
                          <span className="text-muted-foreground">
                            پیش‌پرداخت{" "}
                            <span className="font-bold text-foreground">
                              {formatPrice(Math.trunc(breakdown.firstRial / 10))}
                            </span>
                            {" + "}
                            {toPersianDigits(months - 1)} ×{" "}
                            <span className="font-bold text-foreground">
                              {formatPrice(Math.trunc(breakdown.monthlyRial / 10))}
                            </span>
                          </span>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Supported Shetab Banks Trust Banner */}
              <div className="mt-5 rounded-2xl border border-border/80 bg-muted/20 p-3.5">
                <div className="flex items-center justify-between text-xs text-muted-foreground mb-2">
                  <span className="font-semibold text-foreground flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-emerald-600" />
                    پشتیبانی از تمامی کارت‌های عضو شبکه بانکی شتاب
                  </span>
                  <span className="text-[11px]">رمز پویا (OTP)</span>
                </div>
                <div className="flex flex-wrap items-center gap-2 text-[11px]">
                  {["بانک ملی", "بانک ملت", "بانک سامان", "بانک پاسارگاد", "بانک تجارت", "بانک صادرات", "بانک پارسیان", "اقتصاد نوین"].map((bankName, idx) => (
                    <span
                      key={idx}
                      className="rounded-lg border border-border/60 bg-background/80 px-2 py-1 text-muted-foreground font-medium"
                    >
                      {bankName}
                    </span>
                  ))}
                </div>
              </div>

              {/* Optional Order Notes */}
              <div className="mt-6 border-t border-border pt-4">
                <label className="mb-2 block text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>توضیحات و یادداشت سفارش (اختیاری)</span>
                </label>
                <textarea
                  value={customerNotes}
                  onChange={(e) => setCustomerNotes(e.target.value)}
                  rows={2}
                  maxLength={500}
                  placeholder="نکاتی درباره تحویل، ساعات حضور یا راهنمای نشانی..."
                  className="w-full rounded-lg border border-input bg-background p-3 text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="mt-8 flex items-center justify-between border-t border-border pt-4">
                <Button
                  variant="outline"
                  onClick={() => setCurrentStep("shipping")}
                  className="gap-1.5"
                >
                  <ArrowRight className="h-4 w-4" />
                  <span>بازگشت به روش ارسال</span>
                </Button>

                <Button
                  onClick={handleNextFromPayment}
                  disabled={!selectedPaymentMethod || quoteLoading}
                  size="lg"
                  className="gap-2 px-6"
                >
                  {quoteLoading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>در حال محاسبه مبلغ نهایی...</span>
                    </>
                  ) : (
                    <>
                      <span>بازبینی نهایی و تأیید</span>
                      <ArrowLeft className="h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
              {quoteError && (
                <p className="mt-3 text-sm text-destructive">{quoteError}</p>
              )}
            </Card>
          )}

          {/* ══════════════════════════════════════════════════════════════ */}
          {/* STEP 4: REVIEW & PAY                                          */}
          {/* ══════════════════════════════════════════════════════════════ */}
          {currentStep === "review" && (
            <div className="space-y-6">
              <Card className="p-6 shadow-sm border-border">
                <h2 className="mb-4 text-lg font-bold text-foreground border-b border-border pb-3 flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-primary" />
                  <span>بازبینی نهایی مشخصات سفارش</span>
                </h2>

                <div className="space-y-4 text-sm">
                  {/* Selected Address Summary */}
                  <div className="flex items-start justify-between rounded-xl border border-border/80 bg-muted/20 p-4">
                    <div className="space-y-1">
                      <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5 text-primary" />
                        آدرس تحویل:
                      </span>
                      <p className="font-medium text-foreground">
                        {selectedAddress?.province}، {selectedAddress?.city}، {selectedAddress?.full_address}
                      </p>
                      <span className="text-xs text-muted-foreground">
                        کد پستی: {selectedAddress?.postal_code ? toPersianDigits(selectedAddress.postal_code) : "-"}
                      </span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentStep("address")}
                      className="text-xs text-primary"
                    >
                      تغییر
                    </Button>
                  </div>

                  {/* Selected Shipping Method Summary */}
                  <div className="flex items-start justify-between rounded-xl border border-border/80 bg-muted/20 p-4">
                    <div className="space-y-1">
                      <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                        <Truck className="h-3.5 w-3.5 text-primary" />
                        روش ارسال:
                      </span>
                      <p className="font-medium text-foreground">
                        {selectedShipping?.name} (
                        {selectedShipping?.is_free
                          ? "رایگان"
                          : formatPrice(selectedShipping?.price || 0)}
                        )
                      </p>
                      <span className="text-xs text-muted-foreground">
                        تحویل بین {toPersianDigits(selectedShipping?.estimated_days_min || 1)} الی{" "}
                        {toPersianDigits(selectedShipping?.estimated_days_max || 3)} روز کاری
                      </span>
                      {selectedSlot && (
                        <span className="mt-1 flex items-center gap-1 text-xs font-medium text-primary">
                          <Clock className="h-3.5 w-3.5" />
                          بازه انتخابی: {selectedSlot.dayName} ({selectedSlot.dateStr}) —{" "}
                          {selectedSlot.timeRange}
                        </span>
                      )}
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentStep("shipping")}
                      className="text-xs text-primary"
                    >
                      تغییر
                    </Button>
                  </div>

                  {/* Selected Payment Method Summary */}
                  <div className="flex items-start justify-between rounded-xl border border-border/80 bg-muted/20 p-4">
                    <div className="space-y-1">
                      <span className="text-xs font-semibold text-muted-foreground flex items-center gap-1.5">
                        <CreditCard className="h-3.5 w-3.5 text-primary" />
                        درگاه پرداخت:
                      </span>
                      <p className="font-medium text-foreground">
                        {paymentMethods.find((p) => p.provider === selectedPaymentMethod)?.name_fa ||
                          selectedPaymentMethod}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setCurrentStep("payment")}
                      className="text-xs text-primary"
                    >
                      تغییر
                    </Button>
                  </div>

                  {customerNotes && (
                    <div className="rounded-xl border border-border/80 bg-muted/20 p-4 text-xs">
                      <span className="font-semibold text-muted-foreground block mb-1">یادداشت سفارش:</span>
                      <p className="text-foreground">{customerNotes}</p>
                    </div>
                  )}
                </div>

                {/* Items preview */}
                <div className="mt-6 border-t border-border pt-4">
                  <h3 className="mb-3 text-sm font-bold text-foreground">
                    اقلام سفارش ({toPersianDigits(totalItems)} قلم کالا)
                  </h3>
                  <div className="space-y-2 max-h-56 overflow-y-auto ps-1">
                    {items.map((it) => (
                      <div
                        key={it.id || it.variantId || it.productId}
                        className="flex items-center justify-between text-xs py-1.5 border-b border-border/40 last:border-0"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-foreground line-clamp-1">{it.title}</span>
                          {it.variant && (
                            <span className="text-muted-foreground">({it.variant})</span>
                          )}
                          <span className="text-muted-foreground">× {toPersianDigits(it.quantity)}</span>
                        </div>
                        <span className="font-semibold text-foreground">
                          {formatPrice(it.price * it.quantity)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Error Banner with Retry */}
                {submitError && (
                  <div className="mt-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-destructive/30 bg-destructive/10 p-3.5 text-xs text-destructive">
                    <div className="flex items-center gap-2">
                      <AlertCircle className="h-4 w-4 flex-shrink-0" />
                      <span>{submitError}</span>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSubmitError(null);
                        handleCreateOrderAndPay();
                      }}
                      className="border-destructive/30 hover:bg-destructive/20 text-destructive gap-1.5 shrink-0 h-8 text-xs"
                    >
                      <RefreshCw className="h-3 w-3" />
                      تلاش مجدد
                    </Button>
                  </div>
                )}

                {/* Idempotency info hint */}
                <div className="mt-4 flex items-center justify-between text-[11px] text-muted-foreground border-t border-border pt-3">
                  <span>شناسه یکتای امنیتی سفارش:</span>
                  <span className="font-mono" dir="ltr">
                    {idempotencyKey.slice(0, 16)}...
                  </span>
                </div>

                {/* Actions */}
                <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
                  <Button
                    variant="outline"
                    onClick={() => setCurrentStep("payment")}
                    disabled={isSubmitting}
                    className="gap-1.5"
                  >
                    <ArrowRight className="h-4 w-4" />
                    <span>بازگشت</span>
                  </Button>

                  <Button
                    onClick={handleCreateOrderAndPay}
                    disabled={isSubmitting}
                    size="lg"
                    className="gap-2 px-8 font-bold shadow-md bg-emerald-600 hover:bg-emerald-700 text-white"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>در حال پردازش و انتقال به درگاه...</span>
                      </>
                    ) : (
                      <>
                        <span>پرداخت نهایی ({formatPrice(displayTotal)})</span>
                        <ArrowLeft className="h-4 w-4" />
                      </>
                    )}
                  </Button>
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* ══════════════════════════════════════════════════════════════ */}
        {/* ORDER SUMMARY SIDEBAR                                         */}
        {/* ══════════════════════════════════════════════════════════════ */}
        <div className="space-y-4">
          <Card className="sticky top-24 p-6 shadow-sm border-border">
            <h2 className="mb-4 text-base font-bold text-foreground flex items-center justify-between">
              <span>خلاصه فاکتور خرید</span>
              <Badge variant="secondary" className="text-xs font-normal">
                {toPersianDigits(totalItems)} کالا
              </Badge>
            </h2>

            {/* Price lines — server-quote authoritative once available */}
            {quoteChanged && (
              <div className="mb-3 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300">
                مبلغ نهایی بر اساس نرخ‌های روز سرور به‌روزرسانی شد. لطفاً پیش از پرداخت مجدداً بررسی کنید.
              </div>
            )}
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between text-muted-foreground">
                <span>قیمت کالاها</span>
                <span className="font-medium text-foreground">{formatPrice(displaySubtotal)}</span>
              </div>

              {displayDiscount > 0 && (
                <div className="flex items-center justify-between text-emerald-600 dark:text-emerald-400">
                  <span>تخفیف کوپن</span>
                  <span className="font-medium">{formatPrice(displayDiscount)} -</span>
                </div>
              )}

              <div className="flex items-center justify-between text-muted-foreground">
                <span>هزینه ارسال</span>
                {displayShipping === 0 ? (
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">رایگان</span>
                ) : (
                  <span className="font-medium text-foreground">{formatPrice(displayShipping)}</span>
                )}
              </div>

              {displayTax > 0 && (
                <div className="flex items-center justify-between text-muted-foreground">
                  <span>مالیات بر ارزش افزوده (۱۰٪)</span>
                  <span className="font-medium text-foreground">{formatPrice(displayTax)}</span>
                </div>
              )}

              <div className="my-3 border-t border-border pt-3">
                <div className="flex items-center justify-between text-base font-extrabold text-foreground">
                  <span>مبلغ کل نهایی</span>
                  <span className="text-primary text-lg">{formatPrice(displayTotal)}</span>
                </div>
              </div>
            </div>

            {/* Coupon Code Inline input */}
            <div className="mt-4 border-t border-border pt-4">
              <label className="mb-2 block text-xs font-semibold text-foreground">
                کد تخفیف
              </label>

              {couponCode ? (
                <div className="flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-2 text-xs text-emerald-700 dark:text-emerald-300">
                  <div className="flex items-center gap-1.5">
                    <Tag className="h-3 w-3" />
                    <span>کد فعال: </span>
                    <strong className="font-mono">{couponCode}</strong>
                  </div>
                  <button
                    type="button"
                    onClick={() => removeCoupon()}
                    className="p-1 hover:bg-emerald-500/20 rounded"
                    title="حذف کد تخفیف"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              ) : (
                <form onSubmit={handleInlineCoupon} className="space-y-1.5">
                  <div className="flex gap-2">
                    <Input
                      type="text"
                      value={inputCoupon}
                      onChange={(e) => setInputCoupon(e.target.value)}
                      placeholder="کد تخفیف"
                      className="text-xs font-mono"
                      dir="ltr"
                    />
                    <Button
                      type="submit"
                      variant="outline"
                      size="sm"
                      disabled={couponLoading || !inputCoupon.trim()}
                      className="px-3 text-xs"
                    >
                      {couponLoading ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        "اعمال"
                      )}
                    </Button>
                  </div>
                  {couponError && (
                    <p className="text-[11px] text-destructive">{couponError}</p>
                  )}
                </form>
              )}
            </div>

            {/* Security Guarantee Card */}
            <div className="mt-6 rounded-xl border border-border/80 bg-muted/40 p-3 text-xs text-muted-foreground flex items-center gap-2.5">
              <ShieldCheck className="h-6 w-6 text-primary flex-shrink-0" />
              <span>پرداخت تضمین شده و امن با پروتکل رمزنگاری SSL شاپرک</span>
            </div>
          </Card>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════ */}
      {/* MODAL: ADD NEW ADDRESS                                        */}
      {/* ══════════════════════════════════════════════════════════════ */}
      <Dialog open={isAddressModalOpen} onOpenChange={setIsAddressModalOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold text-foreground">
              افزودن آدرس جدید
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              اطلاعات نشانی دقیق جهت دریافت مرسوله را وارد فرمایید.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSaveAddress} className="space-y-3.5 pt-2">
            <div>
              <label htmlFor="addr-title" className="mb-1 block text-xs font-medium text-foreground">
                عنوان آدرس (مثال: خانه، شرکت)
              </label>
              <Input
                id="addr-title"
                value={addressForm.title}
                onChange={(e) => setAddressForm({ ...addressForm, title: e.target.value })}
                placeholder="منزل"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="addr-province" className="mb-1 block text-xs font-medium text-foreground">
                  استان
                </label>
                <select
                  id="addr-province"
                  value={addressForm.province}
                  onChange={(e) =>
                    setAddressForm({
                      ...addressForm,
                      province: e.target.value,
                      city: e.target.value, // sensible default
                    })
                  }
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1"
                >
                  {IRAN_PROVINCES.map((prov) => (
                    <option key={prov} value={prov}>
                      {prov}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="addr-city" className="mb-1 block text-xs font-medium text-foreground">
                  شهر
                </label>
                <Input
                  id="addr-city"
                  value={addressForm.city}
                  onChange={(e) => setAddressForm({ ...addressForm, city: e.target.value })}
                  placeholder="تهران"
                  required
                />
              </div>
            </div>

            <div>
              <label htmlFor="addr-postal" className="mb-1 block text-xs font-medium text-foreground">
                کد پستی (۱۰ رقم)
              </label>
              <Input
                id="addr-postal"
                value={addressForm.postal_code}
                onChange={(e) => {
                  const digits = e.target.value.replace(/\D/g, "").slice(0, 10);
                  setAddressForm({ ...addressForm, postal_code: digits });
                }}
                onBlur={() =>
                  setAddressForm((prev) => ({
                    ...prev,
                    postal_code: prev.postal_code.replace(/\D/g, "").slice(0, 10),
                  }))
                }
                placeholder="1234567890"
                dir="ltr"
                inputMode="numeric"
                maxLength={10}
                required
                aria-describedby="postal-format-hint"
              />
              <p id="postal-format-hint" className="mt-1 text-[11px] text-muted-foreground">
                الگوی رسمی پست ایران: ۱۰ رقم عددی (مثال: {formatPostalCode("1234567890")})
              </p>
            </div>

            <div>
              <label htmlFor="addr-full" className="mb-1 block text-xs font-medium text-foreground">
                نشانی دقیق پستی
              </label>
              <Textarea
                id="addr-full"
                value={addressForm.full_address}
                onChange={(e) => setAddressForm({ ...addressForm, full_address: e.target.value })}
                rows={3}
                placeholder="خیابان، کوچه، پلاک، زنگ، واحد..."
                className="text-xs"
                required
              />
            </div>

            <label className="flex cursor-pointer items-center gap-2 pt-1 text-xs">
              <input
                type="checkbox"
                checked={addressForm.is_default}
                onChange={(e) =>
                  setAddressForm({ ...addressForm, is_default: e.target.checked })
                }
                className="rounded border-border text-primary focus:ring-primary"
              />
              <span>ذخیره به عنوان آدرس پیش‌فرض</span>
            </label>

            {addressFormError && (
              <div className="rounded-md border border-destructive/20 bg-destructive/10 p-2 text-xs text-destructive">
                {addressFormError}
              </div>
            )}

            <DialogFooter className="pt-3 gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsAddressModalOpen(false)}
                disabled={savingAddress}
              >
                انصراف
              </Button>
              <Button type="submit" disabled={savingAddress}>
                {savingAddress ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  "ثبت و انتخاب آدرس"
                )}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
