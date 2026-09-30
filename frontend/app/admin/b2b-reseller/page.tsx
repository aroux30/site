"use client";

import { useState } from "react";
import { Briefcase, RefreshCw, KeyRound, Plus, Copy, Eye } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { ErrorState } from "@/components/shared/page-state";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const RESELLER_KEYS_QUERY_KEY = "admin-b2b-reseller-keys" as const;

interface ResellerApiKey {
  id: string;
  user_id: string;
  name: string;
  key_prefix: string;
  ip_whitelist: string[] | null;
  credit_balance: number;
  is_active: boolean;
  rate_limit_per_minute: number;
  created_at: string;
}

export default function AdminB2BResellerPage() {
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newUserId, setNewUserId] = useState("");
  const [newCredit, setNewCredit] = useState("0");
  const [newIps, setNewIps] = useState("");
  const [creating, setCreating] = useState(false);
  const [plaintextKey, setPlaintextKey] = useState<string | null>(null);

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery<ResellerApiKey[]>({
    queryKey: [RESELLER_KEYS_QUERY_KEY],
    queryFn: async () => {
      const res = await apiClient.get<ResellerApiKey[]>("/orders/reseller/admin/keys", {
        params: { limit: 100 },
      });
      return Array.isArray(res.data) ? res.data : [];
    },
    // The old load swallowed the failure and rendered the empty state; keep
    // that by not surfacing `error` and not toasting.
    fallbackError: "خطا در دریافت کلیدهای API همکاران",
  });
  const keys: ResellerApiKey[] = data ?? [];

  const runMutation = useAdminMutation();

  const createKey = async () => {
    if (!newName.trim() || !newUserId.trim()) {
      toast({ title: "خطا", description: "نام همکار و شناسه کاربر الزامی است", variant: "destructive" });
      return;
    }
    setCreating(true);
    const result = await runMutation(
      () => {
        const ipList = newIps.trim()
          ? newIps.split("\n").map((ip) => ip.trim()).filter(Boolean)
          : undefined;

        return apiClient.post("/orders/reseller/admin/keys", {
          user_id: newUserId,
          name: newName,
          ip_whitelist: ipList,
          initial_credit: parseInt(newCredit) || 0,
        });
      },
      {
        fallbackError: "ایجاد کلید API با خطا مواجه شد",
        invalidateKeys: [[RESELLER_KEYS_QUERY_KEY]],
        onSuccess: (res) => {
          setPlaintextKey(res.data.plaintext_api_key);
          toast({ title: "موفق", description: "کلید API همکار ایجاد شد" });
          setCreateOpen(false);
        },
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setCreating(false);
  };

  const keyColumns: DataTableColumn<ResellerApiKey>[] = [
    {
      key: "name",
      header: "نام همکار",
      className: "font-medium",
      render: (k) => k.name,
    },
    {
      key: "prefix",
      header: "پیش‌شماره کلید",
      className: "font-mono text-xs",
      render: (k) => <span dir="ltr">{k.key_prefix}...</span>,
    },
    {
      key: "credit",
      header: "اعتبار",
      className: "text-xs",
      render: (k) => `${k.credit_balance.toLocaleString("fa-IR")} ریال`,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (k) => (
        <Badge
          className={k.is_active ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}
        >
          {k.is_active ? "فعال" : "غیرفعال"}
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Briefcase className="h-5 w-5 text-primary" />
            فروش سازمانی و همکاران B2B
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            صدور و مدیریت کلیدهای API برای وب‌سایت‌های همکار
          </p>
        </div>
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 ms-2" />
          صدور کلید API جدید
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : keys.length === 0 ? (
        <Card className="p-12 text-center">
          <KeyRound className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm text-muted-foreground">هنوز هیچ کلید API صادر نشده است</p>
          <Button size="sm" className="mt-4" onClick={() => setCreateOpen(true)}>
            صدور اولین کلید
          </Button>
        </Card>
      ) : (
        <Card>
          <DataTable<ResellerApiKey>
            columns={keyColumns}
            rows={keys}
            rowKey={(k) => k.id}
          />
        </Card>
      )}

      {/* Create Key Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>صدور کلید API سازمانی</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>نام همکار / شرکت</Label>
              <Input placeholder="مثال: فروشگاه نمونه" value={newName} onChange={(e) => setNewName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>شناسه کاربر (UUID)</Label>
              <Input placeholder="UUID کاربر در پنل" value={newUserId} onChange={(e) => setNewUserId(e.target.value)} dir="ltr" />
            </div>
            <div className="space-y-2">
              <Label>اعتبار اولیه (ریال)</Label>
              <Input type="number" value={newCredit} onChange={(e) => setNewCredit(e.target.value)} dir="ltr" />
            </div>
            <div className="space-y-2">
              <Label>آی‌پی‌های مجاز (هر خط یک IP - اختیاری)</Label>
              <Input placeholder="91.107.144.136" value={newIps} onChange={(e) => setNewIps(e.target.value)} dir="ltr" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>انصراف</Button>
            <Button onClick={createKey} disabled={creating}>
              {creating ? "در حال صدور..." : "صدور کلید"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Plaintext Key Display Dialog */}
      <Dialog open={!!plaintextKey} onOpenChange={(open) => !open && setPlaintextKey(null)}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>کلید API شما</DialogTitle>
          </DialogHeader>
          <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 text-sm text-amber-600">
            <strong>هشدار:</strong> این کلید فقط یک بار نمایش داده می‌شود. آن را در جای امن ذخیره کنید.
          </div>
          <div className="mt-4 bg-muted rounded-lg p-3 font-mono text-xs break-all" dir="ltr">
            {plaintextKey}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(plaintextKey || "");
                toast({ title: "کپی شد" });
              }}
            >
              <Copy className="h-4 w-4 ms-2" />
              کپی کلید
            </Button>
            <Button onClick={() => setPlaintextKey(null)}>بستن</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
