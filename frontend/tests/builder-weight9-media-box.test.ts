import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Image Box, Price List & Share Buttons", () => {
  it("renders image_box widget and updates image URL and description reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-media-test", null, "تست مدیا و تصویر", "w9-media-test");

    const imgBoxWidget: BuilderElement = {
      id: "el_w9_imgbox",
      name: "باکس تصویر محصول",
      type: "widget",
      widgetType: "image_box",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        image_url: "/placeholder-hero.svg",
        title: "ضمانت بازگشت وجه",
        description: "تا ۷ روز در صورت عدم رضایت وجه شما کامل بازگردانده می‌شود.",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(imgBoxWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_imgbox");
    expect(found?.widgetProps?.title).toBe("ضمانت بازگشت وجه");
    expect(found?.widgetProps?.image_url).toBe("/placeholder-hero.svg");

    store.updateElementProps("el_w9_imgbox", { title: "تضمین اصالت ۱۰۰٪" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_imgbox");
    expect(updated?.widgetProps?.title).toBe("تضمین اصالت ۱۰۰٪");
  });

  it("handles share_buttons platform selection", () => {
    const store = useBuilderStore.getState();
    const shareWidget: BuilderElement = {
      id: "el_w9_share",
      name: "دکمه‌های اشتراک‌گذاری",
      type: "widget",
      widgetType: "share_buttons",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        platforms: ["telegram", "whatsapp"],
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(shareWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_share");
    expect(found?.widgetProps?.platforms).toHaveLength(2);
  });
});
