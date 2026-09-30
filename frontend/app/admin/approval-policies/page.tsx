"use client";

import React, { useState } from "react";
import {
  ShieldCheck,
  RefreshCw,
  Plus,
  Trash2,
  Pencil,
  ArrowLeft,
  GitBranch,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  approvalPoliciesApi,
  type ApprovalPolicy,
  type ApprovalPolicyPayload,
  type ApprovalPolicyStepDef,
} from "@/lib/api/approval-policies";
import { toPersianDigits, formatPrice, toEnglishDigits } from "@/lib/utils";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const APPROVAL_POLICIES_QUERY_KEY = "admin-approval-policies" as const;

const RESOURCE_LABELS: Record<string, string> = {
  refund: "بازپرداخت",
  wallet_withdrawal: "برداشت از کیف پول",
  vendor_settlement: "تسویه فروشنده",
  product_price: "تغییر قیمت محصول",
  "*": "همه جریان‌ها",
};

function resourceLabel(resource: string): string {
  return RESOURCE_LABELS[resource] ?? resource;
}

type FormState = {
  id: string | null;
  resource: string;
  min_amount_toman: string;
  steps: ApprovalPolicyStepDef[];
  priority: string;
  description: string;
  is_active: boolean;
};

const EMPTY_FORM: FormState = {
  id: null,
  resource: "refund",
  min_amount_toman: "",
  steps: [{ role: null, label: "" }],
  priority: "0",
  description: "",
  is_active: true,
};

export default function ApprovalPoliciesPage() {
  const { toast } = useToast();
  const [saving, setSaving] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);

  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [APPROVAL_POLICIES_QUERY_KEY],
    queryFn: () => approvalPoliciesApi.list({ active_only: false }),
    fallbackError: "خطا در دریافت پالیسی‌ها",
    toastOnError: true,
    toastDescription: "دسترسی approvals:review لازم است.",
  });
  const policies: ApprovalPolicy[] = data ?? [];
  const runMutation = useAdminMutation();

  const openCreate = () => {
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = (policy: ApprovalPolicy) => {
    setForm({
      id: policy.id,
      resource: policy.resource,
      // Display in Toman (the operator-facing unit); the API takes Rials.
      min_amount_toman: policy.min_amount_rial
        ? String(Math.round(policy.min_amount_rial / 10))
        : "",
      steps:
        policy.steps.length > 0
          ? policy.steps.map((s) => ({
              // `required_role` is absent on steps that accept any approver;
              // the form models that as an explicit null, not undefined.
              role: s.required_role ?? null,
              label: s.label ?? "",
            }))
          : [{ role: null, label: "" }],
      priority: String(policy.priority),
      description: policy.description ?? "",
      is_active: policy.is_active,
    });
    setDialogOpen(true);
  };

  const save = async () => {
    const minToman = form.min_amount_toman.trim()
      ? Number(toEnglishDigits(form.min_amount_toman.replace(/,/g, "")))
      : null;
    if (minToman !== null && (Number.isNaN(minToman) || minToman < 0)) {
      toast({ title: "مبلغ آستانه نامعتبر است", variant: "destructive" });
      return;
    }
    const steps = form.steps
      .map((s) => ({ role: s.role || null, label: (s.label || "").trim() || null }))
      .filter((s) => s.label || s.role);
    if (steps.length === 0) {
      toast({ title: "حداقل یک مرحله تایید لازم است", variant: "destructive" });
      return;
    }

    const payload: ApprovalPolicyPayload = {
      resource: form.resource.trim(),
      min_amount_rial: minToman === null ? null : minToman * 10,
      max_amount_rial: null,
      steps,
      priority: Number(toEnglishDigits(form.priority)) || 0,
      is_active: form.is_active,
      description: form.description.trim() || null,
    };

    setSaving(true);
    try {
      if (form.id) {
        await approvalPoliciesApi.update(form.id, payload);
        toast({ title: "پالیسی بروزرسانی شد", variant: "success" });
      } else {
        await approvalPoliciesApi.create(payload);
        toast({ title: "پالیسی ایجاد شد", variant: "success" });
      }
      setDialogOpen(false);
      await load();
    } catch {
      toast({ title: "ذخیره پالیسی ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (policy: ApprovalPolicy) => {
    try {
      await approvalPoliciesApi.deactivate(policy.id);
      toast({ title: "پالیسی غیرفعال شد", variant: "success" });
      await load();
    } catch {
      toast({ title: "غیرفعال‌سازی ناموفق بود", variant: "destructive" });
    }
  };

  const updateStep = (index: number, patch: Partial<ApprovalPolicyStepDef>) => {
    setForm((f) => ({
      ...f,
      steps: f.steps.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    }));
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <GitBranch className="h-5 w-5 text-primary" />
            زنجیره‌های تایید و پالیسی‌های مالی
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            تعیین می‌کند هر جریان مالی (بازپرداخت، برداشت کیف پول، تسویه
            فروشنده) بر اساس مبلغ، به چند امضا و از چه نقشی نیاز دارد.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="ms-2 h-4 w-4" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="ms-2 h-4 w-4" />
            پالیسی جدید
          </Button>
        </div>
      </div>

      <Card className="border-amber-500/30 bg-amber-500/5 p-4">
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <p>
            زنجیره هر درخواست در لحظه ثبت «قفل» می‌شود؛ ویرایش پالیسی، درخواست‌های
            در جریان را تغییر نمی‌دهد. مبالغ به <strong>تومان</strong> وارد
            می‌شوند و درخواست‌های بدون مبلغ فقط با پالیسی‌های بدون آستانه مطابقت
            می‌کنند.
          </p>
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : policies.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          پالیسی‌ای تعریف نشده است. بدون پالیسی، همه درخواست‌ها تک‌مرحله‌ای
          باقی می‌مانند.
        </Card>
      ) : (
        <div className="space-y-3">
          {policies.map((policy) => (
            <Card key={policy.id} className={`p-4 ${policy.is_active ? "" : "opacity-60"}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={policy.is_active ? "default" : "outline"}>
                      {resourceLabel(policy.resource)}
                    </Badge>
                    <span className="text-sm font-medium">
                      {policy.min_amount_rial
                        ? `از ${formatPrice(Math.trunc(policy.min_amount_rial / 10))} به بالا`
                        : "بدون آستانه مبلغ"}
                    </span>
                    {!policy.is_active && (
                      <Badge variant="secondary">غیرفعال</Badge>
                    )}
                  </div>
                  {policy.description && (
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      {policy.description}
                    </p>
                  )}
                  {/* Chain visual */}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <span className="text-[11px] text-muted-foreground">
                      زنجیره تایید:
                    </span>
                    {policy.steps.map((step, idx) => (
                      <React.Fragment key={idx}>
                        <span className="rounded-full bg-muted px-3 py-1 text-xs">
                          {step.label ?? `مرحله ${toPersianDigits(String(idx + 1))}`}
                          {step.required_role && (
                            <span className="ms-1 font-mono text-[10px] text-muted-foreground" dir="ltr">
                              ({step.required_role})
                            </span>
                          )}
                        </span>
                        {idx < policy.steps.length - 1 && (
                          <ArrowLeft className="h-3.5 w-3.5 text-muted-foreground" />
                        )}
                      </React.Fragment>
                    ))}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEdit(policy)}>
                    <Pencil className="ms-1.5 h-3.5 w-3.5" />
                    ویرایش
                  </Button>
                  {policy.is_active && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      onClick={() => deactivate(policy)}
                    >
                      <Trash2 className="ms-1.5 h-3.5 w-3.5" />
                      غیرفعال
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create / edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>
              {form.id ? "ویرایش پالیسی تایید" : "پالیسی تایید جدید"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="policy-resource">جریان مالی</Label>
                <select
                  id="policy-resource"
                  value={form.resource}
                  onChange={(e) => setForm((f) => ({ ...f, resource: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="refund">بازپرداخت</option>
                  <option value="wallet_withdrawal">برداشت از کیف پول</option>
                  <option value="vendor_settlement">تسویه فروشنده</option>
                  <option value="product_price">تغییر قیمت محصول</option>
                  <option value="*">همه جریان‌ها</option>
                </select>
              </div>
              <div>
                <Label htmlFor="policy-min">آستانه مبلغ (تومان)</Label>
                <Input
                  id="policy-min"
                  value={form.min_amount_toman}
                  onChange={(e) => setForm((f) => ({ ...f, min_amount_toman: e.target.value }))}
                  placeholder="مثلاً ۵۰۰۰۰۰۰ — خالی = بدون آستانه"
                  dir="ltr"
                  className="mt-1"
                />
              </div>
            </div>

            <div>
              <Label>زنجیره تایید (به ترتیب)</Label>
              <div className="mt-2 space-y-2">
                {form.steps.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <span className="w-6 shrink-0 text-center text-xs text-muted-foreground">
                      {toPersianDigits(String(idx + 1))}
                    </span>
                    <Input
                      value={step.label ?? ""}
                      onChange={(e) => updateStep(idx, { label: e.target.value })}
                      placeholder="عنوان مرحله (مثلاً تایید مالی)"
                      className="flex-1"
                    />
                    <Input
                      value={step.role ?? ""}
                      onChange={(e) => updateStep(idx, { role: e.target.value || null })}
                      placeholder="نقش (اختیاری)"
                      dir="ltr"
                      className="w-36"
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      disabled={form.steps.length <= 1}
                      onClick={() =>
                        setForm((f) => ({
                          ...f,
                          steps: f.steps.filter((_, i) => i !== idx),
                        }))
                      }
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="mt-2"
                onClick={() =>
                  setForm((f) => ({ ...f, steps: [...f.steps, { role: null, label: "" }] }))
                }
              >
                <Plus className="ms-1.5 h-3.5 w-3.5" />
                افزودن مرحله
              </Button>
            </div>

            <div>
              <Label htmlFor="policy-desc">توضیح (اختیاری)</Label>
              <Input
                id="policy-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                className="mt-1"
              />
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(e) => setForm((f) => ({ ...f, is_active: e.target.checked }))}
                className="h-4 w-4"
              />
              فعال باشد
            </label>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={save} disabled={saving}>
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
