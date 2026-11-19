"use client";

/**
 * Shared bottom dock for the floating storefront bars (compare + cart).
 *
 * Both bars used to be independently `fixed bottom-*` elements — and when a
 * shopper had items in BOTH the compare list and the cart, they rendered at
 * the exact same coordinates and stacked on top of each other, at every
 * viewport (found live 2026-11-01; the user reported bars colliding across
 * breakpoints). One dock stacks them vertically with a gap and owns the
 * viewport-aware offset (above the mobile bottom nav + chat FAB), so the
 * bars can never collide again, whatever combination is visible.
 *
 * The dock is pointer-events-none so its empty area never swallows clicks;
 * each bar re-enables pointer events on itself.
 */

export function FloatingBottomDock({ children }: { children: React.ReactNode }) {
  return (
    <div
      className="pointer-events-none fixed bottom-48 sm:bottom-24 min-[830px]:bottom-4 left-1/2 -translate-x-1/2 z-40 flex w-[94%] max-w-2xl flex-col gap-2"
    >
      {children}
    </div>
  );
}
