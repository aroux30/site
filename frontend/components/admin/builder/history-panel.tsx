"use client";

import React from "react";
import { History, Undo2, Redo2, Check, ArrowRight, Clock } from "lucide-react";
import { useBuilderStore } from "@/stores/builder-store";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

export function HistoryPanel() {
  const ast = useBuilderStore((s) => s.ast);
  const history = useBuilderStore((s) => s.history);
  const jumpToHistoryStep = useBuilderStore((s) => s.jumpToHistoryStep);
  const undo = useBuilderStore((s) => s.undo);
  const redo = useBuilderStore((s) => s.redo);

  const past = history.past;
  const future = history.future;
  const canUndo = past.length > 0;
  const canRedo = future.length > 0;

  // Combine full history timeline: past + current + future
  const timeline = [
    ...past.map((stepAst, idx) => ({
      index: idx,
      ast: stepAst,
      isCurrent: false,
      isPast: true,
      title: `ویرایش #${idx + 1} (${stepAst.rootElements.length} بخش)`,
    })),
    {
      index: past.length,
      ast,
      isCurrent: true,
      isPast: false,
      title: `وضعیت فعلی (${ast.rootElements.length} بخش)`,
    },
    ...future.map((stepAst, idx) => ({
      index: past.length + 1 + idx,
      ast: stepAst,
      isCurrent: false,
      isPast: false,
      title: `انجام مجدد #${idx + 1} (${stepAst.rootElements.length} بخش)`,
    })),
  ];

  return (
    <div
      data-testid="builder-history-panel"
      className="flex flex-col h-full min-h-0 p-3 space-y-3 select-none overflow-y-auto builder-scrollbar"
      dir="rtl"
    >
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2 text-xs font-bold text-foreground">
          <History className="w-4 h-4 text-primary" />
          <span>تاریخچه اقدامات (الگوی المنتور)</span>
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={undo}
            disabled={!canUndo}
            className="h-7 w-7 p-0"
            title="بازگشت (Undo)"
          >
            <Undo2 className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={redo}
            disabled={!canRedo}
            className="h-7 w-7 p-0"
            title="انجام مجدد (Redo)"
          >
            <Redo2 className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>

      <p className="text-[11px] text-muted-foreground px-1 leading-relaxed">
        روی هر یک از مراحل زیر کلیک کنید تا صفحه دقیقاً به همان نقطه از زمان بازگردد.
      </p>

      <div className="space-y-1 mt-1">
        {timeline.map((step) => (
          <button
            key={step.index}
            type="button"
            data-history-step={step.index}
            onClick={() => jumpToHistoryStep(step.index)}
            className={cn(
              "w-full flex items-center justify-between p-2 rounded-lg text-xs transition border text-start",
              step.isCurrent
                ? "bg-primary text-primary-foreground font-bold shadow-xs border-primary"
                : step.isPast
                ? "bg-card/70 hover:bg-muted text-foreground border-border/60"
                : "opacity-60 bg-muted/30 hover:opacity-100 text-muted-foreground border-border/40"
            )}
          >
            <div className="flex items-center gap-2">
              <Clock className={cn("w-3.5 h-3.5 shrink-0", step.isCurrent ? "text-primary-foreground" : "text-muted-foreground")} />
              <span className="truncate">{step.title}</span>
            </div>

            {step.isCurrent && (
              <span className="px-1.5 py-0.5 text-[9px] bg-background/20 rounded font-mono font-bold shrink-0">
                فعال
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
