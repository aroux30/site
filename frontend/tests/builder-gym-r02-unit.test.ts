import { describe, it, expect } from "vitest";
import { PageASTSchema, BorderStyleSchema } from "@/lib/builder/schema";
import { cleanBuilderHtml } from "@/lib/sanitize-html";

describe("Round 02: Schema radiusToken & cleanBuilderHtml SSR parity", () => {
  it("preserves BorderStyle radiusToken through BorderStyleSchema and PageASTSchema", () => {
    const border = BorderStyleSchema.parse({
      style: "none",
      radiusToken: "9999px",
    });
    expect(border.radiusToken).toBe("9999px");

    const ast = PageASTSchema.parse({
      schemaVersion: 1,
      title: "تست راند ۲",
      slug: "r02-test",
      globalStyles: {},
      rootElements: [
        {
          id: "el_card_r02",
          name: "کارت",
          type: "widget",
          widgetType: "button",
          widgetProps: { label: "دکمه", url: "#", newTab: true },
          isLocked: false,
          isHidden: false,
          styles: {
            mobile: {},
            desktop: {
              border: {
                style: "none",
                radiusToken: "var(--radius)",
              },
            },
          },
          children: [],
        },
      ],
    });
    expect(ast.rootElements[0]?.styles.desktop?.border?.radiusToken).toBe("var(--radius)");
  });

  it("cleanBuilderHtml preserves responsive styles, tokens, height, transform, SVG, and data-* while stripping XSS", () => {
    const dirty = `
      <div class="builder-document" dir="rtl">
        <style data-builder-responsive="1">@media (min-width: 1024px) { #el_h1 { font-size: 38px; color: hsl(var(--primary)); } }</style>
        <section id="el_sec1" data-gym="r02" style="display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); opacity: 0.9;">
          <h3 id="el_h1" style="font-size: 38px; color: #fef2f2; background-color: #dc2626; transform: rotate(6deg); filter: contrast(1.15); border-radius: 9999px;">عنوان تست</h3>
          <hr id="el_hr1" style="border-top-style: dashed; border-top-width: 3px; width: 60%;" />
          <div id="el_sp1" style="height: 96px;" aria-hidden="true"></div>
          <svg viewBox="0 0 100 100"><path d="M0 0 L100 100" fill="#ffffff"></path></svg>
          <script>alert('xss')</script>
          <img src="/placeholder-hero.svg" alt="ok" onerror="alert(1)" />
          <a href="javascript:alert(2)">بد</a>
        </section>
      </div>
    `;
    const clean = cleanBuilderHtml(dirty);
    expect(clean).toContain('data-builder-responsive="1"');
    expect(clean).toContain('data-gym="r02"');
    expect(clean).toMatch(/height:\s*96px/);
    expect(clean).toMatch(/border-top-style:\s*dashed/);
    expect(clean).toMatch(/transform:\s*rotate\(6deg\)/);
    expect(clean).toContain("hsl(var(--primary))");
    expect(clean).toContain("<svg");
    expect(clean).toContain("<path");
    expect(clean).not.toContain("<script>");
    expect(clean).not.toContain("alert(");
    expect(clean).not.toContain("onerror");
    expect(clean).not.toContain("javascript:");
  });
});
