import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 2: Widget Controls Audit Across Content, Style & Advanced Tabs", () => {
  it("updates widget content props reactively across base widgets", () => {
    const store = useBuilderStore.getState();
    store.initPage("w2-test", null, "تست ویجت‌ها", "w2-test");

    const headingWidget: BuilderElement = {
      id: "el_w2_heading",
      name: "سرتیتر تستی",
      type: "widget",
      widgetType: "heading",
      widgetProps: { text: "سرتیتر اصلی", tag: "h1" },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(headingWidget);

    store.updateElementProps("el_w2_heading", { text: "سرتیتر تست-۳۶۰", tag: "h2" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w2_heading");
    expect(updated?.widgetProps?.text).toBe("سرتیتر تست-۳۶۰");
    expect(updated?.widgetProps?.tag).toBe("h2");
  });

  it("updates device styles (Padding, Margin, Width, Typography, Background) cleanly", () => {
    const store = useBuilderStore.getState();
    store.updateDeviceStyles("el_w2_heading", "desktop", {
      width: { value: 100, unit: "%" },
      typography: { fontSize: { value: 32, unit: "px" }, fontWeight: "700", textAlign: "right" },
      background: { type: "color", color: "#10b981" },
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w2_heading");
    const desktopStyles = updated?.styles?.desktop;
    expect(desktopStyles?.width?.value).toBe(100);
    expect(desktopStyles?.typography?.fontWeight).toBe("700");
    expect(desktopStyles?.background?.color).toBe("#10b981");
  });

  it("handles Advanced tab controls: authVisibility, customCssClass, and customAttributes", () => {
    const store = useBuilderStore.getState();
    store.updateElementVisibility("el_w2_heading", { auth: "authenticated" });
    store.updateElementStyles("el_w2_heading", {
      customCssClass: "shadow-xl border-primary",
      customAttributes: "data-role|hero-title\naria-label|test-heading",
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w2_heading");
    expect(updated?.authVisibility).toBe("authenticated");
    expect(updated?.styles?.customCssClass).toBe("shadow-xl border-primary");
    expect(updated?.styles?.customAttributes).toContain("data-role|hero-title");
  });

  it("handles form_container props and specialized container controls", () => {
    const store = useBuilderStore.getState();
    const formContainer: BuilderElement = {
      id: "el_w2_form",
      name: "فرم تماس",
      type: "container",
      widgetType: "form_container",
      widgetProps: {
        submit_url: "/api/v1/content/forms/submit",
        success_message: "ارسال شد.",
        error_message: "خطا در ارسال.",
      },
      isLocked: false,
      isHidden: false,
      layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 16, unit: "px" }, gridColumns: 1 },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(formContainer);

    store.updateElementProps("el_w2_form", {
      submit_url: "/api/v1/custom-submit",
      success_message: "با تشکر، پیام دریافت شد.",
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w2_form");
    expect(updated?.widgetProps?.submit_url).toBe("/api/v1/custom-submit");
    expect(updated?.widgetProps?.success_message).toBe("با تشکر، پیام دریافت شد.");
  });
});
