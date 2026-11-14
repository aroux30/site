"use client";

import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { QuickFlowNode } from "@/lib/api/chat";

/**
 * Quick-reply flow builder — the WordPress plugin's tree editor, ported.
 *
 * Each node is a button the visitor sees. A node either sends a canned reply
 * ("reply") or opens a sub-menu of child buttons ("menu"). The tree is stored
 * as `quick_flow` JSON and the widget renders it; completing a flow sends the
 * whole dialogue to n8n so the AI answers with the operator's canned knowledge.
 *
 * Immutable updates throughout: a new array is built at every edit so React
 * re-renders and the parent's save serializes the current tree.
 */

let seq = 0;
function newId(): string {
  seq += 1;
  return `n_${Date.now().toString(36)}_${seq}`;
}

export function QuickFlowBuilder({
  value,
  onChange,
}: {
  value: QuickFlowNode[];
  onChange: (nodes: QuickFlowNode[]) => void;
}) {
  /** Walk to the node at `path`, creating nothing — returns the node itself. */
  const nodeAt = (nodes: QuickFlowNode[], path: number[]): QuickFlowNode => {
    let cursor = nodes;
    let node: QuickFlowNode | undefined = cursor[0];
    for (let i = 0; i < path.length; i++) {
      const idx = path[i] ?? 0;
      node = cursor[idx];
      if (i < path.length - 1) cursor = node?.children ?? [];
    }
    if (!node) throw new Error("quick-flow node not found");
    return node;
  };

  const update = (nodes: QuickFlowNode[], path: number[], patch: Partial<QuickFlowNode>) => {
    const next = structuredClone(nodes);
    Object.assign(nodeAt(next, path), patch);
    onChange(next);
  };

  const remove = (nodes: QuickFlowNode[], path: number[]) => {
    const next = structuredClone(nodes);
    const last = path[path.length - 1] ?? 0;
    const parent = path.length === 1 ? next : nodeAt(next, path.slice(0, -1)).children ?? [];
    parent.splice(last, 1);
    onChange(next);
  };

  const addChild = (nodes: QuickFlowNode[], path: number[]) => {
    const next = structuredClone(nodes);
    const parent = nodeAt(next, path);
    parent.children = parent.children ?? [];
    parent.children.push({ id: newId(), text: "", actionType: "reply", replyText: "", children: [] });
    onChange(next);
  };

  const renderNodes = (nodes: QuickFlowNode[], path: number[], depth: number) =>
    nodes.map((node, i) => {
      const p = [...path, i];
      return (
        <div
          key={node.id || p.join("-")}
          className="rounded-lg border bg-background p-3"
          style={{ marginInlineStart: depth * 16 }}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Input
              value={node.text}
              onChange={(e) => update(value, p, { text: e.target.value })}
              placeholder="عنوان دکمه (مثلاً: پیگیری سفارش)"
              className="h-8 flex-1 text-xs"
            />
            <select
              value={node.actionType}
              onChange={(e) =>
                update(value, p, { actionType: e.target.value as QuickFlowNode["actionType"] })
              }
              className="h-8 rounded-md border bg-background px-2 text-xs"
            >
              <option value="reply">ارسال پاسخ متنی</option>
              <option value="menu">باز کردن زیرمنو</option>
            </select>
            <button
              type="button"
              onClick={() => remove(value, p)}
              className="text-red-500 hover:text-red-700"
              aria-label="حذف دکمه"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>

          {node.actionType === "reply" ? (
            <textarea
              value={node.replyText || ""}
              onChange={(e) => update(value, p, { replyText: e.target.value })}
              placeholder="متن پاسخ آماده... (وقتی کاربر کلیک کند ارسال می‌شود)"
              className="mt-2 w-full rounded-lg border bg-background p-2 text-xs"
              rows={2}
            />
          ) : (
            <div className="mt-2 space-y-2">
              {renderNodes(node.children || [], p, depth + 1)}
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 text-[11px]"
                onClick={() => addChild(value, p)}
              >
                <Plus className="me-1 h-3 w-3" /> افزودن گزینه زیرمجموعه
              </Button>
            </div>
          )}
        </div>
      );
    });

  return (
    <div className="space-y-2">
      {value.length === 0 && (
        <p className="py-4 text-center text-xs text-muted-foreground">
          هیچ دکمه‌ای تعریف نشده است.
        </p>
      )}
      {renderNodes(value, [], 0)}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 text-xs"
        onClick={() =>
          onChange([
            ...value,
            { id: newId(), text: "", actionType: "reply", replyText: "", children: [] },
          ])
        }
      >
        <Plus className="me-1 h-3 w-3" /> افزودن دکمه اصلی
      </Button>
    </div>
  );
}
