import { describe, it, expect } from "vitest";
import {
  hexToRgb,
  getRelativeLuminance,
  getContrastRatio,
  checkWcagCompliance,
} from "@/lib/wcag-contrast";

describe("Phase 5 - WCAG 2.1 AA Contrast Utilities", () => {
  it("converts 3-digit and 6-digit hex codes to RGB accurately", () => {
    expect(hexToRgb("#fff")).toEqual({ r: 255, g: 255, b: 255 });
    expect(hexToRgb("#000")).toEqual({ r: 0, g: 0, b: 0 });
    expect(hexToRgb("#059669")).toEqual({ r: 5, g: 150, b: 105 });
    expect(hexToRgb("invalid")).toBeNull();
  });

  it("calculates relative luminance per W3C formula", () => {
    const whiteLum = getRelativeLuminance({ r: 255, g: 255, b: 255 });
    const blackLum = getRelativeLuminance({ r: 0, g: 0, b: 0 });

    expect(whiteLum).toBeCloseTo(1.0, 2);
    expect(blackLum).toBeCloseTo(0.0, 2);
  });

  it("calculates exact WCAG contrast ratios", () => {
    // Black on White = 21:1
    const maxRatio = getContrastRatio("#000000", "#ffffff");
    expect(maxRatio).toBe(21);

    // Same color = 1:1
    const minRatio = getContrastRatio("#ffffff", "#ffffff");
    expect(minRatio).toBe(1);

    // Brand Emerald (#059669) on White (#ffffff) is ~3.77:1 (passes Large Text AA >= 3:1)
    const emeraldWhite = getContrastRatio("#059669", "#ffffff");
    expect(emeraldWhite).toBeCloseTo(3.77, 1);
    expect(emeraldWhite).toBeGreaterThanOrEqual(3.0);

    // Dark Emerald (#047857) on White (#ffffff) is ~4.7:1 (passes Normal Text AA >= 4.5:1)
    const darkEmeraldWhite = getContrastRatio("#047857", "#ffffff");
    expect(darkEmeraldWhite).toBeGreaterThanOrEqual(4.5);
  });

  it("evaluates WCAG 2.1 AA and AAA thresholds correctly", () => {
    // Normal text on pure background: #09090b on #ffffff
    const resultNormal = checkWcagCompliance("#09090b", "#ffffff");
    expect(resultNormal).not.toBeNull();
    if (resultNormal) {
      expect(resultNormal.ratio).toBeGreaterThan(15);
      expect(resultNormal.isNormalTextAA).toBe(true);
      expect(resultNormal.isNormalTextAAA).toBe(true);
    }

    // Low contrast combination: #a1a1aa on #ffffff (ratio ~2.3:1)
    const resultPoor = checkWcagCompliance("#a1a1aa", "#ffffff");
    expect(resultPoor).not.toBeNull();
    if (resultPoor) {
      expect(resultPoor.isNormalTextAA).toBe(false);
      expect(resultPoor.isLargeTextAA).toBe(false);
    }
  });

  it("parses space-separated HSL channels and hsl() functions seamlessly", () => {
    // White background in HSL channels: "0 0% 100%"
    // Dark foreground in HSL channels: "240 10% 4%"
    const ratioHsl = getContrastRatio("240 10% 4%", "0 0% 100%");
    expect(ratioHsl).not.toBeNull();
    expect(ratioHsl).toBeGreaterThan(15);

    // Functional HSL and RGB syntax
    const ratioFn = getContrastRatio("hsl(160, 84%, 28%)", "rgb(255, 255, 255)");
    expect(ratioFn).not.toBeNull();
    expect(ratioFn).toBeGreaterThanOrEqual(3.0);
  });
});
