"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import { useAuthStore } from "@/stores/auth-store";
import apiClient from "@/lib/api/client";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { triggerCelebrationCannons } from "@/components/ui/confetti";
import {
  getAvailableDeliverySlots,
  validatePostalCode,
  formatPostalCode,
  type DeliverySlot,
} from "@/lib/iranian-commerce";

// --- Types ---

interface Address {
  id: string;
  title: string;
  province: string;
  city: string;
  district?: string | null;
  postal_code: string;
  full_address: string;
  is_default: boolean;
}

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

type CheckoutStep = "address" | "shipping" | "payment" | "review" | "confirmation";

const STEPS: { key: CheckoutStep; label: string; icon: typeof MapPin }[] = [
  { key: "address", label: "آدرس تحویل", icon: MapPin },
  { key: "shipping", label: "روش ارسال", icon: Truck },
  { key: "payment", label: "روش پرداخت", icon: CreditCard },
  { key: "review", label: "بازبینی و پرداخت", icon: CheckCircle2 },
];

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
  } = useCart();

  const { isAuthenticated, user, isLoading: authLoading } = useAuthStore();

  // Navigation & Step State
  const [currentStep, setCurrentStep] = useState<CheckoutStep>("address");

  // Step 1: Addresses
  const [addresses, setAddresses] = useState<Address[]>([]);
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

  // Step 3: Payment
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState<string>("zarinpal");
  const [loadingPaymentMethods, setLoadingPaymentMethods] = useState(false);
  const [customerNotes, setCustomerNotes] = useState("");

  // Step 4: Review & Idempotency
  const [idempotencyKey, setIdempotencyKey] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Step 5: Confirmed Order Result
  const [completedOrder, setCompletedOrder] = useState<CreateOrderResponse | null>(null);

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

  // Initialize Idempotency Key
  const refreshIdempotencyKey = useCallback(() => {
    const key =
      "ord_" +
      (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : Math.random().toString(36).substring(2, 11) + Date.now().toString(36));
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
      const response = await apiClient.get<Address[]>("/users/me/addresses");
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

  const fallbackShipping = useCallback(
    (province: string) => {
      const isTehran = province === "تهران";
      const isFree = subtotal >= 5000000;
      const defaults: ShippingOption[] = [
        {
          method_id: "00000000-0000-0000-0000-000000000001",
          name: "پست پیشتاز",
          slug: "pishtaz",
          provider: "iran_post",
          estimated_days_min: 2,
          estimated_days_max: 4,
          price: isFree ? 0 : 35000,
          is_free: isFree,
        },
        {
          method_id: "00000000-0000-0000-0000-000000000002",
          name: "تیپاکس (اکسپرس)",
          slug: "tipax",
          provider: "tipax",
          estimated_days_min: 1,
          estimated_days_max: 2,
          price: isFree ? 0 : 55000,
          is_free: isFree,
        },
      ];

      if (isTehran) {
        defaults.unshift({
          method_id: "00000000-0000-0000-0000-000000000003",
          name: "پیک موتوری (تحویل فوری تهران)",
          slug: "express_courier",
          provider: "courier",
          estimated_days_min: 0,
          estimated_days_max: 1,
          price: isFree ? 0 : 65000,
          is_free: isFree,
        });
      }

      setShippingOptions(defaults);
      if (defaults[0]) {
        setSelectedShippingMethodId(defaults[0].method_id);
      }
    },
    [subtotal],
  );

  const loadShippingQuotes = useCallback(
    async (province: string) => {
      try {
        setLoadingShipping(true);
        // Subtotal in Rial for quote calculation (1 Toman = 10 Rials)
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
          province: province || "تهران",
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
            price: Math.round(m.price / 10), // convert Rial to Toman
            is_free: m.is_free,
          }));
          setShippingOptions(mapped);
          if (mapped[0]) {
            setSelectedShippingMethodId(mapped[0].method_id);
          }
        } else {
          // Fallback methods if API returns empty
          fallbackShipping(province);
        }
      } catch (err) {
        if (process.env.NODE_ENV === "development") {
          console.warn("Shipping quote API failed, using fallback:", err);
        }
        fallbackShipping(province);
      } finally {
        setLoadingShipping(false);
      }
    },
    [subtotal, fallbackShipping],
  );

  useEffect(() => {
    if (selectedAddress) {
      loadShippingQuotes(selectedAddress.province);
    }
  }, [selectedAddress, loadShippingQuotes]);

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
      {
        provider: "mock",
        name: "Mock Gateway",
        name_fa: "درگاه آزمایشی (شبیه‌ساز پرداخت)",
        is_enabled: true,
        icon: "mock",
        description: "تست فرایند پرداخت بدون اتصال به حساب بانکی",
      },
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
      const response = await apiClient.post<Address>("/users/me/addresses", {
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
  const grandTotal = Math.max(0, subtotal - couponDiscount + shippingCost);

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
      alert("لطفاً یک آدرس تحویل انتخاب کنید یا آدرس جدید اضافه نمایید.");
      return;
    }
    setCurrentStep("shipping");
  };

  const handleNextFromShipping = () => {
    if (!selectedShippingMethodId) {
      alert("لطفاً یک روش ارسال انتخاب کنید.");
      return;
    }
    setCurrentStep("payment");
  };

  const handleNextFromPayment = () => {
    if (!selectedPaymentMethod) {
      alert("لطفاً یک روش پرداخت انتخاب کنید.");
      return;
    }
    setCurrentStep("review");
  };

  // Final Order Submission (POST /checkout/create-order)
  const handleCreateOrderAndPay = async () => {
    if (isSubmitting) return;

    if (!selectedAddressId || !selectedShippingMethodId || !selectedPaymentMethod) {
      setSubmitError("اطلاعات سفارش ناقص است. لطفاً مراحل را مجدداً بررسی کنید.");
      return;
    }

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

      const payload = {
        cart_id: effectiveCartId,
        address_id: selectedAddressId,
        shipping_method_id: selectedShippingMethodId,
        coupon_code: couponCode || null,
        payment_method: selectedPaymentMethod,
        idempotency_key: idempotencyKey,
        notes: customerNoteWithSlot || null,
      };

      const response = await apiClient.post<CreateOrderResponse>(
        "/checkout/create-order",
        payload,
      );

      const orderData = response.data;
      setCompletedOrder(orderData);

      // Clear the cart on successful checkout
      await clearCart();

      // Check if redirect payment URL was returned directly
      if (orderData.payment_url) {
        window.location.href = orderData.payment_url;
        return;
      }

      // Initiate a gateway session for online providers; wallet completes
      // in-page through the server-authoritative verify call (the server
      // debits the wallet and confirms the order in one transaction).
      const onlineProviders = ["zarinpal", "idpay", "nextpay", "crypto", "mock", "wallet"];
      if (onlineProviders.includes(selectedPaymentMethod)) {
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
            window.location.href = payRes.data.gateway_url;
            return;
          }
        } catch (payErr) {
          const payMsg = (payErr as { message?: string })?.message;
          setSubmitError(
            payMsg ||
              "پرداخت با خطا مواجه شد. سفارش شما ثبت شده است؛ از بخش سفارش‌ها می‌توانید پرداخت را تکمیل کنید."
          );
          refreshIdempotencyKey();
          return;
        }
      }

      // Wallet confirmed in-page / COD / confirmed without gateway
      setCurrentStep("confirmation");
    } catch (err: unknown) {
      console.error("Order creation failed:", err);
      const apiMsg =
        (err as { message?: string })?.message ||
        "ثبت سفارش با خطا مواجه شد. لطفاً دوباره تلاش کنید.";
      setSubmitError(apiMsg);
      // Generate a fresh idempotency key in case of recoverable conflict
      refreshIdempotencyKey();
    } finally {
      setIsSubmitting(false);
    }
  };

  // Empty Cart State
  if (!authLoading && items.length === 0 && currentStep !== "confirmation") {
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
        <div className="flex flex-col items-center justify-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm text-muted-foreground">در حال بارگذاری اطلاعات حساب کاربری...</p>
        </div>
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
                <div className="py-12 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
                  در حال دریافت لیست آدرس‌ها...
                </div>
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
                      <label
                        key={addr.id}
                        className={`flex cursor-pointer items-start gap-3 rounded-xl border p-4 transition-all ${
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
                            : "border-border hover:border-border/80 hover:bg-muted/30"
                        }`}
                      >
                        <input
                          type="radio"
                          name="address"
                          value={addr.id}
                          checked={isSelected}
                          onChange={() => setSelectedAddressId(addr.id)}
                          className="mt-1 h-4 w-4 text-primary focus:ring-primary"
                        />

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
                      </label>
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
                <div className="py-12 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
                  در حال استعلام هزینه‌ها و روش‌های ارسال...
                </div>
              ) : (
                <div className="space-y-3">
                  {shippingOptions.map((opt) => {
                    const isSelected = opt.method_id === selectedShippingMethodId;
                    return (
                      <label
                        key={opt.method_id}
                        className={`flex cursor-pointer items-center justify-between rounded-xl border p-4 transition-all ${
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
                            : "border-border hover:border-border/80 hover:bg-muted/30"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="radio"
                            name="shippingMethod"
                            value={opt.method_id}
                            checked={isSelected}
                            onChange={() => setSelectedShippingMethodId(opt.method_id)}
                            className="h-4 w-4 text-primary focus:ring-primary"
                          />

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
                      </label>
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
                      <label
                        key={slot.id}
                        className={`flex cursor-pointer items-center justify-between rounded-xl border p-3 text-xs transition-all ${
                          isSlotSelected
                            ? "border-primary bg-primary/10 ring-1 ring-primary font-bold shadow-xs"
                            : "border-border hover:bg-muted/40"
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <input
                            type="radio"
                            name="deliverySlot"
                            checked={isSlotSelected}
                            onChange={() => setSelectedSlotId(slot.id)}
                            className="h-3.5 w-3.5 text-primary"
                          />
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
                      </label>
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
                  disabled={!selectedShippingMethodId}
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
                <div className="py-12 text-center text-sm text-muted-foreground">
                  <Loader2 className="mx-auto mb-2 h-6 w-6 animate-spin text-primary" />
                  در حال دریافت درگاه‌های پرداخت فعال...
                </div>
              ) : (
                <div className="space-y-3">
                  {paymentMethods.map((pm) => {
                    const isSelected = pm.provider === selectedPaymentMethod;
                    return (
                      <label
                        key={pm.provider}
                        className={`flex cursor-pointer items-center justify-between rounded-xl border p-4 transition-all ${
                          isSelected
                            ? "border-primary bg-primary/5 ring-1 ring-primary"
                            : "border-border hover:border-border/80 hover:bg-muted/30"
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <input
                            type="radio"
                            name="paymentMethod"
                            value={pm.provider}
                            checked={isSelected}
                            onChange={() => setSelectedPaymentMethod(pm.provider)}
                            className="h-4 w-4 text-primary focus:ring-primary"
                          />

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
                      </label>
                    );
                  })}
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
                  disabled={!selectedPaymentMethod}
                  size="lg"
                  className="gap-2 px-6"
                >
                  <span>بازبینی نهایی و تأیید</span>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
              </div>
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
                  <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
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

                {/* Error Banner */}
                {submitError && (
                  <div className="mt-4 flex items-center gap-2 rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-xs text-destructive">
                    <AlertCircle className="h-4 w-4 flex-shrink-0" />
                    <span>{submitError}</span>
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
                        <span>پرداخت نهایی ({formatPrice(grandTotal)})</span>
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

            {/* Price lines */}
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between text-muted-foreground">
                <span>قیمت کالاها</span>
                <span className="font-medium text-foreground">{formatPrice(subtotal)}</span>
              </div>

              {couponDiscount > 0 && (
                <div className="flex items-center justify-between text-emerald-600 dark:text-emerald-400">
                  <span>تخفیف کوپن</span>
                  <span className="font-medium">{formatPrice(couponDiscount)} -</span>
                </div>
              )}

              <div className="flex items-center justify-between text-muted-foreground">
                <span>هزینه ارسال</span>
                {shippingCost === 0 ? (
                  <span className="font-semibold text-emerald-600 dark:text-emerald-400">رایگان</span>
                ) : (
                  <span className="font-medium text-foreground">{formatPrice(shippingCost)}</span>
                )}
              </div>

              <div className="my-3 border-t border-border pt-3">
                <div className="flex items-center justify-between text-base font-extrabold text-foreground">
                  <span>مبلغ کل نهایی</span>
                  <span className="text-primary text-lg">{formatPrice(grandTotal)}</span>
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
              <label className="mb-1 block text-xs font-medium text-foreground">
                عنوان آدرس (مثال: خانه، شرکت)
              </label>
              <Input
                value={addressForm.title}
                onChange={(e) => setAddressForm({ ...addressForm, title: e.target.value })}
                placeholder="منزل"
                required
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  استان
                </label>
                <select
                  value={addressForm.province}
                  onChange={(e) =>
                    setAddressForm({
                      ...addressForm,
                      province: e.target.value,
                      city: e.target.value, // sensible default
                    })
                  }
                  className="w-full rounded-md border border-input bg-background p-2 text-xs text-foreground focus:border-primary focus:outline-none"
                >
                  {IRAN_PROVINCES.map((prov) => (
                    <option key={prov} value={prov}>
                      {prov}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-foreground">
                  شهر
                </label>
                <Input
                  value={addressForm.city}
                  onChange={(e) => setAddressForm({ ...addressForm, city: e.target.value })}
                  placeholder="تهران"
                  required
                />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                کد پستی (۱۰ رقم)
              </label>
              <Input
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
              <label className="mb-1 block text-xs font-medium text-foreground">
                نشانی دقیق پستی
              </label>
              <textarea
                value={addressForm.full_address}
                onChange={(e) => setAddressForm({ ...addressForm, full_address: e.target.value })}
                rows={3}
                placeholder="خیابان، کوچه، پلاک، زنگ، واحد..."
                className="w-full rounded-md border border-input bg-background p-2 text-xs text-foreground focus:border-primary focus:outline-none"
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
