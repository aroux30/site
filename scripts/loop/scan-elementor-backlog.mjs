#!/usr/bin/env node
/**
 * Scans C:\Users\Administrator\Desktop\elementor recursively to map actual PHP/JS/SVG files
 * and construct the Elementor Parity Backlog (.loop/elementor_parity_backlog.json).
 */

import fs from 'node:fs';
import path from 'node:path';

const ELEMENTOR_DIR = 'C:/Users/Administrator/Desktop/elementor';
const ROOT_DIR = process.cwd();

console.log('--- Scanning Elementor Reference Repository ---');

function walkDir(dir, fileList = []) {
  if (!fs.existsSync(dir)) return fileList;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== '.git' && entry.name !== 'node_modules') {
        walkDir(fullPath, fileList);
      }
    } else {
      fileList.push(fullPath.replace(/\\/g, '/'));
    }
  }
  return fileList;
}

const allFiles = walkDir(ELEMENTOR_DIR);
console.log(`Found ${allFiles.length} files in Elementor reference repo.`);

// Filter key directories:
// 1. includes/controls/
// 2. includes/controls/groups/
// 3. includes/widgets/
// 4. assets/shapes/
// 5. core/kits/documents/tabs/
// 6. elementor-pro/modules/

const controlFiles = allFiles.filter(f => f.includes('/includes/controls/'));
const groupControlFiles = allFiles.filter(f => f.includes('/includes/controls/groups/'));
const widgetFiles = allFiles.filter(f => f.includes('/includes/widgets/'));
const shapeFiles = allFiles.filter(f => f.includes('/assets/shapes/') && f.endsWith('.svg'));
const kitTabFiles = allFiles.filter(f => f.includes('/core/kits/documents/tabs/'));
const proModuleFiles = allFiles.filter(f => f.includes('/elementor-pro/modules/'));

console.log(`- Controls: ${controlFiles.length}`);
console.log(`- Control Groups: ${groupControlFiles.length}`);
console.log(`- Widgets: ${widgetFiles.length}`);
console.log(`- Shapes (SVG): ${shapeFiles.length}`);
console.log(`- Global Kit Tabs: ${kitTabFiles.length}`);
console.log(`- Elementor Pro Modules: ${proModuleFiles.length}`);

// Build backlog items based on project specification:
// Wave 1: Professional controls, Grid container, Shape dividers, Navigator
// Wave 2: Core & Pro widgets, Popups, Off-canvas
// Wave 3: Full Site Kit, Theme Builder, Loop Builder, Multi-step Form, Import/Export

const backlog = [];
let idCounter = 1;

function addBacklogItem(wave, category, title, elementorRefPath, targetFiles) {
  const paddedId = String(idCounter++).padStart(3, '0');
  backlog.push({
    id: `EL-W${wave}-${paddedId}`,
    wave,
    category,
    title,
    elementor_ref_path: elementorRefPath,
    target_files: targetFiles,
    acceptance_signals: ['state', 'dom', 'style', 'pixels', 'ssr'],
    passes: false,
  });
}

// --- Wave 1 items ---
addBacklogItem(
  1,
  'control_group',
  'Group Control Typography (Responsive Size, LineHeight, LetterSpacing, Decoration, Transform)',
  'elementor/includes/controls/groups/typography.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/types/builder.ts', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  1,
  'control_group',
  'Group Control Background (Classic, Gradient, Video, Overlay, Blend Mode)',
  'elementor/includes/controls/groups/background.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  1,
  'control_group',
  'Group Control Border & Box Shadow with Normal/Hover transitions',
  'elementor/includes/controls/groups/border.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx']
);

addBacklogItem(
  1,
  'advanced_tab',
  'Advanced 4-Direction Spacing with Linked/Unlinked Toggle and px/rem/%/em units',
  'elementor/includes/widgets/common-base.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/types/builder.ts']
);

addBacklogItem(
  1,
  'advanced_tab',
  'Advanced CSS Transform (Rotate, Scale, Offset, Skew, Flip) in Normal & Hover',
  'elementor/includes/controls/groups/transform.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  1,
  'advanced_tab',
  'Advanced CSS Mask (Shapes: Circle, Flower, Blob, Hexagon, Custom SVG)',
  'elementor/includes/controls/groups/mask.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx']
);

addBacklogItem(
  1,
  'advanced_tab',
  'Advanced Sticky Header/Banner (Top/Bottom + Offset with z-index stacking)',
  'elementor-pro/modules/sticky/module.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx']
);

addBacklogItem(
  1,
  'advanced_tab',
  'Advanced Entrance & Motion Effects with prefers-reduced-motion compliance',
  'elementor/includes/widgets/common-base.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  1,
  'advanced_tab',
  'Advanced Custom Attributes (Key|Value lines with security blacklist and live DOM reflection)',
  'elementor-pro/modules/custom-attributes/module.php',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py', 'backend/app/shared/content/html_sanitizer.py']
);

addBacklogItem(
  1,
  'shape_divider',
  'Shape Dividers (30 SVG Shapes for Container Top/Bottom with Invert, Flip & Width/Height)',
  'elementor/assets/shapes/',
  ['frontend/components/admin/builder/inspector-panel.tsx', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  1,
  'navigator',
  'Navigator / LayersTree Inline Renaming, Visual Badges (Motion, Hidden, CustomCSS) & Context Menu',
  'elementor/includes/managers/elements.php',
  ['frontend/components/admin/builder/layers-tree.tsx']
);

// --- Wave 2 items ---
addBacklogItem(
  2,
  'widget_core',
  'Core Animated Counter Widget (Animated counting up with prefix/suffix/duration)',
  'elementor/includes/widgets/counter.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'widget_core',
  'Core Progress Bar Widget (Animated skill bar with percentage badge)',
  'elementor/includes/widgets/progress.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'widget_core',
  'Core Testimonial Box Widget (Avatar, author, company, rating, quote text)',
  'elementor/includes/widgets/testimonial.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'widget_core',
  'Core Alert Banner Widget (Dismissible info, success, warning, danger alerts)',
  'elementor/includes/widgets/alert.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'widget_pro',
  'Pro Animated Headline Widget (Rotating, typing, highlighted text with SVG shapes)',
  'elementor-pro/modules/animated-headline/widgets/animated-headline.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'widget_pro',
  'Pro Flip Box Widget (3D flip card with front and back interactive faces)',
  'elementor-pro/modules/flip-box/widgets/flip-box.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'widget_pro',
  'Pro Call To Action (CTA) Widget (Boxed banner with image, badge, ribbon, heading and button)',
  'elementor-pro/modules/call-to-action/widgets/call-to-action.php',
  ['frontend/lib/builder/block-registry.ts', 'frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  2,
  'pro_module',
  'Off-Canvas Drawer Module (Slide-in mobile navigation / filter drawer with nested container)',
  'elementor-pro/modules/off-canvas/module.php',
  ['frontend/components/admin/builder/canvas-element.tsx', 'frontend/stores/builder-store.ts']
);

addBacklogItem(
  2,
  'pro_module',
  'Popup Builder Module (Modal designer with load, scroll, exit-intent triggers)',
  'elementor-pro/modules/popup/module.php',
  ['frontend/components/admin/builder/canvas-element.tsx', 'frontend/stores/builder-store.ts']
);

// --- Wave 3 items ---
addBacklogItem(
  3,
  'site_kit',
  'Global Site Kit 12 Tabs (Colors, Typography, Buttons, Images, Form Fields, Breakpoints, Lightbox)',
  'elementor/core/kits/documents/tabs/',
  ['frontend/components/admin/builder/global-styles-dialog.tsx', 'frontend/stores/builder-store.ts']
);

addBacklogItem(
  3,
  'theme_builder',
  'Theme Builder (Header, Footer, Single Product, Product Archive with Display Conditions)',
  'elementor-pro/modules/theme-builder/module.php',
  ['frontend/components/admin/builder/builder-studio.tsx', 'backend/app/modules/content/domain/builder_ast.py']
);

addBacklogItem(
  3,
  'loop_builder',
  'Loop Builder (Custom repeating item card template for Products & Blog Posts)',
  'elementor-pro/modules/loop-builder/module.php',
  ['frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/ast_compiler.py']
);

addBacklogItem(
  3,
  'form_builder',
  'Multi-Step Form Builder with Conditional Fields and Backend Submissions',
  'elementor-pro/modules/forms/module.php',
  ['frontend/components/admin/builder/canvas-element.tsx', 'backend/app/modules/content/application/form_submission_service.py']
);

const backlogOutput = {
  version: '2.0.0',
  scanned_at: new Date().toISOString(),
  elementor_source_path: ELEMENTOR_DIR,
  total_files_scanned: allFiles.length,
  total_items: backlog.length,
  stats: {
    wave1_count: backlog.filter(b => b.wave === 1).length,
    wave2_count: backlog.filter(b => b.wave === 2).length,
    wave3_count: backlog.filter(b => b.wave === 3).length,
    passed_count: 0,
    pending_count: backlog.length,
  },
  items: backlog,
};

const outPath = path.join(ROOT_DIR, '.loop', 'elementor_parity_backlog.json');
fs.writeFileSync(outPath, JSON.stringify(backlogOutput, null, 2), 'utf8');

console.log(`Saved Elementor Parity Backlog with ${backlog.length} items to ${outPath}`);
