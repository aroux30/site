"use client";

/**
 * Password-protected post body (WordPress parity).
 *
 * The server never ships a locked body to the browser: `content` arrives
 * empty with `content_locked: true`. This island renders the unlock form,
 * asks the API for the body with the submitted password, and — on a match —
 * swaps in the article. The password itself is never persisted anywhere;
 * every page load starts locked again, exactly like WordPress.
 */

import { useState } from "react";
import { KeyRound, Loader2, Lock } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchBlogPostBySlug } from "@/lib/api/blog";
import cleanHtml from "@/lib/sanitize-html";

interface PasswordProtectedContentProps {
  slug: string;
  /** Body from the server; empty when `locked` is true. */
  content: string;
  /** True when the server withheld the body (no/wrong password yet). */
  locked: boolean;
}

export function PasswordProtectedContent({
  slug,
  content,
  locked: initiallyLocked,
}: PasswordProtectedContentProps) {
  const [locked, setLocked] = useState(initiallyLocked);
  const [body, setBody] = useState(content);
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!locked) {
    // The same two rendering modes the article page always had: HTML bodies
    // through the sanitizer, plain text split into paragraphs.
    if (/<[a-z][\s\S]*>/i.test(body)) {
      return <div dangerouslySetInnerHTML={{ __html: cleanHtml(body) }} />;
    }
    return (
      <>
        {body.split("\n\n").map((para, i) => {
          if (para.startsWith("### ")) {
            return (
              <h3
                key={i}
                className="text-xl font-bold mt-6 mb-3 text-emerald-600 dark:text-emerald-400"
              >
                {para.replace("### ", "")}
              </h3>
            );
          }
          if (para.startsWith("## ")) {
            return (
              <h2 key={i} className="text-2xl font-bold mt-8 mb-4">
                {para.replace("## ", "")}
              </h2>
            );
          }
          return (
            <p key={i} className="text-base md:text-lg leading-loose">
              {para}
            </p>
          );
        })}
      </>
    );
  }

  const unlock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) return;
    setSubmitting(true);
    setError(null);
    try {
      const post = await fetchBlogPostBySlug(slug, { password });
      if (post && post.content_locked === false) {
        setBody(post.content ?? "");
        setLocked(false);
        setPassword("");
      } else {
        setError("رمز واردشده درست نیست. دوباره تلاش کنید.");
      }
    } catch {
      // A real outage must not read as "wrong password".
      setError("بررسی رمز با خطا مواجه شد؛ لطفاً دوباره تلاش کنید.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card className="rounded-2xl border-border bg-card shadow-sm">
      <CardContent className="p-8">
        <div className="mx-auto max-w-sm space-y-4 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-600">
            <Lock className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h3 className="font-bold text-base">این مطلب با رمز محافظت می‌شود</h3>
            <p className="text-xs text-muted-foreground">
              برای مطالعهٔ متن کامل، رمز را وارد کنید.
            </p>
          </div>
          <form onSubmit={unlock} className="space-y-3 text-start">
            <div className="grid gap-2">
              <Label htmlFor="post-password">رمز مطلب</Label>
              <Input
                id="post-password"
                type="password"
                dir="ltr"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="off"
              />
            </div>
            {error && (
              <p role="alert" className="text-xs text-destructive">
                {error}
              </p>
            )}
            <Button type="submit" className="w-full gap-2" disabled={submitting || !password}>
              {submitting ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <KeyRound className="h-4 w-4" />
              )}
              {submitting ? "در حال بررسی..." : "نمایش مطلب"}
            </Button>
          </form>
        </div>
      </CardContent>
    </Card>
  );
}
