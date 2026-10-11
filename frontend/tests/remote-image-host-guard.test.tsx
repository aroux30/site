/**
 * RemoteImage must never let a URL reach next/image that the optimiser would
 * reject.
 *
 * `next/image` **throws** on a host missing from `images.remotePatterns`, and
 * because it throws during render the whole route is replaced by the error
 * boundary. That happened on every blog article: one comment carried a
 * Gravatar address, and the reader got
 * "خطایی در بارگذاری صفحه رخ داده است" instead of the article.
 *
 * The component's own doc comment claims it "cannot take a page down", and
 * until this test existed that claim was false for any *unconfigured* host —
 * it only handled an empty src.
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { isAllowedImageUrl } from "@/lib/image-hosts";
import { RemoteImage } from "@/components/shared/remote-image";

/**
 * A host that is deliberately NOT configured. Gravatar is the real one: the
 * backend hands out `https://www.gravatar.com/avatar/<md5>` for commenters who
 * gave an email and no uploaded picture, and this project keeps
 * `remotePatterns` narrow on purpose, so it is not and must not be in the list.
 */
const UNCONFIGURED = "https://www.gravatar.com/avatar/5ee40c063ee4410107070c9271b6f5c1?s=80&d=mp&r=g";

describe("isAllowedImageUrl", () => {
  it("accepts a same-origin media path", () => {
    expect(isAllowedImageUrl("/uploads/media/abc.png")).toBe(true);
  });

  it("accepts the wildcard host the project ships with", () => {
    expect(isAllowedImageUrl("https://cdn.arouxpingg.com/x.jpg")).toBe(true);
    expect(isAllowedImageUrl("https://arouxpingg.com/x.jpg")).toBe(true);
  });

  it("refuses a host that is not configured", () => {
    // This is the exact URL that threw during render.
    expect(isAllowedImageUrl(UNCONFIGURED)).toBe(false);
  });

  it("refuses http, protocol-relative and non-URL values", () => {
    // An unencrypted origin has no business going through the optimiser.
    expect(isAllowedImageUrl("http://cdn.arouxpingg.com/x.jpg")).toBe(false);
    expect(isAllowedImageUrl("//evil.example.com/x.jpg")).toBe(false);
    expect(isAllowedImageUrl("javascript:alert(1)")).toBe(false);
    expect(isAllowedImageUrl("not a url")).toBe(false);
    expect(isAllowedImageUrl("")).toBe(false);
  });
});

describe("RemoteImage", () => {
  it("renders the placeholder instead of the image for an unconfigured host", () => {
    // If this threw, the test process would fail with next/image's own error —
    // which is exactly the page-level failure being guarded.
    render(<RemoteImage src={UNCONFIGURED} alt="نویسنده" />);

    // The placeholder carries role="img" with the alt text; no next/image.
    expect(screen.getByRole("img", { name: "نویسنده" })).toBeTruthy();
    expect(document.querySelector("img")).toBeNull();
  });

  it("renders the placeholder for an empty or missing src", () => {
    render(<RemoteImage src="" alt="بدون تصویر" />);
    expect(screen.getByRole("img", { name: "بدون تصویر" })).toBeTruthy();
  });

  it("renders a real next/image for an allowed host", () => {
    // fill stays on (the component's default): next/image requires either
    // `fill` or an explicit width/height, and this component only exposes fill.
    render(<RemoteImage src="/uploads/media/abc.png" alt="تصویر" />);
    const img = document.querySelector("img");
    expect(img).toBeTruthy();
    expect(img?.getAttribute("alt")).toBe("تصویر");
  });
});
