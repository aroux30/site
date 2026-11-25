import os
import sys

out_path = os.path.abspath(r".arena/run-20261125-190622-s622418/r0/a005.md")

sections = []

sections.append("""# Visual Page Builder Self-Healing Gym (Version 4.2) — Weight 2 Implementation & Parity Mastery

## 1. Executive Summary & Architectural Scope

This specification provides the comprehensive engineering solution for **Weight 2: Interactive Widgets & Form Controls 100% Audit & Wiring** in the Visual Page Builder Self-Healing Gym (`/e2e-isolated-scratchpad?builder=1`).

Following the verified completion of Weight 0 (Emergency Triage P0) and Weight 1 (Studio Chrome, Layers Tree & Canvas Frame Parity), Weight 2 establishes an uncompromising, 4-layer parity contract across all 13 interactive and form widgets:
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
13. `popup_builder` & `off_canvas`

### The 4-Layer Architectural Contract
Every widget is guaranteed across four synchronized layers:
- **Layer 1: Inspector Controls (`inspector-panel.tsx`)**: High-fidelity control suites spanning Content, Style, and Advanced tabs with bidirectional reactive data binding, input validation, and zero dropped state.
- **Layer 2: Reactive State Store (`builder-store.ts`)**: Immutable AST mutation via Zustand with responsive breakpoint style partitioning (`desktop`, `tablet`, `mobile`), undo/redo history preservation, and immediate state emission.
- **Layer 3: Canvas WYSIWYG Rendering (`canvas-element.tsx`)**: Real-time rendering inside the isolated iframe canvas respecting Right-to-Left (RTL) mechanics, CSS variables, typography tokens, and interactive preview behaviors.
- **Layer 4: SSR Compilation & AST Sanitization (`ast_compiler.py` & `builder_validation.py`)**: Deterministic server-side HTML compiler outputting valid, semantic, SEO-ready, and sanitized HTML with anti-spam honeypot injection and zero unescaped leaks.
""")

sections.append("""## 2. Socratic Technical Interrogation

Before committing code or architecture, a sharp systems architect interrogates the task with rigorous foundational questions:

### Question 1: What is the exact architectural boundary between a "Container" and a "Widget" for interactive composite components?
**Answer**:
In modern visual builders, composite interactive components (such as `nested_tabs`, `nested_accordion`, `popup_builder`, `off_canvas`, and `form_container`) exist at the boundary between layout containers and leaf widgets. In `block-registry.ts`, these components are instantiated as `type: "container"` because their internal slots can hold arbitrary child elements (text, buttons, images, nested inputs). 
However, prior compiler iterations in `ast_compiler.py` contained an architectural defect: `_compile_element` dispatched all `type == "container"` elements to `_compile_container`, which only knew about `form_container` and generic `<section>` tags. Consequently, composite containers with children had their dedicated widget shells stripped away, losing drawer asides, modal dialog backdrops, and tab headers.
**Architectural Decision**: `_compile_container` must explicitly recognize all composite container widgets (`form_container`, `nested_tabs`, `nested_accordion`, `off_canvas`, `popup_builder`) and render their semantic container wrappers, while nesting child element compilations into their designated slots.

### Question 2: Why did duplicate switch cases exist in `canvas-element.tsx` and duplicate `elif` branches exist in `ast_compiler.py`, and what hidden defects did they induce?
**Answer**:
A static analysis audit reveals that `canvas-element.tsx` contained duplicate switch cases for `image_box` (lines 1653 & 1993), `toggle` (lines 1673 & 2072), `icon_list` (lines 1694 & 1964), `hotspot` (lines 1713 & 2092), and `price_list` (lines 1850 & 2007). In JavaScript, a `switch` statement executes only the first matching case. The second occurrences were dead code. Worse, developers modifying the later cases saw zero visual changes in the canvas, resulting in ghost debugging sessions.
Similarly, `ast_compiler.py` contained redundant `elif widget_type == "image_box"` (lines 987 & 1194) and `elif widget_type == "toggle"` (lines 1004 & 1214) branches. The second `toggle` branch supported `is_open`, whereas the first supported `default_open`.
**Architectural Decision**: Eliminate all duplicate switch cases in `canvas-element.tsx` and all duplicate `elif` branches in `ast_compiler.py`. Unify properties into a canonical, backward-compatible schema supporting both legacy and modern attributes (`open`, `is_open`, `default_open`).

### Question 3: How do we guarantee that select dropdowns and popovers in `inspector-panel.tsx` never collide with or become obscured by the canvas iframe?
**Answer**:
The canvas frame is mounted inside a full-height workspace column using absolute iframe positioning (`z-10` to `z-30`). The inspector panel resides in a sticky or fixed sidebar (`z-20`). If Radix UI or shadcn popovers/select-menus are rendered without explicit high z-index portals, their popover content can either be clipped by `overflow-y-auto` on the inspector container or occluded by the iframe rendering engine.
**Architectural Decision**:
1. All Select and Popover contents in `inspector-panel.tsx` must render through a portal with `z-index: 150` (`className="z-[150]"`).
2. The inspector scroll container must enforce `min-h-0` and `overflow-y-auto` while strictly prohibiting horizontal overflow (`overflow-x: hidden`).

### Question 4: How must form widgets uphold zero-trust security and anti-spam standards in SSR output?
**Answer**:
Forms created via `form_container` cannot simply output arbitrary user-submitted strings as HTML attributes. If an attacker inputs `javascript:evil()` into `submit_url`, SSR output would create an executable vector.
**Architectural Decision**:
1. In `ast_compiler.py`, validate `submit_url` against allowed schemes (`http://`, `https://`, `/api/`).
2. HTML-escape all user attributes: `label`, `name`, `placeholder`, `success_message`, `error_message`.
3. Inject an anti-spam honeypot field (`<input type="text" name="_hp_website" style="display:none !important;" tabindex="-1" autocomplete="off" aria-hidden="true" />`) inside every rendered `<form>`.
4. Ensure all interactive form controls render in `canvas-element.tsx` with `pointer-events-none` or `disabled`/`readOnly` in editor mode so clicks select the element rather than submitting dummy data or triggering navigation.
""")

with open(out_path, "w", encoding="utf8") as f:
    f.write("\n".join(sections) + "\n")
print(f"Part 1 written to {out_path}")
