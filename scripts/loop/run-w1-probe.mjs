import { run5SignalProbe } from "./builder-5signal-probe.mjs";

async function main() {
  console.log("Running 5-Signal Probe for Weight 1: LayersTree & Studio Skeleton...");

  const r1 = await run5SignalProbe({
    targetType: "studio_surface",
    targetSlug: "layers_tree",
    controlTab: "content",
    round: "round-01",
    action: async (page, frame) => {
      const layersBtn = page.locator("button:has-text('لایه‌ها')").first();
      await layersBtn.waitFor({ state: "visible", timeout: 15000 });
      await layersBtn.click();
      await page.waitForTimeout(500);
    }
  });

  console.log("Running 5-Signal Probe for Base Widget: heading...");
  const r2 = await run5SignalProbe({
    targetType: "widget",
    targetSlug: "heading",
    controlTab: "content",
    round: "round-01",
    action: async (page, frame) => {
      const firstHeading = frame.locator("h2, h1, [data-element-id]").first();
      if (await firstHeading.isVisible()) {
        await firstHeading.click();
        await page.waitForTimeout(400);
      }
    }
  });

  console.log("Probe Results:", { r1: r1.verdict, r2: r2.verdict });
}

main().catch(err => {
  console.error("Probe error:", err);
  process.exit(1);
});
