import { describe, it, expect } from "vitest";
import { cleanHtml } from "../sanitize-html";

describe("cleanHtml (sanitize-html)", () => {
  it("should strip malicious script and iframe tags", () => {
    const dirty = '<p>سلام</p><script>alert("xss")</script><iframe src="evil.com"></iframe>';
    const cleaned = cleanHtml(dirty);
    expect(cleaned).not.toContain("<script>");
    expect(cleaned).not.toContain("<iframe>");
    expect(cleaned).toContain("<p>سلام</p>");
  });

  it("should preserve safe tags and attributes", () => {
    const safe = '<p class="text-sm"><a href="https://site.arouxpingg.com">لینک امن</a></p>';
    const cleaned = cleanHtml(safe);
    expect(cleaned).toContain('href="https://site.arouxpingg.com"');
    expect(cleaned).toContain('class="text-sm"');
  });
});
