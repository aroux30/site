"use client";

import { useCallback, useEffect, useState } from "react";
import { CalendarClock, Loader2, Play, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import {
  scheduledJobsApi,
  type ScheduledJob,
} from "@/lib/api/automation";
import { toPersianDigits } from "@/lib/utils";

/**
 * Scheduled jobs — WordPress's Tools → Cron Events.
 *
 * The storefront's scheduled work (expiring carts, purging the media trash,
 * running health checks, sending abandoned-cart reminders) lived only in
 * celery_app's beat_schedule and a read-only summary inside Site Health, so an
 * operator who had just fixed the thing that made a job fail had no button to
 * run it, and could not see any job's schedule without reading source.
 *
 * "Run now" dispatches through the same queue the schedule uses, so it
 * exercises the real path — not a direct in-process call that would pass while
 * the worker was broken.
 */
export default function ScheduledJobsPage() {
  const { toast } = useToast();
  const [jobs, setJobs] = useState<ScheduledJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await scheduledJobsApi.list();
      setJobs(res.jobs);
    } catch {
      toast({ title: "خواندن رویدادهای زمان‌بندی‌شده ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async (job: ScheduledJob) => {
    setRunning(job.name);
    try {
      const res = await scheduledJobsApi.run(job.name);
      if (res.dispatched) {
        toast({
          title: `«${job.name}» در صف اجرا قرار گرفت`,
          description: "اجرا در کارگر سلری انجام می‌شود، نه همین‌جا.",
        });
      } else {
        // A refusal is information: the job cannot run, and the reason is why.
        toast({
          title: `«${job.name}» اجرا نشد`,
          description: res.reason ?? "دلیل نامشخص",
          variant: "destructive",
        });
      }
    } catch {
      toast({ title: "اجرای رویداد ناموفق بود", variant: "destructive" });
    } finally {
      setRunning(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
            <CalendarClock className="h-6 w-6 text-primary" />
            رویدادهای زمان‌بندی‌شده
          </h1>
          <p className="text-sm text-muted-foreground">
            کارهای زمان‌بندی‌شدهٔ سیستم (Celery beat). هر ردیف را می‌توانید دستی
            اجرا کنید — مثلاً بعد از رفع مشکلی که باعث شکستش شده بود.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`ms-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          بازخوانی
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="p-3 text-start font-medium">نام رویداد</th>
                  <th className="p-3 text-start font-medium">زمان‌بندی</th>
                  <th className="p-3 text-start font-medium">وضعیت</th>
                  <th className="p-3 text-start font-medium">تسک</th>
                  <th className="p-3" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.name} className="border-b last:border-0">
                    <td className="p-3 font-medium" dir="ltr">
                      {job.name}
                    </td>
                    <td className="p-3 text-xs text-muted-foreground" dir="ltr">
                      {job.schedule}
                    </td>
                    <td className="p-3">
                      {job.registered ? (
                        <Badge variant="outline" className="text-[10px]">
                          ثبت‌شده
                        </Badge>
                      ) : (
                        // A beat entry whose task is gone fires into
                        // "unregistered task" and dies silently — mark it
                        // rather than list a job that cannot run.
                        <Badge variant="destructive" className="text-[10px]">
                          تسک ثبت نشده
                        </Badge>
                      )}
                    </td>
                    <td
                      className="p-3 font-mono text-[10px] text-muted-foreground"
                      dir="ltr"
                    >
                      {job.task ?? "—"}
                    </td>
                    <td className="p-3 text-end">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={running === job.name || !job.registered}
                        onClick={() => void run(job)}
                      >
                        {running === job.name ? (
                          <Loader2 className="ms-1 h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Play className="ms-1 h-3.5 w-3.5" />
                        )}
                        اجرای دستی
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <p className="text-xs text-muted-foreground">
        {toPersianDigits(String(jobs.length))} رویداد زمان‌بندی‌شده ثبت شده است.
      </p>
    </div>
  );
}