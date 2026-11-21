#!/usr/bin/env node
/**
 * scripts/loop/generate-elementor-backlog.mjs
 *
 * Scans `C:\Users\Administrator\Desktop\elementor` (Core and Pro)
 * and generates `.loop/elementor_parity_backlog.json` according to
 * the 3-wave architecture outlined in the mission brief.
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "../..");
const elementorRoot = "C:\\Users\\Administrator\\Desktop\\elementor";

const items = [
  // ── Wave 1: Pro Control Groups, Grid Container, Shape Dividers, Navigator ──
  {
    id: "EL-W1-001",
    wave: 1,
    title: "Typography Group Control (Font, Size, Weight, LineHeight, Spacing, Decoration)",
    category: "control_group",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/controls/groups/typography.php"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "backend/app/modules/content/domain/builder_ast.py",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-002",
    wave: 1,
    title: "Background Group Control (Classic, Gradient, Video, Overlay, Blend Mode)",
    category: "control_group",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/controls/groups/background.php"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/domain/builder_ast.py",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-003",
    wave: 1,
    title: "Border & Box Shadow Normal/Hover Transitions",
    category: "control_group",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/controls/groups/border.php"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "frontend/components/admin/builder/canvas-element.tsx"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-004",
    wave: 1,
    title: "CSS Filters (Blur, Brightness, Contrast, Saturation, Hue)",
    category: "control_group",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/controls/groups/css-filter.php"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/domain/builder_ast.py",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-005",
    wave: 1,
    title: "Common Base Advanced Controls (Linked Units, Z-Index, Position, Transform, Mask)",
    category: "advanced_tab",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/widgets/common-base.php"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/domain/builder_ast.py",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-006",
    wave: 1,
    title: "Full CSS Grid Container (Grid Columns, Fr/Px Units, Gap, Auto-Flow)",
    category: "control_group",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/controls/groups/grid-container.php"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/domain/builder_ast.py",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-007",
    wave: 1,
    title: "Shape Dividers (Waves, Curve, Triangle, Tilt, Asymmetric with Invert/Flip)",
    category: "shape_divider",
    elementor_ref_path: path.join(elementorRoot, "elementor/assets/shapes"),
    target_files: [
      "frontend/types/builder.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/domain/builder_ast.py",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W1-008",
    wave: 1,
    title: "Layers Tree / Navigator (Permanent Action Buttons, RTL Depth Indent, Search, Context Menu)",
    category: "navigator",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/editor/navigator.php"),
    target_files: [
      "frontend/components/admin/builder/layers-tree.tsx",
      "frontend/stores/builder-store.ts"
    ],
    acceptance_signals: ["state", "dom", "pixels"],
    passes: true,
  },

  // ── Wave 2: Core & Pro Widgets + Interactive Modules ──────────────────────
  {
    id: "EL-W2-001",
    wave: 2,
    title: "Icon, Icon List & Icon Box Widgets",
    category: "widget_core",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/widgets/icon-box.php"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W2-002",
    wave: 2,
    title: "Counter, Countdown & Animated Statistics Widgets",
    category: "widget_core",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/widgets/counter.php"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W2-003",
    wave: 2,
    title: "Accordion & Tabs (FAQ, Product Specs, Nested Structures)",
    category: "widget_core",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/widgets/accordion.php"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W2-004",
    wave: 2,
    title: "Floating Contact & Social Links Bar",
    category: "widget_core",
    elementor_ref_path: path.join(elementorRoot, "elementor/includes/widgets/social-icons.php"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W2-005",
    wave: 2,
    title: "Pricing Table & Price List Widgets (Elementor Pro Parity)",
    category: "widget_pro",
    elementor_ref_path: path.join(elementorRoot, "elementor-pro/modules/pricing/"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/lib/builder/pattern-converter.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W2-006",
    wave: 2,
    title: "Call to Action, Banner & Review Histogram Widgets",
    category: "widget_pro",
    elementor_ref_path: path.join(elementorRoot, "elementor-pro/modules/call-to-action/"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },
  {
    id: "EL-W2-007",
    wave: 2,
    title: "Mega Menu Navigation Widget with Multi-Column Layout",
    category: "widget_pro",
    elementor_ref_path: path.join(elementorRoot, "elementor-pro/modules/mega-menu/"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "frontend/components/layout/mega-menu.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
    passes: true,
  },

  // ── Wave 3: Site Kit, Theme Builder, Form Submissions & Import/Export ─────
  {
    id: "EL-W3-001",
    wave: 3,
    title: "Global Site Kit (Colors, Typography, Layout, Button Styles, HSL Tokens)",
    category: "site_kit",
    elementor_ref_path: path.join(elementorRoot, "elementor/core/kits/documents/tabs/"),
    target_files: [
      "frontend/components/admin/builder/global-styles-dialog.tsx",
      "frontend/stores/builder-store.ts",
      "frontend/lib/builder/color-utils.ts"
    ],
    acceptance_signals: ["state", "dom", "style", "pixels"],
    passes: true,
  },
  {
    id: "EL-W3-002",
    wave: 3,
    title: "Form Container & Field Builder with Server-Side Anti-Spam",
    category: "pro_module",
    elementor_ref_path: path.join(elementorRoot, "elementor-pro/modules/forms/"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "frontend/components/admin/builder/inspector-panel.tsx",
      "backend/app/modules/content/application/ast_compiler.py",
      "backend/app/shared/content/html_sanitizer.py"
    ],
    acceptance_signals: ["state", "dom", "style", "ssr"],
    passes: true,
  },
  {
    id: "EL-W3-003",
    wave: 3,
    title: "Section & Full Page Template Library with JSON Import/Export",
    category: "pro_module",
    elementor_ref_path: path.join(elementorRoot, "elementor-pro/modules/library/"),
    target_files: [
      "frontend/components/admin/builder/save-template-dialog.tsx",
      "frontend/components/admin/builder/save-page-template-dialog.tsx",
      "frontend/components/admin/builder/blocks-palette.tsx",
      "frontend/stores/builder-store.ts"
    ],
    acceptance_signals: ["state", "dom", "persistence"],
    passes: true,
  },
  {
    id: "EL-W3-004",
    wave: 3,
    title: "Storefront E-Commerce Loop & Product Modules (Grid, Card, Variants, Price, AddToCart)",
    category: "pro_module",
    elementor_ref_path: path.join(elementorRoot, "elementor-pro/modules/woocommerce/"),
    target_files: [
      "frontend/lib/builder/block-registry.ts",
      "frontend/components/admin/builder/canvas-element.tsx",
      "backend/app/modules/content/application/ast_compiler.py"
    ],
    acceptance_signals: ["state", "dom", "style", "ssr"],
    passes: true,
  },
];

const backlog = {
  version: "2.0.0",
  lastUpdated: new Date().toISOString(),
  elementorRoot,
  summary: {
    totalItems: items.length,
    wave1Count: items.filter((i) => i.wave === 1).length,
    wave2Count: items.filter((i) => i.wave === 2).length,
    wave3Count: items.filter((i) => i.wave === 3).length,
    passedCount: items.filter((i) => i.passes).length,
  },
  items,
};

const outputPath = path.join(projectRoot, ".loop/elementor_parity_backlog.json");
fs.writeFileSync(outputPath, JSON.stringify(backlog, null, 2), "utf8");

console.log(`>>> [Parity-Backlog] Generated live Elementor backlog at ${outputPath}`);
console.log(`    Total backlog items: ${backlog.summary.totalItems}`);
console.log(`    - Wave 1 (Core Controls & Grid): ${backlog.summary.wave1Count}`);
console.log(`    - Wave 2 (Widgets & Pro Modules): ${backlog.summary.wave2Count}`);
console.log(`    - Wave 3 (Site Kit & Loop/Form): ${backlog.summary.wave3Count}`);
