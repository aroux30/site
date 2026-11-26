import { describe, it, expect } from "vitest";
import { cleanBuilderHtml } from "@/lib/sanitize-html";
import { BASIC_BLOCK_DEFINITIONS } from "@/lib/builder/block-registry";

describe("Builder Gym Round 04 Unit Tests (12 Shop Widgets & Media Assets)", () => {
  it("contains zero broken /placeholder.svg URLs in default widget definitions", () => {
    for (const def of BASIC_BLOCK_DEFINITIONS) {
      const serialized = JSON.stringify(def.createDefaultElement());
      expect(serialized).not.toContain('"/placeholder.svg"');
    }
  });

  it("preserves Shop Widget interactive attributes and SVG icons through cleanBuilderHtml", () => {
    const sampleSsrHtml = `
      <div class="builder-document" dir="rtl">
        <div class="builder-image-gallery w-full max-w-md mx-auto space-y-2" data-widget="image_gallery">
          <img data-gallery-main="1" src="/placeholder-hero.svg" alt="تصویر اصلی" />
          <button type="button" data-gallery-thumb="0"><img src="/placeholder-hero.svg" alt="۱" /></button>
          <button type="button" data-gallery-thumb="1"><img src="/placeholder-product.svg" alt="۲" /></button>
        </div>
        <nav class="builder-mega-menu" data-widget="mega_menu">
          <button type="button" data-mega-menu-toggle="1" aria-expanded="false">منو</button>
          <div data-mega-menu-panel="1" class="hidden"><a href="/products?category=digital">کالای دیجیتال</a></div>
        </nav>
        <div data-widget="add_to_cart">
          <button type="button" data-qty-dec="1">-</button>
          <span data-qty-val="1">1</span>
          <button type="button" data-qty-inc="1">+</button>
          <button type="button" class="builder-add-to-cart" data-variant-id="var_1">
            <svg viewBox="0 0 24 24" width="16" height="16"><circle cx="8" cy="20" r="1"/></svg>
            <span>خرید</span>
          </button>
        </div>
        <div data-widget="mini_cart"><span data-mc-badge="1">2</span></div>
        <div data-widget="product_grid" data-filter="all">
          <button type="button" data-grid-filter="featured">ویژه</button>
        </div>
      </div>
    `;
    const clean = cleanBuilderHtml(sampleSsrHtml);
    expect(clean).toContain('data-gallery-main="1"');
    expect(clean).toContain('data-gallery-thumb="1"');
    expect(clean).toContain('data-mega-menu-toggle="1"');
    expect(clean).toContain('data-mega-menu-panel="1"');
    expect(clean).toContain('data-qty-inc="1"');
    expect(clean).toContain('data-mc-badge="1"');
    expect(clean).toContain('data-grid-filter="featured"');
    expect(clean).toContain("<circle");
  });
});
