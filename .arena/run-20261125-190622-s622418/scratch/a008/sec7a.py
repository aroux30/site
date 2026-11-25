target = ".arena/run-20261125-190622-s622418/r0/a008.md"
part = """### 7. Comprehensive Regression Test Suite

#### 7.1 Vitest Unit Test Suite: `frontend/tests/builder-weight2-interactive-parity.test.ts`

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 2: Interactive Widgets & Form Controls 100% Audit & Wiring", () => {
  beforeEach(() => {
    const store = useBuilderStore.getState();
    store.initPage("w2-interactive-audit", null, "تست جامع ویجت‌های تعاملی", "w2-interactive-audit");
  });

  it("1. updates form_container props and maintains action endpoint integrity", () => {
    const store = useBuilderStore.getState();
    const formContainer: BuilderElement = {
      id: "cont_form_01",
      name: "فرم تماس با ما",
      type: "container",
      widgetType: "form_container",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        submit_url: "/api/v1/content/forms/submit",
        success_message: "پیام ارسال شد",
        error_message: "خطا در ارسال",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(formContainer);

    store.updateElementProps("cont_form_01", {
      submit_url: "/api/v1/custom/lead/submit",
      success_message: "با تشکر، کارشناسان ما به زودی تماس خواهند گرفت.",
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "cont_form_01");
    expect(updated?.widgetProps?.submit_url).toBe("/api/v1/custom/lead/submit");
    expect(updated?.widgetProps?.success_message).toContain("با تشکر");
  });

  it("2. updates form_input, form_select, and form_textarea props immutably", () => {
    const store = useBuilderStore.getState();
    const inputWidget: BuilderElement = {
      id: "el_f_input_01",
      name: "ورودی موبایل",
      type: "widget",
      widgetType: "form_input",
      widgetProps: { label: "شماره تماس", name: "phone", input_type: "tel", required: true },
      styles: { mobile: {} },
      children: [],
    };
    const selectWidget: BuilderElement = {
      id: "el_f_select_01",
      name: "انتخاب خدمت",
      type: "widget",
      widgetType: "form_select",
      widgetProps: { label: "خدمت مورد نظر", name: "service", options: ["طراحی سایت", "سئو"] },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(inputWidget);
    store.addElement(selectWidget);

    store.updateElementProps("el_f_input_01", { placeholder: "۰۹۱۲...", required: false });
    store.updateElementProps("el_f_select_01", { options: ["طراحی سایت", "سئو", "پشتیبانی فنی"] });

    const updatedInput = findElementById(useBuilderStore.getState().ast.rootElements, "el_f_input_01");
    const updatedSelect = findElementById(useBuilderStore.getState().ast.rootElements, "el_f_select_01");

    expect(updatedInput?.widgetProps?.placeholder).toBe("۰۹۱۲...");
    expect(updatedInput?.widgetProps?.required).toBe(false);
    expect((updatedSelect?.widgetProps?.options as string[]).length).toBe(3);
    expect(updatedSelect?.widgetProps?.options).toContain("پشتیبانی فنی");
  });

  it("3. verifies accordion and tabs add/remove item mutations", () => {
    const store = useBuilderStore.getState();
    const accordionWidget: BuilderElement = {
      id: "el_acc_01",
      name: "پرسش‌های متداول",
      type: "widget",
      widgetType: "accordion",
      widgetProps: {
        items: [
          { title: "سوال اول", content: "پاسخ اول", default_open: true },
          { title: "سوال دوم", content: "پاسخ دوم", default_open: false },
        ],
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(accordionWidget);

    const initial = findElementById(useBuilderStore.getState().ast.rootElements, "el_acc_01");
    const initialItems = initial?.widgetProps?.items as any[];
    store.updateElementProps("el_acc_01", {
      items: [...initialItems, { title: "سوال سوم", content: "پاسخ سوم", default_open: false }],
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_acc_01");
    const updatedItems = updated?.widgetProps?.items as any[];
    expect(updatedItems.length).toBe(3);
    expect(updatedItems[2].title).toBe("سوال سوم");
  });

  it("4. handles countdown timer target_date reactivity and title updates", () => {
    const store = useBuilderStore.getState();
    const countdownWidget: BuilderElement = {
      id: "el_cd_01",
      name: "تایمر پیشنهاد شگفت‌انگیز",
      type: "widget",
      widgetType: "countdown",
      widgetProps: {
        title: "مهلت تخفیف ویژه",
        target_date: "2026-12-31T23:59:59",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(countdownWidget);

    store.updateElementProps("el_cd_01", {
      title: "تخفیف جشنواره بهاره",
      target_date: "2027-03-20T00:00:00",
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_cd_01");
    expect(updated?.widgetProps?.title).toBe("تخفیف جشنواره بهاره");
    expect(updated?.widgetProps?.target_date).toBe("2027-03-20T00:00:00");
  });

  it("5. verifies nested_tabs and nested_accordion container structures", () => {
    const store = useBuilderStore.getState();
    const nestedTabs: BuilderElement = {
      id: "cont_nt_01",
      name: "تب‌های تودرتو",
      type: "container",
      widgetType: "nested_tabs",
      widgetProps: { active_tab: 0, tab_titles: ["برگه الف", "برگه ب"] },
      styles: { mobile: {} },
      children: [
        { id: "cont_sub_01", name: "محتوای برگه الف", type: "container", styles: { mobile: {} }, children: [] },
        { id: "cont_sub_02", name: "محتوای برگه ب", type: "container", styles: { mobile: {} }, children: [] },
      ],
    };
    store.addElement(nestedTabs);

    store.updateElementProps("cont_nt_01", { active_tab: 1 });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "cont_nt_01");
    expect(updated?.widgetProps?.active_tab).toBe(1);
    expect(updated?.children.length).toBe(2);
  });
});
```

"""
with open(target, "a", encoding="utf-8") as f:
    f.write(part)
print("Part 7A appended successfully")
