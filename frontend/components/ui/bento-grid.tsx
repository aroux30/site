"use client";

import React, { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { ChevronLeft } from "lucide-react";
import Link from "next/link";

interface BentoGridProps {
  children: ReactNode;
  className?: string;
}

export function BentoGrid({ children, className }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid w-full auto-rows-[18rem] grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3",
        className
      )}
    >
      {children}
    </div>
  );
}

interface BentoCardProps {
  name: string;
  className?: string;
  background?: ReactNode;
  Icon?: React.ComponentType<{ className?: string }>;
  description: string;
  href: string;
  cta?: string;
  badge?: string;
}

export function BentoCard({
  name,
  className,
  background,
  Icon,
  description,
  href,
  cta = "مشاهده بیشتر",
  badge,
}: BentoCardProps) {
  return (
    <div
      key={name}
      className={cn(
        "group relative col-span-1 flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-card p-6 shadow-sm transition-all duration-300 hover:shadow-lg hover:-translate-y-1",
        className
      )}
    >
      {/* Background visual asset/gradient */}
      <div className="absolute inset-0 z-0 transition-transform duration-500 group-hover:scale-105">
        {background}
      </div>

      {/* Top row: Badge and Icon */}
      <div className="relative z-10 flex items-start justify-between">
        {Icon ? (
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary transition-colors duration-300 group-hover:bg-primary group-hover:text-primary-foreground">
            <Icon className="h-6 w-6" />
          </div>
        ) : (
          <div />
        )}
        {badge && (
          <span className="rounded-full bg-primary/15 px-3 py-1 text-xs font-semibold text-primary">
            {badge}
          </span>
        )}
      </div>

      {/* Bottom row: Content and CTA */}
      <div className="relative z-10 mt-6 flex flex-col gap-2">
        <h3 className="text-xl font-bold tracking-tight text-foreground transition-colors group-hover:text-primary">
          {name}
        </h3>
        <p className="max-w-lg text-sm text-muted-foreground line-clamp-2">
          {description}
        </p>

        <Link
          href={href}
          className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-primary transition-all duration-200 group-hover:gap-2.5"
        >
          <span>{cta}</span>
          <ChevronLeft className="h-4 w-4 transition-transform duration-200 group-hover:-translate-x-1" />
        </Link>
      </div>

      {/* Subtle hover gradient overlay */}
      <div className="pointer-events-none absolute inset-0 z-0 bg-gradient-to-t from-background/90 via-background/40 to-transparent opacity-80 transition-opacity duration-300 group-hover:opacity-95" />
    </div>
  );
}
