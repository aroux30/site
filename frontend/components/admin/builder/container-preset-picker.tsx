"use client";

import React from "react";
import { Layout, Columns, LayoutGrid } from "lucide-react";
import { useBuilderStore } from "@/stores/builder-store";
import { generateElementId } from "@/lib/builder/pattern-converter";
import type { BuilderElement } from "@/types/builder";

interface PresetOption {
  id: string;
  title: string;
  label: string;
  cols: number[]; // relative ratios, e.g. [1], [1, 1], [1, 1, 1], [1, 2], [2, 1]
}

const PRESETS: PresetOption[] = [
  { id: "1-col", title: "یک ستون (کامل)", label: "۱ ستون (۱۰۰٪)", cols: [1] },
  { id: "2-col", title: "دو ستون مساوی", label: "۲ ستون (۵۰/۵۰)", cols: [1, 1] },
  { id: "3-col", title: "سه ستون مساوی", label: "۳ ستون (مساوی)", cols: [1, 1, 1] },
  { id: "4-col", title: "چهار ستون مساوی", label: "۴ ستون (مساوی)", cols: [1, 1, 1, 1] },
  { id: "1-2-col", title: "دو ستون (۳۳٪ / ۶۶٪)", label: "۲ ستون (۳۳/۶۶)", cols: [1, 2] },
  { id: "2-1-col", title: "دو ستون (۶۶٪ / ۳۳٪)", label: "۲ ستون (۶۶/۳۳)", cols: [2, 1] },
];

export function ContainerPresetPicker({
  containerId,
}: {
  containerId: string;
}) {
  const updateElementLayout = useBuilderStore((s) => s.updateElementLayout);
  const addElement = useBuilderStore((s) => s.addElement);
  const selectElement = useBuilderStore((s) => s.selectElement);

  const applyPreset = (preset: PresetOption) => {
    const isGrid = preset.cols.length > 1;

    // 1. Update parent container layout
    updateElementLayout(containerId, {
      kind: isGrid ? "grid" : "flex",
      direction: "row",
      justifyContent: "between",
      alignItems: "stretch",
      gridColumns: preset.cols.length,
      gap: { value: 20, unit: "px" },
    });

    // 2. Insert child container columns
    const childContainers: BuilderElement[] = preset.cols.map((ratio, idx) => ({
      id: generateElementId("col"),
      name: `ستون ${idx + 1} (${preset.title})`,
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 1,
      },
      styles: {
        mobile: {
          padding: {
            top: { value: 16, unit: "px" },
            right: { value: 16, unit: "px" },
            bottom: { value: 16, unit: "px" },
            left: { value: 16, unit: "px" },
            isLinked: true,
          },
        },
      },
      children: [],
    }));

    for (const child of childContainers) {
      addElement(child, containerId);
    }

    if (childContainers[0]) {
      selectElement(childContainers[0].id);
    }
  };

  return (
    <div
      data-testid="container-preset-picker"
      className="p-4 rounded-xl border border-primary/30 bg-primary/5 space-y-3 my-2 w-full max-w-xl mx-auto select-none"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between text-xs font-bold text-foreground">
        <div className="flex items-center gap-1.5">
          <LayoutGrid className="w-4 h-4 text-primary" />
          <span>انتخاب ساختار و چیدمان ستون‌ها (الگوی المنتور)</span>
        </div>
        <span className="text-[10px] text-muted-foreground">کلیک برای ایجاد ساختار</span>
      </div>

      <div className="grid grid-cols-3 sm:grid-cols-6 gap-2">
        {PRESETS.map((preset) => {
          const total = preset.cols.reduce((a, b) => a + b, 0);
          return (
            <button
              key={preset.id}
              type="button"
              data-preset-id={preset.id}
              data-testid={`structure-preset-${preset.cols.length}`}
              onClick={() => applyPreset(preset)}
              className="flex flex-col items-center justify-center p-2 rounded-lg border border-border/70 bg-card hover:bg-primary/10 hover:border-primary transition group shadow-xs"
              title={preset.title}
            >
              {/* Visual Column Wireframe */}
              <div className="w-full h-8 flex gap-1 p-1 bg-muted/60 rounded border border-border/40 group-hover:border-primary/40">
                {preset.cols.map((c, i) => (
                  <div
                    key={i}
                    style={{ flex: c }}
                    className="h-full bg-primary/20 group-hover:bg-primary/40 rounded-xs transition-colors"
                  />
                ))}
              </div>
              <span className="text-[10px] text-muted-foreground group-hover:text-foreground font-semibold mt-1 truncate w-full text-center">
                {preset.label || `${preset.cols.length} ستونه`}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
