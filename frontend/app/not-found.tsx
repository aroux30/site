import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="mx-auto max-w-md text-center">
        <h1 className="mb-2 text-8xl font-bold text-primary">۴۰۴</h1>
        <h2 className="mb-4 text-2xl font-semibold text-foreground">
          صفحه مورد نظر یافت نشد
        </h2>
        <p className="mb-8 text-muted-foreground">
          متأسفانه صفحه‌ای که به دنبال آن هستید وجود ندارد یا منتقل شده است.
        </p>
        <Link
          href="/"
          className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-8 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          بازگشت به صفحه اصلی
        </Link>
      </div>
    </main>
  );
}
