import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../..");

const filesToAnalyze = {
  inspector: path.join(ROOT_DIR, "frontend/components/admin/builder/inspector-panel.tsx"),
  toolbar: path.join(ROOT_DIR, "frontend/components/admin/builder/builder-toolbar.tsx"),
  layers: path.join(ROOT_DIR, "frontend/components/admin/builder/layers-tree.tsx"),
  palette: path.join(ROOT_DIR, "frontend/components/admin/builder/blocks-palette.tsx"),
  store: path.join(ROOT_DIR, "frontend/stores/builder-store.ts"),
  canvas: path.join(ROOT_DIR, "frontend/components/admin/builder/canvas-element.tsx"),
  types: path.join(ROOT_DIR, "frontend/types/builder.ts"),
  builderAstPy: path.join(ROOT_DIR, "backend/app/modules/content/domain/builder_ast.py"),
  astCompilerPy: path.join(ROOT_DIR, "backend/app/modules/content/application/ast_compiler.py"),
};

console.log("Analyzing builder source files for static wiring audit...");

const contents = {};
for (const [key, filepath] of Object.entries(filesToAnalyze)) {
  if (fs.existsSync(filepath)) {
    contents[key] = fs.readFileSync(filepath, "utf8");
  } else {
    console.error(`Warning: File not found: ${filepath}`);
    contents[key] = "";
  }
}

// ── 1. HARDCODED_OR_EMPTY_UI ────────────────────────────────────────────────
// Search for empty arrow functions, hardcoded options, window.alert/confirm
const hardcodedOrEmpty = [];

// Check inspector for empty handlers or no-op handlers
const emptyFnRegex = /(\w+)\s*=\s*\{\s*\(\)\s*=>\s*\{\s*\}\s*\}/g;
let match;
while ((match = emptyFnRegex.exec(contents.inspector)) !== null) {
  hardcodedOrEmpty.push({
    file: "frontend/components/admin/builder/inspector-panel.tsx",
    type: "EMPTY_HANDLER",
    code: match[0],
    description: `Empty no-op handler on attribute ${match[1]}`,
  });
}

// Check for window.alert / window.confirm across builder components
for (const [key, text] of Object.entries(contents)) {
  if (text.includes("window.alert")) {
    hardcodedOrEmpty.push({
      file: filesToAnalyze[key],
      type: "NATIVE_ALERT",
      description: "Uses native window.alert instead of toast or modal",
    });
  }
  if (text.includes("window.confirm")) {
    hardcodedOrEmpty.push({
      file: filesToAnalyze[key],
      type: "NATIVE_CONFIRM",
      description: "Uses native window.confirm instead of confirm dialog",
    });
  }
}

// Check for missing onChange or disabled placeholder controls in inspector
const inputWithoutOnChange = /<Input\s+[^>]*\/>/g;
while ((match = inputWithoutOnChange.exec(contents.inspector)) !== null) {
  const tag = match[0];
  if (!tag.includes("onChange") && !tag.includes("readOnly") && !tag.includes("type=\"color\"")) {
    hardcodedOrEmpty.push({
      file: "frontend/components/admin/builder/inspector-panel.tsx",
      type: "READONLY_OR_MISSING_ONCHANGE",
      code: tag.slice(0, 80),
      description: "Input element without onChange handler",
    });
  }
}

// ── 2. UNREAD_IN_CANVAS ─────────────────────────────────────────────────────
// Look for DeviceStyle or element properties updated in inspector but ignored in canvas-element.tsx
const stylePropertiesInTypes = [
  "backdropBlur", "filterBlur", "filter", "opacity", "zIndex", "boxShadow",
  "position", "top", "bottom", "left", "right", "overflow",
  "flexDirection", "justifyContent", "alignItems", "alignSelf", "order",
  "flexGrow", "flexWrap", "gap", "gridTemplateColumns"
];

const unreadInCanvas = [];
for (const prop of stylePropertiesInTypes) {
  // Check if handled in canvas-element.tsx or canvas styles
  const isRead = contents.canvas.includes(prop) || contents.canvas.includes(`styles.${prop}`) || contents.canvas.includes(`currentDeviceStyle.${prop}`);
  if (!isRead) {
    unreadInCanvas.push({
      property: prop,
      location: "DeviceStyle / Element Styles",
      description: `Property '${prop}' defined in builder types/store but not referenced in canvas-element.tsx inline styles or classes`,
    });
  }
}

// ── 3. UNCOMPILED_IN_SSR ────────────────────────────────────────────────────
// Check properties compiled in ast_compiler.py vs those present in builder_ast.py and types
const uncompiledInSsr = [];
for (const prop of ["backdropBlur", "filterBlur", "filter", "alignSelf", "order", "flexGrow", "overflow"]) {
  const pySnake = prop.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
  const isCompiledInSsr = contents.astCompilerPy.includes(pySnake) || contents.astCompilerPy.includes(prop);
  if (!isCompiledInSsr) {
    uncompiledInSsr.push({
      property: prop,
      pythonProperty: pySnake,
      file: "backend/app/modules/content/application/ast_compiler.py",
      description: `Property '${prop}' (${pySnake}) is not compiled to HTML in ast_compiler.py`,
    });
  }
}

// ── 4. WIDGET_CONTROL_BLIND_SPOTS ───────────────────────────────────────────
// Verify whether each of the 35 widgets has a dedicated branch in inspector-panel.tsx
const allKnownWidgets = [
  "container", "section", "columns", "heading", "paragraph", "text", "image", "button", "spacer", "divider",
  "table", "form_container", "form_input", "form_textarea", "form_select", "form_checkbox", "form_radio",
  "accordion", "tabs", "countdown", "video", "icon_box", "social_links",
  "product_card", "product_grid", "image_gallery", "star_rating", "review_histogram", "recently_viewed",
  "mega_menu", "product_price", "product_variants", "add_to_cart", "mini_cart", "cart_summary"
];

const widgetControlBlindSpots = [];
for (const widget of allKnownWidgets) {
  // Check if inspector has case for it
  const hasInspectorCase =
    contents.inspector.includes(`case "${widget}":`) ||
    (widget === "paragraph" && contents.inspector.includes('case "text_editor":')) ||
    (widget === "text" && contents.inspector.includes('case "text_editor":')) ||
    (widget === "container" && contents.inspector.includes('selectedElement.type === "container"')) ||
    (widget === "section" && contents.inspector.includes('selectedElement.type === "container"')) ||
    (widget === "columns" && contents.inspector.includes('selectedElement.type === "container"'));

  if (!hasInspectorCase) {
    widgetControlBlindSpots.push({
      widget,
      hasContentTab: false,
      description: `Widget '${widget}' lacks custom content controls in inspector-panel.tsx and falls back to default empty message.`,
    });
  }
}

const auditOutput = {
  timestamp: new Date().toISOString(),
  summary: {
    hardcodedOrEmptyCount: hardcodedOrEmpty.length,
    unreadInCanvasCount: unreadInCanvas.length,
    uncompiledInSsrCount: uncompiledInSsr.length,
    blindSpotsCount: widgetControlBlindSpots.length,
  },
  gaps: {
    HARDCODED_OR_EMPTY_UI: hardcodedOrEmpty,
    UNREAD_IN_CANVAS: unreadInCanvas,
    UNCOMPILED_IN_SSR: uncompiledInSsr,
    WIDGET_CONTROL_BLIND_SPOTS: widgetControlBlindSpots,
  },
};

const outputDir = path.join(ROOT_DIR, ".loop");
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

const outputPath = path.join(outputDir, "builder_wiring_gaps.json");
fs.writeFileSync(outputPath, JSON.stringify(auditOutput, null, 2), "utf8");
console.log(`Saved builder wiring gaps audit to: ${outputPath}`);
console.log(`Results: ${auditOutput.summary.hardcodedOrEmptyCount} hardcoded/empty, ${auditOutput.summary.unreadInCanvasCount} unread in canvas, ${auditOutput.summary.uncompiledInSsrCount} uncompiled in SSR, ${auditOutput.summary.blindSpotsCount} blind spots.`);
