"use client";

/**
 * Content AI card (Rank Math Pro parity): meta title/description suggestions.
 *
 * Honest skeleton: without a configured key the card says "not connected"
 * and the generate button explains why. With a key, suggestions are shown
 * for the operator to copy — they are NEVER auto-written to live meta tags
 * (a hallucination shipped to Google is worse than no suggestion).
 */

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2, Save, Sparkles, XCircle } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import {
  configureContentAi,
  fetchContentAiStatus,
  generateContentAiSuggestion,
  type ContentAiStatus,
} from "@/lib/api/seo";

export function ContentAiSettingsCard() {
  const { toast } = useToast();
  const [status, setStatus] = useState<ContentAiStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [testTitle, setTestTitle] = useState("");
  const [testContent, setTestContent] = useState("");
  const [suggestion, setSuggestion] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try {
      const s = await fetchContentAiStatus();
      setStatus(s);
      setModel(s.model);
    } catch {
      toast({ title: "خواندن وضعیت Content AI ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      const s = await configureContentAi({
        ...(apiKey.trim() ? { api_key: apiKey.trim() } : {}),
        ...(baseUrl.trim() ? { base_url: baseUrl.trim() } : {}),
        ...(model.trim() ? { model: model.trim() } : {}),
      });
      setStatus(s);
      setApiKey("");
      toast({ title: "تنظیمات Content AI ذخیره شد" });
    } catch {
      toast({ title: "ذخیره ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const generate = async (kind: "title" | "description") => {
    if (!testTitle.trim()) {
      toast({ title: "عنوان نمونه را وارد کنید", variant: "destructive" });
      return;
    }
    setGenerating(true);
    setSuggestion(null);
    try {
      const result = await generateContentAiSuggestion({
        title: testTitle.trim(),
        content: testContent,
        kind,
      });
      if (result.status === "ok" && result.suggestion) {
        setSuggestion(result.suggestion);
      } else {
        toast({
          title: result.reason ?? "تولید پیشنهاد ناموفق بود",
          variant: "destructive",
        });
      }
    } catch {
      toast({ title: "درخواست ناموفق بود", variant: "destructive" });
    } finally {
      setGenerating(false);
    }
  };

  if (loading) {
    return (
      <Card className="flex items-center justify-center p-6">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          <h2 className="text-base font-bold text-foreground">هوش مصنوعی محتوا</h2>
        </div>
        <span className="flex items-center gap-1 text-xs">
          {status?.connected ? (
            <>
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              متصل
            </>
          ) : (
            <>
              <XCircle className="h-3.5 w-3.5 text-muted-foreground" />
              متصل نشده
            </>
          )}
        </span>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">{status?.note}</p>

      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="ai-key">کلید سرویس (API Key)</Label>
            <Input
              id="ai-key"
              dir="ltr"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={status?.connected ? "•••••• (تنظیم شده — برای تغییر بنویسید)" : "sk-..."}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="ai-model">مدل</Label>
            <Input
              id="ai-model"
              dir="ltr"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="gpt-4o-mini"
            />
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="ai-base">آدرس سرویس (خالی = OpenAI پیش‌فرض)</Label>
          <Input
            id="ai-base"
            dir="ltr"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://api.openai.com/v1"
          />
        </div>

        <div className="flex justify-end">
          <Button size="sm" onClick={saveConfig} disabled={saving}>
            <Save className="h-4 w-4 ms-1" />
            {saving ? "در حال ذخیره..." : "ذخیره تنظیمات"}
          </Button>
        </div>

        {status?.connected && (
          <div className="space-y-3 rounded-lg border border-dashed border-border p-4">
            <div className="text-xs font-medium">آزمایش تولید پیشنهاد</div>
            <Input
              value={testTitle}
              onChange={(e) => setTestTitle(e.target.value)}
              placeholder="عنوان نوشته"
            />
            <textarea
              value={testContent}
              onChange={(e) => setTestContent(e.target.value)}
              rows={3}
              placeholder="متن (اختیاری) — برای پیشنهاد دقیق‌تر"
              className="w-full rounded-md border border-input bg-background p-2 text-xs"
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => void generate("title")}
                disabled={generating}
              >
                پیشنهاد عنوان
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => void generate("description")}
                disabled={generating}
              >
                پیشنهاد توضیحات
              </Button>
            </div>
            {suggestion && (
              <div className="rounded-lg bg-muted/40 p-3">
                <div className="mb-1 text-[11px] text-muted-foreground">
                  پیشنهاد (برای استفاده، کپی کنید — خودکار جایی نوشته نمی‌شود)
                </div>
                <div className="text-sm">{suggestion}</div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="mt-2"
                  onClick={() => {
                    void navigator.clipboard.writeText(suggestion);
                    toast({ title: "کپی شد" });
                  }}
                >
                  کپی
                </Button>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}

export default ContentAiSettingsCard;
