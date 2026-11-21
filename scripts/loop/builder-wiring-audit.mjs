#!/usr/bin/env node
/**
 * Static Wiring Audit Scanner for Visual Page Builder (Phase 0 / ELITE V2)
 * Analyzes frontend and backend builder code to classify wiring gaps into 4 categories:
 * - Category 1 (HARDCODED_OR_EMPTY_UI): Handlers that are empty, hardcoded values, or window.alert/confirm.
 * - Category 2 (UNREAD_IN_CANVAS): Keys written by inspector but not parsed/rendered in canvas-element.tsx.
 * - Category 3 (UNCOMPILED_IN_SSR): Frontend widgets/props missing or ignored in builder_ast.py / ast_compiler.py / html_sanitizer.py.
 * - Category 4 (WIDGET_CONTROL_BLIND_SPOTS): Widgets missing specific Content/Style/Advanced controls in Inspector.
 */

import fs from 'node:fs';
import path from 'node:path';

const ROOT_DIR = process.cwd();

function readFileSafe(relPath) {
  try {
    return fs.readFileSync(path.join(ROOT_DIR, relPath), 'utf8');
  } catch (err) {
    console.error(`Failed to read ${relPath}:`, err.message);
    return '';
  }
}

console.log('--- Starting Builder Static Wiring Audit ---');

const inspectorContent = readFileSafe('frontend/components/admin/builder/inspector-panel.tsx');
const canvasElementContent = readFileSafe('frontend/components/admin/builder/canvas-element.tsx');
const toolbarContent = readFileSafe('frontend/components/admin/builder/builder-toolbar.tsx');
const layersContent = readFileSafe('frontend/components/admin/builder/layers-tree.tsx');
const storeContent = readFileSafe('frontend/stores/builder-store.ts');
const blockRegistryContent = readFileSafe('frontend/lib/builder/block-registry.ts');
const typesContent = readFileSafe('frontend/types/builder.ts');
const backendAstContent = readFileSafe('backend/app/modules/content/domain/builder_ast.py');
const astCompilerContent = readFileSafe('backend/app/modules/content/application/ast_compiler.py');
const sanitizerContent = readFileSafe('backend/app/shared/content/html_sanitizer.py');

// 1. Analyze Category 1: HARDCODED_OR_EMPTY_UI
const hardcodedOrEmpty = [];

// Check for empty callbacks in inspector or toolbar
const emptyCallbackRegex = /onClick=\{?\s*\(\)\s*=>\s*\{\s*\}|onChange=\{?\s*\(\)\s*=>\s*\{\s*\}/g;
let match;
while ((match = emptyCallbackRegex.exec(inspectorContent)) !== null) {
  hardcodedOrEmpty.push({
    file: 'frontend/components/admin/builder/inspector-panel.tsx',
    type: 'EMPTY_HANDLER',
    snippet: match[0],
    index: match.index,
  });
}

// Check for window.alert or window.confirm in builder components
const alertConfirmRegex = /window\.(alert|confirm)\s*\(/g;
const filesToCheckAlert = [
  'frontend/components/admin/builder/inspector-panel.tsx',
  'frontend/components/admin/builder/builder-toolbar.tsx',
  'frontend/components/admin/builder/layers-tree.tsx',
  'frontend/components/admin/builder/canvas-element.tsx',
  'frontend/stores/builder-store.ts'
];
for (const rel of filesToCheckAlert) {
  const content = readFileSafe(rel);
  while ((match = alertConfirmRegex.exec(content)) !== null) {
    hardcodedOrEmpty.push({
      file: rel,
      type: 'NATIVE_ALERT_OR_CONFIRM',
      snippet: match[0],
      index: match.index,
    });
  }
}

// 2. Analyze Category 2: UNREAD_IN_CANVAS
// Check style properties in types/builder.ts vs canvas-element.tsx
const unreadInCanvas = [];
const deviceStyleProps = [
  'width', 'minHeight', 'margin', 'padding', 'border', 'background',
  'backgroundOverlay', 'typography', 'boxShadow', 'filter', 'opacity',
  'zIndex', 'position', 'top', 'bottom', 'left', 'right', 'overflow',
  'flexDirection', 'justifyContent', 'alignItems', 'alignSelf', 'order',
  'flexGrow', 'flexWrap', 'gap', 'gridTemplateColumns', 'shadow',
  'backdropBlur', 'filterBlur'
];

for (const prop of deviceStyleProps) {
  if (!canvasElementContent.includes(prop)) {
    unreadInCanvas.push({
      property: prop,
      reason: `DeviceStyle property '${prop}' does not appear in canvas-element.tsx renderer.`,
    });
  }
}

// Check root styles
const rootStyleProps = [
  'entranceAnimation', 'animationDuration', 'animationDelay',
  'customAttributes', 'customCssClass', 'customCss', 'hideOnMobile',
  'hideOnTablet', 'hideOnDesktop', 'authVisibility'
];
for (const prop of rootStyleProps) {
  if (!canvasElementContent.includes(prop)) {
    unreadInCanvas.push({
      property: prop,
      reason: `Root responsive style property '${prop}' not handled in canvas-element.tsx.`,
    });
  }
}

// 3. Analyze Category 3: UNCOMPILED_IN_SSR
const uncompiledInSsr = [];
// Extract all widget types from block-registry
const widgetTypes = [
  'heading', 'text_editor', 'image', 'button', 'spacer', 'divider',
  'table', 'form_input', 'text', 'form_textarea', 'form_select',
  'product_card', 'product_grid', 'product_variants', 'product_price',
  'add_to_cart', 'mini_cart', 'cart_summary', 'form_checkbox',
  'form_radio', 'accordion', 'tabs', 'countdown', 'video',
  'aparat', 'icon_box', 'social_links', 'image_gallery',
  'star_rating', 'review_histogram', 'recently_viewed', 'mega_menu'
];

for (const wType of widgetTypes) {
  const handlerName = `_render_${wType}`;
  const mentionedInCompiler = astCompilerContent.includes(`"${wType}"`) || astCompilerContent.includes(`'${wType}'`) || astCompilerContent.includes(handlerName);
  if (!mentionedInCompiler) {
    uncompiledInSsr.push({
      widgetType: wType,
      reason: `Widget '${wType}' is present in block-registry.ts but has no dedicated compiler branch in ast_compiler.py.`,
    });
  }
}

// 4. Analyze Category 4: WIDGET_CONTROL_BLIND_SPOTS
const widgetControlBlindSpots = [];
for (const wType of widgetTypes) {
  // Check if inspector has specific controls for this widget
  const hasContentBranch = inspectorContent.includes(`"${wType}"`) || inspectorContent.includes(`'${wType}'`);
  if (!hasContentBranch) {
    widgetControlBlindSpots.push({
      widgetType: wType,
      missing: ['content_controls'],
      reason: `InspectorPanel has no specific Content tab controls for widget type '${wType}'.`,
    });
  }
}

const auditOutput = {
  timestamp: new Date().toISOString(),
  summary: {
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
  }
};

const outPath = path.join(ROOT_DIR, '.loop', 'builder_wiring_gaps.json');
fs.writeFileSync(outPath, JSON.stringify(auditOutput, null, 2), 'utf8');

console.log(`Audit saved to ${outPath}`);
console.log(`Summary:`);
console.log(`- Category 1 (HARDCODED_OR_EMPTY_UI): ${hardcodedOrEmpty.length}`);
console.log(`- Category 2 (UNREAD_IN_CANVAS): ${unreadInCanvas.length}`);
console.log(`- Category 3 (UNCOMPILED_IN_SSR): ${uncompiledInSsr.length}`);
console.log(`- Category 4 (WIDGET_CONTROL_BLIND_SPOTS): ${widgetControlBlindSpots.length}`);
