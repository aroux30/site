import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      <div className="mx-auto max-w-2xl text-center">
        <h1 className="mb-6 text-4xl font-bold tracking-tight text-foreground sm:text-5xl">
          فروشگاه آنلاین
        </h1>
        <p className="mb-8 text-lg leading-8 text-muted-foreground">
          به فروشگاه اینترنتی ما خوش آمدید. بهترین محصولات را با بهترین قیمت‌ها
          پیدا کنید.
        </p>
        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/products"
            className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-8 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            مشاهده محصولات
          </Link>
          <Link
            href="/account"
            className="inline-flex h-11 items-center justify-center rounded-md border border-input bg-background px-8 text-sm font-medium ring-offset-background transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            ورود به حساب
          </Link>
        </div>
      </div>
    </main>
  );
}
