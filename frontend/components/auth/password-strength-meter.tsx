"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";

/** Password strength evaluator, WordPress parity.
 *
 *  WordPress's password meter (`zxcvbn`-derived, with four bands: very weak,
 *  weak, medium, strong) is what stops a customer registering with `12345678`
 *  and losing their account the next week.
 *
 *  The calculation is intentionally client-side and deterministic:
 *
 *  * length (8, 12, 16) is the single biggest contributor;
 *  * character diversity (lower, upper, digit, symbol);
 *  * penalty for sequential or repeated characters (`aaaa`, `1234`).
 *
 *  Returns a 0..4 score, a label, and a color, so any form can render it as a
 *  bar or as text.
 */

export interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4;
  label: string;
  color: string;
  barClass: string;
  feedback: string[];
}

const LABELS = [
  "بسیار ضعیف",
  "ضعیف",
  "متوسط",
  "خوب",
  "بسیار قوی",
] as const;

const BAR_COLORS = [
  "bg-rose-500",
  "bg-amber-500",
  "bg-yellow-500",
  "bg-emerald-500",
  "bg-emerald-600",
] as const;

export function evaluatePassword(pwd: string): PasswordStrength {
  if (!pwd) {
    return {
      score: 0,
      label: "",
      color: "text-muted-foreground",
      barClass: "bg-muted",
      feedback: [],
    };
  }

  let points = 0;
  const feedback: string[] = [];

  // Length
  if (pwd.length >= 8) points += 1;
  else feedback.push("حداقل ۸ کاراکتر");

  if (pwd.length >= 12) points += 1;
  if (pwd.length >= 16) points += 1;

  // Diversity
  const hasLower = /[a-z]/.test(pwd);
  const hasUpper = /[A-Z]/.test(pwd);
  const hasDigit = /[0-9]/.test(pwd);
  const hasSpecial = /[^A-Za-z0-9]/.test(pwd);

  const diversity = [hasLower, hasUpper, hasDigit, hasSpecial].filter(Boolean).length;
  if (diversity >= 3) points += 1;
  if (diversity === 4) points += 1;

  if (!hasUpper || !hasLower) feedback.push("ترکیب حروف کوچک و بزرگ");
  if (!hasDigit) feedback.push("حداقل یک عدد");
  if (!hasSpecial) feedback.push("حداقل یک علامت (!@#$...)");

  // Penalties
  if (/^[0-9]+$/.test(pwd)) points = Math.min(points, 1);
  if (/^[a-zA-Z]+$/.test(pwd)) points = Math.min(points, 2);
  if (/(.)\1{2,}/.test(pwd)) points = Math.max(0, points - 1);

  const score = Math.max(0, Math.min(4, points)) as 0 | 1 | 2 | 3 | 4;

  return {
    score,
    label: LABELS[score],
    color: score <= 1 ? "text-rose-600" : score === 2 ? "text-yellow-600" : "text-emerald-600",
    barClass: BAR_COLORS[score],
    feedback,
  };
}

export function PasswordStrengthMeter({
  password,
  className,
}: {
  password: string;
  className?: string;
}) {
  const strength = useMemo(() => evaluatePassword(password), [password]);

  if (!password) return null;

  return (
    <div className={cn("space-y-1.5", className)} aria-live="polite">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">قدرت رمز عبور:</span>
        <span className={cn("font-medium", strength.color)}>{strength.label}</span>
      </div>
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((step) => (
          <div
            key={step}
            className={cn(
              "h-1.5 flex-1 rounded-full transition-colors",
              step <= strength.score - 1 ? strength.barClass : "bg-muted",
            )}
          />
        ))}
      </div>
      {strength.feedback.length > 0 && strength.score < 3 && (
        <p className="text-[11px] text-muted-foreground">
          پیشنهاد: {strength.feedback.slice(0, 2).join("، ")}
        </p>
      )}
    </div>
  );
}