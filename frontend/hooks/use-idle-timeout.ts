"use client";

import { useEffect, useRef, useCallback } from "react";
import { useAuth } from "@/hooks/use-auth";
import { useRouter } from "next/navigation";

/**
 * Hook to automatically log out users after a period of inactivity (idle timeout).
 * Follows OWASP ASVS Session Management security controls.
 *
 * @param timeoutMs Inactivity duration before automatic logout (default: 30 minutes)
 */
export function useIdleTimeout(timeoutMs: number = 30 * 60 * 1000) {
  const router = useRouter();
  const { isAuthenticated, logout } = useAuth();
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  const handleLogout = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      // redirectTo: null keeps navigation here so the login page can explain
      // the idle timeout via query params.
      await logout({ redirectTo: null });
      router.replace("/login?reason=idle_timeout&redirect=/admin/dashboard");
    } catch {
      router.replace("/login?reason=idle_timeout&redirect=/admin/dashboard");
    }
  }, [isAuthenticated, logout, router]);

  const resetTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (isAuthenticated) {
      timerRef.current = setTimeout(() => {
        handleLogout();
      }, timeoutMs);
    }
  }, [isAuthenticated, timeoutMs, handleLogout]);

  useEffect(() => {
    if (!isAuthenticated) return;

    const activityEvents = [
      "mousedown",
      "mousemove",
      "keydown",
      "scroll",
      "touchstart",
      "click",
    ];

    // Initialize timer
    resetTimer();

    // Reset timer on any interaction
    const handleUserActivity = () => {
      resetTimer();
    };

    activityEvents.forEach((event) => {
      window.addEventListener(event, handleUserActivity, { passive: true });
    });

    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }
      activityEvents.forEach((event) => {
        window.removeEventListener(event, handleUserActivity);
      });
    };
  }, [isAuthenticated, resetTimer]);
}

export default useIdleTimeout;
