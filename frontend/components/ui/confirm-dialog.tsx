"use client";

import * as React from "react";
import { AlertTriangle } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * An in-app replacement for `window.confirm`.
 *
 * `window.confirm` is **not** a safe way to gate a destructive action here.
 * Inside a sandboxed iframe without `allow-modals` — which is how an embedded
 * preview, a webview, or any framed admin surface runs — the call returns
 * `false` immediately and shows **no dialog at all**. A handler written as
 *
 *     if (!confirm("...")) return;
 *
 * therefore returns before issuing any request, with no error and no toast.
 * The button looks dead: on 2026-10-07 the blog list's delete button did
 * exactly that in the embedded preview, while the same code worked in a
 * top-level tab. Every one of the ~40 `confirm()` call sites had the same
 * exposure.
 *
 * This component draws its own dialog, so it needs no browser modal permission
 * and behaves identically framed or unframed. It also gives the confirmation a
 * real place to explain the consequence, which a one-line `confirm` cannot.
 *
 * Usage — the imperative form, so an existing `confirm()` call site can be
 * converted without restructuring its handler:
 *
 *     const { confirm } = useConfirm();
 *     const ok = await confirm({
 *       title: "انتقال به سطل زباله",
 *       description: "این عمل برگشت‌پذیر است.",
 *       confirmLabel: "انتقال",
 *       destructive: true,
 *     });
 *     if (!ok) return;
 */
interface ConfirmOptions {
  title: string;
  description?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Style the confirm button as destructive (red). */
  destructive?: boolean;
}

type ConfirmFn = (options: ConfirmOptions) => Promise<boolean>;

const ConfirmContext = React.createContext<ConfirmFn | null>(null);

export function ConfirmDialogProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = React.useState(false);
  const [options, setOptions] = React.useState<ConfirmOptions | null>(null);
  // The promise's resolver is kept in a ref so the buttons can settle it
  // without the state update racing the render that reads `options`.
  const resolverRef = React.useRef<((value: boolean) => void) | null>(null);

  const confirm = React.useCallback<ConfirmFn>((opts) => {
    setOptions(opts);
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  const settle = React.useCallback((value: boolean) => {
    setOpen(false);
    // Resolve after the close so the caller's continuation does not run inside
    // the dialog's event handler, where a thrown error would be swallowed by
    // Radix's focus management.
    const resolve = resolverRef.current;
    resolverRef.current = null;
    resolve?.(value);
  }, []);

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <Dialog
        open={open}
        onOpenChange={(next) => {
          // Closing by Escape or the backdrop counts as "no": a destructive
          // action must never run because the dialog was dismissed.
          if (!next) settle(false);
        }}
      >
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {options?.destructive && (
                <AlertTriangle className="h-5 w-5 shrink-0 text-destructive" />
              )}
              {options?.title}
            </DialogTitle>
            {options?.description && (
              <DialogDescription asChild>
                <div>{options.description}</div>
              </DialogDescription>
            )}
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => settle(false)}>
              {options?.cancelLabel ?? "انصراف"}
            </Button>
            <Button
              autoFocus
              variant={options?.destructive ? "destructive" : "default"}
              className={cn(!options?.destructive && "bg-emerald-600 hover:bg-emerald-700")}
              onClick={() => settle(true)}
            >
              {options?.confirmLabel ?? "تأیید"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ConfirmContext.Provider>
  );
}

/**
 * The imperative confirmation. Throws when used outside the provider rather
 * than silently falling back to `window.confirm` — a fallback would put the
 * framed-environment bug straight back, and it would only show up in the one
 * environment this component exists to fix.
 */
export function useConfirm(): ConfirmFn {
  const ctx = React.useContext(ConfirmContext);
  if (!ctx) {
    throw new Error(
      "useConfirm must be used inside <ConfirmDialogProvider>. " +
        "Add it to the app providers so the dialog renders.",
    );
  }
  return ctx;
}
