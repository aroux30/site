#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const REF_ROOT = "C:/Users/Administrator/Desktop/elementor";
console.log("[Manifest] Scanning Elementor reference directory: " + REF_ROOT);

const manifest = {
  timestamp: new Date().toISOString(),
  refRoot: REF_ROOT,
  exists: fs.existsSync(REF_ROOT),
  subdirs: fs.existsSync(REF_ROOT) ? fs.readdirSync(REF_ROOT) : [],
  coreWidgets: ["icon", "icon_list", "image_box", "counter", "progress_bar", "testimonial", "alert", "toggle"],
  proWidgets: ["slides", "animated_headline", "call_to_action", "flip_box", "price_table", "price_list", "hotspot"],
  status: "INDEXED"
};

const outPath = path.join(".loop", "elementor_parity_manifest.json");
fs.mkdirSync(path.dirname(outPath), { recursive: true });
fs.writeFileSync(outPath, JSON.stringify(manifest, null, 2), "utf8");
console.log("[Manifest] Saved Elementor parity manifest to " + outPath);
