"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ScanLine,
  RefreshCw,
  Trash2,
  PackageCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  inventoryScanApi,
  type ScanBatchResult,
} from "@/lib/api/inventory-operations";
import { toPersianDigits, formatPrice } from "@/lib/utils";

/**
 * Barcode scanning station (ERP feature #26).
 *
 * Input is a plain text field that keeps focus: a USB scanner is a keyboard
 * that types fast and presses Enter, so the fastest interface is one where
 * the operator never touches the mouse. Persian digits are accepted (the
 * backend normalises them) because a hand-typed code is the common fallback
 * when a label is damaged.
 */
export default function AdminInventoryScanPage() {
  const { toast } = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [pending, setPending] = useState<string[]>([]);
  const [result, setResult] = useState<ScanBatchResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [warehouseId, setWarehouseId] = useState("");
  const [receiving, setReceiving] = useState(false);

  // Keep the cursor in the scan field: an operator scanning a shelf should
  // never have to click back into the box between beeps.
  const refocus = useCallback(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    refocus();
  }, [refocus]);

  const addScan = (raw: string) => {
    const code = raw.trim();
    if (!code) return;
    setPending((prev) => [...prev, code]);
  };

  const resolve = async () => {
    if (pending.length === 0) {
      toast({ title: "چیزی اسکن نشده است", variant: "destructive" });
      return;
    }
    setBusy(true);
    try {
      const res = await inventoryScanApi.resolve({
        codes: pending,
        warehouse_id: warehouseId.trim() || null,
      });
      setResult(res);
      if (res.unresolved_count > 0) {
        toast({
          title: `${toPersianDigits(String(res.unresolved_count))} بارکد شناسایی نشد`,
          description: "بقیه اقلام آماده دریافت‌اند.",
          variant: "destructive",
        });
      }
    } catch {
      toast({
        title: "شناسایی ناموفق بود",
        description: "دسترسی inventory:read لازم است.",
        variant: "destructive",
      });
      setResult(null);
    } finally {
      setBusy(false);
      refocus();
    }
  };

  const receive = async () => {
    if (!result || result.resolved_count === 0) return;
    setReceiving(true);
    try {
      const res = await inventoryScanApi.receive({
        codes: pending,
        warehouse_id: warehouseId.trim() || null,
      });
      toast({
        title: "رسید دریافت ایجاد شد",
        description: `${toPersianDigits(String(res.line_count))} قلم — رسید در وضعیت پیش‌نویس است.`,
        variant: "success",
      });
      setPending([]);
      setResult(null);
    } catch {
      toast({
        title: "ایجاد رسید ناموفق بود",
        description: "دسترسی inventory:write لازم است.",
        variant: "destructive",
      });
    } finally {
      setReceiving(false);
      refocus();
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <ScanLine className="h-5 w-5 text-primary" />
            ایستگاه اسکن بارکد
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            بارکد را اسکن کنید و Enter بزنید. اقلام تکراری خودکار جمع می‌شوند
            و موجودی بر اساس انباری که در آن ایستاده‌اید نمایش داده می‌شود.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refocus}>
          <RefreshCw className="ms-2 h-4 w-4" />
          بازگشت به کادر اسکن
        </Button>
      </div>

      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_260px]">
          <div>
            <Label htmlFor="scan-input">کادر اسکن</Label>
            <Input
              id="scan-input"
              ref={inputRef}
              dir="ltr"
              autoFocus
              placeholder="بارکد را اسکن یا تایپ کنید و Enter بزنید"
              className="mt-1 text-lg"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  const value = (e.target as HTMLInputElement).value;
                  addScan(value);
                  (e.target as HTMLInputElement).value = "";
                }
              }}
            />
          </div>
          <div>
            <Label htmlFor="scan-warehouse">شناسه انبار (اختیاری)</Label>
            <Input
              id="scan-warehouse"
              dir="ltr"
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              placeholder="UUID انبار"
              className="mt-1 font-mono text-xs"
            />
            <p className="mt-1 text-[11px] text-muted-foreground">
              خالی بگذارید تا موجودی در همه انبارها جمع شود.
            </p>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Badge variant="secondary">
            {toPersianDigits(String(pending.length))} اسکن در انتظار
          </Badge>
          <Button onClick={resolve} disabled={busy || pending.length === 0}>
            <ScanLine className="ms-2 h-4 w-4" />
            شناسایی
          </Button>
          <Button
            variant="outline"
            onClick={() => {
              setPending([]);
              setResult(null);
              refocus();
            }}
            disabled={pending.length === 0}
          >
            <Trash2 className="ms-2 h-4 w-4" />
            پاک کردن
          </Button>
        </div>

        {pending.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {pending.slice(-20).map((code, i) => (
              <span
                key={`${code}-${i}`}
                className="rounded bg-muted px-2 py-0.5 font-mono text-[11px]"
                dir="ltr"
              >
                {code}
              </span>
            ))}
            {pending.length > 20 && (
              <span className="text-[11px] text-muted-foreground">
                و {toPersianDigits(String(pending.length - 20))} مورد دیگر…
              </span>
            )}
          </div>
        )}
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Card className="p-3">
              <p className="text-xs text-muted-foreground">کل اسکن</p>
              <p className="text-lg font-bold">
                {toPersianDigits(String(result.total_scanned))}
              </p>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-muted-foreground">شناسایی‌شده</p>
              <p className="text-lg font-bold text-emerald-600">
                {toPersianDigits(String(result.resolved_count))}
              </p>
            </Card>
            <Card className="p-3">
              <p className="text-xs text-muted-foreground">شناسایی‌نشده</p>
              <p
                className={`text-lg font-bold ${
                  result.unresolved_count > 0 ? "text-destructive" : ""
                }`}
              >
                {toPersianDigits(String(result.unresolved_count))}
              </p>
            </Card>
          </div>

          {result.unresolved_count > 0 && (
            <Card className="border-destructive/40 bg-destructive/5 p-4">
              <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
                <AlertTriangle className="h-4 w-4 text-destructive" />
                بارکدهای شناسایی‌نشده
              </p>
              <div className="space-y-1">
                {result.unresolved.map((u) => (
                  <div
                    key={u.code}
                    className="flex flex-wrap items-center gap-2 rounded bg-background/60 px-2 py-1 text-xs"
                  >
                    <span className="font-mono" dir="ltr">
                      {u.code}
                    </span>
                    <span className="text-muted-foreground">{u.reason}</span>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-muted-foreground">
                بقیه اقلام سالم‌اند — می‌توانید همین حالا رسید بگیرید و بارکد
                معیوب را جدا اصلاح کنید.
              </p>
            </Card>
          )}

          {result.resolved_count > 0 && (
            <div>
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold">اقلام شناسایی‌شده</h3>
                <Button onClick={receive} disabled={receiving}>
                  <PackageCheck className="ms-2 h-4 w-4" />
                  {receiving ? "در حال ایجاد..." : "ایجاد رسید دریافت"}
                </Button>
              </div>
              <div className="space-y-1.5">
                {result.resolved.map((scan) => (
                  <Card key={scan.variant_id} className="p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex min-w-0 items-center gap-2">
                        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
                        <div className="min-w-0">
                          <p className="truncate text-sm">{scan.product_name}</p>
                          <p
                            className="font-mono text-[10px] text-muted-foreground"
                            dir="ltr"
                          >
                            {scan.sku} · {scan.code}
                          </p>
                        </div>
                        {!scan.is_active && (
                          <Badge variant="destructive" className="text-[10px]">
                            <XCircle className="ms-1 h-3 w-3" />
                            غیرفعال
                          </Badge>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-4 text-xs">
                        <span>
                          تعداد:{" "}
                          <strong>{toPersianDigits(String(scan.quantity))}</strong>
                        </span>
                        <span className="text-muted-foreground">
                          موجودی: {toPersianDigits(String(scan.on_hand))}
                        </span>
                        <span className="text-muted-foreground">
                          قابل‌استفاده:{" "}
                          <span
                            className={
                              scan.available === 0 ? "text-destructive" : ""
                            }
                          >
                            {toPersianDigits(String(scan.available))}
                          </span>
                        </span>
                        <span className="text-muted-foreground">
                          {/* `price_rial` is the raw DB column (Rial), the same value the
                            catalog API divides by 10. Verified against live data:
                            order_items.unit_price equals this column exactly. The
                            division is required, not redundant. */}
                          {formatPrice(Math.trunc(scan.price_rial / 10))}
                        </span>
                      </div>
                    </div>
                    {scan.warnings.length > 0 && (
                      <div className="mt-2 space-y-0.5">
                        {scan.warnings.map((w, i) => (
                          <p
                            key={i}
                            className="flex items-center gap-1 text-[11px] text-amber-600"
                          >
                            <AlertTriangle className="h-3 w-3" />
                            {w}
                          </p>
                        ))}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
