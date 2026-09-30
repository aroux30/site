"use client";

import React, { Component, type ReactNode } from "react";

interface CanvasErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface CanvasErrorBoundaryState {
  hasError: boolean;
}

/**
 * Error boundary specifically for WebGL / Three.js Canvas components.
 * Catches WebGL context loss, shader compilation failures, etc.
 */
export class CanvasErrorBoundary extends Component<
  CanvasErrorBoundaryProps,
  CanvasErrorBoundaryState
> {
  constructor(props: CanvasErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): CanvasErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (process.env.NODE_ENV === "development") {
      console.warn("CanvasErrorBoundary caught an error:", error, info);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback ?? (
          <div className="flex h-full min-h-[200px] w-full items-center justify-center rounded-2xl border border-border bg-muted/30 p-8 text-center">
            <div>
              <p className="text-sm font-semibold text-foreground mb-1">
                نمای سه‌بعدی در دسترس نیست
              </p>
              <p className="text-xs text-muted-foreground">
                مرورگر شما از WebGL پشتیبانی نمی‌کند یا خطایی رخ داده است.
              </p>
            </div>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
