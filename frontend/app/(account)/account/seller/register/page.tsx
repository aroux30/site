"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-message";
import {
  registerAsSeller,
  validateIban,
  validateNationalId,
} from "@/lib/api/seller";

/**
 * Seller sign-up.
 *
 * Validates the two identity fields to the same rules the server enforces
 * (IBAN = IR + 24 digits, national id = 10–14 digits) so a mistyped payout
 * account is caught here rather than after a failed submit. Both are optional
 * at this stage — the backend accepts a vendor without them — but a payout
 * cannot happen without an IBAN, so the field explains what it is for.
 *
 * On success it navigates to the seller dashboard rather than waiting for a
 * refetch: the new vendor is what `/vendors/me` will now return.
 */
export default function SellerRegisterPage() {
  const router = useRouter();

  const [storeName, setStoreName] = useState("");
  const [slug, setSlug] = useState("");
  const [description, setDescription] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [iban, setIban] = useState("");
  const [phone, setPhone] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const next: Record<string, string> = {};
    if (storeName.trim().length < 2) {
      next.storeName = "نام فروشگاه باید حداقل ۲ کاراکتر باشد.";
    }
    const ibanErr = validateIban(iban);
    if (ibanErr) next.iban = ibanErr;
    const nidErr = validateNationalId(nationalId);
    if (nidErr) next.nationalId = nidErr;

    setFieldErrors(next);
    if (Object.keys(next).length > 0) return;

    setSubmitting(true);
    try {
      await registerAsSeller({
        storeName: storeName.trim(),
        // An empty slug lets the backend derive one from the store name.
        slug: slug.trim() || undefined,
        description: description.trim() || null,
        nationalId: nationalId.trim() || null,
        ibanNumber: iban.trim() || null,
        contactPhone: phone.trim() || null,
      });
      router.push("/account/seller");
    } catch (err) {
      setError(
        apiErrorMessage(
          err,
          "ثبت‌نام فروشندگی ناموفق بود. اگر پیش‌تر ثبت‌نام کرده‌اید، به صفحه فروشندگی بروید.",
        ),
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6" dir="rtl">
      <div className="flex items-center gap-3">
        <Button asChild variant="ghost" size="sm">
          <Link href="/account/seller">
            <ArrowRight className="ms-1 h-4 w-4" />
            فروشندگی
          </Link>
        </Button>
        <h1 className="flex items-center gap-2 text-xl font-bold text-foreground">
          <Store className="h-5 w-5 text-primary" />
          ثبت‌نام فروشندگی
        </h1>
      </div>

      <Card className="p-4 text-[11px] leading-relaxed text-muted-foreground">
        هر حساب کاربری می‌تواند یک فروشگاه داشته باشد. پس از ثبت‌نام، وضعیت
        فروشگاه شما توسط تیم پلتفرم بررسی و تأیید می‌شود.
      </Card>

      <form onSubmit={submit} className="space-y-4">
        <Card className="space-y-4 p-4">
          <h2 className="text-sm font-bold text-foreground">اطلاعات فروشگاه</h2>

          <div className="space-y-1.5">
            <Label htmlFor="store-name">نام فروشگاه *</Label>
            <Input
              id="store-name"
              value={storeName}
              onChange={(e) => setStoreName(e.target.value)}
              aria-invalid={!!fieldErrors.storeName}
            />
            {fieldErrors.storeName && (
              <p role="alert" className="text-[11px] text-destructive">
                {fieldErrors.storeName}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="store-slug">نشانی فروشگاه (اختیاری)</Label>
            <Input
              id="store-slug"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              dir="ltr"
              className="font-mono"
              placeholder="pars-store"
            />
            <p className="text-[11px] text-muted-foreground">
              اگر خالی بماند، از نام فروشگاه ساخته می‌شود.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="store-desc">معرفی فروشگاه (اختیاری)</Label>
            <Textarea
              id="store-desc"
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </Card>

        <Card className="space-y-4 p-4">
          <h2 className="text-sm font-bold text-foreground">
            اطلاعات تسویه و هویت
          </h2>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            این اطلاعات برای واریز درآمد فروش لازم است. تا زمانی که ثبت نشوند،
            امکان تسویه وجود ندارد. این داده‌ها فقط در اختیار تیم مالی است و در
            صفحه عمومی فروشگاه نمایش داده نمی‌شود.
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="national-id">کد ملی</Label>
            <Input
              id="national-id"
              value={nationalId}
              onChange={(e) => setNationalId(e.target.value)}
              dir="ltr"
              className="font-mono"
              inputMode="numeric"
              aria-invalid={!!fieldErrors.nationalId}
              placeholder="۱۰ تا ۱۴ رقم"
            />
            {fieldErrors.nationalId && (
              <p role="alert" className="text-[11px] text-destructive">
                {fieldErrors.nationalId}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="iban">شماره شبا</Label>
            <Input
              id="iban"
              value={iban}
              onChange={(e) => setIban(e.target.value)}
              dir="ltr"
              className="font-mono"
              aria-invalid={!!fieldErrors.iban}
              placeholder="IR120120000000001234567890"
            />
            {fieldErrors.iban && (
              <p role="alert" className="text-[11px] text-destructive">
                {fieldErrors.iban}
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="contact-phone">تلفن تماس (اختیاری)</Label>
            <Input
              id="contact-phone"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              dir="ltr"
              className="font-mono"
              placeholder="09121234567"
            />
          </div>
        </Card>

        {error && (
          <div
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            {error}
          </div>
        )}

        <div className="flex gap-2">
          <Button type="submit" disabled={submitting}>
            {submitting ? "در حال ثبت‌نام..." : "ثبت‌نام فروشندگی"}
          </Button>
          <Button asChild type="button" variant="outline">
            <Link href="/account/seller">انصراف</Link>
          </Button>
        </div>
      </form>
    </div>
  );
}
