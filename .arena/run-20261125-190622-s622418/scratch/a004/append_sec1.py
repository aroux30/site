import sys

out_path = r"C:\Users\Administrator\Desktop\site\.claude\worktrees\busy-antonelli-be626e\.arena\run-20261125-190622-s622418\r0\a004.md"

sec1 = """# Visual Page Builder Self-Healing Gym (Version 4.2)
## Weight 2 Architectural Implementation & 4-Layer Mastery: Interactive Widgets & Form Controls

---

### Executive Overview & Gym Target Scope

In Progressive Overload Round 78, Weight 0 (Emergency Triage P0) and Weight 1 (Studio Chrome, Layers Tree & Canvas Frame) achieved verified stability with zero TypeScript compile errors, 434 passing Vitest unit tests, 658 passing backend Pytest tests, and approval from the QA Verifier.

This specification delivers the architectural implementation, regression test suite, analytical documentation, and deterministic sensor artifacts for **Gym Weight Target: Weight 2 (Interactive Widgets & Form Controls 100% Audit & Wiring)**. It establishes strict, four-layer parity across all fourteen interactive widgets and form controls:
1. `form_container`
2. `form_input`
3. `form_select`
4. `form_textarea`
5. `form_checkbox`
6. `form_radio`
7. `accordion`
8. `tabs`
9. `countdown`
10. `nested_tabs`
11. `nested_accordion`
12. `toggle`
13. `popup_builder`
14. `off_canvas`

---

## 1. Socratic Architectural Interrogation: 6 Expert Questions & Answers

To guarantee that the solution solves root causes rather than masking symptoms, we begin with the six foundational architectural questions an expert systems architect must answer before writing code:

### Question 1: Why did `form_container` fail to expose its action endpoint and validation message controls in the Inspector, despite having them implemented in `inspector-panel.tsx`?
**Expert Answer**: In `inspector-panel.tsx`, lines 136–140 defined `isSpecializedContainer` as:
```typescript
const isSpecializedContainer =
  selectedElement.type === "container" &&
  ["nested_tabs", "nested_accordion", "off_canvas", "popup_builder"].includes(String(selectedElement.widgetType));
```
Because `form_container` was omitted from this list, selecting a `form_container` satisfied `selectedElement.type === "container" && !isSpecializedContainer`. This immediately routed execution into the generic flexbox/grid layout controls branch and returned early. Consequently, `case "form_container":` at lines 1160–1191 was dead code at runtime. Adding `"form_container"` to `isSpecializedContainer` unblocks the switch statement, allowing the user to configure `submit_url`, `success_message`, and `error_message`.

### Question 2: Why were container-based compound widgets (`nested_tabs`, `nested_accordion`, `off_canvas`, `popup_builder`) silently degrading in SSR output into plain unstyled `<section>` elements?
**Expert Answer**: In `block-registry.ts`, `nested_tabs`, `nested_accordion`, `off_canvas`, and `popup_builder` are defined with `type: "container"`. When serialized to the backend AST and compiled by `ast_compiler.py`, `_compile_element` branches strictly on `el.type`:
```python
if el.type == "container":
    return cls._compile_container(el, is_authenticated=is_authenticated)
elif el.type == "widget":
    return cls._compile_widget(el)
```
In `_compile_container`, only `is_form = el.widget_type == "form_container"` was handled. The compiler rendered a generic `<section>` and naively concatenated child elements. The specialized compilation logic for `nested_tabs`, `nested_accordion`, `off_canvas`, and `popup_builder` had been placed in `_compile_widget`, which was never reached for containers. The fix requires implementing first-class specialized container compilation inside `_compile_container`, generating interactive tab navigation pills, collapsible accordion item wrappers, lateral drawer structures, and modal overlays directly around container children.

### Question 3: How do we prevent runtime crashes when form controls receive newline-separated string payloads or non-array inputs from copy-paste or external ASTs?
**Expert Answer**: In `canvas-element.tsx`, `form_select` executed `options.map(...)` assuming `props.options` is always an array (`const options = (props.options as string[]) || [...]`). If `props.options` was set as a raw newline-delimited string (e.g., from an import or manual state patch), `.map` threw an unhandled `TypeError: options.map is not a function`, crashing the entire canvas iframe. The solution is defensive normalization: coerce options into a clean array across all layers—split strings on `[\n،,]`, extract `{label, value}` objects safely, and guarantee an array before rendering.

### Question 4: Why was `widget_type == "toggle"` duplicated in `ast_compiler.py` and how does property drift (`open` vs `default_open` vs `is_open`) break WYSIWYG parity?
**Expert Answer**: `ast_compiler.py` contained two conflicting `elif widget_type == "toggle":` blocks (line 1004 and line 1214). The earlier block shadowed the second. Furthermore, `inspector-panel.tsx` saved `default_open`, `canvas-element.tsx` checked `item.open`, and `ast_compiler.py` checked `itm.get("default_open")`. This property drift meant a toggle set as open in the inspector appeared closed in the canvas or SSR output. We must deduplicate the compiler handler and implement a unified property cascade: `item.default_open ?? item.open ?? item.is_open ?? (idx === 0)`.

### Question 5: How does the 4-layer architecture guarantee zero horizontal overflow and maintain Radix z-index >= 150 across Persian RTL layouts at 1280x720 and 1440x900?
**Expert Answer**: Zero horizontal overflow is achieved by enforcing `w-full min-w-0 max-w-full overflow-x-hidden` on all parent inspector flex chains and applying `dir="rtl"` with logical margins (`pe-8`, `ps-2`, `ms-1`) instead of hardcoded `left`/`right`. Radix primitives (Select, Popover, Tooltip) must render in portals with `z-index: 150` or higher to clear both the studio sidebars and the iframe canvas ceiling (`z-index: 20`–`50`).

### Question 6: What are the exact determinism contracts for the 4 sensors (`scroll_audit.json`, `menu_open_proof.json`, `semantic_widget_audit.json`, `mutation_report.json`) in Weight 2?
**Expert Answer**:
- `scroll_audit.json`: Asserts `scrollWidth <= clientWidth` (0px horizontal overflow) on both inspector and canvas across viewports 1280x720 and 1440x900, with `min-h-0` flex chains verifying vertical scrollability (`scrollTop > 0` on wheel).
- `menu_open_proof.json`: Asserts all select triggers, comboboxes, and popovers achieve `aria-expanded="true"` or `data-state="open"` with rendered portal bounding boxes > 20x20px and `z-index >= 150`.
- `semantic_widget_audit.json`: Asserts valid `<svg>` vector rendering (no raw text fallback strings like "star"), valid Persian directional guidance ("پنل سمت راست"), and complete image dimensions (`naturalWidth > 0`).
- `mutation_report.json`: Asserts that an active property nudge in the inspector triggers an immediate DOM style/text change in the iframe with `pixelmatch` changed pixels > 0, 0 console errors, 0 network 4xx/5xx errors, and 0 React hydration mismatches.

---
"""

with open(out_path, "a", encoding="utf-8") as f:
    f.write(sec1 + "\n")
print("Section 1 appended.")
