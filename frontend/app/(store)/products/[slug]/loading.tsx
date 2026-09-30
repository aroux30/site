import { Skeleton } from "@/components/ui/skeleton";

export default function ProductDetailLoading() {
  return (
    <div className="container mx-auto px-4 py-8 space-y-8" dir="rtl">
      {/* Breadcrumb Skeleton */}
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-12" />
        <span className="text-muted-foreground/40">/</span>
        <Skeleton className="h-4 w-20" />
        <span className="text-muted-foreground/40">/</span>
        <Skeleton className="h-4 w-32" />
      </div>

      {/* Main Product Layout (2 Columns) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 items-start">
        {/* Gallery Column (Right in RTL) */}
        <div className="space-y-4">
          <Skeleton className="h-[420px] w-full rounded-3xl" />
          <div className="flex gap-3">
            <Skeleton className="h-20 w-20 rounded-2xl" />
            <Skeleton className="h-20 w-20 rounded-2xl" />
            <Skeleton className="h-20 w-20 rounded-2xl" />
            <Skeleton className="h-20 w-20 rounded-2xl" />
          </div>
        </div>

        {/* Details & Actions Column (Left in RTL) */}
        <div className="space-y-6">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-24 rounded-full" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>

          <div className="rounded-2xl border border-border/60 p-5 space-y-4 bg-muted/20">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-20" />
              <Skeleton className="h-8 w-36" />
            </div>
            <Skeleton className="h-4 w-48" />
          </div>

          {/* Volume Pricing Tiers Skeleton */}
          <div className="space-y-2">
            <Skeleton className="h-4 w-28" />
            <div className="grid grid-cols-3 gap-2">
              <Skeleton className="h-16 rounded-xl" />
              <Skeleton className="h-16 rounded-xl" />
              <Skeleton className="h-16 rounded-xl" />
            </div>
          </div>

          {/* Action Buttons Skeleton */}
          <div className="flex gap-3 pt-2">
            <Skeleton className="h-12 flex-1 rounded-xl" />
            <Skeleton className="h-12 w-12 rounded-xl" />
            <Skeleton className="h-12 w-12 rounded-xl" />
          </div>

          {/* Guarantee Badges Skeleton */}
          <div className="grid grid-cols-3 gap-3 pt-4 border-t border-border">
            <Skeleton className="h-14 rounded-xl" />
            <Skeleton className="h-14 rounded-xl" />
            <Skeleton className="h-14 rounded-xl" />
          </div>
        </div>
      </div>

      {/* Tabs Skeleton */}
      <div className="space-y-4 pt-8 border-t border-border">
        <div className="flex gap-3">
          <Skeleton className="h-10 w-28 rounded-lg" />
          <Skeleton className="h-10 w-28 rounded-lg" />
          <Skeleton className="h-10 w-28 rounded-lg" />
        </div>
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    </div>
  );
}
