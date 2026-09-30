"use client";

import React, { useState } from "react";
import {
  Zap,
  Plus,
  RefreshCw,
  Trash2,
  Pencil,
  Play,
  ShieldCheck,
  Clock,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  ACTION_LABELS,
  ACTION_PARAM_HINTS,
  automationApi,
  OPERATOR_LABELS,
  TRIGGER_LABELS,
  type AutomationActionType,
  type AutomationRule,
  type AutomationRuleCreate,
  type AutomationTriggerType,
  type ConditionOperator,
  type RuleAction,
  type RuleCondition,
  type RuleTestResult,
} from "@/lib/api/automation";
import { toPersianDigits } from "@/lib/utils";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const AUTOMATION_QUERY_KEY = "admin-automation-rules" as const;

const TRIGGERS = Object.keys(TRIGGER_LABELS) as AutomationTriggerType[];
const OPERATORS = Object.keys(OPERATOR_LABELS) as ConditionOperator[];
const ACTION_TYPES = Object.keys(ACTION_LABELS) as AutomationActionType[];

/**
 * Editor for one action's `params` object.
 *
 * The raw text is held separately from the parsed value. Parsing on every
 * keystroke would make a half-typed `{` reset the field and make the caret
 * jump, and parsing on blur alone would let a syntax error sit unnoticed until
 * save. So: keep the text, surface the error as you type, and hand the parent
 * a value only when the text is valid JSON — an invalid box is blocked at save
 * rather than sent as a string where the schema would reject it.
 *
 * One callback, not two: the parent needs the parsed value *and* whether the
 * box was valid at the moment it was produced, and splitting them into
 * separate props lets a caller hold a valid `params` next to a validity flag
 * from a later keystroke — the two then disagree and the save uses the stale one.
 */
/** Reported on every keystroke: the parsed object (or the last good one) and validity. */
type ParamsEditHandler = (params: Record<string, unknown>, valid: boolean) => void;

function ActionParamsEditor({
  value,
  onEdit,
}: {
  value: Record<string, unknown>;
  onEdit: ParamsEditHandler;
}) {
  const [text, setText] = useState(() => JSON.stringify(value, null, 2));
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="space-y-1">
      <Textarea
        dir="ltr"
        rows={4}
        className="font-mono text-xs"
        value={text}
        onChange={(e) => {
          const next = e.target.value;
          setText(next);
          try {
            const parsed = JSON.parse(next || "{}") as unknown;
            if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
              setError("باید یک شیء JSON باشد");
              onEdit(value, false);
              return;
            }
            setError(null);
            onEdit(parsed as Record<string, unknown>, true);
          } catch {
            setError("JSON نامعتبر");
            onEdit(value, false);
          }
        }}
      />
      {error && <p className="text-[10px] text-destructive">{error}</p>}
    </div>
  );
}




/**
 * Automation rules (trigger → conditions → actions).
 *
 * The engine, its five triggers and its dry-run endpoint were all finished and
 * shipped; the six admin routes that drive them had no consumer, so the engine
 * could only be operated over HTTP. This screen is that consumer.
 */
export default function AdminAutomationPage() {
  const { toast } = useToast();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [testOpen, setTestOpen] = useState(false);
  const [testTarget, setTestTarget] = useState<AutomationRule | null>(null);
  const [testContext, setTestContext] = useState("{}");
  const [testResult, setTestResult] = useState<RuleTestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const [form, setForm] = useState<{
    id: string | null;
    name: string;
    description: string;
    trigger_type: AutomationTriggerType;
    conditions: RuleCondition[];
    actions: RuleAction[];
    is_active: boolean;
    cooldown_minutes: string;
  }>({
    id: null,
    name: "",
    description: "",
    trigger_type: "order_paid",
    conditions: [],
    actions: [{ type: "send_notification", params: {} }],
    is_active: true,
    cooldown_minutes: "",
  });
  // Which action's params box is currently invalid. A single boolean would be
  // wrong the moment there is more than one action row: the last one edited
  // would decide for all of them, and a broken box that was not touched last
  // would save fine.
  const [invalidActions, setInvalidActions] = useState<Set<number>>(new Set());

  const { data, loading, reload: load } = useAdminQuery({
    queryKey: [AUTOMATION_QUERY_KEY],
    queryFn: () => automationApi.listRules({ limit: 100 }),
    fallbackError: "بارگذاری قواعد خودکارسازی ناموفق بود",
    toastOnError: true,
    toastDescription: "دسترسی automation:read لازم است.",
  });
  const rules: AutomationRule[] = data?.items ?? [];
  const runMutation = useAdminMutation();

  const openCreate = () => {
    setForm({
      id: null,
      name: "",
      description: "",
      trigger_type: "order_paid",
      conditions: [],
      actions: [{ type: "send_notification", params: {} }],
      is_active: true,
      cooldown_minutes: "",
    });
    setInvalidActions(new Set());
    setDialogOpen(true);
  };

  const openEdit = (rule: AutomationRule) => {
    setForm({
      id: rule.id,
      name: rule.name,
      description: rule.description ?? "",
      // trigger_type is not in AutomationRuleUpdate: the API fixes it at
      // create, so an edit shows it read-only rather than pretending it moved.
      trigger_type: rule.trigger_type,
      conditions: rule.conditions ?? [],
      actions:
        rule.actions && rule.actions.length > 0
          ? rule.actions
          : [{ type: "send_notification", params: {} }],
      is_active: rule.is_active,
      cooldown_minutes:
        rule.cooldown_minutes === null ? "" : String(rule.cooldown_minutes),
    });
    setInvalidActions(new Set());
    setDialogOpen(true);
  };

  const save = async () => {
    if (!form.name.trim()) {
      toast({ title: "نام قاعده الزامی است", variant: "destructive" });
      return;
    }
    if (form.actions.length === 0) {
      toast({ title: "حداقل یک اکشن لازم است", variant: "destructive" });
      return;
    }
    if (invalidActions.size > 0) {
      toast({
        title: "پارامترهای یکی از اکشن‌ها JSON معتبر نیست",
        variant: "destructive",
      });
      return;
    }
    // A condition with no field never matches — the engine fails closed, so
    // the rule would look enabled and silently do nothing.
    const badCondition = form.conditions.find((c) => !c.field.trim());
    if (badCondition) {
      toast({ title: "همهٔ شرط‌ها به نام فیلد نیاز دارند", variant: "destructive" });
      return;
    }

    const cooldown = form.cooldown_minutes.trim();
    const payload: AutomationRuleCreate = {
      name: form.name.trim(),
      description: form.description.trim() || null,
      trigger_type: form.trigger_type,
      conditions: form.conditions,
      actions: form.actions,
      is_active: form.is_active,
      cooldown_minutes: cooldown === "" ? null : Number(cooldown),
    };
    if (cooldown !== "" && (!Number.isFinite(payload.cooldown_minutes!) || (payload.cooldown_minutes as number) < 0)) {
      toast({ title: "مدت خنک‌سازی نامعتبر است", variant: "destructive" });
      return;
    }

    setSaving(true);
    try {
      if (form.id) {
        // trigger_type is deliberately not sent: the API's PATCH schema has no
        // such field, and including it would be a 422 rather than a silent no-op.
        await automationApi.updateRule(form.id, {
          name: payload.name,
          description: payload.description,
          conditions: payload.conditions,
          actions: payload.actions,
          is_active: payload.is_active,
          cooldown_minutes: payload.cooldown_minutes,
        });
        toast({ title: "قاعده بروزرسانی شد" });
      } else {
        await automationApi.createRule(payload);
        toast({ title: "قاعده ساخته شد" });
      }
      setDialogOpen(false);
      await load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { error?: { message?: string } } } })?.response?.data?.error?.message;
      toast({ title: "خطا", description: detail ?? "ذخیره قاعده ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const toggleActive = async (rule: AutomationRule) => {
    setBusyId(rule.id);
    const result = await runMutation(() => automationApi.updateRule(rule.id, { is_active: !rule.is_active }), {
      fallbackError: "تغییر وضعیت قاعده ناموفق بود",
      invalidateKeys: [[AUTOMATION_QUERY_KEY]],
    });
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setBusyId(null);
  };

  const removeRule = async (rule: AutomationRule) => {
    if (!confirm(`قاعده «${rule.name}» حذف شود؟`)) return;
    setBusyId(rule.id);
    const result = await runMutation(() => automationApi.deleteRule(rule.id), {
      fallbackError: "حذف قاعده ناموفق بود",
      invalidateKeys: [[AUTOMATION_QUERY_KEY]],
    });
    if (result.ok) {
      toast({ title: "قاعده حذف شد" });
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setBusyId(null);
  };

  const openTest = (rule: AutomationRule) => {
    setTestTarget(rule);
    setTestResult(null);
    // A starter context rather than "{}": with an empty context every condition
    // fails closed and the dry run reports "no match" for reasons that have
    // nothing to do with the rule.
    setTestContext(
      JSON.stringify(
        rule.trigger_type === "order_paid" || rule.trigger_type === "order_created"
          ? { order: { id: "test-1", total: 1000000, status: "paid" } }
          : rule.trigger_type === "stock_low"
            ? { product: { id: "test-1", stock: 2 } }
            : { user: { id: "test-1" } },
        null,
        2,
      ),
    );
    setTestOpen(true);
  };

  const runTest = async () => {
    if (!testTarget) return;
    let context: Record<string, unknown>;
    try {
      const parsed = JSON.parse(testContext);
      if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
        throw new Error("not an object");
      }
      context = parsed as Record<string, unknown>;
    } catch {
      toast({ title: "context باید یک شیء JSON معتبر باشد", variant: "destructive" });
      return;
    }
    setTesting(true);
    try {
      const res = await automationApi.triggerRule(testTarget.id, context);
      setTestResult(res);
    } catch {
      toast({ title: "اجرای آزمایشی ناموفق بود", variant: "destructive" });
    } finally {
      setTesting(false);
    }
  };

  const updateCondition = (index: number, patch: Partial<RuleCondition>) => {
    setForm((f) => ({
      ...f,
      conditions: f.conditions.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    }));
  };

  const updateAction = (index: number, patch: Partial<RuleAction>) => {
    setForm((f) => ({
      ...f,
      actions: f.actions.map((a, i) => (i === index ? { ...a, ...patch } : a)),
    }));
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Zap className="h-5 w-5 text-primary" />
            قواعد خودکارسازی
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            وقتی رویدادی رخ داد، شرط‌ها بررسی و اکشن‌ها اجرا شوند
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="ms-2 h-4 w-4" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="ms-2 h-4 w-4" />
            قاعده جدید
          </Button>
        </div>
      </div>

      <Card className="border-amber-500/30 bg-amber-500/5 p-4">
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <p>
            «اجرای آزمایشی» اکشن‌ها را واقعاً اجرا می‌کند (ایمیل می‌فرستد، اعلان
            می‌سازد، وب‌هوک را صف می‌کند) — فقط شرط فعال بودن و فاصلهٔ زمانی را
            نادیده می‌گیرد. روی قاعده‌ای با اکشن واقعی تست نگیرید.
          </p>
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : rules.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          قاعده‌ای تعریف نشده است. بدون قاعده، هیچ رویدادی خودکار واکنشی نشان
          نمی‌دهد.
        </Card>
      ) : (
        <div className="space-y-3">
          {rules.map((rule) => (
            <Card
              key={rule.id}
              className={`p-4 ${rule.is_active ? "" : "opacity-60"}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium">{rule.name}</p>
                    <Badge variant="outline" className="text-[10px]">
                      {TRIGGER_LABELS[rule.trigger_type] ?? rule.trigger_type}
                    </Badge>
                    {!rule.is_active && <Badge variant="secondary">غیرفعال</Badge>}
                    {rule.cooldown_minutes !== null && (
                      <Badge variant="secondary" className="text-[10px]">
                        <Clock className="ms-1 h-3 w-3" />
                        {toPersianDigits(String(rule.cooldown_minutes))} دقیقه
                      </Badge>
                    )}
                  </div>
                  {rule.description && (
                    <p className="mt-1.5 text-xs text-muted-foreground">
                      {rule.description}
                    </p>
                  )}

                  {rule.conditions.length > 0 && (
                    <div className="mt-2 flex flex-wrap items-center gap-1">
                      <span className="text-[10px] text-muted-foreground">شرط‌ها:</span>
                      {rule.conditions.map((c, i) => (
                        <Badge
                          key={i}
                          variant="outline"
                          className="text-[10px] font-mono"
                          dir="ltr"
                        >
                          {c.field} {OPERATOR_LABELS[c.operator] ?? c.operator}{" "}
                          {JSON.stringify(c.value)}
                        </Badge>
                      ))}
                    </div>
                  )}

                  <div className="mt-2 flex flex-wrap items-center gap-1">
                    <span className="text-[10px] text-muted-foreground">اکشن‌ها:</span>
                    {rule.actions.map((a, i) => (
                      <Badge key={i} variant="secondary" className="text-[10px]">
                        {ACTION_LABELS[a.type] ?? a.type}
                      </Badge>
                    ))}
                  </div>

                  {rule.last_triggered_at && (
                    <p className="mt-2 text-[10px] text-muted-foreground">
                      آخرین اجرا:{" "}
                      {new Date(rule.last_triggered_at).toLocaleString("fa-IR")}
                    </p>
                  )}
                </div>

                <div className="flex shrink-0 items-center gap-2">
                  <div className="flex items-center gap-1.5">
                    <Switch
                      checked={rule.is_active}
                      disabled={busyId === rule.id}
                      onCheckedChange={() => void toggleActive(rule)}
                    />
                    <span className="text-[10px] text-muted-foreground">
                      {rule.is_active ? "فعال" : "خاموش"}
                    </span>
                  </div>
                  <Button size="sm" variant="outline" onClick={() => openTest(rule)}>
                    <Play className="ms-1.5 h-3.5 w-3.5" />
                    تست
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(rule)}>
                    <Pencil className="ms-1.5 h-3.5 w-3.5" />
                    ویرایش
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-destructive hover:text-destructive"
                    disabled={busyId === rule.id}
                    onClick={() => void removeRule(rule)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* create / edit */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle>
              {form.id ? "ویرایش قاعده" : "قاعده خودکارسازی جدید"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-3">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="rule-name">نام قاعده</Label>
                <Input
                  id="rule-name"
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="اطلاع‌رسانی سفارش"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="rule-trigger">رویداد محرک</Label>
                <select
                  id="rule-trigger"
                  value={form.trigger_type}
                  disabled={!!form.id}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      trigger_type: e.target.value as AutomationTriggerType,
                    }))
                  }
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm disabled:opacity-60"
                >
                  {TRIGGERS.map((t) => (
                    <option key={t} value={t}>
                      {TRIGGER_LABELS[t]}
                    </option>
                  ))}
                </select>
                {form.id && (
                  <p className="text-[10px] text-muted-foreground">
                    رویداد محرک پس از ساخت قابل تغییر نیست؛ برای تغییر آن قاعده
                    را حذف و دوباره بسازید.
                  </p>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="rule-desc">توضیح (اختیاری)</Label>
              <Input
                id="rule-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
              />
            </div>

            {/* Conditions */}
            <div className="space-y-2">
              <Label>شرط‌ها (همه باید برقرار باشند — نبودن شرط یعنی همیشه اجرا)</Label>
              <div className="space-y-2">
                {form.conditions.map((c, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Input
                      value={c.field}
                      onChange={(e) => updateCondition(idx, { field: e.target.value })}
                      placeholder="order.total"
                      dir="ltr"
                      className="flex-1"
                    />
                    <select
                      value={c.operator}
                      onChange={(e) =>
                        updateCondition(idx, { operator: e.target.value as ConditionOperator })
                      }
                      className="rounded-md border border-input bg-background px-2 py-2 text-xs"
                    >
                      {OPERATORS.map((op) => (
                        <option key={op} value={op}>
                          {OPERATOR_LABELS[op]}
                        </option>
                      ))}
                    </select>
                    <Input
                      value={typeof c.value === "string" ? c.value : JSON.stringify(c.value)}
                      onChange={(e) => {
                        // Numeric fields must stay numbers: the engine compares
                        // with Python operators, and "5" > 3 is a TypeError
                        // that the engine swallows into a non-match.
                        const raw = e.target.value;
                        const asNumber = Number(raw);
                        updateCondition(idx, {
                          value: raw !== "" && Number.isFinite(asNumber) ? asNumber : raw,
                        });
                      }}
                      placeholder="مقدار"
                      dir="ltr"
                      className="w-36"
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() =>
                        setForm((f) => ({
                          ...f,
                          conditions: f.conditions.filter((_, i) => i !== idx),
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
                onClick={() =>
                  setForm((f) => ({
                    ...f,
                    conditions: [...f.conditions, { field: "", operator: "eq", value: "" }],
                  }))
                }
              >
                <Plus className="ms-1.5 h-3.5 w-3.5" />
                افزودن شرط
              </Button>
            </div>

            {/* Actions */}
            <div className="space-y-2">
              <Label>اکشن‌ها (حداقل یکی)</Label>
              <div className="space-y-3">
                {form.actions.map((a, idx) => (
                  <div
                    key={idx}
                    className="space-y-2 rounded border p-3"
                  >
                    <div className="flex items-center gap-2">
                      <select
                        value={a.type}
                        onChange={(e) =>
                          updateAction(idx, {
                            type: e.target.value as AutomationActionType,
                            params: {},
                          })
                        }
                        className="rounded-md border border-input bg-background px-2 py-2 text-xs"
                      >
                        {ACTION_TYPES.map((t) => (
                          <option key={t} value={t}>
                            {ACTION_LABELS[t]}
                          </option>
                        ))}
                      </select>
                      {form.actions.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setForm((f) => ({
                              ...f,
                              actions: f.actions.filter((_, i) => i !== idx),
                            }))
                          }
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      )}
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      پارامترهای لازم:{" "}
                      {Object.entries(ACTION_PARAM_HINTS[a.type])
                        .map(([k, v]) => `${k} — ${v}`)
                        .join("، ")}
                    </p>
                    <ActionParamsEditor
                      value={a.params}
                      onEdit={(params, valid) => {
                        updateAction(idx, { params });
                        setInvalidActions((prev) => {
                          const next = new Set(prev);
                          if (valid) next.delete(idx);
                          else next.add(idx);
                          return next;
                        });
                      }}
                    />
                  </div>
                ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() =>
                  setForm((f) => ({
                    ...f,
                    actions: [...f.actions, { type: "send_notification", params: {} }],
                  }))
                }
              >
                <Plus className="ms-1.5 h-3.5 w-3.5" />
                افزودن اکشن
              </Button>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex items-center gap-2">
                <Switch
                  id="rule-active"
                  checked={form.is_active}
                  onCheckedChange={(checked) => setForm((f) => ({ ...f, is_active: checked }))}
                />
                <Label htmlFor="rule-active">قاعده فعال باشد</Label>
              </div>
              <div className="space-y-2">
                <Label htmlFor="rule-cooldown">فاصلهٔ اجرا (دقیقه، اختیاری)</Label>
                <Input
                  id="rule-cooldown"
                  value={form.cooldown_minutes}
                  onChange={(e) => setForm((f) => ({ ...f, cooldown_minutes: e.target.value }))}
                  placeholder="۶۰ — خالی = بدون فاصله"
                  dir="ltr"
                />
              </div>
            </div>
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

      {/* test-fire */}
      <Dialog open={testOpen} onOpenChange={setTestOpen}>
        <DialogContent className="max-w-xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>اجرای آزمایشی — {testTarget?.name}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-3">
            <p className="text-xs text-muted-foreground">
              context ورودی موتور است؛ فیلدهای شرط‌ها از همین شیء خوانده می‌شوند.
              فیلد نبودن یعنی شرط برقرار نیست.
            </p>
            <Textarea
              dir="ltr"
              rows={8}
              className="font-mono text-xs"
              value={testContext}
              onChange={(e) => setTestContext(e.target.value)}
            />
            {testResult && (
              <Card
                className={`p-3 text-xs ${
                  testResult.matched ? "border-green-500/40 bg-green-500/5" : "border-muted"
                }`}
              >
                <p className="font-medium">
                  {testResult.matched
                    ? "شرط‌ها برقرار شد — اکشن‌ها اجرا شدند"
                    : "شرط‌ها برقرار نشد — هیچ اکشنی اجرا نشد"}
                </p>
                {testResult.actions.length > 0 && (
                  <ul className="mt-2 space-y-1">
                    {testResult.actions.map((r, i) => (
                      <li key={i} className="flex items-center gap-2">
                        <Badge
                          variant={r.status === "ok" ? "default" : "destructive"}
                          className="text-[10px]"
                        >
                          {r.status === "ok" ? "موفق" : "ناموفق"}
                        </Badge>
                        <span className="font-mono" dir="ltr">{r.type}</span>
                        {r.error && (
                          <span className="text-destructive">{r.error}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setTestOpen(false)}>
              بستن
            </Button>
            <Button onClick={runTest} disabled={testing}>
              {testing ? "در حال اجرا..." : "اجرا"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
