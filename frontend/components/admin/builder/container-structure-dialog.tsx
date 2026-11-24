"use client";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Layout } from "lucide-react";
import { useBuilderStore } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

interface ContainerStructureDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  targetContainerId?: string;
}

export function ContainerStructureDialog({
  open,
  onOpenChange,
  targetContainerId,
}: ContainerStructureDialogProps) {
  const addElement = useBuilderStore((s) => s.addElement);
  const selectElement = useBuilderStore((s) => s.selectElement);

  const presets = [
    {
      id: "col-1",
      title: "یک ستون کامل (۱۰۰٪)",
      columns: ["100%"],
      gridColumns: 1,
    },
    {
      id: "col-2-equal",
      title: "دو ستون مساوی (۵۰٪ / ۵۰٪)",
      columns: ["50%", "50%"],
      gridColumns: 2,
    },
    {
      id: "col-2-left-wide",
      title: "دو ستون نامتقارن (۳۳٪ / ۶۷٪)",
      columns: ["33.33%", "66.66%"],
      gridColumns: 3,
    },
    {
      id: "col-2-right-wide",
      title: "دو ستون نامتقارن (۶۷٪ / ۳۳٪)",
      columns: ["66.66%", "33.33%"],
      gridColumns: 3,
    },
    {
      id: "col-3-equal",
      title: "سه ستون مساوی (۳۳٪ / ۳۳٪ / ۳۳٪)",
      columns: ["33.33%", "33.33%", "33.33%"],
      gridColumns: 3,
    },
    {
      id: "col-3-center-wide",
      title: "سه ستون با مرکز پهن (۲۵٪ / ۵۰٪ / ۲۵٪)",
      columns: ["25%", "50%", "25%"],
      gridColumns: 4,
    },
    {
      id: "col-4-equal",
      title: "چهار ستون مساوی (۲۵٪ هر ستون)",
      columns: ["25%", "25%", "25%", "25%"],
      gridColumns: 4,
    },
  ];

  const handleSelectPreset = (preset: typeof presets[0]) => {
    const parentContainerId = targetContainerId;

    if (preset.columns.length === 1) {
      // Single sub-container
      const subContainer: BuilderElement = {
        id: `cont_${Math.random().toString(36).slice(2, 10)}`,
        name: "کانتینر تمام‌عرض",
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
              top: { value: 24, unit: "px" },
              right: { value: 16, unit: "px" },
              bottom: { value: 24, unit: "px" },
              left: { value: 16, unit: "px" },
              isLinked: true,
            },
          },
        },
        children: [],
      };

      addElement(subContainer, parentContainerId);
      selectElement(subContainer.id);
    } else {
      // Row container with sub-columns
      const rowContainer: BuilderElement = {
        id: `cont_row_${Math.random().toString(36).slice(2, 10)}`,
        name: `ردیف ${preset.title}`,
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "grid",
          direction: "row",
          justifyContent: "between",
          alignItems: "stretch",
          flexWrap: "wrap",
          gap: { value: 16, unit: "px" },
          gridColumns: preset.gridColumns,
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
        children: preset.columns.map((widthPercent, idx) => ({
          id: `cont_col_${Math.random().toString(36).slice(2, 10)}`,
          name: `ستون ${idx + 1} (${widthPercent})`,
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "start",
            alignItems: "stretch",
            flexWrap: "nowrap",
            gap: { value: 12, unit: "px" },
            gridColumns: 1,
          },
          styles: {
            mobile: {
              padding: {
                top: { value: 16, unit: "px" },
                right: { value: 12, unit: "px" },
                bottom: { value: 16, unit: "px" },
                left: { value: 12, unit: "px" },
                isLinked: true,
              },
            },
          },
          children: [],
        })),
      };

      addElement(rowContainer, parentContainerId);
      selectElement(rowContainer.id);
    }

    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl" dir="rtl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <Layout className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold">
                انتخاب ساختار چیدمان کانتینر (Elementor Structure Preset)
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                تعداد ستون‌ها و ترکیب بندی مورد نظر را انتخاب کنید تا چیدمان آماده درون بوم ایجاد گردد.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 py-4">
          {presets.map((preset) => (
            <button
              key={preset.id}
              type="button"
              data-testid={`container-structure-preset-${preset.id}`}
              onClick={() => handleSelectPreset(preset)}
              className="flex flex-col items-center justify-between p-3 rounded-xl border border-border/80 bg-card hover:bg-primary/5 hover:border-primary transition group text-center shadow-xs"
            >
              {/* Visual ASCII / SVG column representation */}
              <div className="flex items-center gap-1 w-full h-12 p-1.5 rounded-lg bg-muted/60 border border-border/60 mb-2 group-hover:border-primary/40 transition">
                {preset.columns.map((colWidth, cIdx) => (
                  <div
                    key={cIdx}
                    style={{ width: colWidth }}
                    className="h-full rounded bg-primary/20 group-hover:bg-primary group-hover:text-primary-foreground text-[10px] font-bold flex items-center justify-center transition border border-primary/30"
                  >
                    {colWidth.replace(".33", "").replace(".66", "")}
                  </div>
                ))}
              </div>
              <span className="text-xs font-semibold text-foreground group-hover:text-primary transition line-clamp-1">
                {preset.title}
              </span>
            </button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
