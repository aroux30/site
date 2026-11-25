# Task: Visual Page Builder Self-Healing Gym (Version 4.2) — Next Round Implementation & Mastery

## Objective
The user has requested to run the next round of the Visual Page Builder Self-Healing Gym (/e2e-isolated-scratchpad?builder=1) using the Arena Tournament (--quick, 16 competitors).
The competitor that produces the most robust, architecturally sound, fully typed, and regression-tested solution for the next gym weight will win.

## Scope Lock (Strict)
Only the following files are permitted to be modified or extended:
- Frontend:
  - frontend/components/admin/builder/** (builder-studio.tsx, inspector-panel.tsx, canvas-element.tsx, canvas-frame.tsx, layers-tree.tsx, builder-toolbar.tsx, blocks-palette.tsx, global-styles-dialog.tsx, container-preset-picker.tsx, and new control/widget subcomponents)
  - frontend/stores/builder-store.ts
  - frontend/lib/builder/** (block-registry.ts, icon-registry.ts, pattern-converter.ts, theme-schema.ts, color-utils.ts)
  - frontend/types/builder.ts
- Backend:
  - backend/app/modules/content/domain/builder_ast.py
  - backend/app/modules/content/domain/builder_validation.py
  - backend/app/modules/content/application/ast_compiler.py
  - backend/app/modules/content/application/html_sanitizer.py
- Tests:
  - frontend/tests/** (Vitest unit tests & Playwright specs)
  - backend/app/tests/unit/** (Pytest)

Strict Prohibitions:
- DO NOT touch backend/app/modules/audit/application/audit_service.py.
- DO NOT touch store pages (cart, checkout, product list, showcase).
- DO NOT use { force: true }, .skip(), .only(), or skip assertions in tests.

## Gym Weight Target: Weight 2 (Interactive Widgets & Form Controls 100% Audit & Wiring)
Weight 0 (Emergency Triage P0) and Weight 1 (Studio Chrome, Layers Tree & Canvas Frame) are clean and verified in rounds 77 and 78.
For the next round (Weight 2):
1. Audit and ensure 100% 4-layer parity for interactive and form widgets (e.g. form_container, form_input, form_select, form_textarea, form_checkbox, accordion, tabs, countdown, nested_tabs, nested_accordion, toggle, popup_builder, off_canvas).
2. Guarantee that every control across Content, Style, and Advanced tabs in inspector-panel.tsx:
   - Properly propagates state into builder-store.ts without throwing errors or dropping values.
   - Renders cleanly inside canvas-element.tsx (in the iframe canvas) with correct RTL styling and design token variables.
   - Compiles faithfully in ast_compiler.py for SSR output without unescaped strings, broken tags, or raw text leaks.
   - Passes all 4 deterministic sensors:
     - scroll_audit.json: 0 horizontal overflow at 1280x720 and 1440x900, min-h-0 + vertical scrolling without clipping.
     - menu_open_proof.json: All select/combobox/popover elements open with z-index >= 150 unblocked above canvas.
     - semantic_widget_audit.json: Valid SVG rendering, no raw star strings, RTL helper text directing to right panel.
     - mutation_report.json: Active nudge with pixelmatch changed pixels > 0, 0 console errors, 0 network errors, 0 hydration errors.
3. Provide concrete unified diffs or code blocks for any fixes/enhancements needed across the 4 layers.
4. Include complete analytical documentation:
   - 5-Whys Root Cause Analysis
   - SWOT Analysis & TOWS Strategies
   - Risk Matrix
   - Vitest / Playwright regression test suite
