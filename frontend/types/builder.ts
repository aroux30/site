/**
 * Visual Page Builder Core Type Definitions (Phase P0).
 *
 * Provides TypeScript interfaces for:
 * - Mobile-First Responsive Styles
 * - Layout & Containers (Flex / Grid)
 * - Builder Elements (Tree nodes)
 * - Page AST (Root Document)
 * - Templates (Page & Section)
 */

export type UnitType = "px" | "rem" | "%" | "vh" | "vw" | "em" | "pt" | "auto";

export interface UnitValue {
  value: number;
  unit: UnitType;
}

export interface SpacingBox {
  top: UnitValue;
  right: UnitValue;
  bottom: UnitValue;
  left: UnitValue;
  isLinked: boolean;
}

export interface TypographyStyle {
  fontFamily?: "vazirmatn" | "system-ui" | "inherit" | string;
  fontSize?: UnitValue;
  fontWeight?: "300" | "400" | "500" | "600" | "700" | "800" | "900" | "inherit";
  lineHeight?: UnitValue;
  letterSpacing?: UnitValue;
  textAlign?: "right" | "center" | "left" | "justify" | "inherit";
  textTransform?: "none" | "uppercase" | "lowercase" | "capitalize";
  textDecoration?: "none" | "underline" | "line-through";
  color?: string; // hex, hsl(var(--token)), or semantic token key
}

export interface BorderStyle {
  style: "none" | "solid" | "dashed" | "dotted" | "double";
  width?: SpacingBox;
  color?: string;
  radius?: SpacingBox;
}

export interface BackgroundGradient {
  direction: "to-r" | "to-l" | "to-t" | "to-b" | "to-tr" | "to-tl";
  fromColor: string;
  toColor: string;
}

export interface BackgroundStyle {
  type: "none" | "color" | "gradient" | "image";
  color?: string;
  gradient?: BackgroundGradient;
  imageUrl?: string;
  position?: "center" | "top" | "bottom" | "left" | "right";
  size?: "cover" | "contain" | "auto";
}

export interface DeviceStyle {
  typography?: TypographyStyle;
  margin?: SpacingBox;
  padding?: SpacingBox;
  border?: BorderStyle;
  background?: BackgroundStyle;
  width?: UnitValue;
  minHeight?: UnitValue;
  display?: "block" | "flex" | "grid" | "inline-block" | "none" | "inherit";
  opacity?: number;
  zIndex?: number;
}

export interface ResponsiveStyles {
  /** Mobile is the base style (no media query / no prefix) */
  mobile: DeviceStyle;
  /** Tablet overrides via md: prefix (min-width: 768px) */
  tablet?: DeviceStyle;
  /** Desktop overrides via lg: prefix (min-width: 1024px) */
  desktop?: DeviceStyle;
  customCssClass?: string;
  customCssId?: string;
  direction?: "rtl" | "ltr" | "inherit";
}

export interface ContainerLayout {
  kind: "flex" | "grid";
  direction: "row" | "column" | "row-reverse" | "column-reverse";
  justifyContent: "start" | "center" | "end" | "between" | "around" | "evenly";
  alignItems: "start" | "center" | "end" | "stretch" | "baseline";
  flexWrap: "nowrap" | "wrap" | "wrap-reverse";
  gap: UnitValue;
  gridColumns: number;
  boxedWidth?: UnitValue | null;
}

export interface BuilderElement {
  id: string;
  name: string;
  type: "container" | "widget";
  isLocked: boolean;
  isHidden: boolean;
  styles: ResponsiveStyles;
  layout?: ContainerLayout;
  widgetType?: string;
  widgetProps?: Record<string, unknown>;
  children: BuilderElement[];
}

export interface PageAST {
  schemaVersion: number;
  title: string;
  slug: string;
  globalStyles?: Record<string, unknown>;
  rootElements: BuilderElement[];
}

export interface PageTemplate {
  id: string;
  title: string;
  slug: string;
  templateType: "page" | "section";
  builderData: PageAST;
  thumbnailUrl?: string | null;
  authorId?: string | null;
  createdAt: string;
  updatedAt: string;
}
