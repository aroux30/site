import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../..");
const ELEMENTOR_BASE = "C:/Users/Administrator/Desktop/elementor";

console.log("Scanning Elementor reference directory for parity backlog...");

// Define categories to scan
const pathsToScan = [
  { category: "control_group", dir: path.join(ELEMENTOR_BASE, "elementor/includes/controls/groups"), wave: 1 },
  { category: "widget_core", dir: path.join(ELEMENTOR_BASE, "elementor/includes/widgets"), wave: 2 },
  { category: "shape_divider", dir: path.join(ELEMENTOR_BASE, "elementor/assets/shapes"), wave: 1 },
  { category: "site_kit", dir: path.join(ELEMENTOR_BASE, "elementor/core/kits/documents/tabs"), wave: 3 },
  { category: "pro_module", dir: path.join(ELEMENTOR_BASE, "elementor-pro/modules"), wave: 2 }
];

const backlogItems = [];
let counter = 1;

for (const scanTarget of pathsToScan) {
  if (fs.existsSync(scanTarget.dir)) {
    const files = fs.readdirSync(scanTarget.dir);
    for (const f of files) {
      const fullPath = path.join(scanTarget.dir, f);
      const isDir = fs.statSync(fullPath).isDirectory();
      const ext = path.extname(f);

      // Only care about php, svg or module dirs
      if (!isDir && ext !== ".php" && ext !== ".svg") continue;

      const baseName = path.basename(f, ext);
      const itemId = `EL-W${scanTarget.wave}-${String(counter++).padStart(3, "0")}`;

      // Map to target files in site
      let targetFiles = ["frontend/components/admin/builder/inspector-panel.tsx"];
      if (scanTarget.category === "shape_divider") {
        targetFiles = [
          "frontend/components/admin/builder/canvas-element.tsx",
          "frontend/types/builder.ts",
          "backend/app/modules/content/application/ast_compiler.py"
        ];
      } else if (scanTarget.category === "widget_core" || scanTarget.category === "pro_module") {
        targetFiles = [
          "frontend/components/admin/builder/inspector-panel.tsx",
          "frontend/components/admin/builder/canvas-element.tsx",
          "frontend/lib/builder/block-registry.ts",
          "backend/app/modules/content/application/ast_compiler.py"
        ];
      } else if (scanTarget.category === "site_kit") {
        targetFiles = [
          "frontend/components/admin/builder/global-styles-dialog.tsx",
          "frontend/stores/builder-store.ts"
        ];
      }

      backlogItems.push({
        id: itemId,
        wave: scanTarget.wave,
        category: scanTarget.category,
        featureName: baseName,
        elementor_ref_path: fullPath.replace(/\\/g, "/"),
        target_files: targetFiles,
        acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
        passes: false
      });
    }
  }
}

// Add advanced tab controls from common-base.php
backlogItems.push({
  id: `EL-W1-${String(counter++).padStart(3, "0")}`,
  wave: 1,
  category: "advanced_tab",
  featureName: "advanced_transform_and_mask",
  elementor_ref_path: `${ELEMENTOR_BASE}/elementor/includes/widgets/common-base.php`,
  target_files: [
    "frontend/components/admin/builder/inspector-panel.tsx",
    "frontend/components/admin/builder/canvas-element.tsx",
    "frontend/types/builder.ts",
    "backend/app/modules/content/application/ast_compiler.py"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

// Add navigator improvements
backlogItems.push({
  id: `EL-W1-${String(counter++).padStart(3, "0")}`,
  wave: 1,
  category: "navigator",
  featureName: "layers_tree_navigator_parity",
  elementor_ref_path: `${ELEMENTOR_BASE}/elementor/includes/widgets/common.php`,
  target_files: [
    "frontend/components/admin/builder/layers-tree.tsx",
    "frontend/stores/builder-store.ts"
  ],
  acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
  passes: false
});

const outputPath = path.join(ROOT_DIR, ".loop/elementor_parity_backlog.json");
fs.writeFileSync(outputPath, JSON.stringify(backlogItems, null, 2), "utf8");
console.log(`Saved Elementor parity backlog to: ${outputPath}`);
console.log(`Indexed ${backlogItems.length} Elementor parity items across Waves 1, 2, and 3.`);
