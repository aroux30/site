"use client";

import React from "react";
import { BASIC_BLOCK_DEFINITIONS, createPatternElement } from "@/lib/builder/block-registry";
import { blockPatternsApi } from "@/lib/api/block-patterns";
import { useBuilderStore, cloneElementWithNewIds, type Breakpoint } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";
import { CanvasElement } from "./canvas-element";

/**
 * The canvas content layer, rendered inside the iframe's own React root.
 *
 * Dragging is native HTML5 drag-and-drop. dnd-kit was tried first and cannot
 * work here: its pointer sensor attaches move/up listeners to
 * ``getOwnerDocument(event.target)`` while the DndContext's measuring and
 * overlay live in the parent document, so a drag started inside the iframe
 * never activates (no aria-pressed, no transform, no onDragStart). HTML5 drag
 * events are delivered by the browser into the iframe document, so the same
 * mechanism serves both palette→canvas inserts and canvas reordering.
 *
 * The root drop zone handles inserts into the page root; CanvasElement
 * handles drops onto individual elements (container → insert inside, widget →
 * insert as a sibling).
 */
export function CanvasDndLayer({
  elements,
  activeBreakpoint,
}: {
  elements: BuilderElement[];
  activeBreakpoint: Breakpoint;
}) {
  const addElement = useBuilderStore((s) => s.addElement);
  const moveElement = useBuilderStore((s) => s.moveElement);

  return (
    <div
      data-testid="builder-canvas-root"
      className="space-y-4 min-h-[500px] w-full"
      onDragOver={(e) => {
        e.preventDefault();
        const isMove = e.dataTransfer.effectAllowed === "move";
        e.dataTransfer.dropEffect = isMove ? "move" : "copy";
      }}
      onDrop={async (e) => {
        e.preventDefault();
        const raw = e.dataTransfer.getData("application/json");
        if (!raw) return;
        try {
          const data = JSON.parse(raw) as
            | { type: "block_def"; blockType: string }
            | { type: "pattern_def"; patternSlug: string; title: string; category: string; html?: string; variables?: Record<string, string> }
            | { type: "template_def"; templateId: string; title: string; elements: BuilderElement[] }
            | { type: "element"; elementId: string };

          if (data.type === "block_def") {
            const def = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === data.blockType);
            if (def) addElement(def.createDefaultElement());
          } else if (data.type === "pattern_def") {
            const renderedHtml = data.html || (await blockPatternsApi.render(data.patternSlug, {})).html;
            const newEl = createPatternElement(
              { slug: data.patternSlug, title: data.title, category: data.category },
              renderedHtml,
              data.variables
            );
            addElement(newEl);
          } else if (data.type === "template_def" && Array.isArray((data as any).elements)) {
            for (const el of (data as any).elements) {
              addElement(cloneElementWithNewIds(el));
            }
          } else if (data.type === "element") {
            // Moving an element to the root: append it last.
            const lastRoot = elements[elements.length - 1];
            if (lastRoot && lastRoot.id !== data.elementId) {
              moveElement(data.elementId, lastRoot.id);
            }
          }
        } catch {
          /* not our payload */
        }
      }}
    >
      {elements.map((element) => (
        <CanvasElement
          key={element.id}
          element={element}
          activeBreakpoint={activeBreakpoint}
          depth={1}
        />
      ))}
    </div>
  );
}
