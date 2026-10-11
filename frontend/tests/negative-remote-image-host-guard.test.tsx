/**
 * Negative test: the RemoteImage host guard is load-bearing.
 *
 * The guard exists because `next/image` **throws** on a host missing from
 * `images.remotePatterns` inside a Next app, and because it throws during
 * render the whole route is replaced by the error boundary. That is what every
 * blog article showed — "خطایی در بارگذاری صفحه رخ داده است" — caused by one
 * comment carrying a Gravatar address.
 *
 * ## Why this asserts on the rendered output, not on a throw
 *
 * A unit test **cannot** assert the throw: vitest does not load
 * `next.config.ts`, so `next/image` has no `remotePatterns` and happily renders
 * `/_next/image?url=https%3A%2F%2Fwww.gravatar.com%2F...` without complaining.
 * The failure only exists inside a real Next app. An earlier draft of this
 * file asserted "the pre-fix component throws" and passed for the wrong reason
 * on a machine with a differently-configured environment.
 *
 * So the invariant asserted here is the one the guard actually provides, and the
 * one that makes the throw impossible in the app: **a URL on an unconfigured
 * host must never reach `next/image`.** The observable difference is that the
 * pre-fix component emits an `/_next/image?url=...` optimizer URL for the
 * Gravatar address while the fixed one renders a placeholder and emits no
 * image at all. Remove the guard and the pre-fix column below goes back to
 * producing an optimizer URL, which is the same path that throws in the app.
 */
import { describe, it, expect } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { PreFixRemoteImage } from "./fixtures/pre-fix-remote-image";
import { RemoteImage } from "@/components/shared/remote-image";

/** The URL the live page failed on, taken from the captured console error. */
const UNCONFIGURED =
  "https://www.gravatar.com/avatar/5ee40c063ee4410107070c9271b6f5c1?s=80&d=mp&r=g";

const here = dirname(fileURLToPath(import.meta.url));

/** The optimizer URL next/image builds for a given src. */
function optimizerUrlFor(src: string): string {
  const { container } = render(<PreFixRemoteImage src={src} alt="probe" />);
  const img = container.querySelector("img");
  const url = img?.getAttribute("src") ?? "";
  cleanup();
  return url;
}

describe("negative test: RemoteImage host guard", () => {
  it("the fixture really is the pre-fix component", () => {
    // Confirm the injection: the fixture must not contain the guard.
    const source = readFileSync(join(here, "fixtures", "pre-fix-remote-image.tsx"), "utf-8");
    expect(source).toContain("next/image");
    expect(source).not.toContain("isAllowedImageUrl");
  });

  it("WITHOUT the guard, an unconfigured host reaches next/image", () => {
    // This is the path that throws inside a real Next app. Asserted through
    // the optimizer URL because vitest itself does not throw.
    const url = optimizerUrlFor(UNCONFIGURED);
    expect(url).toContain("/_next/image?url=");
    expect(url).toContain("gravatar.com");
  });

  it("WITH the guard, the same host never reaches next/image", () => {
    const { container } = render(<RemoteImage src={UNCONFIGURED} alt="نویسنده" />);
    expect(screen.getByRole("img", { name: "نویسنده" })).toBeTruthy();
    expect(container.querySelector("img")).toBeNull();
    expect(container.innerHTML).not.toContain("_next/image");
    cleanup();
  });

  it("the guard is not over-broad: an allowed host still renders", () => {
    // A guard that rejected everything would also keep the page up. Assert the
    // opposite direction, so the fix cannot degrade into "no images anywhere".
    const { container } = render(<RemoteImage src="/uploads/media/abc.png" alt="تصویر" />);
    expect(container.querySelector("img")).toBeTruthy();
    cleanup();
  });
});
