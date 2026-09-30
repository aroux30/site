import { Skeleton } from "@/components/ui/skeleton";

export default function FAQLoading() {
  return (
    <div className="container-page py-10 space-y-8" dir="rtl">
      {/* Header Skeleton */}
      <div className="text-center space-y-3 max-w-xl mx-auto">
        <Skeleton className="h-8 w-48 mx-auto" />
        <Skeleton className="h-4 w-72 mx-auto" />
        <Skeleton className="h-10 w-full max-w-md mx-auto rounded-xl mt-4" />
      </div>

      {/* Category Pills Skeleton */}
      <div className="flex flex-wrap items-center justify-center gap-2 pt-2">
        <Skeleton className="h-9 w-28 rounded-full" />
        <Skeleton className="h-9 w-28 rounded-full" />
        <Skeleton className="h-9 w-28 rounded-full" />
        <Skeleton className="h-9 w-28 rounded-full" />
      </div>

      {/* Accordion List Skeleton */}
      <div className="max-w-3xl mx-auto space-y-3 pt-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="rounded-xl border border-border/80 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-4 w-4 rounded-full" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
