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
  fontSize?: UnitValue | null;
  fontWeight?: "300" | "400" | "500" | "600" | "700" | "800" | "900" | "inherit" | null;
  lineHeight?: UnitValue | null;
  letterSpacing?: UnitValue | null;
  textAlign?: "right" | "center" | "left" | "justify" | "inherit" | null;
  textTransform?: "none" | "uppercase" | "lowercase" | "capitalize" | null;
  textDecoration?: "none" | "underline" | "line-through" | null;
  textShadow?: string | null;
  color?: string | null; // hex, hsl(var(--token)), or semantic token key
}

export interface BorderStyle {
  style: "none" | "solid" | "dashed" | "dotted" | "double";
  width?: SpacingBox | null;
  color?: string | null;
  radius?: SpacingBox | null;
}

export interface BackgroundGradient {
  direction: "to-r" | "to-l" | "to-t" | "to-b" | "to-tr" | "to-tl";
  fromColor: string;
  toColor: string;
}

export interface BackgroundStyle {
  type: "none" | "color" | "gradient" | "image";
  color?: string | null;
  gradient?: BackgroundGradient | null;
  imageUrl?: string | null;
  position?: "center" | "top" | "bottom" | "left" | "right" | null;
  size?: "cover" | "contain" | "auto" | null;
}

export interface BackgroundOverlayStyle {
  type: "none" | "color" | "gradient";
  color?: string | null;
  gradient?: BackgroundGradient | null;
  opacity?: number | null;
}

export interface TransformStyle {
  rotate?: number | null; // degrees
  scale?: number | null; // scale multiplier
  skewX?: number | null; // degrees
  skewY?: number | null; // degrees
  translateX?: number | null;
  translateY?: number | null;
  flipX?: boolean;
  flipY?: boolean;
}

export interface MaskStyle {
  shape?: "none" | "circle" | "flower" | "sketch" | "triangle" | "blob" | "hexagon" | string | null;
  size?: "contain" | "cover" | "auto" | null;
  position?: string | null;
  repeat?: "no-repeat" | "repeat" | null;
}

export interface DeviceStyle {
  typography?: TypographyStyle | null;
  margin?: SpacingBox | null;
  padding?: SpacingBox | null;
  border?: BorderStyle | null;
  background?: BackgroundStyle | null;
  backgroundOverlay?: BackgroundOverlayStyle | null;
  width?: UnitValue | null;
  minHeight?: UnitValue | null;
  display?: "block" | "flex" | "grid" | "inline-block" | "none" | "inherit" | null;
  filter?: string | null;
  opacity?: number | null;
  zIndex?: number | null;
  boxShadow?: string | null;
  transform?: TransformStyle | null;
  mask?: MaskStyle | null;
  // Advanced Layout (P4)
  position?: "static" | "relative" | "absolute" | "sticky" | "inherit" | null;
  top?: UnitValue | null;
  bottom?: UnitValue | null;
  left?: UnitValue | null;
  right?: UnitValue | null;
  overflow?: "visible" | "hidden" | "scroll" | "auto" | "inherit" | null;
  flexDirection?: "row" | "column" | "row-reverse" | "column-reverse" | "inherit" | null;
  justifyContent?: "start" | "center" | "end" | "between" | "around" | "evenly" | "inherit" | null;
  alignItems?: "start" | "center" | "end" | "stretch" | "baseline" | "inherit" | null;
  alignSelf?: "auto" | "start" | "center" | "end" | "stretch" | "inherit" | null;
  order?: number | null;
  flexGrow?: number | null;
  flexWrap?: "nowrap" | "wrap" | "wrap-reverse" | "inherit" | null;
  gap?: UnitValue | null;
  gridTemplateColumns?: string | null;
  shadow?: string | null;
  backdropBlur?: "none" | "sm" | "md" | "lg" | "xl" | string | null;
  filterBlur?: number | null;
}

export interface ResponsiveStyles {
  /** Mobile is the base style (no media query / no prefix) */
  mobile: DeviceStyle;
  /** Tablet overrides via md: prefix (min-width: 768px) */
  tablet?: DeviceStyle | null;
  /** Desktop overrides via lg: prefix (min-width: 1024px) */
  desktop?: DeviceStyle | null;
  customCssClass?: string | null;
  customCssId?: string | null;
  customAttributes?: string | Record<string, string> | null;
  scopedCss?: string | null;
  direction?: "rtl" | "ltr" | "inherit";
  animation?: "none" | "fade-in" | "slide-up" | "zoom-in" | string | null;
  animationDuration?: number | null; // seconds
  animationDelay?: number | null; // seconds
  shapeDividerTop?: "none" | "waves" | "curve" | "triangle" | "tilt" | string | null;
  shapeDividerBottom?: "none" | "waves" | "curve" | "triangle" | "tilt" | string | null;
  shapeDividerColor?: string | null;
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
  layout?: ContainerLayout | null;
  widgetType?: string | null;
  widgetProps?: Record<string, unknown> | null;
  children: BuilderElement[];
  // Conditional visibility (P4)
  visibleOnDesktop?: boolean;
  visibleOnTablet?: boolean;
  visibleOnMobile?: boolean;
  authVisibility?: "all" | "authenticated" | "guest";
  // Synced / Global Components (P4)
  globalComponentId?: string | null;
}

export interface PageAST {
  schemaVersion: number;
  title: string;
  slug: string;
  globalStyles?: Record<string, unknown>;
  rootElements: BuilderElement[];
}

export type ThemeTemplateLocation = "header" | "footer" | "single_product" | "product_archive" | "not_found" | "custom";

export interface ThemeTemplate {
  id: string;
  location: ThemeTemplateLocation;
  title: string;
  conditions: {
    include: string[]; // e.g. ["entire_site", "products/*", "archives"]
    exclude?: string[];
  };
  builderData: PageAST;
}

export interface PageTemplate {
  id: string;
  title: string;
  slug: string;
  templateType: "page" | "section";
  category?: string | null;
  builderData: PageAST;
  thumbnailUrl?: string | null;
  authorId?: string | null;
  createdAt: string;
  updatedAt: string;
}
