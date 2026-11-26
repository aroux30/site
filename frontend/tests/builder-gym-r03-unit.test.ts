import { describe, it, expect } from "vitest";
import { normalizeVideoEmbedUrl } from "@/lib/builder/video-utils";
import { cleanBuilderHtml } from "@/lib/sanitize-html";

describe("Builder Gym Round 03 Unit Tests (Interactive & Video Parity)", () => {
  it("normalizes YouTube watch/shorts/youtu.be URLs to safe embed URLs", () => {
    expect(
      normalizeVideoEmbedUrl("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "youtube")
    ).toBe("https://www.youtube.com/embed/dQw4w9WgXcQ");

    expect(
      normalizeVideoEmbedUrl("https://youtu.be/dQw4w9WgXcQ?t=12", "youtube")
    ).toBe("https://www.youtube.com/embed/dQw4w9WgXcQ");

    expect(
      normalizeVideoEmbedUrl("https://www.youtube.com/shorts/abcDEF12345", "youtube")
    ).toBe("https://www.youtube.com/embed/abcDEF12345");
  });

  it("normalizes Aparat share URLs to iframe embed URLs", () => {
    expect(
      normalizeVideoEmbedUrl("https://www.aparat.com/v/sampleHash99", "aparat")
    ).toBe("https://www.aparat.com/video/video/embed/videohash/sampleHash99/vt/frame");

    expect(
      normalizeVideoEmbedUrl(
        "https://www.aparat.com/video/video/embed/videohash/sampleHash99/vt/frame",
        "aparat"
      )
    ).toBe("https://www.aparat.com/video/video/embed/videohash/sampleHash99/vt/frame");
  });

  it("rejects unsafe video schemes like javascript: and empty strings", () => {
    expect(normalizeVideoEmbedUrl("")).toBe("");
    expect(normalizeVideoEmbedUrl("javascript:alert(1)", "youtube")).toBe("");
  });

  it("preserves tabs data attributes, SVG shapes/icons, form submit buttons, and YouTube/Aparat iframes in cleanBuilderHtml", () => {
    const html = `
      <div class="builder-document" dir="rtl">
        <form id="el_f1" data-form-container="true" action="/api/v1/content/forms/submit" method="POST">
          <button type="submit" class="px-4 py-2">ثبت نهایی</button>
        </form>
        <div class="builder-tabs" data-widget="tabs">
          <button type="button" data-tab-index="0" aria-selected="true">اول</button>
          <button type="button" data-tab-index="1" aria-selected="false">دوم</button>
          <div class="tab-contents">
            <div data-tab-pane="0">محتوای اول</div>
            <div data-tab-pane="1" class="hidden">محتوای دوم</div>
          </div>
        </div>
        <div class="builder-video" data-widget="video">
          <iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ" allowfullscreen></iframe>
        </div>
        <div class="builder-social-links" data-widget="social_links">
          <a href="https://instagram.com"><svg viewBox="0 0 24 24" width="14" height="14"><circle cx="18" cy="5" r="3"/></svg><span>اینستا</span></a>
        </div>
      </div>
    `;
    const sanitized = cleanBuilderHtml(html);
    expect(sanitized).toContain('data-tab-index="1"');
    expect(sanitized).toContain('data-tab-pane="1"');
    expect(sanitized).toContain('type="submit"');
    expect(sanitized).toContain("ثبت نهایی");
    expect(sanitized).toContain("https://www.youtube.com/embed/dQw4w9WgXcQ");
    expect(sanitized).toContain("<circle");
  });
});
