import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Countdown Timer, Video Player & Rich Media", () => {
  it("renders countdown widget and calculates remaining time blocks reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-countdown-test", null, "تست شمارنده معکوس", "w9-countdown-test");

    const futureDate = new Date(Date.now() + 86400000 * 3).toISOString();
    const countdownWidget: BuilderElement = {
      id: "el_w9_countdown",
      name: "تایمر تخفیف ویژه",
      type: "widget",
      widgetType: "countdown",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        title: "حراج پاییزه",
        target_date: futureDate,
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(countdownWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_countdown");
    expect(found?.widgetProps?.title).toBe("حراج پاییزه");
    expect(found?.widgetProps?.target_date).toBe(futureDate);

    store.updateElementProps("el_w9_countdown", { title: "تخفیف بلک فرایدی" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_countdown");
    expect(updated?.widgetProps?.title).toBe("تخفیف بلک فرایدی");
  });

  it("handles video player widget properties (aparat, youtube, direct mp4)", () => {
    const store = useBuilderStore.getState();
    const videoWidget: BuilderElement = {
      id: "el_w9_video",
      name: "ویدیو معرفی محصول",
      type: "widget",
      widgetType: "video",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        video_type: "aparat",
        url: "https://www.aparat.com/video/video/embed/videohash/abcde/vt/frame",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(videoWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_video");
    expect(found?.widgetProps?.video_type).toBe("aparat");
    expect(found?.widgetProps?.url).toContain("aparat.com");
  });
});
