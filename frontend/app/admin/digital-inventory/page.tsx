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
}

export default function AdminDigitalInventoryPage() {
  const { toast } = useToast();
  const [cards, setCards] = useState<DigitalCard[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  // Import dialog
  const [importOpen, setImportOpen] = useState(false);
  const [productId, setProductId] = useState("");
  const [deliveryType, setDeliveryType] = useState("unique");
  const [maxUses, setMaxUses] = useState("1");
  const [pinsText, setPinsText] = useState("");
  const [importing, setImporting] = useState(false);

  const fetchCards = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/inventory/digital/cards", {
        params: { status: statusFilter !== "all" ? statusFilter : undefined },
      });
      setCards(res.data.items || res.data);
    } catch {
      toast({
        title: "خطا در بارگذاری",
        description: "دریافت لیست کارت‌های دیجیتال با خطا مواجه شد",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchCards();
  }, [fetchCards]);

  const handleBulkImport = async () => {
    if (!pinsText.trim()) {
      toast({ title: "خطا", description: "کدها را وارد کنید", variant: "destructive" });
      return;
    }
    if (!productId) {
      toast({ title: "خطا", description: "محصول را انتخاب کنید", variant: "destructive" });
      return;
    }
    setImporting(true);
    try {
      // Create a Blob from the text and upload as file
      const lines = pinsText.trim().split("\n");
      const csvContent = lines.join("\n");
      const blob = new Blob([csvContent], { type: "text/csv" });
      const file = new File([blob], "pins.csv", { type: "text/csv" });

      const formData = new FormData();
      formData.append("product_id", productId);
      formData.append("delivery_type", deliveryType);
      formData.append("max_uses", maxUses);
      formData.append("file", file);

      const res = await apiClient.post("/inventory/digital/cards/import", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const result: ImportResult = res.data;
      toast({
        title: "ایمپورت موفق",
        description: `${result.imported_count} کارت اضافه شد، ${result.duplicate_count} تکراری، ${result.error_count} خطا`,
      });
      setImportOpen(false);
      setPinsText("");
      fetchCards();
    } catch {
      toast({ title: "خطا", description: "ایمپورت کارت‌ها با خطا مواجه شد", variant: "destructive" });
    } finally {
      setImporting(false);
    }
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
            <RefreshCw className="h-4 w-4 mr-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setImportOpen(true)}>
            <Upload className="h-4 w-4 mr-2" />
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
            className="pr-9"
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

      {/* Cards Table */}
      <Card>
        {loading ? (
          <div className="flex items-center justify-center p-12">
            <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : filteredCards.length === 0 ? (
          <div className="text-center p-12 text-muted-foreground">
            <CreditCard className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm">هیچ کارتی یافت نشد</p>
            <p className="text-xs mt-1">برای افزودن کارت جدید روی «بارگذاری کارت جدید» کلیک کنید</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-right p-3 font-medium">سریال</th>
                  <th className="text-right p-3 font-medium">نوع</th>
                  <th className="text-right p-3 font-medium">وضعیت</th>
                  <th className="text-right p-3 font-medium">استفاده</th>
                  <th className="text-right p-3 font-medium">تاریخ ایجاد</th>
                </tr>
              </thead>
              <tbody>
                {filteredCards.slice(0, 50).map((card) => (
                  <tr key={card.id} className="border-b hover:bg-muted/30">
                    <td className="p-3 font-mono text-xs" dir="ltr">
                      {card.serial_number || card.card_hash.slice(0, 12) + "..."}
                    </td>
                    <td className="p-3 text-xs">
                      <Badge variant="outline">
                        {card.delivery_type === "unique" ? "یکتا" : card.delivery_type === "shared" ? "اشتراکی" : "فایل"}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Badge className={statusColors[card.status]}>{statusLabels[card.status]}</Badge>
                    </td>
                    <td className="p-3 text-xs">
                      {card.used_count} / {card.max_uses}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground" dir="ltr">
                      {new Date(card.created_at).toLocaleDateString("fa-IR")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>حداکثر استفاده</Label>
                <Input type="number" min={1} value={maxUses} onChange={(e) => setMaxUses(e.target.value)} dir="ltr" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>کدها (هر خط یک کد)</Label>
              <Textarea
                placeholder={"PIN-001\nPIN-002\nPIN-003\n..."}
                value={pinsText}
                onChange={(e) => setPinsText(e.target.value)}
                rows={8}
                dir="ltr"
                className="font-mono"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportOpen(false)}>
              انصراف
            </Button>
            <Button onClick={handleBulkImport} disabled={importing}>
              {importing ? "در حال بارگذاری..." : "بارگذاری"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
