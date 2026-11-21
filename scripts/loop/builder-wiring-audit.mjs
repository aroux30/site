#!/usr/bin/env node
/**
 * scripts/loop/builder-wiring-audit.mjs
 *
 * Static code analyzer that maps and verifies wiring between:
 * - Inspector Panel UI (`inspector-panel.tsx`)
 * - Builder Store (`builder-store.ts`)
 * - Canvas Rendering (`canvas-element.tsx`)
 * - Backend AST and SSR Compiler (`builder_ast.py`, `ast_compiler.py`, `html_sanitizer.py`)
 *
 * Produces: `.loop/builder_wiring_gaps.json` with 4 definitive categories:
 * 1. HARDCODED_OR_EMPTY_UI
 * 2. UNREAD_IN_CANVAS
 * 3. UNCOMPILED_IN_SSR
 * 4. WIDGET_CONTROL_BLIND_SPOTS
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "../..");

const files = {
  inspector: path.join(projectRoot, "frontend/components/admin/builder/inspector-panel.tsx"),
  toolbar: path.join(projectRoot, "frontend/components/admin/builder/builder-toolbar.tsx"),
  layers: path.join(projectRoot, "frontend/components/admin/builder/layers-tree.tsx"),
  palette: path.join(projectRoot, "frontend/components/admin/builder/blocks-palette.tsx"),
  store: path.join(projectRoot, "frontend/stores/builder-store.ts"),
  canvas: path.join(projectRoot, "frontend/components/admin/builder/canvas-element.tsx"),
  types: path.join(projectRoot, "frontend/types/builder.ts"),
  blockRegistry: path.join(projectRoot, "frontend/lib/builder/block-registry.ts"),
  backendAst: path.join(projectRoot, "backend/app/modules/content/domain/builder_ast.py"),
  backendCompiler: path.join(projectRoot, "backend/app/modules/content/application/ast_compiler.py"),
  backendSanitizer: path.join(projectRoot, "backend/app/shared/content/html_sanitizer.py"),
};

// Check all files exist
for (const [key, filePath] of Object.entries(files)) {
  if (!fs.existsSync(filePath)) {
    console.error(`[ERROR] File missing for ${key}: ${filePath}`);
    process.exit(1);
  }
}

const inspectorCode = fs.readFileSync(files.inspector, "utf8");
const toolbarCode = fs.readFileSync(files.toolbar, "utf8");
const layersCode = fs.readFileSync(files.layers, "utf8");
const paletteCode = fs.readFileSync(files.palette, "utf8");
const storeCode = fs.readFileSync(files.store, "utf8");
const canvasCode = fs.readFileSync(files.canvas, "utf8");
const typesCode = fs.readFileSync(files.types, "utf8");
const registryCode = fs.readFileSync(files.blockRegistry, "utf8");
const backendAstCode = fs.readFileSync(files.backendAst, "utf8");
const backendCompilerCode = fs.readFileSync(files.backendCompiler, "utf8");
const backendSanitizerCode = fs.readFileSync(files.backendSanitizer, "utf8");

console.log(">>> [Wiring-Audit] Analyzing builder files...");

// ── 1. HARDCODED_OR_EMPTY_UI ────────────────────────────────────────────────
const hardcodedOrEmpty = [];

// Look for empty handlers `() => {}` in inspector and toolbar
const emptyHandlerRegex = /(?:onClick|onChange|onValueChange|onSelect|onCheckedChange)\s*=\s*\{\s*\(\s*[^)]*\s*\)\s*=>\s*\{\s*\}\s*\}/g;
let match;
while ((match = emptyHandlerRegex.exec(inspectorCode)) !== null) {
  const line = inspectorCode.substring(0, match.index).split("\n").length;
  hardcodedOrEmpty.push({
    file: "inspector-panel.tsx",
    line,
    match: match[0],
    issue: "EMPTY_CALLBACK_HANDLER",
    detail: "Handler does nothing when triggered",
  });
}

while ((match = emptyHandlerRegex.exec(toolbarCode)) !== null) {
  const line = toolbarCode.substring(0, match.index).split("\n").length;
  hardcodedOrEmpty.push({
    file: "builder-toolbar.tsx",
    line,
    match: match[0],
    issue: "EMPTY_CALLBACK_HANDLER",
    detail: "Handler does nothing when triggered",
  });
}

// Check for window.alert / window.confirm
const alertConfirmRegex = /(?:window\.)?(alert|confirm)\s*\(/g;
while ((match = alertConfirmRegex.exec(inspectorCode)) !== null) {
  const line = inspectorCode.substring(0, match.index).split("\n").length;
  hardcodedOrEmpty.push({
    file: "inspector-panel.tsx",
    line,
    match: match[0],
    issue: "NATIVE_ALERT_CONFIRM_TRAP",
    detail: "Uses synchronous window.alert/confirm which fails or blocks in sandboxed iframes",
  });
}

while ((match = alertConfirmRegex.exec(toolbarCode)) !== null) {
  const line = toolbarCode.substring(0, match.index).split("\n").length;
  hardcodedOrEmpty.push({
    file: "builder-toolbar.tsx",
    line,
    match: match[0],
    issue: "NATIVE_ALERT_CONFIRM_TRAP",
    detail: "Uses synchronous window.alert/confirm which fails or blocks in sandboxed iframes",
  });
}

// ── 2. UNREAD_IN_CANVAS ─────────────────────────────────────────────────────
const unreadInCanvas = [];

// Extract all style and prop keys manipulated in inspector
const propChangeRegex = /handlePropChange\s*\(\s*["']([^"']+)["']/g;
const inspectorProps = new Set();
while ((match = propChangeRegex.exec(inspectorCode)) !== null) {
  inspectorProps.add(match[1]);
}

// Check if each prop is actually referenced in canvas-element.tsx
for (const prop of inspectorProps) {
  const propRefRegex = new RegExp(`(?:props\\.${prop}|props\\[["']${prop}["']\\]|widgetProps\\?.${prop})`, "g");
  if (!propRefRegex.test(canvasCode) && !canvasCode.includes(`"${prop}"`) && !canvasCode.includes(`'${prop}'`)) {
    unreadInCanvas.push({
      prop,
      source: "inspector-panel.tsx",
      target: "canvas-element.tsx",
      issue: "PROP_NOT_RENDERED_IN_CANVAS",
      detail: `Property "${prop}" is edited in Inspector but never read in CanvasElementComponent`,
    });
  }
}

// Check device style attributes
const deviceStyleKeys = [
  "margin", "padding", "border", "background", "backgroundOverlay",
  "width", "minHeight", "filter", "opacity", "zIndex", "boxShadow",
  "position", "top", "bottom", "left", "right", "overflow",
  "alignSelf", "order", "flexGrow", "backdropBlur", "filterBlur"
];
for (const styleKey of deviceStyleKeys) {
  if (!canvasCode.includes(styleKey)) {
    unreadInCanvas.push({
      styleKey,
      source: "frontend/types/builder.ts",
      target: "canvas-element.tsx",
      issue: "STYLE_KEY_IGNORED_IN_CANVAS",
      detail: `DeviceStyle key "${styleKey}" is defined in types but not applied in CanvasElement style computation`,
    });
  }
}

// ── 3. UNCOMPILED_IN_SSR ────────────────────────────────────────────────────
const uncompiledInSsr = [];

// Get all 35 widgets and blocks
const all35Widgets = [
  "container", "section", "columns", "heading", "text_editor", "image", "button", "spacer", "divider",
  "table", "form_container", "form_input", "form_textarea", "form_select", "form_checkbox", "form_radio",
  "accordion", "tabs", "countdown", "video", "icon_box", "social_links",
  "product_card", "product_grid", "image_gallery", "star_rating", "review_histogram", "recently_viewed",
  "mega_menu", "product_price", "product_variants", "add_to_cart", "mini_cart", "cart_summary"
];

for (const wType of all35Widgets) {
  // Check if handled in ast_compiler.py
  const isContainerType = ["container", "section", "columns", "form_container"].includes(wType);
  if (isContainerType) {
    if (!backendCompilerCode.includes("_compile_container")) {
      uncompiledInSsr.push({
        widgetType: wType,
        issue: "CONTAINER_UNCOMPILED_IN_SSR",
        detail: `Container type "${wType}" missing dedicated compilation logic in ast_compiler.py`,
      });
    }
  } else {
    const handledInCompiler = backendCompilerCode.includes(`widget_type == "${wType}"`) ||
                              backendCompilerCode.includes(`widget_type in ("${wType}"`) ||
                              backendCompilerCode.includes(`"${wType}"`);
    if (!handledInCompiler) {
      uncompiledInSsr.push({
        widgetType: wType,
        issue: "WIDGET_UNCOMPILED_IN_SSR",
        detail: `Widget type "${wType}" is defined in frontend but not handled in ASTCompiler._compile_widget`,
      });
    }
  }
}

// Check sanitizer tags for forms/inputs
const requiredTags = ["form", "input", "textarea", "select", "option", "table", "button"];
for (const tag of requiredTags) {
  if (!backendSanitizerCode.includes(`"${tag}"`)) {
    uncompiledInSsr.push({
      tag,
      issue: "SANITIZER_TAG_STRIPPED",
      detail: `HTML tag <${tag}> is not in html_sanitizer.py ALLOWED_TAGS and will be dropped on SSR output`,
    });
  }
}

// ── 4. WIDGET_CONTROL_BLIND_SPOTS ───────────────────────────────────────────
const widgetBlindSpots = [];

// For each widget, verify if inspector has a dedicated case in `renderContentControls`
for (const wType of all35Widgets) {
  const isContainer = ["container", "section", "columns"].includes(wType);
  if (!isContainer) {
    const hasCase = inspectorCode.includes(`case "${wType}":`);
    if (!hasCase) {
      widgetBlindSpots.push({
        widgetType: wType,
        missingTab: "content",
        issue: "MISSING_DEDICATED_CONTENT_CONTROLS",
        detail: `Widget "${wType}" falls back to default message in Inspector Content Tab`,
      });
    }
  }
}

const report = {
  timestamp: new Date().toISOString(),
  summary: {
    hardcodedOrEmptyCount: hardcodedOrEmpty.length,
    unreadInCanvasCount: unreadInCanvas.length,
    uncompiledInSsrCount: uncompiledInSsr.length,
    widgetBlindSpotsCount: widgetBlindSpots.length,
    totalGaps: hardcodedOrEmpty.length + unreadInCanvas.length + uncompiledInSsr.length + widgetBlindSpots.length,
  },
  categories: {
    HARDCODED_OR_EMPTY_UI: hardcodedOrEmpty,
    UNREAD_IN_CANVAS: unreadInCanvas,
    UNCOMPILED_IN_SSR: uncompiledInSsr,
    WIDGET_CONTROL_BLIND_SPOTS: widgetBlindSpots,
  },
};

const outputPath = path.join(projectRoot, ".loop/builder_wiring_gaps.json");
fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), "utf8");

console.log(`>>> [Wiring-Audit] Complete. Gaps written to ${outputPath}`);
console.log(`    - HARDCODED_OR_EMPTY_UI   : ${hardcodedOrEmpty.length}`);
console.log(`    - UNREAD_IN_CANVAS        : ${unreadInCanvas.length}`);
console.log(`    - UNCOMPILED_IN_SSR       : ${uncompiledInSsr.length}`);
console.log(`    - WIDGET_CONTROL_BLIND_SPOTS: ${widgetBlindSpots.length}`);
console.log(`    Total gaps indexed: ${report.summary.totalGaps}`);
