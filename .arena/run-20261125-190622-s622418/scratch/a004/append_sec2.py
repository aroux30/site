import sys

out_path = r"C:\Users\Administrator\Desktop\site\.claude\worktrees\busy-antonelli-be626e\.arena\run-20261125-190622-s622418\r0\a004.md"

sec2 = """## 2. Test-First Acceptance Criteria & Verification Protocol

In accordance with test-first engineering discipline, we define the exact pass/fail criteria that all components must satisfy across each layer before implementation:

### Phase 1: Acceptance Criteria for Layer 1 & 2 (Store & Inspector)
- **AC-L1.1**: Invoking `updateElementProps(id, patch)` for any interactive widget must immutably update AST state in `builder-store.ts` without losing existing sibling properties.
- **AC-L2.1**: When `form_container` is selected, `inspector-panel.tsx` Content tab MUST render:
  - Action URL input (`data-testid="form-container-submit-url"`).
  - Success message input (`data-testid="form-container-success-input"`).
  - Error message input (`data-testid="form-container-error-input"`).
- **AC-L2.2**: When `form_select` options are modified via textarea, state in store MUST serialize as a clean `string[]` or `{label, value}[]` without trailing whitespace or empty entries.
- **AC-L2.3**: Adding/deleting items in `accordion`, `tabs`, and `toggle` repeaters MUST update item counts and titles reactively without mutating history unprompted.

### Phase 2: Acceptance Criteria for Layer 3 (Canvas Rendering & RTL)
- **AC-L3.1**: Required form fields (`form_input`, `form_textarea`, `form_select`) MUST display `<span class="text-destructive ms-1">*</span>` next to the label in the iframe canvas.
- **AC-L3.2**: `countdown` widget in canvas MUST compute remaining time against target date and render digits using Persian numerals (`۰۱۲۳۴۵۶۷۸۹`).
- **AC-L3.3**: `nested_tabs` container in canvas MUST render tab navigation pills and switch visible child containers upon clicking tab headers without unmounting unselected children.
- **AC-L3.4**: `nested_accordion` container in canvas MUST render collapsible header bars with rotated chevrons wrapping each child container.

### Phase 3: Acceptance Criteria for Layer 4 (AST Compilation & SSR HTML)
- **AC-L4.1**: `ast_compiler.py` compiling `form_container` MUST produce `<form action="..." method="POST" data-form-container="true">` containing the anti-spam honeypot `<input type="text" name="_hp_website" style="display:none !important;" tabindex="-1" autocomplete="off" aria-hidden="true" />`.
- **AC-L4.2**: `ast_compiler.py` compiling `nested_tabs` container MUST output `<div class="builder-nested-tabs">` containing navigation buttons and tab panes with the first pane active and remaining panes hidden.
- **AC-L4.3**: All user-controlled text strings (`label`, `placeholder`, `title`, `content`) MUST be sanitized via `html.escape` to eliminate XSS injection vulnerabilities.
- **AC-L4.4**: Duplicate `toggle` compilation in `ast_compiler.py` MUST be eliminated, unifying open-state evaluation.

### Phase 4: Deterministic 4-Sensor Verification Criteria
- **Sensor 1 (Scroll)**: Horizontal overflow == 0px at 1280x720 and 1440x900. Vertical scroll offset > 0px on wheel event.
- **Sensor 2 (Menu Proof)**: Select dropdown open verified with `z-index >= 150`, unblocked by iframe ceiling.
- **Sensor 3 (Semantic)**: Zero raw glyph strings ("star" -> `<svg>`), RTL direction indicator refers to "پنل سمت راست".
- **Sensor 4 (Mutation)**: Inspector property change yields `pixelmatch` diff > 0, 0 console errors, 0 network errors.

---

## 3. Explicit Architectural Trade-Offs

Every sound engineering choice involves deliberate trade-offs. The following decisions are made to align with production constraints:

| Architectural Decision | Chosen Approach | Alternative Considered | Deliberate Trade-Off & Justification |
| :--- | :--- | :--- | :--- |
| **Specialized Container Content Hierarchy** | Show specialized widget controls first in Content tab; keep layout controls (dimensions, padding, background) in Style tab. | Duplicate all flex/grid layout controls inside Content tab alongside specialized controls. | **Gives up**: Quick access to flex direction inside Content tab.<br>**Gains**: Zero vertical scroll bloat, clean mental model separating *What* (Content) from *How it looks* (Style). |
| **SSR Accordion & Toggle Engine** | Use semantic HTML5 `<details>` and `<summary>` tags with CSS `:open` pseudo-class and Tailwind chevrons. | Inject inline JavaScript event handlers or hydration script blocks into SSR HTML. | **Gives up**: Complex JS transition animations without hydration.<br>**Gains**: 100% accessible, zero-JS functionality, instant time-to-interactive, and zero XSS attack surface. |
| **Countdown SSR Calculation** | Pre-compute static time diff on server render with Persian numerals; activate live ticker upon client hydration. | Render empty placeholders or zeroed values during SSR until client loads. | **Gives up**: Dynamic live tick on pure static HTML without JS.<br>**Gains**: Complete SEO indexing, zero layout shift (CLS = 0), and immediate readable preview. |
| **Defensive Option Coercion** | Automatically parse and split strings into arrays across canvas and compiler layers. | Reject malformed options with strict validation error. | **Gives up**: Strict schema purism.<br>**Gains**: Resilient authoring experience—user can type or paste options separated by commas or newlines without breaking the studio. |

---
"""

with open(out_path, "a", encoding="utf-8") as f:
    f.write(sec2 + "\n")
print("Section 2 appended.")
