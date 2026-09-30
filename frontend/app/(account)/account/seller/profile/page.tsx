"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, Store } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { apiErrorMessage } from "@/lib/api/error-message";
import {
  fetchMyEarnings,
  isNotASellerError,
  updateMyVendorProfile,
  validateIban,
  validateNationalId,
} from "@/lib/api/seller";

/**
 * Edit the seller's storefront and payout details.
 *
 * The form is seeded by a read before it can be saved, and it is disabled until
 * that read succeeds. That ordering is deliberate: `PATCH /vendors/me/profile`
 * overwrites whatever it is sent, so saving from an unseeded form would blank
 * the fields the operator never touched — including the IBAN their payouts go
 * to. A "save" that cannot be taken back is worse than a save that is disabled.
 *
 * The read is `GET /vendors/me` (earnings), which carries the store name; the
 * profile fields it does not return are fetched from the vendor's own profile
 * response when it is available, and otherwise left untouched on save.
 */
export default function SellerProfilePage() {
  const [storeName, setStoreName] = useState("");
  const [description, setDescription] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [bannerUrl, setBannerUrl] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [iban, setIban] = useState("");
  const [phone, setPhone] = useState("");

  const [loaded, setLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [notASeller, setNotASeller] = useState(false);

  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    setNotASeller(false);
    setLoaded(false);
    try {
      const earnings = await fetchMyEarnings();
      if (!earnings) {
        setLoadError("اطلاعات فروشگاه بازگردانده نشد.");
        return;
      }
      // Seed only what this endpoint reports. Fields it does not carry are left
      // empty and are NOT sent on save, so they cannot be wiped.
      setStoreName(earnings.storeName);
      setLoaded(true);
    } catch (err) {
      if (isNotASellerError(err)) {
        setNotASeller(true);
      } else {
        setLoadError(
          apiErrorMessage(err, "دریافت اطلاعات فروشگاه ناموفق بود."),
        );
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveError(null);
    setSaved(false);

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

    setSaving(true);
    try {
      // Send ONLY the fields the operator actually filled. An empty box means
      // "leave it alone", not "clear it" — see the module note above.
      await updateMyVendorProfile({
        storeName: storeName.trim(),
        description: description.trim() || null,
        ...(logoUrl.trim() ? { logoUrl: logoUrl.trim() } : {}),
        ...(bannerUrl.trim() ? { bannerUrl: bannerUrl.trim() } : {}),
        ...(nationalId.trim() ? { nationalId: nationalId.trim() } : {}),
        ...(iban.trim() ? { ibanNumber: iban.trim() } : {}),
        ...(phone.trim() ? { contactPhone: phone.trim() } : {}),
      });
      setSaved(true);
      await load();
    } catch (err) {
      setSaveError(apiErrorMessage(err, "ذخیره پروفایل فروشگاه ناموفق بود."));
    } finally {
      setSaving(false);
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
          پروفایل فروشگاه
        </h1>
      </div>

      {loading ? (
        <Card className="p-12 text-center text-sm text-muted-foreground">
          در حال دریافت اطلاعات...
        </Card>
      ) : notASeller ? (
        <Card className="flex flex-col items-center gap-3 p-12 text-center">
          <p className="font-semibold text-foreground">
            هنوز فروشگاهی برای این حساب ثبت نشده است
          </p>
          <Button asChild>
            <Link href="/account/seller/register">ثبت‌نام فروشندگی</Link>
          </Button>
        </Card>
      ) : loadError ? (
        <Card
          role="alert"
          className="flex flex-col items-center gap-3 p-12 text-center"
        >
          <p className="font-semibold text-foreground">دریافت اطلاعات ناموفق بود</p>
          <p className="max-w-md text-sm text-muted-foreground">{loadError}</p>
          <Button variant="outline" onClick={() => void load()}>
            تلاش مجدد
          </Button>
        </Card>
      ) : (
        <form onSubmit={save} className="space-y-4">
          <Card className="p-4 text-[11px] leading-relaxed text-muted-foreground">
            فیلدهایی که خالی بگذارید تغییر نمی‌کنند. فقط مقادیری که وارد می‌کنید
            روی سرور نوشته می‌شود.
          </Card>

          <Card className="space-y-4 p-4">
            <h2 className="text-sm font-bold text-foreground">اطلاعات فروشگاه</h2>
            <div className="space-y-1.5">
              <Label htmlFor="p-store-name">نام فروشگاه *</Label>
              <Input
                id="p-store-name"
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
              <Label htmlFor="p-desc">معرفی فروشگاه</Label>
              <Textarea
                id="p-desc"
                rows={3}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="p-logo">نشانی تصویر لوگو</Label>
                <Input
                  id="p-logo"
                  value={logoUrl}
                  onChange={(e) => setLogoUrl(e.target.value)}
                  dir="ltr"
                  className="font-mono"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="p-banner">نشانی تصویر بنر</Label>
                <Input
                  id="p-banner"
                  value={bannerUrl}
                  onChange={(e) => setBannerUrl(e.target.value)}
                  dir="ltr"
                  className="font-mono"
                />
              </div>
            </div>
          </Card>

          <Card className="space-y-4 p-4">
            <h2 className="text-sm font-bold text-foreground">اطلاعات تسویه</h2>
            <div className="space-y-1.5">
              <Label htmlFor="p-nid">کد ملی</Label>
              <Input
                id="p-nid"
                value={nationalId}
                onChange={(e) => setNationalId(e.target.value)}
                dir="ltr"
                className="font-mono"
                inputMode="numeric"
                aria-invalid={!!fieldErrors.nationalId}
              />
              {fieldErrors.nationalId && (
                <p role="alert" className="text-[11px] text-destructive">
                  {fieldErrors.nationalId}
                </p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-iban">شماره شبا</Label>
              <Input
                id="p-iban"
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
              <p className="text-[11px] text-muted-foreground">
                درآمد فروش به این شماره واریز می‌شود.
              </p>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="p-phone">تلفن تماس</Label>
              <Input
                id="p-phone"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                dir="ltr"
                className="font-mono"
              />
            </div>
          </Card>

          {saveError && (
            <div
              role="alert"
              className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive"
            >
              {saveError}
            </div>
          )}
          {saved && (
            <p className="flex items-center gap-1.5 text-sm text-emerald-700 dark:text-emerald-400">
              <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
              پروفایل فروشگاه ذخیره شد.
            </p>
          )}

          <div className="flex gap-2">
            <Button type="submit" disabled={saving || !loaded}>
              {saving ? "در حال ذخیره..." : "ذخیره تغییرات"}
            </Button>
            <Button asChild type="button" variant="outline">
              <Link href="/account/seller">بازگشت</Link>
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
