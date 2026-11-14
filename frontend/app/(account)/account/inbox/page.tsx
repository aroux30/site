"use client";

import { AccountDashboard } from "@/components/account/account-dashboard";

/**
 * Notification inbox route.
 *
 * `/account/notifications` is the *preferences* screen (channel/category
 * toggles); this route is the list itself. Before it existed, every in-app
 * notification (orders, wallet, referral rewards) was written to the
 * database with no surface that ever rendered it.
 */
export default function AccountInboxPage() {
  return <AccountDashboard initialTab="notifications" />;
}
