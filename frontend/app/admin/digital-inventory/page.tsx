"use client";

import React, { useState, useEffect, useCallback } from "react";
import { CreditCard, Upload, Plus, Search, RefreshCw, Layers, Tag } from "lucide-react";
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
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { useAdminQuery } from "@/lib/api/admin-query";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { PageLoader } from "@/components/shared/page-state";
import {
  validateBulkImportFile,
  validatePastedPins,
  extractRowErrors,
  type BulkImportRowResult,
} from "@/lib/bulk-import-validator";

interface DigitalCard {
  id: string;
  product_id: string;
  delivery_type: "unique" | "shared" | "file";
  serial_number: string | null;
  card_hash: string;
  status: "available" | "reserved" | "delivered" | "revoked" | "expired";
  max_uses: number;
  used_count: number;
  expire_at: string | null;
  reading_at: string | null;
  created_at: string;
}

interface ImportResult {
  total_rows: number;
  imported_count: number;
  duplicate_count: number;
  error_count: number;
  details?: BulkImportRowResult[];
}

export default function AdminDigitalInventoryPage() {
  const { toast } = useToast();
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  // Data fetching via TanStack Query wrapper
  const {
    data: cards = [],
    loading,
    reload: fetchCards,
  } = useAdminQuery<DigitalCard[]>({
    queryKey: ["admin", "digital-inventory", statusFilter],
    queryFn: async () => {
      const res = await apiClient.get("/inventory/digital/cards", {
        params: { status: statusFilter !== "all" ? statusFilter : undefined },
      });
      return res.data?.items || res.data || [];
    },
    fallbackError: "دریافت لیست کارت‌های دیجیتال با خطا مواجه شد",
  });

  // Import dialog
  const [importOpen, setImportOpen] = useState(false);
  const [productId, setProductId] = useState("");
  const [deliveryType, setDeliveryType] = useState("unique");
  const [maxUses, setMaxUses] = useState("1");
  const [pinsText, setPinsText] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [importValidationError, setImportValidationError] = useState<string | null>(null);
  const [pastedWarnings, setPastedWarnings] = useState<string | null>(null);
  // File-type stocking (Karta file_to_cards) + real CSV/XLSX import
  const [assetFile, setAssetFile] = useState<File | null>(null);
  const [copies, setCopies] = useState("1");
  const [importFile, setImportFile] = useState<File | null>(null);
  // Batch edit (Sprint 1.4)
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  // Tiered pricing (Sprint 1.6)
  const [tiersOpen, setTiersOpen] = useState(false);
  const [tierProductId, setTierProductId] = useState("");
  const [tierList, setTierList] = useState<Array<{ id: string; from_qty: number; to_qty: number | null; unit_price: number }>>([]);
  const [tierFrom, setTierFrom] = useState("");
  const [tierTo, setTierTo] = useState("");
  const [tierPrice, setTierPrice] = useState("");

  const handleBulkImport = async () => {
    setImportValidationError(null);
    setPastedWarnings(null);
    setImportResult(null);

    if (!productId) {
      const err = "لطفاً یک محصول را انتخاب کنید";
      setImportValidationError(err);
      toast({ title: "خطای اعتبارسنجی", description: err, variant: "destructive" });
      return;
    }

    // Pre-validation for File delivery type
    if (deliveryType === "file") {
      if (!assetFile) {
        const err = "فایل لایسنس/کانفیگ را انتخاب کنید";
        setImportValidationError(err);
        toast({ title: "خطای اعتبارسنجی", description: err, variant: "destructive" });
        return;
      }
      if (assetFile.size > 50 * 1024 * 1024) {
        const err = "حجم فایل لایسنس نمی‌تواند بیشتر از ۵۰ مگابایت باشد";
        setImportValidationError(err);
        toast({ title: "خطای اعتبارسنجی", description: err, variant: "destructive" });
        return;
      }
    } else {
      // Pre-validation for CSV/Excel file or pasted text
      if (importFile) {
        const fileCheck = validateBulkImportFile(importFile);
        if (!fileCheck.isValid) {
          setImportValidationError(fileCheck.error);
          toast({ title: "خطای فایل انتخابی", description: fileCheck.error, variant: "destructive" });
          return;
        }
      } else {
        const textCheck = validatePastedPins(pinsText);
        if (!textCheck.isValid) {
          setImportValidationError(textCheck.error);
          toast({ title: "خطای ورودی کدها", description: textCheck.error, variant: "destructive" });
          return;
        }
        if (textCheck.duplicateCount > 0) {
          setPastedWarnings(`${textCheck.duplicateCount} کد تکراری در متن ورودی یافت شد.`);
        }
      }
    }

    setImporting(true);
    try {
      // Karta file_to_cards: upload one asset and stock N sellable copies
      if (deliveryType === "file") {
        const assetForm = new FormData();
        assetForm.append("file", assetFile as File);
        const assetRes = await apiClient.post("/inventory/digital/file-assets", assetForm, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const cardsRes = await apiClient.post("/inventory/digital/cards/file", {
          product_id: productId,
          file_path: assetRes.data.file_path,
          copies: Math.max(1, parseInt(copies || "1", 10)),
        });
        toast({
          title: "ثبت موفق",
          description: `${cardsRes.data.created} نسخه قابل‌فروش از فایل ساخته شد`,
        });
        setImportOpen(false);
        setAssetFile(null);
        setCopies("1");
        fetchCards();
        return;
      }

      // Upload a real CSV/XLSX file when provided; otherwise build CSV from pasted text
      let file: File;
      if (importFile) {
        file = importFile;
      } else {
        const lines = pinsText.trim().split("\n");
        const csvContent = lines.join("\n");
        const blob = new Blob([csvContent], { type: "text/csv" });
        file = new File([blob], "pins.csv", { type: "text/csv" });
      }

      const formData = new FormData();
      formData.append("product_id", productId);
      formData.append("delivery_type", deliveryType);
      formData.append("max_uses", maxUses);
      formData.append("file", file);

      const res = await apiClient.post("/inventory/digital/cards/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const result: ImportResult = res.data;
      setImportResult(result);

      if (result.error_count === 0 && result.duplicate_count === 0) {
        toast({
          title: "ایمپورت کامل و موفق",
          description: `${result.imported_count} کارت با موفقیت اضافه شد.`,
        });
        setImportOpen(false);
        setPinsText("");
        setImportFile(null);
        setImportResult(null);
      } else {
        toast({
          title: "ایمپورت با خطا یا تکرار ردیف‌ها",
          description: `${result.imported_count} موفق، ${result.duplicate_count} تکراری، ${result.error_count} خطا`,
          variant: "destructive",
        });
      }
      fetchCards();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "ایمپورت کارت‌ها با خطا مواجه شد";
      setImportValidationError(msg);
      toast({ title: "خطا در عملیات", description: msg, variant: "destructive" });
    } finally {
      setImporting(false);
    }
  };

  const handleLoadTiers = async () => {
    if (!tierProductId) return;
    try {
      const res = await apiClient.get(`/inventory/digital/products/${tierProductId}/pricing-tiers`);
      setTierList(Array.isArray(res.data) ? res.data : []);
    } catch {
      setTierList([]);
    }
  };

  const handleCreateTier = async () => {
    if (!tierProductId || !tierFrom || !tierPrice) {
      toast({ title: "خطا", description: "شناسه محصول، از تعداد و قیمت واحد الزامی است", variant: "destructive" });
      return;
    }
    try {
      await apiClient.post("/inventory/digital/pricing-tiers", {
        product_id: tierProductId,
        from_qty: parseInt(tierFrom, 10),
        to_qty: tierTo ? parseInt(tierTo, 10) : null,
        unit_price: parseInt(tierPrice, 10),
      });
      toast({ title: "ثبت شد", description: "پله قیمتی جدید ایجاد شد" });
      setTierFrom("");
      setTierTo("");
      setTierPrice("");
      handleLoadTiers();
    } catch {
      toast({ title: "خطا", description: "ایجاد پله قیمتی ناموفق بود", variant: "destructive" });
    }
  };

  const handleBatchEdit = async (payload: Record<string, unknown>, label: string) => {
    if (selectedIds.length === 0) {
      toast({ title: "خطا", description: "کارتی انتخاب نشده است", variant: "destructive" });
      return;
    }
    try {
      const res = await apiClient.patch("/inventory/digital/cards/batch", {
        card_ids: selectedIds,
        ...payload,
      });
      toast({ title: label, description: `${res.data.updated} کارت به‌روزرسانی شد` });
      setSelectedIds([]);
      fetchCards();
    } catch {
      toast({ title: "خطا", description: "ویرایش گروهی ناموفق بود", variant: "destructive" });
    }
  };

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const filteredCards = cards.filter(
    (c) =>
      !search ||
      (c.serial_number && c.serial_number.includes(search)) ||
      c.card_hash.includes(search)
  );

  const statusColors: Record<string, string> = {
    available: "bg-emerald-500/10 text-emerald-500",
    delivered: "bg-blue-500/10 text-blue-500",
    reserved: "bg-amber-500/10 text-amber-500",
    revoked: "bg-rose-500/10 text-rose-500",
    expired: "bg-neutral-500/10 text-neutral-500",
  };

  const statusLabels: Record<string, string> = {
    available: "موجود",
    delivered: "تحویل‌شده",
    reserved: "رزرو‌شده",
    revoked: "ابطال‌شده",
    expired: "منقضی",
  };

  const cardColumns: DataTableColumn<DigitalCard>[] = [
    {
      key: "select",
      header: "",
      className: "w-8",
      render: (card) => (
        <input
          type="checkbox"
          checked={selectedIds.includes(card.id)}
          onChange={() => toggleSelect(card.id)}
          aria-label="انتخاب کارت"
        />
      ),
    },
    {
      key: "serial",
      header: "سریال",
      className: "font-mono text-xs",
      render: (card) => (
        <span dir="ltr">{card.serial_number || card.card_hash.slice(0, 12) + "..."}</span>
      ),
    },
    {
      key: "type",
      header: "نوع",
      className: "text-xs",
      render: (card) => (
        <Badge variant="outline">
          {card.delivery_type === "unique" ? "یکتا" : card.delivery_type === "shared" ? "اشتراکی" : "فایل"}
        </Badge>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (card) => <Badge className={statusColors[card.status]}>{statusLabels[card.status]}</Badge>,
    },
    {
      key: "uses",
      header: "استفاده",
      className: "text-xs",
      render: (card) => `${card.used_count} / ${card.max_uses}`,
    },
    {
      key: "created",
      header: "تاریخ ایجاد",
      className: "text-xs text-muted-foreground",
      render: (card) => (
        <span dir="ltr">{new Date(card.created_at).toLocaleDateString("fa-IR")}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <CreditCard className="h-5 w-5 text-primary" />
            انبار کدهای دیجیتال
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            مدیریت و بارگذاری پین‌ها، سریال‌ها و فایل‌های لایسنس
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchCards}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <Button size="sm" variant="outline" onClick={() => setTiersOpen(true)}>
            <Layers className="h-4 w-4 ms-2" />
            قیمت‌گذاری پلکانی
          </Button>
          <Button size="sm" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4 ms-2" />
            بارگذاری کارت جدید
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="وضعیت" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">همه</SelectItem>
            <SelectItem value="available">موجود</SelectItem>
            <SelectItem value="delivered">تحویل‌شده</SelectItem>
            <SelectItem value="reserved">رزرو‌شده</SelectItem>
            <SelectItem value="revoked">ابطال‌شده</SelectItem>
            <SelectItem value="expired">منقضی</SelectItem>
          </SelectContent>
        </Select>
        <div className="relative flex-1">
          <Search className="absolute right-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="جستجو بر اساس سریال یا هش..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="ps-9"
            dir="ltr"
          />
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">کل کارت‌ها</p>
          <p className="text-2xl font-bold">{cards.length.toLocaleString("fa-IR")}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">موجود</p>
          <p className="text-2xl font-bold text-emerald-500">
            {cards.filter((c) => c.status === "available").length.toLocaleString("fa-IR")}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">تحویل‌شده</p>
          <p className="text-2xl font-bold text-blue-500">
            {cards.filter((c) => c.status === "delivered").length.toLocaleString("fa-IR")}
          </p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">منقضی</p>
          <p className="text-2xl font-bold text-neutral-400">
            {cards.filter((c) => c.status === "expired").length.toLocaleString("fa-IR")}
          </p>
        </Card>
      </div>

      {/* Batch edit bar (Sprint 1.4) */}
      {selectedIds.length > 0 && (
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3">
          <span className="text-sm font-bold">
            {selectedIds.length.toLocaleString("fa-IR")} کارت انتخاب شده
          </span>
          <Button size="sm" variant="destructive" onClick={() => handleBatchEdit({ status: "revoked" }, "ابطال گروهی")}>
            ابطال گروهی
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleBatchEdit({ status: "available" }, "بازگشت به موجودی")}>
            بازگشت به موجودی
          </Button>
          <Button size="sm" variant="ghost" onClick={() => handleBatchEdit({ clear_expire: true }, "حذف انقضا")}>
            حذف تاریخ انقضا
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setSelectedIds([])}>
            لغو انتخاب
          </Button>
        </div>
      )}

      {/* Cards Table */}
      <Card>
        {loading ? (
          <PageLoader message="در حال دریافت کارت‌های دیجیتال..." className="min-h-0 p-12" />
        ) : (
          <DataTable<DigitalCard>
            columns={cardColumns}
            rows={filteredCards.slice(0, 50)}
            rowKey={(c) => c.id}
            emptyMessage="هیچ کارتی یافت نشد"
            emptyDescription="برای افزودن کارت جدید روی «بارگذاری کارت جدید» کلیک کنید"
            emptyIcon={<CreditCard className="h-12 w-12 text-muted-foreground/30" />}
          />
        )}
      </Card>

      {/* Import Dialog */}
      <Dialog open={importOpen} onOpenChange={setImportOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>بارگذاری کارت جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>شناسه محصول</Label>
              <Input
                placeholder="UUID محصول"
                value={productId}
                onChange={(e) => setProductId(e.target.value)}
                dir="ltr"
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>نوع تحویل</Label>
                <Select value={deliveryType} onValueChange={setDeliveryType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unique">یکتا (یکبارمصرف)</SelectItem>
                    <SelectItem value="shared">اشتراکی (چندکاربره)</SelectItem>
                    <SelectItem value="file">فایل (لایسنس/کانفیگ)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {deliveryType !== "file" && (
                <div className="space-y-2">
                  <Label>حداکثر استفاده</Label>
                  <Input type="number" min={1} value={maxUses} onChange={(e) => setMaxUses(e.target.value)} dir="ltr" />
                </div>
              )}
            </div>
            {deliveryType === "file" ? (
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-2">
                  <Label>فایل لایسنس/کانفیگ</Label>
                  <input
                    type="file"
                    onChange={(e) => {
                      setAssetFile(e.target.files?.[0] ?? null);
                      setImportValidationError(null);
                    }}
                    className="w-full text-xs"
                  />
                </div>
                <div className="space-y-2">
                  <Label>تعداد نسخه قابل‌فروش</Label>
                  <Input type="number" min={1} value={copies} onChange={(e) => setCopies(e.target.value)} dir="ltr" />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  <Label>فایل CSV / Excel (اختیاری)</Label>
                  <input
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={(e) => {
                      setImportFile(e.target.files?.[0] ?? null);
                      setImportValidationError(null);
                    }}
                    className="w-full text-xs"
                  />
                </div>
                <div className="space-y-2">
                  <Label>یا کدها (هر خط یک کد)</Label>
                  <Textarea
                    placeholder={"PIN-001\nPIN-002\nPIN-003\n..."}
                    value={pinsText}
                    onChange={(e) => {
                      setPinsText(e.target.value);
                      setImportValidationError(null);
                      setPastedWarnings(null);
                    }}
                    rows={6}
                    dir="ltr"
                    className="font-mono"
                  />
                </div>
              </div>
            )}

            {/* Pre-validation warnings & errors */}
            {importValidationError && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-xs text-red-600 font-medium">
                {importValidationError}
              </div>
            )}
            {pastedWarnings && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-700">
                {pastedWarnings}
              </div>
            )}

            {/* Row-level / Partial Errors Breakdown */}
            {importResult && (importResult.error_count > 0 || importResult.duplicate_count > 0) && (
              <div className="space-y-3 rounded-lg border border-border p-3 bg-muted/30">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-foreground">گزارش پردازش ردیف‌ها:</span>
                  <div className="flex gap-2">
                    <Badge variant="outline">کل: {importResult.total_rows}</Badge>
                    <Badge variant="default" className="bg-emerald-600">موفق: {importResult.imported_count}</Badge>
                    {importResult.duplicate_count > 0 && (
                      <Badge variant="secondary" className="bg-amber-500/20 text-amber-700">تکراری: {importResult.duplicate_count}</Badge>
                    )}
                    {importResult.error_count > 0 && (
                      <Badge variant="destructive">خطا: {importResult.error_count}</Badge>
                    )}
                  </div>
                </div>

                {importResult.details && extractRowErrors(importResult.details).length > 0 && (
                  <div className="max-h-48 overflow-y-auto rounded border border-border bg-background p-2 text-xs">
                    <table className="w-full text-right">
                      <thead>
                        <tr className="border-b border-border text-muted-foreground">
                          <th className="py-1 px-2">ردیف</th>
                          <th className="py-1 px-2">فیلد</th>
                          <th className="py-1 px-2">شناسه/کارت</th>
                          <th className="py-1 px-2">وضعیت</th>
                          <th className="py-1 px-2">کد / علت خطا</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extractRowErrors(importResult.details).map((detail, idx) => {
                          const rowNum = detail.row_number ?? detail.row ?? idx + 1;
                          const isDup = detail.status === "duplicate_skipped";
                          return (
                            <tr key={idx} className="border-b border-border/50 last:border-0 hover:bg-muted/20">
                              <td className="py-1 px-2 font-mono" dir="ltr">{rowNum}</td>
                              <td className="py-1 px-2">
                                {detail.field ? (
                                  <Badge variant="outline" className="font-mono text-[10px] px-1 py-0" dir="ltr">
                                    {detail.field}
                                  </Badge>
                                ) : (
                                  <span className="text-muted-foreground">-</span>
                                )}
                              </td>
                              <td className="py-1 px-2 font-mono text-muted-foreground" dir="ltr">
                                {detail.serial_number || "-"}
                              </td>
                              <td className="py-1 px-2">
                                {isDup ? (
                                  <Badge variant="secondary" className="text-[10px] bg-amber-500/10 text-amber-600">
                                    تکراری
                                  </Badge>
                                ) : (
                                  <Badge variant="destructive" className="text-[10px]">
                                    خطا
                                  </Badge>
                                )}
                              </td>
                              <td className="py-1 px-2 text-red-500 text-[11px]">
                                {detail.detail || detail.error_code || "خطا در پردازش رکورد"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setImportOpen(false);
                setImportResult(null);
                setImportValidationError(null);
                setPastedWarnings(null);
              }}
            >
              {importResult && (importResult.error_count > 0 || importResult.duplicate_count > 0) ? "بستن گزارش" : "انصراف"}
            </Button>
            <Button onClick={handleBulkImport} disabled={importing}>
              {importing ? "در حال بارگذاری..." : "بارگذاری مجدد"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      {/* Tiered Pricing Dialog (Sprint 1.6) */}
      <Dialog open={tiersOpen} onOpenChange={setTiersOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>قیمت‌گذاری پلکانی تیراژ (Karta findPrice)</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>شناسه محصول</Label>
              <div className="flex gap-2">
                <Input
                  placeholder="UUID محصول"
                  value={tierProductId}
                  onChange={(e) => setTierProductId(e.target.value)}
                  dir="ltr"
                />
                <Button size="sm" variant="outline" onClick={handleLoadTiers}>
                  نمایش
                </Button>
              </div>
            </div>

            {tierList.length > 0 && (
              <div className="rounded-lg border border-border p-3 text-xs">
                {tierList.map((t) => (
                  <div key={t.id} className="flex justify-between py-1">
                    <span dir="rtl">
                      {t.to_qty === null
                        ? `${t.from_qty.toLocaleString("fa-IR")} و بالاتر`
                        : `${t.from_qty.toLocaleString("fa-IR")} تا ${t.to_qty.toLocaleString("fa-IR")}`}
                    </span>
                    <span className="font-bold" dir="ltr">
                      {t.unit_price.toLocaleString("fa-IR")} ریال
                    </span>
                  </div>
                ))}
              </div>
            )}

            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-2">
                <Label>از تعداد</Label>
                <Input type="number" min={1} value={tierFrom} onChange={(e) => setTierFrom(e.target.value)} dir="ltr" />
              </div>
              <div className="space-y-2">
                <Label>تا تعداد (خالی = بی‌نهایت)</Label>
                <Input type="number" min={1} value={tierTo} onChange={(e) => setTierTo(e.target.value)} dir="ltr" />
              </div>
              <div className="space-y-2">
                <Label>قیمت واحد (ریال)</Label>
                <Input type="number" min={0} value={tierPrice} onChange={(e) => setTierPrice(e.target.value)} dir="ltr" />
              </div>
            </div>
            <Button size="sm" className="w-full" onClick={handleCreateTier}>
              <Plus className="h-4 w-4 ms-2" />
              افزودن پله قیمتی
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
