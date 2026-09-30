"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/**
 * Fallback for gateway redirects that arrive without a payment identifier.
 * Payment state is never derived from URL parameters here; the user is sent
 * to their orders where the server-reported status is shown.
 */
export default function PaymentCallbackFallbackPage() {
  const router = useRouter();

  useEffect(() => {
    const t = setTimeout(() => router.replace("/account/orders"), 1200);
    return () => clearTimeout(t);
  }, [router]);

  return (
    <div className="container-page flex min-h-[60vh] items-center justify-center py-16">
      <p className="text-sm text-muted-foreground">
        در حال انتقال به صفحه سفارش‌ها…
      </p>
    </div>
  );
}
