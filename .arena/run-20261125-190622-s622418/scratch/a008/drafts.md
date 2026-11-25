# Three Drafts for Weight 2: Interactive Widgets & Form Controls

## Draft 1: Minimal Property-Patching Pipeline
- Scope: Focus strictly on fixing missing props in `inspector-panel.tsx` for form controls (`form_input`, `form_select`, `form_textarea`, `form_checkbox`, `form_radio`) and adding missing handlers for `accordion`, `tabs`, `countdown`.
- Architectural Model: Linear property mapping between React input components and `useBuilderStore.getState().updateElementProps`.
- Trade-offs:
  - Pros: Minimal lines of diff, isolated changes.
  - Cons: Ignores container-level interactions (such as `nested_tabs` and `nested_accordion` where containers contain other containers and selection propagation fails); fails second-order effects like form honeypot SSR compilation, RTL layout flips, and z-index collision of open dropdowns in inspector panel.

## Draft 2: Comprehensive 4-Layer Parity with Systems-Level Reactive Topology (SELECTED)
- Scope: End-to-end audit and unification of all 13 interactive and form widgets across all four architectural layers:
  1. Layer 1: Schema & Block Registry (`frontend/types/builder.ts`, `frontend/lib/builder/block-registry.ts`)
     - Complete typed definitions for all widget props (`FormContainerProps`, `FormInputProps`, `AccordionItem`, `TabItem`, `NestedTabProps`, `CountdownProps`, `PopupProps`, `OffCanvasProps`).
  2. Layer 2: Inspector Panel Controls & Store Plumbing (`frontend/components/admin/builder/inspector-panel.tsx`, `frontend/stores/builder-store.ts`)
     - Robust multi-tab controls (Content, Style, Advanced).
     - State propagation without value drops or type casting errors.
     - Select and Popover menus elevated to z-index >= 150 with unconstrained viewports to guarantee 0 horizontal overflow.
  3. Layer 3: Iframe Canvas Rendering & Design Token RTL Parity (`frontend/components/admin/builder/canvas-element.tsx`)
     - Native form wrappers with disabled preview mode to prevent unintended submit redirects.
     - Nested container child rendering with active tab/accordion toggling.
     - Semantic SVG icon rendering and RTL spacing with CSS variables.
  4. Layer 4: SSR Compiler & Security Sanitization (`backend/app/modules/content/application/ast_compiler.py`, `html_sanitizer.py`)
     - HTML-escaped output, valid `<form>` action endpoints, CSRF/honeypot anti-spam fields.
     - WAI-ARIA compliance (`aria-expanded`, `aria-controls`, `role="tab"`, `role="tablist"`).
- Systems Analysis & Second/Third-Order Dynamics:
  - 1st order: Controls update AST in Zustand store and persist to backend.
  - 2nd order: Canvas element re-renders in iframe without breaking drag-and-drop or parent container selection.
  - 3rd order: SSR compiler outputs valid SEO-friendly HTML with zero client hydration mismatch or script execution overhead.
- Trade-offs:
  - Pros: Complete 100% 4-layer parity, satisfies all 4 deterministic sensors, zero regressions.
  - Cons: Requires extensive and precise diffs across multiple files.

## Draft 3: Pure Component Modularization
- Scope: Decompose `inspector-panel.tsx` and `canvas-element.tsx` into dozens of independent subcomponent files under `frontend/components/admin/builder/widgets/*`.
- Trade-offs:
  - Pros: High code cleanliness and small individual files.
  - Cons: High risk of import circularities in existing builder build setup; introduces structural churn right after rounds 77 and 78; risks violating strict scope lock or breaking existing Vitest mocks that rely on monolithic exports.

## Conclusion & Selection
Draft 2 is chosen because it directly addresses the task requirements, satisfies all 4 deterministic sensors with zero compromises, and applies systems thinking to handle first, second, and third-order interactions.
