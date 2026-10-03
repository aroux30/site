"use client";

import { useState } from "react";
import RichBodyEditor from "@/components/admin/RichBodyEditor";

/**
 * The probe's client half. It holds `value` in real state and feeds it back,
 * because that is how every post form uses the editor.
 *
 * An earlier version passed a no-op `onChange`, which made one-shot toolbar
 * commands (alignment, table, rule) look broken: the parent never took the
 * new value, so React re-applied the old markup and undid the command. The
 * test has to exercise the real contract, not a convenient fake one.
 */
export function EditorProbeClient() {
  const [value, setValue] = useState("<p>متن اولیه</p>");
  return (
    <div className="container mx-auto max-w-4xl px-4 py-10" dir="rtl">
      <h1 className="mb-4 text-2xl font-black">پروب ادیتور</h1>
      <RichBodyEditor value={value} onChange={setValue} />
      <pre
        data-testid="probe-value"
        className="mt-6 whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 text-xs"
      >
        {value}
      </pre>
    </div>
  );
}
