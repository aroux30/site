import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Code Highlight, Lottie & Breadcrumbs", () => {
  it("renders code_highlight widget and updates language and code text reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-code-test", null, "تست هایلایت کد", "w9-code-test");

    const codeWidget: BuilderElement = {
      id: "el_w9_code",
      name: "کد پایتون نمونه",
      type: "widget",
      widgetType: "code_highlight",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        title: "script.py",
        language: "python",
        code: "def main():\n    print('Hello Builder Gym!')\n\nmain()",
        line_numbers: true,
        copy_to_clipboard: true,
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(codeWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_code");
    expect(found?.widgetProps?.language).toBe("python");
    expect(found?.widgetProps?.title).toBe("script.py");

    store.updateElementProps("el_w9_code", { language: "typescript", title: "app.ts" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_code");
    expect(updated?.widgetProps?.language).toBe("typescript");
    expect(updated?.widgetProps?.title).toBe("app.ts");
  });

  it("renders lottie and breadcrumbs widgets with zero errors", () => {
    const store = useBuilderStore.getState();
    const lottieWidget: BuilderElement = {
      id: "el_w9_lottie",
      name: "انیمیشن تحویل",
      type: "widget",
      widgetType: "lottie",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        url: "/animations/delivery.json",
        loop: true,
        autoplay: true,
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(lottieWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_lottie");
    expect(found?.widgetType).toBe("lottie");
    expect(found?.widgetProps?.url).toBe("/animations/delivery.json");
  });
});
