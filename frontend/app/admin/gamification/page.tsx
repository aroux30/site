"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Gift, RefreshCw, Ticket, Dices, Wallet, Plus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";

interface ChargePackage {
  id: string;
  title: string;
  pay_amount: number;
  credit_amount: number;
  is_active: boolean;
  ordering: number;
}

interface LuckyWheelPrize {
  id: string;
  title: string;
  prize_type: string;
  value: number;
  probability_weight: number;
  is_active: boolean;
  claimed_count: number;
}

export default function AdminGamificationPage() {
  const { toast } = useToast();
  const [packages, setPackages] = useState<ChargePackage[]>([]);
  const [prizes, setPrizes] = useState<LuckyWheelPrize[]>([]);
  const [loading, setLoading] = useState(true);
  const [giftCode, setGiftCode] = useState<string | null>(null);

  // Create gift card dialog
  const [giftOpen, setGiftOpen] = useState(false);
  const [giftAmount, setGiftAmount] = useState("500000");
  const [giftTemplate, setGiftTemplate] = useState("gold");
  const [creating, setCreating] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const pkgRes = await apiClient.get("/gamification/gifts/charge-packages");
      setPackages(Array.isArray(pkgRes.data) ? pkgRes.data : []);
    } catch {
      toast({ title: "خطا", description: "بارگذاری اطلاعات باشگاه مشتریان با خطا مواجه شد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const issueGiftCard = async () => {
    setCreating(true);
    try {
      const res = await apiClient.post("/gamification/gifts/cards/issue", {
        amount: parseInt(giftAmount),
        card_template: giftTemplate,
      });
      setGiftCode(res.data.code);
      toast({ title: "موفق", description: `کارت هدیه ${res.data.code} صادر شد` });
      setGiftOpen(false);
    } catch {
      toast({ title: "خطا", description: "صدور کارت هدیه با خطا مواجه شد", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Gift className="h-5 w-5 text-primary" />
            باشگاه مشتریان و گیمیفیکیشن
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            صدور کارت هدیه، جوایز گردونه شانس و بسته‌های شارژ تشویقی
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setGiftOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            صدور کارت هدیه
          </Button>
        </div>
      </div>

      <Tabs defaultValue="packages" dir="rtl">
        <TabsList>
          <TabsTrigger value="packages">بسته‌های شارژ</TabsTrigger>
          <TabsTrigger value="prizes">جوایز گردونه شانس</TabsTrigger>
        </TabsList>

        <TabsContent value="packages">
          {loading ? (
            <div className="flex items-center justify-center p-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : packages.length === 0 ? (
            <Card className="p-12 text-center">
              <Wallet className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm text-muted-foreground">هیچ بسته شارژی تعریف نشده است</p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {packages.map((p) => (
                <Card key={p.id} className="p-5">
                  <h4 className="font-semibold">{p.title}</h4>
                  <p className="text-sm text-muted-foreground mt-1">
                    پرداخت: <span className="font-medium">{p.pay_amount.toLocaleString("fa-IR")}</span> ریال
                  </p>
                  <p className="text-sm text-muted-foreground">
                    اعتبار: <span className="font-medium text-emerald-600">{p.credit_amount.toLocaleString("fa-IR")}</span> ریال
                  </p>
                  <Badge className="mt-2 bg-emerald-500/10 text-emerald-500">
                    بونوس: {(p.credit_amount - p.pay_amount).toLocaleString("fa-IR")} ریال
                  </Badge>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="prizes">
          <Card className="p-12 text-center">
            <Dices className="h-12 w-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm text-muted-foreground">
              جوایز گردونه شانس از پنل ادمین قابل مدیریت است
            </p>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Issue Gift Card Dialog */}
      <Dialog open={giftOpen} onOpenChange={setGiftOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>صدور کارت هدیه دیجیتال</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>مبلغ (ریال)</Label>
              <Input type="number" value={giftAmount} onChange={(e) => setGiftAmount(e.target.value)} dir="ltr" />
            </div>
            <div className="space-y-2">
              <Label>قالب گرافیکی</Label>
              <select
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={giftTemplate}
                onChange={(e) => setGiftTemplate(e.target.value)}
              >
                <option value="gold">طلایی</option>
                <option value="birthday">تولد</option>
                <option value="festive">مناسبت</option>
                <option value="vip">VIP</option>
              </select>
            </div>
          </div>
          {giftCode && (
            <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 text-center">
              <p className="text-xs text-muted-foreground">کد کارت هدیه:</p>
              <p className="font-mono text-lg font-bold text-emerald-600" dir="ltr">{giftCode}</p>
            </div>
          )}
          <DialogFooter>
            {!giftCode ? (
              <>
                <Button variant="outline" onClick={() => setGiftOpen(false)}>انصراف</Button>
                <Button onClick={issueGiftCard} disabled={creating}>
                  {creating ? "در حال صدور..." : "صدور"}
                </Button>
              </>
            ) : (
              <Button onClick={() => { setGiftCode(null); setGiftOpen(false); }}>بستن</Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
