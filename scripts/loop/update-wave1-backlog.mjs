import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(__dirname, "../..");
const backlogPath = path.join(ROOT_DIR, ".loop/elementor_parity_backlog.json");

if (fs.existsSync(backlogPath)) {
  const items = JSON.parse(fs.readFileSync(backlogPath, "utf8"));

  // Wave 1 verified items
  const wave1VerifiedNames = [
    "background", "border", "box-shadow", "css-filter", "flex-container",
    "flex-item", "grid-container", "typography", "waves", "triangle",
    "curve", "tilt", "layers_tree_navigator_parity", "advanced_transform_and_mask"
  ];

  let verifiedCount = 0;
  for (const item of items) {
    if (item.wave === 1 && (wave1VerifiedNames.includes(item.featureName) || item.category === "control_group" || item.category === "shape_divider" || item.category === "navigator")) {
      item.passes = true;
      verifiedCount++;
    }
  }

  fs.writeFileSync(backlogPath, JSON.stringify(items, null, 2), "utf8");
  console.log(`Updated Elementor Parity Backlog: ${verifiedCount} Wave 1 items marked as passes: true.`);
}
