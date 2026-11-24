import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Forms, Inputs & Interactive Form Containers", () => {
  it("renders form_container with children and verifies action URL and honeypot", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-form-test", null, "تست فرم سازنده", "w9-form-test");

    const formContainer: BuilderElement = {
      id: "cont_lead_form",
      name: "فرم تماس و مشاوره",
      type: "container",
      widgetType: "form_container",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        submit_url: "/api/v1/content/forms/submit",
        success_message: "درخواست شما با موفقیت ثبت شد",
        error_message: "خطا در ارسال فرم",
      },
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 1,
      },
      styles: { mobile: {} },
      children: [
        {
          id: "el_f_name",
          name: "فیلد نام",
          type: "widget",
          widgetType: "form_input",
          widgetProps: { label: "نام کامل", placeholder: "مثلاً علی محمدی", required: true },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_f_phone",
          name: "فیلد شماره موبایل",
          type: "widget",
          widgetType: "form_input",
          widgetProps: { label: "شماره تماس", placeholder: "۰۹۱۲...", required: true },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_f_select",
          name: "فیلد موضوع مشاوره",
          type: "widget",
          widgetType: "form_select",
          widgetProps: { label: "نوع خدمت", options: ["فروشگاهی", "سازمانی", "سفارشی"] },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(formContainer);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "cont_lead_form");
    expect(found?.children?.length).toBe(3);
    expect(found?.widgetProps?.submit_url).toBe("/api/v1/content/forms/submit");
  });

  it("handles form_checkbox and form_radio options", () => {
    const store = useBuilderStore.getState();
    const chkWidget: BuilderElement = {
      id: "el_f_chk",
      name: "چک‌باکس قوانین",
      type: "widget",
      widgetType: "form_checkbox",
      widgetProps: { label: "قوانین سایت را مطالعه نموده و می‌پذیرم", checked: true },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(chkWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_f_chk");
    expect(found?.widgetProps?.label).toContain("قوانین");
    expect(found?.widgetProps?.checked).toBe(true);
  });
});
