"use client";

import React, { useState } from "react";
import { Plus, Tag, Loader2, Trash2, Percent, DollarSign } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import { useAdminQuery } from "@/lib/api/admin-query";

const PRICING_QUERY_KEY = "admin-pricing" as const;

/**
 * Price list management (Odoo product.pricelist concept, clean-room).
 *
 * Admins group pricing rules per customer segment. A rule overrides a
 * product's price by a fixed Rial amount or a percentage (entered as a whole
 * percent, sent to the API in basis points — integer money end to end).
 */

type Segment = "retail" | "gold" | "wholesale" | "b2b";

interface PriceList {
  id: string;
  name: string;
  segment: Segment;
  priority: number;
  is_active: boolean;
}

interface RuleDraft {
  product_id: string;
  min_quantity: string;
  mode: "fixed" | "percent";
  value: string; // Rial for fixed, whole-percent for percent
}

const SEGMENTS: { value: Segment; label: string }[] = [
  { value: "retail", label: "خرده‌فروشی" },
  { value: "gold", label: "مشتری طلایی" },
  { value: "wholesale", label: "عمده‌فروشی" },
  { value: "b2b", label: "سازمانی (B2B)" },
];

const segmentLabel = (s: Segment) => SEGMENTS.find((x) => x.value === s)?.label ?? s;

const EMPTY_RULE: RuleDraft = { product_id: "", min_quantity: "0", mode: "percent", value: "" };

export default function AdminPricingPage() {
  const { toast } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [name, setName] = useState("");
  const [segment, setSegment] = useState<Segment>("retail");
  const [priority, setPriority] = useState("100");
  const [rules, setRules] = useState<RuleDraft[]>([]);

  // Its failure was silent (an empty list) in the original; the query keeps
  // that, but derives the empty state from the loaded value rather than a
  // setter that also ran on error.
  const {
    data: listsData,
    loading: isLoading,
    reload: fetchLists,
  } = useAdminQuery({
    queryKey: [PRICING_QUERY_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/pricing/price-lists");
      return Array.isArray(res.data?.items) ? (res.data.items as PriceList[]) : [];
    },
    fallbackError: "بارگذاری فهرست قیمت ناموفق بود",
  });
  const lists: PriceList[] = listsData ?? [];

  const openModal = () => {
    setName("");
    setSegment("retail");
    setPriority("100");
    setRules([]);
    setIsModalOpen(true);
  };

  const updateRule = (idx: number, patch: Partial<RuleDraft>) => {
    setRules((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast({ title: "نام لیست قیمت الزامی است", variant: "destructive" });
      return;
    }
    setIsSubmitting(true);
    try {
      const payloadRules = rules
        .filter((r) => r.value.trim() !== "")
        .map((r) => {
          const numericValue = parseInt(r.value.replace(/\D/g, ""), 10) || 0;
          const base: Record<string, unknown> = {
            min_quantity: parseInt(r.min_quantity.replace(/\D/g, ""), 10) || 0,
          };
          if (r.product_id.trim()) base.product_id = r.product_id.trim();
          if (r.mode === "fixed") {
            base.fixed_price_rial = numericValue; // integer Rial
          } else {
            base.discount_bp = numericValue * 100; // whole % → basis points
          }
          return base;
        });

      await apiClient.post("/pricing/price-lists", {
        name: name.trim(),
        segment,
        priority: parseInt(priority, 10) || 100,
        is_active: true,
        rules: payloadRules,
      });

      toast({
        title: "لیست قیمت ایجاد شد",
        description: `لیست «${name}» با ${toPersianDigits(payloadRules.length)} قانون ثبت شد.`,
        variant: "success",
      });
      setIsModalOpen(false);
      await fetchLists();
    } catch (err: any) {
      toast({
        title: "خطا در ایجاد لیست قیمت",
        description: err?.response?.data?.detail || err?.message || "عملیات با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 p-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
            <Tag className="h-6 w-6 text-primary" />
            لیست‌های قیمت
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            قیمت‌گذاری چندسطحی بر اساس گروه مشتری (خرده، طلایی، عمده، سازمانی).
          </p>
        </div>
        <Button onClick={openModal} className="gap-2">
          <Plus className="h-4 w-4" />
          لیست قیمت جدید
        </Button>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
        </div>
      ) : lists.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 py-16 text-center">
          <Tag className="h-10 w-10 text-muted-foreground" />
          <p className="text-muted-foreground">هنوز لیست قیمتی ثبت نشده است.</p>
          <Button onClick={openModal} variant="outline" className="gap-2">
            <Plus className="h-4 w-4" />
            اولین لیست را بسازید
          </Button>
        </Card>
      ) : (
        <div className="grid gap-3">
          {lists.map((pl) => (
            <Card key={pl.id} className="flex items-center justify-between p-4">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                  <Tag className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">{pl.name}</p>
                  <p className="text-xs text-muted-foreground">
                    اولویت {toPersianDigits(pl.priority)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary">{segmentLabel(pl.segment)}</Badge>
                <Badge variant={pl.is_active ? "default" : "outline"}>
                  {pl.is_active ? "فعال" : "غیرفعال"}
                </Badge>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle>لیست قیمت جدید</DialogTitle>
            <DialogDescription>
              قوانین قیمت‌گذاری برای یک گروه مشتری را تعریف کنید.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>نام لیست</Label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="مثلاً: همکاران طلایی"
                />
              </div>
              <div className="space-y-1.5">
                <Label>گروه مشتری</Label>
                <Select value={segment} onValueChange={(v: Segment) => setSegment(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SEGMENTS.map((s) => (
                      <SelectItem key={s.value} value={s.value}>
                        {s.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>اولویت (کمتر = مهم‌تر)</Label>
                <Input
                  type="number"
                  inputMode="numeric"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                />
              </div>
            </div>

            {/* Rules */}
            <div className="space-y-2 border-t border-border pt-4">
              <div className="flex items-center justify-between">
                <Label>قوانین قیمت</Label>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-1"
                  onClick={() => setRules((prev) => [...prev, { ...EMPTY_RULE }])}
                >
                  <Plus className="h-3.5 w-3.5" />
                  افزودن قانون
                </Button>
              </div>
              {rules.length === 0 && (
                <p className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                  هیچ قانونی اضافه نشده؛ بدون قانون، لیست قیمت پایه اعمال می‌کند.
                </p>
              )}
              {rules.map((rule, idx) => (
                <div
                  key={idx}
                  className="grid grid-cols-12 items-end gap-2 rounded-lg border border-border p-3"
                >
                  <div className="col-span-12 sm:col-span-4">
                    <Label className="text-xs">شناسه محصول (خالی = کل کاتالوگ)</Label>
                    <Input
                      value={rule.product_id}
                      onChange={(e) => updateRule(idx, { product_id: e.target.value })}
                      placeholder="UUID محصول"
                      dir="ltr"
                    />
                  </div>
                  <div className="col-span-4 sm:col-span-2">
                    <Label className="text-xs">حداقل تعداد</Label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      value={rule.min_quantity}
                      onChange={(e) => updateRule(idx, { min_quantity: e.target.value })}
                    />
                  </div>
                  <div className="col-span-8 sm:col-span-3">
                    <Label className="text-xs">نوع</Label>
                    <Select
                      value={rule.mode}
                      onValueChange={(v: "fixed" | "percent") => updateRule(idx, { mode: v })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="percent">
                          <span className="flex items-center gap-1">
                            <Percent className="h-3 w-3" /> درصد تخفیف
                          </span>
                        </SelectItem>
                        <SelectItem value="fixed">
                          <span className="flex items-center gap-1">
                            <DollarSign className="h-3 w-3" /> قیمت ثابت (ریال)
                          </span>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="col-span-10 sm:col-span-2">
                    <Label className="text-xs">
                      {rule.mode === "percent" ? "درصد" : "ریال"}
                    </Label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      value={rule.value}
                      onChange={(e) => updateRule(idx, { value: e.target.value })}
                    />
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-destructive"
                      onClick={() => setRules((prev) => prev.filter((_, i) => i !== idx))}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" onClick={() => setIsModalOpen(false)}>
                انصراف
              </Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? "در حال ذخیره..." : "ایجاد لیست قیمت"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
