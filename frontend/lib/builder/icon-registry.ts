/**
 * frontend/lib/builder/icon-registry.ts
 * Unified SVG Icon Registry for Visual Page Builder (Elementor Parity)
 * Provides valid SVG data, dimensions, and path mappings ensuring 0 raw string slugs.
 */

import React from "react";
import {
  Star,
  Heart,
  ShieldCheck,
  Truck,
  Headphones,
  Award,
  Check,
  Zap,
  Sparkles,
  Clock,
  CreditCard,
  ShoppingCart,
  ShoppingBag,
  Gift,
  Phone,
  Mail,
  ThumbsUp,
  MapPin,
  User,
  Lock,
  Camera,
  Bell,
  Tag,
  Eye,
  Compass,
  Info,
  type LucideIcon,
} from "lucide-react";
import { BUILDER_ICONS, BUILDER_ICON_OPTIONS, getBuilderIcon } from "./icon-map";

export { BUILDER_ICONS, BUILDER_ICON_OPTIONS, getBuilderIcon };

export interface IconSvgDefinition {
  viewBox: string;
  paths: string[];
  isPolygon?: boolean;
  polygonPoints?: string;
}

export const BUILDER_ICON_SVG_REGISTRY: Record<string, IconSvgDefinition> = {
  star: {
    viewBox: "0 0 24 24",
    paths: [],
    isPolygon: true,
    polygonPoints: "12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2",
  },
  heart: {
    viewBox: "0 0 24 24",
    paths: [
      "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",
    ],
  },
  "shield-check": {
    viewBox: "0 0 24 24",
    paths: [
      "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",
      "m9 12 2 2 4-4",
    ],
  },
  truck: {
    viewBox: "0 0 24 24",
    paths: [
      "M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2",
      "M15 18H9",
      "M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14",
      "circle:cx=17:cy=18:r=2",
      "circle:cx=7:cy=18:r=2",
    ],
  },
  headphones: {
    viewBox: "0 0 24 24",
    paths: [
      "M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3",
    ],
  },
  award: {
    viewBox: "0 0 24 24",
    paths: [
      "circle:cx=12:cy=8:r=6",
      "M15.477 12.89 17 22l-5-3-5 3 1.523-9.11",
    ],
  },
  check: {
    viewBox: "0 0 24 24",
    paths: ["M20 6 9 17l-5-5"],
  },
  zap: {
    viewBox: "0 0 24 24",
    paths: [],
    isPolygon: true,
    polygonPoints: "13 2 3 14 12 14 11 22 21 10 12 10 13 2",
  },
  sparkles: {
    viewBox: "0 0 24 24",
    paths: [
      "m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z",
    ],
  },
  clock: {
    viewBox: "0 0 24 24",
    paths: [
      "circle:cx=12:cy=12:r=10",
      "M12 6v6l4 2",
    ],
  },
};

export function getIconSvgString(
  name: string,
  size = 24,
  className = "lucide"
): string {
  const key = String(name || "star").trim().toLowerCase();
  const def = BUILDER_ICON_SVG_REGISTRY[key] || BUILDER_ICON_SVG_REGISTRY.star || {
    viewBox: "0 0 24 24",
    paths: ["M12 2v20M2 12h20"],
    isPolygon: false,
  };

  if (def.isPolygon && def.polygonPoints) {
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${def.viewBox}" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="${className} lucide-${key}"><polygon points="${def.polygonPoints}"/></svg>`;
  }

  const pathElements = (def.paths || [])
    .map((p) => {
      if (p.startsWith("circle:")) {
        const parts = Object.fromEntries(
          p.replace("circle:", "").split(":").map((kv) => kv.split("="))
        );
        return `<circle cx="${parts.cx}" cy="${parts.cy}" r="${parts.r}" />`;
      }
      return `<path d="${p}" />`;
    })
    .join("");

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="${def.viewBox}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="${className} lucide-${key}">${pathElements}</svg>`;
}
