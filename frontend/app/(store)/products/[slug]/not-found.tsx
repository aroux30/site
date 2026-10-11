import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/ui/button";

/** The 404 document still needs a title: without one the browser tab and
 *  the error page in search consoles show the URL only.
 *
 *  A `metadata` export cannot be used here — Next.js ignores metadata from a
 *  segment-level `not-found.tsx` (only the root one supports it; verified
 *  live: the title stayed empty). React 19 hoists a plain `<title>` element
 *  from anywhere in the tree into `<head>`, which is the documented way for
 *  this file. The 404 status itself already keeps the URL out of the index;
 *  the root layout's robots rules cover the rest. */
export default function ProductNotFound() {
  return (
    <div className="container-page">
      <title>محصول مورد نظر یافت نشد</title>
      <div className="flex flex-col items-center justify-center py-20">
        <PackageX className="mb-4 h-16 w-16 text-muted-foreground" />
        <h1 className="mb-2 text-2xl font-bold text-foreground">
          محصول مورد نظر یافت نشد
        </h1>
        <p className="mb-8 max-w-md text-center text-muted-foreground">
          متأسفانه محصولی که به دنبال آن هستید وجود ندارد یا حذف شده است.
          لطفاً از صفحه محصولات بازدید کنید.
        </p>
        <Link href="/products">
          <Button>مشاهده محصولات</Button>
        </Link>
      </div>
    </div>
  );
}
