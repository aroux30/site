"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

/**
 * FAQ and news editors — the WordPress plugin's two list editors, ported.
 *
 * FAQ rows: question / category / answer. News rows: title / icon / description
 * / link. These lists are the ONLY source for the widget's «سوالات»/«اخبار»
 * tabs, exactly like the plugin (which reads its own `n8n_chat_faqs` /
 * `n8n_chat_news` options and has no CMS fallback). When a list is empty the
 * widget shows its empty state («سوالی نیست» / «خبری نیست»).
 */

export interface FaqRow {
  q: string;
  a: string;
  cat?: string;
}
export interface NewsRow {
  title: string;
  desc: string;
  link?: string;
  icon?: string;
}

export function FaqEditor({
  value,
  onChange,
}: {
  value: FaqRow[];
  onChange: (rows: FaqRow[]) => void;
}) {
  const update = (i: number, patch: Partial<FaqRow>) =>
    onChange(value.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  return (
    <div className="space-y-2">
      {value.map((r, i) => (
        <div key={i} className="space-y-2 rounded-lg border bg-background p-3">
          <div className="flex gap-2">
            <Input
              value={r.q}
              onChange={(e) => update(i, { q: e.target.value })}
              placeholder="سوال"
              className="h-9 flex-1 text-sm"
            />
            <Input
              value={r.cat || ""}
              onChange={(e) => update(i, { cat: e.target.value })}
              placeholder="دسته"
              className="h-9 w-28 text-sm"
            />
            <button
              type="button"
              onClick={() => onChange(value.filter((_, idx) => idx !== i))}
              className="text-destructive hover:opacity-80"
              aria-label="حذف سوال"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <Textarea
            value={r.a}
            onChange={(e) => update(i, { a: e.target.value })}
            placeholder="پاسخ..."
            rows={2}
            className="text-sm"
          />
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 text-xs"
        onClick={() => onChange([...value, { q: "", a: "", cat: "" }])}
      >
        <Plus className="me-1 h-3 w-3" /> افزودن سوال
      </Button>
    </div>
  );
}

export function NewsEditor({
  value,
  onChange,
}: {
  value: NewsRow[];
  onChange: (rows: NewsRow[]) => void;
}) {
  const update = (i: number, patch: Partial<NewsRow>) =>
    onChange(value.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  return (
    <div className="space-y-2">
      {value.map((r, i) => (
        <div key={i} className="space-y-2 rounded-lg border bg-background p-3">
          <div className="flex gap-2">
            <Input
              value={r.title}
              onChange={(e) => update(i, { title: e.target.value })}
              placeholder="عنوان"
              className="h-9 flex-1 text-sm"
            />
            <Input
              value={r.icon || ""}
              onChange={(e) => update(i, { icon: e.target.value })}
              placeholder="🚀"
              className="h-9 w-16 text-center text-sm"
            />
            <button
              type="button"
              onClick={() => onChange(value.filter((_, idx) => idx !== i))}
              className="text-destructive hover:opacity-80"
              aria-label="حذف خبر"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
          <Textarea
            value={r.desc}
            onChange={(e) => update(i, { desc: e.target.value })}
            placeholder="متن خبر..."
            rows={2}
            className="text-sm"
          />
          <Input
            value={r.link || ""}
            onChange={(e) => update(i, { link: e.target.value })}
            placeholder="لینک (اختیاری)"
            dir="ltr"
            className="h-9 text-sm"
          />
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 text-xs"
        onClick={() => onChange([...value, { title: "", desc: "", link: "", icon: "🚀" }])}
      >
        <Plus className="me-1 h-3 w-3" /> افزودن خبر
      </Button>
    </div>
  );
}
