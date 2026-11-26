import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { isSafeUrl, toSafeUrl } from "@/lib/builder/schema";
import type { BuilderElement } from "@/types/builder";

describe("Weight 7: Elementor Parity Wave 2 — Core & Pro Interactive Widgets", () => {
  it("renders and updates call_to_action widget props reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w7-test", null, "تست ویجت‌های پرو", "w7-test");

    const ctaWidget: BuilderElement = {
      id: "el_w7_cta",
      name: "فراخوان اقدام",
      type: "widget",
      widgetType: "call_to_action",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        title: "تخفیف ویژه روز اول",
        description: "همین الان شروع کنید و از ۳۰٪ تخفیف بهره‌مند شوید",
        button_label: "عضویت سریع",
        button_url: "/signup",
        badge: "فرصت محدود",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(ctaWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w7_cta");
    expect(found?.widgetProps?.title).toBe("تخفیف ویژه روز اول");
    expect(found?.widgetProps?.badge).toBe("فرصت محدود");

    store.updateElementProps("el_w7_cta", { title: "عنوان به‌روزرسانی شده" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w7_cta");
    expect(updated?.widgetProps?.title).toBe("عنوان به‌روزرسانی شده");
  });

  it("handles flip_box front and back face properties", () => {
    const store = useBuilderStore.getState();
    const flipWidget: BuilderElement = {
      id: "el_w7_flip",
      name: "کارت چرخان",
      type: "widget",
      widgetType: "flip_box",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        front_title: "خدمات ما",
        front_desc: "مشاهده جزئیات",
        back_title: "همین حالا سفارش دهید",
        back_desc: "تضمین بهترین کیفیت",
        button_text: "شروع",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(flipWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w7_flip");
    expect(found?.widgetProps?.front_title).toBe("خدمات ما");
    expect(found?.widgetProps?.back_title).toBe("همین حالا سفارش دهید");
  });

  it("handles interactive container types (off_canvas, popup_builder)", () => {
    const store = useBuilderStore.getState();
    const popupContainer: BuilderElement = {
      id: "cont_w7_popup",
      name: "پاپ‌آپ تبلیغاتی",
      type: "container",
      widgetType: "popup_builder",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        trigger: "exit_intent",
        delay: 5,
        width: 500,
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(popupContainer);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "cont_w7_popup");
    expect(found?.widgetType).toBe("popup_builder");
    expect(found?.widgetProps?.trigger).toBe("exit_intent");
  });

  it("sanitizes widget button URLs rejecting javascript: and data: protocols (XSS prevention)", () => {
    expect(isSafeUrl("https://example.com")).toBe(true);
    expect(isSafeUrl("/relative/path")).toBe(true);
    expect(isSafeUrl("#section")).toBe(true);
    expect(isSafeUrl("javascript:alert(1)")).toBe(false);
    expect(isSafeUrl("DATA:text/html,<script>alert(1)</script>")).toBe(false);
    expect(isSafeUrl("vbscript:msgbox(1)")).toBe(false);

    expect(toSafeUrl("/checkout")).toBe("/checkout");
    expect(toSafeUrl("javascript:evil()")).toBe("#");
    expect(toSafeUrl("data:text/html,bad")).toBe("#");
  });
});
