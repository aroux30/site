"use client";

import React from "react";
import { useBuilderStore } from "@/stores/builder-store";
import { useToast } from "@/components/ui/use-toast";
import type { BuilderElement } from "@/types/builder";

interface StructureOption {
  title: string;
  cols: number;
  preview: React.ReactNode;
  generateChildren: () => BuilderElement[];
}

function createCol(name: string, flexBasis?: string): BuilderElement {
  const id = `cont_col_${Math.random().toString(36).slice(2, 10)}`;
  return {
    id,
    name,
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
  };
}

export function ContainerStructurePicker({
  targetContainerId,
  onSelected,
}: {
  targetContainerId?: string;
  onSelected?: () => void;
}) {
  const { toast } = useToast();
  const addElement = useBuilderStore((s) => s.addElement);
  const selectElement = useBuilderStore((s) => s.selectElement);

  const structures: StructureOption[] = [
    {
      title: "۱ ستون (تک ستونه)",
      cols: 1,
      preview: <div className="w-full h-8 bg-muted-foreground/20 rounded border border-dashed border-primary/40" />,
      generateChildren: () => [createCol("ستون ۱")],
    },
    {
      title: "۲ ستون مساوی (۵۰٪ - ۵۰٪)",
      cols: 2,
      preview: (
        <div className="w-full h-8 grid grid-cols-2 gap-1.5">
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
        </div>
      ),
      generateChildren: () => [createCol("ستون ۱"), createCol("ستون ۲")],
    },
    {
      title: "۳ ستون مساوی (۳۳٪ - ۳۳٪ - ۳۳٪)",
      cols: 3,
      preview: (
        <div className="w-full h-8 grid grid-cols-3 gap-1.5">
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
        </div>
      ),
      generateChildren: () => [createCol("ستون ۱"), createCol("ستون ۲"), createCol("ستون ۳")],
    },
    {
      title: "۲ ستون نامتقارن (۳۳٪ - ۶۶٪)",
      cols: 2,
      preview: (
        <div className="w-full h-8 grid grid-cols-3 gap-1.5">
          <div className="col-span-1 bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="col-span-2 bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
        </div>
      ),
      generateChildren: () => [createCol("ستون سایدبار"), createCol("ستون اصلی")],
    },
    {
      title: "۲ ستون نامتقارن (۶۶٪ - ۳۳٪)",
      cols: 2,
      preview: (
        <div className="w-full h-8 grid grid-cols-3 gap-1.5">
          <div className="col-span-2 bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="col-span-1 bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
        </div>
      ),
      generateChildren: () => [createCol("ستون اصلی"), createCol("ستون سایدبار")],
    },
    {
      title: "۴ ستون (۲۵٪ - ۲۵٪ - ۲۵٪ - ۲۵٪)",
      cols: 4,
      preview: (
        <div className="w-full h-8 grid grid-cols-4 gap-1">
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
          <div className="bg-muted-foreground/20 rounded border border-dashed border-primary/40" />
        </div>
      ),
      generateChildren: () => [
        createCol("ستون ۱"),
        createCol("ستون ۲"),
        createCol("ستون ۳"),
        createCol("ستون ۴"),
      ],
    },
  ];

  const handleApplyStructure = (struct: StructureOption) => {
    const children = struct.generateChildren();

    if (targetContainerId) {
      // Apply columns directly inside existing empty container
      for (const child of children) {
        addElement(child, targetContainerId);
      }
      selectElement(children[0]?.id || targetContainerId);
    } else {
      // Create new section container with this column structure
      const newSectionId = `cont_sec_${Math.random().toString(36).slice(2, 10)}`;
      const newSection: BuilderElement = {
        id: newSectionId,
        name: `بخش ${struct.title}`,
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: struct.cols > 1 ? "grid" : "flex",
          direction: "row",
          justifyContent: "between",
          alignItems: "stretch",
          flexWrap: "wrap",
          gap: { value: 20, unit: "px" },
          gridColumns: struct.cols,
        },
        styles: {
          mobile: {
            padding: {
              top: { value: 32, unit: "px" },
              right: { value: 20, unit: "px" },
              bottom: { value: 32, unit: "px" },
              left: { value: 20, unit: "px" },
              isLinked: true,
            },
          },
        },
        children,
      };

      addElement(newSection);
      selectElement(children[0]?.id || newSectionId);
    }

    toast({
      title: "چیدمان اعمال شد",
      description: `چیدمان «${struct.title}» به بوم اضافه شد.`,
      duration: 2000,
    });

    if (onSelected) onSelected();
  };

  return (
    <div className="p-4 bg-card border border-border/80 rounded-2xl shadow-sm space-y-3" dir="rtl">
      <div className="flex items-center justify-between">
        <h4 className="text-xs font-bold text-foreground">
          انتخاب چیدمان ستونی ساختار (Elementor Layout Picker)
        </h4>
        <span className="text-[10px] text-muted-foreground">ساختار مورد نظر را انتخاب کنید</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5">
        {structures.map((s, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleApplyStructure(s)}
            className="flex flex-col items-center p-3 rounded-xl border border-border hover:border-primary hover:bg-primary/5 transition group space-y-2 text-center"
          >
            <div className="w-full group-hover:scale-105 transition-transform">{s.preview}</div>
            <span className="text-[11px] font-semibold text-foreground group-hover:text-primary transition-colors">
              {s.title}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
