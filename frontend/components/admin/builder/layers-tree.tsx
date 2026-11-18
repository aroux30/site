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
  Eye,
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
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);

  const Icon = getElementIcon(element);
  const hasChildren = element.children && element.children.length > 0;

  return (
    <div
      className={cn("flex flex-col select-none", depth > 0 && "pr-1")}
      style={{ marginRight: depth > 0 ? `${depth * 24}px` : 0 }}
    >
      <div
        onClick={() => selectElement(element.id)}
        className={cn(
          "flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer text-xs transition group my-0.5 border",
          isSelected
            ? "bg-primary text-primary-foreground font-semibold shadow-xs border-primary"
            : "hover:bg-muted/70 text-foreground bg-card/70 border-border/50"
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
                  ? "text-primary-foreground hover:bg-white/20"
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
                ? "text-primary-foreground/70"
                : "text-muted-foreground/50 group-hover:text-muted-foreground"
            )}
          />

          <Icon className={cn("w-3.5 h-3.5 shrink-0", isSelected ? "text-primary-foreground" : "text-primary/70")} />
          <span className="truncate">{element.name}</span>

          {element.isLocked && (
            <Lock className={cn("w-3 h-3 shrink-0 ms-1", isSelected ? "text-amber-200" : "text-amber-500")} />
          )}
          {element.isHidden && (
            <EyeOff className={cn("w-3 h-3 shrink-0 ms-1", isSelected ? "text-primary-foreground/70" : "text-muted-foreground")} />
          )}
        </div>

        {/* Action Buttons: ALWAYS visible on all items — ZERO opacity-0 */}
        <div
          className={cn(
            "flex items-center gap-0.5 shrink-0 transition-opacity",
            isSelected ? "opacity-100 text-primary-foreground" : "opacity-80 hover:opacity-100 text-muted-foreground"
          )}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              toggleHideElement(element.id);
            }}
            className={cn(
              "p-1 rounded transition",
              isSelected
                ? "text-primary-foreground hover:bg-white/20"
                : element.isHidden
                ? "text-amber-500 hover:bg-amber-500/10"
                : "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
            title={element.isHidden ? "نمایش لایه" : "مخفی‌سازی لایه"}
            aria-label={element.isHidden ? `نمایش ${element.name}` : `مخفی‌سازی ${element.name}`}
          >
            {element.isHidden ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              duplicateElement(element.id);
            }}
            className={cn(
              "p-1 rounded transition",
              isSelected
                ? "text-primary-foreground hover:bg-white/20"
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
                ? "text-primary-foreground hover:bg-white/20"
                : "text-destructive hover:bg-destructive/10"
            )}
            title="حذف (Delete)"
            aria-label={`حذف ${element.name}`}
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {hasChildren && isExpanded && (
        <div className="flex flex-col border-r-2 border-primary/40 mr-3 pr-3 space-y-1 my-1">
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
    <div className="flex flex-col h-full p-3 space-y-2 select-none overflow-y-auto" dir="rtl">
      <div className="flex items-center gap-2 px-2 py-1 text-xs font-bold text-muted-foreground uppercase tracking-wider">
        <Layers className="w-4 h-4 text-primary" />
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
