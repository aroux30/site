import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Pricing Tiers, Badges & Feature Checklist", () => {
  it("renders price_table widget and handles feature availability checklist", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-price-table-test", null, "تست جدول قیمت", "w9-price-table-test");

    const priceTableWidget: BuilderElement = {
      id: "el_w9_pricetbl",
      name: "پلن سازمانی",
      type: "widget",
      widgetType: "price_table",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        title: "پلن تجاری ویژه",
        subtitle: "شامل سرور اختصاصی و پشتیبانی ۲۴ ساعته",
        price: "۸۹۰,۰۰۰",
        currency: "تومان",
        period: "ماهانه",
        is_featured: true,
        badge: "پرفروش‌ترین",
        button_label: "سفارش آنلاین",
        features: [
          { text: "دامنه اختصاصی رایگان", available: true },
          { text: "گواهینامه SSL نامحدود", available: true },
          { text: "بک‌آپ روزانه ابری", available: true },
          { text: "مشاوره سئو اختصاصی", available: false },
        ],
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(priceTableWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_pricetbl");
    expect(found?.widgetProps?.title).toBe("پلن تجاری ویژه");
    expect(found?.widgetProps?.is_featured).toBe(true);
    expect(found?.widgetProps?.badge).toBe("پرفروش‌ترین");

    const features = found?.widgetProps?.features as any[];
    expect(features).toHaveLength(4);
    expect(features[0].text).toBe("دامنه اختصاصی رایگان");
    expect(features[0].available).toBe(true);
    expect(features[3].available).toBe(false);

    store.updateElementProps("el_w9_pricetbl", { price: "۹۹۰,۰۰۰" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_pricetbl");
    expect(updated?.widgetProps?.price).toBe("۹۹۰,۰۰۰");
  });
});
