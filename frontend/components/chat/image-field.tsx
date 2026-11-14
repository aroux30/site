"use client";

import { MediaPicker } from "@/components/admin/media-picker";
import { Label } from "@/components/ui/label";
import { X } from "lucide-react";

/**
 * Image field with the plugin's upload/clear behaviour: pick from the media
 * library (or upload), preview the current value, and clear it.
 */
export function ImageField({
  label,
  value,
  onChange,
  hint,
}: {
  label: string;
  value: string;
  onChange: (url: string) => void;
  hint?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="text-sm font-semibold">{label}</Label>
      <div className="flex items-center gap-3">
        <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-lg border bg-muted">
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt="" className="h-full w-full object-cover" />
          ) : (
            <span className="text-lg text-muted-foreground">🖼️</span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <MediaPicker value={value} onChange={onChange} label={label} />
          {value && (
            <button
              type="button"
              onClick={() => onChange("")}
              className="inline-flex items-center gap-1 rounded-md border border-destructive/40 px-2 py-1 text-xs font-medium text-destructive hover:bg-destructive/10"
            >
              <X className="h-3 w-3" /> حذف
            </button>
          )}
        </div>
      </div>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
