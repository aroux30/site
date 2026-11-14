"use client";

import { create } from "zustand";
import type {
  BuilderElement,
  DeviceStyle,
  PageAST,
  ResponsiveStyles,
} from "@/types/builder";

export type Breakpoint = "desktop" | "tablet" | "mobile";
export type LeftSidebarTab = "blocks" | "layers";
export type InspectorTab = "content" | "style" | "advanced";

const MAX_HISTORY_LENGTH = 50;

// ── Tree Traversal Helpers ──────────────────────────────────────────────────

export function findElementById(
  elements: BuilderElement[],
  id: string
): BuilderElement | null {
  for (const el of elements) {
    if (el.id === id) return el;
    if (el.children && el.children.length > 0) {
      const found = findElementById(el.children, id);
      if (found) return found;
    }
  }
  return null;
}

export function findElementAndParent(
  elements: BuilderElement[],
  id: string,
  parent: BuilderElement | null = null
): { element: BuilderElement; parent: BuilderElement | null; index: number } | null {
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i]!;
    if (el.id === id) {
      return { element: el, parent, index: i };
    }
    if (el.children && el.children.length > 0) {
      const found = findElementAndParent(el.children, id, el);
      if (found) return found;
    }
  }
  return null;
}

export function cloneElementWithNewIds(el: BuilderElement): BuilderElement {
  const newId = `el_${Math.random().toString(36).slice(2, 10)}`;
  return {
    ...el,
    id: newId,
    name: `${el.name} (کپی)`,
    children: el.children ? el.children.map(cloneElementWithNewIds) : [],
  };
}

function updateElementInTree(
  elements: BuilderElement[],
  id: string,
  updater: (el: BuilderElement) => BuilderElement
): BuilderElement[] {
  return elements.map((el) => {
    if (el.id === id) {
      return updater(el);
    }
    if (el.children && el.children.length > 0) {
      return {
        ...el,
        children: updateElementInTree(el.children, id, updater),
      };
    }
    return el;
  });
}

function removeElementFromTree(
  elements: BuilderElement[],
  id: string
): BuilderElement[] {
  return elements
    .filter((el) => el.id !== id)
    .map((el) => {
      if (el.children && el.children.length > 0) {
        return {
          ...el,
          children: removeElementFromTree(el.children, id),
        };
      }
      return el;
    });
}

// ── Default Blank AST ───────────────────────────────────────────────────────

export function createDefaultAST(title = "برگه جدید", slug = "new-page"): PageAST {
  return {
    schemaVersion: 1,
    title,
    slug,
    globalStyles: { contentMaxWidth: "1280px" },
    rootElements: [
      {
        id: `el_${Math.random().toString(36).slice(2, 10)}`,
        name: "بخش آغازین",
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "flex",
          direction: "column",
          justifyContent: "center",
          alignItems: "center",
          flexWrap: "nowrap",
          gap: { value: 16, unit: "px" },
          gridColumns: 3,
        },
        styles: {
          mobile: {
            padding: {
              top: { value: 32, unit: "px" },
              right: { value: 16, unit: "px" },
              bottom: { value: 32, unit: "px" },
              left: { value: 16, unit: "px" },
              isLinked: true,
            },
          },
          desktop: {
            padding: {
              top: { value: 48, unit: "px" },
              right: { value: 24, unit: "px" },
              bottom: { value: 48, unit: "px" },
              left: { value: 24, unit: "px" },
              isLinked: true,
            },
          },
        },
        children: [
          {
            id: `el_${Math.random().toString(36).slice(2, 10)}`,
            name: "سرتیتر خوش‌آمدگویی",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "عنوان برگه را اینجا بنویسید", tag: "h1" },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
          {
            id: `el_${Math.random().toString(36).slice(2, 10)}`,
            name: "متن توضیحی",
            type: "widget",
            widgetType: "text_editor",
            widgetProps: {
              content:
                "<p>برای ویرایش این بخش روی آن کلیک کنید یا از پنل سمت چپ عناصر جدید اضافه نمایید.</p>",
            },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
        ],
      },
    ],
  };
}

// ── State Definition ────────────────────────────────────────────────────────

export interface BuilderState {
  pageId: string | null;
  ast: PageAST;
  selectedElementId: string | null;
  hoveredElementId: string | null;
  activeBreakpoint: Breakpoint;
  activeLeftTab: LeftSidebarTab;
  activeInspectorTab: InspectorTab;
  previewMode: boolean;
  isDirty: boolean;
  isSaving: boolean;
  mutationVersion: number;
  history: {
    past: PageAST[];
    future: PageAST[];
  };

  // Actions
  initPage: (pageId: string, initialAst?: PageAST | null, fallbackTitle?: string, fallbackSlug?: string) => void;
  selectElement: (id: string | null) => void;
  setHoveredElement: (id: string | null) => void;
  setBreakpoint: (bp: Breakpoint) => void;
  setLeftTab: (tab: LeftSidebarTab) => void;
  setInspectorTab: (tab: InspectorTab) => void;
  setPreviewMode: (enabled: boolean) => void;
  setIsSaving: (saving: boolean) => void;

  // Tree mutations
  addElement: (element: BuilderElement, targetContainerId?: string, targetIndex?: number) => void;
  moveElement: (activeId: string, overId: string) => void;
  updateElementProps: (id: string, props: Record<string, unknown>) => void;
  updateElementStyles: (id: string, styles: Partial<ResponsiveStyles>) => void;
  updateDeviceStyles: (id: string, bp: Breakpoint, patch: Partial<DeviceStyle>) => void;
  deleteElement: (id: string) => void;
  duplicateElement: (id: string) => void;

  // History & Save
  undo: () => void;
  redo: () => void;
  markClean: () => void;
}

export const useBuilderStore = create<BuilderState>((set, get) => ({
  pageId: null,
  ast: createDefaultAST(),
  selectedElementId: null,
  hoveredElementId: null,
  activeBreakpoint: "desktop",
  activeLeftTab: "blocks",
  activeInspectorTab: "content",
  previewMode: false,
  isDirty: false,
  isSaving: false,
  mutationVersion: 0,
  history: {
    past: [],
    future: [],
  },

  initPage: (pageId, initialAst, fallbackTitle, fallbackSlug) => {
    const ast =
      initialAst && Array.isArray(initialAst.rootElements) && initialAst.rootElements.length > 0
        ? initialAst
        : createDefaultAST(fallbackTitle, fallbackSlug);

    set({
      pageId,
      ast,
      selectedElementId: ast.rootElements[0]?.children[0]?.id || ast.rootElements[0]?.id || null,
      hoveredElementId: null,
      activeBreakpoint: "desktop",
      previewMode: false,
      isDirty: false,
      mutationVersion: 0,
      history: { past: [], future: [] },
    });
  },

  selectElement: (id) => set({ selectedElementId: id }),
  setHoveredElement: (id) => set({ hoveredElementId: id }),
  setBreakpoint: (bp) => set({ activeBreakpoint: bp }),
  setLeftTab: (tab) => set({ activeLeftTab: tab }),
  setInspectorTab: (tab) => set({ activeInspectorTab: tab }),
  setPreviewMode: (enabled) => set({ previewMode: enabled }),
  setIsSaving: (saving) => set({ isSaving: saving }),

  addElement: (element, targetContainerId, targetIndex) => {
    const { ast, history } = get();
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    let updatedRoots: BuilderElement[];

    if (!targetContainerId) {
      // Append to roots
      const idx = targetIndex !== undefined ? targetIndex : ast.rootElements.length;
      updatedRoots = [...ast.rootElements];
      updatedRoots.splice(idx, 0, element);
    } else {
      // Insert inside target container
      updatedRoots = updateElementInTree(ast.rootElements, targetContainerId, (container) => {
        const children = [...(container.children || [])];
        const idx = targetIndex !== undefined && targetIndex <= children.length ? targetIndex : children.length;
        children.splice(idx, 0, element);
        return { ...container, children };
      });
    }

    set({
      ast: { ...ast, rootElements: updatedRoots },
      selectedElementId: element.id,
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  moveElement: (activeId, overId) => {
    const { ast, history } = get();
    if (activeId === overId) return;

    const activeInfo = findElementAndParent(ast.rootElements, activeId);
    const overInfo = findElementAndParent(ast.rootElements, overId);

    if (!activeInfo || !overInfo) return;

    // Prevent dragging a container into its own descendant
    const activeEl = activeInfo.element;
    if (activeEl.type === "container" && findElementById(activeEl.children || [], overId)) {
      return;
    }

    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    // 1. Remove active element from its current position
    const cleanedRoots = removeElementFromTree(ast.rootElements, activeId);

    // 2. Re-locate target over element in the cleaned tree
    const targetInfo = findElementAndParent(cleanedRoots, overId);
    if (!targetInfo) return;

    let finalRoots: BuilderElement[];

    if (targetInfo.element.type === "container") {
      // Drop inside container
      finalRoots = updateElementInTree(cleanedRoots, overId, (container) => ({
        ...container,
        children: [...(container.children || []), activeEl],
      }));
    } else if (targetInfo.parent) {
      // Sibling insertion inside parent container
      finalRoots = updateElementInTree(cleanedRoots, targetInfo.parent.id, (parent) => {
        const children = [...(parent.children || [])];
        children.splice(targetInfo.index, 0, activeEl);
        return { ...parent, children };
      });
    } else {
      // Root level sibling insertion
      finalRoots = [...cleanedRoots];
      finalRoots.splice(targetInfo.index, 0, activeEl);
    }

    set({
      ast: { ...ast, rootElements: finalRoots },
      selectedElementId: activeId,
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  updateElementProps: (id, props) => {
    const { ast, history } = get();
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    const updatedRoots = updateElementInTree(ast.rootElements, id, (el) => ({
      ...el,
      widgetProps: { ...(el.widgetProps || {}), ...props },
    }));

    set({
      ast: { ...ast, rootElements: updatedRoots },
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  updateElementStyles: (id, styles) => {
    const { ast, history } = get();
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    const updatedRoots = updateElementInTree(ast.rootElements, id, (el) => ({
      ...el,
      styles: { ...(el.styles || { mobile: {} }), ...styles },
    }));

    set({
      ast: { ...ast, rootElements: updatedRoots },
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  updateDeviceStyles: (id, bp, patch) => {
    const { ast, history } = get();
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    const updatedRoots = updateElementInTree(ast.rootElements, id, (el) => {
      const currentStyles = el.styles || { mobile: {} };
      const currentDeviceStyle = currentStyles[bp] || {};
      const updatedDeviceStyle = { ...currentDeviceStyle, ...patch };

      return {
        ...el,
        styles: {
          ...currentStyles,
          [bp]: updatedDeviceStyle,
        },
      };
    });

    set({
      ast: { ...ast, rootElements: updatedRoots },
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  deleteElement: (id) => {
    const { ast, history, selectedElementId } = get();
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);
    const updatedRoots = removeElementFromTree(ast.rootElements, id);

    set({
      ast: { ...ast, rootElements: updatedRoots },
      selectedElementId: selectedElementId === id ? null : selectedElementId,
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  duplicateElement: (id) => {
    const { ast, history } = get();
    const info = findElementAndParent(ast.rootElements, id);
    if (!info) return;

    const cloned = cloneElementWithNewIds(info.element);
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    let updatedRoots: BuilderElement[];
    if (info.parent) {
      updatedRoots = updateElementInTree(ast.rootElements, info.parent.id, (parent) => {
        const children = [...(parent.children || [])];
        children.splice(info.index + 1, 0, cloned);
        return { ...parent, children };
      });
    } else {
      updatedRoots = [...ast.rootElements];
      updatedRoots.splice(info.index + 1, 0, cloned);
    }

    set({
      ast: { ...ast, rootElements: updatedRoots },
      selectedElementId: cloned.id,
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: [] },
    });
  },

  undo: () => {
    const { ast, history } = get();
    if (history.past.length === 0) return;

    const previous = history.past[history.past.length - 1]!;
    const newPast = history.past.slice(0, -1);
    const newFuture = [ast, ...history.future].slice(0, MAX_HISTORY_LENGTH);

    set({
      ast: previous,
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: newFuture },
    });
  },

  redo: () => {
    const { ast, history } = get();
    if (history.future.length === 0) return;

    const next = history.future[0]!;
    const newFuture = history.future.slice(1);
    const newPast = [...history.past, ast].slice(-MAX_HISTORY_LENGTH);

    set({
      ast: next,
      isDirty: true,
      mutationVersion: get().mutationVersion + 1,
      history: { past: newPast, future: newFuture },
    });
  },

  markClean: () => set({ isDirty: false }),
}));
