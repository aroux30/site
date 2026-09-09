import { describe, it, expect, beforeEach, vi } from "vitest";
import { useCompareStore, MAX_COMPARE_PRODUCTS } from "../compare-store";
import type { Product } from "@/types/product";

// Mock toast
vi.mock("@/components/ui/use-toast", () => ({
  toast: vi.fn(),
  useToast: vi.fn(),
}));

const mockProduct = (id: string, title: string): Product => ({
  id,
  title,
  slug: `slug-${id}`,
  description: `Description for ${title}`,
  price: 1000000,
  sku: `SKU-${id}`,
  stock: 10,
  isActive: true,
  isFeatured: false,
  images: [],
  categoryId: "cat-1",
  tags: [],
  variants: [],
  attributes: [],
  rating: 4.5,
  reviewCount: 10,
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
});

describe("compare-store", () => {
  beforeEach(() => {
    useCompareStore.setState({ products: [] });
    vi.clearAllMocks();
  });

  it("should initialize with empty products array", () => {
    const state = useCompareStore.getState();
    expect(state.products).toEqual([]);
  });

  it("should add a product if count < 4", () => {
    const p1 = mockProduct("p1", "Product 1");
    const result = useCompareStore.getState().addProduct(p1);

    expect(result).toBe(true);
    expect(useCompareStore.getState().products).toHaveLength(1);
    expect(useCompareStore.getState().products[0]?.id).toBe("p1");
  });

  it("should prevent duplicates", () => {
    const p1 = mockProduct("p1", "Product 1");
    useCompareStore.getState().addProduct(p1);
    const resultDuplicate = useCompareStore.getState().addProduct(p1);

    expect(resultDuplicate).toBe(false);
    expect(useCompareStore.getState().products).toHaveLength(1);
  });

  it("should allow adding up to 4 products and prevent adding a 5th", () => {
    const p1 = mockProduct("p1", "Product 1");
    const p2 = mockProduct("p2", "Product 2");
    const p3 = mockProduct("p3", "Product 3");
    const p4 = mockProduct("p4", "Product 4");
    const p5 = mockProduct("p5", "Product 5");

    expect(useCompareStore.getState().addProduct(p1)).toBe(true);
    expect(useCompareStore.getState().addProduct(p2)).toBe(true);
    expect(useCompareStore.getState().addProduct(p3)).toBe(true);
    expect(useCompareStore.getState().addProduct(p4)).toBe(true);
    expect(useCompareStore.getState().products).toHaveLength(MAX_COMPARE_PRODUCTS);

    // 5th product should be rejected
    const result5th = useCompareStore.getState().addProduct(p5);
    expect(result5th).toBe(false);
    expect(useCompareStore.getState().products).toHaveLength(4);
  });

  it("should correctly check isInCompare", () => {
    const p1 = mockProduct("p1", "Product 1");
    expect(useCompareStore.getState().isInCompare("p1")).toBe(false);

    useCompareStore.getState().addProduct(p1);
    expect(useCompareStore.getState().isInCompare("p1")).toBe(true);
    expect(useCompareStore.getState().isInCompare("p2")).toBe(false);
  });

  it("should remove a product by id", () => {
    const p1 = mockProduct("p1", "Product 1");
    const p2 = mockProduct("p2", "Product 2");

    useCompareStore.getState().addProduct(p1);
    useCompareStore.getState().addProduct(p2);
    expect(useCompareStore.getState().products).toHaveLength(2);

    useCompareStore.getState().removeProduct("p1");
    expect(useCompareStore.getState().products).toHaveLength(1);
    expect(useCompareStore.getState().isInCompare("p1")).toBe(false);
    expect(useCompareStore.getState().isInCompare("p2")).toBe(true);
  });

  it("should clear all products with clearCompare", () => {
    const p1 = mockProduct("p1", "Product 1");
    const p2 = mockProduct("p2", "Product 2");

    useCompareStore.getState().addProduct(p1);
    useCompareStore.getState().addProduct(p2);
    expect(useCompareStore.getState().products).toHaveLength(2);

    useCompareStore.getState().clearCompare();
    expect(useCompareStore.getState().products).toEqual([]);
  });

  it("should toggle product in and out of comparison", () => {
    const p1 = mockProduct("p1", "Product 1");

    useCompareStore.getState().toggleProduct(p1);
    expect(useCompareStore.getState().isInCompare("p1")).toBe(true);

    useCompareStore.getState().toggleProduct(p1);
    expect(useCompareStore.getState().isInCompare("p1")).toBe(false);
  });
});
