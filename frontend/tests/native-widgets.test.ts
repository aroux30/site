import { describe, it, expect } from "vitest";
import { BASIC_BLOCK_DEFINITIONS } from "@/lib/builder/block-registry";
import { PageASTSchema } from "@/lib/builder/schema";

describe("P2.1 Native Widgets: Table & Form Inputs", () => {
  it("registers table widget in BASIC_BLOCK_DEFINITIONS", () => {
    const tableDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "table");
    expect(tableDef).toBeDefined();
    expect(tableDef?.name).toContain("جدول");

    const element = tableDef!.createDefaultElement();
    expect(element.type).toBe("widget");
    expect(element.widgetType).toBe("table");
    expect(element.widgetProps?.headers).toBeInstanceOf(Array);
    expect(element.widgetProps?.rows).toBeInstanceOf(Array);
  });

  it("registers form_input, form_textarea, and form_select in BASIC_BLOCK_DEFINITIONS", () => {
    const formInput = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_input");
    const formTextarea = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_textarea");
    const formSelect = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_select");

    expect(formInput).toBeDefined();
    expect(formTextarea).toBeDefined();
    expect(formSelect).toBeDefined();

    const inputEl = formInput!.createDefaultElement();
    expect(inputEl.widgetType).toBe("form_input");
    expect(inputEl.widgetProps?.label).toBeDefined();
    expect(inputEl.widgetProps?.name).toBeDefined();

    const textareaEl = formTextarea!.createDefaultElement();
    expect(textareaEl.widgetType).toBe("form_textarea");
    expect(textareaEl.widgetProps?.rows).toBe(4);

    const selectEl = formSelect!.createDefaultElement();
    expect(selectEl.widgetType).toBe("form_select");
    expect(selectEl.widgetProps?.options).toBeInstanceOf(Array);
  });

  it("ensures native table and form widgets conform to PageASTSchema", () => {
    const tableEl = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "table")!.createDefaultElement();
    const inputEl = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_input")!.createDefaultElement();

    const ast = {
      schemaVersion: 1,
      title: "Test AST",
      slug: "test-ast",
      globalStyles: {},
      rootElements: [
        {
          id: "el_container",
          name: "کانتینر",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [tableEl, inputEl],
        },
      ],
    };

    const parsed = PageASTSchema.safeParse(ast);
    expect(parsed.success).toBe(true);
  });
});
