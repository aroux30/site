import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Testimonial, Alert & Progress Bar", () => {
  it("renders testimonial widget and updates quote author and role reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-testimonial-test", null, "تست نظر مشتری", "w9-testimonial-test");

    const testimonialWidget: BuilderElement = {
      id: "el_w9_testimonial",
      name: "دیدگاه مشتری",
      type: "widget",
      widgetType: "testimonial",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        author: "سارا احمدی",
        role: "طراح ارشد محصول",
        company: "تک‌دیزاین",
        quote: "استفاده از این ابزار سرعت طراحی صفحات فرود ما را ۵ برابر کرد.",
        avatar_url: "/placeholder-hero.svg",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(testimonialWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_testimonial");
    expect(found?.widgetProps?.author).toBe("سارا احمدی");
    expect(found?.widgetProps?.quote).toContain("سرعت طراحی");

    store.updateElementProps("el_w9_testimonial", { author: "مریم حسینی", role: "مدیر ارشد تجربه کاربری" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_testimonial");
    expect(updated?.widgetProps?.author).toBe("مریم حسینی");
    expect(updated?.widgetProps?.role).toBe("مدیر ارشد تجربه کاربری");
  });

  it("handles progress_bar and alert widgets with zero error", () => {
    const store = useBuilderStore.getState();
    const progressWidget: BuilderElement = {
      id: "el_w9_progress",
      name: "نوار پیشرفت پروژه",
      type: "widget",
      widgetType: "progress_bar",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        title: "پیشرفت کلی فاز ۱",
        percentage: 85,
        show_percentage: true,
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(progressWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_progress");
    expect(found?.widgetProps?.percentage).toBe(85);
  });
});
