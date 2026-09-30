"use client";

import confetti from "canvas-confetti";

interface ConfettiOptions {
  particleCount?: number;
  spread?: number;
  startVelocity?: number;
  decay?: number;
  origin?: { x: number; y: number };
  colors?: string[];
}

export function triggerConfetti(options?: ConfettiOptions) {
  const defaultColors = [
    "#10b981", // primary emerald
    "#14b8a6", // secondary teal
    "#f59e0b", // accent amber/gold
    "#3b82f6", // blue
    "#ec4899", // pink
  ];

  confetti({
    particleCount: options?.particleCount ?? 80,
    spread: options?.spread ?? 70,
    origin: options?.origin ?? { y: 0.6 },
    colors: options?.colors ?? defaultColors,
    startVelocity: options?.startVelocity ?? 45,
    decay: options?.decay ?? 0.9,
    disableForReducedMotion: true,
  });
}

export function triggerCelebrationCannons() {
  const count = 200;
  const defaults = {
    origin: { y: 0.7 },
    disableForReducedMotion: true,
  };

  function fire(particleRatio: number, opts: confetti.Options) {
    confetti({
      ...defaults,
      ...opts,
      particleCount: Math.floor(count * particleRatio),
    });
  }

  fire(0.25, {
    spread: 26,
    startVelocity: 55,
  });
  fire(0.2, {
    spread: 60,
  });
  fire(0.35, {
    spread: 100,
    decay: 0.91,
    scalar: 0.8,
  });
  fire(0.1, {
    spread: 120,
    startVelocity: 25,
    decay: 0.92,
    scalar: 1.2,
  });
  fire(0.1, {
    spread: 120,
    startVelocity: 45,
  });
}
