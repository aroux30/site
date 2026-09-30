"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Loader2, ShoppingBag, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cartApi } from "@/lib/api/cart";
import { useToast } from "@/components/ui/use-toast";
import { toPersianDigits, formatPrice } from "@/lib/utils";

function RecoverForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const token = searchParams.get("token");

  const [state, setState] = useState<"loading" | "done" | "error">("loading");
  const [itemCount, setItemCount] = useState(0);
  const [subtotal, setSubtotal] = useState(0);

  useEffect(() => {
    if (!token) {
      setState("error");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await cartApi.recoverCart(token);
        if (cancelled) return;
        setItemCount(res.cart?.item_count ?? 0);
        setSubtotal(res.cart?.subtotal ?? 0);
        setState("done");
        toast({
          title: "سبد خرید شما بازیابی شد",
          description: "آیتم‌های قبلی شما به سبد برگشتند.",
        });
      } catch {
        if (!cancelled) setState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [token, toast]);

  if (state === "loading") {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        <p className="text-muted-foreground">در حال بازیابی سبد خرید…</p>
      </div>
    );
  }

  if (state === "error") {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-4 py-16 text-center">
        <AlertCircle className="h-12 w-12 text-destructive" />
        <h1 className="text-xl font-bold">لینک بازیابی نامعتبر یا منقضی شده است</h1>
        <p className="text-sm text-muted-foreground">
          ممکن است سبد شما قبلاً تسویه شده یا مدت لینک به پایان رسیده باشد.
        </p>
        <Link href="/cart">
          <Button>مشاهده سبد خرید</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md py-16">
      <Card>
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex h-12 w-12 items-center justify-center rounded-full bg-primary/10">
            <ShoppingBag className="h-6 w-6 text-primary" />
          </div>
          <CardTitle>سبد خرید شما بازیابی شد</CardTitle>
          <CardDescription>
            {toPersianDigits(itemCount)} قلم کالا به ارزش {formatPrice(subtotal)} در سبد شماست.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <Button className="w-full" onClick={() => router.push("/checkout")}>
            ادامه خرید و تسویه
          </Button>
          <Button className="w-full" variant="outline" onClick={() => router.push("/cart")}>
            مرور سبد خرید
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function RecoverCartPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[50vh] items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <RecoverForm />
    </Suspense>
  );
}
