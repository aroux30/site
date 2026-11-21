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
  fontSize: UnitValueSchema.nullable().optional(),
  fontWeight: z
    .enum(["300", "400", "500", "600", "700", "800", "900", "inherit"])
    .nullable()
    .optional(),
  lineHeight: UnitValueSchema.nullable().optional(),
  letterSpacing: UnitValueSchema.nullable().optional(),
  textAlign: z.enum(["right", "center", "left", "justify", "inherit"]).nullable().optional(),
  textTransform: z.enum(["none", "uppercase", "lowercase", "capitalize"]).nullable().optional(),
  textDecoration: z.enum(["none", "underline", "line-through"]).nullable().optional(),
  color: z.string().nullable().optional(),
});

export const BorderStyleSchema = z.object({
  style: z.enum(["none", "solid", "dashed", "dotted", "double"]).default("none"),
  width: SpacingBoxSchema.nullable().optional(),
  color: z.string().nullable().optional(),
  radius: SpacingBoxSchema.nullable().optional(),
});

export const BackgroundGradientSchema = z.object({
  direction: z.enum(["to-r", "to-l", "to-t", "to-b", "to-tr", "to-tl"]).default("to-l"),
  fromColor: z.string(),
  toColor: z.string(),
});

export const BackgroundStyleSchema = z.object({
  type: z.enum(["none", "color", "gradient", "image"]).default("none"),
  color: z.string().nullable().optional(),
  gradient: BackgroundGradientSchema.nullable().optional(),
  imageUrl: z.string().nullable().optional(),
  position: z.enum(["center", "top", "bottom", "left", "right"]).nullable().optional(),
  size: z.enum(["cover", "contain", "auto"]).nullable().optional(),
});

export const BackgroundOverlayStyleSchema = z.object({
  type: z.enum(["none", "color", "gradient"]).default("none"),
  color: z.string().nullable().optional(),
  gradient: BackgroundGradientSchema.nullable().optional(),
  opacity: z.number().min(0).max(1).nullable().optional(),
});

export const DeviceStyleSchema = z.object({
  typography: TypographyStyleSchema.nullable().optional(),
  margin: SpacingBoxSchema.nullable().optional(),
  padding: SpacingBoxSchema.nullable().optional(),
  border: BorderStyleSchema.nullable().optional(),
  background: BackgroundStyleSchema.nullable().optional(),
  backgroundOverlay: BackgroundOverlayStyleSchema.nullable().optional(),
  width: UnitValueSchema.nullable().optional(),
  minHeight: UnitValueSchema.nullable().optional(),
  display: z
    .enum(["block", "flex", "grid", "inline-block", "none", "inherit"])
    .nullable()
    .optional(),
  filter: z.string().nullable().optional(),
  opacity: z.number().min(0).max(1).nullable().optional(),
  zIndex: z.number().int().min(0).max(999).nullable().optional(),
  boxShadow: z.string().nullable().optional(),
  // Advanced Layout (P4)
  position: z.enum(["static", "relative", "absolute", "sticky", "inherit"]).nullable().optional(),
  top: UnitValueSchema.nullable().optional(),
  bottom: UnitValueSchema.nullable().optional(),
  left: UnitValueSchema.nullable().optional(),
  right: UnitValueSchema.nullable().optional(),
  overflow: z.enum(["visible", "hidden", "scroll", "auto", "inherit"]).nullable().optional(),
  flexDirection: z.enum(["row", "column", "row-reverse", "column-reverse", "inherit"]).nullable().optional(),
  justifyContent: z.enum(["start", "center", "end", "between", "around", "evenly", "inherit"]).nullable().optional(),
  alignItems: z.enum(["start", "center", "end", "stretch", "baseline", "inherit"]).nullable().optional(),
  alignSelf: z.enum(["auto", "start", "center", "end", "stretch", "inherit"]).nullable().optional(),
  order: z.number().int().nullable().optional(),
  flexGrow: z.number().nullable().optional(),
  flexWrap: z.enum(["nowrap", "wrap", "wrap-reverse", "inherit"]).nullable().optional(),
  gap: UnitValueSchema.nullable().optional(),
  gridTemplateColumns: z.string().nullable().optional(),
  shadow: z.string().nullable().optional(),
  backdropBlur: z.string().nullable().optional(),
  filterBlur: z.number().nullable().optional(),
});

export const ResponsiveStylesSchema = z.object({
  mobile: DeviceStyleSchema.default({}),
  tablet: DeviceStyleSchema.nullable().optional(),
  desktop: DeviceStyleSchema.nullable().optional(),
  customCssClass: z.string().nullable().optional(),
  customCssId: z.string().nullable().optional(),
  direction: z.enum(["rtl", "ltr", "inherit"]).default("inherit"),
  animation: z.string().nullable().optional(),
  animationDuration: z.number().nullable().optional(),
  animationDelay: z.number().nullable().optional(),
  shapeDividerTop: z.string().nullable().optional(),
  shapeDividerBottom: z.string().nullable().optional(),
  shapeDividerColor: z.string().nullable().optional(),
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
    layout: ContainerLayoutSchema.nullable().optional(),
    widgetType: z.string().nullable().optional(),
    widgetProps: z.record(z.unknown()).nullable().optional(),
    children: z.array(BuilderElementSchema).default([]),
    // Conditional visibility (P4)
    visibleOnDesktop: z.boolean().default(true),
    visibleOnTablet: z.boolean().default(true),
    visibleOnMobile: z.boolean().default(true),
    authVisibility: z.enum(["all", "authenticated", "guest"]).default("all"),
    // Synced / Global Components (P4)
    globalComponentId: z.string().nullable().optional(),
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
