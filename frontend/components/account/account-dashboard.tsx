"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  User,
  Package,
  Loader2,
  MapPin,
  Heart,
  Wallet as WalletIcon,
  Headphones,
  Users,
  LogOut,
  Bell,
  Edit3,
  Trash2,
  Plus,
  ShoppingBag,
  CheckCircle2,
  AlertCircle,
  Truck,
  Eye,
  ArrowUpLeft,
  ArrowDownRight,
  ShieldCheck,
  CreditCard,
  Building2,
  ExternalLink,
  Lock,
  Mail,
  Phone,
  MessageSquare,
  Printer,
  FileText,
  Gift,
  RotateCcw,
  Repeat,
  Coins,
  Store,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
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
import { useToast } from "@/components/ui/use-toast";
import { formatPrice, toPersianDigits, toEnglishDigits } from "@/lib/utils";
import { SavedCardsPanel } from "@/components/account/saved-cards-panel";
import { maskNationalId, maskPhoneNumber } from "@/lib/pii-mask";
import { checkReturnEligibility } from "@/lib/rma";
import { ShipmentStepper } from "@/components/orders/shipment-stepper";
import { ReferralPanel } from "@/components/account/referral-panel";
import { OrderHistorySkeleton } from "@/components/shared/skeleton-loaders";
import { apiErrorMessage } from "@/lib/api/error-message";
import { authApi } from "@/lib/api/auth";
import { useAuthStore } from "@/stores/auth-store";
import { MfaSettingsCard } from "@/components/account/mfa-settings-card";
import { PasskeyCard } from "@/components/account/passkey-card";
import { ApplicationPasswordsCard } from "@/components/account/application-passwords-card";
import { SessionsCard } from "@/components/account/sessions-card";
import { useCartStore } from "@/stores/cart-store";
import { useAuth } from "@/hooks/use-auth";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

// Mirrors OrderStatus in backend/app/modules/orders/domain/models.py.
// Note `canceled` (one l): the backend serialises the enum value, not the name.
type OrderStatusType =
  | "pending"
  | "confirmed"
  | "processing"
  | "packing"
  | "shipped"
  | "delivered"
  | "completed"
  | "canceled"
  | "on_hold"
  | "returned"
  | "refunded"
  | "partially_refunded";

interface OrderItemDisplay {
  id: string;
  title: string;
  image?: string;
  quantity: number;
  price: number;
}

interface OrderDisplay {
  id: string;
  orderNumber: string;
  date: string;
  total: number;
  status: OrderStatusType;
  items: OrderItemDisplay[];
  shippingAddress?: string;
  trackingCode?: string;
  paymentMethod?: string;
  deliveredAt?: string | null;
}

interface AddressItem {
  id: string;
  title: string;
  receiverName: string;
  phone: string;
  province: string;
  city: string;
  postalCode: string;
  fullAddress: string;
  isDefault: boolean;
}

interface WalletTransaction {
  id: string;
  type: "deposit" | "withdraw" | "purchase" | "refund";
  amount: number;
  date: string;
  description: string;
  trackingCode: string;
  status: "success" | "pending" | "failed";
}

interface WishlistItem {
  id: string;
  productId: string;
  title: string;
  slug: string;
  price: number;
  originalPrice?: number | null;
  image?: string;
  inStock: boolean;
  category?: string;
}

interface SupportTicket {
  id: string;
  ticketNumber: string;
  subject: string;
  department: string;
  priority: "low" | "medium" | "high" | "urgent";
  status: "open" | "in_progress" | "answered" | "closed";
  createdAt: string;
  updatedAt: string;
  lastMessage?: string;
}

/* ------------------------------------------------------------------ */
/*  Persian Status Mappings                                            */
/* ------------------------------------------------------------------ */

const ORDER_STATUS_CONFIG: Record<
  OrderStatusType,
  { label: string; badgeVariant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info" }
> = {
  pending: { label: "در انتظار پرداخت", badgeVariant: "warning" },
  confirmed: { label: "تایید شده", badgeVariant: "info" },
  processing: { label: "در حال پردازش", badgeVariant: "default" },
  packing: { label: "در حال بسته‌بندی", badgeVariant: "info" },
  shipped: { label: "ارسال شده", badgeVariant: "info" },
  delivered: { label: "تحویل داده شده", badgeVariant: "success" },
  completed: { label: "تکمیل شده", badgeVariant: "success" },
  canceled: { label: "لغو شده", badgeVariant: "destructive" },
  on_hold: { label: "در انتظار بررسی", badgeVariant: "warning" },
  returned: { label: "مرجوع شده", badgeVariant: "destructive" },
  refunded: { label: "بازپرداخت شده", badgeVariant: "secondary" },
  partially_refunded: { label: "بازپرداخت جزئی", badgeVariant: "secondary" },
};

const TICKET_STATUS_CONFIG: Record<
  SupportTicket["status"],
  { label: string; badgeVariant: "default" | "secondary" | "destructive" | "outline" | "success" | "warning" | "info" }
> = {
  open: { label: "باز", badgeVariant: "info" },
  in_progress: { label: "در حال بررسی", badgeVariant: "warning" },
  answered: { label: "پاسخ داده شده", badgeVariant: "success" },
  closed: { label: "بسته شده", badgeVariant: "secondary" },
};

const TICKET_PRIORITY_LABELS: Record<SupportTicket["priority"], string> = {
  low: "کم",
  medium: "متوسط",
  high: "زیاد",
  urgent: "فوری",
};

/* ------------------------------------------------------------------ */
/*  Initial Fallback Data                                              */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Main Account Page Component                                        */
/* ------------------------------------------------------------------ */

/**
 * Shown in place of a section's empty state when its read failed.
 *
 * Every account section used to fall back to "nothing here" on a failed load,
 * which is a claim about the customer's own data that the page cannot support.
 * This states the failure instead, and keeps the backend's own message.
 */
/**
 * Which of the three states an account section is in.
 *
 * Pulled out as a pure function so the rule can be tested without rendering the
 * whole dashboard (which pulls in stores and a cart and does not settle under
 * jsdom). The rule is the point: a failed load outranks an empty list, because
 * "we could not read this" and "you have none" are different facts and only one
 * of them is true.
 */
export function accountSectionState(
  loading: boolean,
  error: string | undefined,
  itemCount: number,
): "loading" | "error" | "empty" | "ready" {
  if (loading) return "loading";
  if (error) return "error";
  if (itemCount === 0) return "empty";
  return "ready";
}

function SectionLoadError({
  title,
  message,
  onRetry,
}: {
  title: string;
  message: string;
  onRetry: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center py-16 text-center"
    >
      <AlertCircle className="mb-3 h-12 w-12 text-destructive/70" />
      <p className="font-semibold text-foreground">{title}</p>
      <p className="mt-1 mb-4 text-sm text-muted-foreground">{message}</p>
      <Button variant="outline" onClick={onRetry}>
        تلاش مجدد
      </Button>
    </div>
  );
}

export function AccountDashboard({
  initialTab = "profile",
}: {
  initialTab?:
    | "profile"
    | "orders"
    | "addresses"
    | "wallet"
    | "cards"
    | "wishlist"
    | "referrals"
    | "support";
}) {
  const { toast } = useToast();
  const { user, updateProfile } = useAuthStore();
  // useAuth().logout performs the full server logout + cookie/session cleanup
  // (the raw zustand logout leaves a zombie session behind).
  const { logout, fetchCurrentUser } = useAuth();
  const { addItem: addToCart } = useCartStore();

  const [activeTab, setActiveTab] = useState<
    | "profile"
    | "orders"
    | "addresses"
    | "wallet"
    | "cards"
    | "wishlist"
    | "referrals"
    | "support"
  >(initialTab);

  // Profile Form State — start from the real session user; never seed demo
  // values, they would stick for users whose profile fields are still empty.
  const [profileForm, setProfileForm] = useState({
    firstName: user?.firstName ?? "",
    lastName: user?.lastName ?? "",
    // The public nickname. Empty means "show my first + last name", which is
    // what every consumer did before this field existed.
    displayName: user?.display_name ?? "",
    email: user?.email ?? "",
    phone: user?.phone ?? "",
    nationalId: ((user as unknown as Record<string, unknown>)?.national_id as string) || ((user as unknown as Record<string, unknown>)?.nationalId as string) || "",
  });
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // The outstanding email-change proposal, if the server holds one. Fetched on
  // mount so a user who requested a change and then came back is told what is
  // pending rather than being asked to resend.
  const [pendingEmailChange, setPendingEmailChange] = useState<{
    new_email: string;
    expires_at: string;
  } | null>(null);

  // Email verification. `user.is_verified` used to be set by the OTP flow
  // (phone ownership), so it never actually told anyone whether their email
  // was confirmed; a resend is offered whenever the address is unconfirmed.
  const [resendingVerification, setResendingVerification] = useState(false);

  // Custom avatar upload. The profile carried `avatar_url` and the PATCH
  // accepted it, but the account area had no way to get a file in: the media
  // library is admin-gated, so the field was only fillable by pasting a URL.
  const [avatarBusy, setAvatarBusy] = useState(false);

  // True when the form holds an address the account does not have yet. Drives
  // the "this will send a confirmation link" hint, so the change is never a
  // surprise: the field looks editable but silently does something else.
  const emailDiffersFromSaved =
    profileForm.email.trim().toLowerCase() !== (user?.email ?? "").trim().toLowerCase() &&
    profileForm.email.trim() !== "";

  // Password Form State
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Load failures, keyed by section. Five reads on this page used to swallow
  // their error and leave an empty list on screen, so a backend outage read as
  // "you have no orders / no wallet / no tickets" — the customer was told
  // something false about their own account. Each section now records its
  // failure and renders it instead of an empty state.
  const [loadErrors, setLoadErrors] = useState<
    Partial<Record<"orders" | "addresses" | "wallet" | "wishlist" | "tickets", string>>
  >({});

  // Orders State
  const [orders, setOrders] = useState<OrderDisplay[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [selectedOrderForTracking, setSelectedOrderForTracking] = useState<OrderDisplay | null>(null);

  // Addresses State
  const [addresses, setAddresses] = useState<AddressItem[]>([]);
  const [isLoadingAddresses, setIsLoadingAddresses] = useState(false);
  const [isAddressModalOpen, setIsAddressModalOpen] = useState(false);
  const [editingAddress, setEditingAddress] = useState<AddressItem | null>(null);
  const [addressForm, setAddressForm] = useState({
    title: "",
    receiverName: "",
    phone: "",
    province: "تهران",
    city: "تهران",
    postalCode: "",
    fullAddress: "",
    isDefault: false,
  });

  // Wallet State — 0 until the API responds; a fabricated balance misleads
  const [walletBalance, setWalletBalance] = useState<number>(0);
  const [transactions, setTransactions] = useState<WalletTransaction[]>([]);
  const [isLoadingWallet, setIsLoadingWallet] = useState(false);
  const [isDepositModalOpen, setIsDepositModalOpen] = useState(false);
  const [depositAmount, setDepositAmount] = useState<string>("500000");
  const [depositGateway, setDepositGateway] = useState<string>("zarinpal");
  const [isDepositing, setIsDepositing] = useState(false);

  // Wishlist State
  const [wishlist, setWishlist] = useState<WishlistItem[]>([]);
  const [isLoadingWishlist, setIsLoadingWishlist] = useState(false);

  // Support Tickets State
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [isLoadingTickets, setIsLoadingTickets] = useState(false);
  const [isTicketModalOpen, setIsTicketModalOpen] = useState(false);
  const [selectedTicketView, setSelectedTicketView] = useState<SupportTicket | null>(null);
  const [ticketForm, setTicketForm] = useState({
    subject: "",
    department: "سفارش و ارسال",
    priority: "medium" as SupportTicket["priority"],
    message: "",
  });
  const [isCreatingTicket, setIsCreatingTicket] = useState(false);

  // Update profileForm if auth store updates
  useEffect(() => {
    if (user) {
      setProfileForm((prev) => ({
        ...prev,
        firstName: user.firstName ?? "",
        lastName: user.lastName ?? "",
        displayName: user.display_name ?? "",
        email: user.email ?? "",
        phone: user.phone ?? "",
      }));
    }
  }, [user]);

  // Load the outstanding email-change proposal so the form can say what is
  // waiting for confirmation. A failure here is deliberately silent and local:
  // it only affects a hint, and the account screen should not look broken
  // because an optional status call did not answer.
  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<{ pending: boolean; new_email?: string; expires_at?: string }>("/auth/me/email/pending")
      .then((res) => {
        if (cancelled) return;
        const body = res.data;
        if (body?.pending && body.new_email) {
          setPendingEmailChange({ new_email: body.new_email, expires_at: body.expires_at ?? "" });
        } else {
          setPendingEmailChange(null);
        }
      })
      .catch(() => {
        if (!cancelled) setPendingEmailChange(null);
      });
    return () => {
      cancelled = true;
    };
  }, [user?.email]);

  // Redeem a confirmation link. The token arrives in the query string because
  // that is where the emailed link points; it is stripped from the URL
  // afterwards so it does not linger in history, in a shared screen, or in a
  // screenshot. Without this the whole flow would be a backend capability no
  // user could reach.
  const searchParams = useSearchParams();
  const [confirmingEmail, setConfirmingEmail] = useState(false);
  const emailToken = searchParams.get("email_token");

  useEffect(() => {
    if (!emailToken || confirmingEmail) return;
    setConfirmingEmail(true);

    apiClient
      .post("/auth/me/email/confirm", { token: emailToken })
      .then(() => {
        toast({
          title: "ایمیل حساب تأیید شد",
          description: "ایمیل حساب شما با موفقیت تغییر کرد.",
          variant: "success",
        });
        // Re-read the account so the header and the form show the new address.
        void fetchCurrentUser();
      })
      .catch((err: unknown) => {
        toast({
          title: "تأیید ایمیل ناموفق بود",
          description: (err as Error)?.message || "این لینک معتبر نیست یا منقضی شده است.",
          variant: "destructive",
        });
      })
      .finally(() => {
        setConfirmingEmail(false);
        setPendingEmailChange(null);
        // Drop the token from the address bar whether it worked or not.
        window.history.replaceState(null, "", window.location.pathname);
      });
  }, [emailToken, confirmingEmail]);

  /**
   * Ask the server to mail a fresh verification link.
   *
   * The server reports honestly — "already verified", "no address", or a real
   * send failure — so the toast carries its message rather than a fixed
   * success line that would leave a user watching an empty inbox.
   */
  /**
   * Upload a new avatar image.
   *
   * Multipart to /auth/me/avatar; the server stores the file, points the
   * profile at it and returns the updated profile. The auth store is refreshed
   * so every surface showing the avatar (header, sidebar) updates at once
   * rather than waiting for the next /auth/me.
   */
  const uploadAvatar = async (file: File) => {
    setAvatarBusy(true);
    try {
      const form = new FormData();
      form.append("file", file);
      await apiClient.post("/auth/me/avatar", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      await fetchCurrentUser();
      toast({
        title: "تصویر پروفایل به‌روزرسانی شد",
        variant: "success",
      });
    } catch (err) {
      toast({
        title: apiErrorMessage(err, "بارگذاری تصویر پروفایل ناموفق بود."),
        variant: "destructive",
      });
    } finally {
      setAvatarBusy(false);
    }
  };

  const resendVerification = async () => {
    setResendingVerification(true);
    try {
      const res = await authApi.resendEmailVerification();
      toast({
        title: "ارسال پیوند تأیید",
        description: res.message,
        variant: res.message.includes("فرستاده شد") ? "success" : "destructive",
      });
    } catch {
      toast({
        title: "ارسال پیوند تأیید ناموفق بود",
        description: "لطفاً کمی بعد دوباره تلاش کنید.",
        variant: "destructive",
      });
    } finally {
      setResendingVerification(false);
    }
  };

  // Fetch initial data from APIs with fallback
  useEffect(() => {
    // 1. Fetch Orders from GET /orders
    const fetchOrders = async () => {
      try {
        setLoadErrors((prev) => ({ ...prev, orders: undefined }));
        setIsLoadingOrders(true);
        const res = await apiClient.get("/orders");
        if (res.data?.items && Array.isArray(res.data.items)) {
          // Map backend orders schema to our display format
          const mapped: OrderDisplay[] = res.data.items.map((o: Record<string, unknown>) => ({
            id: String(o.id || o.order_number),
            orderNumber: (o.order_number || o.orderNumber || `ORD-${(o.id as string)?.slice?.(0, 6) || "100"}`) as string,
            date: o.created_at ? new Date(o.created_at as string).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            total: Math.trunc(((o.total_price || o.total || o.final_price || 0) as number) / 10),
            status: ((o.status as string)?.toLowerCase() as OrderStatusType) || "pending",
            shippingAddress: ((o.shipping_address as Record<string, unknown>)?.full_address || (o.shippingAddress as Record<string, unknown>)?.address || "تهران") as string,
            trackingCode: (o.tracking_code || o.tracking_number) as string | undefined,
            paymentMethod: (o.payment_method || "پرداخت اینترنتی") as string,
            // The /orders response carries no delivery timestamp, so it is
            // approximated by the last update. Both `delivered` and
            // `completed` are post-delivery states — the backend accepts
            // returns from either (returns_service.validate_eligibility) — so
            // both must get a date, or the RMA UI claims the window expired.
            deliveredAt: (o.delivered_at ||
              o.deliveredAt ||
              (["delivered", "completed"].includes(String(o.status).toLowerCase())
                ? o.updated_at || o.created_at
                : null)) as string | null,
            items: ((o.items || []) as Record<string, unknown>[]).map((it: Record<string, unknown>, idx: number) => ({
              id: String(it.id || idx),
              title: (it.product_title || it.title || it.product_name || "کالای سفارش") as string,
              price: Math.trunc(((it.unit_price || it.price || 0) as number) / 10),
              quantity: (it.quantity || 1) as number,
              image: (it.product_image || it.image) as string | undefined,
            })),
          }));
          // Set unconditionally: an empty real list must clear any stale rows
          setOrders(mapped);
        }
      } catch (err) {
        setLoadErrors((prev) => ({ ...prev, orders: apiErrorMessage(err, "دریافت سفارش‌ها ناموفق بود") }));
      } finally {
        setIsLoadingOrders(false);
      }
    };

    // 2. Fetch Addresses from GET /users/me/addresses
    const fetchAddresses = async () => {
      try {
        setLoadErrors((prev) => ({ ...prev, addresses: undefined }));
        setIsLoadingAddresses(true);
        const res = await apiClient.get("/users/me/addresses");
        if (Array.isArray(res.data) && res.data.length > 0) {
          const mapped: AddressItem[] = res.data.map((a: Record<string, unknown>) => ({
            id: String(a.id),
            title: (a.title || "آدرس") as string,
            receiverName: (a.receiver_name || `${a.first_name || ""} ${a.last_name || ""}`.trim() || "کاربر") as string,
            phone: (a.phone || "") as string,
            province: (a.province || "تهران") as string,
            city: (a.city || "تهران") as string,
            postalCode: (a.postal_code || "") as string,
            fullAddress: (a.full_address || a.address || "") as string,
            isDefault: Boolean(a.is_default),
          }));
          setAddresses(mapped);
        }
      } catch (err) {
        setLoadErrors((prev) => ({ ...prev, addresses: apiErrorMessage(err, "دریافت نشانی‌ها ناموفق بود") }));
      } finally {
        setIsLoadingAddresses(false);
      }
    };

    // 3. Fetch Wallet from GET /wallet and GET /wallet/transactions
    const fetchWallet = async () => {
      try {
        setLoadErrors((prev) => ({ ...prev, wallet: undefined }));
        setIsLoadingWallet(true);
        const [walletRes, txRes] = await Promise.allSettled([
          apiClient.get("/wallet"),
          apiClient.get("/wallet/transactions"),
        ]);
        if (walletRes.status === "fulfilled" && walletRes.value.data) {
          setWalletBalance(Math.trunc(((walletRes.value.data.balance ?? 0) as number) / 10));
        }
        if (txRes.status === "fulfilled" && txRes.value.data?.items) {
          const mappedTx: WalletTransaction[] = txRes.value.data.items.map((t: Record<string, unknown>) => ({
            id: String(t.id),
            type: t.type === "credit" ? "deposit" : t.type === "debit" ? "withdraw" : ((t.type || "deposit") as WalletTransaction["type"]),
            amount: Math.trunc(((t.amount || 0) as number) / 10),
            date: t.created_at ? new Date(t.created_at as string).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            description: (t.description || "تراکنش مالی") as string,
            trackingCode: (t.reference_id || `TRX-${(t.id as string)?.slice?.(0, 7) || "00"}`) as string,
            status: (t.status === "failed" ? "failed" : t.status === "pending" ? "pending" : "success") as WalletTransaction["status"],
          }));
          setTransactions(mappedTx);
        }
      } catch (err) {
        setLoadErrors((prev) => ({ ...prev, wallet: apiErrorMessage(err, "دریافت کیف پول ناموفق بود") }));
      } finally {
        setIsLoadingWallet(false);
      }
    };

    // 4. Fetch Wishlist from GET /wishlist
    const fetchWishlist = async () => {
      try {
        setLoadErrors((prev) => ({ ...prev, wishlist: undefined }));
        setIsLoadingWishlist(true);
        const res = await apiClient.get("/wishlist");
        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: WishlistItem[] = res.data.items.map((it: Record<string, unknown>) => ({
            id: String(it.id),
            productId: String(it.product_id),
            title: (it.product_name || it.title || "محصول ذخیره شده") as string,
            slug: (it.product_slug || "product") as string,
            // product_price arrives in Rial from /wishlist; this view formats
            // Toman (see the order mapping below, which divides the same way).
            price: Math.trunc(Number(it.product_price || it.price || 0) / 10),
            originalPrice: it.product_original_price
              ? Math.trunc(Number(it.product_original_price) / 10)
              : null,
            image: (it.product_image_url || it.image) as string | undefined,
            inStock: (it.product_is_active ?? true) as boolean,
            category: "کالای دیجیتال",
          }));
          setWishlist(mapped);
        }
      } catch (err) {
        setLoadErrors((prev) => ({ ...prev, wishlist: apiErrorMessage(err, "دریافت علاقه‌مندی‌ها ناموفق بود") }));
      } finally {
        setIsLoadingWishlist(false);
      }
    };

    // 5. Fetch Tickets from GET /support or /support/tickets
    const fetchTickets = async () => {
      try {
        setLoadErrors((prev) => ({ ...prev, tickets: undefined }));
        setIsLoadingTickets(true);
        const res = await apiClient.get("/support/tickets");
        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: SupportTicket[] = res.data.items.map((t: Record<string, unknown>) => ({
            id: String(t.id),
            ticketNumber: (t.ticket_number || `TCK-${(t.id as string)?.slice?.(0, 5) || "100"}`) as string,
            subject: (t.subject || "پشتیبانی") as string,
            department: (t.department || "عمومی") as string,
            priority: ((t.priority as string)?.toLowerCase() as SupportTicket["priority"]) || "medium",
            status: ((t.status as string)?.toLowerCase() as SupportTicket["status"]) || "open",
            createdAt: t.created_at ? new Date(t.created_at as string).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            updatedAt: t.updated_at ? new Date(t.updated_at as string).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            lastMessage: (t.body || t.last_message || "") as string,
          }));
          setTickets(mapped);
        }
      } catch (err) {
        setLoadErrors((prev) => ({ ...prev, tickets: apiErrorMessage(err, "دریافت تیکت‌ها ناموفق بود") }));
      } finally {
        setIsLoadingTickets(false);
      }
    };

    fetchOrders();
    fetchAddresses();
    fetchWallet();
    fetchWishlist();
    fetchTickets();
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Actions: Orders & Invoice                                        */
  /* ---------------------------------------------------------------- */

  const handlePrintInvoice = (orderId: string) => {
    // Rely on HttpOnly browser cookies sent with withCredentials
    window.open(`/api/v1/orders/${orderId}/invoice`, "_blank");
  };

  /**
   * The *fiscal* document — the posted invoice with its formal number, hash
   * and frozen archive. Distinct from ``/invoice`` above, which renders a
   * live receipt: the receipt is a courtesy copy, the fiscal document is the
   * one an accountant or a dispute needs. The endpoint falls back to the
   * receipt when no invoice has been posted yet, so the button is always
   * safe to press.
   */
  const handleOpenFiscalDocument = (orderId: string) => {
    window.open(`/api/v1/invoicing/orders/${orderId}/invoice-document`, "_blank");
  };

  /* ---------------------------------------------------------------- */
  /*  Actions: Profile & Password                                      */
  /* ---------------------------------------------------------------- */

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingProfile(true);
    try {
      // The profile endpoint is PATCH /auth/me (the /users/me prefix 404s).
      const res = await apiClient.patch<{
        email_change?: { status: string; message: string; email_sent: boolean };
      }>("/auth/me", {
        first_name: profileForm.firstName,
        last_name: profileForm.lastName,
        // Sent as an explicit value, including empty: clearing the nickname is
        // a real intent ("show my real name again"), and an omitted field
        // would silently keep the old one.
        display_name: profileForm.displayName.trim(),
        email: profileForm.email,
        phone: profileForm.phone,
      });

      // The email is NOT changed by this call. It is proposed, and a
      // confirmation link goes to the new address; the account's address moves
      // only when that link is redeemed. Writing the new value into the local
      // store would show an address the server has not accepted yet, so the
      // form is reverted to what the account actually holds.
      const emailChange = res?.data?.email_change;
      const emailWasChanged = profileForm.email.trim().toLowerCase() !== (user?.email ?? "").trim().toLowerCase();

      if (emailWasChanged) {
        updateProfile({
          firstName: profileForm.firstName,
          lastName: profileForm.lastName,
          fullName: `${profileForm.firstName} ${profileForm.lastName}`.trim(),
          email: user?.email ?? "",
          phone: profileForm.phone,
        });
        setProfileForm((f) => ({ ...f, email: user?.email ?? "" }));
      } else {
        updateProfile({
          firstName: profileForm.firstName,
          lastName: profileForm.lastName,
          fullName: `${profileForm.firstName} ${profileForm.lastName}`.trim(),
          email: profileForm.email,
          phone: profileForm.phone,
        });
      }

      if (emailChange) {
        // Two distinct outcomes, and the difference matters: with SMTP down the
        // request is recorded but the link was never sent, so "check your inbox"
        // would be a promise nobody kept.
        toast({
          title: emailChange.email_sent ? "درخواست تغییر ایمیل ثبت شد" : "درخواست ثبت شد، ایمیل ارسال نشد",
          description: emailChange.email_sent
            ? "لینک تأیید به ایمیل جدید فرستاده شد. تا زمانی که روی آن کلیک نکنید، ایمیل حساب شما تغییر نمی‌کند."
            : "ارسال ایمیل با خطا مواجه شد. لطفاً کمی بعد دوباره تلاش کنید.",
          variant: emailChange.email_sent ? "success" : "destructive",
        });
        // Reflect the proposal in the form immediately. Re-fetching would be
        // rounder but slower, and this is the moment the user is looking at the
        // field they just typed into.
        setPendingEmailChange(
          emailChange.status === "unchanged"
            ? null
            : { new_email: profileForm.email.trim().toLowerCase(), expires_at: "" },
        );
        return;
      }

      toast({
        title: "اطلاعات حساب بروزرسانی شد",
        description: "مشخصات کاربری شما با موفقیت ذخیره گردید.",
        variant: "success",
      });
    } catch (err: unknown) {
      toast({
        title: "خطا در بروزرسانی",
        description: (err as Error)?.message || "امکان ذخیره اطلاعات وجود نداشت.",
        variant: "destructive",
      });
    } finally {
      setIsSavingProfile(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!passwordForm.currentPassword) {
      toast({
        title: "رمز عبور فعلی الزامی است",
        variant: "destructive",
      });
      return;
    }
    if (passwordForm.newPassword.length < 8) {
      toast({
        title: "رمز عبور جدید باید حداقل ۸ کاراکتر باشد",
        description: "برای امنیت بیشتر، حداقل ۸ کاراکتر شامل یک حرف انگلیسی و یک عدد وارد کنید.",
        variant: "destructive",
      });
      return;
    }
    if (!/[A-Za-z]/.test(passwordForm.newPassword) || !/\d/.test(passwordForm.newPassword)) {
      toast({
        title: "رمز عبور جدید ضعیف است",
        description: "رمز عبور باید حداقل شامل یک حرف انگلیسی و یک عدد باشد.",
        variant: "destructive",
      });
      return;
    }
    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      toast({
        title: "تکرار رمز عبور یکسان نیست",
        description: "رمز عبور جدید با تکرار آن مطابقت ندارد.",
        variant: "destructive",
      });
      return;
    }

    setIsChangingPassword(true);
    try {
      await apiClient.post("/auth/change-password", {
        old_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      });

      setPasswordForm({
        currentPassword: "",
        newPassword: "",
        confirmPassword: "",
      });

      toast({
        title: "رمز عبور تغییر یافت",
        description: "کلمه عبور حساب کاربری شما با موفقیت به روز شد.",
        variant: "success",
      });
    } catch (err: unknown) {
      toast({
        title: "خطا در تغییر رمز عبور",
        description: (err as Error)?.message || "تغییر رمز عبور با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setIsChangingPassword(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Actions: Addresses                                               */
  /* ---------------------------------------------------------------- */

  const handleOpenAddAddress = () => {
    setEditingAddress(null);
    setAddressForm({
      title: "خانه",
      receiverName: `${profileForm.firstName} ${profileForm.lastName}`.trim(),
      phone: profileForm.phone,
      province: "تهران",
      city: "تهران",
      postalCode: "",
      fullAddress: "",
      isDefault: addresses.length === 0,
    });
    setIsAddressModalOpen(true);
  };

  const handleOpenEditAddress = (addr: AddressItem) => {
    setEditingAddress(addr);
    setAddressForm({
      title: addr.title,
      receiverName: addr.receiverName,
      phone: addr.phone,
      province: addr.province,
      city: addr.city,
      postalCode: addr.postalCode,
      fullAddress: addr.fullAddress,
      isDefault: addr.isDefault,
    });
    setIsAddressModalOpen(true);
  };

  const handleSaveAddress = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!addressForm.fullAddress.trim()) {
      toast({ title: "نشانی کامل الزامی است", variant: "destructive" });
      return;
    }
    if (!addressForm.postalCode.trim() || addressForm.postalCode.replace(/\D/g, "").length !== 10) {
      toast({ title: "کد پستی باید ۱۰ رقم باشد", variant: "destructive" });
      return;
    }

    try {
      if (editingAddress) {
        // Update — receiver_name/phone must be sent, otherwise edits silently
        // revert on reload.
        await apiClient.patch(`/users/me/addresses/${editingAddress.id}`, {
          title: addressForm.title,
          receiver_name: addressForm.receiverName,
          phone: addressForm.phone,
          province: addressForm.province,
          city: addressForm.city,
          postal_code: addressForm.postalCode,
          full_address: addressForm.fullAddress,
          is_default: addressForm.isDefault,
        });

        setAddresses((prev) =>
          prev.map((a) => {
            if (a.id === editingAddress.id) {
              return {
                ...a,
                title: addressForm.title,
                receiverName: addressForm.receiverName,
                phone: addressForm.phone,
                province: addressForm.province,
                city: addressForm.city,
                postalCode: addressForm.postalCode,
                fullAddress: addressForm.fullAddress,
                isDefault: addressForm.isDefault,
              };
            }
            return addressForm.isDefault ? { ...a, isDefault: false } : a;
          })
        );
        toast({ title: "آدرس ویرایش شد", variant: "success" });
      } else {
        // Create — use the server-returned ID so subsequent edit/delete
        // operations target a real record.
        const created = await apiClient.post<{ id?: string }>("/users/me/addresses", {
          title: addressForm.title,
          receiver_name: addressForm.receiverName,
          phone: addressForm.phone,
          province: addressForm.province,
          city: addressForm.city,
          postal_code: addressForm.postalCode,
          full_address: addressForm.fullAddress,
          is_default: addressForm.isDefault,
        });

        const newId = created.data?.id || `addr-${Date.now()}`;

        const newAddrItem: AddressItem = {
          id: newId,
          title: addressForm.title,
          receiverName: addressForm.receiverName,
          phone: addressForm.phone,
          province: addressForm.province,
          city: addressForm.city,
          postalCode: addressForm.postalCode,
          fullAddress: addressForm.fullAddress,
          isDefault: addressForm.isDefault,
        };

        setAddresses((prev) => [
          ...(addressForm.isDefault ? prev.map((a) => ({ ...a, isDefault: false })) : prev),
          newAddrItem,
        ]);
        toast({ title: "آدرس جدید افزوده شد", variant: "success" });
      }
      setIsAddressModalOpen(false);
    } catch (err: unknown) {
      toast({
        title: "خطا در ثبت آدرس",
        description: (err as Error)?.message || "عملیات با خطا مواجه شد",
        variant: "destructive",
      });
    }
  };

  const handleSetDefaultAddress = async (id: string) => {
    try {
      await apiClient.patch(`/users/me/addresses/${id}`, { is_default: true }).catch(() => null);
      setAddresses((prev) =>
        prev.map((a) => ({
          ...a,
          isDefault: a.id === id,
        }))
      );
      toast({ title: "آدرس پیش‌فرض تغییر یافت", variant: "success" });
    } catch (err) {
      // Ignored
    }
  };

  const handleDeleteAddress = async (id: string) => {
    try {
      await apiClient.delete(`/users/me/addresses/${id}`).catch(() => null);
      setAddresses((prev) => prev.filter((a) => a.id !== id));
      toast({ title: "آدرس با موفقیت حذف شد", variant: "default" });
    } catch (err) {
      // Ignored
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Actions: Wallet Deposit                                          */
  /* ---------------------------------------------------------------- */

  const handleDepositSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const numericAmount = parseInt(depositAmount.replace(/\D/g, ""), 10);
    if (!numericAmount || numericAmount < 10_000) {
      toast({
        title: "مبلغ نامعتبر",
        description: "حداقل مبلغ افزایش موجودی ۱۰,۰۰۰ تومان می‌باشد.",
        variant: "destructive",
      });
      return;
    }

    setIsDepositing(true);
    try {
      // Gateway-backed top-up: the wallet is credited server-side only
      // after the gateway verifies the payment; here we just redirect.
      const topupRes = await apiClient.post<{ gateway_url?: string | null }>(
        "/wallet/topup",
        {
          provider: depositGateway,
          amount: numericAmount,
        },
      );

      if (topupRes.data?.gateway_url) {
        // Redirecting to the gateway: the wallet is credited server-side
        // only after the gateway verifies the payment — never claim
        // success before that.
        window.location.href = topupRes.data.gateway_url;
        return;
      }

      // No gateway URL means the payment was never started: surface an
      // error instead of a fabricated success message.
      toast({
        title: "درگاه پرداخت در دسترس نیست",
        description: "لطفاً درگاه دیگری انتخاب کنید یا بعداً دوباره تلاش کنید.",
        variant: "destructive",
      });
    } catch (err: unknown) {
      toast({
        title: "خطا در افزایش موجودی",
        description: (err as { message?: string })?.message || "ارتباط با درگاه برقرار نشد. لطفاً دوباره تلاش کنید.",
        variant: "destructive",
      });
    } finally {
      setIsDepositing(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Actions: Wishlist                                                */
  /* ---------------------------------------------------------------- */

  const handleRemoveFromWishlist = async (productId: string) => {
    try {
      await apiClient.delete(`/wishlist/items/${productId}`).catch(() => null);
      setWishlist((prev) => prev.filter((item) => item.productId !== productId));
      toast({ title: "محصول از علاقه‌مندی‌ها حذف شد", variant: "default" });
    } catch (err) {
      // Ignored
    }
  };

  const handleMoveToCart = async (item: WishlistItem) => {
    try {
      await addToCart({
        productId: item.productId,
        title: item.title,
        price: item.price,
        originalPrice: item.originalPrice || undefined,
        slug: item.slug,
        image: item.image,
        quantity: 1,
      });
    } catch (err: unknown) {
      // Keep the wishlist entry when the cart add fails (QA B19) — moving
      // items to a cart the server rejected lost them entirely.
      toast({
        title: "انتقال به سبد ناموفق بود",
        description: (err as { message?: string })?.message,
        variant: "destructive",
      });
      return;
    }
    handleRemoveFromWishlist(item.productId);
    toast({
      title: "به سبد خرید منتقل شد",
      description: item.title,
      variant: "success",
    });
  };

  /* ---------------------------------------------------------------- */
  /*  Actions: Support Tickets                                         */
  /* ---------------------------------------------------------------- */

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ticketForm.subject.trim() || !ticketForm.message.trim()) {
      toast({
        title: "تکمیل فیلدهای موضوع و متن پیام الزامی است",
        variant: "destructive",
      });
      return;
    }

    setIsCreatingTicket(true);
    try {
      const ticketRes = await apiClient.post<{
        id?: string;
        ticket_number?: string;
      }>("/support/tickets", {
        subject: ticketForm.subject,
        department: ticketForm.department,
        priority: ticketForm.priority,
        body: ticketForm.message,
      });

      const newTicket: SupportTicket = {
        id: ticketRes.data?.id || `tck-${Date.now()}`,
        ticketNumber: ticketRes.data?.ticket_number || "—",
        subject: ticketForm.subject,
        department: ticketForm.department,
        priority: ticketForm.priority,
        status: "open",
        createdAt: new Date().toLocaleDateString("fa-IR"),
        updatedAt: new Date().toLocaleDateString("fa-IR"),
        lastMessage: ticketForm.message,
      };

      setTickets((prev) => [newTicket, ...prev]);
      setIsTicketModalOpen(false);
      setTicketForm({
        subject: "",
        department: "سفارش و ارسال",
        priority: "medium",
        message: "",
      });

      toast({
        title: "تیکت جدید با موفقیت ثبت شد",
        description: "کارشناسان پشتیبانی به زودی پاسخگوی شما خواهند بود.",
        variant: "success",
      });
    } catch (err: unknown) {
      toast({
        title: "خطا در ارسال تیکت",
        description: (err as Error)?.message || "ارسال تیکت انجام نشد.",
        variant: "destructive",
      });
    } finally {
      setIsCreatingTicket(false);
    }
  };

  /* ---------------------------------------------------------------- */
  /*  Navigation items definition                                      */
  /* ---------------------------------------------------------------- */

  interface NavItem {
    key:
      | "profile"
      | "orders"
      | "addresses"
      | "wallet"
      | "cards"
      | "wishlist"
      | "referrals"
      | "support";
    label: string;
    icon: React.ComponentType<{ className?: string }>;
    badge?: number;
    highlight?: string;
  }

  const navItems: NavItem[] = [
    { key: "profile", label: "اطلاعات حساب", icon: User },
    { key: "orders", label: "سفارش‌ها", icon: Package, badge: orders.length },
    { key: "addresses", label: "آدرس‌ها", icon: MapPin, badge: addresses.length },
    { key: "wallet", label: "کیف پول", icon: WalletIcon, highlight: formatPrice(walletBalance) },
    { key: "cards", label: "کارت‌ها و اقساط", icon: CreditCard },
    { key: "referrals", label: "دعوت دوستان", icon: Users },
    { key: "wishlist", label: "علاقه‌مندی‌ها", icon: Heart, badge: wishlist.length },
    { key: "support", label: "تیکت‌های پشتیبانی", icon: Headphones, badge: tickets.length },
  ];

  // One state per section, all derived from the same rule (see
  // accountSectionState). The JSX branches on these rather than re-deriving
  // the order inline, so a section cannot drift into showing "empty" for a
  // failed read.
  const ordersState = accountSectionState(
    isLoadingOrders,
    loadErrors.orders,
    orders.length,
  );
  const addressesState = accountSectionState(
    isLoadingAddresses,
    loadErrors.addresses,
    addresses.length,
  );
  const walletState = accountSectionState(
    isLoadingWallet,
    loadErrors.wallet,
    transactions.length,
  );
  const wishlistState = accountSectionState(
    isLoadingWishlist,
    loadErrors.wishlist,
    wishlist.length,
  );
  const ticketsState = accountSectionState(
    isLoadingTickets,
    loadErrors.tickets,
    tickets.length,
  );

  return (
    <div className="space-y-6 py-6" dir="rtl">
      {/* Header breadcrumb & greeting */}
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">حساب کاربری</h1>
          <p className="text-sm text-muted-foreground">
            مدیریت مشخصات فردی، سفارش‌ها، آدرس‌ها و کیف پول
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-1.5 text-sm">
            <span className="text-xs text-muted-foreground">موجودی کیف پول:</span>
            <span className="font-bold text-primary">{formatPrice(walletBalance)}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-4">
        {/* ============================================================== */}
        {/* Sidebar Nav (Desktop & Mobile Tabs)                             */}
        {/* ============================================================== */}
        <aside className="lg:col-span-1">
          <Card className="p-4">
            {/* User Profile Card Header */}
            <div className="mb-4 flex items-center gap-3 border-b border-border pb-4">
              {/* The avatar is a label wrapping a file input: clicking the
                  image opens the picker, which is what a person expects, and
                  the input stays keyboard-reachable because it is the label's
                  control rather than a hidden div. */}
              <label
                className="relative flex h-14 w-14 shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-full bg-primary/10 font-bold text-lg text-primary"
                title="تغییر تصویر پروفایل"
              >
                {user?.avatar_url ? (
                  // eslint-disable-next-line @next/next/no-img-element -- user-uploaded media, not a build-time asset
                  <img
                    src={user.avatar_url}
                    alt="تصویر پروفایل"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  profileForm.firstName?.charAt(0) || "ک"
                )}
                {avatarBusy && (
                  <span className="absolute inset-0 flex items-center justify-center bg-background/70">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </span>
                )}
                <input
                  type="file"
                  accept="image/*"
                  className="sr-only"
                  disabled={avatarBusy}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    // Reset first so picking the same file twice fires again.
                    e.target.value = "";
                    if (file) void uploadAvatar(file);
                  }}
                />
              </label>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-foreground">
                  {profileForm.firstName} {profileForm.lastName}
                </p>
                <p className="truncate text-xs text-muted-foreground font-mono" dir="ltr">
                  {maskPhoneNumber(profileForm.phone)}
                </p>
              </div>
            </div>

            {/* Nav links */}
            <nav className="space-y-1">
              {navItems.map((item) => {
                const IconComponent = item.icon;
                const isActive = activeTab === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setActiveTab(item.key)}
                    className={`flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-primary text-primary-foreground shadow-sm"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <IconComponent className="h-4 w-4 shrink-0" />
                      <span>{item.label}</span>
                    </div>
                    {item.badge !== undefined && (
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-mono ${
                          isActive
                            ? "bg-primary-foreground/20 text-primary-foreground"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {toPersianDigits(item.badge)}
                      </span>
                    )}
                  </button>
                );
              })}

              <Separator className="my-3" />
              <Link
                href="/account/subscriptions"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Repeat className="h-4 w-4 shrink-0" />
                <span>اشتراک‌های من</span>
              </Link>

              <Link
                href="/account/notifications"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Bell className="h-4 w-4 shrink-0" />
                <span>تنظیمات اعلان‌ها</span>
              </Link>

              <Link
                href="/account/tickets"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Headphones className="h-4 w-4 shrink-0" />
                <span>مرکز تیکت‌ها و گفتگو</span>
              </Link>

              <Link
                href="/account/digital-codes"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Gift className="h-4 w-4 shrink-0" />
                <span>کدهای دیجیتال من</span>
              </Link>

              {/* Route-based pages. Without these entries the cashback history
                  and the seller dashboard existed but could only be reached by
                  typing the URL — the same defect the admin nav guard exists to
                  catch. */}
              <Link
                href="/account/cashback"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Coins className="h-4 w-4 shrink-0" />
                <span>کش‌بک من</span>
              </Link>

              <Link
                href="/account/seller"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <Store className="h-4 w-4 shrink-0" />
                <span>فروشندگی در بازارگاه</span>
              </Link>

              {/* Data-subject rights live on their own page rather than as a
                  dashboard tab: filing an erasure takes a password and a
                  confirmation, which is not a side-panel action. */}
              <Link
                href="/account/privacy"
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              >
                <ShieldCheck className="h-4 w-4 shrink-0" />
                <span>حریم خصوصی و داده‌های من</span>
              </Link>

              <button
                type="button"
                onClick={() => {
                  // logout() clears the session and hard-navigates home; a
                  // toast would never be seen on a page that unloads.
                  void logout();
                }}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-destructive transition-colors hover:bg-destructive/10"
              >
                <LogOut className="h-4 w-4" />
                <span>خروج از حساب</span>
              </button>
            </nav>
          </Card>
        </aside>

        {/* ============================================================== */}
        {/* Main Content Area                                              */}
        {/* ============================================================== */}
        <div className="lg:col-span-3 space-y-6">

          {/* ------------------------------------------------------------ */}
          {/* TAB 1: Profile Info & Change Password                        */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "profile" && (
            <div className="space-y-6">
              <Card className="p-6">
                <div className="mb-6 flex items-center justify-between border-b pb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">اطلاعات فردی</h2>
                    <p className="text-xs text-muted-foreground">
                      اطلاعات هویتی و راه‌های ارتباطی خود را ویرایش کنید.
                    </p>
                  </div>
                  <Badge variant="outline" className="gap-1">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-500" />
                    حساب تایید شده
                  </Badge>
                </div>

                <form onSubmit={handleSaveProfile} className="space-y-4">
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="firstName">نام</Label>
                      <Input
                        id="firstName"
                        value={profileForm.firstName}
                        onChange={(e) =>
                          setProfileForm({ ...profileForm, firstName: e.target.value })
                        }
                        placeholder="نام خود را وارد کنید"
                        required
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="lastName">نام خانوادگی</Label>
                      <Input
                        id="lastName"
                        value={profileForm.lastName}
                        onChange={(e) =>
                          setProfileForm({ ...profileForm, lastName: e.target.value })
                        }
                        placeholder="نام خانوادگی خود را وارد کنید"
                        required
                      />
                    </div>
                  </div>

                  {/* The public nickname. Kept separate from the legal name
                      because they differ: an author under a pen name must not
                      have their real name published, and a customer may want
                      "آرش" on reviews while the account holds a full legal
                      name. Empty falls back to first + last. */}
                  <div className="space-y-1.5">
                    <Label htmlFor="displayName">
                      نام نمایشی{" "}
                      <span className="text-muted-foreground">(اختیاری)</span>
                    </Label>
                    <Input
                      id="displayName"
                      value={profileForm.displayName}
                      onChange={(e) =>
                        setProfileForm({ ...profileForm, displayName: e.target.value })
                      }
                      placeholder="نامی که به‌جای نام واقعی نمایش داده می‌شود"
                      maxLength={100}
                    />
                    <p className="text-[11px] text-muted-foreground">
                      اگر خالی بماند، نام و نام خانوادگی شما نمایش داده می‌شود.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="phone">شماره موبایل</Label>
                        {profileForm.phone && (
                          <span className="text-[11px] font-mono text-muted-foreground" dir="ltr">
                            نمایش امن: {maskPhoneNumber(profileForm.phone)}
                          </span>
                        )}
                      </div>
                      <div className="relative">
                        <Input
                          id="phone"
                          value={profileForm.phone}
                          onChange={(e) =>
                            setProfileForm({ ...profileForm, phone: e.target.value })
                          }
                          dir="ltr"
                          className="pe-9 text-left font-mono"
                          required
                        />
                        <Phone className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      </div>
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <Label htmlFor="nationalId">کد ملی</Label>
                        {profileForm.nationalId && (
                          <span className="text-[11px] font-mono text-muted-foreground" dir="ltr">
                            نمایش امن: {maskNationalId(profileForm.nationalId)}
                          </span>
                        )}
                      </div>
                      <div className="relative">
                        <Input
                          id="nationalId"
                          value={profileForm.nationalId}
                          onChange={(e) =>
                            setProfileForm({ ...profileForm, nationalId: e.target.value })
                          }
                          dir="ltr"
                          className="pe-9 text-left font-mono"
                          placeholder="مثلاً: 0012345011"
                          maxLength={10}
                        />
                        <ShieldCheck className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      </div>
                    </div>

                    <div className="space-y-1.5 sm:col-span-2">
                      <Label htmlFor="email">پست الکترونیک (ایمیل)</Label>
                      <div className="relative">
                        <Input
                          id="email"
                          type="email"
                          value={profileForm.email}
                          onChange={(e) =>
                            setProfileForm({ ...profileForm, email: e.target.value })
                          }
                          dir="ltr"
                          className="pe-9 text-left font-mono"
                          placeholder="name@example.com"
                        />
                        <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      </div>
                      {pendingEmailChange ? (
                        <p className="text-xs text-amber-600 dark:text-amber-400">
                          درخواست تغییر به <span dir="ltr">{pendingEmailChange.new_email}</span> ثبت شده و
                          منتظر تأیید است. ایمیل فعلی حساب شما همچنان{" "}
                          <span dir="ltr">{user?.email || "—"}</span> است.
                        </p>
                      ) : emailDiffersFromSaved ? (
                        <p className="text-xs text-muted-foreground">
                          با ذخیره، لینک تأیید به این آدرس فرستاده می‌شود. ایمیل حساب شما تا پس از
                          کلیک روی لینک تغییر نمی‌کند.
                        </p>
                      ) : null}
                      {/* Verification status. A saved but unconfirmed address
                          is where password resets go, so the user should see
                          that state and be able to fix it without support. */}
                      {!pendingEmailChange && !emailDiffersFromSaved && user?.email ? (
                        user.is_verified ? (
                          <p className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            ایمیل تأیید شده است.
                          </p>
                        ) : (
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-xs text-amber-600 dark:text-amber-400">
                              این ایمیل هنوز تأیید نشده است.
                            </p>
                            <Button
                              type="button"
                              variant="link"
                              size="sm"
                              className="h-auto p-0 text-xs"
                              disabled={resendingVerification}
                              onClick={() => void resendVerification()}
                            >
                              {resendingVerification
                                ? "در حال ارسال…"
                                : "ارسال پیوند تأیید"}
                            </Button>
                          </div>
                        )
                      ) : null}
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button type="submit" disabled={isSavingProfile}>
                      {isSavingProfile ? "در حال ذخیره..." : "ذخیره اطلاعات کاربری"}
                    </Button>
                  </div>
                </form>
              </Card>

              {/* Password Change Card */}
              <Card className="p-6">
                <div className="mb-6 flex items-center justify-between border-b pb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">تغییر کلمه عبور</h2>
                    <p className="text-xs text-muted-foreground">
                      جهت افزایش امنیت حساب خود، کلمه عبور پیچیده انتخاب نمایید.
                    </p>
                  </div>
                  <Lock className="h-5 w-5 text-muted-foreground" />
                </div>

                <form onSubmit={handleChangePassword} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label htmlFor="currentPassword">رمز عبور فعلی</Label>
                    <Input
                      id="currentPassword"
                      type="password"
                      value={passwordForm.currentPassword}
                      onChange={(e) =>
                        setPasswordForm({ ...passwordForm, currentPassword: e.target.value })
                      }
                      dir="ltr"
                      placeholder="••••••••"
                      required
                    />
                  </div>

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="newPassword">رمز عبور جدید</Label>
                      <Input
                        id="newPassword"
                        type="password"
                        value={passwordForm.newPassword}
                        onChange={(e) =>
                          setPasswordForm({ ...passwordForm, newPassword: e.target.value })
                        }
                        dir="ltr"
                        placeholder="حداقل ۶ کاراکتر"
                        required
                      />
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="confirmPassword">تکرار رمز عبور جدید</Label>
                      <Input
                        id="confirmPassword"
                        type="password"
                        value={passwordForm.confirmPassword}
                        onChange={(e) =>
                          setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })
                        }
                        dir="ltr"
                        placeholder="تکرار رمز عبور جدید"
                        required
                      />
                    </div>
                  </div>

                  <div className="flex justify-end pt-2">
                    <Button type="submit" variant="outline" disabled={isChangingPassword}>
                      {isChangingPassword ? "در حال بروزرسانی..." : "تغییر کلمه عبور"}
                    </Button>
                  </div>
                </form>
              </Card>

              {/* TOTP MFA management (server-backed) */}
              <div className="mt-6">
                <MfaSettingsCard
                  enabled={!!user?.totp_enabled}
                  onChanged={() => window.location.reload()}
                />
              </div>

              {/* Passkeys: passwordless sign-in with a device credential. The
                  hook and endpoints were both stubs before this. */}
              <div className="mt-6">
                <PasskeyCard />
              </div>

              {/* Application passwords: API credentials for a phone app or
                  script, revocable one at a time instead of the account
                  password itself. */}
              <div className="mt-6">
                <ApplicationPasswordsCard />
              </div>

              {/* Live sessions: which devices are signed in, and a way to cut
                  one off. The endpoints existed with no caller, so someone
                  with access to the account could be spotted but not removed
                  without signing out of every device including this one. */}
              <div className="mt-6">
                <SessionsCard />
              </div>
            </div>
          )}

          {/* ------------------------------------------------------------ */}
          {/* TAB 2: Orders & Tracking Timeline Modal                      */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "orders" && (
            <Card className="p-6">
              <div className="mb-6 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">تاریخچه سفارش‌ها</h2>
                  <p className="text-xs text-muted-foreground">
                    لیست کامل سفارش‌ها و وضعیت ارسال هر بسته
                  </p>
                </div>
                <Badge variant="secondary" className="w-fit">
                  {isLoadingOrders ? "در حال دریافت..." : `${toPersianDigits(orders.length)} سفارش ثبت شده`}
                </Badge>
              </div>

              {ordersState === "loading" ? (
                <OrderHistorySkeleton count={3} />
              ) : ordersState === "error" ? (
                // A failed read must not render as "you have no orders" — that
                // tells the customer something false about their own account.
                <div
                  role="alert"
                  className="flex flex-col items-center justify-center py-16 text-center"
                >
                  <AlertCircle className="h-12 w-12 text-destructive/70 mb-3" />
                  <p className="font-semibold text-foreground">
                    دریافت سفارش‌ها ناموفق بود
                  </p>
                  <p className="text-sm text-muted-foreground mt-1 mb-4">
                    {loadErrors.orders}
                  </p>
                  <Button variant="outline" onClick={() => window.location.reload()}>
                    تلاش مجدد
                  </Button>
                </div>
              ) : ordersState === "empty" ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Package className="h-12 w-12 text-muted-foreground/60 mb-3" />
                  <p className="font-semibold text-foreground">هیچ سفارشی ثبت نشده است</p>
                  <p className="text-sm text-muted-foreground mt-1 mb-4">
                    می‌توانید از بخش فروشگاه محصولات مورد نظر خود را خریداری فرمایید.
                  </p>
                  <Link href="/products">
                    <Button>مشاهده فروشگاه</Button>
                  </Link>
                </div>
              ) : (
                <div className="space-y-4">
                  {orders.map((order) => {
                    const statusConfig = ORDER_STATUS_CONFIG[order.status] || {
                      label: order.status,
                      badgeVariant: "secondary",
                    };
                    return (
                      <div
                        key={order.id}
                        className="rounded-xl border border-border bg-card p-4 transition-all hover:shadow-sm"
                      >
                        {/* Order Header */}
                        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                              <Package className="h-5 w-5" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-bold text-foreground font-mono">
                                  {order.orderNumber}
                                </span>
                                <Badge variant={statusConfig.badgeVariant}>
                                  {statusConfig.label}
                                </Badge>
                              </div>
                              <span className="text-xs text-muted-foreground">
                                ثبت شده در تاریخ {order.date}
                              </span>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-3">
                            <div className="text-left sm:text-right">
                              <span className="text-xs text-muted-foreground block">مبلغ کل:</span>
                              <span className="font-bold text-primary">
                                {formatPrice(order.total)}
                              </span>
                            </div>
                            <div className="flex items-center gap-2">
                              {order.status === "delivered" && (() => {
                                const eligibility = checkReturnEligibility("delivered", order.deliveredAt);
                                if (eligibility.isEligible) {
                                  return (
                                    <Link href={`/returns/request?orderId=${order.id}`}>
                                      <Button
                                        variant="outline"
                                        size="sm"
                                        className="gap-1.5 text-xs text-amber-600 border-amber-500/30 hover:bg-amber-500/10"
                                        title={`ثبت مرجوعی (${toPersianDigits(eligibility.daysRemaining)} روز از مهلت قانونی باقی مانده است)`}
                                      >
                                        <RotateCcw className="h-4 w-4" />
                                        ثبت مرجوعی
                                      </Button>
                                    </Link>
                                  );
                                }
                                return (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    disabled
                                    className="gap-1.5 text-xs text-muted-foreground opacity-60 cursor-not-allowed"
                                    title="مهلت ۷ روزه مرجوعی منقضی شده است"
                                  >
                                    <RotateCcw className="h-4 w-4" />
                                    مهلت ۷ روزه منقضی شده
                                  </Button>
                                );
                              })()}
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handlePrintInvoice(order.id)}
                                className="gap-1.5 text-xs"
                                title="رسید سفارش — نسخه قابل چاپ"
                              >
                                <Printer className="h-4 w-4" />
                                رسید سفارش
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleOpenFiscalDocument(order.id)}
                                className="gap-1.5 text-xs text-primary border-primary/20 hover:bg-primary/5"
                                title="سند مالی رسمی با شماره و اثر انگشت دیجیتال"
                              >
                                <FileText className="h-4 w-4" />
                                سند مالی رسمی
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setSelectedOrderForTracking(order)}
                                className="gap-1.5 text-xs"
                              >
                                <Truck className="h-4 w-4" />
                                رهگیری سفارش
                              </Button>
                            </div>
                          </div>
                        </div>

                        {/* Order Items List */}
                        <div className="mt-3 divide-y divide-border/40">
                          {order.items.map((item) => (
                            <div
                              key={item.id}
                              className="flex items-center justify-between py-2 text-sm"
                            >
                              <div className="flex items-center gap-3 min-w-0">
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground text-xs font-semibold">
                                  <ShoppingBag className="h-5 w-5" />
                                </div>
                                <span className="truncate font-medium text-foreground">
                                  {item.title}
                                </span>
                              </div>
                              <div className="flex items-center gap-4 shrink-0 text-xs">
                                <span className="text-muted-foreground font-mono">
                                  {toPersianDigits(item.quantity)} عدد
                                </span>
                                <span className="font-semibold text-foreground">
                                  {formatPrice(item.price)}
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          )}

          {/* ------------------------------------------------------------ */}
          {/* TAB 3: Addresses Tab                                         */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "addresses" && (
            <Card className="p-6">
              <div className="mb-6 flex items-center justify-between border-b pb-4">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">دفترچه آدرس‌ها</h2>
                  <p className="text-xs text-muted-foreground">
                    {isLoadingAddresses
                      ? "در حال دریافت اطلاعات آدرس‌ها..."
                      : "آدرس‌های ارسال مرسولات پستی خود را در این بخش مدیریت کنید."}
                  </p>
                </div>
                <Button onClick={handleOpenAddAddress} size="sm" className="gap-1.5">
                  <Plus className="h-4 w-4" />
                  افزودن آدرس جدید
                </Button>
              </div>

              {addressesState === "error" ? (
                <SectionLoadError
                  title="دریافت نشانی‌ها ناموفق بود"
                  message={loadErrors.addresses ?? "تلاش دوباره ناموفق بود."}
                  onRetry={() => window.location.reload()}
                />
              ) : addressesState === "empty" ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <MapPin className="h-12 w-12 text-muted-foreground/60 mb-3" />
                  <p className="font-semibold text-foreground">آدرسی ثبت نکرده‌اید</p>
                  <p className="text-sm text-muted-foreground mt-1 mb-4">
                    برای ارسال سفارشات، حداقل یک آدرس دریافت کالا ثبت کنید.
                  </p>
                  <Button onClick={handleOpenAddAddress}>افزودن آدرس اول</Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {addresses.map((addr) => (
                    <div
                      key={addr.id}
                      className={`relative flex flex-col justify-between rounded-xl border p-4 transition-all ${
                        addr.isDefault
                          ? "border-primary/60 bg-primary/[0.02] shadow-sm"
                          : "border-border bg-card hover:border-border/80"
                      }`}
                    >
                      <div>
                        {/* Address Title & Default Badge */}
                        <div className="flex items-center justify-between mb-3">
                          <div className="flex items-center gap-2">
                            <MapPin className="h-4 w-4 text-primary shrink-0" />
                            <span className="font-bold text-foreground">{addr.title}</span>
                            {addr.isDefault && (
                              <Badge variant="success" className="text-[11px] py-0 px-2">
                                پیش‌فرض
                              </Badge>
                            )}
                          </div>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-muted-foreground hover:text-foreground"
                              onClick={() => handleOpenEditAddress(addr)}
                            >
                              <Edit3 className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="h-8 w-8 text-destructive hover:bg-destructive/10"
                              onClick={() => handleDeleteAddress(addr.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>

                        {/* Full Address */}
                        <p className="text-sm text-foreground/90 leading-relaxed mb-3">
                          {addr.province}، {addr.city}، {addr.fullAddress}
                        </p>

                        <div className="space-y-1 text-xs text-muted-foreground">
                          <p>
                            گیرنده:{" "}
                            <span className="text-foreground font-medium">{addr.receiverName}</span>
                          </p>
                          <p>
                            شماره تماس:{" "}
                            <span className="font-mono text-foreground font-medium" dir="ltr">
                              {addr.phone}
                            </span>
                          </p>
                          <p>
                            کد پستی:{" "}
                            <span className="font-mono text-foreground font-medium" dir="ltr">
                              {toPersianDigits(addr.postalCode)}
                            </span>
                          </p>
                        </div>
                      </div>

                      {/* Set as default button */}
                      {!addr.isDefault && (
                        <div className="mt-4 pt-3 border-t border-border/60 flex justify-end">
                          <Button
                            variant="link"
                            size="sm"
                            className="h-auto p-0 text-xs text-primary"
                            onClick={() => handleSetDefaultAddress(addr.id)}
                          >
                            انتخاب به عنوان آدرس پیش‌فرض
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* ------------------------------------------------------------ */}
          {/* TAB 4: Wallet & Transactions                                 */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "wallet" && (
            <div className="space-y-6">
              {/* Wallet Hero Card */}
              <div className="relative overflow-hidden rounded-2xl bg-gradient-to-l from-primary/90 to-primary p-6 text-primary-foreground shadow-md">
                <div className="relative z-10 flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-primary-foreground/80 text-sm">
                      <WalletIcon className="h-5 w-5" />
                      <span>موجودی قابل استفاده کیف پول</span>
                    </div>
                    <div className="text-3xl font-extrabold tracking-tight sm:text-4xl">
                      {formatPrice(walletBalance)}
                    </div>
                    <p className="text-xs text-primary-foreground/75 font-mono">
                      معادل {toPersianDigits(walletBalance * 10)} ریال
                    </p>
                  </div>

                  <Button
                    onClick={() => setIsDepositModalOpen(true)}
                    variant="secondary"
                    size="lg"
                    className="gap-2 font-bold shadow-sm"
                  >
                    <Plus className="h-5 w-5" />
                    افزایش موجودی (شارژ)
                  </Button>
                </div>
              </div>

              {/* Transactions List */}
              <Card className="p-6">
                <div className="mb-6 flex items-center justify-between border-b pb-4">
                  <div>
                    <h2 className="text-lg font-semibold text-foreground">گردش حساب و تراکنش‌ها</h2>
                    <p className="text-xs text-muted-foreground">
                      ریز مبالغ واریز شده و برداشت‌های خرید
                    </p>
                  </div>
                  <Badge variant="outline">
                    {isLoadingWallet ? "در حال بروزرسانی..." : `${toPersianDigits(transactions.length)} تراکنش`}
                  </Badge>
                </div>

                {walletState === "error" ? (
                  <SectionLoadError
                    title="دریافت کیف پول ناموفق بود"
                    message={loadErrors.wallet ?? "تلاش دوباره ناموفق بود."}
                    onRetry={() => window.location.reload()}
                  />
                ) : walletState === "empty" ? (
                  <div className="py-12 text-center text-muted-foreground text-sm">
                    هیچ تراکنشی در تاریخچه حساب شما ثبت نشده است.
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {transactions.map((tx) => {
                      const isCredit = tx.type === "deposit" || tx.type === "refund";
                      return (
                        <div
                          key={tx.id}
                          className="flex flex-col gap-2 py-3.5 sm:flex-row sm:items-center sm:justify-between hover:bg-muted/30 px-2 rounded-lg transition-colors"
                        >
                          <div className="flex items-center gap-3">
                            <div
                              className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
                                isCredit
                                  ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400"
                                  : "bg-red-100 text-red-600 dark:bg-red-950 dark:text-red-400"
                              }`}
                            >
                              {isCredit ? (
                                <ArrowDownRight className="h-5 w-5" />
                              ) : (
                                <ArrowUpLeft className="h-5 w-5" />
                              )}
                            </div>
                            <div>
                              <p className="font-semibold text-sm text-foreground">
                                {tx.description}
                              </p>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                                <span>{tx.date}</span>
                                <span>&middot;</span>
                                <span className="font-mono">کد پیگیری: {tx.trackingCode}</span>
                              </div>
                            </div>
                          </div>

                          <div className="flex items-center justify-between sm:justify-end gap-3 text-left">
                            <span
                              className={`font-bold font-mono text-sm ${
                                isCredit ? "text-emerald-600" : "text-foreground"
                              }`}
                            >
                              {isCredit ? "+ " : "- "}
                              {formatPrice(tx.amount)}
                            </span>
                            <Badge
                              variant={
                                tx.status === "success"
                                  ? "success"
                                  : tx.status === "pending"
                                  ? "warning"
                                  : "destructive"
                              }
                              className="text-[11px]"
                            >
                              {tx.status === "success"
                                ? "موفق"
                                : tx.status === "pending"
                                ? "در حال پرداخت"
                                : "ناموفق"}
                            </Badge>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>
            </div>
          )}

          {/* ------------------------------------------------------------ */}
          {/* TAB 5: Invite friends (referrals)                            */}
          {/* ------------------------------------------------------------ */}
          {/* ------------------------------------------------------------ */}
          {/* TAB: Saved cards & installment plans                          */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "cards" && <SavedCardsPanel />}

          {activeTab === "referrals" && <ReferralPanel />}

          {/* ------------------------------------------------------------ */}
          {/* TAB 6: Wishlist                                              */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "wishlist" && (
            <Card className="p-6">
              <div className="mb-6 flex items-center justify-between border-b pb-4">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">لیست علاقه‌مندی‌ها</h2>
                  <p className="text-xs text-muted-foreground">
                    محصولاتی که برای خرید در آینده نشان کرده‌اید
                  </p>
                </div>
                <Badge variant="secondary">
                  {isLoadingWishlist ? "در حال دریافت..." : `${toPersianDigits(wishlist.length)} کالا`}
                </Badge>
              </div>

              {wishlistState === "error" ? (
                <SectionLoadError
                  title="دریافت علاقه‌مندی‌ها ناموفق بود"
                  message={loadErrors.wishlist ?? "تلاش دوباره ناموفق بود."}
                  onRetry={() => window.location.reload()}
                />
              ) : wishlistState === "empty" ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Heart className="h-12 w-12 text-muted-foreground/60 mb-3" />
                  <p className="font-semibold text-foreground">لیست علاقه‌مندی‌های شما خالی است</p>
                  <p className="text-sm text-muted-foreground mt-1 mb-4">
                    با کلیک روی آیکون قلب در صفحه محصولات، آن‌ها را در این بخش ذخیره کنید.
                  </p>
                  <Link href="/products">
                    <Button>کاوش در فروشگاه</Button>
                  </Link>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {wishlist.map((item) => (
                    <div
                      key={item.id}
                      className="flex flex-col justify-between rounded-xl border border-border p-4 bg-card transition-all hover:shadow-sm"
                    >
                      <div className="space-y-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                            <ShoppingBag className="h-8 w-8" />
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={() => handleRemoveFromWishlist(item.productId)}
                            title="حذف از لیست"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>

                        <div>
                          <p className="text-xs text-muted-foreground">{item.category}</p>
                          <Link
                            href={`/products/${item.slug}`}
                            className="text-sm font-semibold text-foreground hover:text-primary transition-colors line-clamp-2"
                          >
                            {item.title}
                          </Link>
                        </div>

                        <div className="flex items-baseline gap-2">
                          <span className="font-bold text-primary text-base">
                            {formatPrice(item.price)}
                          </span>
                          {item.originalPrice && item.originalPrice > item.price && (
                            <span className="text-xs text-muted-foreground line-through">
                              {formatPrice(item.originalPrice)}
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="mt-4 pt-3 border-t border-border flex items-center justify-between gap-2">
                        <Badge variant={item.inStock ? "success" : "secondary"}>
                          {item.inStock ? "موجود در انبار" : "ناموجود"}
                        </Badge>

                        <Button
                          size="sm"
                          disabled={!item.inStock}
                          onClick={() => handleMoveToCart(item)}
                          className="gap-1.5"
                        >
                          <ShoppingBag className="h-4 w-4" />
                          افزودن به سبد
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>
          )}

          {/* ------------------------------------------------------------ */}
          {/* TAB 6: Support Tickets & Create Modal                        */}
          {/* ------------------------------------------------------------ */}
          {activeTab === "support" && (
            <Card className="p-6">
              <div className="mb-6 flex items-center justify-between border-b pb-4">
                <div>
                  <h2 className="text-lg font-semibold text-foreground">تیکت‌های پشتیبانی</h2>
                  <p className="text-xs text-muted-foreground">
                    {isLoadingTickets
                      ? "در حال بروزرسانی وضعیت تیکت‌ها..."
                      : "ارتباط مستقیم با کارشناسان و پیگیری پاسخ‌ها"}
                  </p>
                </div>
                <Button onClick={() => setIsTicketModalOpen(true)} size="sm" className="gap-1.5">
                  <Plus className="h-4 w-4" />
                  ارسال تیکت جدید
                </Button>
              </div>

              {ticketsState === "error" ? (
                <SectionLoadError
                  title="دریافت تیکت‌ها ناموفق بود"
                  message={loadErrors.tickets ?? "تلاش دوباره ناموفق بود."}
                  onRetry={() => window.location.reload()}
                />
              ) : ticketsState === "empty" ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Headphones className="h-12 w-12 text-muted-foreground/60 mb-3" />
                  <p className="font-semibold text-foreground">هیچ تیکت پشتیبانی ثبت نشده است</p>
                  <p className="text-sm text-muted-foreground mt-1 mb-4">
                    هرگونه سوال، ابهام یا مشکل خود را با ثبت تیکت جدید با ما در میان بگذارید.
                  </p>
                  <Button onClick={() => setIsTicketModalOpen(true)}>ارسال اولین تیکت</Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {tickets.map((tck) => {
                    const statusConfig = TICKET_STATUS_CONFIG[tck.status] || {
                      label: tck.status,
                      badgeVariant: "secondary",
                    };
                    return (
                      <div
                        key={tck.id}
                        className="rounded-xl border border-border p-4 bg-card hover:border-border/80 transition-all"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 pb-3">
                          <div className="flex items-center gap-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                              <MessageSquare className="h-5 w-5" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono font-bold text-foreground">
                                  {tck.ticketNumber}
                                </span>
                                <Badge variant={statusConfig.badgeVariant}>
                                  {statusConfig.label}
                                </Badge>
                                <span className="text-xs text-muted-foreground">
                                  اولویت: {TICKET_PRIORITY_LABELS[tck.priority]}
                                </span>
                              </div>
                              <p className="font-semibold text-sm text-foreground mt-0.5">
                                {tck.subject}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 text-xs text-muted-foreground">
                            <span>دپارتمان: {tck.department}</span>
                            <span>&middot;</span>
                            <span>بروزرسانی: {tck.updatedAt}</span>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setSelectedTicketView(tck)}
                              className="gap-1 text-xs"
                            >
                              <Eye className="h-3.5 w-3.5" />
                              مشاهده پیام
                            </Button>
                          </div>
                        </div>

                        {tck.lastMessage && (
                          <div className="mt-3 text-xs text-muted-foreground line-clamp-2 bg-muted/40 p-2.5 rounded-lg">
                            <span className="font-medium text-foreground">آخرین پیام: </span>
                            {tck.lastMessage}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </Card>
          )}

        </div>
      </div>

      {/* ============================================================== */}
      {/* MODAL 1: Order Tracking Timeline Modal                         */}
      {/* ============================================================== */}
      <Dialog
        open={Boolean(selectedOrderForTracking)}
        onOpenChange={(open) => !open && setSelectedOrderForTracking(null)}
      >
        <DialogContent className="max-w-xl" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Truck className="h-5 w-5 text-primary" />
              رهگیری و وضعیت سفارش {selectedOrderForTracking?.orderNumber}
            </DialogTitle>
            <DialogDescription>
              مراحل پردازش، آماده‌سازی و ارسال بسته پستی
            </DialogDescription>
          </DialogHeader>

          {selectedOrderForTracking && (
            <div className="space-y-6 py-2">
              {/* Top metadata info */}
              <div className="grid grid-cols-2 gap-3 rounded-lg bg-muted/50 p-3 text-xs sm:grid-cols-3">
                <div>
                  <span className="text-muted-foreground block">کد رهگیری پستی:</span>
                  <span className="font-mono font-bold text-foreground">
                    {selectedOrderForTracking.trackingCode || "در انتظار صدور"}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">تاریخ ثبت:</span>
                  <span className="font-semibold text-foreground">
                    {selectedOrderForTracking.date}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground block">روش پرداخت:</span>
                  <span className="font-semibold text-foreground">
                    {selectedOrderForTracking.paymentMethod || "آنلاین"}
                  </span>
                </div>
              </div>

              {/* 4-Step Shipment Tracking Stepper & RMA Integration (Sprint 3 Phase 2) */}
              {selectedOrderForTracking.status === "canceled" ? (
                <div className="flex items-center gap-3 rounded-lg bg-destructive/10 p-4 text-destructive text-sm">
                  <AlertCircle className="h-5 w-5 shrink-0" />
                  <div>
                    <p className="font-bold">این سفارش لغو شده است</p>
                    <p className="text-xs text-destructive/80 mt-0.5">
                      در صورت کسر وجه، مبالغ به کیف پول شما برگشت داده شده است.
                    </p>
                  </div>
                </div>
              ) : (
                <ShipmentStepper
                  orderId={selectedOrderForTracking.id}
                  trackingCode={selectedOrderForTracking.trackingCode}
                  carrier="شرکت ملی پست ایران (پیشتاز)"
                  status={selectedOrderForTracking.status}
                  deliveredAt={selectedOrderForTracking.deliveredAt}
                  showRmaAction={true}
                />
              )}

              {/* Shipping Address Footer */}
              {selectedOrderForTracking.shippingAddress && (
                <div className="rounded-lg border border-border p-3 text-xs">
                  <span className="text-muted-foreground block mb-1">نشانی تحویل گیرنده:</span>
                  <p className="font-medium text-foreground">
                    {selectedOrderForTracking.shippingAddress}
                  </p>
                </div>
              )}
            </div>
          )}

          <DialogFooter className="flex flex-col-reverse sm:flex-row sm:justify-between items-center gap-2">
            <Button
              variant="outline"
              onClick={() => setSelectedOrderForTracking(null)}
              className="w-full sm:w-auto"
            >
              بستن
            </Button>
            {selectedOrderForTracking && (
              <Button
                variant="default"
                onClick={() => handlePrintInvoice(selectedOrderForTracking.id)}
                className="w-full sm:w-auto gap-2"
              >
                <Printer className="h-4 w-4" />
                چاپ فاکتور رسمی
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ============================================================== */}
      {/* MODAL 2: Add / Edit Address Modal                              */}
      {/* ============================================================== */}
      <Dialog open={isAddressModalOpen} onOpenChange={setIsAddressModalOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MapPin className="h-5 w-5 text-primary" />
              {editingAddress ? "ویرایش آدرس" : "افزودن آدرس جدید"}
            </DialogTitle>
            <DialogDescription>
              اطلاعات دقیق پستی و گیرنده مرسوله را وارد کنید.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleSaveAddress} className="space-y-4 py-2">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="addrTitle">عنوان آدرس</Label>
                <Input
                  id="addrTitle"
                  value={addressForm.title}
                  onChange={(e) => setAddressForm({ ...addressForm, title: e.target.value })}
                  placeholder="مثلاً: خانه، محل کار"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="receiverName">نام و نام خانوادگی تحویل‌گیرنده</Label>
                <Input
                  id="receiverName"
                  value={addressForm.receiverName}
                  onChange={(e) =>
                    setAddressForm({ ...addressForm, receiverName: e.target.value })
                  }
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="addrProvince">استان</Label>
                <Input
                  id="addrProvince"
                  value={addressForm.province}
                  onChange={(e) => setAddressForm({ ...addressForm, province: e.target.value })}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="addrCity">شهر</Label>
                <Input
                  id="addrCity"
                  value={addressForm.city}
                  onChange={(e) => setAddressForm({ ...addressForm, city: e.target.value })}
                  required
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="addrPostalCode">کد پستی (۱۰ رقم)</Label>
                <Input
                  id="addrPostalCode"
                  value={addressForm.postalCode}
                  onChange={(e) =>
                    setAddressForm({
                      ...addressForm,
                      postalCode: e.target.value.replace(/\D/g, "").slice(0, 10),
                    })
                  }
                  dir="ltr"
                  placeholder="1234567890"
                  className="font-mono text-left"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="addrPhone">شماره موبایل تحویل‌گیرنده</Label>
                <Input
                  id="addrPhone"
                  value={addressForm.phone}
                  onChange={(e) => setAddressForm({ ...addressForm, phone: e.target.value })}
                  dir="ltr"
                  className="font-mono text-left"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="fullAddress">نشانی پستی دقیق</Label>
              <Textarea
                id="fullAddress"
                value={addressForm.fullAddress}
                onChange={(e) => setAddressForm({ ...addressForm, fullAddress: e.target.value })}
                placeholder="شامل نام خیابان، کوچه، پلاک، طبقه و واحد"
                rows={3}
                required
              />
            </div>

            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="isDefaultCheckbox"
                checked={addressForm.isDefault}
                onChange={(e) => setAddressForm({ ...addressForm, isDefault: e.target.checked })}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
              />
              <Label htmlFor="isDefaultCheckbox" className="text-xs cursor-pointer">
                این نشانی به عنوان آدرس پیش‌فرض ذخیره شود
              </Label>
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsAddressModalOpen(false)}
              >
                انصراف
              </Button>
              <Button type="submit">
                {editingAddress ? "ذخیره ویرایش" : "ثبت آدرس"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ============================================================== */}
      {/* MODAL 3: Wallet Deposit Modal                                  */}
      {/* ============================================================== */}
      <Dialog open={isDepositModalOpen} onOpenChange={setIsDepositModalOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard className="h-5 w-5 text-primary" />
              افزایش موجودی کیف پول
            </DialogTitle>
            <DialogDescription>
              مبلغ مورد نظر را وارد کرده و از درگاه امن پرداخت بانکی شارژ نمایید.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleDepositSubmit} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="depositAmount">مبلغ شارژ (تومان)</Label>
              <Input
                id="depositAmount"
                value={depositAmount ? Number(depositAmount).toLocaleString("fa-IR") : ""}
                onChange={(e) => {
                  // Normalize Persian/Arabic digits before stripping, otherwise
                  // the formatted value wipes itself on every keystroke.
                  const raw = toEnglishDigits(e.target.value).replace(/\D/g, "");
                  setDepositAmount(raw);
                }}
                placeholder="مثلاً: ۵۰۰,۰۰۰"
                className="font-bold text-lg text-left font-mono"
                dir="ltr"
                required
              />
            </div>

            {/* Quick Chips */}
            <div className="space-y-1">
              <span className="text-xs text-muted-foreground block">انتخاب سریع مبلغ:</span>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {[
                  { label: "۱۰۰ هزار", val: "100000" },
                  { label: "۵۰۰ هزار", val: "500000" },
                  { label: "۱ میلیون", val: "1000000" },
                  { label: "۲ میلیون", val: "2000000" },
                ].map((chip) => (
                  <Button
                    key={chip.val}
                    type="button"
                    variant={depositAmount === chip.val ? "default" : "outline"}
                    size="sm"
                    className="text-xs py-1"
                    onClick={() => setDepositAmount(chip.val)}
                  >
                    {chip.label}
                  </Button>
                ))}
              </div>
            </div>

            {/* Gateway selection */}
            <div className="space-y-1.5 pt-2">
              <Label>درگاه پرداخت اینترنتی</Label>
              <div className="grid grid-cols-2 gap-3">
                <button
                  type="button"
                  onClick={() => setDepositGateway("zarinpal")}
                  className={`flex items-center gap-2.5 rounded-lg border p-3 text-xs font-semibold transition-all ${
                    depositGateway === "zarinpal"
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border hover:border-border/80 text-foreground"
                  }`}
                >
                  <Building2 className="h-4 w-4" />
                  درگاه شاپرک - زرین‌پال
                </button>
                <button
                  type="button"
                  onClick={() => setDepositGateway("idpay")}
                  className={`flex items-center gap-2.5 rounded-lg border p-3 text-xs font-semibold transition-all ${
                    depositGateway === "idpay"
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border hover:border-border/80 text-foreground"
                  }`}
                >
                  <Building2 className="h-4 w-4" />
                  درگاه پرداخت آی‌دی‌پی
                </button>
              </div>
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsDepositModalOpen(false)}
              >
                انصراف
              </Button>
              <Button type="submit" disabled={isDepositing} className="gap-2">
                {isDepositing ? "در حال اتصال..." : "ورود به درگاه پرداخت"}
                <ExternalLink className="h-4 w-4" />
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ============================================================== */}
      {/* MODAL 4: Create Support Ticket Modal                           */}
      {/* ============================================================== */}
      <Dialog open={isTicketModalOpen} onOpenChange={setIsTicketModalOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Headphones className="h-5 w-5 text-primary" />
              ارسال تیکت پشتیبانی جدید
            </DialogTitle>
            <DialogDescription>
              پرسش یا درخواست خود را مطرح نمایید تا همکاران ما در اسرع وقت پاسخ دهند.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleCreateTicket} className="space-y-4 py-2">
            <div className="space-y-1.5">
              <Label htmlFor="ticketSubject">موضوع تیکت</Label>
              <Input
                id="ticketSubject"
                value={ticketForm.subject}
                onChange={(e) => setTicketForm({ ...ticketForm, subject: e.target.value })}
                placeholder="عنوان خلاصه از درخواست"
                required
              />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>دپارتمان مربوطه</Label>
                <Select
                  value={ticketForm.department}
                  onValueChange={(val) => setTicketForm({ ...ticketForm, department: val })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="انتخاب دپارتمان" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="سفارش و ارسال">سفارش و پیگیری مرسوله</SelectItem>
                    <SelectItem value="امور مالی و حسابداری">امور مالی و بازگشت وجه</SelectItem>
                    <SelectItem value="پشتیبانی فنی سایت">پشتیبانی فنی سایت</SelectItem>
                    <SelectItem value="پیشنهادات و انتقادات">پیشنهادات و شکایات</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label>اولویت</Label>
                <Select
                  value={ticketForm.priority}
                  onValueChange={(val: string) => setTicketForm({ ...ticketForm, priority: val as SupportTicket["priority"] })}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="اولویت" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="low">کم</SelectItem>
                    <SelectItem value="medium">متوسط</SelectItem>
                    <SelectItem value="high">زیاد</SelectItem>
                    <SelectItem value="urgent">فوری</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ticketMessage">متن پیام و توضیحات</Label>
              <Textarea
                id="ticketMessage"
                value={ticketForm.message}
                onChange={(e) => setTicketForm({ ...ticketForm, message: e.target.value })}
                placeholder="توضیحات کامل درخواست خود را با ذکر شماره سفارش یا کدهای مرتبط بنویسید..."
                rows={5}
                required
              />
            </div>

            <DialogFooter className="pt-4">
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsTicketModalOpen(false)}
              >
                انصراف
              </Button>
              <Button type="submit" disabled={isCreatingTicket}>
                {isCreatingTicket ? "در حال ارسال..." : "ارسال تیکت"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* ============================================================== */}
      {/* MODAL 5: View Ticket Message Details Modal                     */}
      {/* ============================================================== */}
      <Dialog
        open={Boolean(selectedTicketView)}
        onOpenChange={(open) => !open && setSelectedTicketView(null)}
      >
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              تیکت {selectedTicketView?.ticketNumber}
            </DialogTitle>
            <DialogDescription>{selectedTicketView?.subject}</DialogDescription>
          </DialogHeader>

          {selectedTicketView && (
            <div className="space-y-4 py-2 text-sm">
              <div className="flex items-center justify-between rounded-lg bg-muted p-3 text-xs">
                <div>
                  <span className="text-muted-foreground">دپارتمان: </span>
                  <span className="font-semibold text-foreground">
                    {selectedTicketView.department}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">تاریخ: </span>
                  <span className="font-semibold text-foreground">
                    {selectedTicketView.createdAt}
                  </span>
                </div>
              </div>

              <div className="rounded-lg border border-border p-4 space-y-2 bg-card">
                <span className="text-xs text-muted-foreground block font-medium">متن پیام:</span>
                <p className="text-foreground leading-relaxed whitespace-pre-wrap">
                  {selectedTicketView.lastMessage || "پیامی ثبت نشده است."}
                </p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setSelectedTicketView(null)}
              className="w-full sm:w-auto"
            >
              بستن
            </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    );
  }
