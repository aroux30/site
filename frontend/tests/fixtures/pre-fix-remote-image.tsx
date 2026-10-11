/**
 * The RemoteImage component as it was **before** the host guard, kept only so
 * the negative test can prove the guard is load-bearing.
 *
 * Do not fix this file and do not use it in the app: an unconfigured host must
 * reach `next/image` here, because that throw is exactly what
 * `negative-remote-image-host-guard.test.tsx` asserts.
 */
import Image from "next/image";
import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function PreFixRemoteImage({
  src,
  alt,
  className,
  sizes,
  priority,
  fill = true,
}: {
  src?: string | null;
  alt: string;
  className?: string;
  sizes?: string;
  priority?: boolean;
  fill?: boolean;
}) {
  // The old condition: an empty src degrades, anything else goes to next/image.
  const url = typeof src === "string" && src.trim() ? src.trim() : null;

  if (!url) {
    return (
      <div className={cn("flex", fill && "absolute inset-0")} role="img" aria-label={alt}>
        <ImageIcon className="h-6 w-6" />
        <span>{alt}</span>
      </div>
    );
  }

  return <Image src={url} alt={alt} fill={fill} sizes={sizes} priority={priority} className={className} />;
}
