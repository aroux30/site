import re

out_path = r"C:\Users\Administrator\Desktop\site\.claude\worktrees\busy-antonelli-be626e\.arena\run-20261125-190622-s622418\r0\a004.md"

sec4 = """## 4. 100% 4-Layer Interactive & Form Widget Parity Matrix

The complete state of parity across all fourteen interactive and form widgets is audited below:

| Widget Key | Type Category | Layer 1: Block Registry Default | Layer 2: Inspector Panel Controls | Layer 3: Canvas Iframe Rendering | Layer 4: AST Compiler & SSR Output | Parity Status |
| :--- | :---: | :--- | :--- | :--- | :--- | :---: |
| `form_container` | Container | `type: "container"`, `widgetType: "form_container"`, action URL, honeypot config | Action URL, Success Message, Error Message inputs unmasked in Content tab | Form drop-zone with container layout, badge indicator, honeypot field | `<form action="..." method="POST">` with hidden honeypot and data attributes | 100% Verified |
| `form_input` | Leaf Widget | Label, Name, Placeholder, Input Type, Required | Inputs for label, name, placeholder; Select for type; Switch for required | ReadOnly input with label and required `<span class="text-destructive ms-1">*</span>` | Escaped `<input>` wrapped in `.builder-form-group` with required asterisk | 100% Verified |
| `form_textarea` | Leaf Widget | Label, Name, Placeholder, Rows, Required | Inputs for label, name, placeholder; Number for rows; Switch for required | ReadOnly `<textarea>` with dynamic rows and required asterisk | Escaped `<textarea>` with matching rows and required asterisk | 100% Verified |
| `form_select` | Leaf Widget | Label, Name, Options array, Required | Inputs for label, name; Textarea for newline/comma options; Switch for required | Disabled `<select>` with defensively parsed options and required asterisk | Escaped `<select>` with `<option value="...">` tags and required asterisk | 100% Verified |
| `form_checkbox` | Leaf Widget | Label, Name, Checked, Required | Inputs for label, name; Switch for default checked and required | Checkbox input with linked label and primary accent focus ring | Valid SSR `<input type="checkbox">` with escaped label | 100% Verified |
| `form_radio` | Leaf Widget | Label, Group Name, Options array, Required | Inputs for label, name; Textarea for newline options; Switch for required | Radio option stack with cursor pointer and RTL spacing | Grouped SSR `<input type="radio">` sharing group name | 100% Verified |
| `accordion` | Leaf Widget | Array of `{title, content, default_open}` | Repeater list: title, content, delete button, "+ Add Item" button | Semantic `<details>` and `<summary>` with rotating chevron and border tokens | SSR `<details open>` with escaped title and content; zero raw tags | 100% Verified |
| `tabs` | Leaf Widget | Array of `{title, content}` | Repeater list: tab title, content, delete button, "+ Add Tab" button | Tab navigation bar with active tab tracking and active border/bg tokens | SSR tab buttons with `.tab-contents` and active panel display | 100% Verified |
| `countdown` | Leaf Widget | Title, Target Date ISO string | Title input, Target Date ISO picker | Real-time interval ticker with Persian numerals (`۰۱۲۳۴۵۶۷۸۹`) | SSR countdown card with Persian numerals pre-calculated from target date | 100% Verified |
| `nested_tabs` | Container | `type: "container"`, `tab_titles` array, `active_tab` | Active tab index selector, Tab titles list repeater | Tab navigation pills switching visible child containers; preserves state | SSR tab headers and child container divs with active state classes | 100% Verified |
| `nested_accordion`| Container | `type: "container"`, `item_titles` array | Section titles list repeater | Collapsible section bars wrapping child container drop-zones | SSR collapsible accordions wrapping child container elements | 100% Verified |
| `toggle` | Leaf Widget | Array of `{title, content, default_open}` | Repeater list: title, content, delete button, "+ Add Section" button | Multiple `<details>` blocks supporting independent open states | SSR `<details open>` blocks with escaped text (deduplicated compiler) | 100% Verified |
| `popup_builder` | Container | `type: "container"`, Trigger, Delay, Children | Trigger selector (`exit_intent`, `on_scroll`, `on_load`), Scroll % | Studio overlay card with badge; unmounts outside preview | SSR `<div class="builder-popup hidden" data-trigger="...">` with modal card | 100% Verified |
| `off_canvas` | Container | `type: "container"`, Position, Width, Children | Drawer position selector (`right`, `left`), Width px input | Studio canvas drawer with position badge; renders child elements | SSR `<aside class="hidden fixed inset-y-0 ...">` with drawer title and content | 100% Verified |

---
"""

with open(out_path, "a", encoding="utf-8") as f:
    f.write(sec4 + "\n")
print("Section 4 appended.")
