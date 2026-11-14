"use client";

import { useEffect, useCallback, useSyncExternalStore } from "react";

// ─── Service Worker Registration ─────────────────────────

/** Register the service worker in production only. */
export function registerServiceWorker(): void {
  if (
    typeof window === "undefined" ||
    !("serviceWorker" in navigator)
  ) {
    return;
  }

  // ── Development heal ────────────────────────────────────────────────
  // A service worker registered by an OLD build keeps serving stale pages
  // and API responses from its v1-* caches on that origin — the source of
  // «ویژگی‌ها غیب شدند» / hydration crashes that only happened on one host
  // (localhost) and never on 127.0.0.1. In dev there is no reason to keep
  // one: unregister it and drop every cache, on every load (idempotent).
  if (process.env.NODE_ENV !== "production") {
    window.addEventListener("load", async () => {
      try {
        const registrations = await navigator.serviceWorker.getRegistrations();
        await Promise.all(registrations.map((r) => r.unregister()));
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
        if (registrations.length > 0) {
          console.info(
            "[SW] Development mode: service worker and caches cleared.",
          );
        }
      } catch {
        // Nothing registered / storage unavailable — nothing to clean.
      }
    });
    return;
  }

  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js", {
        scope: "/",
      });

      // Listen for updates
      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        newWorker.addEventListener("statechange", () => {
          if (
            newWorker.state === "installed" &&
            navigator.serviceWorker.controller
          ) {
            // New version available — notify subscribers
            pwaState.updateAvailable = true;
            pwaState.registration = registration;
            notifySubscribers();
          }
        });
      });

      pwaState.registration = registration;
    } catch (err) {
      console.error("[SW] Registration failed:", err);
    }
  });
}

// ─── PWA State Store ─────────────────────────────────────

interface PWAState {
  isOnline: boolean;
  canInstall: boolean;
  isInstalled: boolean;
  updateAvailable: boolean;
  deferredPrompt: BeforeInstallPromptEvent | null;
  registration: ServiceWorkerRegistration | null;
}

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const pwaState: PWAState = {
  isOnline: typeof navigator !== "undefined" ? navigator.onLine : true,
  canInstall: false,
  isInstalled: false,
  updateAvailable: false,
  deferredPrompt: null,
  registration: null,
};

const subscribers = new Set<() => void>();

function notifySubscribers() {
  // Create a new snapshot reference so useSyncExternalStore detects the change
  snapshotRef = { ...pwaState };
  subscribers.forEach((cb) => cb());
}

let snapshotRef: PWAState = { ...pwaState };

function subscribe(callback: () => void): () => void {
  subscribers.add(callback);
  return () => subscribers.delete(callback);
}

const serverSnapshot: PWAState = {
  isOnline: true,
  canInstall: false,
  isInstalled: false,
  updateAvailable: false,
  deferredPrompt: null,
  registration: null,
};

function getSnapshot(): PWAState {
  return snapshotRef;
}

function getServerSnapshot(): PWAState {
  return serverSnapshot;
}

// ─── Browser event listeners (initialized once) ─────────

let listenersInitialized = false;

function initListeners() {
  if (listenersInitialized || typeof window === "undefined") return;
  listenersInitialized = true;

  // Online/offline
  window.addEventListener("online", () => {
    pwaState.isOnline = true;
    notifySubscribers();
  });
  window.addEventListener("offline", () => {
    pwaState.isOnline = false;
    notifySubscribers();
  });

  // Install prompt
  window.addEventListener("beforeinstallprompt", ((e: Event) => {
    e.preventDefault();
    pwaState.deferredPrompt = e as BeforeInstallPromptEvent;
    pwaState.canInstall = true;
    notifySubscribers();
  }) as EventListener);

  // Detect if already installed
  window.addEventListener("appinstalled", () => {
    pwaState.isInstalled = true;
    pwaState.canInstall = false;
    pwaState.deferredPrompt = null;
    notifySubscribers();
  });

  // Check standalone mode (already installed)
  if (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as unknown as { standalone?: boolean }).standalone === true
  ) {
    pwaState.isInstalled = true;
    notifySubscribers();
  }
}

// ─── usePWA Hook ─────────────────────────────────────────

export interface UsePWAReturn {
  isOnline: boolean;
  canInstall: boolean;
  isInstalled: boolean;
  updateAvailable: boolean;
  installPrompt: () => Promise<boolean>;
  applyUpdate: () => void;
}

/**
 * React hook for PWA install state, online/offline status, and update
 * notifications.
 */
export function usePWA(): UsePWAReturn {
  useEffect(() => {
    initListeners();
  }, []);

  const state = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const installPrompt = useCallback(async (): Promise<boolean> => {
    const prompt = pwaState.deferredPrompt;
    if (!prompt) return false;

    await prompt.prompt();
    const { outcome } = await prompt.userChoice;

    if (outcome === "accepted") {
      pwaState.deferredPrompt = null;
      pwaState.canInstall = false;
      pwaState.isInstalled = true;
      notifySubscribers();
      return true;
    }
    return false;
  }, []);

  const applyUpdate = useCallback(() => {
    const reg = pwaState.registration;
    if (reg?.waiting) {
      reg.waiting.postMessage({ type: "SKIP_WAITING" });
      window.location.reload();
    }
  }, []);

  return {
    isOnline: state.isOnline,
    canInstall: state.canInstall,
    isInstalled: state.isInstalled,
    updateAvailable: state.updateAvailable,
    installPrompt,
    applyUpdate,
  };
}
