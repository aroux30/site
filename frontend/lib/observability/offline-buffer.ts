/**
 * Offline Telemetry Resend Buffer
 * Persists failed telemetry logs and events in localStorage (with safe fallback) when network is unavailable,
 * and automatically retries sending upon network recovery (online event).
 */

import { logger } from "./logger";

// ponytail: localStorage batch buffer -> skipped: background sync service worker, add when background sync API widely supported.

export interface QueuedTelemetryItem {
  id: string;
  endpoint: string;
  payload: unknown;
  timestamp: number;
  attempts: number;
}

const STORAGE_KEY = "karta_offline_telemetry_queue";
const MAX_QUEUE_ITEMS = 50;
const MAX_RETRY_ATTEMPTS = 5;
const ITEM_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

let memoryStore: Record<string, string> = {};

interface SimpleStorage {
  getItem: (key: string) => string | null;
  setItem: (key: string, value: string) => void;
  removeItem: (key: string) => void;
}

function getStorage(): SimpleStorage {
  if (
    typeof window !== "undefined" &&
    typeof window.localStorage !== "undefined"
  ) {
    try {
      const testKey = "__karta_test_storage__";
      window.localStorage.setItem(testKey, "1");
      const read = window.localStorage.getItem(testKey);
      window.localStorage.removeItem(testKey);
      if (read === "1") {
        return window.localStorage;
      }
    } catch {
      // Fallback to memoryStore if localStorage access is denied or throws in Node 22
    }
  }

  return {
    getItem: (key: string) => (key in memoryStore ? memoryStore[key]! : null),
    setItem: (key: string, value: string) => {
      memoryStore[key] = value;
    },
    removeItem: (key: string) => {
      delete memoryStore[key];
    },
  };
}

/**
 * Safely loads queued items from storage.
 */
function loadQueue(): QueuedTelemetryItem[] {
  try {
    const storage = getStorage();
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    const now = Date.now();
    // Filter out expired items
    return parsed.filter(
      (item) =>
        item &&
        typeof item === "object" &&
        now - (item.timestamp || 0) < ITEM_TTL_MS,
    );
  } catch {
    return [];
  }
}

/**
 * Safely saves queued items to storage.
 */
function saveQueue(queue: QueuedTelemetryItem[]): void {
  try {
    const storage = getStorage();
    storage.setItem(STORAGE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE_ITEMS)));
  } catch {
    // Ignore storage quota exceeded or private browsing errors
  }
}

/**
 * Enqueues a telemetry payload to be sent when network connectivity is restored.
 */
export function enqueueOfflinePayload(
  payload: unknown,
  endpoint = "/api/v1/observability/client-logs",
): void {
  const queue = loadQueue();
  const id =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : "off-" + Math.random().toString(36).substring(2, 10);

  const item: QueuedTelemetryItem = {
    id,
    endpoint,
    payload,
    timestamp: Date.now(),
    attempts: 0,
  };

  queue.push(item);
  saveQueue(queue);
}

/**
 * Flushes the queued telemetry items to their respective endpoints.
 */
export async function flushOfflineBuffer(): Promise<number> {
  // If browser reports offline, don't attempt flush yet
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return 0;
  }

  const queue = loadQueue();
  if (queue.length === 0) return 0;

  const remaining: QueuedTelemetryItem[] = [];
  let flushedCount = 0;

  for (const item of queue) {
    if (item.attempts >= MAX_RETRY_ATTEMPTS) {
      // Discard after max retries
      continue;
    }

    try {
      if (typeof fetch === "function") {
        const response = await fetch(item.endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(item.payload),
          keepalive: true,
        });

        if (response.ok) {
          flushedCount++;
          continue;
        }
      }
    } catch {
      // Network still unavailable
    }

    item.attempts++;
    remaining.push(item);
  }

  saveQueue(remaining);

  if (flushedCount > 0) {
    logger.debug(
      `Flushed ${flushedCount} offline telemetry items successfully`,
    );
  }

  return flushedCount;
}

/**
 * Returns current count of offline queued items.
 */
export function getOfflineBufferSize(): number {
  return loadQueue().length;
}

/**
 * Clears offline queue (useful for testing).
 */
export function clearOfflineBuffer(): void {
  memoryStore = {};
  try {
    const storage = getStorage();
    storage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore
  }
}

/**
 * Initializes automatic online event listener and flushes buffer on network reconnection.
 */
export function initOfflineSync(): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const onOnline = () => {
    flushOfflineBuffer().catch(() => {});
  };

  window.addEventListener("online", onOnline);

  // Attempt an initial flush in case previous items are pending
  setTimeout(() => {
    flushOfflineBuffer().catch(() => {});
  }, 3000);

  return () => {
    window.removeEventListener("online", onOnline);
  };
}
