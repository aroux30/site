// @vitest-environment jsdom

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useIdleTimeout } from "../use-idle-timeout";

const mockReplace = vi.fn();
const mockLogout = vi.fn().mockResolvedValue(undefined);

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: mockReplace,
    push: vi.fn(),
  }),
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    logout: mockLogout,
  }),
}));

describe("useIdleTimeout security hook", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockReplace.mockClear();
    mockLogout.mockClear();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it("should trigger logout and redirect after timeout expires", async () => {
    const { unmount } = renderHook(() => useIdleTimeout(1000));

    await act(async () => {
      vi.advanceTimersByTime(1100);
    });

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockReplace).toHaveBeenCalledWith("/login?reason=idle_timeout&redirect=/admin/dashboard");

    unmount();
  });

  it("should reset timer when user interaction occurs", async () => {
    const { unmount } = renderHook(() => useIdleTimeout(5000));

    // Advance 3s (not expired)
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });
    expect(mockLogout).not.toHaveBeenCalled();

    // Reset via activity
    await act(async () => {
      window.dispatchEvent(new Event("mousemove"));
    });

    // Advance another 3s (total 6s from start, but only 3s from reset)
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });
    expect(mockLogout).not.toHaveBeenCalled();

    // Now advance past the reset timeout (3000 more -> 6000 since reset)
    await act(async () => {
      vi.advanceTimersByTime(3000);
    });
    expect(mockLogout).toHaveBeenCalledTimes(1);

    unmount();
  });
});
