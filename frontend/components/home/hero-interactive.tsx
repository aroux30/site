"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { Sparkles, Zap } from "lucide-react";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { Button } from "@/components/ui/button";

// Defer Three.js / WebGL loading strictly on client side to protect LCP & TTFB
const Hero3DScene = dynamic(
  () => import("@/components/3d/hero-scene").then((mod) => mod.Hero3DScene),
  {
    ssr: false,
    loading: () => (
      <div className="h-[380px] md:h-[450px] w-full flex items-center justify-center">
        <div className="h-48 w-48 rounded-full bg-emerald-500/10 blur-3xl animate-pulse" />
      </div>
    ),
  }
);

export function HeroInteractive() {
  return (
    <div className="relative w-full">
      {/* 3D Visual Centerpiece */}
      <div className="relative h-[380px] md:h-[450px] w-full flex items-center justify-center">
        <Hero3DScene />
      </div>

      {/* Floating Interactive Badge */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 z-20 whitespace-nowrap">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-background/80 backdrop-blur-md border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-semibold shadow-lg">
          <Sparkles className="w-3.5 h-3.5 animate-spin" style={{ animationDuration: "4s" }} />
          <span>نمای سه‌بعدی تعاملی ۳۶۰ درجه</span>
        </div>
      </div>
    </div>
  );
}

export function HeroActions() {
  return (
    <div className="flex flex-wrap items-center justify-center lg:justify-start gap-4">
      <Link href="/products">
        <ShimmerButton className="shadow-2xl">
          <span className="whitespace-pre-wrap text-center text-sm font-bold leading-none tracking-tight text-white dark:from-white dark:to-slate-900/10 lg:text-base">
            مشاهده کاتالوگ محصولات
          </span>
        </ShimmerButton>
      </Link>
      <Link href="/products?sort_by=price&sort_order=desc">
        <Button
          variant="outline"
          size="lg"
          className="rounded-2xl border-emerald-500/30 hover:bg-emerald-500/10 text-foreground font-bold px-6 h-12"
        >
          <Zap className="w-4 h-4 ml-2 text-amber-500" />
          تخفیف‌های ویژه روز
        </Button>
      </Link>
    </div>
  );
}
