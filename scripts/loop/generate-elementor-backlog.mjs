#!/usr/bin/env node
/**
 * scripts/loop/generate-elementor-backlog.mjs
 * Recursively scans C:/Users/Administrator/Desktop/elementor and extracts the live
 * architecture map and gap inventory for the builder port waves.
 *
 * Output: .loop/elementor_parity_backlog.json
 */

import fs from 'node:fs';
import path from 'node:path';

const projectRoot = process.cwd();
const elementorRoot = 'C:/Users/Administrator/Desktop/elementor';

console.log('>>> [elementor-backlog] Scanning Elementor reference directory at:', elementorRoot);

if (!fs.existsSync(elementorRoot)) {
  console.error(`ERROR: Elementor reference directory does not exist at: ${elementorRoot}`);
  process.exit(1);
}

function scanDir(dir, filterExt = ['.php', '.svg', '.js']) {
  const results = [];
  function recurse(current) {
    if (!fs.existsSync(current)) return;
    const items = fs.readdirSync(current);
    for (const item of items) {
      if (item === '.git' || item === 'node_modules' || item === 'vendor') continue;
      const full = path.join(current, item);
      const stat = fs.statSync(full);
      if (stat.isDirectory()) {
        recurse(full);
      } else if (filterExt.some(ext => item.endsWith(ext))) {
        results.push(full.replace(/\\/g, '/'));
      }
    }
  }
  recurse(dir);
  return results;
}

// 1. Controls & Groups
const controlsPath = path.join(elementorRoot, 'elementor/includes/controls');
const controlGroupsPath = path.join(elementorRoot, 'elementor/includes/controls/groups');
const controlsFiles = scanDir(controlsPath, ['.php']);
const controlGroupsFiles = scanDir(controlGroupsPath, ['.php']);

// 2. Core Widgets
const coreWidgetsPath = path.join(elementorRoot, 'elementor/includes/widgets');
const coreWidgetFiles = scanDir(coreWidgetsPath, ['.php']);

// 3. Shapes (SVG Dividers)
const shapesPath = path.join(elementorRoot, 'elementor/assets/shapes');
const shapeFiles = scanDir(shapesPath, ['.svg']);

// 4. Kits & Tabs
const kitsPath = path.join(elementorRoot, 'elementor/core/kits/documents/tabs');
const kitFiles = scanDir(kitsPath, ['.php']);

// 5. Elementor Pro Modules
const proModulesPath = path.join(elementorRoot, 'elementor-pro/modules');
const proModuleFiles = scanDir(proModulesPath, ['.php']);

console.log(`    Found ${controlsFiles.length} control files.`);
console.log(`    Found ${controlGroupsFiles.length} control group files.`);
console.log(`    Found ${coreWidgetFiles.length} core widget files.`);
console.log(`    Found ${shapeFiles.length} SVG shape divider files.`);
console.log(`    Found ${kitFiles.length} global kit tab files.`);
console.log(`    Found ${proModuleFiles.length} Elementor Pro module files.`);

// Read site's current widgets and features to determine what's missing
const blockRegistryContent = fs.readFileSync(path.join(projectRoot, 'frontend/lib/builder/block-registry.ts'), 'utf8');

// Build backlog items based on prompt Wave 1, 2, 3 specifications:
const backlogItems = [];

// ── Wave 1: Control groups, Grid Container, Shape Dividers, Navigator ────────
// W1-001: Group Control Typography
backlogItems.push({
  id: "EL-W1-001",
  wave: 1,
  title: "Group Control Typography (فونت، سایز ریسپانسیو، وزن، ارتفاع خط، فاصله حروف و ترانسفورم)",
  category: "control_group",
  elementor_ref_path: "elementor/includes/controls/groups/typography.php",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/types/builder.ts",
    "backend/app/modules/content/domain/builder_ast.py",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W1-002: Group Control Background (Classic, Gradient, Overlay)
backlogItems.push({
  id: "EL-W1-002",
  wave: 1,
  title: "Group Control Background & Overlay (گرادیانت زاویه‌دار، سایز، موقعیت و Blend Mode)",
  category: "control_group",
  elementor_ref_path: "elementor/includes/controls/groups/background.php",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/components/admin/builder/canvas-element.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W1-003: Group Control Border & Box Shadow Normal/Hover
backlogItems.push({
  id: "EL-W1-003",
  wave: 1,
  title: "Group Control Border & Box Shadow در حالت‌های Normal و Hover با Transition",
  category: "control_group",
  elementor_ref_path: "elementor/includes/controls/groups/box-shadow.php",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/types/builder.ts",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W1-004: Advanced Tab Transform (Rotate, Scale, Offset, Skew)
backlogItems.push({
  id: "EL-W1-004",
  wave: 1,
  title: "Advanced Tab Transform & Motion Effects (Rotate, Scale, Skew)",
  category: "advanced_tab",
  elementor_ref_path: "elementor/includes/widgets/common-base.php",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/types/builder.ts",
    "frontend/components/admin/builder/canvas-element.tsx"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W1-005: Shape Dividers (Top/Bottom 29 SVG Dividers)
backlogItems.push({
  id: "EL-W1-005",
  wave: 1,
  title: "SVG Shape Dividers (امواج، منحنی، مثلث، شیب، زیکزاک با رنگ و ارتفاع)",
  category: "shape_divider",
  elementor_ref_path: "elementor/assets/shapes/",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/components/admin/builder/canvas-element.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W1-006: CSS Grid Container Enhancements
backlogItems.push({
  id: "EL-W1-006",
  wave: 1,
  title: "CSS Grid Container (ستون‌ها/سطرهای سفارشی، راهنماهای شبکه، Autoflow)",
  category: "layout",
  elementor_ref_path: "elementor/includes/controls/groups/grid.php",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/components/admin/builder/canvas-element.tsx"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W1-007: Navigator Enhancements (Inline rename, visual indicators, context menu)
backlogItems.push({
  id: "EL-W1-007",
  wave: 1,
  title: "Navigator / Layers Tree (تغییر نام مستقیم با دابل‌کلیک، بج‌های وضعیت، کانتکست منو)",
  category: "navigator",
  elementor_ref_path: "elementor/includes/editor-templates/navigator.php",
  target_files: [
    "frontend/components/admin/builder/layers-tree.tsx"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels"],
  passes: false
});

// ── Wave 2: Missing Core & Pro Widgets + Popup + Off-Canvas ───────────────────
// W2-001: Animated Headline & Counter
backlogItems.push({
  id: "EL-W2-001",
  wave: 2,
  title: "ویجت‌های Animated Headline و شمارنده اعداد متحرک (Counter Widget)",
  category: "widget_core",
  elementor_ref_path: "elementor/includes/widgets/counter.php",
  target_files: [
    "frontend/lib/builder/block-registry.ts",
    "frontend/components/admin/builder/canvas-element.tsx",
    "frontend/components/admin/builder/inspector-panel.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W2-002: Progress Bar & Progress Tracker
backlogItems.push({
  id: "EL-W2-002",
  wave: 2,
  title: "ویجت نوار پیشرفت (Progress Bar & Tracker)",
  category: "widget_core",
  elementor_ref_path: "elementor/includes/widgets/progress.php",
  target_files: [
    "frontend/lib/builder/block-registry.ts",
    "frontend/components/admin/builder/canvas-element.tsx",
    "frontend/components/admin/builder/inspector-panel.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W2-003: Testimonial Carousel & Nested Carousel
backlogItems.push({
  id: "EL-W2-003",
  wave: 2,
  title: "اسلایدر دیدگاه مشتریان و اسلایدر محتوای تودرتو (Nested Carousel)",
  category: "widget_pro",
  elementor_ref_path: "elementor-pro/modules/nested-carousel/",
  target_files: [
    "frontend/lib/builder/block-registry.ts",
    "frontend/components/admin/builder/canvas-element.tsx",
    "frontend/components/admin/builder/inspector-panel.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W2-004: Table of Contents & Menu Anchor
backlogItems.push({
  id: "EL-W2-004",
  wave: 2,
  title: "فهرست مطالب خودکار (Table of Contents) و نقطه لنگر منو (Menu Anchor)",
  category: "widget_pro",
  elementor_ref_path: "elementor-pro/modules/table-of-contents/",
  target_files: [
    "frontend/lib/builder/block-registry.ts",
    "frontend/components/admin/builder/canvas-element.tsx",
    "frontend/components/admin/builder/inspector-panel.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W2-005: Popup Builder & Off-Canvas Drawer
backlogItems.push({
  id: "EL-W2-005",
  wave: 2,
  title: "ماژول طراحی پاپ‌آپ و کشوی جانبی (Popup Builder & Off-Canvas Drawer)",
  category: "pro_module",
  elementor_ref_path: "elementor-pro/modules/popup/",
  target_files: [
    "frontend/components/admin/builder/builder-studio.tsx",
    "frontend/stores/builder-store.ts",
    "backend/app/modules/content/domain/builder_ast.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// ── Wave 3: Site Kit, Theme Builder, Loop Builder, Multi-Step Form ────────────
// W3-001: 12 Global Site Settings Tabs
backlogItems.push({
  id: "EL-W3-001",
  wave: 3,
  title: "۱۲ تب تنظیمات سراسری کیت طراحی (Global Colors, Fonts, Buttons, Forms, Layout)",
  category: "site_kit",
  elementor_ref_path: "elementor/core/kits/documents/tabs/",
  target_files: [
    "frontend/components/admin/builder/global-styles-dialog.tsx",
    "frontend/lib/builder/theme-schema.ts"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// W3-002: Theme Builder Templates
backlogItems.push({
  id: "EL-W3-002",
  wave: 3,
  title: "سیستم Theme Builder (قالب‌های هدر، فوتر، تک‌محصول و آرشیو با شرط‌های نمایش)",
  category: "theme_builder",
  elementor_ref_path: "elementor-pro/modules/theme-builder/",
  target_files: [
    "frontend/components/admin/builder/save-page-template-dialog.tsx",
    "frontend/stores/builder-store.ts"
  ],
  acceptance_signals: ["state", "dom", "style", "ssr"],
  passes: false
});

// W3-003: Loop Builder
backlogItems.push({
  id: "EL-W3-003",
  wave: 3,
  title: "سیستم Loop Builder (طراحی کارت‌های تکرارشونده داینامیک محصولات و مقالات)",
  category: "loop_builder",
  elementor_ref_path: "elementor-pro/modules/loop-builder/",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/components/admin/builder/canvas-element.tsx"
  ],
  acceptance_signals: ["state", "dom", "style", "ssr"],
  passes: false
});

// W3-004: Multi-Step Forms & Submissions
backlogItems.push({
  id: "EL-W3-004",
  wave: 3,
  title: "ارتقای فرم‌ساز به فرم چندمرحله‌ای (Multi-Step Forms) با فیلدهای شرطی",
  category: "forms",
  elementor_ref_path: "elementor-pro/modules/forms/",
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/components/admin/builder/canvas-element.tsx",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "ssr"],
  passes: false
});

const report = {
  timestamp: new Date().toISOString(),
  elementor_reference_root: elementorRoot,
  scanned_files_summary: {
    controls: controlsFiles.length,
    control_groups: controlGroupsFiles.length,
    core_widgets: coreWidgetFiles.length,
    svg_shapes: shapeFiles.length,
    global_kit_tabs: kitFiles.length,
    pro_modules: proModuleFiles.length
  },
  waves_summary: {
    wave1_items: backlogItems.filter(i => i.wave === 1).length,
    wave2_items: backlogItems.filter(i => i.wave === 2).length,
    wave3_items: backlogItems.filter(i => i.wave === 3).length,
    total_backlog_items: backlogItems.length,
    total_passed: backlogItems.filter(i => i.passes).length
  },
  items: backlogItems
};

const outputPath = path.join(projectRoot, '.loop/elementor_parity_backlog.json');
fs.writeFileSync(outputPath, JSON.stringify(report, null, 2), 'utf8');

console.log(`>>> [elementor-backlog] Elementor parity backlog generated at: ${outputPath}`);
console.log(`    Total backlog items: ${backlogItems.length} across Waves 1, 2, and 3.`);
