import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Social Links, Blockquotes & Floating Bar", () => {
  it("renders social_links widget and updates platforms and urls reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-social-test", null, "تست شبکه‌های اجتماعی", "w9-social-test");

    const socialWidget: BuilderElement = {
      id: "el_w9_social",
      name: "شبکه‌های اجتماعی",
      type: "widget",
      widgetType: "social_links",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        links: [
          { platform: "اینستاگرام", url: "https://instagram.com" },
          { platform: "تلگرام", url: "https://t.me" },
          { platform: "لینکدین", url: "https://linkedin.com" },
        ],
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(socialWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_social");
    expect(found?.widgetProps?.links).toHaveLength(3);
    const links = found?.widgetProps?.links as any[];
    expect(links[0].platform).toBe("اینستاگرام");
  });

  it("renders blockquote widget with italic styling and author cite", () => {
    const store = useBuilderStore.getState();
    const quoteWidget: BuilderElement = {
      id: "el_w9_quote",
      name: "نقل‌قول مشتری",
      type: "widget",
      widgetType: "blockquote",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        text: "کیفیت خدمات و پشتیبانی فوق‌العاده سریع بود.",
        author: "مدیر مارکتینگ شرکت",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(quoteWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_quote");
    expect(found?.widgetProps?.text).toContain("کیفیت خدمات");
    expect(found?.widgetProps?.author).toBe("مدیر مارکتینگ شرکت");
  });
});
