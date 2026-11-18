"use client";

import React, { useState } from "react";
import {
  Layers,
  Layout,
  Heading,
  AlignLeft,
  Image,
  MousePointer,
  Minus,
  EyeOff,
  Lock,
  Trash2,
  Copy,
  ChevronLeft,
  ChevronDown,
  GripVertical,
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

const TreeItem = React.memo(function TreeItem({ element, depth = 0 }: TreeItemProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Fine-grained boolean selector (P5 Hardening):
  // Only re-renders this item when its own selection state changes
  const isSelected = useBuilderStore(
    (s) => s.selectedElementId === element.id || s.selectedElementIds.includes(element.id)
  );
  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);

  const Icon = getElementIcon(element);
  const hasChildren = element.children && element.children.length > 0;

  return (
    <div
      className={cn("flex flex-col select-none", depth > 0 && "border-r-2 border-border/70 pr-1.5")}
      style={{ marginInlineStart: depth > 0 ? `${depth * 10}px` : 0 }}
    >
      <div
        onClick={() => selectElement(element.id)}
        className={cn(
          "flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer text-xs transition group my-0.5",
          isSelected
            ? "bg-primary text-primary-foreground font-semibold shadow-xs"
            : "hover:bg-muted/70 text-foreground"
        )}
      >
        <div className="flex items-center gap-1.5 truncate">
          {/* Expand / Collapse Chevron for containers with children */}
          {hasChildren ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!isExpanded);
              }}
              className={cn(
                "p-0.5 rounded transition",
                isSelected
                  ? "text-white/90 hover:text-white hover:bg-white/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
              title={isExpanded ? "بستن زیرمجموعه‌ها" : "باز کردن زیرمجموعه‌ها"}
            >
              {isExpanded ? (
                <ChevronDown className="w-3.5 h-3.5" />
              ) : (
                <ChevronLeft className="w-3.5 h-3.5" />
              )}
            </button>
          ) : (
            <span className="w-3.5 shrink-0" />
          )}

          {/* Drag Grip Handle */}
          <GripVertical
            className={cn(
              "w-3 h-3 shrink-0 cursor-grab active:cursor-grabbing",
              isSelected
                ? "text-white/60"
                : "text-muted-foreground/40 group-hover:text-muted-foreground"
            )}
          />

          <Icon className={cn("w-3.5 h-3.5 shrink-0", isSelected ? "text-white" : "opacity-70")} />
          <span className="truncate">{element.name}</span>

          {element.isLocked && (
            <Lock className={cn("w-3 h-3 shrink-0 ms-1", isSelected ? "text-amber-300" : "text-amber-500")} />
          )}
          {element.isHidden && (
            <EyeOff className={cn("w-3 h-3 shrink-0 ms-1", isSelected ? "text-white/60" : "text-muted-foreground")} />
          )}
        </div>

        {/* Action Buttons: 100% visible on selected items, visible on hover/focus otherwise */}
        <div
          className={cn(
            "flex items-center gap-0.5 transition-opacity shrink-0",
            isSelected ? "opacity-100" : "opacity-0 group-hover:opacity-100 focus-within:opacity-100"
          )}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              duplicateElement(element.id);
            }}
            className={cn(
              "p-1 rounded transition",
              isSelected
                ? "text-white/90 hover:text-white hover:bg-white/20"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
            title="تکثیر (Duplicate)"
            aria-label={`تکثیر ${element.name}`}
          >
            <Copy className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              deleteElement(element.id);
            }}
            className={cn(
              "p-1 rounded transition",
              isSelected
                ? "text-white/90 hover:text-white hover:bg-white/20"
                : "text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            )}
            title="حذف (Delete)"
            aria-label={`حذف ${element.name}`}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {hasChildren && isExpanded && (
        <div className="flex flex-col space-y-0.5">
          {element.children.map((child) => (
            <TreeItem key={child.id} element={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
});

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
