import fs from 'node:fs';
import path from 'node:path';

const ELEMENTOR_ROOT = 'C:/Users/Administrator/Desktop/elementor';
const SITE_ROOT = process.cwd();

function scanElementorReference() {
  console.log(`>>> Scanning Elementor Reference at ${ELEMENTOR_ROOT}...`);

  const backlog = [];
  let itemCounter = 1;

  function nextId(wave) {
    const padded = String(itemCounter++).padStart(3, '0');
    return `EL-W${wave}-${padded}`;
  }

  // 1. Control Groups (Wave 1)
  const controlGroupsDir = path.join(ELEMENTOR_ROOT, 'elementor/includes/controls/groups');
  if (fs.existsSync(controlGroupsDir)) {
    const files = fs.readdirSync(controlGroupsDir).filter(f => f.endsWith('.php'));
    for (const f of files) {
      const groupName = f.replace('.php', '');
      backlog.push({
        id: nextId(1),
        wave: 1,
        category: "control_group",
        name: `Group Control: ${groupName}`,
        elementor_ref_path: `elementor/includes/controls/groups/${f}`,
        target_files: [
          "frontend/types/builder.ts",
          "frontend/components/admin/builder/inspector-panel.tsx",
          "frontend/components/admin/builder/canvas-element.tsx",
          "backend/app/modules/content/domain/builder_ast.py",
          "backend/app/modules/content/application/ast_compiler.py"
        ],
        acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
        passes: false
      });
    }
  }

  // 2. Shape Dividers (Wave 1)
  const shapesDir = path.join(ELEMENTOR_ROOT, 'elementor/assets/shapes');
  if (fs.existsSync(shapesDir)) {
    const shapes = fs.readdirSync(shapesDir).filter(f => f.endsWith('.svg'));
    for (const s of shapes) {
      const shapeName = s.replace('.svg', '');
      backlog.push({
        id: nextId(1),
        wave: 1,
        category: "shape_divider",
        name: `Shape Divider: ${shapeName}`,
        elementor_ref_path: `elementor/assets/shapes/${s}`,
        target_files: [
          "frontend/components/admin/builder/canvas-element.tsx",
          "frontend/components/admin/builder/inspector-panel.tsx",
          "backend/app/modules/content/application/ast_compiler.py"
        ],
        acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
        passes: false
      });
    }
  }

  // 3. Navigator & Advanced Tab Features (Wave 1)
  const wave1Advanced = [
    { name: "Navigator Inline Element Renaming", ref: "elementor/includes/widgets/common-base.php", cat: "navigator" },
    { name: "Navigator Visual Status Badges", ref: "elementor/includes/widgets/common-base.php", cat: "navigator" },
    { name: "Navigator Right-Click Context Actions", ref: "elementor/includes/widgets/common-base.php", cat: "navigator" },
    { name: "Advanced Transform Controls (Rotate/Scale/Skew/Flip)", ref: "elementor/includes/widgets/common-base.php", cat: "advanced_tab" },
    { name: "Advanced Masking (Circle/Flower/Triangle/Blob/SVG)", ref: "elementor/includes/widgets/common-base.php", cat: "advanced_tab" },
    { name: "Advanced Sticky Scrolling & Offset", ref: "elementor-pro/modules/sticky/module.php", cat: "advanced_tab" },
    { name: "Advanced Motion & Scroll Effects", ref: "elementor-pro/modules/motion-fx/module.php", cat: "advanced_tab" },
    { name: "Advanced Custom Attributes Key-Value", ref: "elementor-pro/modules/custom-attributes/module.php", cat: "advanced_tab" },
    { name: "Advanced Scoped Custom CSS", ref: "elementor-pro/modules/custom-code/module.php", cat: "advanced_tab" },
    { name: "CSS Grid Advanced Container (FR/Repeat/Outline)", ref: "elementor/includes/controls/groups/grid-container.php", cat: "control_group" }
  ];

  for (const item of wave1Advanced) {
    backlog.push({
      id: nextId(1),
      wave: 1,
      category: item.cat,
      name: item.name,
      elementor_ref_path: item.ref,
      target_files: [
        "frontend/components/admin/builder/inspector-panel.tsx",
        "frontend/components/admin/builder/layers-tree.tsx",
        "frontend/components/admin/builder/canvas-element.tsx",
        "backend/app/modules/content/application/ast_compiler.py"
      ],
      acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
      passes: false
    });
  }

  // 4. Missing Core Widgets (Wave 2)
  const coreWidgetsDir = path.join(ELEMENTOR_ROOT, 'elementor/includes/widgets');
  if (fs.existsSync(coreWidgetsDir)) {
    const files = fs.readdirSync(coreWidgetsDir).filter(f => f.endsWith('.php'));
    const coreMissing = [
      "icon", "icon-list", "image-box", "image-carousel", "counter",
      "progress", "testimonial", "alert", "toggle", "menu-anchor", "read-more"
    ];
    for (const m of coreMissing) {
      const fileName = `${m}.php`;
      if (files.includes(fileName)) {
        backlog.push({
          id: nextId(2),
          wave: 2,
          category: "widget_core",
          name: `Core Widget: ${m}`,
          elementor_ref_path: `elementor/includes/widgets/${fileName}`,
          target_files: [
            "frontend/lib/builder/block-registry.ts",
            "frontend/components/admin/builder/canvas-element.tsx",
            "frontend/components/admin/builder/inspector-panel.tsx",
            "backend/app/modules/content/application/ast_compiler.py"
          ],
          acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
          passes: false
        });
      }
    }
  }

  // 5. Missing Pro Widgets & Modules (Wave 2)
  const proModulesDir = path.join(ELEMENTOR_ROOT, 'elementor-pro/modules');
  if (fs.existsSync(proModulesDir)) {
    const proMissing = [
      { name: "slides", label: "Slides / Nested Carousel Widget", cat: "widget_pro" },
      { name: "animated-headline", label: "Animated Headline Widget", cat: "widget_pro" },
      { name: "call-to-action", label: "Call to Action Widget", cat: "widget_pro" },
      { name: "flip-box", label: "Flip Box 3D Card Widget", cat: "widget_pro" },
      { name: "pricing", label: "Pricing Table & Price List Module", cat: "widget_pro" },
      { name: "hotspot", label: "Interactive Image Hotspots", cat: "widget_pro" },
      { name: "table-of-contents", label: "Automatic Table of Contents", cat: "widget_pro" },
      { name: "progress-tracker", label: "Page Scroll Progress Tracker", cat: "widget_pro" },
      { name: "blockquote", label: "Pro Blockquote & Tweet Share", cat: "widget_pro" },
      { name: "share-buttons", label: "Social Share Buttons Bar", cat: "widget_pro" },
      { name: "lottie", label: "Lottie Vector Animation Widget", cat: "widget_pro" },
      { name: "off-canvas", label: "Off-Canvas Drawer & Flyout Menu", cat: "pro_module" },
      { name: "popup", label: "Pop-up Builder (Modal/Banner/Slide-in)", cat: "pro_module" }
    ];

    for (const p of proMissing) {
      backlog.push({
        id: nextId(2),
        wave: 2,
        category: p.cat,
        name: p.label,
        elementor_ref_path: `elementor-pro/modules/${p.name}`,
        target_files: [
          "frontend/lib/builder/block-registry.ts",
          "frontend/components/admin/builder/canvas-element.tsx",
          "frontend/components/admin/builder/inspector-panel.tsx",
          "backend/app/modules/content/application/ast_compiler.py"
        ],
        acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
        passes: false
      });
    }
  }

  // 6. Site Kit & Theme Builder (Wave 3)
  const kitTabsDir = path.join(ELEMENTOR_ROOT, 'elementor/core/kits/documents/tabs');
  if (fs.existsSync(kitTabsDir)) {
    const tabs = fs.readdirSync(kitTabsDir).filter(f => f.endsWith('.php') && f !== 'tab-base.php');
    for (const t of tabs) {
      const tabName = t.replace('.php', '');
      backlog.push({
        id: nextId(3),
        wave: 3,
        category: "site_kit",
        name: `Global Site Kit Tab: ${tabName}`,
        elementor_ref_path: `elementor/core/kits/documents/tabs/${t}`,
        target_files: [
          "frontend/components/admin/builder/global-styles-dialog.tsx",
          "frontend/types/builder.ts",
          "backend/app/modules/content/domain/builder_ast.py"
        ],
        acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
        passes: false
      });
    }
  }

  const wave3Modules = [
    { name: "Theme Builder (Header/Footer/Single/Archive/404)", ref: "elementor-pro/modules/theme-builder", cat: "pro_module" },
    { name: "Loop Builder & Custom Query Grid", ref: "elementor-pro/modules/loop-builder", cat: "pro_module" },
    { name: "Multi-Step Form Builder with Conditional Logic", ref: "elementor-pro/modules/forms", cat: "pro_module" },
    { name: "Full Site Kit Export & Import Engine", ref: "elementor/core/kits", cat: "pro_module" }
  ];

  for (const m of wave3Modules) {
    backlog.push({
      id: nextId(3),
      wave: 3,
      category: m.cat,
      name: m.name,
      elementor_ref_path: m.ref,
      target_files: [
        "frontend/components/admin/builder/builder-studio.tsx",
        "backend/app/modules/content/application/cms_page_service.py"
      ],
      acceptance_signals: ["state", "dom", "style", "pixels", "ssr"],
      passes: false
    });
  }

  const results = {
    version: "2.0.0",
    lastUpdated: new Date().toISOString(),
    elementorRoot: ELEMENTOR_ROOT,
    totalItems: backlog.length,
    waveSummary: {
      wave1: backlog.filter(b => b.wave === 1).length,
      wave2: backlog.filter(b => b.wave === 2).length,
      wave3: backlog.filter(b => b.wave === 3).length
    },
    backlog
  };

  const outputPath = path.join(SITE_ROOT, '.loop/elementor_parity_backlog.json');
  fs.writeFileSync(outputPath, JSON.stringify(results, null, 2), 'utf-8');
  console.log(`>>> Written ${backlog.length} Elementor parity items to ${outputPath}`);
  console.log(`    - Wave 1: ${results.waveSummary.wave1}`);
  console.log(`    - Wave 2: ${results.waveSummary.wave2}`);
  console.log(`    - Wave 3: ${results.waveSummary.wave3}`);
}

scanElementorReference();
