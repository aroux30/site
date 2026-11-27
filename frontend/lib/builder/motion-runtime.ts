import type { MotionEffectsStyle } from "@/types/builder";

/**
 * Shared Motion Effects calculator & CSS filter parser/composer (Elementor Pro Parity).
 * Used identically in CanvasFrame (editor preview) and BuilderInteractiveRuntime (SSR).
 */

export interface CssFilterValues {
  blur: number;       // 0..10 px
  brightness: number; // 0..200 %
  contrast: number;   // 0..200 %
  saturate: number;   // 0..200 %
  hue: number;        // 0..360 deg
}

export const DEFAULT_CSS_FILTERS: CssFilterValues = {
  blur: 0,
  brightness: 100,
  contrast: 100,
  saturate: 100,
  hue: 0,
};

export function parseCssFilterString(raw?: string | null): CssFilterValues {
  const res = { ...DEFAULT_CSS_FILTERS };
  if (!raw) return res;
  const blurM = raw.match(/blur\(([\d.]+)px\)/i);
  if (blurM) res.blur = Number(blurM[1]) || 0;
  const brM = raw.match(/brightness\(([\d.]+)%\)/i);
  if (brM) res.brightness = Number(brM[1]) ?? 100;
  const ctM = raw.match(/contrast\(([\d.]+)%\)/i);
  if (ctM) res.contrast = Number(ctM[1]) ?? 100;
  const satM = raw.match(/saturate\(([\d.]+)%\)/i);
  if (satM) res.saturate = Number(satM[1]) ?? 100;
  const hueM = raw.match(/hue-rotate\(([\d.-]+)deg\)/i);
  if (hueM) res.hue = Number(hueM[1]) || 0;
  return res;
}

export function composeCssFilterString(vals: CssFilterValues): string | undefined {
  const parts: string[] = [];
  if (vals.blur !== 0) parts.push(`blur(${vals.blur}px)`);
  if (vals.brightness !== 100) parts.push(`brightness(${vals.brightness}%)`);
  if (vals.contrast !== 100) parts.push(`contrast(${vals.contrast}%)`);
  if (vals.saturate !== 100) parts.push(`saturate(${vals.saturate}%)`);
  if (vals.hue !== 0) parts.push(`hue-rotate(${vals.hue}deg)`);
  return parts.length > 0 ? parts.join(" ") : undefined;
}

export function computeScrollMotionVars(
  motion: MotionEffectsStyle,
  viewportRatio: number // 0 (bottom entering) .. 1 (top leaving)
): { translateY: number; scale: number; opacity?: number } {
  const centered = viewportRatio - 0.5; // -0.5 .. +0.5
  let translateY = 0;
  let scale = 1;
  let opacity: number | undefined;

  if (motion.scrollParallax) {
    const speed = motion.parallaxSpeed ?? 4;
    translateY = Math.round(centered * speed * -18 * 100) / 100;
  }
  if (motion.scrollScale) {
    const speed = motion.scrollScaleSpeed ?? 1.15;
    const progress = Math.max(0, Math.min(1, viewportRatio));
    scale = Math.round((1 + (speed - 1) * progress) * 1000) / 1000;
  }
  if (motion.scrollOpacity) {
    const progress = Math.max(0, Math.min(1, viewportRatio * 1.4));
    opacity = Math.round(Math.max(0.2, Math.min(1, progress)) * 100) / 100;
  }
  return { translateY, scale, opacity };
}

export function applyMotionTransformToNode(
  el: HTMLElement,
  motion: MotionEffectsStyle,
  win: Window,
  mouseOffset: { nx: number; ny: number }
): void {
  const rect = el.getBoundingClientRect();
  const vh = win.innerHeight || 900;
  const ratio = 1 - (rect.top + rect.height / 2) / Math.max(1, vh + rect.height);
  const { translateY, scale, opacity } = computeScrollMotionVars(motion, ratio);

  let mouseX = 0;
  let mouseY = 0;
  if (motion.mouseTrack) {
    const mSpeed = motion.mouseSpeed ?? 3;
    const dir = motion.mouseOpposite ? -1 : 1;
    mouseX = Math.round(mouseOffset.nx * mSpeed * 12 * dir * 100) / 100;
    mouseY = Math.round(mouseOffset.ny * mSpeed * 12 * dir * 100) / 100;
  }

  const transforms: string[] = [];
  if (mouseX !== 0 || mouseY !== 0 || translateY !== 0) {
    transforms.push(`translate3d(${mouseX}px, ${(translateY + mouseY).toFixed(2)}px, 0)`);
  }
  if (scale !== 1) {
    transforms.push(`scale(${scale})`);
  }

  if (transforms.length > 0) {
    const baseTransform = el.dataset.baseTransform || "";
    el.style.transform = baseTransform ? `${baseTransform} ${transforms.join(" ")}` : transforms.join(" ");
  }
  if (opacity !== undefined) {
    el.style.opacity = String(opacity);
  }
}
