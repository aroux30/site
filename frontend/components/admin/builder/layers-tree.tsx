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
  ChevronsDown,
  ChevronsUp,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
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
  filterQuery?: string;
  forceExpanded?: boolean | null;
}

const TreeItem = React.memo(function TreeItem({
  element,
  depth = 0,
  filterQuery = "",
  forceExpanded = null,
}: TreeItemProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Sync forced expand / collapse
  React.useEffect(() => {
    if (forceExpanded !== null) {
      setIsExpanded(forceExpanded);
    }
  }, [forceExpanded]);

  const effectiveExpanded = filterQuery ? true : isExpanded;

  // Fine-grained boolean selector (P5 Hardening):
  // Only re-renders this item when its own selection state changes
  const isSelected = useBuilderStore(
    (s) => s.selectedElementId === element.id || s.selectedElementIds.includes(element.id)
  );
  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);
  const renameElement = useBuilderStore((s) => s.renameElement);
  const moveElement = useBuilderStore((s) => s.moveElement);
  const [isEditingName, setIsEditingName] = useState(false);

  const Icon = getElementIcon(element);
  const hasChildren = element.children && element.children.length > 0;

  return (
    <div
      className={cn("flex flex-col select-none", depth > 0 && "pr-0.5")}
      style={{ marginRight: depth > 0 ? `${depth * 24}px` : 0 }}
    >
      <div
        onClick={() => selectElement(element.id)}
        draggable={!element.isLocked}
        onDragStart={(e) => {
          e.stopPropagation();
          e.dataTransfer.setData("application/json", JSON.stringify({ type: "element", elementId: element.id }));
          e.dataTransfer.effectAllowed = "move";
        }}
        onDragOver={(e) => {
          e.preventDefault();
          e.stopPropagation();
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
          {isEditingName ? (
            <input
              type="text"
              defaultValue={element.name}
              autoFocus
              onClick={(e) => e.stopPropagation()}
              onBlur={(e) => {
                setIsEditingName(false);
                const val = e.target.value.trim();
                if (val && val !== element.name) renameElement(element.id, val);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.currentTarget.blur();
                } else if (e.key === "Escape") {
                  setIsEditingName(false);
                }
              }}
              className="bg-background text-foreground px-1 py-0.5 rounded text-xs w-full max-w-[120px] outline-none ring-1 ring-primary"
            />
          ) : (
            <span
              onDoubleClick={(e) => {
                e.stopPropagation();
                setIsEditingName(true);
              }}
              className="truncate cursor-text"
              title="برای تغییر نام دابل کلیک کنید"
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
              filterQuery={filterQuery}
              forceExpanded={forceExpanded}
            />
          ))}
        </div>
      )}
    </div>
  );
});

export function LayersTree() {
  const ast = useBuilderStore((s) => s.ast);
  const [search, setSearch] = useState("");
  const [forceExpanded, setForceExpanded] = useState<boolean | null>(null);

  const filterText = search.trim().toLowerCase();

  // Helper function to check if element or any child matches query
  function matchesQuery(el: BuilderElement): boolean {
    if (!filterText) return true;
    if (el.name.toLowerCase().includes(filterText) || (el.widgetType && el.widgetType.toLowerCase().includes(filterText))) {
      return true;
    }
    if (el.children && el.children.length > 0) {
      return el.children.some(matchesQuery);
    }
    return false;
  }

  const filteredElements = useMemo(() => {
    if (!filterText) return ast.rootElements;
    return ast.rootElements.filter(matchesQuery);
  }, [ast.rootElements, filterText]);

  return (
    <div className="flex flex-col h-full p-3 space-y-2 select-none overflow-y-auto" dir="rtl">
      <div className="flex items-center justify-between px-1 text-xs font-bold text-muted-foreground uppercase tracking-wider">
        <div className="flex items-center gap-1.5">
          <Layers className="w-4 h-4 text-primary" />
          <span>درخت ساختار لایه‌ها</span>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setForceExpanded(true)}
            className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition"
            title="گسترش همه شاخه‌ها"
            data-testid="expand-all-layers-btn"
          >
            <ChevronsDown className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setForceExpanded(false)}
            className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground transition"
            title="بستن همه شاخه‌ها"
            data-testid="collapse-all-layers-btn"
          >
            <ChevronsUp className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Layers Quick Filter Search (Elementor Navigator Parity) */}
      <div className="relative">
        <Search className="absolute start-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          data-testid="layers-search-input"
          placeholder="فیلتر المان‌ها و لایه‌ها..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ps-8 h-8 text-xs"
        />
      </div>

      <div className="space-y-0.5 mt-1">
        {filteredElements.length === 0 ? (
          <div className="text-center py-6 text-xs text-muted-foreground">
            لایه‌ای با نام «{search}» یافت نشد.
          </div>
        ) : (
          filteredElements.map((el) => (
            <TreeItem
              key={el.id}
              element={el}
              filterQuery={filterText}
              forceExpanded={forceExpanded}
            />
          ))
        )}
      </div>
    </div>
  );
}
