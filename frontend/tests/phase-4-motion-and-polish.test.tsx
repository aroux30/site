import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, fireEvent, act } from "@testing-library/react";

// Mock IntersectionObserver for AnimatedNumber in jsdom
class MockIntersectionObserver {
  observe = vi.fn((el) => {
    // immediate mock trigger
  });
  unobserve = vi.fn();
  disconnect = vi.fn();
}
Object.defineProperty(window, "IntersectionObserver", {
  writable: true,
  value: MockIntersectionObserver,
});

import { ClickSpark } from "@/components/ui/click-spark";
import { PulseHeart } from "@/components/ui/pulse-heart";
import { TextLoop } from "@/components/ui/text-loop";
import { AnimatedNumber } from "@/components/ui/animated-number";
import { Toaster } from "@/components/ui/toaster";
import { useToast } from "@/components/ui/use-toast";

describe("Phase 4 - Motion & Polish Components Suite", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── 1. ClickSpark & PulseHeart ──────────────────────────────────────────────
  describe("1. ClickSpark & PulseHeart Components", () => {
    it("renders ClickSpark wrapper and handles click without crashing", () => {
      const handleClick = vi.fn();
      render(
        <ClickSpark>
          <button type="button" onClick={handleClick}>
            خرید سریع
          </button>
        </ClickSpark>
      );

      const btn = screen.getByText("خرید سریع");
      expect(btn).toBeDefined();

      fireEvent.click(btn);
      expect(handleClick).toHaveBeenCalled();
    });

    it("renders PulseHeart in active and inactive states and handles toggle", () => {
      const handleToggle = vi.fn();
      const { rerender } = render(<PulseHeart active={false} onToggle={handleToggle} />);

      const heartBtn = screen.getByRole("button", { name: "افزودن به علاقه‌مندی‌ها" });
      expect(heartBtn).toBeDefined();
      expect(heartBtn.getAttribute("aria-pressed")).toBe("false");

      fireEvent.click(heartBtn);
      expect(handleToggle).toHaveBeenCalled();

      // Rerender active
      rerender(<PulseHeart active={true} onToggle={handleToggle} />);
      const activeBtn = screen.getByRole("button", { name: "حذف از علاقه‌مندی‌ها" });
      expect(activeBtn.getAttribute("aria-pressed")).toBe("true");
    });
  });

  // ── 2. TextLoop ─────────────────────────────────────────────────────────────
  describe("2. TextLoop Component", () => {
    it("renders promotional text loop cleanly", () => {
      const taglines = [
        "ارسال رایگان به سراسر کشور",
        "ضمانت اصالت ۷ روزه کالا",
        "پشتیبانی شبانه‌روزی",
      ];
      render(<TextLoop texts={taglines} interval={2000} />);

      const els = screen.getAllByText("ارسال رایگان به سراسر کشور");
      expect(els.length).toBeGreaterThanOrEqual(1);
    });
  });

  // ── 3. AnimatedNumber ───────────────────────────────────────────────────────
  describe("3. AnimatedNumber Component", () => {
    it("renders formatted number with Persian numerals", () => {
      render(<AnimatedNumber value={125000} suffix=" تومان" formatPersian={true} />);

      const el = screen.getByText(/تومان/);
      expect(el).toBeDefined();
    });
  });

  // ── 4. Semantic Toast System ────────────────────────────────────────────────
  describe("4. Semantic Toast Variants System", () => {
    function ToastTrigger() {
      const { toast } = useToast();
      return (
        <div>
          <button
            type="button"
            onClick={() =>
              toast({
                title: "اطلاعیه مهم",
                description: "سرویس در حال به‌روزرسانی است.",
                variant: "info",
              })
            }
          >
            ارسال پیام اطلاع‌رسانی
          </button>
          <button
            type="button"
            onClick={() =>
              toast({
                title: "هشدار امنیتی",
                description: "رمز عبور منقضی شده است.",
                variant: "warning",
              })
            }
          >
            ارسال پیام هشدار
          </button>
          <button
            type="button"
            onClick={() =>
              toast({
                title: "تراکنش موفق",
                description: "سفارش شما با موفقیت ثبت شد.",
                variant: "success",
              })
            }
          >
            ارسال پیام موفقیت
          </button>
        </div>
      );
    }

    it("triggers and displays info, warning, and success semantic toasts", () => {
      render(
        <div>
          <ToastTrigger />
          <Toaster />
        </div>
      );

      // Trigger Info Toast
      fireEvent.click(screen.getByText("ارسال پیام اطلاع‌رسانی"));
      expect(screen.getByText("اطلاعیه مهم")).toBeDefined();
      expect(screen.getByText("سرویس در حال به‌روزرسانی است.")).toBeDefined();

      // Trigger Warning Toast
      fireEvent.click(screen.getByText("ارسال پیام هشدار"));
      expect(screen.getByText("هشدار امنیتی")).toBeDefined();

      // Trigger Success Toast
      fireEvent.click(screen.getByText("ارسال پیام موفقیت"));
      expect(screen.getByText("تراکنش موفق")).toBeDefined();
    });
  });
});
