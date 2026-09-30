"use client";

import React, { useState } from "react";
import {
  Users,
  RefreshCw,
  MessageSquarePlus,
  TrendingUp,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  ArrowLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { useToast } from "@/components/ui/use-toast";
import {
  crmApi,
  type InquiryStage,
  type LeadInquiry,
  type PipelineSummary,
} from "@/lib/api/crm";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits, formatPrice } from "@/lib/utils";

const CRM_QUERY_KEY = "admin-crm" as const;

const STAGE_LABELS: Record<InquiryStage, string> = {
  new: "جدید",
  contacted: "تماس گرفته‌شده",
  qualified: "تایید صلاحیت",
  negotiating: "در مذاکره",
  converted: "تبدیل‌شده",
  lost: "از دست رفته",
};

const STAGE_ORDER: InquiryStage[] = [
  "new",
  "contacted",
  "qualified",
  "negotiating",
  "converted",
  "lost",
];

const STAGE_VARIANTS: Record<
  InquiryStage,
  "default" | "secondary" | "destructive" | "outline"
> = {
  new: "secondary",
  contacted: "secondary",
  qualified: "default",
  negotiating: "default",
  converted: "default",
  lost: "destructive",
};

/** Next stages reachable from a stage — mirrors the backend transition table. */
const NEXT_STAGES: Record<InquiryStage, InquiryStage[]> = {
  new: ["contacted", "qualified", "lost"],
  contacted: ["qualified", "lost"],
  qualified: ["negotiating", "lost"],
  negotiating: ["lost"],
  converted: [],
  lost: [],
};

export default function AdminCrmPage() {
  const { toast } = useToast();
  const [stageFilter, setStageFilter] = useState<InquiryStage | "">("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const [detail, setDetail] = useState<LeadInquiry | null>(null);
  const [noteText, setNoteText] = useState("");
  const [lostDialog, setLostDialog] = useState<{ id: string; reason: string } | null>(null);
  const [convertDialog, setConvertDialog] = useState<{
    id: string;
    user_id: string;
    key_name: string;
  } | null>(null);
  const [convertResult, setConvertResult] = useState<{
    key_prefix: string;
    api_key: string;
  } | null>(null);

  // One query for both halves: the pipeline summary and the row list always
  // came from the same Promise.all, so they must not be able to disagree.
  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [CRM_QUERY_KEY, stageFilter],
    queryFn: async () => {
      const [rows, stats] = await Promise.all([
        crmApi.list({
          stage: stageFilter || undefined,
          limit: 300,
        }),
        crmApi.pipeline(),
      ]);
      return { inquiries: rows, summary: stats };
    },
    fallbackError: "خطا در دریافت درخواست‌ها",
    // Load failures were reported as a toast naming the required permission.
    toastOnError: true,
    toastDescription: "دسترسی crm:read لازم است.",
  });
  const inquiries: LeadInquiry[] = data?.inquiries ?? [];
  const summary: PipelineSummary | null = data?.summary ?? null;
  const runMutation = useAdminMutation();

  const moveStage = async (
    id: string,
    stage: InquiryStage,
    extra?: { lost_reason?: string; note?: string },
  ) => {
    setBusyId(id);
    const result = await runMutation(
      () => crmApi.moveStage(id, { stage, ...extra }),
      {
        fallbackError: "تغییر مرحله ناموفق بود",
        invalidateKeys: [[CRM_QUERY_KEY]],
      },
    );
    if (result.ok) {
      toast({ title: `به «${STAGE_LABELS[stage]}» منتقل شد`, variant: "success" });
    } else {
      toast({
        title: "تغییر مرحله ناموفق بود",
        description: "گذار درخواستی مجاز نیست یا دلیل الزامی است.",
        variant: "destructive",
      });
    }
    setBusyId(null);
  };

  const addNote = async () => {
    if (!detail || !noteText.trim()) return;
    try {
      const updated = await crmApi.addNote(detail.id, noteText.trim());
      setDetail(updated);
      setNoteText("");
      toast({ title: "یادداشت ثبت شد", variant: "success" });
    } catch {
      toast({ title: "ثبت یادداشت ناموفق بود", variant: "destructive" });
    }
  };

  const convert = async () => {
    if (!convertDialog) return;
    if (!convertDialog.user_id.trim()) {
      toast({ title: "شناسه کاربر الزامی است", variant: "destructive" });
      return;
    }
    try {
      const result = await crmApi.convert(convertDialog.id, {
        user_id: convertDialog.user_id.trim(),
        api_key_name: convertDialog.key_name.trim() || null,
      });
      setConvertDialog(null);
      setConvertResult({ key_prefix: result.key_prefix, api_key: result.api_key });
      await load();
    } catch {
      toast({
        title: "تبدیل ناموفق بود",
        description: "درخواست باید در مرحله تایید صلاحیت یا مذاکره باشد.",
        variant: "destructive",
      });
    }
  };

  const columns: DataTableColumn<LeadInquiry>[] = [
    {
      key: "contact",
      header: "تماس",
      render: (i) => (
        <div>
          <p className="font-medium">{i.contact_name}</p>
          {i.company_name && (
            <p className="text-xs text-muted-foreground">{i.company_name}</p>
          )}
        </div>
      ),
    },
    {
      key: "phone",
      header: "شماره",
      render: (i) => (
        <span dir="ltr" className="font-mono text-xs">
          {toPersianDigits(i.phone)}
        </span>
      ),
    },
    {
      key: "stage",
      header: "مرحله",
      render: (i) => (
        <Badge variant={STAGE_VARIANTS[i.stage]}>{STAGE_LABELS[i.stage]}</Badge>
      ),
    },
    {
      key: "value",
      header: "ارزش ماهانه",
      render: (i) =>
        i.estimated_monthly_value_rial
          ? formatPrice(Math.trunc(i.estimated_monthly_value_rial / 10))
          : "—",
    },
    {
      key: "actions",
      header: "اقدام",
      render: (i) => {
        const next = NEXT_STAGES[i.stage];
        if (next.length === 0) {
          return <span className="text-xs text-muted-foreground">بسته</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            {next
              .filter((s) => s !== "lost")
              .map((s) => (
                <Button
                  key={s}
                  variant="outline"
                  size="sm"
                  className="text-[11px]"
                  disabled={busyId === i.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    moveStage(i.id, s);
                  }}
                >
                  <ArrowLeft className="ms-1 h-3 w-3" />
                  {STAGE_LABELS[s]}
                </Button>
              ))}
            {i.stage === "qualified" || i.stage === "negotiating" ? (
              <Button
                variant="default"
                size="sm"
                className="text-[11px]"
                onClick={(e) => {
                  e.stopPropagation();
                  setConvertDialog({
                    id: i.id,
                    user_id: "",
                    key_name: i.company_name ?? i.contact_name,
                  });
                }}
              >
                <CheckCircle2 className="ms-1 h-3 w-3" />
                تبدیل به همکار
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              className="text-[11px] text-destructive hover:text-destructive"
              disabled={busyId === i.id}
              onClick={(e) => {
                e.stopPropagation();
                setLostDialog({ id: i.id, reason: "" });
              }}
            >
              <XCircle className="ms-1 h-3 w-3" />
              از دست رفته
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Users className="h-5 w-5 text-primary" />
            قیف فروش عمده
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            درخواست‌های خرید عمده — از ثبت اولیه تا تبدیل به همکار تجاری با
            کلید API.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="ms-2 h-4 w-4" />
          بروزرسانی
        </Button>
      </div>

      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">کل درخواست‌ها</p>
            <p className="text-lg font-bold">{toPersianDigits(String(summary.total))}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">باز</p>
            <p className="text-lg font-bold">{toPersianDigits(String(summary.open))}</p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">ارزش قیف باز</p>
            <p className="text-sm font-bold">
              {formatPrice(Math.trunc(summary.open_pipeline_value_rial / 10))}
            </p>
          </Card>
          <Card className="p-3">
            <p className="text-xs text-muted-foreground">تبدیل‌شده</p>
            <p className="text-lg font-bold">
              {toPersianDigits(String(summary.by_stage["converted"] ?? 0))}
            </p>
          </Card>
        </div>
      )}

      <Card className="p-4">
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setStageFilter("")}
            className={`rounded-full px-3 py-1 text-xs transition-colors ${
              stageFilter === ""
                ? "bg-primary text-primary-foreground"
                : "bg-muted hover:bg-muted/80"
            }`}
          >
            همه
          </button>
          {STAGE_ORDER.map((s) => (
            <button
              key={s}
              onClick={() => setStageFilter(s)}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                stageFilter === s
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80"
              }`}
            >
              {STAGE_LABELS[s]}
              {summary?.by_stage[s] ? (
                <span className="ms-1 text-[10px] opacity-75">
                  ({toPersianDigits(String(summary.by_stage[s]))})
                </span>
              ) : null}
            </button>
          ))}
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card className="p-1">
          <DataTable
            columns={columns}
            rows={inquiries}
            rowKey={(i) => i.id}
            loading={loading}
            emptyMessage="درخواستی یافت نشد"
            emptyDescription="درخواست‌ها از فرم عمومی سایت ثبت می‌شوند."
            onRowClick={(i) => setDetail(i)}
          />
        </Card>
      )}

      {/* Detail dialog with timeline */}
      <Dialog open={detail !== null} onOpenChange={(open) => !open && setDetail(null)}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>{detail?.company_name ?? detail?.contact_name}</DialogTitle>
            <DialogDescription>
              {detail ? `مرحله فعلی: ${STAGE_LABELS[detail.stage]}` : ""}
            </DialogDescription>
          </DialogHeader>
          {detail && (
            <div className="space-y-4">
              {detail.message && (
                <div className="rounded bg-muted/40 p-3 text-sm">{detail.message}</div>
              )}
              <div className="flex items-center gap-2">
                <Input
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder="یادداشت جدید..."
                />
                <Button onClick={addNote} disabled={!noteText.trim()}>
                  <MessageSquarePlus className="ms-1.5 h-4 w-4" />
                  ثبت
                </Button>
              </div>
              <div>
                <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                  <TrendingUp className="h-3.5 w-3.5" />
                  تاریخچه
                </p>
                <div className="max-h-64 space-y-1.5 overflow-y-auto">
                  {(detail.notes ?? []).slice().reverse().map((n, idx) => (
                    <div key={idx} className="rounded bg-muted/40 p-2 text-xs">
                      <span className="font-mono text-[10px] text-muted-foreground" dir="ltr">
                        {toPersianDigits(new Date(n.at).toLocaleString("fa-IR"))}
                      </span>
                      <p className="mt-1">{n.text}</p>
                    </div>
                  ))}
                  {(detail.notes ?? []).length === 0 && (
                    <p className="text-xs text-muted-foreground">یادداشتی ثبت نشده است.</p>
                  )}
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDetail(null)}>
              بستن
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Lost-reason dialog */}
      <Dialog
        open={lostDialog !== null}
        onOpenChange={(open) => !open && setLostDialog(null)}
      >
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>ثبت از دست رفتن درخواست</DialogTitle>
            <DialogDescription>
              دلیل الزامی است — «چرا از دست دادیم» تنها سؤالی است که یک قیف
              برای پاسخ به آن وجود دارد.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label htmlFor="lost-reason">دلیل</Label>
            <Input
              id="lost-reason"
              value={lostDialog?.reason ?? ""}
              onChange={(e) =>
                setLostDialog((d) => (d ? { ...d, reason: e.target.value } : d))
              }
              className="mt-1"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setLostDialog(null)}>
              انصراف
            </Button>
            <Button
              variant="destructive"
              disabled={!lostDialog?.reason.trim()}
              onClick={() => {
                if (lostDialog) {
                  moveStage(lostDialog.id, "lost", { lost_reason: lostDialog.reason });
                  setLostDialog(null);
                }
              }}
            >
              ثبت
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Convert dialog */}
      <Dialog
        open={convertDialog !== null}
        onOpenChange={(open) => !open && setConvertDialog(null)}
      >
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>تبدیل به همکار تجاری</DialogTitle>
            <DialogDescription>
              یک کلید API برای همکار صادر می‌شود و درخواست به مرحله «تبدیل‌شده»
              می‌رود. کلید فقط یک‌بار نمایش داده خواهد شد.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label htmlFor="convert-user">شناسه کاربر (UUID)</Label>
              <Input
                id="convert-user"
                value={convertDialog?.user_id ?? ""}
                onChange={(e) =>
                  setConvertDialog((d) => (d ? { ...d, user_id: e.target.value } : d))
                }
                dir="ltr"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="convert-name">نام کلید</Label>
              <Input
                id="convert-name"
                value={convertDialog?.key_name ?? ""}
                onChange={(e) =>
                  setConvertDialog((d) => (d ? { ...d, key_name: e.target.value } : d))
                }
                className="mt-1"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConvertDialog(null)}>
              انصراف
            </Button>
            <Button onClick={convert}>تبدیل و صدور کلید</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* One-time key dialog */}
      <Dialog
        open={convertResult !== null}
        onOpenChange={(open) => !open && setConvertResult(null)}
      >
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>کلید API همکار صادر شد</DialogTitle>
            <DialogDescription>
              این مقدار فقط همین یک‌بار نمایش داده می‌شود. آن را به همکار تحویل
              دهید.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <p className="text-xs text-muted-foreground">
              پیشوند کلید: <span className="font-mono" dir="ltr">{convertResult?.key_prefix}</span>
            </p>
            <code className="block break-all rounded-md bg-muted p-3 text-xs" dir="ltr">
              {convertResult?.api_key}
            </code>
            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              پس از بستن، بازیابی ممکن نیست؛ در صورت گم شدن باید کلید جدید صادر شود.
            </div>
          </div>
          <DialogFooter>
            <Button onClick={() => setConvertResult(null)}>متوجه شدم</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
