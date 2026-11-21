# Builder Gym — Round 01 Report

**Round**: Round 01  
**Level**: Level 1 — Studio Foundation  
**Date**: 2026-11-21  
**Branch**: `claude/hungry-khorana-4f765b`  
**Participating Agents**:
- Lead Architect (Agent 1)
- Elementor Architecture Specialist (Agent 2)
- UI/UX & Visual QA (Agent 3)
- Builder Functional QA (Agent 4)
- Frontend & Backend Engineer (Agent 5)
- Independent Reviewer & QA (Agent 6)

---

## 1. Scope & Audited Areas
- **Builder Studio Root Layout**: Fullscreen container (`fixed inset-0 z-[100]`), 3-column architecture (Palette/Layers on left, Canvas Frame in center, Inspector on right).
- **Navigation & Routing**: Direct studio activation via `?builder=1` and `?visual_editor=true`.
- **CanvasFrame & Overlay Layer**: Isolated iframe rendering with root-level `#builder-canvas-overlay-mount` portal for selection and floating toolbar.
- **LayersTree**: Hierarchical layer nesting, RTL indentation, and action button visibility without hover dependency.
- **Empty Container Guidance**: Visual dashed boundary and actionable block insertion guide.

---

## 2. Tested Capabilities & Invariants
1. `?builder=1` query parameter triggers `BuilderStudio` on CMS pages and scratchpad route without requiring manual token injection.
2. Floating action toolbar maintains >= 0px clearance from the canvas top boundary, automatically flipping below selected elements when approaching the ceiling.
3. LayersTree action buttons (Eye/Hide, Copy/Duplicate, Trash/Delete) are permanently visible (`opacity-80 hover:opacity-100`, zero `opacity-0` violations) with exact `depth * 24px` RTL indentation and vertical primary border line.
4. Empty container guide renders a dashed box with min-height `80px` and Persian action prompt «افزودن بلوک به این بخش».
5. Initial selection on page load is set to `null` to prevent immediate overlay toolbar interception on initial canvas interaction.
6. Button widget wraps text in `<span className="truncate">` for exact selector targeting and text overflow resilience.

---

## 3. Discovered Defects & Root Causes

### Defect 1: LayersTree RTL Indentation Clamping
- **Observation**: `layers-tree.tsx` clamped indentation to `Math.min(depth * 16, 48)px`, causing deep nested elements (depth >= 3) to lose visual parent-child hierarchy.
- **Root Cause**: Defensive width clamping intended for narrow sidebars broke strict RTL tree indent specifications.
- **Fix**: Restored clean `depth * 24px` RTL indent with right-margin spacing and `border-r-2 border-primary/40` guide line.

### Defect 2: Empty Container Guide Dimensions & Text
- **Observation**: Empty container dashed box had `min-h-[64px]` and non-standard text `+ یا افزودن مستقیم ویجت دلخواه از پالت`.
- **Root Cause**: Incomplete alignment with master prompt P0 specification.
- **Fix**: Updated `canvas-element.tsx` to `min-h-[80px]` with standard text «افزودن بلوک به این بخش».

### Defect 3: Initial Selected Element Intercepting Canvas Pointer Events
- **Observation**: `builder-store.ts` automatically selected the first child widget on `initPage`, rendering the floating toolbar immediately on load over top elements.
- **Root Cause**: Stale initialization logic.
- **Fix**: Set `selectedElementId: null` on `initPage` so selection occurs only on explicit user click.

### Defect 4: Button Widget Text Node Wrapping
- **Observation**: Button widget rendered raw text node directly inside `<a>` tag, causing locator matching issues and text truncation inconsistency.
- **Root Cause**: Missing wrapper element inside button anchor.
- **Fix**: Wrapped button label with `<span className="truncate">{labelVal}</span>`.

---

## 4. Verification Results & Test Evidence

### 4.1 Automated Tests
- **Vitest**: `tests/builder-schema.test.ts` and `tests/builder-store.test.ts` (17 passed)
- **TypeScript**: `tsc --noEmit` (0 errors)
- **Playwright E2E**: `tests/e2e/builder-gym-r01.spec.ts` (3 passed in 10.1s):
  1. `?builder=1 activates BuilderStudio directly and suppresses chat FAB collision`: **PASS**
  2. `Floating action toolbar clears iframe ceiling without clipping`: **PASS**
  3. `LayersTree action buttons permanently visible at mouse (0,0) with 24px RTL indent`: **PASS**

### 4.2 Code Review & Independent QA Sign-Off
- **Verdict**: **CONFIRMED & ACCEPTED**
- **Quality Score**: 100%
- **Regressions Introduced**: None.

---

## 5. Next Round Objective
- **Round 02**: Level 2 — Widgets & Patterns. Comprehensive verification of all 34 basic blocks and 28 ready-made block patterns.
