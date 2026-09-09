"use client";

import { useCallback, useEffect } from "react";
import { useAuthStore } from "@/stores/auth-store";
import apiClient, { tokenStore } from "@/lib/api/client";
import type { AuthResponse } from "@/lib/api/types";
import type {
  User,
  LoginRequest,
  RegisterRequest,
  OtpRequest,
  OtpVerifyRequest,
  UpdateProfileRequest,
  ChangePasswordRequest,
} from "@/types/user";

export function useAuth() {
  const store = useAuthStore();

  // Check auth status on mount
  useEffect(() => {
    const token = tokenStore.getAccessToken();
    if (token && !store.user) {
      fetchCurrentUser();
    } else {
      store.setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchCurrentUser = useCallback(async () => {
    try {
      store.setLoading(true);
      const { data } = await apiClient.get<{ data: User }>("/auth/me");
      store.setUser(data.data);
    } catch {
      store.logout();
    }
  }, [store]);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      const { data } = await apiClient.post<AuthResponse>(
        "/auth/login",
        credentials,
      );
      store.login(
        data.user as unknown as User,
        data.access_token,
        data.refresh_token,
      );
      return data;
    },
    [store],
  );

  const register = useCallback(
    async (userData: RegisterRequest) => {
      const { data } = await apiClient.post<AuthResponse>(
        "/auth/register",
        userData,
      );
      store.login(
        data.user as unknown as User,
        data.access_token,
        data.refresh_token,
      );
      return data;
    },
    [store],
  );

  const requestOtp = useCallback(async (request: OtpRequest) => {
    const { data } = await apiClient.post("/auth/otp/send", request);
    return data;
  }, []);

  const verifyOtp = useCallback(
    async (request: OtpVerifyRequest) => {
      const { data } = await apiClient.post<AuthResponse>(
        "/auth/otp/verify",
        request,
      );
      store.login(
        data.user as unknown as User,
        data.access_token,
        data.refresh_token,
      );
      return data;
    },
    [store],
  );

  const logout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Silently fail - we clear local state regardless
    } finally {
      store.logout();
    }
  }, [store]);

  const updateProfile = useCallback(
    async (updates: UpdateProfileRequest) => {
      const { data } = await apiClient.put<{ data: User }>(
        "/auth/profile",
        updates,
      );
      store.updateProfile(data.data);
      return data.data;
    },
    [store],
  );

  const changePassword = useCallback(
    async (request: ChangePasswordRequest) => {
      const { data } = await apiClient.put("/auth/password", request);
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
