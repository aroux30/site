"use client";

import { useState } from "react";
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
import {
  MissingDataNotice,
  PartialDataNotice,
} from "@/components/admin/async-state";
import apiClient from "@/lib/api/client";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { formatRial, toPersianDigits } from "@/lib/utils";
import {
  REWARD_TYPES,
  REWARD_TYPE_LABELS,
  createReward,
  createRule,
  fetchRewards,
  fetchRules,
  rewardTypeLabel,
  updateReward,
  updateRule,
  type GamificationReward,
  type GamificationRule,
} from "@/lib/api/gamification-admin";

const GAMIFICATION_QUERY_KEY = "admin-gamification" as const;
const RULES_QUERY_KEY = "admin-gamification-rules" as const;
const REWARDS_QUERY_KEY = "admin-gamification-rewards" as const;

interface ChargePackage {
  id: string;
  title: string;
  pay_amount: number;
  credit_amount: number;
  is_active: boolean;
  ordering: number;
}

export default function AdminGamificationPage() {
  const { toast } = useToast();
  const [giftCode, setGiftCode] = useState<string | null>(null);

  // Create gift card dialog
  const [giftOpen, setGiftOpen] = useState(false);
  const [giftAmount, setGiftAmount] = useState("500000");
  const [giftTemplate, setGiftTemplate] = useState("gold");
  const [creating, setCreating] = useState(false);

  // Create charge-package dialog. The list endpoint was already wired to this
  // page but the matching admin create endpoint (`POST
  // /gamification/gifts/admin/charge-packages`) had no caller anywhere, so
  // packages could be displayed and never defined from the panel.
  const [packageOpen, setPackageOpen] = useState(false);
  const [packageTitle, setPackageTitle] = useState("");
  const [packagePay, setPackagePay] = useState("");
  const [packageCredit, setPackageCredit] = useState("");
  const [packageOrdering, setPackageOrdering] = useState("0");
  const [creatingPackage, setCreatingPackage] = useState(false);
  const [packageError, setPackageError] = useState<string | null>(null);

  // Point-rule dialog
  const [ruleDialogOpen, setRuleDialogOpen] = useState(false);
  const [ruleName, setRuleName] = useState("");
  const [ruleEventType, setRuleEventType] = useState("");
  const [rulePoints, setRulePoints] = useState("");
  const [ruleActive, setRuleActive] = useState(true);
  const [savingRule, setSavingRule] = useState(false);
  const [ruleError, setRuleError] = useState<string | null>(null);

  // Reward dialog
  const [rewardDialogOpen, setRewardDialogOpen] = useState(false);
  const [rewardName, setRewardName] = useState("");
  const [rewardDescription, setRewardDescription] = useState("");
  const [rewardType, setRewardType] = useState("discount");
  const [rewardPoints, setRewardPoints] = useState("");
  const [rewardQuantity, setRewardQuantity] = useState("");
  const [rewardActive, setRewardActive] = useState(true);
  const [savingReward, setSavingReward] = useState(false);
  const [rewardError, setRewardError] = useState<string | null>(null);

  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery<ChargePackage[]>({
    queryKey: [GAMIFICATION_QUERY_KEY],
    queryFn: async () => {
      const pkgRes = await apiClient.get("/gamification/gifts/charge-packages");
      return Array.isArray(pkgRes.data) ? pkgRes.data : [];
    },
    fallbackError: "بارگذاری اطلاعات باشگاه مشتریان با خطا مواجه شد",
    // The old load reported failures with a toast and left the tab empty.
    toastOnError: true,
  });
  const packages: ChargePackage[] = data ?? [];
  const runMutation = useAdminMutation();

  // ── Point rules and rewards ──
  // These load only while their tab is open, so a closed tab costs nothing.
  const [rulesEnabled, setRulesEnabled] = useState(false);
  const [rewardsEnabled, setRewardsEnabled] = useState(false);

  const rulesQuery = useAdminQuery({
    queryKey: [RULES_QUERY_KEY],
    queryFn: () => fetchRules(),
    fallbackError: "دریافت قواعد امتیازدهی ناموفق بود",
    enabled: rulesEnabled,
  });
  const rewardsQuery = useAdminQuery({
    queryKey: [REWARDS_QUERY_KEY],
    queryFn: () => fetchRewards(),
    fallbackError: "دریافت جوایز ناموفق بود",
    enabled: rewardsEnabled,
  });
  const rules: GamificationRule[] = rulesQuery.data?.items ?? [];
  const rewards: GamificationReward[] = rewardsQuery.data?.items ?? [];

  const createPointRule = async () => {
    setRuleError(null);
    const points = Number.parseInt(rulePoints.replace(/[^\d]/g, ""), 10);
    if (!ruleName.trim()) {
      setRuleError("نام قاعده الزامی است.");
      return;
    }
    if (!ruleEventType.trim()) {
      setRuleError("نوع رویداد الزامی است؛ قاعده بر پایه آن ارزیابی می‌شود.");
      return;
    }
    // Points are a positive integer by contract (gt=0). Zero would create a
    // rule that matches events and awards nothing.
    if (!Number.isFinite(points) || points <= 0) {
      setRuleError("امتیاز باید یک عدد صحیح بزرگ‌تر از صفر باشد.");
      return;
    }
    setSavingRule(true);
    const result = await runMutation(
      () =>
        createRule({
          name: ruleName.trim(),
          eventType: ruleEventType.trim(),
          points,
          isActive: ruleActive,
        }),
      {
        fallbackError: "ایجاد قاعده امتیازدهی ناموفق بود",
        invalidateKeys: [[RULES_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "موفق", description: "قاعده امتیازدهی ایجاد شد" });
          setRuleDialogOpen(false);
          setRuleName("");
          setRuleEventType("");
          setRulePoints("");
        },
      },
    );
    if (!result.ok) setRuleError(result.error);
    setSavingRule(false);
  };

  const toggleRule = async (rule: GamificationRule) => {
    const result = await runMutation(() => updateRule(rule.id, { isActive: !rule.isActive }), {
      fallbackError: "تغییر وضعیت قاعده ناموفق بود",
      invalidateKeys: [[RULES_QUERY_KEY]],
    });
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const createNewReward = async () => {
    setRewardError(null);
    const pointsRequired = Number.parseInt(rewardPoints.replace(/[^\d]/g, ""), 10);
    const quantity = rewardQuantity.trim()
      ? Number.parseInt(rewardQuantity.replace(/[^\d]/g, ""), 10)
      : null;

    if (!rewardName.trim()) {
      setRewardError("نام جایزه الزامی است.");
      return;
    }
    if (!Number.isFinite(pointsRequired) || pointsRequired <= 0) {
      setRewardError("امتیاز لازم باید یک عدد صحیح بزرگ‌تر از صفر باشد.");
      return;
    }
    if (quantity !== null && (!Number.isFinite(quantity) || quantity < 0)) {
      setRewardError("تعداد موجود باید عددی نامنفی باشد یا خالی بماند (بدون محدودیت).");
      return;
    }
    setSavingReward(true);
    const result = await runMutation(
      () =>
        createReward({
          name: rewardName.trim(),
          description: rewardDescription.trim() || null,
          type: rewardType,
          pointsRequired,
          isActive: rewardActive,
          quantityAvailable: quantity,
        }),
      {
        fallbackError: "ایجاد جایزه ناموفق بود",
        invalidateKeys: [[REWARDS_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "موفق", description: "جایزه ایجاد شد" });
          setRewardDialogOpen(false);
          setRewardName("");
          setRewardDescription("");
          setRewardPoints("");
          setRewardQuantity("");
        },
      },
    );
    if (!result.ok) setRewardError(result.error);
    setSavingReward(false);
  };

  const toggleReward = async (reward: GamificationReward) => {
    const result = await runMutation(
      () => updateReward(reward.id, { isActive: !reward.isActive }),
      {
        fallbackError: "تغییر وضعیت جایزه ناموفق بود",
        invalidateKeys: [[REWARDS_QUERY_KEY]],
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const createChargePackage = async () => {
    setPackageError(null);

    const pay = Number.parseInt(packagePay.replace(/[^\d]/g, ""), 10);
    const credit = Number.parseInt(packageCredit.replace(/[^\d]/g, ""), 10);
    const ordering = Number.parseInt(packageOrdering || "0", 10) || 0;

    if (!packageTitle.trim()) {
      setPackageError("عنوان بسته الزامی است.");
      return;
    }
    // The backend requires at least 10,000 IRR on both sides. Refusing here
    // saves a round trip and states the rule in the operator's own language.
    if (!Number.isFinite(pay) || pay < 10_000) {
      setPackageError("مبلغ پرداختی باید حداقل ۱۰٬۰۰۰ ریال باشد.");
      return;
    }
    if (!Number.isFinite(credit) || credit < 10_000) {
      setPackageError("اعتبار بسته باید حداقل ۱۰٬۰۰۰ ریال باشد.");
      return;
    }
    // A package whose credit is below what the customer pays is not a bonus;
    // it is a surcharge, almost certainly a data-entry mistake.
    if (credit < pay) {
      setPackageError(
        "اعتبار بسته نباید کمتر از مبلغ پرداختی باشد؛ در غیر این صورت مشتری کمتر از مبلغ پرداختی دریافت می‌کند.",
      );
      return;
    }

    setCreatingPackage(true);
    const result = await runMutation(
      () =>
        apiClient.post("/gamification/gifts/admin/charge-packages", {
          title: packageTitle.trim(),
          pay_amount: pay,
          credit_amount: credit,
          ordering,
        }),
      {
        fallbackError: "ایجاد بسته شارژ با خطا مواجه شد",
        // The packages list is what this page renders, so it must refresh.
        invalidateKeys: [[GAMIFICATION_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "موفق", description: "بسته شارژ تشویقی ایجاد شد" });
          setPackageOpen(false);
          setPackageTitle("");
          setPackagePay("");
          setPackageCredit("");
          setPackageOrdering("0");
        },
      },
    );
    if (!result.ok) {
      setPackageError(result.error);
    }
    setCreatingPackage(false);
  };

  const issueGiftCard = async () => {
    setCreating(true);
    const result = await runMutation(
      () =>
        apiClient.post("/gamification/gifts/cards/issue", {
          amount: parseInt(giftAmount),
          card_template: giftTemplate,
        }),
      {
        fallbackError: "صدور کارت هدیه با خطا مواجه شد",
        // Issuing a card changes no list this page shows, so the old handler
        // did not reload; no key is invalidated here either.
        onSuccess: (res) => {
          setGiftCode(res.data.code);
          toast({ title: "موفق", description: `کارت هدیه ${res.data.code} صادر شد` });
          setGiftOpen(false);
        },
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setCreating(false);
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
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setGiftOpen(true)}>
            <Plus className="h-4 w-4 ms-2" />
            صدور کارت هدیه
          </Button>
        </div>
      </div>

      <Tabs
        defaultValue="packages"
        dir="rtl"
        // Each tab fetches on first open; the queries stay cached afterwards.
        onValueChange={(value) => {
          if (value === "rules") setRulesEnabled(true);
          if (value === "prizes") setRewardsEnabled(true);
        }}
      >
        <TabsList>
          <TabsTrigger value="packages">بسته‌های شارژ</TabsTrigger>
          <TabsTrigger value="rules">قواعد امتیازدهی</TabsTrigger>
          <TabsTrigger value="prizes">جوایز و گردونه شانس</TabsTrigger>
        </TabsList>

        <TabsContent value="packages">
          <div className="mb-4 flex justify-end">
            <Button size="sm" onClick={() => setPackageOpen(true)}>
              <Plus className="h-4 w-4 ms-2" />
              بسته شارژ جدید
            </Button>
          </div>
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

        <TabsContent value="rules" className="space-y-4">
          <div className="flex flex-wrap justify-end gap-2">
            <Button size="sm" onClick={() => setRuleDialogOpen(true)}>
              <Plus className="h-4 w-4 ms-2" />
              قاعده جدید
            </Button>
          </div>

          <PartialDataNotice
            count={rulesQuery.data?.invalidCount ?? 0}
            label="قواعد بازگشتی"
          />

          {rulesQuery.error ? (
            <Card className="p-8 text-center text-sm text-destructive">
              {rulesQuery.error}
            </Card>
          ) : rulesQuery.loading ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">
              در حال دریافت قواعد...
            </Card>
          ) : rules.length === 0 ? (
            <Card className="p-12 text-center">
              <Dices className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm text-muted-foreground">
                قاعده امتیازدهی‌ای تعریف نشده است
              </p>
              <p className="mt-1 text-[11px] text-muted-foreground">
                بدون قاعده، هیچ رویدادی امتیاز نمی‌دهد و مشتری امتیازی برای
                خرج‌کردن در جوایز نخواهد داشت.
              </p>
            </Card>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-right text-sm">
                <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-4 py-3">نام قاعده</th>
                    <th scope="col" className="px-4 py-3">رویداد</th>
                    <th scope="col" className="px-4 py-3">امتیاز</th>
                    <th scope="col" className="px-4 py-3">وضعیت</th>
                    <th scope="col" className="px-4 py-3"> </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {rules.map((rule) => (
                    <tr key={rule.id}>
                      <td className="px-4 py-3 font-medium text-foreground">
                        {rule.name}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs" dir="ltr">
                        {rule.eventType || "—"}
                      </td>
                      <td className="px-4 py-3 font-mono">
                        {rule.points === null
                          ? "—"
                          : toPersianDigits(String(rule.points))}
                      </td>
                      <td className="px-4 py-3">
                        {rule.isActive ? (
                          <Badge variant="success">فعال</Badge>
                        ) : (
                          <Badge variant="outline">غیرفعال</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void toggleRule(rule)}
                        >
                          {rule.isActive ? "غیرفعال" : "فعال"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>

        <TabsContent value="prizes" className="space-y-4">
          <div className="flex flex-wrap justify-end gap-2">
            <Button size="sm" variant="outline" onClick={() => setRewardDialogOpen(true)}>
              <Plus className="h-4 w-4 ms-2" />
              جایزه جدید
            </Button>
          </div>

          <PartialDataNotice
            count={rewardsQuery.data?.invalidCount ?? 0}
            label="جوایز بازگشتی"
          />

          {rewardsQuery.error ? (
            <Card className="p-8 text-center text-sm text-destructive">
              {rewardsQuery.error}
            </Card>
          ) : rewardsQuery.loading ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">
              در حال دریافت جوایز...
            </Card>
          ) : rewards.length === 0 ? (
            <Card className="p-12 text-center">
              <Dices className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm text-muted-foreground">
                جایزه فعالی تعریف نشده است
              </p>
            </Card>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-right text-sm">
                <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-4 py-3">نام جایزه</th>
                    <th scope="col" className="px-4 py-3">نوع</th>
                    <th scope="col" className="px-4 py-3">امتیاز لازم</th>
                    <th scope="col" className="px-4 py-3">موجودی</th>
                    <th scope="col" className="px-4 py-3">وضعیت</th>
                    <th scope="col" className="px-4 py-3"> </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {rewards.map((reward) => (
                    <tr key={reward.id}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-foreground">{reward.name}</div>
                        {reward.description && (
                          <div className="text-[11px] text-muted-foreground">
                            {reward.description}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="secondary">{rewardTypeLabel(reward.type)}</Badge>
                      </td>
                      <td className="px-4 py-3 font-mono">
                        {reward.pointsRequired === null
                          ? "—"
                          : toPersianDigits(String(reward.pointsRequired))}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs">
                        {reward.quantityAvailable === null
                          ? "بدون محدودیت"
                          : toPersianDigits(String(reward.quantityAvailable))}
                      </td>
                      <td className="px-4 py-3">
                        {reward.isActive ? (
                          <Badge variant="success">فعال</Badge>
                        ) : (
                          <Badge variant="outline">غیرفعال</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void toggleReward(reward)}
                        >
                          {reward.isActive ? "غیرفعال" : "فعال"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Create Point Rule Dialog */}
      <Dialog open={ruleDialogOpen} onOpenChange={setRuleDialogOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>قاعده امتیازدهی جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-[11px] leading-5 text-muted-foreground">
              قاعده وقتی رویدادی از نوع مشخص‌شده رخ دهد، امتیاز اعطا می‌کند.
              «نوع رویداد» باید دقیقاً با شناسه رویدادی که سرور منتشر می‌کند
              مطابقت داشته باشد، وگرنه قاعده هرگز اجرا نمی‌شود.
            </p>
            <div className="space-y-2">
              <Label htmlFor="rule-name">نام</Label>
              <Input
                id="rule-name"
                value={ruleName}
                onChange={(e) => setRuleName(e.target.value)}
                placeholder="مثلاً امتیاز تکمیل سفارش"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rule-event">نوع رویداد</Label>
              <Input
                id="rule-event"
                value={ruleEventType}
                onChange={(e) => setRuleEventType(e.target.value)}
                placeholder="order_completed"
                dir="ltr"
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="rule-points">امتیاز</Label>
              <Input
                id="rule-points"
                type="number"
                min="1"
                value={rulePoints}
                onChange={(e) => setRulePoints(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={ruleActive}
                onChange={(e) => setRuleActive(e.target.checked)}
              />
              فعال
            </label>
          </div>
          {ruleError && (
            <p role="alert" className="text-sm text-destructive">
              {ruleError}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRuleDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void createPointRule()} disabled={savingRule}>
              {savingRule ? "در حال ایجاد..." : "ایجاد قاعده"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Reward Dialog */}
      <Dialog open={rewardDialogOpen} onOpenChange={setRewardDialogOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>جایزه جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="reward-name">نام</Label>
              <Input
                id="reward-name"
                value={rewardName}
                onChange={(e) => setRewardName(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reward-desc">توضیح (اختیاری)</Label>
              <Input
                id="reward-desc"
                value={rewardDescription}
                onChange={(e) => setRewardDescription(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reward-type">نوع</Label>
              <select
                id="reward-type"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={rewardType}
                onChange={(e) => setRewardType(e.target.value)}
              >
                {REWARD_TYPES.map((t) => (
                  <option key={t} value={t}>
                    {REWARD_TYPE_LABELS[t] ?? t}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="reward-points">امتیاز لازم</Label>
              <Input
                id="reward-points"
                type="number"
                min="1"
                value={rewardPoints}
                onChange={(e) => setRewardPoints(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="reward-qty">تعداد موجود (خالی = بدون محدودیت)</Label>
              <Input
                id="reward-qty"
                type="number"
                min="0"
                value={rewardQuantity}
                onChange={(e) => setRewardQuantity(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
            </div>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={rewardActive}
                onChange={(e) => setRewardActive(e.target.checked)}
              />
              فعال
            </label>
          </div>
          {rewardError && (
            <p role="alert" className="text-sm text-destructive">
              {rewardError}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRewardDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void createNewReward()} disabled={savingReward}>
              {savingReward ? "در حال ایجاد..." : "ایجاد جایزه"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create Charge Package Dialog */}
      <Dialog open={packageOpen} onOpenChange={setPackageOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>بسته شارژ تشویقی جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-[11px] leading-5 text-muted-foreground">
              مشتری مبلغ پرداختی را می‌پردازد و اعتبار بیشتری دریافت می‌کند. مبالغ
              به ریال صحیح ثبت می‌شوند و اختلاف دو عدد، بونوس مشتری است.
            </p>
            <div className="space-y-2">
              <Label htmlFor="pkg-title">عنوان</Label>
              <Input
                id="pkg-title"
                value={packageTitle}
                onChange={(e) => setPackageTitle(e.target.value)}
                placeholder="مثلاً بسته طلایی"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pkg-pay">مبلغ پرداختی (ریال)</Label>
              <Input
                id="pkg-pay"
                type="number"
                value={packagePay}
                onChange={(e) => setPackagePay(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="pkg-credit">اعتبار اعطایی (ریال)</Label>
              <Input
                id="pkg-credit"
                type="number"
                value={packageCredit}
                onChange={(e) => setPackageCredit(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
              {packagePay && packageCredit &&
                Number(packageCredit) >= Number(packagePay) && (
                  <p className="text-[11px] text-emerald-700 dark:text-emerald-400">
                    بونوس: {formatRial(Number(packageCredit) - Number(packagePay))}
                  </p>
                )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="pkg-order">ترتیب نمایش</Label>
              <Input
                id="pkg-order"
                type="number"
                value={packageOrdering}
                onChange={(e) => setPackageOrdering(e.target.value)}
                dir="ltr"
              />
            </div>
          </div>
          {packageError && (
            <p role="alert" className="text-sm text-destructive">
              {packageError}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setPackageOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void createChargePackage()} disabled={creatingPackage}>
              {creatingPackage ? "در حال ایجاد..." : "ایجاد بسته"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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
