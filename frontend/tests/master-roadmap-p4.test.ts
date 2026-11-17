import { describe, it, expect, beforeEach } from "vitest";
import { useBuilderStore, findElementById, cloneElementWithNewIds } from "@/stores/builder-store";
import { BASIC_BLOCK_DEFINITIONS } from "@/lib/builder/block-registry";
import { DEFAULT_THEME_TOKENS, SHORTHAND_MAP } from "@/lib/builder/theme-schema";
import { BuilderElementSchema, PageASTSchema, validateUniqueElementIds } from "@/lib/builder/schema";
import type { BuilderElement } from "@/types/builder";

describe("Visual Page Builder Master Roadmap (P2, P3 & P4)", () => {
  beforeEach(() => {
    useBuilderStore.getState().initPage("page-master-p4", null, "برگه جامع P4", "master-p4");
  });

  // ── 1. Full Page Templates & Layout Tokens (P2) ──────────────────────────
  describe("1. Full Page Templates & Layout Design Tokens (P2)", () => {
    it("includes layout & spacing dimensions in theme schema and shorthand mapping", () => {
      expect(DEFAULT_THEME_TOKENS.semantic.dimension.containerWidth.$value).toBe("1280px");
      expect(DEFAULT_THEME_TOKENS.semantic.dimension.contentWidth.$value).toBe("768px");
      expect(DEFAULT_THEME_TOKENS.semantic.dimension.sectionSpacing.$value).toBe("64px");
      expect(DEFAULT_THEME_TOKENS.semantic.dimension.spacingScale.$value).toBe("16px");

      expect(SHORTHAND_MAP["dimension.containerWidth"]).toBe("--container-width");
      expect(SHORTHAND_MAP["dimension.contentWidth"]).toBe("--content-width");
      expect(SHORTHAND_MAP["dimension.sectionSpacing"]).toBe("--section-spacing");
      expect(SHORTHAND_MAP["dimension.spacingScale"]).toBe("--spacing-scale");
    });

    it("regenerates unique element IDs when cloning / importing page templates", () => {
      const state = useBuilderStore.getState();
      const originalRoot = state.ast.rootElements[0]!;
      const cloned = cloneElementWithNewIds(originalRoot);

      expect(cloned.id).not.toBe(originalRoot.id);
      expect(cloned.id).toMatch(/^el_[a-z0-9]+$/);
      for (let i = 0; i < cloned.children.length; i++) {
        expect(cloned.children[i]!.id).not.toBe(originalRoot.children[i]!.id);
      }

      // Verify AST passes unique ID validation
      const newAST = {
        ...state.ast,
        rootElements: [originalRoot, cloned],
      };
      expect(() => validateUniqueElementIds(newAST)).not.toThrow();
    });
  });

  // ── 2. E-Commerce Native AST Widgets (P3) ────────────────────────────────
  describe("2. E-Commerce Native AST Widgets (P3)", () => {
    it("registers all required P3 ecommerce widgets in BASIC_BLOCK_DEFINITIONS", () => {
      const types = BASIC_BLOCK_DEFINITIONS.map((b) => b.type);
      expect(types).toContain("product_variants");
      expect(types).toContain("product_price");
      expect(types).toContain("add_to_cart");
      expect(types).toContain("mini_cart");
      expect(types).toContain("cart_summary");
      expect(types).toContain("product_grid");
    });

    it("instantiates product_variants widget with proper props", () => {
      const def = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "product_variants")!;
      const el = def.createDefaultElement();
      expect(el.widgetType).toBe("product_variants");
      expect(el.widgetProps?.product_title).toBeDefined();
      expect(Array.isArray(el.widgetProps?.variants)).toBe(true);
      expect((el.widgetProps?.variants as any[]).length).toBeGreaterThan(0);
      expect(BuilderElementSchema.safeParse(el).success).toBe(true);
    });

    it("instantiates add_to_cart and cart_summary widgets correctly", () => {
      const cartBtnDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "add_to_cart")!;
      const cartBtn = cartBtnDef.createDefaultElement();
      expect(cartBtn.widgetType).toBe("add_to_cart");
      expect(cartBtn.widgetProps?.label).toBe("افزودن به سبد خرید");
      expect(cartBtn.widgetProps?.show_quantity).toBe(true);

      const cartSumDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "cart_summary")!;
      const cartSum = cartSumDef.createDefaultElement();
      expect(cartSum.widgetType).toBe("cart_summary");
      expect(cartSum.widgetProps?.checkout_url).toBe("/checkout");
    });

    it("supports product_grid enhanced filtering and pagination props", () => {
      const gridDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "product_grid")!;
      const grid = gridDef.createDefaultElement();
      expect(grid.widgetType).toBe("product_grid");
      expect(grid.widgetProps?.filter).toBe("all");
      expect(grid.widgetProps?.show_pagination).toBe(true);
      expect(grid.widgetProps?.enable_load_more).toBe(true);
    });
  });

  // ── 3. Advanced Layout Controls (P4) ─────────────────────────────────────
  describe("3. Advanced Layout Controls (P4)", () => {
    it("updates and stores Flexbox layout controls per breakpoint", () => {
      const rootId = useBuilderStore.getState().ast.rootElements[0]!.id;

      useBuilderStore.getState().updateDeviceStyles(rootId, "desktop", {
        display: "flex",
        flexDirection: "row-reverse",
        justifyContent: "between",
        alignItems: "center",
        flexWrap: "wrap",
        gap: { value: 24, unit: "px" },
      });

      const updated = findElementById(useBuilderStore.getState().ast.rootElements, rootId)!;
      expect(updated.styles.desktop?.display).toBe("flex");
      expect(updated.styles.desktop?.flexDirection).toBe("row-reverse");
      expect(updated.styles.desktop?.justifyContent).toBe("between");
      expect(updated.styles.desktop?.alignItems).toBe("center");
      expect(updated.styles.desktop?.flexWrap).toBe("wrap");
      expect(updated.styles.desktop?.gap?.value).toBe(24);
    });

    it("updates Positioning, Z-Index, and Overflow controls", () => {
      const rootId = useBuilderStore.getState().ast.rootElements[0]!.id;

      useBuilderStore.getState().updateDeviceStyles(rootId, "mobile", {
        position: "sticky",
        top: { value: 0, unit: "px" },
        zIndex: 50,
        overflow: "hidden",
      });

      const updated = findElementById(useBuilderStore.getState().ast.rootElements, rootId)!;
      expect(updated.styles.mobile.position).toBe("sticky");
      expect(updated.styles.mobile.top?.value).toBe(0);
      expect(updated.styles.mobile.zIndex).toBe(50);
      expect(updated.styles.mobile.overflow).toBe("hidden");
    });
  });

  // ── 4. Form Builder Elements (P4) ────────────────────────────────────────
  describe("4. Form Builder Elements (P4)", () => {
    it("registers form_container as layout container with submission settings", () => {
      const formDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_container")!;
      expect(formDef).toBeDefined();
      expect(formDef.category).toBe("layout");

      const formEl = formDef.createDefaultElement();
      expect(formEl.type).toBe("container");
      expect(formEl.widgetType).toBe("form_container");
      expect(formEl.widgetProps?.submit_url).toBe("/api/v1/content/forms/submit");
      expect(formEl.widgetProps?.success_message).toBeDefined();
      expect(Array.isArray(formEl.children)).toBe(true);
    });

    it("registers form_checkbox and form_radio with validation props", () => {
      const chkDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_checkbox")!;
      const chk = chkDef.createDefaultElement();
      expect(chk.widgetType).toBe("form_checkbox");
      expect(chk.widgetProps?.required).toBe(true);
      expect(chk.widgetProps?.name).toBe("accept_terms");

      const radDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_radio")!;
      const rad = radDef.createDefaultElement();
      expect(rad.widgetType).toBe("form_radio");
      expect(Array.isArray(rad.widgetProps?.options)).toBe(true);
      expect((rad.widgetProps?.options as string[]).length).toBeGreaterThan(1);
    });
  });

  // ── 5. Native Interactive Widgets (P4) ───────────────────────────────────
  describe("5. Native Interactive Widgets (P4)", () => {
    it("registers accordion, tabs, countdown, video, icon_box, and social_links", () => {
      const types = BASIC_BLOCK_DEFINITIONS.map((b) => b.type);
      expect(types).toContain("accordion");
      expect(types).toContain("tabs");
      expect(types).toContain("countdown");
      expect(types).toContain("video");
      expect(types).toContain("icon_box");
      expect(types).toContain("social_links");
    });

    it("instantiates video block with aparat support", () => {
      const vidDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "video")!;
      const vid = vidDef.createDefaultElement();
      expect(vid.widgetType).toBe("video");
      expect(vid.widgetProps?.video_type).toBe("aparat");
    });
  });

  // ── 6. Conditional Visibility & Synced Components (P4) ───────────────────
  describe("6. Conditional Visibility & Synced Components (P4)", () => {
    it("updates device and auth visibility flags on element", () => {
      const elId = useBuilderStore.getState().ast.rootElements[0]!.children[0]!.id;

      useBuilderStore.getState().updateElementVisibility(elId, {
        desktop: true,
        tablet: false,
        mobile: false,
        auth: "authenticated",
      });

      const updated = findElementById(useBuilderStore.getState().ast.rootElements, elId)!;
      expect(updated.visibleOnDesktop).toBe(true);
      expect(updated.visibleOnTablet).toBe(false);
      expect(updated.visibleOnMobile).toBe(false);
      expect(updated.authVisibility).toBe("authenticated");
    });

    it("makes an element a global component and synchronizes shared updates across instances", () => {
      const originalEl = useBuilderStore.getState().ast.rootElements[0]!.children[0]!;
      const globalId = useBuilderStore.getState().makeGlobalComponent(originalEl.id);
      expect(globalId).toMatch(/^gc_/);

      // Clone an instance sharing the same globalComponentId
      const secondInstance: BuilderElement = {
        ...cloneElementWithNewIds(originalEl),
        globalComponentId: globalId,
      };
      useBuilderStore.getState().addElement(secondInstance);

      // Synchronize shared change
      useBuilderStore.getState().updateGlobalComponent(globalId!, {
        name: "هدر سازمانی همگام‌شده",
      });

      const roots = useBuilderStore.getState().ast.rootElements;
      const inst1 = findElementById(roots, originalEl.id)!;
      const inst2 = findElementById(roots, secondInstance.id)!;

      expect(inst1.name).toBe("هدر سازمانی همگام‌شده");
      expect(inst2.name).toBe("هدر سازمانی همگام‌شده");
      expect(inst1.id).not.toBe(inst2.id); // Maintains unique element IDs
    });
  });

  // ── 7. Editor Productivity: Copy/Paste & Multi-Select (P4) ────────────────
  describe("7. Editor Productivity (Copy/Paste Styles, Elements & Multi-Select)", () => {
    it("copies and pastes element with new unique ID", () => {
      const originalWidget = useBuilderStore.getState().ast.rootElements[0]!.children[0]!;

      useBuilderStore.getState().copyElement(originalWidget.id);
      expect(useBuilderStore.getState().clipboard.element).not.toBeNull();
      expect(useBuilderStore.getState().clipboard.element?.id).toBe(originalWidget.id);

      // Paste element
      useBuilderStore.getState().pasteElement();

      const state = useBuilderStore.getState();
      const lastCreatedId = state.selectedElementId;
      expect(lastCreatedId).not.toBe(originalWidget.id);

      const pastedEl = findElementById(state.ast.rootElements, lastCreatedId!)!;
      expect(pastedEl.name).toContain("(کپی)");
      expect(pastedEl.id).toMatch(/^el_/);
    });

    it("copies and pastes styles between elements", () => {
      const sourceEl = useBuilderStore.getState().ast.rootElements[0]!.children[0]!;
      const targetEl = useBuilderStore.getState().ast.rootElements[0]!.children[1]!;

      // Give source custom opacity and padding
      useBuilderStore.getState().updateDeviceStyles(sourceEl.id, "mobile", {
        opacity: 0.75,
      });

      useBuilderStore.getState().copyStyles(sourceEl.id);
      expect(useBuilderStore.getState().clipboard.styles).not.toBeNull();

      useBuilderStore.getState().pasteStyles(targetEl.id);

      const updatedTarget = findElementById(useBuilderStore.getState().ast.rootElements, targetEl.id)!;
      expect(updatedTarget.styles.mobile.opacity).toBe(0.75);
    });

    it("supports multi-selection and batch deletion", () => {
      const child1 = useBuilderStore.getState().ast.rootElements[0]!.children[0]!;
      const child2 = useBuilderStore.getState().ast.rootElements[0]!.children[1]!;

      // Select child1
      useBuilderStore.getState().toggleSelectElement(child1.id, false);
      expect(useBuilderStore.getState().selectedElementIds).toEqual([child1.id]);

      // Multi-select child2
      useBuilderStore.getState().toggleSelectElement(child2.id, true);
      expect(useBuilderStore.getState().selectedElementIds).toContain(child1.id);
      expect(useBuilderStore.getState().selectedElementIds).toContain(child2.id);
      expect(useBuilderStore.getState().selectedElementIds).toHaveLength(2);

      // Batch delete
      useBuilderStore.getState().deleteSelectedElements();

      const roots = useBuilderStore.getState().ast.rootElements;
      expect(findElementById(roots, child1.id)).toBeNull();
      expect(findElementById(roots, child2.id)).toBeNull();
      expect(useBuilderStore.getState().selectedElementIds).toHaveLength(0);
    });
  });
});
