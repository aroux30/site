"use client";

import React from "react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { formatPrice, toPersianDigits, cn } from "@/lib/utils";
import type {
  ApiProductAddonField,
  ApiProductAddonOption,
  AddonAnswers,
} from "@/lib/api/services";
import { addonOptionPriceToman } from "@/lib/api/services";

/**
 * Per-product add-on fields on the product page — WooCommerce Product
 * Add-ons parity. Renders the reference plugin's field types (multiple
 * choice with select/radio display, checkboxes, short/long text with
 * character limits, buyer-defined price, quantity multiplier, heading) and
 * shows each priced option's contribution, like the plugin's price suffix.
 *
 * Answers are keyed by `field_key`; the caller prefixes them with `p:` when
 * sending to the cart so the backend can separate product add-ons from
 * category dynamic fields at checkout.
 */

function optionPriceSuffix(
  option: ApiProductAddonOption,
  quantity: number,
): string | null {
  const t = addonOptionPriceToman(option, quantity);
  if (t <= 0) return null;
  const sign = t > 0 ? "+" : "";
  return `${sign}${formatPrice(t)}`;
}

export function ProductAddonsForm({
  fields,
  answers,
  errors,
  quantity,
  onChange,
}: {
  fields: ApiProductAddonField[];
  answers: AddonAnswers;
  errors: Record<string, string>;
  quantity: number;
  onChange: (fieldKey: string, value: string | number | (string | number)[]) => void;
}) {
  const actionable = fields.filter((f) => f.field_type !== "heading");
  if (actionable.length === 0) return null;

  const headings = fields.filter((f) => f.field_type === "heading");

  return (
    <div className="space-y-4" dir="rtl">
      {headings.length > 0 && (
        <div className="rounded-xl border border-border bg-muted/30 px-4 py-2.5">
          {headings.map((h) => (
            <h3 key={h.id} className="text-sm font-bold text-foreground">
              {h.label}
            </h3>
          ))}
        </div>
      )}

      {actionable.map((field) => {
        const value = answers[field.field_key];
        const error = errors[field.field_key];
        return (
          <div key={field.id} className="space-y-1.5">
            <Label className="text-xs font-semibold text-foreground">
              {field.label}
              {field.is_required && <span className="text-destructive ms-1">*</span>}
            </Label>
            {field.description && (
              <p className="text-[11px] text-muted-foreground">{field.description}</p>
            )}

            {field.field_type === "multiple_choice" && field.display === "radio" && (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {(field.options_json || []).map((opt) => {
                  const selected = String(value ?? "") === opt.label;
                  const suffix = optionPriceSuffix(opt, quantity);
                  return (
                    <label
                      key={opt.label}
                      className={cn(
                        "flex cursor-pointer items-center justify-between gap-2 rounded-xl border border-border px-3 py-2 text-xs transition-colors",
                        selected
                          ? "border-primary bg-primary/10 font-semibold text-primary"
                          : "hover:bg-muted/60",
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <input
                          type="radio"
                          name={`addon-${field.field_key}`}
                          checked={selected}
                          onChange={() => onChange(field.field_key, opt.label)}
                          className="accent-primary"
                        />
                        {opt.label}
                      </span>
                      {suffix && <span className="font-mono">{suffix}</span>}
                    </label>
                  );
                })}
              </div>
            )}

            {field.field_type === "multiple_choice" && field.display !== "radio" && (
              /* Radix Select — same component as the rest of the storefront
                 panel; the native <select> read as a legacy dropdown. */
              <Select
                value={String(value ?? "") || undefined}
                onValueChange={(v) => onChange(field.field_key, v)}
              >
                <SelectTrigger
                  aria-label={field.label}
                  className={cn(
                    "h-10 w-full rounded-xl text-xs",
                    error && "border-destructive",
                  )}
                >
                  <SelectValue placeholder="یک گزینه انتخاب کنید…" />
                </SelectTrigger>
                <SelectContent>
                  {(field.options_json || []).map((opt) => {
                    const suffix = optionPriceSuffix(opt, quantity);
                    return (
                      <SelectItem key={opt.label} value={opt.label} className="text-xs">
                        {opt.label}
                        {suffix ? (
                          <span className="ms-1 font-mono text-muted-foreground">
                            ({suffix})
                          </span>
                        ) : null}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            )}

            {field.field_type === "checkbox" && (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {(field.options_json || []).map((opt) => {
                  const list = Array.isArray(value) ? value.map(String) : [];
                  const checked = list.includes(opt.label);
                  const suffix = optionPriceSuffix(opt, quantity);
                  return (
                    <label
                      key={opt.label}
                      className={cn(
                        "flex cursor-pointer items-center justify-between gap-2 rounded-xl border border-border px-3 py-2 text-xs transition-colors",
                        checked
                          ? "border-primary bg-primary/10 font-semibold text-primary"
                          : "hover:bg-muted/60",
                      )}
                    >
                      <span className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => {
                            const next = e.target.checked
                              ? [...list, opt.label]
                              : list.filter((l) => l !== opt.label);
                            onChange(field.field_key, next);
                          }}
                          className="accent-primary"
                        />
                        {opt.label}
                      </span>
                      {suffix && <span className="font-mono">{suffix}</span>}
                    </label>
                  );
                })}
              </div>
            )}

            {field.field_type === "custom_text" && (
              <Input
                value={String(value ?? "")}
                onChange={(e) => onChange(field.field_key, e.target.value)}
                maxLength={field.max_val ?? 200}
                className={cn("h-10 rounded-xl text-xs", error && "border-destructive")}
                aria-label={field.label}
                placeholder={field.min_val ? `حداقل ${toPersianDigits(field.min_val)} کاراکتر` : undefined}
              />
            )}

            {field.field_type === "custom_textarea" && (
              <Textarea
                value={String(value ?? "")}
                onChange={(e) => onChange(field.field_key, e.target.value)}
                maxLength={field.max_val ?? 1000}
                rows={3}
                className={cn("rounded-xl text-xs", error && "border-destructive")}
                aria-label={field.label}
                placeholder={
                  field.max_val ? `حداکثر ${toPersianDigits(field.max_val)} کاراکتر` : undefined
                }
              />
            )}

            {(field.field_type === "custom_price" ||
              field.field_type === "input_multiplier") && (
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  inputMode="numeric"
                  min={field.min_val ?? 0}
                  max={field.max_val ?? undefined}
                  value={String(value ?? "")}
                  onChange={(e) =>
                    onChange(field.field_key, e.target.value === "" ? "" : Number(e.target.value))
                  }
                  className={cn("h-10 rounded-xl text-xs", error && "border-destructive")}
                  aria-label={field.label}
                  placeholder={
                    field.field_type === "custom_price"
                      ? "مبلغ به تومان"
                      : `تعداد (۱ تا ${toPersianDigits(field.max_val ?? 99)})`
                  }
                />
                {field.field_type === "custom_price" && (
                  <span className="whitespace-nowrap text-[11px] text-muted-foreground">
                    تومان
                  </span>
                )}
                {field.field_type === "input_multiplier" && field.price ? (
                  <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">
                    {formatPrice(field.price)} / عدد
                  </span>
                ) : null}
              </div>
            )}

            {error && (
              <p className="text-[11px] font-medium text-destructive" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
