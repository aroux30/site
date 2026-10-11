/**
 * Pins the crawler-500 regression (found live 2026-10-09).
 *
 * The article page rendered its cover with a raw `next/image`. When the
 * stored `cover_image_url` points at a host that is not in
 * `images.remotePatterns` — which is what a WXR import stores when the
 * sideload did not run (`https://arouxshop.com/…`) — `next/image` **throws
 * during render**, and the whole route answered **HTTP 500 to every
 * crawler**: verified live with Googlebot, bingbot, curl and no-UA. Google
 * sees a 500 as "server broken" and drops the page from the index; the same
 * throw took the whole article down for logged-out readers.
 *
 * The fix routes the cover through `RemoteImage`, which checks the host
 * first and degrades to a placeholder. These tests read the page source and
 * assert the contract; the live HTTP check (Googlebot UA → 200) runs in the
 * E2E probe and is reproduced in the docstring of the fix commit.
 *
 * Negative test: restore a raw `<Image src={post.cover_image_url}` in the
 * page and the first assertion fails.
 */
import { readFileSync } from "fs";
import { resolve } from "path";
import { describe, expect, it } from "vitest";

const pageSrc = readFileSync(
  resolve(__dirname, "../app/(store)/blog/[slug]/page.tsx"),
  "utf-8",
);

describe("article cover cannot 500 the page", () => {
  it("renders the cover through RemoteImage, not a raw next/image", () => {
    // The cover block must exist and must use RemoteImage.
    expect(pageSrc).toContain("Featured Cover Image");
    expect(pageSrc).toMatch(/<RemoteImage[\s\S]*?post\.cover_image_url/);
  });

  it("has no raw <Image src={post.cover_image_url}", () => {
    // A raw next/image on a data-driven URL is the throw. There must be no
    // such call left for the cover (other raw Image uses, if any, must not
    // take post.cover_image_url).
    const rawImageOnCover = /<Image\s[^>]*src=\{post\.cover_image_url\}/.test(pageSrc);
    expect(rawImageOnCover).toBe(false);
  });

  it("og:image is filtered to a servable host", () => {
    // A foreign-host og:image breaks when the old site goes away; the
    // metadata builder must filter it out rather than pass it through.
    expect(pageSrc).toContain("isLocalImage");
  });
});
