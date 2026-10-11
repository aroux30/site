"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import apiClient from "@/lib/api/client";
import type { Wallet } from "@/lib/api/wallet";
import { AccountDashboard } from "@/components/account/account-dashboard";
import { PageLoader } from "@/components/shared/page-state";

/**
 * The wallet has a master module switch. When it is off the whole surface must
 * disappear — not merely its buttons — so this deep link must not land on a
 * page that renders nothing. Until `/wallet` has answered we hold the loader
 * rather than flashing the dashboard and then bouncing, and on a failed read we
 * render the dashboard: hiding a page because the switch check failed would be
 * its own lie (the module may well be on).
 */
export default function AccountWalletPage() {
  const router = useRouter();
  const [verdict, setVerdict] = useState<"loading" | "show" | "redirect">("loading");

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<Wallet>("/wallet")
      .then((res) => {
        if (cancelled) return;
        setVerdict(res.data?.features?.enabled === false ? "redirect" : "show");
      })
      .catch(() => {
        if (!cancelled) setVerdict("show");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (verdict === "redirect") router.replace("/account");
  }, [verdict, router]);

  if (verdict === "loading") {
    return <PageLoader message="در حال بررسی وضعیت کیف پول..." />;
  }

  if (verdict === "redirect") return null;

  return <AccountDashboard initialTab="wallet" />;
}