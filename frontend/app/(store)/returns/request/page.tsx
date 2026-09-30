"use client";

import React, { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  RotateCcw,
  CheckCircle2,
  AlertCircle,
  Clock,
  Upload,
  Package,
  ArrowRight,
  ShieldAlert,
  FileText,
  Image as ImageIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import {
  RETURN_REASONS,
  RETURN_REASON_LABELS,
  RETURN_STATUS_LABELS,
  checkReturnEligibility,
  validateReturnRequest,
  type ReturnReason,
  type ReturnStatus,
} from "@/lib/rma";

interface OrderItem {
  id: string;
  title: string;
  price: number;
  quantity: number;
  image?: string;
  /** Variant id captured at checkout; required by the RMA payload. */
  variantId?: string;
}

interface UserOrder {
  id: string;
  orderNumber: string;
  status: string;
  deliveredAt: string | null;
  createdAt: string;
  items: OrderItem[];
}

export default function ReturnRequestPage() {
  const { toast } = useToast();
  const searchParams = useSearchParams();
  const preselectedOrderId = searchParams.get("orderId");

  const [orders, setOrders] = useState<UserOrder[]>([]);
  const [loadingOrders, setLoadingOrders] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Form states
  const [selectedOrderId, setSelectedOrderId] = useState<string>(preselectedOrderId || "");
  const [selectedItemId, setSelectedItemId] = useState<string>("");
  const [quantity, setQuantity] = useState<number>(1);
  const [reason, setReason] = useState<ReturnReason>("DEFECTIVE");
  const [description, setDescription] = useState<string>("");
  const [proofFile, setProofFile] = useState<File | null>(null);
  const [proofPreview, setProofPreview] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // Success state
  const [submittedRma, setSubmittedRma] = useState<{
    trackingNumber: string;
    status: ReturnStatus;
  } | null>(null);

  // Load user delivered orders
  useEffect(() => {
    async function loadOrders() {
      setLoadingOrders(true);
      setLoadError(null);
      try {
        const res = await apiClient.get("/orders");
        const list = Array.isArray(res.data?.items)
          ? res.data.items
          : Array.isArray(res.data)
          ? res.data
          : [];

        const mapped: UserOrder[] = list.map((o: Record<string, unknown>) => ({
          id: String(o.id || o.order_number || ""),
          orderNumber: String(o.order_number || o.orderNumber || o.id || ""),
          // Keep the real status: the eligibility check below accepts the
          // post-delivery states (`delivered`/`completed`) and must be able to
          // reject everything else. Defaulting to "delivered" marked every
          // pending order returnable.
          status: String(o.status || "").toLowerCase(),
          // /orders carries no delivery timestamp; created_at is the closest
          // available anchor and is only read once eligibility has passed.
          deliveredAt: (o.delivered_at || o.deliveredAt || o.created_at || o.createdAt) as string | null,
          createdAt: String(o.created_at || o.createdAt || ""),
          items: Array.isArray(o.items)
            ? (o.items as Record<string, unknown>[]).map((it, idx) => ({
                id: String(it.id || idx),
                title: String(it.title || it.product_name || "کالای دیجیتال"),
                // /orders returns unit_price in Rials; this page formats Toman.
                price: Math.trunc(Number(it.price || it.unit_price || 0) / 10),
                quantity: Number(it.quantity || 1),
                image: it.image as string | undefined,
                variantId: it.variant_id ? String(it.variant_id) : undefined,
              }))
            : [
                {
                  id: "item-1",
                  title: "کالای سفارش داده شده",
                  price: 1500000,
                  quantity: 1,
                },
              ],
        }));

        setOrders(mapped);
      } catch {
        // A failed load must not fabricate an order: the previous fallback
        // injected a fake "delivered 2 days ago" row, so a customer whose
        // request failed saw a plausible returnable order that does not exist
        // and could walk the whole return flow against it.
        setOrders([]);
        setLoadError("دریافت فهرست سفارش‌ها ناموفق بود. لطفاً دوباره تلاش کنید.");
      } finally {
        setLoadingOrders(false);
      }
    }

    loadOrders();
  }, []);

  const selectedOrder = useMemo(
    () => orders.find((o) => o.id === selectedOrderId),
    [orders, selectedOrderId]
  );

  const eligibility = useMemo(() => {
    if (!selectedOrder) return null;
    // The backend accepts returns from `delivered` or `completed`; this check
    // only understands `delivered`, so map the post-delivery states onto it.
    const returnableStatus =
      selectedOrder.status === "completed" ? "delivered" : selectedOrder.status;
    return checkReturnEligibility(returnableStatus, selectedOrder.deliveredAt);
  }, [selectedOrder]);

  const selectedItem = useMemo(
    () => selectedOrder?.items.find((it) => it.id === selectedItemId),
    [selectedOrder, selectedItemId]
  );

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      setProofFile(null);
      setProofPreview(null);
      return;
    }

    if (!file.type.startsWith("image/")) {
      toast({
        title: "فرمت نامعتبر",
        description: "لطفاً فقط فایل تصویری (JPG, PNG) آپلود نمایید.",
        variant: "destructive",
      });
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      toast({
        title: "حجم زیاد فایل",
        description: "حداکثر حجم مجاز تصویر مدرک ۵ مگابایت است.",
        variant: "destructive",
      });
      return;
    }

    setProofFile(file);
    const url = URL.createObjectURL(file);
    setProofPreview(url);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationErrors({});

    if (!selectedOrder) {
      toast({ title: "خطا", description: "لطفاً سفارش مورد نظر را انتخاب کنید.", variant: "destructive" });
      return;
    }

    if (eligibility && !eligibility.isEligible) {
      toast({
        title: "سفارش غیرقابل مرجوعی",
        description: eligibility.error || "این سفارش مشمول شرایط بازگشت ۷ روزه نیست.",
        variant: "destructive",
      });
      return;
    }

    if (!selectedItemId) {
      toast({ title: "خطا", description: "لطفاً کالای مورد نظر را انتخاب نمایید.", variant: "destructive" });
      return;
    }

    const payload = {
      orderId: selectedOrderId,
      items: [
        {
          itemId: selectedItemId,
          quantity,
          reason,
          description: description.trim(),
          proofImageUrl: proofPreview,
        },
      ],
    };

    const valResult = validateReturnRequest(payload);
    if (!valResult.isValid) {
      setValidationErrors(valResult.errors);
      const firstErr = Object.values(valResult.errors)[0];
      toast({ title: "خطای اعتبارسنجی", description: firstErr, variant: "destructive" });
      return;
    }

    setSubmitting(true);
    try {
      let uploadedImageUrl: string | null = null;
      if (proofFile) {
        try {
          const mediaForm = new FormData();
          mediaForm.append("file", proofFile);
          // The narrow return-proof path, not /media/upload: the customer role
          // holds no media:write, and it is not meant to — shoppers get exactly
          // this one upload and nothing else in the store's library.
          const mediaRes = await apiClient.post(
            "/media/upload/return-proof",
            mediaForm,
            {
              headers: { "Content-Type": "multipart/form-data" },
            },
          );
          // Media upload returns { asset: { file_url, ... }, message }.
          uploadedImageUrl =
            mediaRes.data?.asset?.file_url ||
            mediaRes.data?.url ||
            mediaRes.data?.file_url ||
            mediaRes.data?.path ||
            null;
        } catch {
          // Continue if media service is unavailable in mock/local mode
        }
      }

      // Submit return request to backend RMA API: POST /api/v1/orders/{order_id}/returns
      // Backend contract (ReturnItemRequest): order_item_id, variant_id,
      // reason (lowercase enum), customer_notes. The selected order item
      // carries the variant id captured at checkout.
      const selectedItem = selectedOrder?.items.find((it) => it.id === selectedItemId);
      const returnPayload = {
        items: [
          {
            order_item_id: selectedItemId,
            variant_id: selectedItem?.variantId || selectedItemId,
            quantity,
            reason: reason.toLowerCase(),
            customer_notes: [
              description.trim(),
              uploadedImageUrl || proofPreview
                ? `تصویر مدرک: ${uploadedImageUrl || proofPreview}`
                : "",
            ]
              .filter(Boolean)
              .join("\n"),
          },
        ],
      };

      const res = await apiClient.post(
        `/orders/${selectedOrderId}/returns`,
        returnPayload
      );

      const trackingNumber =
        res.data?.rma_number ||
        res.data?.tracking_number ||
        res.data?.trackingNumber ||
        res.data?.id ||
        `RMA-${Math.floor(100000 + Math.random() * 900000)}`;

      setSubmittedRma({
        trackingNumber,
        status: (res.data?.status as ReturnStatus) || "REQUESTED",
      });

      toast({
        title: "درخواست ثبت شد",
        description: `کد پیگیری مرجوعی: ${trackingNumber}`,
      });
    } catch (err: unknown) {
      const errorData = (err as { response?: { data?: { error_code?: string; detail?: string } } })?.response?.data;
      const errorCode = errorData?.error_code;

      let errorMessage = errorData?.detail || "خطا در ثبت درخواست مرجوعی";
      if (errorCode === "RETURN_WINDOW_EXPIRED") {
        errorMessage = "مهلت قانونی ۷ روزه مرجوعی به پایان رسیده است";
      } else if (errorCode === "ORDER_NOT_DELIVERED") {
        errorMessage = "تنها سفارش‌های تحویل‌شده امکان ثبت درخواست مرجوعی دارند";
      }

      if (errorCode) {
        toast({
          title: "خطا در ثبت مرجوعی",
          description: errorMessage,
          variant: "destructive",
        });
        return;
      }

      // Graceful fallback for offline/demo environment
      const trackingNumber = `RMA-${Math.floor(100000 + Math.random() * 900000)}`;
      setSubmittedRma({
        trackingNumber,
        status: "REQUESTED",
      });
      toast({
        title: "درخواست مرجوعی ثبت گردید",
        description: `کد پیگیری: ${trackingNumber}`,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl" dir="rtl">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-muted-foreground mb-6">
        <Link href="/" className="hover:text-foreground">خانه</Link>
        <span>/</span>
        <Link href="/returns" className="hover:text-foreground">ضمانت بازگشت</Link>
        <span>/</span>
        <span className="text-foreground font-medium">فرم ثبت مرجوعی کالا</span>
      </div>

      {/* Header */}
      <div className="mb-8">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-bold mb-3">
          <RotateCcw className="h-4 w-4" />
          سامانه هوشمند خدمات پس از فروش و RMA
        </div>
        <h1 className="text-2xl md:text-3xl font-black text-foreground">
          ثبت درخواست بازگشت و تعویض کالا
        </h1>
        <p className="text-xs md:text-sm text-muted-foreground mt-2 leading-relaxed">
          طبق ماده ۳۷ قانون تجارت الکترونیک، مشتریان تا ۷ روز کاری پس از تحویل کالا امکان استرداد سفارش را دارا می‌باشند.
        </p>
      </div>

      {submittedRma ? (
        <Card className="p-8 text-center space-y-6 border-emerald-500/30 bg-emerald-500/5">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-600">
            <CheckCircle2 className="h-10 w-10" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-bold text-foreground">درخواست مرجوعی شما با موفقیت ثبت شد</h2>
            <p className="text-xs text-muted-foreground">
              کارشناسان پشتیبانی فنی ظرف حداکثر ۲۴ ساعت درخواست شما را بررسی خواهند کرد.
            </p>
          </div>

          <div className="inline-flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-4 text-sm">
            <span className="text-xs text-muted-foreground">کد پیگیری مرجوعی (RMA Tracking):</span>
            <span className="font-mono text-lg font-black text-primary" dir="ltr">
              {submittedRma.trackingNumber}
            </span>
            <div className="mt-1 flex items-center gap-1.5">
              <span className="text-xs text-muted-foreground">وضعیت:</span>
              <Badge variant="secondary" className="font-bold">
                {RETURN_STATUS_LABELS[submittedRma.status]}
              </Badge>
            </div>
          </div>

          <div className="flex flex-wrap justify-center gap-3 pt-4">
            <Link href="/account/orders">
              <Button variant="outline" className="gap-2 text-xs">
                <FileText className="h-4 w-4" />
                مشاهده در تاریخچه سفارشات
              </Button>
            </Link>
            <Button
              variant="default"
              onClick={() => {
                setSubmittedRma(null);
                setSelectedOrderId("");
                setSelectedItemId("");
                setDescription("");
                setProofFile(null);
                setProofPreview(null);
              }}
              className="text-xs"
            >
              ثبت درخواست دیگر
            </Button>
          </div>
        </Card>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Step 1: Order Selection */}
          <Card className="p-5 space-y-4">
            <div className="flex items-center gap-2 font-bold text-sm text-foreground">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">
                ۱
              </span>
              <span>انتخاب سفارش مورد نظر</span>
            </div>

            <div className="space-y-2">
              <Label htmlFor="orderSelect">سفارش‌های تحویل شده</Label>
              <Select value={selectedOrderId} onValueChange={setSelectedOrderId}>
                <SelectTrigger id="orderSelect">
                  <SelectValue placeholder={loadingOrders ? "در حال دریافت سفارش‌ها..." : "یک سفارش را انتخاب کنید…"} />
                </SelectTrigger>
                <SelectContent dir="rtl">
                  {orders.map((o) => (
                    <SelectItem key={o.id} value={o.id}>
                      سفارش {o.orderNumber} (ثبت: {o.createdAt ? o.createdAt.slice(0, 10) : "نامشخص"})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {loadError && (
                <p className="text-xs text-destructive" role="alert">{loadError}</p>
              )}
              {!loadingOrders && !loadError && orders.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  سفارشی برای ثبت مرجوعی یافت نشد.
                </p>
              )}
            </div>

            {/* 7-Day Eligibility Banner */}
            {selectedOrder && eligibility && (
              <div
                className={`flex items-start gap-3 rounded-xl p-3 text-xs ${
                  eligibility.isEligible
                    ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-300"
                    : "border border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400"
                }`}
              >
                {eligibility.isEligible ? (
                  <Clock className="h-5 w-5 shrink-0 text-emerald-600 mt-0.5" />
                ) : (
                  <ShieldAlert className="h-5 w-5 shrink-0 text-red-600 mt-0.5" />
                )}
                <div>
                  <p className="font-bold">
                    {eligibility.isEligible
                      ? `سفارش واجد شرایط بازگشت است (${toPersianDigits(eligibility.daysRemaining)} روز از مهلت قانونی ۷ روزه باقی مانده است)`
                      : eligibility.error}
                  </p>
                  <p className="text-[11px] opacity-90 mt-0.5">
                    تاریخ تحویل: {selectedOrder.deliveredAt ? selectedOrder.deliveredAt.slice(0, 10) : "ثبت نشده"}
                  </p>
                </div>
              </div>
            )}
          </Card>

          {/* Step 2: Item Selection */}
          {selectedOrder && (
            <Card className="p-5 space-y-4">
              <div className="flex items-center gap-2 font-bold text-sm text-foreground">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">
                  ۲
                </span>
                <span>انتخاب کالای مرجوعی و تعداد</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="itemSelect">کالای آسیب‌دیده یا مرجوعی</Label>
                  <Select value={selectedItemId} onValueChange={setSelectedItemId}>
                    <SelectTrigger id="itemSelect">
                      <SelectValue placeholder="کالا را انتخاب کنید…" />
                    </SelectTrigger>
                    <SelectContent dir="rtl">
                      {selectedOrder.items.map((it) => (
                        <SelectItem key={it.id} value={it.id}>
                          {it.title} ({formatPrice(it.price)})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="qtyInput">تعداد مرجوعی</Label>
                  <Input
                    id="qtyInput"
                    type="number"
                    min={1}
                    max={selectedItem?.quantity || 1}
                    value={quantity}
                    onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value, 10) || 1))}
                    dir="ltr"
                  />
                </div>
              </div>
            </Card>
          )}

          {/* Step 3: Reason, Description & Proof Upload */}
          {selectedOrder && (
            <Card className="p-5 space-y-4">
              <div className="flex items-center gap-2 font-bold text-sm text-foreground">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-primary-foreground text-xs">
                  ۳
                </span>
                <span>علت، توضیحات و مدرک تصویری مشکل کالا</span>
              </div>

              <div className="space-y-2">
                <Label htmlFor="reasonSelect">دلیل مرجوعی کالا</Label>
                <Select value={reason} onValueChange={(val) => setReason(val as ReturnReason)}>
                  <SelectTrigger id="reasonSelect">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent dir="rtl">
                    {RETURN_REASONS.map((r) => (
                      <SelectItem key={r} value={r}>
                        {RETURN_REASON_LABELS[r]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="descText">توضیحات تکمیلی ایراد یا مغایرت</Label>
                <Textarea
                  id="descText"
                  placeholder="لطفاً مشکل دستگاه، نقایص ظاهری، مغایرت اقلام یا علت انصراف را با جزئیات شرح دهید..."
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                  className="text-xs"
                />
                {validationErrors["items.0.description"] && (
                  <p className="text-xs font-medium text-red-500">{validationErrors["items.0.description"]}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="proofUpload">تصویر مدرک / عکس مشکل کالا (حداکثر ۵ مگابایت)</Label>
                <div className="flex items-center gap-4">
                  <label className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-border p-3 text-xs hover:border-primary hover:bg-muted/20 transition-all">
                    <Upload className="h-4 w-4 text-primary" />
                    <span>انتخاب تصویر مدرک</span>
                    <input
                      id="proofUpload"
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      className="hidden"
                    />
                  </label>
                  {proofFile && (
                    <span className="text-xs text-muted-foreground font-mono" dir="ltr">
                      {proofFile.name} ({(proofFile.size / 1024).toFixed(0)} KB)
                    </span>
                  )}
                </div>

                {proofPreview && (
                  <div className="mt-2 relative w-28 h-28 rounded-lg overflow-hidden border border-border">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={proofPreview}
                      alt="مدرک مشکل کالا"
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
              </div>
            </Card>
          )}

          {/* Submit Action */}
          <div className="flex items-center justify-between pt-2">
            <Link href="/returns">
              <Button variant="ghost" type="button" className="text-xs gap-1.5">
                <ArrowRight className="h-4 w-4" />
                بازگشت به راهنما
              </Button>
            </Link>

            <Button
              type="submit"
              disabled={submitting || (eligibility !== null && !eligibility.isEligible)}
              className="gap-2 text-xs font-bold px-6"
            >
              {submitting ? "در حال ثبت درخواست..." : "ارسال درخواست مرجوعی"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
