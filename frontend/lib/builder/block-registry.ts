import {
  Layout,
  Columns,
  Heading,
  AlignLeft,
  Image,
  MousePointer,
  Minus,
  Maximize2,
  Code,
  Layers,
  Table,
  TextCursorInput,
  AlignJustify,
  ListFilter,
  type LucideIcon,
} from "lucide-react";
import type { BuilderElement } from "@/types/builder";

export interface BlockDefinition {
  type: string;
  name: string;
  category: "layout" | "basic";
  icon: LucideIcon;
  description: string;
  createDefaultElement: () => BuilderElement;
}

export const BASIC_BLOCK_DEFINITIONS: BlockDefinition[] = [
  // ── Layout Blocks ─────────────────────────────────────────────────────────
  {
    type: "container",
    name: "کانتینر (Container)",
    category: "layout",
    icon: Layout,
    description: "باکس انعطاف‌پذیر با چیدمان فلکس یا شبکه",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "کانتینر",
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 3,
      },
      styles: {
        mobile: {
          padding: {
            top: { value: 24, unit: "px" },
            right: { value: 16, unit: "px" },
            bottom: { value: 24, unit: "px" },
            left: { value: 16, unit: "px" },
            isLinked: true,
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "section",
    name: "بخش کامل (Section)",
    category: "layout",
    icon: Maximize2,
    description: "بخش سرتاسری برای گروه‌بندی محتوا با پس‌زمینه اختصاصی",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "سکشن سرتاسری",
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 24, unit: "px" },
        gridColumns: 1,
      },
      styles: {
        mobile: {
          padding: {
            top: { value: 40, unit: "px" },
            right: { value: 16, unit: "px" },
            bottom: { value: 40, unit: "px" },
            left: { value: 16, unit: "px" },
            isLinked: true,
          },
        },
        desktop: {
          padding: {
            top: { value: 64, unit: "px" },
            right: { value: 24, unit: "px" },
            bottom: { value: 64, unit: "px" },
            left: { value: 24, unit: "px" },
            isLinked: true,
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "columns",
    name: "دو ستونه (2 Columns)",
    category: "layout",
    icon: Columns,
    description: "چیدمان دو ستون مساوی کنار هم",
    createDefaultElement: () => {
      const colId1 = `el_${Math.random().toString(36).slice(2, 10)}`;
      const colId2 = `el_${Math.random().toString(36).slice(2, 10)}`;
      return {
        id: `el_${Math.random().toString(36).slice(2, 10)}`,
        name: "ردیف دو ستونه",
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "grid",
          direction: "row",
          justifyContent: "between",
          alignItems: "stretch",
          flexWrap: "wrap",
          gap: { value: 20, unit: "px" },
          gridColumns: 2,
        },
        styles: {
          mobile: {
            padding: {
              top: { value: 16, unit: "px" },
              right: { value: 16, unit: "px" },
              bottom: { value: 16, unit: "px" },
              left: { value: 16, unit: "px" },
              isLinked: true,
            },
          },
        },
        children: [
          {
            id: colId1,
            name: "ستون اول",
            type: "container",
            isLocked: false,
            isHidden: false,
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 12, unit: "px" }, gridColumns: 1 },
            styles: { mobile: {} },
            children: [],
          },
          {
            id: colId2,
            name: "ستون دوم",
            type: "container",
            isLocked: false,
            isHidden: false,
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 12, unit: "px" }, gridColumns: 1 },
            styles: { mobile: {} },
            children: [],
          },
        ],
      };
    },
  },

  // ── Basic Content Blocks ──────────────────────────────────────────────────
  {
    type: "heading",
    name: "سرتیتر (Heading)",
    category: "basic",
    icon: Heading,
    description: "عنوان H1 تا H6 با تایپوگرافی استاندارد",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "سرتیتر",
      type: "widget",
      widgetType: "heading",
      widgetProps: {
        text: "یک عنوان جذاب بنویسید",
        tag: "h2",
      },
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          typography: {
            fontSize: { value: 24, unit: "px" },
            fontWeight: "700",
            textAlign: "right",
          },
        },
        desktop: {
          typography: {
            fontSize: { value: 32, unit: "px" },
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "text_editor",
    name: "پاراگراف متن (Paragraph)",
    category: "basic",
    icon: AlignLeft,
    description: "متن توضیحی با فرمت‌بندی پاراگرافی",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "متن پاراگراف",
      type: "widget",
      widgetType: "text_editor",
      widgetProps: {
        content:
          "<p>توضیحات مربوط به محصولات یا خدمات خود را در این بخش قرار دهید. این متن به‌صورت کاملاً بهینه‌شده برای موتورهای جستجو رندر خواهد شد.</p>",
      },
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          typography: {
            fontSize: { value: 15, unit: "px" },
            lineHeight: { value: 28, unit: "px" },
            color: "hsl(var(--muted-foreground))",
            textAlign: "right",
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "image",
    name: "تصویر (Image)",
    category: "basic",
    icon: Image,
    description: "تصویر با پشتیبانی از کتابخانه رسانه و Alt Text",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "تصویر",
      type: "widget",
      widgetType: "image",
      widgetProps: {
        url: "/placeholder-hero.svg",
        alt: "تصویر شاخص",
      },
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          border: {
            style: "none",
            radius: {
              top: { value: 12, unit: "px" },
              right: { value: 12, unit: "px" },
              bottom: { value: 12, unit: "px" },
              left: { value: 12, unit: "px" },
              isLinked: true,
            },
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "button",
    name: "دکمه اقدام (Button)",
    category: "basic",
    icon: MousePointer,
    description: "دکمه فراخوان به عمل (Call to Action) با استایل‌های سازمانی",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "دکمه اقدام",
      type: "widget",
      widgetType: "button",
      widgetProps: {
        label: "همین حالا اقدام کنید",
        url: "#",
        newTab: false,
      },
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          padding: {
            top: { value: 12, unit: "px" },
            right: { value: 24, unit: "px" },
            bottom: { value: 12, unit: "px" },
            left: { value: 24, unit: "px" },
            isLinked: false,
          },
          border: {
            style: "none",
            radius: {
              top: { value: 10, unit: "px" },
              right: { value: 10, unit: "px" },
              bottom: { value: 10, unit: "px" },
              left: { value: 10, unit: "px" },
              isLinked: true,
            },
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "spacer",
    name: "فاصله‌ساز (Spacer)",
    category: "basic",
    icon: Minus,
    description: "فضای خالی عمودی قابل تنظیم بین بخش‌ها",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "فاصله‌ساز",
      type: "widget",
      widgetType: "spacer",
      widgetProps: {
        height: 32,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    }),
  },
  {
    type: "divider",
    name: "خط جداکننده (Divider)",
    category: "basic",
    icon: Minus,
    description: "خط افقی ظریف برای تفکیک بخش‌های مختلف صفحه",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "خط جداکننده",
      type: "widget",
      widgetType: "divider",
      widgetProps: {},
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          margin: {
            top: { value: 24, unit: "px" },
            right: { value: 0, unit: "px" },
            bottom: { value: 24, unit: "px" },
            left: { value: 0, unit: "px" },
            isLinked: false,
          },
        },
      },
      children: [],
    }),
  },
  {
    type: "table",
    name: "جدول داده (Table)",
    category: "basic",
    icon: Table,
    description: "جدول با سطرها و ستون‌های قابل تنظیم و ویرایش سلولی",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "جدول داده",
      type: "widget",
      widgetType: "table",
      widgetProps: {
        headers: ["مشخصه", "مدل الف", "مدل ب"],
        rows: [
          ["گارانتی", "۱۸ ماه تعویض", "۱۲ ماه تعمیر"],
          ["پشتیبانی", "۲۴ ساعته", "۹ الی ۱۷"],
        ],
        bordered: true,
        striped: true,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    }),
  },
  {
    type: "form_input",
    name: "فیلد ورودی متن (Input)",
    category: "basic",
    icon: TextCursorInput,
    description: "فیلد متنی یک خطی فرم با برچسب و متن راهنما",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "فیلد ورودی",
      type: "widget",
      widgetType: "form_input",
      widgetProps: {
        label: "نام و نام خانوادگی",
        name: "full_name",
        placeholder: "مثلاً علی رضایی",
        input_type: "text",
        required: false,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    }),
  },
  {
    type: "form_textarea",
    name: "متن چندخطی (Textarea)",
    category: "basic",
    icon: AlignJustify,
    description: "فیلد پیام چندخطی با ارتفاع قابل تنظیم",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "متن چندخطی",
      type: "widget",
      widgetType: "form_textarea",
      widgetProps: {
        label: "پیام شما",
        name: "message",
        placeholder: "پیام یا درخواست خود را بنویسید...",
        rows: 4,
        required: false,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    }),
  },
  {
    type: "form_select",
    name: "منوی کشویی (Select)",
    category: "basic",
    icon: ListFilter,
    description: "فیلد گزینش تک انتخابی از لیست",
    createDefaultElement: () => ({
      id: `el_${Math.random().toString(36).slice(2, 10)}`,
      name: "منوی کشویی",
      type: "widget",
      widgetType: "form_select",
      widgetProps: {
        label: "انتخاب موضوع",
        name: "topic",
        options: ["پشتیبانی فنی", "فروش و مشاوره", "سایر موارد"],
        required: false,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    }),
  },
];

import { createPatternAST } from "./pattern-converter";

/**
 * Constructs a fully editable, nested container + widget element tree from a block pattern.
 */
export function createPatternElement(
  pattern: { slug: string; title: string; category: string },
  renderedHtml: string,
  variables?: Record<string, string>
): BuilderElement {
  return createPatternAST(pattern, renderedHtml, variables);
}
