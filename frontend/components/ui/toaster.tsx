"use client";

import { useToast } from "@/components/ui/use-toast";
import {
  Toast,
  ToastClose,
  ToastDescription,
  ToastTitle,
} from "@/components/ui/toast";

export function Toaster() {
  const { toasts, dismiss } = useToast();

  return (
    // pointer-events-none on the empty container: it is `fixed top-0 z-[100]
    // w-full`, so without this an empty toaster swallowed clicks on the top
    // ~32px of every mobile page — the admin menu button (2026-10-06) and
    // anything else in a sticky header. Each Toast re-enables its own
    // pointer-events (the toast item already carries pointer-events-auto).
    <div className="pointer-events-none fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse gap-2 p-4 sm:bottom-0 sm:start-0 sm:top-auto sm:flex-col md:max-w-[420px]">
      {toasts.map(({ id, title, description, action, variant, open }) => (
        <Toast key={id} variant={variant} open={open}>
          <div className="grid gap-1">
            {title && <ToastTitle>{title}</ToastTitle>}
            {description && (
              <ToastDescription>{description}</ToastDescription>
            )}
          </div>
          {action}
          <ToastClose onClick={() => dismiss(id)} />
        </Toast>
      ))}
    </div>
  );
}
