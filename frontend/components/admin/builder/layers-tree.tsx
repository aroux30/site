"use client";

import React, { useState, useMemo } from "react";
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
  Search,
  ChevronsUpDown,
} from "lucide-react";
import { Input } from "@/components/ui/input";
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
  onContextMenu?: (e: React.MouseEvent, elementId: string) => void;
  forceExpanded?: boolean | null;
  searchFilter?: string;
}

const TreeItem = React.memo(function TreeItem({
  element,
  depth = 0,
  onContextMenu,
  forceExpanded = null,
  searchFilter = "",
}: TreeItemProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const [isEditingName, setIsEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState(element.name);

  const effectiveExpanded = forceExpanded !== null ? forceExpanded : isExpanded;

  // Fine-grained boolean selector (P5 Hardening):
  // Only re-renders this item when its own selection state changes
  const isSelected = useBuilderStore(
    (s) => s.selectedElementId === element.id || s.selectedElementIds.includes(element.id)
  );
  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);
  const updateElementName = useBuilderStore((s) => s.updateElementName);
  const moveElement = useBuilderStore((s) => s.moveElement);

  const Icon = getElementIcon(element);
  const hasChildren = element.children && element.children.length > 0;

  const matchesSearch = useMemo(() => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return element.name.toLowerCase().includes(q) || element.id.toLowerCase().includes(q);
  }, [element.name, element.id, searchFilter]);

  const handleFinishEditing = () => {
    setIsEditingName(false);
    if (nameDraft.trim() && nameDraft.trim() !== element.name) {
      updateElementName(element.id, nameDraft.trim());
    } else {
      setNameDraft(element.name);
    }
  };

  return (
    <div
      className={cn("flex flex-col select-none", depth > 0 && "pr-0.5", !matchesSearch && "opacity-40")}
      style={{ marginRight: depth > 0 ? `${Math.min(depth * 16, 48)}px` : 0 }}
    >
      <div
        onClick={() => selectElement(element.id)}
        onDoubleClick={(e) => {
          e.stopPropagation();
          setIsEditingName(true);
        }}
        onContextMenu={(e) => {
          if (onContextMenu) {
            e.preventDefault();
            e.stopPropagation();
            onContextMenu(e, element.id);
          }
        }}
        draggable={!element.isLocked}
        onDragStart={(e) => {
          e.stopPropagation();
          e.dataTransfer.setData(
            "application/json",
            JSON.stringify({ type: "element", elementId: element.id })
          );
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        }}
        onDrop={(e) => {
          e.preventDefault();
          e.stopPropagation();
          const raw = e.dataTransfer.getData("application/json");
          if (!raw) return;
          try {
            const data = JSON.parse(raw);
            if (data.type === "element" && data.elementId && data.elementId !== element.id) {
              moveElement(data.elementId, element.id);
            }
          } catch {}
        }}
        data-layer-row=""
        data-depth={depth}
        data-element-id={element.id}
        className={cn(
          "flex items-center justify-between py-1.5 px-2 rounded-lg cursor-pointer text-xs transition group my-0.5 border overflow-hidden",
          isSelected
            ? "bg-primary text-primary-foreground font-semibold shadow-xs border-primary"
            : "hover:bg-muted/70 text-foreground bg-card/70 border-border/50"
        )}
      >
        <div className="flex items-center gap-1.5 min-w-0 flex-1 truncate">
          {/* Expand / Collapse Chevron for containers with children */}
          {hasChildren ? (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                setIsExpanded(!effectiveExpanded);
              }}
              className={cn(
                "p-0.5 rounded transition",
                isSelected
                  ? "text-primary-foreground hover:bg-white/20"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted"
              )}
              title={effectiveExpanded ? "بستن زیرمجموعه‌ها" : "باز کردن زیرمجموعه‌ها"}
            >
              {effectiveExpanded ? (
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

          {isEditingName ? (
            <input
              type="text"
              autoFocus
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onBlur={handleFinishEditing}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleFinishEditing();
                if (e.key === "Escape") {
                  setIsEditingName(false);
                  setNameDraft(element.name);
                }
              }}
              onClick={(e) => e.stopPropagation()}
              className="bg-background text-foreground px-1.5 py-0.5 rounded border border-input text-xs font-normal w-full max-w-[120px] focus:outline-none"
            />
          ) : (
            <span
              className="truncate"
              title="دابل کلیک برای تغییر نام"
            >
              {element.name}
            </span>
          )}

          {element.isLocked && (
            <Lock className={cn("w-3 h-3 shrink-0 ms-1", isSelected ? "text-amber-200" : "text-amber-500")} />
          )}
          {element.isHidden && (
            <EyeOff className={cn("w-3 h-3 shrink-0 ms-1", isSelected ? "text-primary-foreground/70" : "text-muted-foreground")} />
          )}
        </div>

        {/* Action Buttons: ALWAYS visible on all items with zero hiding */}
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

      {hasChildren && effectiveExpanded && (
        <div className="flex flex-col border-r-2 border-primary/40 mr-3 pr-3 space-y-1 my-1">
          {element.children.map((child) => (
            <TreeItem
              key={child.id}
              element={child}
              depth={depth + 1}
              onContextMenu={onContextMenu}
              forceExpanded={forceExpanded}
              searchFilter={searchFilter}
            />
          ))}
        </div>
      )}
    </div>
  );
});

function countTotalElements(elements: BuilderElement[]): number {
  let count = 0;
  for (const el of elements) {
    count++;
    if (el.children && el.children.length > 0) {
      count += countTotalElements(el.children);
    }
  }
  return count;
}

export function LayersTree({ onContextMenu }: { onContextMenu?: (e: React.MouseEvent, elementId: string) => void }) {
  const ast = useBuilderStore((s) => s.ast);
  const [search, setSearch] = useState("");
  const [expandAll, setExpandAll] = useState<boolean | null>(null);

  const totalCount = useMemo(() => countTotalElements(ast.rootElements), [ast.rootElements]);

  return (
    <div className="flex flex-col h-full p-3 space-y-2 select-none overflow-y-auto" dir="rtl">
      <div className="flex items-center justify-between px-1 py-1 border-b border-border/60 pb-2">
        <div className="flex items-center gap-1.5 text-xs font-bold text-foreground">
          <Layers className="w-4 h-4 text-primary" />
          <span>لایه‌ها (Navigator)</span>
          <span className="text-[10px] bg-muted/80 text-muted-foreground px-1.5 py-0.5 rounded-full font-mono">
            {totalCount}
          </span>
        </div>

        <button
          type="button"
          onClick={() => setExpandAll((prev) => (prev === true ? false : true))}
          className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground py-0.5 px-1.5 rounded hover:bg-muted transition"
          title="باز و بسته کردن همه لایه‌ها"
        >
          <ChevronsUpDown className="w-3 h-3" />
          <span>{expandAll === true ? "بستن همه" : "باز کردن همه"}</span>
        </button>
      </div>

      {/* Navigator Search */}
      <div className="relative shrink-0">
        <Search className="absolute start-2.5 top-2.5 h-3 w-3 text-muted-foreground" />
        <Input
          placeholder="جستجوی لایه بر اساس نام یا شناسه..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ps-7 h-7 text-xs"
        />
      </div>

      <div className="space-y-0.5 flex-1 overflow-y-auto pt-1">
        {ast.rootElements.map((el) => (
          <TreeItem
            key={el.id}
            element={el}
            onContextMenu={onContextMenu}
            forceExpanded={expandAll}
            searchFilter={search}
          />
        ))}
      </div>
    </div>
  );
}
