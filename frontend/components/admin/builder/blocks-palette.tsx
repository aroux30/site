"use client";

import React, { useState, useMemo } from "react";
import { Search, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { BASIC_BLOCK_DEFINITIONS, type BlockDefinition } from "@/lib/builder/block-registry";
import { useBuilderStore } from "@/stores/builder-store";

export function BlocksPalette() {
  const [search, setSearch] = useState("");
  const addElement = useBuilderStore((s) => s.addElement);
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const ast = useBuilderStore((s) => s.ast);

  const filteredBlocks = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return BASIC_BLOCK_DEFINITIONS;
    return BASIC_BLOCK_DEFINITIONS.filter(
      (b) =>
        b.name.toLowerCase().includes(q) ||
        b.description.toLowerCase().includes(q) ||
        b.type.toLowerCase().includes(q)
    );
  }, [search]);

  const layoutBlocks = filteredBlocks.filter((b) => b.category === "layout");
  const basicBlocks = filteredBlocks.filter((b) => b.category === "basic");

  const handleAddBlock = (def: BlockDefinition) => {
    const newEl = def.createDefaultElement();
    // If selected element is a container, add inside it; otherwise append to root
    const selectedEl = selectedElementId
      ? ast.rootElements.find((r) => r.id === selectedElementId)
      : null;
    const targetId = selectedEl?.type === "container" ? selectedEl.id : undefined;

    addElement(newEl, targetId);
  };

  return (
    <div className="flex flex-col h-full space-y-4 p-4 select-none">
      <div className="relative">
        <Search className="absolute start-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="جستجوی بلوک..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ps-9 h-9 text-xs"
        />
      </div>

      <div className="flex-1 overflow-y-auto space-y-6 pe-1">
        {/* Layout Blocks */}
        {layoutBlocks.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider px-1">
              طرح‌بندی و ساختار
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {layoutBlocks.map((block) => {
                const Icon = block.icon;
                return (
                  <button
                    key={block.type}
                    type="button"
                    onClick={() => handleAddBlock(block)}
                    className="flex flex-col items-center justify-center p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/50 hover:border-primary/50 text-center transition shadow-sm group"
                  >
                    <Icon className="w-5 h-5 text-muted-foreground group-hover:text-primary mb-1.5 transition-colors" />
                    <span className="text-xs font-semibold text-foreground line-clamp-1">
                      {block.name.split(" ")[0]}
                    </span>
                    <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">
                      {block.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Basic Content Blocks */}
        {basicBlocks.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-bold text-muted-foreground uppercase tracking-wider px-1">
              عناصر محتوایی
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {basicBlocks.map((block) => {
                const Icon = block.icon;
                return (
                  <button
                    key={block.type}
                    type="button"
                    onClick={() => handleAddBlock(block)}
                    className="flex flex-col items-center justify-center p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/50 hover:border-primary/50 text-center transition shadow-sm group"
                  >
                    <Icon className="w-5 h-5 text-muted-foreground group-hover:text-primary mb-1.5 transition-colors" />
                    <span className="text-xs font-semibold text-foreground line-clamp-1">
                      {block.name.split(" ")[0]}
                    </span>
                    <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">
                      {block.description}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
