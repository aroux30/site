"use client";

import React from "react";
import {
  Layers,
  Layout,
  Heading,
  AlignLeft,
  Image,
  MousePointer,
  Minus,
  Eye,
  EyeOff,
  Lock,
  Unlock,
  Trash2,
  Copy,
  ChevronRight,
  ChevronDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBuilderStore } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

function getElementIcon(el: BuilderElement) {
  if (el.type === "container") return Layout;
  switch (el.widgetType) {
    case "heading":
      return Heading;
    case "text_editor":
      return AlignLeft;
    case "image":
      return Image;
    case "button":
      return MousePointer;
    case "spacer":
    case "divider":
      return Minus;
    default:
      return Layers;
  }
}

interface TreeItemProps {
  element: BuilderElement;
  depth?: number;
}

function TreeItem({ element, depth = 0 }: TreeItemProps) {
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const updateElementProps = useBuilderStore((s) => s.updateElementProps);

  const isSelected = selectedElementId === element.id;
  const Icon = getElementIcon(element);
  const hasChildren = element.children && element.children.length > 0;

  return (
    <div className="flex flex-col">
      <div
        onClick={() => selectElement(element.id)}
        className={cn(
          "flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer text-xs transition group",
          isSelected
            ? "bg-primary text-primary-foreground font-semibold"
            : "hover:bg-muted/70 text-foreground"
        )}
        style={{ paddingInlineStart: `${depth * 16 + 8}px` }}
      >
        <div className="flex items-center gap-1.5 truncate">
          <Icon className="w-3.5 h-3.5 shrink-0 opacity-70" />
          <span className="truncate">{element.name}</span>
        </div>

        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              duplicateElement(element.id);
            }}
            className="p-1 hover:bg-black/10 dark:hover:bg-white/10 rounded"
            title="تکثیر"
          >
            <Copy className="w-3 h-3" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              deleteElement(element.id);
            }}
            className="p-1 hover:bg-destructive text-destructive-foreground rounded"
            title="حذف"
          >
            <Trash2 className="w-3 h-3" />
          </button>
        </div>
      </div>

      {hasChildren && (
        <div className="flex flex-col">
          {element.children.map((child) => (
            <TreeItem key={child.id} element={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function LayersTree() {
  const ast = useBuilderStore((s) => s.ast);

  return (
    <div className="flex flex-col h-full p-3 space-y-2 select-none overflow-y-auto">
      <div className="flex items-center gap-2 px-2 py-1 text-xs font-bold text-muted-foreground uppercase tracking-wider">
        <Layers className="w-4 h-4" />
        <span>درخت ساختار لایه‌ها</span>
      </div>

      <div className="space-y-0.5">
        {ast.rootElements.map((el) => (
          <TreeItem key={el.id} element={el} />
        ))}
      </div>
    </div>
  );
}
