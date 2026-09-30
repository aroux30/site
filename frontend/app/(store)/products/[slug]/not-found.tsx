import Link from "next/link";
import { PackageX } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ProductNotFound() {
  return (
    <div className="container-page">
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
