"use client";

import React, { Component, type ReactNode, type ErrorInfo } from "react";
import Link from "next/link";
import { logger } from "./logger";
import { getActiveTraceId } from "./tracer";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";

// ponytail: in-memory error deduplication window -> skipped: indexedDB deduplication, add when persistent session replay needed.

export interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?:
    ReactNode | ((props: { error: Error; reset: () => void }) => ReactNode);
  onError?: (error: Error, errorInfo: ErrorInfo) => void;
  name?: string;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * Standard React Error Boundary component for catching and reporting rendering errors.
 */
export class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    const traceId = getActiveTraceId();

    logger.error(
      `React render error in ${this.props.name || "ErrorBoundary"}`,
      error,
      {
        componentStack: errorInfo.componentStack,
        boundaryName: this.props.name,
        traceId,
      },
    );

    if (this.props.onError) {
      try {
        this.props.onError(error, errorInfo);
      } catch {
        // Prevent recursive failures in custom error callbacks
      }
    }
  }

  resetErrorBoundary = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError && this.state.error) {
      if (typeof this.props.fallback === "function") {
        return this.props.fallback({
          error: this.state.error,
          reset: this.resetErrorBoundary,
        });
      }

      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="shadow-xs flex min-h-[280px] w-full flex-col items-center justify-center rounded-xl border border-destructive/20 bg-destructive/5 p-6 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-destructive/10 text-destructive">
            <AlertTriangle className="h-6 w-6" aria-hidden="true" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-foreground">
            خطایی در نمایش این بخش رخ داده است
          </h3>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            متأسفانه مشکلی در پردازش اطلاعات به وجود آمده است. می‌توانید دوباره
            تلاش کنید.
          </p>
          <div className="mt-5 flex items-center gap-3">
            <button
              onClick={this.resetErrorBoundary}
              className="shadow-xs focus:outline-hidden inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:ring-2 focus:ring-primary/20"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              تلاش مجدد
            </button>
            <Link
              href="/"
              className="focus:outline-hidden inline-flex items-center gap-2 rounded-lg border border-input bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent focus:ring-2 focus:ring-ring/20"
            >
              <Home className="h-4 w-4" aria-hidden="true" />
              صفحه اصلی
            </Link>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

/**
 * Initializes global handlers for uncaught exceptions and unhandled promise rejections.
 * Safe for execution in browser environments with automatic deduplication.
 */
export function initGlobalErrorHandlers(): () => void {
  if (typeof window === "undefined") {
    return () => {};
  }

  const recentErrors = new Set<string>();

  const isDuplicate = (key: string): boolean => {
    if (recentErrors.has(key)) return true;
    recentErrors.add(key);
    setTimeout(() => recentErrors.delete(key), 1000);
    return false;
  };

  const errorHandler = (event: ErrorEvent): void => {
    const message = event.message || "Uncaught runtime exception";
    const key = `${message}:${event.filename}:${event.lineno}`;
    if (isDuplicate(key)) return;

    logger.error(
      `Uncaught Error: ${message}`,
      event.error || new Error(message),
      {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        traceId: getActiveTraceId(),
      },
    );
  };

  const rejectionHandler = (event: PromiseRejectionEvent): void => {
    const reason = event.reason;
    const isError = reason instanceof Error;
    const message = isError ? reason.message : String(reason);
    const key = `unhandledrejection:${message}`;
    if (isDuplicate(key)) return;

    logger.error(
      `Unhandled Promise Rejection: ${message}`,
      isError ? reason : new Error(message),
      {
        reasonType: typeof reason,
        traceId: getActiveTraceId(),
      },
    );
  };

  window.addEventListener("error", errorHandler);
  window.addEventListener("unhandledrejection", rejectionHandler);

  return () => {
    window.removeEventListener("error", errorHandler);
    window.removeEventListener("unhandledrejection", rejectionHandler);
  };
}
