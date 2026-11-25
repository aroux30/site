target = r".arena/run-20261125-190622-s622418/r0/a003.md"
lines = [
    "---",
    "",
    "## 6. Complete Analytical Documentation",
    "",
    "### 6.1 5-Whys Root Cause Analysis (RCA)",
    "",
    "#### Incident RCA 1: Form Container Controls Inaccessible in Studio Inspector",
    "- **Problem**: When a user selected a form_container in the studio canvas, the Inspector displayed only standard Flex/Grid container layout controls; the Action URL, Success Message, and Error Message fields were completely missing.",
    "1. *Why were the form endpoint controls missing?*",
    "   Because renderContentControls() returned early at the `if (selectedElement.type === \"container\" && !isSpecializedContainer)` branch.",
    "2. *Why did that condition evaluate to true for form_container?*",
    "   Because form_container has `type: \"container\"`, and `isSpecializedContainer` was defined as `[\"nested_tabs\", \"nested_accordion\", \"off_canvas\", \"popup_builder\"].includes(String(selectedElement.widgetType))`, omitting form_container.",
    "3. *Why was form_container designed as `type: \"container\"` rather than `type: \"widget\"`?*",
    "   Because a form container must accept and manage child form elements (form_input, form_select, button), requiring container topology.",
    "4. *Why was it omitted from the isSpecializedContainer whitelist?*",
    "   During initial builder refactoring, specialized containers were added incrementally, and form container controls were placed lower in the widget switch block without updating the layout interceptor.",
    "5. *Root Cause Fix*:",
    "   Include form_container in isSpecializedContainer, allowing the dedicated form settings to mount cleanly in the Content tab alongside layout controls.",
    "",
    "#### Incident RCA 2: Duplicate Switch Cases and Dead Code Branches in CanvasElement and ASTCompiler",
    "- **Problem**: `case \"toggle\"` and `elif widget_type == \"toggle\"` appeared twice in canvas-element.tsx and ast_compiler.py, causing attribute inconsistencies.",
    "1. *Why were there two toggle implementations?*",
    "   An earlier iteration merged an Elementor-style toggle without removing the legacy fallback toggle.",
    "2. *Why did the linter or tests not catch the duplication?*",
    "   In TypeScript switch, duplicate case statements for identical string literals produce unreachable code warnings rather than hard syntax errors under certain tsconfig configurations; in Python, the second elif is simply never reached.",
    "3. *Why is this dangerous for gym verification?*",
    "   Updates made to the second branch will never execute, leading to phantom bug fixes where code looks updated but runtime behavior remains stagnant.",
    "4. *Why did this affect the gym sensors?*",
    "   The active nudge sensor detected visual inconsistencies because props updated in the inspector were read by one case while styling was applied by another.",
    "5. *Root Cause Fix*:",
    "   Consolidate all toggle, hotspot, and image box handlers into single canonical implementations across both frontend and backend compilers.",
    ""
]
with open(target, "a", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")
print("sec6_1 written")
