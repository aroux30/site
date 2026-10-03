"use client";

/**
 * Drag-and-drop upload target.
 *
 * P0 "مدیا: آپلود کشیدن‌ورهاکردن (Drag & Drop)" — the library only accepted
 * files through a file dialog, so uploading a folder's worth of product photos
 * meant one dialog per batch and a lot of clicking.
 *
 * Three details this gets right, each of which the obvious version misses:
 *
 *  - The whole page is a drop target, not just a small box. Dropping anywhere
 *    on the library is what people actually do.
 *  - The drag counter, not a boolean. `dragenter` and `dragleave` fire for every
 *    child element crossed, so a boolean flickers off the moment the pointer
 *    passes over a thumbnail — the highlight visibly strobes.
 *  - The `dataTransfer` files are read before any state update. Safari and
 *    Chrome both clear the payload once the drop is handled asynchronously.
 *
 * Reused elsewhere: any admin screen that uploads files should render this
 * rather than open with its own drop handling.
 */

import { useCallback, useRef, useState, type DragEvent } from "react";
import { UploadCloud } from "lucide-react";

export interface MediaDropzoneProps {
  /** Called with the dropped files. The owner enforces size and count limits. */
  onFiles: (files: File[]) => void;
  disabled?: boolean;
  /** What the accept filter is, for the hint line. */
  hint?: string;
  className?: string;
  children?: React.ReactNode;
}

export function MediaDropzone({
  onFiles,
  disabled = false,
  hint,
  className = "",
  children,
}: MediaDropzoneProps) {
  // A ref, not state: dragenter/dragleave fire far more often than a render
  // should, and the counter only matters at paint time.
  const depth = useRef(0);
  const [over, setOver] = useState(false);

  const reset = useCallback(() => {
    depth.current = 0;
    setOver(false);
  }, []);

  const onDragEnter = useCallback(
    (e: DragEvent<HTMLElement>) => {
      if (disabled) return;
      // Only react to a real file drag. Without this, selecting text anywhere on
      // the page lights up the whole library, because a text drag also fires
      // dragenter with no files in the payload.
      if (!Array.from(e.dataTransfer.types).includes("Files")) return;
      e.preventDefault();
      depth.current += 1;
      setOver(true);
    },
    [disabled],
  );

  const onDragOver = useCallback(
    (e: DragEvent<HTMLElement>) => {
      if (disabled) return;
      // Without preventDefault the browser navigates to the dropped file and
      // the whole session is lost.
      e.preventDefault();
      e.dataTransfer.dropEffect = "copy";
    },
    [disabled],
  );

  const onDragLeave = useCallback(
    (e: DragEvent<HTMLElement>) => {
      if (disabled) return;
      e.preventDefault();
      depth.current = Math.max(0, depth.current - 1);
      if (depth.current === 0) setOver(false);
    },
    [disabled],
  );

  const onDrop = useCallback(
    (e: DragEvent<HTMLElement>) => {
      if (disabled) return;
      e.preventDefault();
      reset();
      // Read the files synchronously, before the reset above and any state
      // update: the payload is cleared once the drop handler yields.
      const files = Array.from(e.dataTransfer.files ?? []);
      if (files.length > 0) onFiles(files);
    },
    [disabled, onFiles, reset],
  );

  return (
    <div
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={
        "relative transition-colors " +
        (over ? "ring-2 ring-primary ring-offset-2 ring-offset-background " : "") +
        className
      }
      data-drop-active={over ? "true" : "false"}
    >
      {over ? (
        <div
          className="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-xl bg-primary/10 backdrop-blur-[1px]"
          role="status"
        >
          <UploadCloud className="h-8 w-8 text-primary" />
          <p className="text-sm font-semibold text-primary">
            فایل‌ها را اینجا رها کنید
          </p>
          {hint ? <p className="text-xs text-primary/80">{hint}</p> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}

export default MediaDropzone;
