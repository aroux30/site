"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Coins,
  Percent,
  Sparkles,
  Truck,
  Trophy,
  RotateCw,
  Gift,
  Zap,
  Check,
  Copy,
  Clock,
  HelpCircle,
  Volume2,
  VolumeX,
} from "lucide-react";
import { triggerCelebrationCannons, triggerConfetti } from "@/components/ui/confetti";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import { earnLoyaltyPoints } from "@/lib/api/gamification";
import { useAuthStore } from "@/stores/auth-store";

export interface WheelSlice {
  id: number;
  label: string;
  subLabel: string;
  type: "points" | "discount" | "shipping" | "respin" | "voucher";
  value: number; // points amount or discount percent or voucher value
  couponCode?: string;
  color: string;
  accentColor: string;
  textColor: string;
  icon: React.ReactNode;
}

const WHEEL_SLICES: WheelSlice[] = [
  {
    id: 0,
    label: "۵۰ امتیاز",
    subLabel: "افزایش موجودی باشگاه",
    type: "points",
    value: 50,
    color: "#4f46e5", // Indigo
    accentColor: "#6366f1",
    textColor: "#ffffff",
    icon: <Coins className="h-5 w-5" />,
  },
  {
    id: 1,
    label: "۱۰٪ تخفیف",
    subLabel: "سقف ۵۰,۰۰۰ تومان",
    type: "discount",
    value: 10,
    couponCode: "WHEEL10OFF",
    color: "#db2777", // Rose / Pink
    accentColor: "#ec4899",
    textColor: "#ffffff",
    icon: <Percent className="h-5 w-5" />,
  },
  {
    id: 2,
    label: "۲۰ امتیاز",
    subLabel: "افزایش موجودی باشگاه",
    type: "points",
    value: 20,
    color: "#0891b2", // Cyan
    accentColor: "#06b6d4",
    textColor: "#ffffff",
    icon: <Sparkles className="h-5 w-5" />,
  },
  {
    id: 3,
    label: "ارسال رایگان",
    subLabel: "برای سفارش دلخواه",
    type: "shipping",
    value: 0,
    couponCode: "FREESHIP-WHEEL",
    color: "#059669", // Emerald
    accentColor: "#10b981",
    textColor: "#ffffff",
    icon: <Truck className="h-5 w-5" />,
  },
  {
    id: 4,
    label: "۱۰۰ امتیاز",
    subLabel: "جایزه ویژه طلایی!",
    type: "points",
    value: 100,
    color: "#d97706", // Amber / Gold
    accentColor: "#f59e0b",
    textColor: "#ffffff",
    icon: <Trophy className="h-5 w-5" />,
  },
  {
    id: 5,
    label: "شانس مجدد",
    subLabel: "یک چرخش رایگان هدیه",
    type: "respin",
    value: 1,
    color: "#7c3aed", // Violet
    accentColor: "#8b5cf6",
    textColor: "#ffffff",
    icon: <RotateCw className="h-5 w-5" />,
  },
  {
    id: 6,
    label: "۵۰ هزار تومان",
    subLabel: "بن تخفیف نقدی",
    type: "voucher",
    value: 50000,
    couponCode: "TOMAN50K",
    color: "#e11d48", // Crimson
    accentColor: "#f43f5e",
    textColor: "#ffffff",
    icon: <Gift className="h-5 w-5" />,
  },
  {
    id: 7,
    label: "۱۵ امتیاز",
    subLabel: "افزایش موجودی باشگاه",
    type: "points",
    value: 15,
    color: "#0d9488", // Teal
    accentColor: "#14b8a6",
    textColor: "#ffffff",
    icon: <Zap className="h-5 w-5" />,
  },
];

const SPIN_COST = 20;

// Web Audio API click sound generator
function playWheelTick(audioCtx: AudioContext | null) {
  if (!audioCtx || audioCtx.state !== "running") return;
  try {
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "triangle";
    osc.frequency.setValueAtTime(450, audioCtx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(120, audioCtx.currentTime + 0.04);
    gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.04);
    osc.connect(gain);
    gain.connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + 0.045);
  } catch {
    // Ignore audio errors
  }
}

// Web Audio API win fanfare
function playWinFanfare(audioCtx: AudioContext | null) {
  if (!audioCtx || audioCtx.state !== "running") return;
  try {
    const notes = [261.63, 329.63, 392.0, 523.25]; // C, E, G, C
    notes.forEach((freq, idx) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      const startTime = audioCtx.currentTime + idx * 0.1;
      gain.gain.setValueAtTime(0.12, startTime);
      gain.gain.exponentialRampToValueAtTime(0.001, startTime + 0.35);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start(startTime);
      osc.stop(startTime + 0.36);
    });
  } catch {
    // Ignore audio errors
  }
}

interface WheelOfFortuneProps {
  userPoints: number;
  onPointsUpdate: (_newPoints: number, _change: number, _reason: string) => void;
  onRewardWon?: (_slice: WheelSlice) => void;
}

export function WheelOfFortune({
  userPoints,
  onPointsUpdate,
  onRewardWon,
}: WheelOfFortuneProps) {
  const { user, updateProfile } = useAuthStore();
  const [rotation, setRotation] = useState(0);
  const [isSpinning, setIsSpinning] = useState(false);
  const [freeSpinAvailable, setFreeSpinAvailable] = useState(true);
  const [extraFreeSpins, setExtraFreeSpins] = useState(0);
  const [winningSlice, setWinningSlice] = useState<WheelSlice | null>(null);
  const [winDialogOpen, setWinDialogOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [soundEnabled, setSoundEnabled] = useState(true);

  const audioCtxRef = useRef<AudioContext | null>(null);
  const pointerRef = useRef<HTMLDivElement>(null);

  // Initialize audio context lazily on first user interaction
  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current && typeof window !== "undefined") {
      const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (AudioCtx) {
        audioCtxRef.current = new AudioCtx();
      }
    }
    if (audioCtxRef.current && audioCtxRef.current.state === "suspended") {
      audioCtxRef.current.resume();
    }
    return audioCtxRef.current;
  }, []);

  // Check free spin status for today from localStorage
  useEffect(() => {
    if (typeof window === "undefined") return;
    const today = new Date().toISOString().split("T")[0];
    const lastFreeSpinDate = localStorage.getItem("wheel_last_free_spin_date");
    if (lastFreeSpinDate === today) {
      setFreeSpinAvailable(false);
    } else {
      setFreeSpinAvailable(true);
    }

    const savedBonus = localStorage.getItem("wheel_bonus_spins");
    if (savedBonus) {
      setExtraFreeSpins(parseInt(savedBonus, 10) || 0);
    }
  }, []);

  // Spin wheel execution
  const handleSpin = () => {
    if (isSpinning) return;

    // Check cost: free spin > bonus spins > 20 points
    const isFree = freeSpinAvailable || extraFreeSpins > 0;
    if (!isFree && userPoints < SPIN_COST) {
      return;
    }

    if (soundEnabled) {
      getAudioContext();
    }

    setIsSpinning(true);
    setWinningSlice(null);

    // Deduct points if not free
    if (!isFree) {
      onPointsUpdate(userPoints - SPIN_COST, -SPIN_COST, "هزینه چرخش گردونه شانس");
    } else if (!freeSpinAvailable && extraFreeSpins > 0) {
      const newBonus = extraFreeSpins - 1;
      setExtraFreeSpins(newBonus);
      localStorage.setItem("wheel_bonus_spins", String(newBonus));
    } else {
      // Used today's daily free spin
      const today = new Date().toISOString().split("T")[0] || "";
      localStorage.setItem("wheel_last_free_spin_date", today);
      setFreeSpinAvailable(false);
    }

    // Weighted selection for fun, engaging gameplay
    // Slices: 0: 50pts, 1: 10% off, 2: 20pts, 3: free shipping, 4: 100pts, 5: respin, 6: 50k toman, 7: 15pts
    const weights = [12, 16, 22, 14, 6, 10, 8, 12];
    const totalWeight = weights.reduce((acc, w) => acc + w, 0);
    let rand = Math.random() * totalWeight;
    let targetIndex = 0;
    for (let i = 0; i < weights.length; i++) {
      const w = weights[i] ?? 0;
      if (rand < w) {
        targetIndex = i;
        break;
      }
      rand -= w;
    }

    const sliceCount = WHEEL_SLICES.length;
    const sliceAngle = 360 / sliceCount; // 45 deg

    // Slice i center is at `targetIndex * 45 + 22.5` degrees relative to top (12 o'clock)
    const sliceCenterAngle = targetIndex * sliceAngle + sliceAngle / 2;

    // Full rotations (5 to 7 turns)
    const fullTurns = 5 + Math.floor(Math.random() * 3);
    const fullTurnsDeg = fullTurns * 360;

    // Add safe jitter so it doesn't land dead-center on every spin (-12° to +12°)
    const jitter = (Math.random() - 0.5) * (sliceAngle * 0.5);

    // Current angle modulo 360
    const currentModulo = rotation % 360;

    // To align sliceCenterAngle with 12 o'clock (0 deg), the wheel must end at: (360 - sliceCenterAngle)
    const targetModulo = (360 - sliceCenterAngle + 360) % 360;
    const additionalDeg = (targetModulo - currentModulo + 360) % 360;

    const finalRotation = rotation + fullTurnsDeg + additionalDeg + jitter;

    setRotation(finalRotation);

    // Ticker sound timer
    if (soundEnabled) {
      const audioCtx = getAudioContext();
      let ticksFired = 0;
      const totalTicks = fullTurns * sliceCount + 8;
      const durationMs = 5200;

      const tickInterval = setInterval(() => {
        if (!isSpinning && ticksFired > totalTicks) {
          clearInterval(tickInterval);
          return;
        }
        playWheelTick(audioCtx);
        ticksFired++;
        if (ticksFired >= totalTicks) {
          clearInterval(tickInterval);
        }
      }, durationMs / (totalTicks * 1.6));
    }

    // Completion after animation (5.2 seconds)
    setTimeout(() => {
      setIsSpinning(false);
      const chosen = WHEEL_SLICES[targetIndex] || WHEEL_SLICES[0];
      if (!chosen) return;
      setWinningSlice(chosen);
      setWinDialogOpen(true);

      if (soundEnabled) {
        playWinFanfare(getAudioContext());
      }

      // Confetti burst
      triggerCelebrationCannons();
      setTimeout(() => {
        triggerConfetti({ particleCount: 70, spread: 80 });
      }, 350);

      // Handle win rewards
      if (chosen.type === "points") {
        const added = chosen.value;
        const newBalance = userPoints + added;
        onPointsUpdate(newBalance, added, `برنده ${added} امتیاز در گردونه شانس`);

        // Update auth store user if authenticated
        if (user) {
          updateProfile({
            loyalty_points: (user.loyalty_points || 0) + added,
            loyaltyPoints: (user.loyaltyPoints || 0) + added,
          });
        }

        // Backend loyalty sync
        earnLoyaltyPoints(added, `برنده گردونه شانس (${chosen.label})`);
      } else if (chosen.type === "respin") {
        const newBonus = extraFreeSpins + 1;
        setExtraFreeSpins(newBonus);
        localStorage.setItem("wheel_bonus_spins", String(newBonus));
      }

      if (onRewardWon) {
        onRewardWon(chosen);
      }
    }, 5300);
  };

  const copyCouponCode = (code?: string) => {
    if (!code) return;
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const canSpin =
    !isSpinning && (freeSpinAvailable || extraFreeSpins > 0 || userPoints >= SPIN_COST);

  return (
    <div className="relative flex flex-col items-center justify-center overflow-hidden rounded-3xl border border-border/80 bg-gradient-to-b from-card via-card/90 to-background p-4 sm:p-8 shadow-xl">
      {/* Header with sound toggle & status badges */}
      <div className="w-full flex items-center justify-between gap-2 mb-6">
        <div className="flex items-center gap-2">
          <Badge
            variant={freeSpinAvailable ? "default" : "secondary"}
            className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold"
          >
            <Clock className="h-3.5 w-3.5" />
            {freeSpinAvailable ? (
              <span>چرخش رایگان روزانه فعال است!</span>
            ) : extraFreeSpins > 0 ? (
              <span>{toPersianDigits(extraFreeSpins)} چرخش هدیه مجدد</span>
            ) : (
              <span>هزینه هر چرخش: {toPersianDigits(SPIN_COST)} امتیاز</span>
            )}
          </Badge>
        </div>

        <button
          type="button"
          onClick={() => setSoundEnabled(!soundEnabled)}
          className="flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-muted/60 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title={soundEnabled ? "قطع صدا" : "وصل صدا"}
          aria-label={soundEnabled ? "قطع صدا" : "وصل صدا"}
        >
          {soundEnabled ? (
            <Volume2 className="h-4 w-4 text-primary" />
          ) : (
            <VolumeX className="h-4 w-4" />
          )}
        </button>
      </div>

      {/* Main Wheel Container with 3D Perspective */}
      <div className="relative flex items-center justify-center my-2 select-none perspective-1000">
        {/* Glowing Background Ring */}
        <div
          className={`absolute h-[340px] w-[340px] sm:h-[440px] sm:w-[440px] rounded-full bg-gradient-to-tr from-primary/20 via-amber-500/15 to-purple-500/20 blur-2xl transition-opacity duration-700 pointer-events-none ${
            isSpinning ? "opacity-100 scale-105 animate-pulse" : "opacity-60"
          }`}
        />

        {/* Outer Golden/Metallic Decorative Rim with 3D Stage Depth */}
        <div
          style={{ transform: "rotateX(6deg)", transformStyle: "preserve-3d" }}
          className="relative p-2.5 sm:p-3 rounded-full bg-gradient-to-br from-amber-400 via-yellow-500 to-amber-700 shadow-2xl border-4 border-amber-300/60 transition-transform duration-300 hover:rotate-x-0"
        >
          {/* LED Sparkling Bulbs around the border */}
          <div className="absolute inset-0 rounded-full pointer-events-none overflow-hidden">
            {Array.from({ length: 24 }).map((_, i) => {
              const angle = (i * 360) / 24;
              const rad = (angle * Math.PI) / 180;
              const radiusPercent = 48.2;
              const left = 50 + radiusPercent * Math.sin(rad);
              const top = 50 - radiusPercent * Math.cos(rad);
              const isEven = i % 2 === 0;

              return (
                <div
                  key={i}
                  className={`absolute h-2 w-2 sm:h-2.5 sm:w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full transition-all duration-300 ${
                    isSpinning
                      ? isEven
                        ? "bg-amber-100 shadow-[0_0_8px_#fef08a] scale-110"
                        : "bg-amber-400 shadow-[0_0_4px_#f59e0b] scale-90"
                      : isEven
                      ? "bg-amber-200 shadow-[0_0_6px_#fde047]"
                      : "bg-amber-500"
                  }`}
                  style={{
                    left: `${left}%`,
                    top: `${top}%`,
                  }}
                />
              );
            })}
          </div>

          {/* SVG Rotating Wheel */}
          <div
            className="relative h-[290px] w-[290px] sm:h-[380px] sm:w-[380px] rounded-full overflow-hidden shadow-inner cursor-pointer"
            onClick={handleSpin}
            style={{
              transform: `rotate(${rotation}deg)`,
              transition: isSpinning
                ? "transform 5.2s cubic-bezier(0.12, 0.9, 0.15, 1)"
                : "none",
            }}
          >
            <svg
              viewBox="0 0 400 400"
              className="h-full w-full select-none"
              style={{ transform: "rotate(0deg)" }}
            >
              <defs>
                {WHEEL_SLICES.map((slice) => (
                  <linearGradient
                    key={`grad-${slice.id}`}
                    id={`slice-grad-${slice.id}`}
                    x1="0%"
                    y1="0%"
                    x2="100%"
                    y2="100%"
                  >
                    <stop offset="0%" stopColor={slice.accentColor} />
                    <stop offset="100%" stopColor={slice.color} />
                  </linearGradient>
                ))}
                {/* Center hub shadow */}
                <radialGradient id="center-hub-grad" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#ffffff" />
                  <stop offset="35%" stopColor="#fef08a" />
                  <stop offset="70%" stopColor="#eab308" />
                  <stop offset="100%" stopColor="#a16207" />
                </radialGradient>
              </defs>

              {/* Slices */}
              {WHEEL_SLICES.map((slice, idx) => {
                const totalSlices = WHEEL_SLICES.length;
                const angle = 360 / totalSlices;
                const startAngle = idx * angle;
                const endAngle = (idx + 1) * angle;
                const midAngle = startAngle + angle / 2;

                // SVG Arc calculation (radius = 200, center = 200, 200)
                const r = 200;
                const cx = 200;
                const cy = 200;

                const startRad = ((startAngle - 90) * Math.PI) / 180;
                const endRad = ((endAngle - 90) * Math.PI) / 180;

                const x1 = cx + r * Math.cos(startRad);
                const y1 = cy + r * Math.sin(startRad);
                const x2 = cx + r * Math.cos(endRad);
                const y2 = cy + r * Math.sin(endRad);

                const pathData = `M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2} Z`;

                return (
                  <g key={slice.id}>
                    {/* Slice wedge */}
                    <path
                      d={pathData}
                      fill={`url(#slice-grad-${slice.id})`}
                      stroke="#ffffff"
                      strokeWidth="2.5"
                    />

                    {/* Content inside slice rotated to midAngle */}
                    <g
                      transform={`rotate(${midAngle} ${cx} ${cy})`}
                      style={{ pointerEvents: "none" }}
                    >
                      {/* Label Text */}
                      <text
                        x={cx}
                        y={55}
                        textAnchor="middle"
                        fill="#ffffff"
                        fontSize="14"
                        fontWeight="bold"
                        className="font-sans drop-shadow-md"
                        style={{
                          textShadow: "0 2px 4px rgba(0,0,0,0.5)",
                          letterSpacing: "0.2px",
                        }}
                      >
                        {slice.label}
                      </text>

                      {/* Small sublabel */}
                      <text
                        x={cx}
                        y={72}
                        textAnchor="middle"
                        fill="rgba(255,255,255,0.85)"
                        fontSize="8.5"
                        fontWeight="500"
                        className="font-sans"
                        style={{ textShadow: "0 1px 2px rgba(0,0,0,0.6)" }}
                      >
                        {slice.subLabel}
                      </text>
                    </g>
                  </g>
                );
              })}

              {/* Decorative slice divider inner rings */}
              <circle
                cx="200"
                cy="200"
                r="194"
                fill="none"
                stroke="rgba(255,255,255,0.25)"
                strokeWidth="1.5"
              />
              <circle
                cx="200"
                cy="200"
                r="120"
                fill="none"
                stroke="rgba(255,255,255,0.15)"
                strokeDasharray="4 4"
                strokeWidth="1"
              />
            </svg>
          </div>

          {/* Golden Center Hub Button */}
          <div
            className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 cursor-pointer transition-transform active:scale-95"
            onClick={handleSpin}
          >
            <div className="relative flex h-16 w-16 sm:h-20 sm:w-20 items-center justify-center rounded-full bg-gradient-to-tr from-amber-600 via-amber-400 to-yellow-200 p-1 shadow-2xl border-2 border-yellow-200">
              <div className="flex h-full w-full items-center justify-center rounded-full bg-gradient-to-b from-amber-900 to-amber-950 text-amber-100 shadow-inner">
                <span className="text-xs sm:text-sm font-black text-amber-200 drop-shadow">
                  {isSpinning ? "..." : "بچرخون!"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Pointer / Needle at Top (12 o'clock) */}
        <div
          ref={pointerRef}
          className={`absolute -top-3 sm:-top-4 left-1/2 -translate-x-1/2 z-20 transition-transform ${
            isSpinning ? "animate-pulse" : ""
          }`}
          style={{ filter: "drop-shadow(0 4px 6px rgba(0,0,0,0.4))" }}
        >
          <svg
            width="38"
            height="46"
            viewBox="0 0 38 46"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Pointer arrow */}
            <path
              d="M19 46L6 14C4 9 8 3 14 3H24C30 3 34 9 32 14L19 46Z"
              fill="url(#pointer-gradient)"
              stroke="#fbbf24"
              strokeWidth="2"
            />
            {/* Center jewel */}
            <circle cx="19" cy="14" r="5" fill="#dc2626" stroke="#fef08a" strokeWidth="1.5" />
            <defs>
              <linearGradient id="pointer-gradient" x1="19" y1="3" x2="19" y2="46" gradientUnits="userSpaceOnUse">
                <stop stopColor="#fef08a" />
                <stop offset="0.5" stopColor="#f59e0b" />
                <stop offset="1" stopColor="#b45309" />
              </linearGradient>
            </defs>
          </svg>
        </div>
      </div>

      {/* Spin Controls & Information */}
      <div className="mt-8 flex flex-col items-center gap-3 w-full max-w-sm">
        <Button
          size="lg"
          onClick={handleSpin}
          disabled={!canSpin}
          className={`relative w-full h-13 rounded-2xl text-base font-bold shadow-lg transition-all ${
            canSpin
              ? "bg-gradient-to-r from-amber-500 via-primary to-emerald-600 text-white hover:brightness-110 active:scale-98 shadow-primary/25"
              : "opacity-60 cursor-not-allowed"
          }`}
        >
          {isSpinning ? (
            <div className="flex items-center gap-2">
              <RotateCw className="h-5 w-5 animate-spin" />
              <span>در حال چرخش گردونه...</span>
            </div>
          ) : freeSpinAvailable ? (
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 animate-bounce text-yellow-200" />
              <span>چرخش رایگان امروز (کلیک کنید)</span>
            </div>
          ) : extraFreeSpins > 0 ? (
            <div className="flex items-center gap-2">
              <RotateCw className="h-5 w-5 text-yellow-200" />
              <span>استفاده از شانس مجدد ({toPersianDigits(extraFreeSpins)})</span>
            </div>
          ) : userPoints >= SPIN_COST ? (
            <div className="flex items-center gap-2">
              <Coins className="h-5 w-5 text-yellow-300" />
              <span>چرخش با {toPersianDigits(SPIN_COST)} امتیاز</span>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <HelpCircle className="h-4 w-4" />
              <span>امتیاز ناکافی ({toPersianDigits(SPIN_COST)} امتیاز لازم است)</span>
            </div>
          )}
        </Button>

        <p className="text-xs text-muted-foreground text-center flex items-center gap-1.5">
          <span>هر روز ۱ شانس چرخش رایگان دارید؛ چرخش‌های بعدی ۲۰ امتیاز است.</span>
        </p>
      </div>

      {/* Win Celebration Dialog */}
      <Dialog open={winDialogOpen} onOpenChange={setWinDialogOpen}>
        <DialogContent className="sm:max-w-md text-center p-6">
          <DialogHeader>
            <div className="mx-auto my-3 flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-tr from-amber-400 to-yellow-200 text-amber-900 shadow-xl animate-in zoom-in-75 duration-300">
              <Trophy className="h-10 w-10 text-amber-800" />
            </div>
            <DialogTitle className="text-2xl font-black text-foreground">
              تبریک! شما برنده شدید!
            </DialogTitle>
            <DialogDescription className="text-sm text-muted-foreground">
              جایزه ویژه شما از گردونه شانس با موفقیت ثبت گردید.
            </DialogDescription>
          </DialogHeader>

          {winningSlice && (
            <div className="my-4 space-y-4">
              {/* Prize Highlight Box */}
              <div
                className="rounded-2xl p-5 border text-white shadow-lg"
                style={{
                  backgroundColor: winningSlice.color,
                  borderColor: winningSlice.accentColor,
                }}
              >
                <div className="flex items-center justify-center gap-2 mb-1">
                  {winningSlice.icon}
                  <span className="text-2xl font-extrabold">{winningSlice.label}</span>
                </div>
                <p className="text-xs opacity-90">{winningSlice.subLabel}</p>
              </div>

              {/* Coupon Code copy box if discount / voucher / shipping */}
              {winningSlice.couponCode && (
                <div className="rounded-xl border border-dashed border-primary/50 bg-primary/5 p-3.5 text-right">
                  <div className="text-xs text-muted-foreground mb-1.5 font-medium">
                    کد تخفیف اختصاصی شما:
                  </div>
                  <div className="flex items-center justify-between gap-2 rounded-lg bg-background p-2 border border-border">
                    <span className="font-mono text-base font-bold tracking-wider text-primary">
                      {winningSlice.couponCode}
                    </span>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyCouponCode(winningSlice.couponCode)}
                      className="gap-1.5 text-xs h-8"
                    >
                      {copied ? (
                        <>
                          <Check className="h-3.5 w-3.5 text-emerald-600" />
                          <span>کپی شد!</span>
                        </>
                      ) : (
                        <>
                          <Copy className="h-3.5 w-3.5" />
                          <span>کپی کد</span>
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* Points Won Feedback */}
              {winningSlice.type === "points" && (
                <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-700 dark:text-emerald-400 font-medium">
                  {toPersianDigits(winningSlice.value)} امتیاز به موجودی باشگاه مشتریان شما افزوده شد.
                </div>
              )}

              {/* Respin Won Feedback */}
              {winningSlice.type === "respin" && (
                <div className="rounded-xl bg-purple-500/10 border border-purple-500/20 p-3 text-xs text-purple-700 dark:text-purple-400 font-medium">
                  ۱ شانس چرخش بدون هزینه به حساب شما اضافه شد! همین حالا می‌توانید دوباره بچرخید.
                </div>
              )}
            </div>
          )}

          <div className="mt-2 flex gap-2">
            <Button
              className="flex-1 rounded-xl bg-primary text-primary-foreground font-semibold"
              onClick={() => setWinDialogOpen(false)}
            >
              عالیه، متشکرم!
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
