"use client";

import React, { useState } from "react";
import { User as UserIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface UserAvatarProps {
  src?: string | null;
  name?: string | null;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export function UserAvatar({
  src,
  name,
  className = "",
  size = "md",
}: UserAvatarProps) {
  const [imageError, setImageError] = useState(false);

  // Validate that src is a non-empty, valid URL string
  const isValidSrc = Boolean(
    src &&
      typeof src === "string" &&
      src.trim() !== "" &&
      src !== "null" &&
      src !== "undefined" &&
      (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("/"))
  );

  const initial = name?.trim() ? name.trim()[0] : null;

  const sizeClasses = {
    sm: "h-7 w-7 text-xs",
    md: "h-8 w-8 text-xs",
    lg: "h-10 w-10 text-sm",
  };

  return (
    <div
      className={cn(
        "relative flex shrink-0 items-center justify-center rounded-full overflow-hidden border border-border bg-primary/10 text-primary font-bold select-none",
        sizeClasses[size],
        className
      )}
    >
      {isValidSrc && !imageError ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src!}
          alt={name || "آواتار کاربر"}
          className="h-full w-full object-cover"
          onError={() => setImageError(true)}
        />
      ) : initial ? (
        <span>{initial}</span>
      ) : (
        <UserIcon className="h-4 w-4 text-primary" />
      )}
    </div>
  );
}

export default UserAvatar;
