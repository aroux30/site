"use client";

import { useCallback, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useCartStore } from "@/stores/cart-store";
import apiClient from "@/lib/api/client";
import type {
  User,
  UserProfileResponse,
  TokenResponse,
  LoginRequest,
  RegisterRequest,
  OtpRequest,
  OtpResponse,
  OtpVerifyRequest,
  UpdateProfileRequest,
  ChangePasswordRequest,
  MessageResponse,
} from "@/types/user";

function mapProfileToUser(data: UserProfileResponse): User {
  const fullName =
    [data.first_name, data.last_name].filter(Boolean).join(" ") || null;
  return {
    ...data,
    name: fullName,
    firstName: data.first_name,
    lastName: data.last_name,
    fullName: fullName || data.phone,
    isActive: data.is_active,
  };
}

export function useAuth() {
  const store = useAuthStore();

  const fetchCurrentUser = useCallback(async (): Promise<User | null> => {
    try {
      store.setLoading(true);
      const { data } = await apiClient.get<UserProfileResponse>("/auth/me");
      const user = mapProfileToUser(data);
      store.setUser(user);
      return user;
    } catch {
      store.logout();
      throw new Error("Failed to fetch current user");
    } finally {
      store.setLoading(false);
    }
  }, [store]);

  // Check auth status on mount by calling /auth/me.
  // If the access_token cookie is present the server will respond with user data;
  // otherwise the request will 401 and we clear state.
  useEffect(() => {
    if (store.isAuthenticated && !store.user) {
      fetchCurrentUser().catch(() => {
        // Silently handle error on mount if session is invalid/expired
      });
    } else if (!store.isAuthenticated) {
      // Even without persisted auth flag, try to fetch in case a valid cookie exists
      fetchCurrentUser().catch(() => {
        store.setLoading(false);
      });
    } else {
      store.setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAuthSuccess = useCallback(
    async (): Promise<{ user: User | null }> => {
      // Cookies are set by the server response automatically.
      // Just fetch /auth/me to populate user state.
      const user = await fetchCurrentUser();

      // Merge guest cart with authenticated user's cart
      useCartStore.getState().mergeCart().catch((err) => {
        console.warn("Auto merge cart failed on login:", err);
      });

      return { user };
    },
    [fetchCurrentUser],
  );

  const login = useCallback(
    async (credentials: LoginRequest) => {
      await apiClient.post<TokenResponse>("/auth/login", {
        phone: credentials.phone,
        password: credentials.password,
      });
      return await handleAuthSuccess();
    },
    [handleAuthSuccess],
  );

  const register = useCallback(
    async (userData: RegisterRequest) => {
      await apiClient.post<TokenResponse>("/auth/register", {
        phone: userData.phone,
        password: userData.password,
        first_name: userData.first_name || userData.firstName || "",
        last_name: userData.last_name || userData.lastName || "",
      });
      return await handleAuthSuccess();
    },
    [handleAuthSuccess],
  );

  const requestOtp = useCallback(
    async (request: OtpRequest): Promise<OtpResponse> => {
      const { data } = await apiClient.post<OtpResponse>(
        "/auth/otp/request",
        {
          phone: request.phone,
        },
      );
      return data;
    },
    [],
  );

  const verifyOtp = useCallback(
    async (request: OtpVerifyRequest) => {
      await apiClient.post<TokenResponse>(
        "/auth/otp/verify",
        {
          phone: request.phone,
          code: request.code,
        },
      );
      return await handleAuthSuccess();
    },
    [handleAuthSuccess],
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await apiClient.post<MessageResponse>("/auth/logout");
    } catch {
      // Silently fail - we clear local state regardless
    } finally {
      store.logout();
    }
  }, [store]);

  const updateProfile = useCallback(
    async (updates: UpdateProfileRequest): Promise<User> => {
      const payload = {
        first_name: updates.first_name ?? updates.firstName,
        last_name: updates.last_name ?? updates.lastName,
        email: updates.email,
        national_code: updates.national_code ?? updates.nationalId,
        birth_date: updates.birth_date ?? updates.birthDate,
        avatar_url: updates.avatar_url,
        gender: updates.gender,
      };

      const { data } = await apiClient.patch<UserProfileResponse>(
        "/auth/me",
        payload,
      );
      const updatedUser = mapProfileToUser(data);
      store.setUser(updatedUser);
      return updatedUser;
    },
    [store],
  );

  const changePassword = useCallback(
    async (request: ChangePasswordRequest): Promise<MessageResponse> => {
      const payload = {
        old_password: request.old_password || request.currentPassword,
        new_password: request.new_password,
      };
      const { data } = await apiClient.post<MessageResponse>(
        "/auth/change-password",
        payload,
      );
      return data;
    },
    [],
  );

  return {
    user: store.user,
    isAuthenticated: store.isAuthenticated,
    isLoading: store.isLoading,
    login,
    register,
    requestOtp,
    verifyOtp,
    logout,
    updateProfile,
    changePassword,
    fetchCurrentUser,
  };
}
