"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Shield, RefreshCw, CreditCard, AlertTriangle, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";

interface UserTrustProfile {
  user_id: string;
  is_trusted: boolean;
  shahkar_verified: boolean;
  risk_score: number;
  delayed_delivery_enabled: boolean;
  daily_spend_limit: number;
}

interface FailedAttempt {
  id: string;
  identifier: string;
  attempt_type: string;
  ip_address: string | null;
  created_at: string;
}

export default function AdminAntiFraudPage() {
  const { toast } = useToast();
  const [trustProfiles, setTrustProfiles] = useState<UserTrustProfile[]>([]);
  const [failedAttempts, setFailedAttempts] = useState<FailedAttempt[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch trust profiles and failed attempts (from analytics endpoint if available)
      const [trustRes, attemptsRes] = await Promise.allSettled([
        apiClient.get("/users/kyc/trust-profile"),
        apiClient.get("/admin/audit?resource=failed_attempt&limit=50"),
      ]);

      if (trustRes.status === "fulfilled") {
        setTrustProfiles(Array.isArray(trustRes.value.data) ? trustRes.value.data : [trustRes.value.data]);
      }
      if (attemptsRes.status === "fulfilled") {
        setFailedAttempts(Array.isArray(attemptsRes.value.data) ? attemptsRes.value.data : []);
      }
    } catch {
      toast({ title: "خطا", description: "بارگذاری اطلاعات ضدتقلب با خطا مواجه شد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            سامانه ضدتقلب و احراز هویت
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            پروفایل اعتماد کاربران، استعلام شاهکار و لاگ تلاش‌های ناموفق
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 mr-2" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-6">
          {/* Trust Profiles */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <Users className="h-4 w-4 text-primary" />
              پروفایل اعتماد کاربران
            </h3>
            {trustProfiles.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                هنوز هیچ کاربری احراز هویت نشده است
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="text-right p-3 font-medium">کاربر</th>
                      <th className="text-right p-3 font-medium">شاهکار</th>
                      <th className="text-right p-3 font-medium">امتیاز ریسک</th>
                      <th className="text-right p-3 font-medium">سقف روزانه</th>
                      <th className="text-right p-3 font-medium">تحویل</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trustProfiles.map((p) => (
                      <tr key={p.user_id} className="border-b hover:bg-muted/30">
                        <td className="p-3 font-mono text-xs" dir="ltr">
                          {p.user_id.slice(0, 8)}...
                        </td>
                        <td className="p-3">
                          <Badge className={p.shahkar_verified ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}>
                            {p.shahkar_verified ? "تایید‌شده" : "تایید نشده"}
                          </Badge>
                        </td>
                        <td className="p-3">
                          <Badge className={p.risk_score < 30 ? "bg-emerald-500/10 text-emerald-500" : p.risk_score < 60 ? "bg-amber-500/10 text-amber-500" : "bg-rose-500/10 text-rose-500"}>
                            {p.risk_score} / 100
                          </Badge>
                        </td>
                        <td className="p-3 text-xs">{p.daily_spend_limit.toLocaleString("fa-IR")} ریال</td>
                        <td className="p-3">
                          <Badge className={p.is_trusted ? "bg-emerald-500/10 text-emerald-500" : "bg-amber-500/10 text-amber-500"}>
                            {p.is_trusted ? "آنی" : "با تاخیر"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Failed Attempts */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              لاگ تلاش‌های ناموفق (Brute-Force)
            </h3>
            {failedAttempts.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                هیچ تلاش ناموفقی ثبت نشده است
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="text-right p-3 font-medium">شناسه</th>
                      <th className="text-right p-3 font-medium">نوع</th>
                      <th className="text-right p-3 font-medium">IP</th>
                      <th className="text-right p-3 font-medium">زمان</th>
                    </tr>
                  </thead>
                  <tbody>
                    {failedAttempts.map((a) => (
                      <tr key={a.id} className="border-b hover:bg-muted/30">
                        <td className="p-3 font-mono text-xs" dir="ltr">{a.identifier}</td>
                        <td className="p-3">
                          <Badge variant="outline">{a.attempt_type}</Badge>
                        </td>
                        <td className="p-3 font-mono text-xs" dir="ltr">{a.ip_address || "-"}</td>
                        <td className="p-3 text-xs text-muted-foreground" dir="ltr">
                          {new Date(a.created_at).toLocaleString("fa-IR")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
