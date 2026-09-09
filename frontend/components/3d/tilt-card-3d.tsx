"use client";

import React, { useRef, useState, useCallback, MouseEvent } from "react";
import { cn } from "@/lib/utils";

interface TiltCard3DProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  maxTilt?: number; // degrees
  perspective?: number; // px
  glareOpacity?: number;
}

export function TiltCard3D({
  children,
  className,
  maxTilt = 12,
  perspective = 1000,
  glareOpacity = 0.25,
  ...props
}: TiltCard3DProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [transform, setTransform] = useState<string>("rotateX(0deg) rotateY(0deg)");
  const [glarePosition, setGlarePosition] = useState<{ x: number; y: number } | null>(null);
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = useCallback(
    (e: MouseEvent<HTMLDivElement>) => {
      if (!cardRef.current) return;
      const rect = cardRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      const centerX = rect.width / 2;
      const centerY = rect.height / 2;

      // Calculate tilt angles
      const rotateX = ((y - centerY) / centerY) * -maxTilt;
      const rotateY = ((x - centerX) / centerX) * maxTilt;

      setTransform(
        `perspective(${perspective}px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) scale3d(1.02, 1.02, 1.02)`
      );

      setGlarePosition({
        x: (x / rect.width) * 100,
        y: (y / rect.height) * 100,
      });
    },
    [maxTilt, perspective]
  );

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    setTransform(`perspective(${perspective}px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`);
    setGlarePosition(null);
  }, [perspective]);

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      style={{
        transform,
        transformStyle: "preserve-3d",
        transition: isHovered ? "none" : "transform 0.5s ease-out",
      }}
      className={cn(
        "relative will-change-transform rounded-2xl border border-border bg-card p-5 shadow-sm transition-shadow duration-300 hover:shadow-xl",
        className
      )}
      {...props}
    >
      {/* Dynamic Specular Glare Overlay */}
      {isHovered && glarePosition && (
        <div
          className="pointer-events-none absolute inset-0 z-20 rounded-2xl transition-opacity duration-200"
          style={{
            background: `radial-gradient(circle 350px at ${glarePosition.x}% ${glarePosition.y}%, rgba(255, 255, 255, ${glareOpacity}), transparent 70%)`,
          }}
        />
      )}

      {/* Children elements with depth */}
      <div style={{ transform: "translateZ(20px)" }} className="relative z-10">
        {children}
      </div>
    </div>
  );
}
