import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";

// Mock RemoteImage to standard img
vi.mock("@/components/shared/remote-image", () => ({
  RemoteImage: ({ src, alt, className }: any) =>
    React.createElement("img", { src, alt, className, "data-testid": "remote-img" }),
}));

// Mock Audio effects
vi.mock("@/lib/audio-effects", () => ({
  playAddToCartChime: vi.fn(),
}));

// Mock cart hook
const mockAddToCart = vi.fn().mockResolvedValue(undefined);
vi.mock("@/hooks/use-cart", () => ({
  useCart: () => ({
    addToCart: mockAddToCart,
    cart: { items: [] },
  }),
}));

import { ProductCard } from "@/components/store/product-card";
import { ImageGallery } from "@/components/store/image-gallery";
import { StarRating } from "@/components/ui/star-rating";
import { ReviewHistogram } from "@/components/store/review-histogram";
import { QuickViewModal } from "@/components/store/quick-view-modal";
import { RecentlyViewed, trackProductView, useRecentlyViewedStore } from "@/components/store/recently-viewed";
import { MegaMenu } from "@/components/layout/mega-menu";

// Mock matchMedia for Embla Carousel in jsdom
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IntersectionObserver & ResizeObserver for Embla Carousel in jsdom
class MockIntersectionObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
Object.defineProperty(window, "IntersectionObserver", {
  writable: true,
  value: MockIntersectionObserver,
});

class MockResizeObserver {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
Object.defineProperty(window, "ResizeObserver", {
  writable: true,
  value: MockResizeObserver,
});

describe("Phase 3 - Storefront Core Components Suite", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useRecentlyViewedStore.getState().clear();
  });

  // ── 1. ProductCard ──────────────────────────────────────────────────────────
  describe("1. ProductCard Component", () => {
    const sampleProduct: any = {
      id: "prod-101",
      name: "کفش کوهنوردی کینتیکس",
      slug: "kinetix-shoes",
      category_name: "کوهنوردی",
      min_price: 1500000,
      max_price: 2000000,
      primary_image_url: "/shoes.jpg",
      is_featured: true,
      variant_count: 2,
      is_in_stock: true,
      rating_average: 4.8,
      review_count: 26,
    };

    it("renders product name, price, discount badge and rating", () => {
      render(<ProductCard product={sampleProduct} />);

      expect(screen.getByText("کفش کوهنوردی کینتیکس")).toBeDefined();
      expect(screen.getAllByText(/کوهنوردی/).length).toBeGreaterThan(0);
      expect(screen.getByText(/۲۵٪ تخفیف/)).toBeDefined();
      expect(screen.getByText(/پیشنهاد ویژه/)).toBeDefined();
      expect(screen.getByText("خرید")).toBeDefined();
    });

    it("renders out-of-stock badge and disables action button when out of stock", () => {
      const outOfStockProd = { ...sampleProduct, is_in_stock: false };
      render(<ProductCard product={outOfStockProd} />);

      const outOfStockEls = screen.getAllByText("ناموجود");
      expect(outOfStockEls.length).toBeGreaterThanOrEqual(1);
      const buyBtn = screen.getByRole("button", { name: /ناموجود است/ });
      expect(buyBtn).toBeDefined();
      expect(buyBtn.hasAttribute("disabled")).toBe(true);
    });

    it("triggers onQuickView callback when quick-view button clicked", () => {
      const handleQuickView = vi.fn();
      render(<ProductCard product={sampleProduct} onQuickView={handleQuickView} />);

      const qvButton = screen.getByRole("button", { name: "مشاهده سریع" });
      fireEvent.click(qvButton);

      expect(handleQuickView).toHaveBeenCalledWith(sampleProduct);
    });

    it("calls addToCart when buy button clicked", () => {
      render(<ProductCard product={sampleProduct} />);

      const buyBtn = screen.getByRole("button", { name: /افزودن .* به سبد/ });
      fireEvent.click(buyBtn);

      expect(mockAddToCart).toHaveBeenCalledWith(
        expect.objectContaining({
          productId: "prod-101",
          title: "کفش کوهنوردی کینتیکس",
        })
      );
    });
  });

  // ── 2. ImageGallery + Lightbox ──────────────────────────────────────────────
  describe("2. ImageGallery + Lightbox Component", () => {
    const images = [
      { url: "/img1.jpg", alt: "تصویر اصلی" },
      { url: "/img2.jpg", alt: "تصویر زاویه دوم" },
      { url: "/img3.jpg", alt: "تصویر جزئیات" },
    ];

    it("renders thumbnails and counter", () => {
      render(<ImageGallery images={images} productName="کفش ورزشی" />);

      expect(screen.getByText("بزرگ‌نمایی")).toBeDefined();
      expect(screen.getByText(/۱ \/ ۳/)).toBeDefined();
    });

    it("opens lightbox dialog when main image is clicked", () => {
      render(<ImageGallery images={images} productName="کفش ورزشی" />);

      const mainImg = screen.getAllByAltText("تصویر اصلی")[0];
      fireEvent.click(mainImg);

      // Lightbox dialog should open with counter
      expect(screen.getByText(/۱ از ۳/)).toBeDefined();
    });
  });

  // ── 3. StarRating & ReviewHistogram ─────────────────────────────────────────
  describe("3. StarRating & ReviewHistogram Components", () => {
    it("renders StarRating in read-only mode with value and review count", () => {
      render(<StarRating value={4.6} showValue={true} reviewCount={35} />);

      expect(screen.getByText("4.6")).toBeDefined();
      expect(screen.getByText("(۳۵ نظر)")).toBeDefined();
    });

    it("supports interactive StarRating with keyboard navigation", () => {
      const handleChange = vi.fn();
      render(<StarRating value={3} onChange={handleChange} />);

      const stars = screen.getAllByRole("radio");
      expect(stars.length).toBe(5);

      fireEvent.click(stars[4]); // Click 5th star
      expect(handleChange).toHaveBeenCalledWith(5);
    });

    it("renders ReviewHistogram with distribution bars and average", () => {
      const dist = { star_5: 40, star_4: 10, star_3: 5, star_2: 2, star_1: 1 };
      render(
        <ReviewHistogram
          distribution={dist}
          averageRating={4.7}
          totalReviews={58}
          verifiedCount={45}
        />
      );

      expect(screen.getByText("4.7")).toBeDefined();
      expect(screen.getByText(/بر اساس ۵۸ نظر/)).toBeDefined();
      expect(screen.getByText(/۴۵ خرید تأییدشده/)).toBeDefined();
    });
  });

  // ── 4. QuickViewModal ───────────────────────────────────────────────────────
  describe("4. QuickViewModal Component", () => {
    const qvProduct: any = {
      id: "qv-1",
      name: "ساعت هوشمند سری ۹",
      slug: "smartwatch-9",
      min_price: 3500000,
      max_price: 4000000,
      primary_image_url: "/watch.jpg",
      short_description: "دارای سنسورهای سلامتی پیشرفته و ضدآب تا عمق ۵۰ متر",
      rating_average: 4.9,
      review_count: 88,
    };

    it("renders product info, quantity stepper, and full details link", () => {
      const handleClose = vi.fn();
      render(<QuickViewModal product={qvProduct} onClose={handleClose} />);

      expect(screen.getByText("ساعت هوشمند سری ۹")).toBeDefined();
      expect(screen.getByText(/دارای سنسورهای سلامتی/)).toBeDefined();
      expect(screen.getByText("مشاهده جزئیات کامل محصول")).toBeDefined();

      // Stepper test
      const plusBtn = screen.getByRole("button", { name: "افزایش تعداد" });
      fireEvent.click(plusBtn);
      expect(screen.getByText("۲")).toBeDefined();
    });
  });

  // ── 5. RecentlyViewed & Zustand Store ───────────────────────────────────────
  describe("5. RecentlyViewed & Zustand Store", () => {
    it("tracks viewed products and deduplicates them in Zustand store", () => {
      trackProductView({ id: "p1", name: "محصول یک", min_price: 10000 });
      trackProductView({ id: "p2", name: "محصول دو", min_price: 20000 });
      trackProductView({ id: "p1", name: "محصول یک به‌روزرسانی شده", min_price: 15000 });

      const state = useRecentlyViewedStore.getState();
      expect(state.products.length).toBe(2);
      expect(state.products[0].id).toBe("p1"); // p1 moved to top
      expect(state.products[1].id).toBe("p2");
    });

    it("renders RecentlyViewed section with recorded products", () => {
      useRecentlyViewedStore.setState({
        products: [
          {
            id: "rv-1",
            name: "کوله پشتی مسافرتی",
            slug: "travel-backpack",
            min_price: 800000,
            max_price: null,
            primary_image_url: "/bag.jpg",
            is_featured: false,
            variant_count: 1,
            viewedAt: Date.now(),
          },
        ],
      });

      render(<RecentlyViewed />);

      expect(screen.getByText("بازدید‌های اخیر شما")).toBeDefined();
      expect(screen.getByText("کوله پشتی مسافرتی")).toBeDefined();
    });
  });

  // ── 6. MegaMenu ─────────────────────────────────────────────────────────────
  describe("6. MegaMenu RTL Component", () => {
    const categories: any[] = [
      { id: "c1", name: "الکترونیک", slug: "electronics", parent_id: null, is_active: true },
      { id: "c2", name: "هدفون", slug: "headphones", parent_id: "c1", is_active: true },
      { id: "c3", name: "پوشاک", slug: "clothing", parent_id: null, is_active: true },
    ];

    it("renders trigger and opens multi-column flyout on click", () => {
      render(<MegaMenu categories={categories} label="منوی کالاها" />);

      const trigger = screen.getByRole("button", { name: /باز کردن منوی دسته‌بندی کالاها/ });
      expect(trigger).toBeDefined();

      fireEvent.click(trigger);

      expect(screen.getByText("الکترونیک")).toBeDefined();
      expect(screen.getByText("پوشاک")).toBeDefined();
      expect(screen.getByText(/همه‌ی الکترونیک/)).toBeDefined();
      expect(screen.getByText("هدفون")).toBeDefined();
    });
  });
});
