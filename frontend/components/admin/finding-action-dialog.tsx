"use client";

import React, { useEffect, useRef, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  formatRialAmount,
  validateReconciliationNotes,
  type ReconciliationFinding,
} from "@/lib/api/reconciliation";

export type FindingAction = "resolve" | "dismiss";

export interface FindingActionDialogProps {
  finding: ReconciliationFinding | null;
  action: FindingAction;
  isSubmitting: boolean;
  submitError: string | null;
  onCancel: () => void;
  onConfirm: (notes: string) => void;
}

const NOTES_HINT_ID = "finding-action-notes-hint";
const NOTES_ERROR_ID = "finding-action-notes-error";

export function FindingActionDialog({
  finding,
  action,
  isSubmitting,
  submitError,
  onCancel,
  onConfirm,
}: FindingActionDialogProps) {
  const [notes, setNotes] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Reset the draft whenever the dialog is opened for a different finding, so
  // an operator note can never be carried onto another record.
  useEffect(() => {
    setNotes("");
    setLocalError(null);
  }, [finding?.id, action]);

  useEffect(() => {
    if (finding) {
      // Radix focuses the content shell; the note is the only required input,
      // so it takes focus when the dialog opens.
      textareaRef.current?.focus();
    }
  }, [finding]);

  if (!finding) return null;

  const isResolve = action === "resolve";
  const title = isResolve
    ? `حل مغایرت ${finding.findingTypeLabel}`
    : `نادیده‌گیری مغایرت ${finding.findingTypeLabel}`;
  const errorText = localError ?? submitError;

  const handleConfirm = () => {
    const validation = validateReconciliationNotes(notes);
    if (!validation.isValid) {
      setLocalError(validation.error);
      textareaRef.current?.focus();
      return;
    }
    setLocalError(null);
    onConfirm(notes.trim());
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onCancel()}>
      <DialogContent className="max-w-md" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base font-bold">
            {isResolve ? (
              <CheckCircle2
                className="h-5 w-5 text-emerald-600"
                aria-hidden="true"
              />
            ) : (
              <XCircle className="h-5 w-5 text-amber-600" aria-hidden="true" />
            )}
            {title}
          </DialogTitle>
          <DialogDescription className="text-xs leading-relaxed">
            {isResolve
              ? "یادداشت اپراتور الزامی است. ثبت این اقدام، رکورد مالی زیربنایی را تغییر نمی‌دهد و تنها وضعیت همین یافته را بروزرسانی می‌کند."
              : "دلیل نادیده‌گرفتن این یافته را ثبت کنید. این اقدام هیچ مبلغ، سفارش یا بازپرداختی را اصلاح نمی‌کند."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs">
          <FindingSummary finding={finding} />

          <div className="space-y-1.5">
            <Label htmlFor="finding-action-notes" className="text-xs">
              یادداشت اپراتور (الزامی — حداقل ۵ کاراکتر)
            </Label>
            <Textarea
              id="finding-action-notes"
              ref={textareaRef}
              value={notes}
              onChange={(event) => {
                setNotes(event.target.value);
                setLocalError(null);
              }}
              rows={4}
              className="text-xs"
              aria-required="true"
              aria-describedby={
                errorText ? `${NOTES_HINT_ID} ${NOTES_ERROR_ID}` : NOTES_HINT_ID
              }
              aria-invalid={errorText ? true : undefined}
              placeholder={
                isResolve
                  ? "مثلاً: با تأیید واحد مالی بررسی شد و از طریق فرایند بازپرداخت رسمی اصلاح می‌شود."
                  : "مثلاً: مغایرت ناشی از تأخیر شناخته‌شده وب‌هوک بود و نیاز به اقدام مالی ندارد."
              }
            />
            <p id={NOTES_HINT_ID} className="text-[11px] text-muted-foreground">
              این یادداشت در سابقه حسابرسی همان یافته ثبت می‌شود.
            </p>
            {errorText && (
              <p
                id={NOTES_ERROR_ID}
                role="alert"
                className="text-[11px] font-medium text-red-600"
              >
                {errorText}
              </p>
            )}
          </div>
        </div>

        <DialogFooter className="flex flex-row items-center justify-between gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onCancel}
            disabled={isSubmitting}
            className="text-xs"
          >
            انصراف
          </Button>
          <Button
            type="button"
            size="sm"
            variant={isResolve ? "default" : "secondary"}
            onClick={handleConfirm}
            disabled={isSubmitting}
            className="text-xs font-bold"
          >
            {isSubmitting
              ? "در حال ثبت..."
              : isResolve
                ? "تأیید و حل یافته"
                : "تأیید و نادیده‌گیری"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function FindingSummary({ finding }: { finding: ReconciliationFinding }) {
  const expected = formatRialAmount(finding.expectedAmountIrr);
  const actual = formatRialAmount(finding.actualAmountIrr);

  const rows: Array<{ label: string; value: string }> = [];
  if (finding.entityId) {
    rows.push({ label: "مورد وابسته", value: finding.entityId });
  }
  if (expected !== null) rows.push({ label: "مبلغ مورد انتظار", value: expected });
  if (actual !== null) rows.push({ label: "مبلغ واقعی", value: actual });
  if (finding.detailSummary) {
    rows.push({ label: "جزئیات", value: finding.detailSummary });
  }

  return (
    <div className="space-y-1.5 rounded-lg border border-border bg-muted/40 p-3">
      <p className="font-bold text-foreground">{finding.findingTypeLabel}</p>
      {rows.map((row) => (
        <p key={row.label} className="text-[11px] text-muted-foreground">
          <span className="font-medium">{row.label}: </span>
          <span
            className={row.label.startsWith("مبلغ") ? "font-mono" : undefined}
            dir={row.label.startsWith("مبلغ") ? "ltr" : undefined}
          >
            {row.value}
          </span>
        </p>
      ))}
    </div>
  );
}

export default FindingActionDialog;