/**
 * Web-push subscription for the storefront.
 *
 * Registration lives in ``lib/sw-register.ts`` (it also owns the install and
 * offline state the banners read). This module only *uses* the registered
 * worker: it asks permission, subscribes the browser, and hands the
 * subscription to our backend. Splitting it this way keeps one registration
 * call — two modules registering the same worker with different options is
 * undefined behaviour in some browsers.
 *
 * Everything here is best-effort and silent-by-default: a browser without
 * service workers, a user who denies notifications, or a dev server on a
 * non-secure origin must all leave the site working exactly as before.
 */

import apiClient from "./api/client";

/** True when the browser can do everything a PWA needs. */
export function isPwaSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/** The registered worker, or null when none is active yet. */
async function currentRegistration(): Promise<ServiceWorkerRegistration | null> {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }
  return (await navigator.serviceWorker.getRegistration()) ?? null;
}

/** base64url → Uint8Array, the format ``pushManager.subscribe`` wants. */
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  const output = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    output[i] = rawData.charCodeAt(i);
  }
  return output;
}

export type PushSubscribeResult =
  | { ok: true }
  | { ok: false; reason: "unsupported" | "denied" | "no-vapid-key" | "failed" };

/**
 * Ask for notification permission and register the browser's subscription
 * with our backend.
 *
 * Permission is requested here and only here — never on page load. A
 * permission prompt the user did not ask for is the fastest way to get
 * permanently denied, and the denial is sticky.
 */
export async function subscribeToPush(): Promise<PushSubscribeResult> {
  if (!isPwaSupported()) {
    return { ok: false, reason: "unsupported" };
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return { ok: false, reason: "denied" };
  }

  let publicKey: string | null = null;
  try {
    const res = await apiClient.get<{ public_key: string | null }>(
      "/notifications/push/public-key",
    );
    publicKey = res.data?.public_key ?? null;
  } catch {
    return { ok: false, reason: "failed" };
  }

  // The backend reports a null key when pywebpush/VAPID is not configured.
  // Subscribing anyway would create a browser subscription that can never
  // receive anything — a worse outcome than telling the user it is off.
  if (!publicKey) {
    return { ok: false, reason: "no-vapid-key" };
  }

  try {
    const registration = await currentRegistration();
    if (!registration) {
      // Registration is the provider's job and happens on every page load;
      // reaching here means it failed or was blocked, and subscribing without
      // a worker cannot deliver anything.
      return { ok: false, reason: "failed" };
    }

    await navigator.serviceWorker.ready;

    const subscription = await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
    });

    await apiClient.post("/notifications/push/subscribe", {
      subscription: subscription.toJSON(),
    });
    return { ok: true };
  } catch {
    return { ok: false, reason: "failed" };
  }
}

/** Remove the browser subscription and tell the backend to drop it. */
export async function unsubscribeFromPush(): Promise<boolean> {
  if (!isPwaSupported()) return false;
  try {
    const registration = await currentRegistration();
    const subscription = await registration?.pushManager.getSubscription();
    if (!subscription) return true;

    const endpoint = subscription.endpoint;
    await subscription.unsubscribe();
    try {
      await apiClient.post("/notifications/push/unsubscribe", { endpoint });
    } catch {
      // The browser subscription is already gone; the backend row is stale
      // but harmless, and the send path drops expired endpoints anyway.
    }
    return true;
  } catch {
    return false;
  }
}

/** True when this browser currently holds a push subscription. */
export async function hasPushSubscription(): Promise<boolean> {
  if (!isPwaSupported()) return false;
  try {
    const registration = await currentRegistration();
    const subscription = await registration?.pushManager.getSubscription();
    return Boolean(subscription);
  } catch {
    return false;
  }
}
