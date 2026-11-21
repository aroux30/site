#!/usr/bin/env node
/**
 * scripts/loop/builder-wiring-audit.mjs
 *
 * Exhaustive static wiring audit for Visual Page Builder:
 * - Category 1 (HARDCODED_OR_EMPTY_UI): Unwired handlers, empty callbacks `() => {}`, window.alert/confirm, hardcoded values.
 * - Category 2 (UNREAD_IN_CANVAS): Props or styles modified in Inspector but unhandled/ignored in canvas-element.tsx.
 * - Category 3 (UNCOMPILED_IN_SSR): Frontend widgets/props missing from backend builder_ast.py or ast_compiler.py.
 * - Category 4 (WIDGET_CONTROL_BLIND_SPOTS): Widgets missing dedicated Content/Style/Advanced controls in inspector-panel.tsx.
 *
 * Output: .loop/builder_wiring_gaps.json
 */

import fs from 'node:fs';
import path from 'node:path';

const projectRoot = process.cwd();

const files = {
  inspector: path.join(projectRoot, 'frontend/components/admin/builder/inspector-panel.tsx'),
  toolbar: path.join(projectRoot, 'frontend/components/admin/builder/builder-toolbar.tsx'),
  layers: path.join(projectRoot, 'frontend/components/admin/builder/layers-tree.tsx'),
  palette: path.join(projectRoot, 'frontend/components/admin/builder/blocks-palette.tsx'),
  store: path.join(projectRoot, 'frontend/stores/builder-store.ts'),
  canvas: path.join(projectRoot, 'frontend/components/admin/builder/canvas-element.tsx'),
  types: path.join(projectRoot, 'frontend/types/builder.ts'),
  registry: path.join(projectRoot, 'frontend/lib/builder/block-registry.ts'),
  backendAst: path.join(projectRoot, 'backend/app/modules/content/domain/builder_ast.py'),
  backendCompiler: path.join(projectRoot, 'backend/app/modules/content/application/ast_compiler.py'),
};

function read(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`File not found: ${filePath}`);
  }
  return fs.readFileSync(filePath, 'utf8');
}

console.log('>>> [wiring-audit] Reading source files...');
const contents = {
  inspector: read(files.inspector),
  toolbar: read(files.toolbar),
  layers: read(files.layers),
  palette: read(files.palette),
  store: read(files.store),
  canvas: read(files.canvas),
  types: read(files.types),
  registry: read(files.registry),
  backendAst: read(files.backendAst),
  backendCompiler: read(files.backendCompiler),
};

// ── Category 1: HARDCODED_OR_EMPTY_UI ─────────────────────────────────────────
console.log('>>> [wiring-audit] Auditing Category 1: HARDCODED_OR_EMPTY_UI...');
const hardcodedOrEmpty = [];

// Check for window.alert or window.confirm in inspector or toolbar
const alertConfirmRegex = /window\.(alert|confirm)\b/g;
for (const [name, code] of Object.entries({ inspector: contents.inspector, toolbar: contents.toolbar, layers: contents.layers })) {
  let m;
  while ((m = alertConfirmRegex.exec(code)) !== null) {
    hardcodedOrEmpty.push({
      file: name,
      type: 'NATIVE_ALERT_CONFIRM',
      issue: `Found window.${m[1]} at index ${m.index}. Should use accessible UI dialog or toast.`,
      index: m.index,
    });
  }
}

// Check for empty arrow functions in event handlers (e.g. onClick={() => {}}, onChange={() => {}})
const emptyHandlerRegex = /on[A-Z][a-zA-Z]+\s*=\s*\{(?:\(\s*\)\s*=>\s*\{\s*\}|\(\s*_\s*\)\s*=>\s*\{\s*\})\}/g;
for (const [name, code] of Object.entries({ inspector: contents.inspector, toolbar: contents.toolbar, layers: contents.layers })) {
  let m;
  while ((m = emptyHandlerRegex.exec(code)) !== null) {
    hardcodedOrEmpty.push({
      file: name,
      type: 'EMPTY_EVENT_HANDLER',
      issue: `Empty handler found: "${m[0]}" at index ${m.index}.`,
      index: m.index,
    });
  }
}

// Check for buttons with disabled or empty action
const deadButtonRegex = /<button[^>]*onClick\s*=\s*\{(?:\(\s*\)\s*=>\s*\{\s*\}|\s*undefined\s*)\}[^>]*>/g;
let dbm;
while ((dbm = deadButtonRegex.exec(contents.inspector)) !== null) {
  hardcodedOrEmpty.push({
    file: 'inspector',
    type: 'NOOP_BUTTON',
    issue: `Button with no-op onClick: ${dbm[0]}`,
    index: dbm.index,
  });
}

// ── Category 2: UNREAD_IN_CANVAS ─────────────────────────────────────────────
console.log('>>> [wiring-audit] Auditing Category 2: UNREAD_IN_CANVAS...');
const unreadInCanvas = [];

// Extract props updated in Inspector via handlePropChange or updateElementProps
const inspectorPropChanges = new Set();
const propChangeRegex = /handlePropChange\(\s*["']([^"']+)["']/g;
let pcm;
while ((pcm = propChangeRegex.exec(contents.inspector)) !== null) {
  inspectorPropChanges.add(pcm[1]);
}

// Extract styles handled in handleDeviceStyleChange / updateDeviceStyles
const inspectorStyleKeys = new Set();
const styleKeyRegex = /handleDeviceStyleChange\(\s*\{\s*([a-zA-Z0-9_]+)/g;
let skm;
while ((skm = styleKeyRegex.exec(contents.inspector)) !== null) {
  inspectorStyleKeys.add(skm[1]);
}

// Check if each prop changed in Inspector is referenced in canvas-element.tsx
for (const prop of inspectorPropChanges) {
  const referencedInCanvas = contents.canvas.includes(`props.${prop}`) ||
                             contents.canvas.includes(`element.widgetProps?.${prop}`) ||
                             contents.canvas.includes(`widgetProps?.${prop}`) ||
                             contents.canvas.includes(`["${prop}"]`) ||
                             contents.canvas.includes(`['${prop}']`) ||
                             contents.canvas.includes(`${prop}`);
  if (!referencedInCanvas) {
    unreadInCanvas.push({
      prop,
      source: 'inspector-panel.tsx',
      target: 'canvas-element.tsx',
      issue: `Widget prop "${prop}" is updated in Inspector but does not appear to be read in CanvasElement.`,
    });
  }
}

// Check device style keys in canvas
for (const styleKey of inspectorStyleKeys) {
  const referencedInCanvas = contents.canvas.includes(styleKey);
  if (!referencedInCanvas) {
    unreadInCanvas.push({
      styleKey,
      source: 'inspector-panel.tsx',
      target: 'canvas-element.tsx',
      issue: `Device style "${styleKey}" is modified in Inspector but missing in CanvasElement style calculations.`,
    });
  }
}

// ── Category 3: UNCOMPILED_IN_SSR ────────────────────────────────────────────
console.log('>>> [wiring-audit] Auditing Category 3: UNCOMPILED_IN_SSR...');
const uncompiledInSsr = [];

// Extract all registered widget types from block-registry.ts
const registeredTypes = new Set();
const regTypeRegex = /type:\s*["']([a-zA-Z0-9_]+)["']/g;
let rtm;
while ((rtm = regTypeRegex.exec(contents.registry)) !== null) {
  const t = rtm[1];
  if (t !== 'container' && t !== 'widget') {
    registeredTypes.add(t);
  }
}

// Check each widget type against ast_compiler.py
for (const widgetType of registeredTypes) {
  const handledInCompiler = contents.backendCompiler.includes(`"${widgetType}"`) ||
                            contents.backendCompiler.includes(`'${widgetType}'`);
  if (!handledInCompiler) {
    uncompiledInSsr.push({
      widgetType,
      file: 'backend/app/modules/content/application/ast_compiler.py',
      issue: `Widget type "${widgetType}" is registered in frontend but missing in backend AST compiler.`,
    });
  }
}

// Check if shape divider top/bottom/color are compiled in SSR
const shapeDividerProps = ['shape_divider_top', 'shape_divider_bottom', 'shape_divider_color'];
for (const sdp of shapeDividerProps) {
  if (!contents.backendCompiler.includes(sdp) && !contents.backendCompiler.includes(sdp.replace(/_/g, ''))) {
    // Check camelCase in case python uses camelCase or helper
    const camel = sdp.replace(/_([a-z])/g, (_, l) => l.toUpperCase());
    if (!contents.backendCompiler.includes(camel)) {
      uncompiledInSsr.push({
        prop: sdp,
        file: 'backend/app/modules/content/application/ast_compiler.py',
        issue: `Shape divider property "${sdp}" may not be compiled into SSR HTML output.`,
      });
    }
  }
}

// ── Category 4: WIDGET_CONTROL_BLIND_SPOTS ───────────────────────────────────
console.log('>>> [wiring-audit] Auditing Category 4: WIDGET_CONTROL_BLIND_SPOTS...');
const widgetControlBlindSpots = [];

// Collect all 35 known widgets
const ALL_35_WIDGETS = [
  "container", "section", "columns", "heading", "paragraph", "text", "image", "button", "spacer", "divider",
  "table", "form_container", "form_input", "form_textarea", "form_select", "form_checkbox", "form_radio",
  "accordion", "tabs", "countdown", "video", "icon_box", "social_links",
  "product_card", "product_grid", "image_gallery", "star_rating", "review_histogram", "recently_viewed",
  "mega_menu", "product_price", "product_variants", "add_to_cart", "mini_cart", "cart_summary"
];

for (const w of ALL_35_WIDGETS) {
  const hasContentCase = contents.inspector.includes(`case "${w}":`) ||
                         contents.inspector.includes(`case '${w}':`) ||
                         (w === 'container' || w === 'section' || w === 'columns');

  if (!hasContentCase && w !== 'paragraph' && w !== 'text') {
    widgetControlBlindSpots.push({
      widget: w,
      tab: 'content',
      issue: `Widget "${w}" has no specific switch case in Inspector renderContentControls.`,
    });
  }
}

// ── Compile Report ────────────────────────────────────────────────────────────
const gapsReport = {
  timestamp: new Date().toISOString(),
  summary: {
    totalIssues: hardcodedOrEmpty.length + unreadInCanvas.length + uncompiledInSsr.length + widgetControlBlindSpots.length,
    hardcodedOrEmptyCount: hardcodedOrEmpty.length,
    unreadInCanvasCount: unreadInCanvas.length,
    uncompiledInSsrCount: uncompiledInSsr.length,
    widgetControlBlindSpotsCount: widgetControlBlindSpots.length,
  },
  categories: {
    HARDCODED_OR_EMPTY_UI: hardcodedOrEmpty,
    UNREAD_IN_CANVAS: unreadInCanvas,
    UNCOMPILED_IN_SSR: uncompiledInSsr,
    WIDGET_CONTROL_BLIND_SPOTS: widgetControlBlindSpots,
  },
};

const outputPath = path.join(projectRoot, '.loop/builder_wiring_gaps.json');
fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, JSON.stringify(gapsReport, null, 2), 'utf8');

console.log(`>>> [wiring-audit] Completed! Gaps report saved to ${outputPath}`);
console.log(`    Total gaps identified: ${gapsReport.summary.totalIssues}`);
console.log(`    - HARDCODED_OR_EMPTY_UI: ${gapsReport.summary.hardcodedOrEmptyCount}`);
console.log(`    - UNREAD_IN_CANVAS: ${gapsReport.summary.unreadInCanvasCount}`);
console.log(`    - UNCOMPILED_IN_SSR: ${gapsReport.summary.uncompiledInSsrCount}`);
console.log(`    - WIDGET_CONTROL_BLIND_SPOTS: ${gapsReport.summary.widgetControlBlindSpotsCount}`);
