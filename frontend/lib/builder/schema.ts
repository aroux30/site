import { z } from "zod";
import type { BuilderElement, PageAST, ResponsiveStyles } from "@/types/builder";

// ── 1. Unit & Spacing Schemas ───────────────────────────────────────────────

export const ElementIdSchema = z
  .string()
  .regex(/^[a-zA-Z][a-zA-Z0-9_-]{5,15}$/, "Element ID must start with a letter and be 6-16 characters.");

export const UnitValueSchema = z.object({
  value: z.number(),
  unit: z.enum(["px", "rem", "%", "vh", "vw", "em", "pt", "auto"]),
});

export const SpacingBoxSchema = z.object({
  top: UnitValueSchema.default({ value: 0, unit: "px" }),
  right: UnitValueSchema.default({ value: 0, unit: "px" }),
  bottom: UnitValueSchema.default({ value: 0, unit: "px" }),
  left: UnitValueSchema.default({ value: 0, unit: "px" }),
  isLinked: z.boolean().default(true),
});

// ── 2. Style Schemas ────────────────────────────────────────────────────────

export const TypographyStyleSchema = z.object({
  fontFamily: z.string().default("inherit"),
  fontSize: UnitValueSchema.optional(),
  fontWeight: z
    .enum(["300", "400", "500", "600", "700", "800", "900", "inherit"])
    .optional(),
  lineHeight: UnitValueSchema.optional(),
  letterSpacing: UnitValueSchema.optional(),
  textAlign: z.enum(["right", "center", "left", "justify", "inherit"]).optional(),
  textTransform: z.enum(["none", "uppercase", "lowercase", "capitalize"]).optional(),
  textDecoration: z.enum(["none", "underline", "line-through"]).optional(),
  color: z.string().optional(),
});

export const BorderStyleSchema = z.object({
  style: z.enum(["none", "solid", "dashed", "dotted", "double"]).default("none"),
  width: SpacingBoxSchema.optional(),
  color: z.string().optional(),
  radius: SpacingBoxSchema.optional(),
});

export const BackgroundGradientSchema = z.object({
  direction: z.enum(["to-r", "to-l", "to-t", "to-b", "to-tr", "to-tl"]).default("to-l"),
  fromColor: z.string(),
  toColor: z.string(),
});

export const BackgroundStyleSchema = z.object({
  type: z.enum(["none", "color", "gradient", "image"]).default("none"),
  color: z.string().optional(),
  gradient: BackgroundGradientSchema.optional(),
  imageUrl: z.string().optional(),
  position: z.enum(["center", "top", "bottom", "left", "right"]).optional(),
  size: z.enum(["cover", "contain", "auto"]).optional(),
});

export const DeviceStyleSchema = z.object({
  typography: TypographyStyleSchema.optional(),
  margin: SpacingBoxSchema.optional(),
  padding: SpacingBoxSchema.optional(),
  border: BorderStyleSchema.optional(),
  background: BackgroundStyleSchema.optional(),
  width: UnitValueSchema.optional(),
  minHeight: UnitValueSchema.optional(),
  display: z
    .enum(["block", "flex", "grid", "inline-block", "none", "inherit"])
    .optional(),
  opacity: z.number().min(0).max(1).optional(),
  zIndex: z.number().int().min(0).max(999).optional(),
});

export const ResponsiveStylesSchema = z.object({
  mobile: DeviceStyleSchema.default({}),
  tablet: DeviceStyleSchema.optional(),
  desktop: DeviceStyleSchema.optional(),
  customCssClass: z.string().optional(),
  customCssId: z.string().optional(),
  direction: z.enum(["rtl", "ltr", "inherit"]).default("inherit"),
});

// ── 3. Container Layout Schema ──────────────────────────────────────────────

export const ContainerLayoutSchema = z.object({
  kind: z.enum(["flex", "grid"]).default("flex"),
  direction: z
    .enum(["row", "column", "row-reverse", "column-reverse"])
    .default("column"),
  justifyContent: z
    .enum(["start", "center", "end", "between", "around", "evenly"])
    .default("start"),
  alignItems: z
    .enum(["start", "center", "end", "stretch", "baseline"])
    .default("stretch"),
  flexWrap: z.enum(["nowrap", "wrap", "wrap-reverse"]).default("nowrap"),
  gap: UnitValueSchema.default({ value: 16, unit: "px" }),
  gridColumns: z.number().int().min(1).max(12).default(3),
  boxedWidth: UnitValueSchema.nullable().optional(),
});

// ── 4. Element & Tree Node Schema ───────────────────────────────────────────

export const BuilderElementSchema: z.ZodType<BuilderElement, z.ZodTypeDef, any> = z.lazy(() =>
  z.object({
    id: ElementIdSchema,
    name: z.string().max(100),
    type: z.enum(["container", "widget"]),
    isLocked: z.boolean().default(false),
    isHidden: z.boolean().default(false),
    styles: ResponsiveStylesSchema.default({ mobile: {} }),
    layout: ContainerLayoutSchema.optional(),
    widgetType: z.string().optional(),
    widgetProps: z.record(z.unknown()).optional(),
    children: z.array(BuilderElementSchema).default([]),
  })
);

export const PageASTSchema = z.object({
  schemaVersion: z.number().int().default(1),
  title: z.string().min(1).max(300),
  slug: z.string().min(1).max(220),
  globalStyles: z.record(z.unknown()).default({}),
  rootElements: z.array(BuilderElementSchema).default([]),
});

// ── 5. Tree Validation Functions ────────────────────────────────────────────

export class BuilderValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BuilderValidationError";
  }
}

export function validateUniqueElementIds(ast: PageAST): void {
  const seenIds = new Set<string>();

  function traverse(el: BuilderElement) {
    if (seenIds.has(el.id)) {
      throw new BuilderValidationError(`Duplicate element ID: '${el.id}'`);
    }
    seenIds.add(el.id);
    for (const child of el.children) {
      traverse(child);
    }
  }

  for (const rootEl of ast.rootElements) {
    traverse(rootEl);
  }
}

export function validateTreeTopology(ast: PageAST, maxDepth = 5): void {
  function traverse(el: BuilderElement, ancestry: Set<string>, depth: number) {
    if (ancestry.has(el.id)) {
      throw new BuilderValidationError(
        `Circular reference detected at element: '${el.id}'`
      );
    }

    if (el.type === "widget") {
      if (el.children && el.children.length > 0) {
        throw new BuilderValidationError(
          `Widget '${el.id}' (${el.widgetType}) cannot have child elements.`
        );
      }
      return;
    }

    // Container
    if (depth > maxDepth) {
      throw new BuilderValidationError(
        `Max nesting depth of ${maxDepth} exceeded at container: '${el.id}'`
      );
    }

    const nextAncestry = new Set(ancestry);
    nextAncestry.add(el.id);

    for (const child of el.children) {
      traverse(child, nextAncestry, depth + 1);
    }
  }

  for (const rootEl of ast.rootElements) {
    traverse(rootEl, new Set(), 1);
  }
}

// ── 6. Mobile-First Responsive Resolution ───────────────────────────────────

export function resolveResponsiveValue<T>(
  values: { mobile?: T; tablet?: T; desktop?: T },
  activeBreakpoint: "mobile" | "tablet" | "desktop"
): T | undefined {
  if (activeBreakpoint === "mobile") {
    return values.mobile;
  }
  if (activeBreakpoint === "tablet") {
    return values.tablet ?? values.mobile;
  }
  // desktop
  return values.desktop ?? values.tablet ?? values.mobile;
}
