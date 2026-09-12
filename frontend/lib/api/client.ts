import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/stores/auth-store";

// Browser must always call same-origin /api/v1 (the reverse proxy routes /api
// to the backend container). SSR calls the backend container directly, since a
// relative base URL is invalid outside the browser.
const API_BASE_URL: string =
  typeof window === "undefined"
    ? process.env.INTERNAL_API_URL || "http://backend:8000/api/v1"
    : "/api/v1";

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
          : "guest-" + Math.random().toString(36).substring(2, 11) + "-" + Date.now().toString(36);
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

// Request interceptor: attach session ID header and Authorization header if cookie exists
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== "undefined") {
      const sessionId = sessionStore.getOrCreateSessionId();
      if (sessionId && config.headers && !config.headers["X-Session-ID"]) {
        config.headers["X-Session-ID"] = sessionId;
      }
      // Dual-channel auth: also attach Authorization header if access_token cookie is accessible
      const cookieMatch = document.cookie.match(/(?:^|;\s*)access_token=([^;]+)/);
      if (cookieMatch && cookieMatch[1] && config.headers && !config.headers["Authorization"]) {
        config.headers["Authorization"] = `Bearer ${decodeURIComponent(cookieMatch[1])}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

// Response interceptor: handle token refresh and error mapping
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
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

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
      error.response?.status === 401 &&
      !originalRequest?._retry &&
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
          // Clean up invalid session state and expired client cookie
          sessionStore.clearSessionId();
          const isSecure = window.location.protocol === "https:";
          const secureAttr = isSecure ? "; Secure" : "";
          document.cookie = `access_token=; path=/; max-age=0; SameSite=Lax${secureAttr}`;

          // Clear zustand auth store state so client doesn't hold stale session
          try {
            useAuthStore.getState().logout();
          } catch {
            // In case store is inaccessible
          }

          // Only hard-redirect for account/checkout pages (they have no
          // reactive auth guard). /admin is handled reactively by
          // AdminAuthGuard, and /auth/me failures by the login page effect.
          const currentPathname = window.location.pathname;
          const isProtectedRoute =
            currentPathname.startsWith("/account") ||
            currentPathname.startsWith("/checkout");

          const isAuthPage =
            currentPathname.startsWith("/login") ||
            currentPathname.startsWith("/register");

          if (isProtectedRoute && !isAuthPage && !isSessionCheck) {
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

    // Map error responses to a consistent format
    const apiError = {
      status: error.response?.status || 500,
      message: getErrorMessage(error),
      errors: (error.response?.data as Record<string, unknown>)?.errors || null,
    };

    return Promise.reject(apiError);
  },
);

function getErrorMessage(error: AxiosError): string {
  if (error.response) {
    const data = error.response.data as Record<string, unknown>;
    const errorObj = data?.error as Record<string, unknown> | undefined;

    if (typeof errorObj?.message === "string") return errorObj.message;
    if (typeof data?.message === "string") return data.message;
    if (typeof data?.detail === "string") return data.detail;

    // In case detail is an array of validation errors (Pydantic / FastAPI default)
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const first = data.detail[0] as { msg?: string };
      if (typeof first?.msg === "string") return first.msg;
    }

    switch (error.response.status) {
      case 400:
        return "درخواست نامعتبر است.";
      case 401:
        return "شماره موبایل یا رمز عبور اشتباه است.";
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
