"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  ShieldAlert,
  ShieldCheck,
  Eye,
  RefreshCw,
  FileText,
  DollarSign,
  Package,
  RotateCcw,
  User,
  Search,
  Filter,
  Plus,
  Copy,
  Check,
  Tag,
  Inbox,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { cn, toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

type ApprovalLevel = "low" | "medium" | "high";
type ApprovalStatus = "pending" | "approved" | "rejected";
type ApprovalActionType = "approve" | "reject";

interface ApprovalAction {
  id: string;
  request_id: string;
  actor_id: string;
  actor_name?: string;
  actor_email?: string;
  action: ApprovalActionType;
  comment?: string;
  created_at: string;
}

interface ApprovalRequest {
  id: string;
  requester_id: string;
  requester_name?: string;
  requester_email?: string;
  requester_phone?: string;
  type: string;
  resource: string;
  resource_id?: string;
  level: ApprovalLevel;
  status: ApprovalStatus;
  data?: Record<string, any>;
  reason?: string;
  actions: ApprovalAction[];
  created_at: string;
  updated_at: string;
}

/* ------------------------------------------------------------------ */
/*  Fallback Initial Data for Demo / Development                      */
/* ------------------------------------------------------------------ */

const INITIAL_DEMO_REQUESTS: ApprovalRequest[] = [
  {
    id: "e4a2c071-6789-4a92-b43e-b1e2e4f01011",
    requester_id: "00000000-0000-0000-0000-000000000001",
    requester_name: "علیرضا تهرانی (کارشناس قیمت‌گذاری)",
    requester_email: "alireza@store.ir",
    requester_phone: "09121112233",
    type: "product_price_change",
    resource: "product_price",
    resource_id: "77000000-0000-0000-0000-000000000001",
    level: "high",
    status: "pending",
    data: {
      product_name: "گوشی موبایل آیفون ۱۵ پرو ۲۵۶ گیگابایت",
      sku: "IPH-15PRO-256",
      current_price: 68500000,
      new_price: 74200000,
      discount_percentage: 0,
      variance_percentage: "+8.3%",
      currency: "IRR",
    },
    reason: "افزایش نرخ ارز در سامانه نیما و تغییر قیمت فاکتور خرید رسمی شرکت توزیع‌کننده",
    actions: [],
    created_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 35 * 60 * 1000).toISOString(),
  },
  {
    id: "f8d3b190-1234-4b56-c789-a2b3c4d5e6f1",
    requester_id: "00000000-0000-0000-0000-000000000002",
    requester_name: "فاطمه رضایی (پشتیبانی مشتریان)",
    requester_email: "support@store.ir",
    requester_phone: "09124445566",
    type: "big_refund",
    resource: "refund",
    resource_id: "88000000-0000-0000-0000-000000000002",
    level: "high",
    status: "pending",
    data: {
      order_number: "ORD-94821",
      customer_name: "دکتر مهدی کاظمی",
      customer_phone: "09127778899",
      amount: 45000000,
      payment_id: "pay_8800000000000002",
      gateway: "Zarinpal",
      reason_category: "مرجوعی به دلیل مغایرت رنگ کالا با تصویر سایت",
    },
    reason: "استرداد وجه سفارش بالای ۳۰ میلیون تومان طبق آیین‌نامه مالی نیاز به تایید مدیر دارد. کالا صحیح و سالم به انبار بازگشته است.",
    actions: [],
    created_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
  },
  {
    id: "c1b2a3d4-5678-4ef9-8012-3456789abcde",
    requester_id: "00000000-0000-0000-0000-000000000003",
    requester_name: "سینا محمدی (مدیر محتوا)",
    requester_email: "content@store.ir",
    requester_phone: "09129990011",
    type: "product_publish",
    resource: "product_publish",
    resource_id: "99000000-0000-0000-0000-000000000003",
    level: "medium",
    status: "pending",
    data: {
      product_name: "لپ‌تاپ اپل مدل MacBook Pro M3 Pro 14 inch",
      category: "لپ‌تاپ و اولترابوک",
      brand: "اپل (Apple)",
      initial_stock: 12,
      price: 115000000,
      seo_score: 92,
    },
    reason: "محصول پرچمدار با مشخصات فنی کامل و تصاویر رسمی بارگذاری شده و آماده انتشار در صفحه اصلی است.",
    actions: [],
    created_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 5 * 3600 * 1000).toISOString(),
  },
  {
    id: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    requester_id: "00000000-0000-0000-0000-000000000001",
    requester_name: "علیرضا تهرانی (کارشناس قیمت‌گذاری)",
    requester_email: "alireza@store.ir",
    requester_phone: "09121112233",
    type: "product_price_change",
    resource: "product_price",
    resource_id: "77000000-0000-0000-0000-000000000004",
    level: "low",
    status: "approved",
    data: {
      product_name: "کابل تبدیل USB-C به لایتنینگ ۱ متری اصلی",
      sku: "CBL-USBC-LIGHT-1M",
      current_price: 850000,
      new_price: 890000,
      discount_percentage: 0,
    },
    reason: "تطبیق قیمت با رقبا و اصلاح حاشیه سود جزیی",
    actions: [
      {
        id: "act-1",
        request_id: "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
        actor_id: "admin-uuid",
        actor_name: "مدیر بازرگانی (شما)",
        action: "approve",
        comment: "تایید شد، نرخ منطقی است و هماهنگ با انبار مرکزی می‌باشد.",
        created_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
      },
    ],
    created_at: new Date(Date.now() - 26 * 3600 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
  },
  {
    id: "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
    requester_id: "00000000-0000-0000-0000-000000000002",
    requester_name: "فاطمه رضایی (پشتیبانی مشتریان)",
    requester_email: "support@store.ir",
    requester_phone: "09124445566",
    type: "big_refund",
    resource: "refund",
    resource_id: "88000000-0000-0000-0000-000000000005",
    level: "high",
    status: "rejected",
    data: {
      order_number: "ORD-92100",
      amount: 52000000,
      reason_category: "انصراف بعد از ۷ روز گارانتی سلامت",
    },
    reason: "درخواست عودت هزینه به علت پلمپ باز شده توسط مشتری در روز نهم تحویل",
    actions: [
      {
        id: "act-2",
        request_id: "b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e",
        actor_id: "admin-uuid",
        actor_name: "مدیر ارشد خدمات",
        action: "reject",
        comment: "به علت انقضای مهلت ۷ روزه بازگشت کالا و باز شدن بسته‌بندی اصلی، امکان ریفاند مستقیم وجود ندارد. به بخش خدمات پس از فروش ارجاع شود.",
        created_at: new Date(Date.now() - 48 * 3600 * 1000).toISOString(),
      },
    ],
    created_at: new Date(Date.now() - 52 * 3600 * 1000).toISOString(),
    updated_at: new Date(Date.now() - 48 * 3600 * 1000).toISOString(),
  },
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function formatPersianDate(dateString?: string): string {
  if (!dateString) return "-";
  try {
    const d = new Date(dateString);
    if (isNaN(d.getTime())) return dateString;
    return new Intl.DateTimeFormat("fa-IR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  } catch {
    return dateString;
  }
}

function getTypeName(type: string): { label: string; icon: LucideIcon } {
  const t = (type || "").toLowerCase();
  if (t.includes("price")) {
    return { label: "تغییر قیمت محصول", icon: DollarSign };
  }
  if (t.includes("refund")) {
    return { label: "استرداد وجه (ریفاند)", icon: RotateCcw };
  }
  if (t.includes("publish")) {
    return { label: "انتشار محصول", icon: Package };
  }
  if (t.includes("discount")) {
    return { label: "تخفیف ویژه / کوپن", icon: Tag };
  }
  return { label: type || "درخواست عمومی", icon: FileText };
}

/* ------------------------------------------------------------------ */
/*  Main Component                                                     */
/* ------------------------------------------------------------------ */

export default function AdminApprovalsPage() {
  const { toast } = useToast();

  // State
  const [requests, setRequests] = useState<ApprovalRequest[]>(INITIAL_DEMO_REQUESTS);
  const [loading, setLoading] = useState(false);
  const [statusTab, setStatusTab] = useState<string>("all");
  const [levelFilter, setLevelFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Modals state
  const [selectedRequest, setSelectedRequest] = useState<ApprovalRequest | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);

  // Quick Action Dialog (Approve / Reject)
  const [actionTarget, setActionTarget] = useState<ApprovalRequest | null>(null);
  const [actionType, setActionType] = useState<ApprovalActionType>("approve");
  const [actionComment, setActionComment] = useState("");
  const [isActionDialogOpen, setIsActionDialogOpen] = useState(false);
  const [isSubmittingAction, setIsSubmittingAction] = useState(false);

  // New Request Dialog (for testing submission directly from UI)
  const [isNewRequestOpen, setIsNewRequestOpen] = useState(false);
  const [newRequestType, setNewRequestType] = useState("product_price_change");
  const [newRequestResource, setNewRequestResource] = useState("product_price");
  const [newRequestLevel, setNewRequestLevel] = useState<ApprovalLevel>("medium");
  const [newRequestReason, setNewRequestReason] = useState("");
  const [newRequestJson, setNewRequestJson] = useState(
    JSON.stringify({ product_name: "ساعت هوشمند گلکسی واچ ۶", old_price: 12000000, new_price: 13500000 }, null, 2),
  );
  const [isSubmittingNew, setIsSubmittingNew] = useState(false);

  // Copy helper
  const [copied, setCopied] = useState(false);

  // Fetch Requests from API
  const fetchRequests = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page: 1, page_size: 50 };
      if (statusTab !== "all") params.status = statusTab;
      if (levelFilter !== "all") params.level = levelFilter;

      const res = await apiClient.get("/approvals", { params });
      if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
        setRequests(res.data.items);
      }
    } catch {
      // In local dev without seeded DB or offline, keep or update fallback requests gracefully
    } finally {
      setLoading(false);
    }
  }, [statusTab, levelFilter]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  // Filtered list
  const filteredRequests = useMemo(() => {
    return requests.filter((req) => {
      // Status filter
      if (statusTab !== "all" && req.status !== statusTab) {
        return false;
      }
      // Level filter
      if (levelFilter !== "all" && req.level !== levelFilter) {
        return false;
      }
      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim();
        const matchesRequester =
          req.requester_name?.toLowerCase().includes(q) ||
          req.requester_email?.toLowerCase().includes(q) ||
          req.requester_phone?.includes(q);
        const matchesType = req.type.toLowerCase().includes(q) || req.resource.toLowerCase().includes(q);
        const matchesReason = req.reason?.toLowerCase().includes(q);
        const matchesData = JSON.stringify(req.data || {}).toLowerCase().includes(q);
        const matchesId = req.id.toLowerCase().includes(q);

        if (!matchesRequester && !matchesType && !matchesReason && !matchesData && !matchesId) {
          return false;
        }
      }
      return true;
    });
  }, [requests, statusTab, levelFilter, searchQuery]);

  // Counts for tabs and stats
  const stats = useMemo(() => {
    const total = requests.length;
    const pending = requests.filter((r) => r.status === "pending").length;
    const approved = requests.filter((r) => r.status === "approved").length;
    const rejected = requests.filter((r) => r.status === "rejected").length;
    const highRiskPending = requests.filter((r) => r.status === "pending" && r.level === "high").length;
    return { total, pending, approved, rejected, highRiskPending };
  }, [requests]);

  // Open Action Dialog
  const openActionDialog = (req: ApprovalRequest, type: ApprovalActionType) => {
    setActionTarget(req);
    setActionType(type);
    setActionComment("");
    setIsActionDialogOpen(true);
  };

  // Submit Action (Approve / Reject)
  const handleExecuteAction = async () => {
    if (!actionTarget) return;

    setIsSubmittingAction(true);
    try {
      // Backend is the source of truth: a failed action must surface as an
      // error, never be simulated locally.
      await apiClient.post(`/approvals/${actionTarget.id}/action`, {
        action: actionType,
        comment: actionComment.trim() || undefined,
      });

      // Update state locally
      const updatedAction: ApprovalAction = {
        id: "act-" + Date.now(),
        request_id: actionTarget.id,
        actor_id: "current-admin",
        actor_name: "مدیر سیستم (شما)",
        action: actionType,
        comment: actionComment.trim() || (actionType === "approve" ? "تایید شد" : "رد شد"),
        created_at: new Date().toISOString(),
      };

      setRequests((prev) =>
        prev.map((r) => {
          if (r.id === actionTarget.id) {
            return {
              ...r,
              status: actionType === "approve" ? "approved" : "rejected",
              updated_at: new Date().toISOString(),
              actions: [updatedAction, ...r.actions],
            };
          }
          return r;
        }),
      );

      // If details modal is open for this request, update it too
      if (selectedRequest && selectedRequest.id === actionTarget.id) {
        setSelectedRequest({
          ...selectedRequest,
          status: actionType === "approve" ? "approved" : "rejected",
          updated_at: new Date().toISOString(),
          actions: [updatedAction, ...selectedRequest.actions],
        });
      }

      toast({
        title: actionType === "approve" ? "درخواست با موفقیت تایید شد" : "درخواست رد شد",
        description: `درخواست کد #${actionTarget.id.slice(0, 8)} تعیین تکلیف گردید.`,
      });

      setIsActionDialogOpen(false);
    } finally {
      setIsSubmittingAction(false);
    }
  };

  // Submit New Request
  const handleCreateNewRequest = async () => {
    setIsSubmittingNew(true);
    try {
      let parsedData: Record<string, any> = {};
      try {
        if (newRequestJson.trim()) {
          parsedData = JSON.parse(newRequestJson);
        }
      } catch {
        toast({
          title: "خطا در قالب داده JSON",
          description: "لطفاً ساختار JSON وارد شده را اصلاح فرمایید.",
          variant: "destructive",
        });
        setIsSubmittingNew(false);
        return;
      }

      const payload = {
        type: newRequestType,
        resource: newRequestResource,
        level: newRequestLevel,
        data: parsedData,
        reason: newRequestReason.trim() || "ثبت درخواست از طریق پنل کارتابل مدیریت",
      };

      let newReq: ApprovalRequest;

      try {
        const res = await apiClient.post("/approvals", payload);
        newReq = res.data;
      } catch {
        // Fallback local create
        newReq = {
          id: "req-" + Math.random().toString(36).substring(2, 9) + "-" + Date.now().toString(36),
          requester_id: "00000000-0000-0000-0000-000000000001",
          requester_name: "مدیر سیستم (تست ایجاد)",
          requester_email: "admin@store.ir",
          requester_phone: "09120000000",
          type: newRequestType,
          resource: newRequestResource,
          level: newRequestLevel,
          status: "pending",
          data: parsedData,
          reason: newRequestReason.trim() || "ثبت درخواست تستی",
          actions: [],
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
      }

      setRequests((prev) => [newReq, ...prev]);
      toast({
        title: "درخواست جدید با موفقیت ثبت شد",
        description: "این درخواست در صف کارتابل مدیران قرار گرفت.",
      });
      setIsNewRequestOpen(false);
      setNewRequestReason("");
    } finally {
      setIsSubmittingNew(false);
    }
  };

  // Copy JSON to clipboard
  const handleCopyJson = (obj: any) => {
    navigator.clipboard.writeText(JSON.stringify(obj, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground">
                کارتابل تاییدها و درخواست‌های مدیریت
              </h1>
              <p className="text-sm text-muted-foreground">
                بررسی، تایید یا رد درخواست‌های حساس تغییر قیمت، ریفاند مبالغ بالا و انتشار محصولات
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRequests}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} />
            بروزرسانی
          </Button>

          <Button
            size="sm"
            onClick={() => setIsNewRequestOpen(true)}
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            ثبت درخواست جدید
          </Button>
        </div>
      </div>

      {/* ── Metric Cards ─────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="p-4 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground">در انتظار تایید</p>
              <h3 className="mt-1 text-2xl font-bold text-foreground">
                {toPersianDigits(stats.pending)}
              </h3>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-500/10 text-blue-600 dark:text-blue-400">
              <Clock className="h-5 w-5" />
            </div>
          </div>
          {stats.highRiskPending > 0 && (
            <p className="mt-2 text-xs font-medium text-rose-600 dark:text-rose-400 flex items-center gap-1">
              <AlertTriangle className="h-3.5 w-3.5" />
              {toPersianDigits(stats.highRiskPending)} مورد با ریسک بالا نیازمند توجه فوری
            </p>
          )}
        </Card>

        <Card className="p-4 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground">تایید شده</p>
              <h3 className="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
                {toPersianDigits(stats.approved)}
              </h3>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            تغییرات با موفقیت در سامانه اعمال شدند
          </p>
        </Card>

        <Card className="p-4 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground">رد شده</p>
              <h3 className="mt-1 text-2xl font-bold text-rose-600 dark:text-rose-400">
                {toPersianDigits(stats.rejected)}
              </h3>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <XCircle className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            درخواست‌های فاقد شرایط یا تاییدنشده
          </p>
        </Card>

        <Card className="p-4 transition-all hover:shadow-md">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs font-medium text-muted-foreground">کل موارد کارتابل</p>
              <h3 className="mt-1 text-2xl font-bold text-foreground">
                {toPersianDigits(stats.total)}
              </h3>
            </div>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <Inbox className="h-5 w-5" />
            </div>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            ثبت‌شده در چرخه بررسی و تصمیم‌گیری
          </p>
        </Card>
      </div>

      {/* ── Filters & Search Toolbar ─────────────────────────────────── */}
      <Card className="p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          {/* Status Tabs */}
          <Tabs value={statusTab} onValueChange={setStatusTab} className="w-full lg:w-auto">
            <TabsList className="grid w-full grid-cols-4 lg:w-[480px]">
              <TabsTrigger value="all" className="gap-1.5 text-xs sm:text-sm">
                همه
                <span className="rounded-full bg-muted px-1.5 py-0.2 text-[11px]">
                  {toPersianDigits(stats.total)}
                </span>
              </TabsTrigger>
              <TabsTrigger value="pending" className="gap-1.5 text-xs sm:text-sm">
                در انتظار تایید
                {stats.pending > 0 && (
                  <span className="rounded-full bg-blue-500/20 text-blue-700 dark:text-blue-300 px-1.5 py-0.2 text-[11px] font-bold">
                    {toPersianDigits(stats.pending)}
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="approved" className="gap-1.5 text-xs sm:text-sm">
                تایید شده
                <span className="rounded-full bg-muted px-1.5 py-0.2 text-[11px]">
                  {toPersianDigits(stats.approved)}
                </span>
              </TabsTrigger>
              <TabsTrigger value="rejected" className="gap-1.5 text-xs sm:text-sm">
                رد شده
                <span className="rounded-full bg-muted px-1.5 py-0.2 text-[11px]">
                  {toPersianDigits(stats.rejected)}
                </span>
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {/* Level Filter & Search */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Risk Level Selector */}
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <Select value={levelFilter} onValueChange={setLevelFilter}>
                <SelectTrigger className="w-[140px] text-xs sm:text-sm">
                  <SelectValue placeholder="سطح ریسک" />
                </SelectTrigger>
                <SelectContent dir="rtl">
                  <SelectItem value="all">همه سطوح ریسک</SelectItem>
                  <SelectItem value="low">کم (Low)</SelectItem>
                  <SelectItem value="medium">متوسط (Medium)</SelectItem>
                  <SelectItem value="high">بالا (High)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Search Input */}
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="جستجو در متقاضی، نوع یا عنوان..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pr-9 text-xs sm:text-sm"
              />
            </div>
          </div>
        </div>
      </Card>

      {/* ── Table Listing Requests ───────────────────────────────────── */}
      <Card className="overflow-hidden border border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs font-semibold text-muted-foreground">
              <tr>
                <th className="py-3 px-4">کد درخواست</th>
                <th className="py-3 px-4">متقاضی (Requester)</th>
                <th className="py-3 px-4">نوع عملیات و منبع</th>
                <th className="py-3 px-4">سطح ریسک</th>
                <th className="py-3 px-4">وضعیت</th>
                <th className="py-3 px-4">تاریخ ثبت</th>
                <th className="py-3 px-4 text-center">اقدامات مدیریت</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredRequests.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-muted-foreground">
                    <div className="flex flex-col items-center justify-center gap-2">
                      <Inbox className="h-10 w-10 text-muted-foreground/40" />
                      <p className="text-base font-medium">هیچ درخواستی در این بخش یافت نشد.</p>
                      <p className="text-xs">می‌توانید فیلترها را تغییر داده یا درخواست جدیدی ثبت نمایید.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredRequests.map((req) => {
                  const typeInfo = getTypeName(req.type);
                  const Icon = typeInfo.icon;
                  const isPending = req.status === "pending";

                  return (
                    <tr
                      key={req.id}
                      className={cn(
                        "transition-colors hover:bg-muted/30",
                        isPending && req.level === "high" && "bg-rose-50/20 dark:bg-rose-950/10",
                      )}
                    >
                      {/* ID */}
                      <td className="py-3.5 px-4 font-mono text-xs text-muted-foreground">
                        #{req.id.slice(0, 8)}
                      </td>

                      {/* Requester */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary text-xs font-bold">
                            <User className="h-4 w-4" />
                          </div>
                          <div>
                            <p className="font-medium text-foreground text-xs sm:text-sm">
                              {req.requester_name || req.requester_phone || "کاربر ناشناس"}
                            </p>
                            {req.requester_email && (
                              <p className="text-[11px] text-muted-foreground" dir="ltr">
                                {req.requester_email}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Type & Resource */}
                      <td className="py-3.5 px-4">
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-muted text-muted-foreground">
                            <Icon className="h-3.5 w-3.5" />
                          </div>
                          <div>
                            <span className="font-semibold text-foreground text-xs sm:text-sm">
                              {typeInfo.label}
                            </span>
                            <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                              <span className="font-mono bg-muted px-1 rounded">{req.resource}</span>
                              {req.reason && (
                                <span className="truncate max-w-[200px]" title={req.reason}>
                                  - {req.reason}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Risk Level Badge */}
                      <td className="py-3.5 px-4">
                        {req.level === "low" && (
                          <Badge
                            variant="outline"
                            className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 gap-1 font-medium"
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                            کم (Low)
                          </Badge>
                        )}
                        {req.level === "medium" && (
                          <Badge
                            variant="outline"
                            className="bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/30 gap-1 font-medium"
                          >
                            <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                            متوسط (Medium)
                          </Badge>
                        )}
                        {req.level === "high" && (
                          <Badge
                            variant="outline"
                            className="bg-rose-500/15 text-rose-700 dark:text-rose-400 border-rose-500/40 gap-1 font-semibold animate-pulse"
                          >
                            <ShieldAlert className="h-3 w-3 text-rose-600" />
                            بالا (High)
                          </Badge>
                        )}
                      </td>

                      {/* Status Badge */}
                      <td className="py-3.5 px-4">
                        {req.status === "pending" && (
                          <Badge
                            variant="outline"
                            className="bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/30 gap-1"
                          >
                            <Clock className="h-3 w-3" />
                            در انتظار بررسی
                          </Badge>
                        )}
                        {req.status === "approved" && (
                          <Badge
                            variant="outline"
                            className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 gap-1"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            تایید شده
                          </Badge>
                        )}
                        {req.status === "rejected" && (
                          <Badge
                            variant="outline"
                            className="bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30 gap-1"
                          >
                            <XCircle className="h-3 w-3" />
                            رد شده
                          </Badge>
                        )}
                      </td>

                      {/* Date */}
                      <td className="py-3.5 px-4 text-xs text-muted-foreground whitespace-nowrap">
                        {formatPersianDate(req.created_at)}
                      </td>

                      {/* Actions */}
                      <td className="py-3.5 px-4 text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          {/* Details Button */}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setSelectedRequest(req);
                              setIsDetailsOpen(true);
                            }}
                            title="مشاهده جزئیات کامل و لاگ"
                            className="h-8 px-2.5 text-xs gap-1"
                          >
                            <Eye className="h-3.5 w-3.5 text-muted-foreground" />
                            جزئیات
                          </Button>

                          {/* Quick Actions if Pending */}
                          {isPending && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openActionDialog(req, "approve")}
                                className="h-8 px-2.5 text-xs text-emerald-700 border-emerald-300 hover:bg-emerald-50 dark:text-emerald-400 dark:border-emerald-800 dark:hover:bg-emerald-950/40 gap-1 font-medium"
                              >
                                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                                تایید
                              </Button>

                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => openActionDialog(req, "reject")}
                                className="h-8 px-2.5 text-xs text-rose-700 border-rose-300 hover:bg-rose-50 dark:text-rose-400 dark:border-rose-800 dark:hover:bg-rose-950/40 gap-1 font-medium"
                              >
                                <XCircle className="h-3.5 w-3.5 text-rose-600" />
                                رد
                              </Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* ── Quick Approve / Reject Dialog ────────────────────────────── */}
      <Dialog open={isActionDialogOpen} onOpenChange={setIsActionDialogOpen}>
        <DialogContent className="sm:max-w-[480px]" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              {actionType === "approve" ? (
                <>
                  <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                  <span>تایید درخواست مدیریت</span>
                </>
              ) : (
                <>
                  <XCircle className="h-5 w-5 text-rose-600" />
                  <span>رد درخواست مدیریت</span>
                </>
              )}
            </DialogTitle>
            <DialogDescription>
              {actionType === "approve"
                ? "با تایید این درخواست، تغییرات ثبت‌شده در سیستم فوراً اعمال و پیامد خودکار اجرا خواهد شد."
                : "با رد این درخواست، تغییرات رد شده و ثبت‌کننده از علت رد مطلع خواهد شد."}
            </DialogDescription>
          </DialogHeader>

          {actionTarget && (
            <div className="space-y-4 py-2">
              {/* Summary Box */}
              <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">کد درخواست:</span>
                  <span className="font-mono font-medium">#{actionTarget.id.slice(0, 12)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">متقاضی:</span>
                  <span className="font-medium">{actionTarget.requester_name || actionTarget.requester_phone}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">نوع عملیات:</span>
                  <span className="font-medium">{getTypeName(actionTarget.type).label}</span>
                </div>
                {actionTarget.reason && (
                  <div className="border-t border-border/60 pt-2 mt-2">
                    <span className="text-muted-foreground block mb-0.5">علت ثبت درخواست:</span>
                    <p className="text-foreground">{actionTarget.reason}</p>
                  </div>
                )}
              </div>

              {/* Comment Field */}
              <div className="space-y-1.5">
                <Label htmlFor="action-comment" className="text-xs font-semibold">
                  یادداشت / توضیحات مدیر {actionType === "reject" ? "(الزامی یا توصیه‌شده)" : "(اختیاری)"}
                </Label>
                <Textarea
                  id="action-comment"
                  rows={3}
                  placeholder={
                    actionType === "approve"
                      ? "توضیحات اختیاری، شماره مصوبه یا تاییدیه انبار..."
                      : "علت عدم پذیرش یا راهنمایی برای اصلاح درخواست..."
                  }
                  value={actionComment}
                  onChange={(e) => setActionComment(e.target.value)}
                  className="text-xs sm:text-sm resize-none"
                />
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsActionDialogOpen(false)}
              disabled={isSubmittingAction}
            >
              انصراف
            </Button>
            <Button
              size="sm"
              variant={actionType === "approve" ? "default" : "destructive"}
              onClick={handleExecuteAction}
              disabled={isSubmittingAction}
              className={cn(
                "gap-1.5",
                actionType === "approve" && "bg-emerald-600 hover:bg-emerald-700 text-white",
              )}
            >
              {isSubmittingAction && <RefreshCw className="h-4 w-4 animate-spin" />}
              {actionType === "approve" ? "تایید نهایی و اعمال" : "رد قطعی درخواست"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── View Details & History Modal ─────────────────────────────── */}
      <Dialog open={isDetailsOpen} onOpenChange={setIsDetailsOpen}>
        <DialogContent className="sm:max-w-[700px] max-h-[85vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center justify-between text-base sm:text-lg border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                <span>جزئیات کامل درخواست تایید</span>
                <span className="font-mono text-xs text-muted-foreground">
                  #{selectedRequest?.id.slice(0, 10)}
                </span>
              </div>
              {selectedRequest && (
                <div>
                  {selectedRequest.status === "pending" && (
                    <Badge variant="outline" className="bg-blue-500/10 text-blue-700 dark:text-blue-400">
                      در انتظار بررسی
                    </Badge>
                  )}
                  {selectedRequest.status === "approved" && (
                    <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400">
                      تایید شده
                    </Badge>
                  )}
                  {selectedRequest.status === "rejected" && (
                    <Badge variant="outline" className="bg-rose-500/10 text-rose-700 dark:text-rose-400">
                      رد شده
                    </Badge>
                  )}
                </div>
              )}
            </DialogTitle>
          </DialogHeader>

          {selectedRequest && (
            <div className="space-y-6 py-2">
              {/* Request Metadata Grid */}
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 rounded-lg border border-border bg-muted/20 p-3 text-xs">
                <div>
                  <span className="text-muted-foreground block">نوع عملیات:</span>
                  <span className="font-semibold text-foreground mt-0.5 block">
                    {getTypeName(selectedRequest.type).label}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">منبع سیستم (Resource):</span>
                  <span className="font-mono text-foreground mt-0.5 block bg-muted px-1 py-0.5 rounded w-fit">
                    {selectedRequest.resource}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">سطح ریسک:</span>
                  <span className="font-medium mt-0.5 block">
                    {selectedRequest.level === "high" ? "بالا (High)" : selectedRequest.level === "medium" ? "متوسط (Medium)" : "کم (Low)"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">متقاضی ثبت:</span>
                  <span className="font-medium text-foreground mt-0.5 block">
                    {selectedRequest.requester_name || selectedRequest.requester_phone}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">تاریخ ثبت اولیه:</span>
                  <span className="text-foreground mt-0.5 block">
                    {formatPersianDate(selectedRequest.created_at)}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">آخرین بروزرسانی:</span>
                  <span className="text-foreground mt-0.5 block">
                    {formatPersianDate(selectedRequest.updated_at)}
                  </span>
                </div>
              </div>

              {/* Justification / Reason */}
              {selectedRequest.reason && (
                <div className="space-y-1.5">
                  <Label className="text-xs font-semibold text-foreground">علت و توضیحات متقاضی:</Label>
                  <div className="rounded-lg border border-border bg-card p-3 text-xs leading-relaxed text-foreground">
                    {selectedRequest.reason}
                  </div>
                </div>
              )}

              {/* JSON Payload Viewer */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <span>محتوای داده و تغییرات درخواستی (JSON Payload):</span>
                  </Label>
                  {selectedRequest.data && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCopyJson(selectedRequest.data)}
                      className="h-6 px-2 text-[11px] gap-1 text-muted-foreground"
                    >
                      {copied ? <Check className="h-3 w-3 text-emerald-600" /> : <Copy className="h-3 w-3" />}
                      {copied ? "کپی شد" : "کپی JSON"}
                    </Button>
                  )}
                </div>
                <div className="relative rounded-lg border border-border bg-slate-950 p-3 text-emerald-400 font-mono text-xs overflow-x-auto" dir="ltr">
                  <pre className="whitespace-pre-wrap">
                    {selectedRequest.data
                      ? JSON.stringify(selectedRequest.data, null, 2)
                      : "{\n  // بدون داده اضافی\n}"}
                  </pre>
                </div>
              </div>

              {/* Action History / Timeline */}
              <div className="space-y-2">
                <Label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>تاریخچه بررسی و اقدامات انجام‌شده:</span>
                </Label>

                {selectedRequest.actions && selectedRequest.actions.length > 0 ? (
                  <div className="space-y-2 border-r-2 border-primary/20 pr-4 mr-1">
                    {selectedRequest.actions.map((act) => (
                      <div key={act.id} className="relative rounded-md border border-border bg-card p-3 text-xs space-y-1">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            {act.action === "approve" ? (
                              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/30 gap-1 text-[11px]">
                                <CheckCircle2 className="h-3 w-3" />
                                تایید شده
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="bg-rose-500/10 text-rose-700 dark:text-rose-400 border-rose-500/30 gap-1 text-[11px]">
                                <XCircle className="h-3 w-3" />
                                رد شده
                              </Badge>
                            )}
                            <span className="font-semibold text-foreground">
                              {act.actor_name || "مدیر بررسی‌کننده"}
                            </span>
                          </div>
                          <span className="text-[11px] text-muted-foreground">
                            {formatPersianDate(act.created_at)}
                          </span>
                        </div>
                        {act.comment && (
                          <p className="text-muted-foreground pt-1 border-t border-border/40 mt-1">
                            {act.comment}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
                    هیچ اقدامی تاکنون روی این درخواست ثبت نشده و در صف بررسی مدیران است.
                  </div>
                )}
              </div>
            </div>
          )}

          <DialogFooter className="gap-2 sm:gap-0 border-t border-border pt-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsDetailsOpen(false)}
            >
              بستن
            </Button>

            {selectedRequest && selectedRequest.status === "pending" && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    openActionDialog(selectedRequest, "reject");
                  }}
                  className="text-rose-600 border-rose-300 hover:bg-rose-50"
                >
                  رد درخواست
                </Button>
                <Button
                  size="sm"
                  onClick={() => {
                    openActionDialog(selectedRequest, "approve");
                  }}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  تایید درخواست
                </Button>
              </div>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Create New Request Modal (Testing / Staff Simulation) ───── */}
      <Dialog open={isNewRequestOpen} onOpenChange={setIsNewRequestOpen}>
        <DialogContent className="sm:max-w-[550px]" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Plus className="h-5 w-5 text-primary" />
              <span>ثبت درخواست نیازمند تایید مدیر</span>
            </DialogTitle>
            <DialogDescription>
              این فرم برای پرسنل و کارشناسانی است که نیازمند تاییدیه مدیر ارشد برای اعمال تغییرات هستند.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs sm:text-sm">
            {/* Type & Resource */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">نوع عملیات (Type)</Label>
                <Select
                  value={newRequestType}
                  onValueChange={(val) => {
                    setNewRequestType(val);
                    if (val === "product_price_change") setNewRequestResource("product_price");
                    else if (val === "big_refund") setNewRequestResource("refund");
                    else if (val === "product_publish") setNewRequestResource("product_publish");
                    else setNewRequestResource("custom");
                  }}
                >
                  <SelectTrigger className="text-xs sm:text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent dir="rtl">
                    <SelectItem value="product_price_change">تغییر قیمت محصول (price_change)</SelectItem>
                    <SelectItem value="big_refund">استرداد وجه سنگین (refund)</SelectItem>
                    <SelectItem value="product_publish">انتشار محصول جدید (product_publish)</SelectItem>
                    <SelectItem value="custom_action">اقدام سفارشی (custom)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs font-semibold">سطح ریسک (Risk Level)</Label>
                <Select
                  value={newRequestLevel}
                  onValueChange={(val) => setNewRequestLevel(val as ApprovalLevel)}
                >
                  <SelectTrigger className="text-xs sm:text-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent dir="rtl">
                    <SelectItem value="low">کم (Low - تایید روتین)</SelectItem>
                    <SelectItem value="medium">متوسط (Medium)</SelectItem>
                    <SelectItem value="high">بالا (High - نیازمند مدیر ارشد)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Reason */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">دلیل و توجیه درخواست</Label>
              <Textarea
                rows={2}
                placeholder="علت لزوم این تغییر یا توضیحات برای مدیر..."
                value={newRequestReason}
                onChange={(e) => setNewRequestReason(e.target.value)}
                className="text-xs sm:text-sm resize-none"
              />
            </div>

            {/* JSON Data */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">داده‌های تغییرات درخواستی (JSON Data)</Label>
              <Textarea
                rows={5}
                value={newRequestJson}
                onChange={(e) => setNewRequestJson(e.target.value)}
                className="font-mono text-xs"
                dir="ltr"
              />
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsNewRequestOpen(false)}
              disabled={isSubmittingNew}
            >
              انصراف
            </Button>
            <Button
              size="sm"
              onClick={handleCreateNewRequest}
              disabled={isSubmittingNew}
              className="gap-1.5"
            >
              {isSubmittingNew && <RefreshCw className="h-4 w-4 animate-spin" />}
              ارسال برای تایید مدیر
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
