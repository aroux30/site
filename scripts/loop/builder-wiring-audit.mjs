import fs from 'node:fs';
import path from 'node:path';

const ROOT_DIR = process.cwd();

// Paths to analyze
const PATHS = {
  inspectorPanel: path.join(ROOT_DIR, 'frontend/components/admin/builder/inspector-panel.tsx'),
  builderToolbar: path.join(ROOT_DIR, 'frontend/components/admin/builder/builder-toolbar.tsx'),
  layersTree: path.join(ROOT_DIR, 'frontend/components/admin/builder/layers-tree.tsx'),
  blocksPalette: path.join(ROOT_DIR, 'frontend/components/admin/builder/blocks-palette.tsx'),
  builderStore: path.join(ROOT_DIR, 'frontend/stores/builder-store.ts'),
  canvasElement: path.join(ROOT_DIR, 'frontend/components/admin/builder/canvas-element.tsx'),
  typesBuilder: path.join(ROOT_DIR, 'frontend/types/builder.ts'),
  builderAstPy: path.join(ROOT_DIR, 'backend/app/modules/content/domain/builder_ast.py'),
  astCompilerPy: path.join(ROOT_DIR, 'backend/app/modules/content/application/ast_compiler.py'),
  blockRegistry: path.join(ROOT_DIR, 'frontend/lib/builder/block-registry.ts'),
};

const ALL_35_WIDGETS = [
  // 10 Basic & Layout
  "container", "section", "columns", "heading", "text_editor", "image", "button", "spacer", "divider", "table",
  // 13 Interactive / Form
  "form_container", "form_input", "form_textarea", "form_select", "form_checkbox", "form_radio",
  "accordion", "tabs", "countdown", "video", "icon_box", "social_links", "html_custom",
  // 12 Shop / Commerce
  "product_card", "product_grid", "image_gallery", "star_rating", "review_histogram", "recently_viewed",
  "mega_menu", "product_price", "product_variants", "add_to_cart", "mini_cart", "cart_summary"
];

function runWiringAudit() {
  console.log('>>> Running Builder Static Wiring Audit...');

  const inspectorContent = fs.readFileSync(PATHS.inspectorPanel, 'utf-8');
  const canvasContent = fs.readFileSync(PATHS.canvasElement, 'utf-8');
  const storeContent = fs.readFileSync(PATHS.builderStore, 'utf-8');
  const astPyContent = fs.readFileSync(PATHS.builderAstPy, 'utf-8');
  const compilerPyContent = fs.readFileSync(PATHS.astCompilerPy, 'utf-8');
  const toolbarContent = fs.readFileSync(PATHS.builderToolbar, 'utf-8');
  const layersContent = fs.readFileSync(PATHS.layersTree, 'utf-8');

  // Category 1: HARDCODED_OR_EMPTY_UI
  // Check for () => {}, empty onClick/onChange, window.alert/confirm, or static un-wired buttons
  const hardcodedOrEmptyUI = [];

  // Check alert / confirm
  const alertMatches = inspectorContent.match(/window\.(alert|confirm)\([^)]*\)/g) || [];
  for (const m of alertMatches) {
    hardcodedOrEmptyUI.push({
      file: 'inspector-panel.tsx',
      issue: 'Native window dialog usage',
      codeSnippet: m,
    });
  }

  // Check empty arrow handlers in inspector
  const emptyHandlerMatches = inspectorContent.match(/(?:onClick|onChange|onValueChange|onCheckedChange)\s*=\s*\{\s*\(\s*\)\s*=>\s*\{\s*\}\s*\}/g) || [];
  for (const m of emptyHandlerMatches) {
    hardcodedOrEmptyUI.push({
      file: 'inspector-panel.tsx',
      issue: 'Empty handler callback (() => {})',
      codeSnippet: m,
    });
  }

  // Check for known no-op placeholders or hardcoded controls
  const hardcodedCheck = [
    { name: 'motionEffectsHover', pattern: /hoverAnimation/ },
    { name: 'customCssLint', pattern: /customCssErrors/ },
    { name: 'shapeDividerBottomOffset', pattern: /shapeDividerBottomOffset/ },
  ];

  for (const check of hardcodedCheck) {
    if (inspectorContent.includes(check.name)) {
      if (!canvasContent.includes(check.name)) {
        hardcodedOrEmptyUI.push({
          file: 'inspector-panel.tsx',
          issue: `Control '${check.name}' present in inspector but not connected`,
          codeSnippet: check.name,
        });
      }
    }
  }

  // Category 2: UNREAD_IN_CANVAS
  // Detect styles or props updated in store by InspectorPanel that are not consumed in canvas-element.tsx
  const unreadInCanvas = [];

  // Inspect styles properties:
  const stylePropsInInspector = [
    'letterSpacing', 'textTransform', 'textDecoration',
    'filterBlur', 'backdropBlur', 'overflow',
    'top', 'bottom', 'left', 'right', 'position'
  ];

  for (const prop of stylePropsInInspector) {
    const isWritten = inspectorContent.includes(prop);
    const isReadInCanvas = canvasContent.includes(prop) || canvasContent.includes(`styleObj.${prop}`) || canvasContent.includes(`styles.${prop}`);
    if (isWritten && !isReadInCanvas) {
      unreadInCanvas.push({
        property: prop,
        source: 'inspector-panel.tsx',
        destination: 'canvas-element.tsx',
        description: `Property '${prop}' is edited in Inspector but not converted to DOM/CSS in canvas element styles.`
      });
    }
  }

  // Category 3: UNCOMPILED_IN_SSR
  // Detect widgets or props rendered on frontend canvas that are missing or ignored in ast_compiler.py
  const uncompiledInSSR = [];

  for (const w of ALL_35_WIDGETS) {
    const inCanvas = canvasContent.includes(`widgetType === "${w}"`) || canvasContent.includes(`widget_type == "${w}"`) || canvasContent.includes(w);
    const inCompiler = compilerPyContent.includes(`widget_type == "${w}"`) ||
      (compilerPyContent.includes('widget_type in') && compilerPyContent.includes(`"${w}"`)) ||
      (w === "columns" || w === "section" || w === "container");
    if (!inCompiler) {
      uncompiledInSSR.push({
        widgetType: w,
        issue: `Widget '${w}' has frontend implementation but is not compiled in backend ast_compiler.py`,
      });
    }
  }

  // Check style properties compiled in SSR vs frontend
  const ssrStylesCheck = [
    { prop: 'filter', pyField: 'filter' },
    { prop: 'boxShadow', pyField: 'box_shadow' },
    { prop: 'backgroundOverlay', pyField: 'background_overlay' },
    { prop: 'backdropBlur', pyField: 'backdrop_blur' },
    { prop: 'zIndex', pyField: 'z_index' },
  ];

  for (const item of ssrStylesCheck) {
    if (!compilerPyContent.includes(item.pyField)) {
      uncompiledInSSR.push({
        property: item.prop,
        issue: `Style property '${item.prop}' (${item.pyField}) is not compiled into HTML attributes or styles in ast_compiler.py`,
      });
    }
  }

  // Category 4: WIDGET_CONTROL_BLIND_SPOTS
  // Check which of the 35 widgets in Content, Style, or Advanced tabs lack dedicated controls
  const widgetControlBlindSpots = [];

  for (const w of ALL_35_WIDGETS) {
    if (w === "container" || w === "section" || w === "columns") continue;

    // Check if inspector handles this widgetType in switch case
    const hasContentCase = inspectorContent.includes(`case "${w}":`);
    if (!hasContentCase) {
      widgetControlBlindSpots.push({
        widgetType: w,
        tab: 'content',
        issue: `Widget '${w}' lacks a dedicated 'case "${w}":' block in InspectorPanel Content tab. Falls back to default/empty.`
      });
    }
  }

  const results = {
    timestamp: new Date().toISOString(),
    summary: {
      hardcodedOrEmptyCount: hardcodedOrEmptyUI.length,
      unreadInCanvasCount: unreadInCanvas.length,
      uncompiledInSSRCount: uncompiledInSSR.length,
      widgetControlBlindSpotsCount: widgetControlBlindSpots.length,
    },
    gaps: {
      HARDCODED_OR_EMPTY_UI: hardcodedOrEmptyUI,
      UNREAD_IN_CANVAS: unreadInCanvas,
      UNCOMPILED_IN_SSR: uncompiledInSSR,
      WIDGET_CONTROL_BLIND_SPOTS: widgetControlBlindSpots,
    }
  };

  const outputPath = path.join(ROOT_DIR, '.loop/builder_wiring_gaps.json');
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf-8');
  console.log(`>>> Written wiring gaps to ${outputPath}`);
  console.log(`    - Category 1 (HARDCODED_OR_EMPTY_UI): ${hardcodedOrEmptyUI.length}`);
  console.log(`    - Category 2 (UNREAD_IN_CANVAS): ${unreadInCanvas.length}`);
  console.log(`    - Category 3 (UNCOMPILED_IN_SSR): ${uncompiledInSSR.length}`);
  console.log(`    - Category 4 (WIDGET_CONTROL_BLIND_SPOTS): ${widgetControlBlindSpots.length}`);

  return results;
}

runWiringAudit();
