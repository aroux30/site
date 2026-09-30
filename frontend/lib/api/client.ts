import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/stores/auth-store";
import {
  createTraceParent,
  generateSpanId,
  getActiveTraceId,
} from "@/lib/observability/tracer";
import { logger } from "@/lib/observability/logger";
import { metrics, SLOW_API_THRESHOLD_MS } from "@/lib/observability/metrics";
import { apiInternalUrl } from "@/lib/api/server-base";

// ponytail: axios single-instance interceptors -> skipped: multi-tenant dynamic axios registry, add when microfrontends needed.

declare module "axios" {
  export interface InternalAxiosRequestConfig {
    _observability?: {
      requestId: string;
      traceId: string;
      spanId: string;
      startTime: number;
    };
    _retry?: boolean;
  }
}

// Browser must always call same-origin /api/v1 (the reverse proxy routes /api
// to the backend container). SSR calls the backend container directly, since a
// relative base URL is invalid outside the browser.
const API_BASE_URL: string =
  typeof window === "undefined" ? apiInternalUrl() : "/api/v1";

interface SessionStore {
  getSessionId: () => string | null;
  getOrCreateSessionId: () => string;
  clearSessionId: () => void;
}

const sessionStore: SessionStore = {
  getSessionId: () => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("cart_session_id");
  },
  getOrCreateSessionId: () => {
    if (typeof window === "undefined") return "";
    let sid = localStorage.getItem("cart_session_id");
    if (!sid) {
      sid =
        typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
          ? crypto.randomUUID()
          : "guest-" +
            Math.random().toString(36).substring(2, 11) +
            "-" +
            Date.now().toString(36);
      localStorage.setItem("cart_session_id", sid);
    }
    return sid;
  },
  clearSessionId: () => {
    if (typeof window === "undefined") return;
    localStorage.removeItem("cart_session_id");
  },
};

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
  withCredentials: true,
});

// Request interceptor: inject X-Request-ID, W3C traceparent, session headers,
// and Idempotency-Key for financial mutation endpoints.
const FINANCIAL_ENDPOINTS = [
  "/payments",
  "/checkout",
  "/orders",
  "/wallet",
  "/cart/checkout",
  "/cashback",
  "/discounts",
  "/admin/inventory/transfers",
];

/**
 * A "guest session probe" is an unauthenticated GET against a public,
 * read-only endpoint that the backend answers with 401 — the browser is
 * checking whether a session exists. These are expected control flow, not
 * failures, so they log at debug instead of error.
 */
function isGuestSessionProbe(
  method: string,
  url: string,
  status: number,
): boolean {
  if (method !== "GET" || status !== 401) return false;
  return /\/(catalog|products|categories|search|content)\b/.test(url);
}

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Generate unique request ID for trace correlation
    const requestId =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : "req-" +
          Math.random().toString(36).substring(2, 11) +
          "-" +
          Date.now().toString(36);

    const traceId = getActiveTraceId();
    const spanId = generateSpanId();
    const traceparent = createTraceParent(traceId, spanId, true);

    if (config.headers) {
      if (!config.headers["X-Request-ID"]) {
        config.headers["X-Request-ID"] = requestId;
      }
      if (!config.headers["traceparent"]) {
        config.headers["traceparent"] = traceparent;
      }
      if (!config.headers["X-Correlation-ID"]) {
        config.headers["X-Correlation-ID"] = traceId;
      }

      // Idempotency-Key: auto-inject on POST/PUT/PATCH to financial endpoints
      // so duplicate submissions (double-click, network retry) are deduplicated
      // server-side. The key is per-request, not per-session.
      const method = (config.method || "GET").toUpperCase();
      const isMutating = ["POST", "PUT", "PATCH"].includes(method);
      const isFinancial = FINANCIAL_ENDPOINTS.some((ep) =>
        config.url?.includes(ep),
      );
      if (isMutating && isFinancial && !config.headers["Idempotency-Key"]) {
        config.headers["Idempotency-Key"] =
          typeof crypto !== "undefined" &&
          typeof crypto.randomUUID === "function"
            ? crypto.randomUUID()
            : `idem-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
      }
    }

    // Attach timing and trace metadata for observability tracking
    config._observability = {
      requestId,
      traceId,
      spanId,
      startTime:
        typeof performance !== "undefined" ? performance.now() : Date.now(),
    };

    if (typeof window !== "undefined") {
      const sessionId = sessionStore.getOrCreateSessionId();
      if (sessionId && config.headers && !config.headers["X-Session-ID"]) {
        config.headers["X-Session-ID"] = sessionId;
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor: handle observability timing, token refresh, and error mapping
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (_value: unknown) => void;
  reject: (_reason: unknown) => void;
}> = [];

const processQueue = (error: unknown) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(undefined);
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => {
    const obs = response.config?._observability;
    if (obs) {
      const now =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const durationMs = Math.round((now - obs.startTime) * 100) / 100;
      const url = response.config.url || "";
      const method = (response.config.method || "GET").toUpperCase();

      metrics.recordApiLatency(url, method, durationMs, response.status, {
        requestId: obs.requestId,
        traceId: obs.traceId,
      });

      if (durationMs >= SLOW_API_THRESHOLD_MS) {
        logger.warn(`Slow API response: [${method}] ${url} (${durationMs}ms)`, {
          durationMs,
          status: response.status,
          requestId: obs.requestId,
          traceId: obs.traceId,
        });
      } else {
        logger.debug(`API response: [${method}] ${url} (${durationMs}ms)`, {
          durationMs,
          status: response.status,
          requestId: obs.requestId,
          traceId: obs.traceId,
        });
      }
    }
    return response;
  },
  async (error: AxiosError) => {
    const originalRequest = error.config as
      InternalAxiosRequestConfig | undefined;
    const obs = originalRequest?._observability;

    if (obs && originalRequest) {
      const now =
        typeof performance !== "undefined" ? performance.now() : Date.now();
      const durationMs = Math.round((now - obs.startTime) * 100) / 100;
      const url = originalRequest.url || "";
      const method = (originalRequest.method || "GET").toUpperCase();
      const status = error.response?.status || 0;

      metrics.recordApiLatency(url, method, durationMs, status, {
        requestId: obs.requestId,
        traceId: obs.traceId,
      });

      if (isGuestSessionProbe(method, url, status)) {
        logger.debug(`API session probe unauthenticated: [GET] ${url}`, {
          durationMs,
          status,
          requestId: obs.requestId,
          traceId: obs.traceId,
        });
      } else {
        logger.error(
          `API request failed: [${method}] ${url} (${status}) [${durationMs}ms]`,
          error,
          {
            durationMs,
            status,
            requestId: obs.requestId,
            traceId: obs.traceId,
          },
        );
      }
    }

    // Do not attempt token refresh for auth entry/challenge endpoints
    const isAuthEndpoint =
      originalRequest?.url?.includes("/auth/login") ||
      originalRequest?.url?.includes("/auth/register") ||
      originalRequest?.url?.includes("/auth/refresh") ||
      originalRequest?.url?.includes("/auth/otp");

    // Only the session check (/auth/me) drives the refresh+logout cascade.
    // Endpoint 401s (e.g. cart/admin APIs racing right after login) must
    // reject to their callers — a global logout here used to kill fresh
    // admin sessions mid-navigation (admin panel bounce bug).
    const isSessionCheck = originalRequest?.url?.includes("/auth/me");

    // If 401 and not already retrying, attempt token refresh
    if (
      originalRequest &&
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !isAuthEndpoint &&
      isSessionCheck
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => {
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Call refresh endpoint without a body; the refresh_token cookie
        // is sent automatically via withCredentials.
        await axios.post(
          `${API_BASE_URL}/auth/refresh`,
          {},
          { withCredentials: true },
        );

        processQueue(null);

        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);

        if (typeof window !== "undefined") {
          // Clean up invalid session state. The auth cookies are HttpOnly
          // (server-managed); JS cannot and must not clear them — the expired
          // refresh token is revoked server-side on this failed refresh.
          sessionStore.clearSessionId();

          // Clear zustand auth store state so client doesn't hold stale session
          try {
            useAuthStore.getState().logout();
          } catch {
            // In case store is inaccessible
          }

          // Land the user on the login page from a session-protected area
          // once refresh has failed. /admin and /account are handled
          // reactively by their auth guards; this is the fallback for a page
          // that has no guard of its own (e.g. /checkout).
          const currentPathname = window.location.pathname;
          const isProtectedRoute =
            currentPathname.startsWith("/account") ||
            currentPathname.startsWith("/checkout");

          const isAuthPage =
            currentPathname.startsWith("/login") ||
            currentPathname.startsWith("/register");

          if (isProtectedRoute && !isAuthPage) {
            const currentPath = currentPathname + window.location.search;
            const redirectParam = encodeURIComponent(currentPath);
            window.location.href = `/login?redirect=${redirectParam}`;
          }
        }

        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Map error responses to a consistent format.
    //
    // `response` is preserved so callers can keep reading the backend's own
    // payload shape (`err.response.data.error.message`, `.detail`, …). It used
    // to be dropped, which silently broke ~45 call sites that read exactly
    // those paths: every one of them fell through to its generic Persian
    // fallback, so an operator saw "ثبت سند ناموفق بود" instead of the
    // server's actual reason (e.g. "سند باطل‌شده قابل ثبت نیست").
    //
    // `message` carries the already-extracted human message, so the simpler
    // `err.message` style keeps working too. Both spellings now resolve to the
    // server's text.
    const apiError = {
      status: error.response?.status || 500,
      message: getErrorMessage(error),
      errors: (error.response?.data as Record<string, unknown>)?.errors || null,
      response: error.response,
      isAxiosError: true,
    };

    return Promise.reject(apiError);
  },
);

function getErrorMessage(error: AxiosError): string {
  if (error.response) {
    const data = error.response.data as Record<string, unknown>;
    const errorObj = data?.error as Record<string, unknown> | undefined;

    // Several of the server's generic auth messages are English and reach the
    // user verbatim. They arrive in two different envelopes: `error.message`
    // (AppException) and `detail` (plain HTTPException), so both are checked.
    // Match the exact server strings — "Token has expired" is what jwt.py
    // raises, not "Token expired".
    const GENERIC_AUTH_MESSAGES = new Set([
      "Not authenticated",
      "Authentication required",
      "Token has expired",
      "Token has been revoked",
      "Invalid token",
      "Account is disabled",
    ]);
    // The 401 from a failed login is not a session problem — telling the user
    // to "log in" while they are looking at the login form is useless. The
    // backend distinguishes it only by this message, so it is matched
    // explicitly and rendered Persian here (the status-code switch below
    // would do this, but the envelope branch returns first).
    const INVALID_CREDENTIALS = new Set([
      "Invalid phone or password",
      "Invalid credentials",
    ]);

    const translateGeneric = (text: unknown): string | null => {
      if (typeof text !== "string") return null;
      if (INVALID_CREDENTIALS.has(text)) return "شماره موبایل یا رمز عبور اشتباه است.";
      if (GENERIC_AUTH_MESSAGES.has(text)) return "لطفاً ابتدا وارد حساب کاربری خود شوید.";
      return null;
    };

    const fromErrorObj = translateGeneric(errorObj?.message);
    if (fromErrorObj) return fromErrorObj;
    const fromMessage = translateGeneric(data?.message);
    if (fromMessage) return fromMessage;

    if (typeof errorObj?.message === "string") return errorObj.message;
    if (typeof data?.message === "string") return data.message;
    if (typeof data?.detail === "string") {
      return translateGeneric(data.detail) ?? data.detail;
    }

    // In case detail is an array of validation errors (Pydantic / FastAPI default)
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const first = data.detail[0] as { msg?: string };
      if (typeof first?.msg === "string") return first.msg;
    }

    const reqUrl = error.config?.url || "";
    switch (error.response.status) {
      case 400:
        return "درخواست نامعتبر است.";
      case 401:
        return reqUrl.includes("/auth/login")
          ? "شماره موبایل یا رمز عبور اشتباه است."
          : "لطفاً ابتدا وارد حساب کاربری خود شوید.";
      case 403:
        return "شما مجوز دسترسی به این بخش را ندارید.";
      case 404:
        return "مورد درخواستی یافت نشد.";
      case 409:
        return "این شماره موبایل قبلاً در سامانه ثبت شده است.";
      case 422:
        return "اطلاعات وارد شده نامعتبر است.";
      case 429:
        return "تعداد درخواست‌ها بیش از حد مجاز است. لطفاً کمی صبر کنید.";
      case 500:
        return "خطای سرور. لطفاً بعداً تلاش کنید.";
      default:
        return "خطایی رخ داده است.";
    }
  }

  if (error.code === "ERR_NETWORK") {
    return "خطا در برقراری ارتباط با سرور. اتصال اینترنت خود را بررسی کنید.";
  }

  return "خطای ناشناخته‌ای رخ داده است.";
}

export { apiClient, sessionStore };
export default apiClient;
