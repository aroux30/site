import axios, {
  type AxiosError,
  type AxiosInstance,
  type InternalAxiosRequestConfig,
} from "axios";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface TokenStore {
  getAccessToken: () => string | null;
  getRefreshToken: () => string | null;
  setTokens: (_access: string, _refresh: string) => void;
  clearTokens: () => void;
}

const tokenStore: TokenStore = {
  getAccessToken: () => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  },
  getRefreshToken: () => {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("refresh_token");
  },
  setTokens: (access: string, refresh: string) => {
    if (typeof window === "undefined") return;
    localStorage.setItem("access_token", access);
    localStorage.setItem("refresh_token", refresh);
  },
  clearTokens: () => {
    if (typeof window === "undefined") return;
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  },
};

const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// Request interceptor: attach auth token
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = tokenStore.getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
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

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
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

    // If 401 and not already retrying, attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            if (originalRequest.headers) {
              originalRequest.headers.Authorization = `Bearer ${token}`;
            }
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = tokenStore.getRefreshToken();
      if (!refreshToken) {
        tokenStore.clearTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return Promise.reject(error);
      }

      try {
        const { data } = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token: newRefresh } = data;
        tokenStore.setTokens(access_token, newRefresh);

        processQueue(null, access_token);

        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        tokenStore.clearTokens();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
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
    if (typeof data?.message === "string") return data.message;

    switch (error.response.status) {
      case 400:
        return "درخواست نامعتبر است.";
      case 401:
        return "لطفاً وارد حساب کاربری خود شوید.";
      case 403:
        return "شما مجوز دسترسی به این بخش را ندارید.";
      case 404:
        return "مورد درخواستی یافت نشد.";
      case 422:
        return "اطلاعات وارد شده صحیح نیست.";
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

export { apiClient, tokenStore };
export default apiClient;
