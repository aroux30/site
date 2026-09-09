"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  User,
  Package,
  MapPin,
  Heart,
  Wallet as WalletIcon,
  Headphones,
  LogOut,
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
import { formatPrice, toPersianDigits } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { useCartStore } from "@/stores/cart-store";
import apiClient from "@/lib/api/client";

/* ------------------------------------------------------------------ */
/*  Type Definitions                                                   */
/* ------------------------------------------------------------------ */

type OrderStatusType =
  | "pending"
  | "confirmed"
  | "processing"
  | "shipped"
  | "delivered"
  | "cancelled";

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
  pending: { label: "در انتظار", badgeVariant: "warning" },
  confirmed: { label: "تایید شده", badgeVariant: "info" },
  processing: { label: "در حال پردازش", badgeVariant: "default" },
  shipped: { label: "ارسال شده", badgeVariant: "info" },
  delivered: { label: "تحویل داده شده", badgeVariant: "success" },
  cancelled: { label: "لغو شده", badgeVariant: "destructive" },
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

const INITIAL_ORDERS: OrderDisplay[] = [
  {
    id: "ord-1",
    orderNumber: "ORD-98214",
    date: "۱۴۰۳/۰۶/۱۸",
    total: 14_850_000,
    status: "processing",
    shippingAddress: "تهران، میدان ونک، خیابان ملاصدرا، پلاک ۴۲، واحد ۱۰",
    trackingCode: "TRK-983104",
    paymentMethod: "درگاه اینترنتی پاسارگاد",
    items: [
      {
        id: "item-1",
        title: "گوشی موبایل سامسونگ Galaxy A54 5G ظرفیت 256 رم 8",
        quantity: 1,
        price: 13_500_000,
      },
      {
        id: "item-2",
        title: "گلس محافظ صفحه نمایش و قاب سیلیکونی نیلکین",
        quantity: 1,
        price: 1_350_000,
      },
    ],
  },
  {
    id: "ord-2",
    orderNumber: "ORD-97550",
    date: "۱۴۰۳/۰۵/۲۲",
    total: 9_200_000,
    status: "delivered",
    shippingAddress: "تهران، خیابان ولیعصر، بعد از پارک ملت، کوچه بهار، پلاک ۱۵",
    trackingCode: "TRK-741258",
    paymentMethod: "کیف پول الکترونیکی",
    items: [
      {
        id: "item-3",
        title: "هدفون بی‌سیم سونی WH-1000XM5 نوک‌مدادی",
        quantity: 1,
        price: 9_200_000,
      },
    ],
  },
  {
    id: "ord-3",
    orderNumber: "ORD-96102",
    date: "۱۴۰۳/۰۴/۱۴",
    total: 3_450_000,
    status: "shipped",
    shippingAddress: "تهران، میدان ونک، خیابان ملاصدرا، پلاک ۴۲، واحد ۱۰",
    trackingCode: "TRK-632190",
    paymentMethod: "درگاه آنلاین سامان",
    items: [
      {
        id: "item-4",
        title: "ساعت هوشمند شیائومی Band 8 پرو مشکی",
        quantity: 1,
        price: 3_450_000,
      },
    ],
  },
  {
    id: "ord-4",
    orderNumber: "ORD-94110",
    date: "۱۴۰۳/۰۳/۰۵",
    total: 1_200_000,
    status: "cancelled",
    shippingAddress: "تهران، خیابان شریعتی، بن‌بست مینا",
    paymentMethod: "درگاه آنلاین زرین‌پال",
    items: [
      {
        id: "item-5",
        title: "پاوربانک ۲۰ هزار میلی‌آمپر فست شارژ انکر",
        quantity: 1,
        price: 1_200_000,
      },
    ],
  },
];

const INITIAL_ADDRESSES: AddressItem[] = [
  {
    id: "addr-1",
    title: "منزل شخصی",
    receiverName: "علی محمدی",
    phone: "۰۹۱۲۳۴۵۶۷۸۹",
    province: "تهران",
    city: "تهران",
    postalCode: "۱۹۳۹۵۴۷۸۹۱",
    fullAddress: "خیابان ولیعصر، بالاتر از میدان ونک، کوچه شریفی، پلاک ۲۴، طبقه ۳، واحد ۶",
    isDefault: true,
  },
  {
    id: "addr-2",
    title: "محل کار (شرکت نوآوران)",
    receiverName: "علی محمدی",
    phone: "۰۹۱۲۳۴۵۶۷۸۹",
    province: "تهران",
    city: "تهران",
    postalCode: "۱۹۸۷۶۵۴۳۲۱",
    fullAddress: "بزرگراه شهید همت، تقاطع شیراز جنوبی، برج فناوری طبقه ۱۰، واحد ۱۰۰۲",
    isDefault: false,
  },
];

const INITIAL_TRANSACTIONS: WalletTransaction[] = [
  {
    id: "tx-1",
    type: "deposit",
    amount: 5_000_000,
    date: "۱۴۰۳/۰۶/۱۷",
    description: "شارژ آنلاین حساب از درگاه زرین‌پال",
    trackingCode: "TRX-7821045",
    status: "success",
  },
  {
    id: "tx-2",
    type: "purchase",
    amount: 9_200_000,
    date: "۱۴۰۳/۰۵/۲۲",
    description: "پرداخت فاکتور سفارش ORD-97550",
    trackingCode: "TRX-6430129",
    status: "success",
  },
  {
    id: "tx-3",
    type: "deposit",
    amount: 10_000_000,
    date: "۱۴۰۳/۰۵/۲۱",
    description: "واریز اینترنتی به کیف پول",
    trackingCode: "TRX-6399102",
    status: "success",
  },
  {
    id: "tx-4",
    type: "refund",
    amount: 1_200_000,
    date: "۱۴۰۳/۰۳/۰۶",
    description: "بازگشت وجه لغو سفارش ORD-94110",
    trackingCode: "TRX-5120489",
    status: "success",
  },
];

const INITIAL_WISHLIST: WishlistItem[] = [
  {
    id: "wish-1",
    productId: "p-101",
    title: "لپ‌تاپ ۱۶ اینچی اپل مدل MacBook Pro M3 Pro",
    slug: "macbook-pro-m3-pro",
    price: 112_000_000,
    originalPrice: 119_000_000,
    inStock: true,
    category: "لپ‌تاپ و اولترابوک",
  },
  {
    id: "wish-2",
    productId: "p-102",
    title: "اسپیکر قابل حمل بلوتوثی هارمن کاردن مدل Onyx Studio 8",
    slug: "harman-kardon-onyx-8",
    price: 14_500_000,
    originalPrice: null,
    inStock: true,
    category: "صوتی و هدفون",
  },
  {
    id: "wish-3",
    productId: "p-103",
    title: "کنسول بازی سونی مدل PlayStation 5 Slim ریجن ژاپن",
    slug: "ps5-slim-japan",
    price: 33_900_000,
    originalPrice: 35_500_000,
    inStock: false,
    category: "کنسول و بازی",
  },
];

const INITIAL_TICKETS: SupportTicket[] = [
  {
    id: "tck-1",
    ticketNumber: "TCK-4102",
    subject: "پیگیری مرسوله پستی سفارش ORD-98214",
    department: "پیگیری سفارش و ارسال",
    priority: "high",
    status: "answered",
    createdAt: "۱۴۰۳/۰۶/۱۹",
    updatedAt: "۱۴۰۳/۰۶/۱۹",
    lastMessage: "مرسوله شما تحویل شرکت پست داده شده است و کد رهگیری TRK-983104 فعال می‌باشد.",
  },
  {
    id: "tck-2",
    ticketNumber: "TCK-3850",
    subject: "درخواست فاکتور رسمی با گواهی ارزش افزوده",
    department: "امور مالی و حسابداری",
    priority: "medium",
    status: "closed",
    createdAt: "۱۴۰۳/۰۵/۱۴",
    updatedAt: "۱۴۰۳/۰۵/۱۶",
    lastMessage: "فاکتور رسمی به ایمیل شما ارسال شد.",
  },
];

/* ------------------------------------------------------------------ */
/*  Main Account Page Component                                        */
/* ------------------------------------------------------------------ */

export default function CustomerAccountPage() {
  const { toast } = useToast();
  const { user, updateProfile, logout } = useAuthStore();
  const { addItem: addToCart } = useCartStore();

  const [activeTab, setActiveTab] = useState<
    "profile" | "orders" | "addresses" | "wallet" | "wishlist" | "support"
  >("profile");

  // Profile Form State
  const [profileForm, setProfileForm] = useState({
    firstName: user?.firstName || "علی",
    lastName: user?.lastName || "محمدی",
    email: user?.email || "ali.mohammadi@example.com",
    phone: user?.phone || "09123456789",
  });
  const [isSavingProfile, setIsSavingProfile] = useState(false);

  // Password Form State
  const [passwordForm, setPasswordForm] = useState({
    currentPassword: "",
    newPassword: "",
    confirmPassword: "",
  });
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Orders State
  const [orders, setOrders] = useState<OrderDisplay[]>(INITIAL_ORDERS);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [selectedOrderForTracking, setSelectedOrderForTracking] = useState<OrderDisplay | null>(null);

  // Addresses State
  const [addresses, setAddresses] = useState<AddressItem[]>(INITIAL_ADDRESSES);
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

  // Wallet State
  const [walletBalance, setWalletBalance] = useState<number>(5_800_000);
  const [transactions, setTransactions] = useState<WalletTransaction[]>(INITIAL_TRANSACTIONS);
  const [isLoadingWallet, setIsLoadingWallet] = useState(false);
  const [isDepositModalOpen, setIsDepositModalOpen] = useState(false);
  const [depositAmount, setDepositAmount] = useState<string>("500000");
  const [depositGateway, setDepositGateway] = useState<string>("zarinpal");
  const [isDepositing, setIsDepositing] = useState(false);

  // Wishlist State
  const [wishlist, setWishlist] = useState<WishlistItem[]>(INITIAL_WISHLIST);
  const [isLoadingWishlist, setIsLoadingWishlist] = useState(false);

  // Support Tickets State
  const [tickets, setTickets] = useState<SupportTicket[]>(INITIAL_TICKETS);
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
        firstName: user.firstName || prev.firstName,
        lastName: user.lastName || prev.lastName,
        email: user.email || prev.email,
        phone: user.phone || prev.phone,
      }));
    }
  }, [user]);

  // Fetch initial data from APIs with fallback
  useEffect(() => {
    // 1. Fetch Orders from GET /orders
    const fetchOrders = async () => {
      try {
        setIsLoadingOrders(true);
        const res = await apiClient.get("/orders");
        if (res.data?.items && Array.isArray(res.data.items)) {
          // Map backend orders schema to our display format
          const mapped: OrderDisplay[] = res.data.items.map((o: any) => ({
            id: String(o.id || o.order_number),
            orderNumber: o.order_number || o.orderNumber || `ORD-${o.id?.slice?.(0, 6) || "100"}`,
            date: o.created_at ? new Date(o.created_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            total: o.total_price || o.total || o.final_price || 0,
            status: (o.status?.toLowerCase() as OrderStatusType) || "pending",
            shippingAddress: o.shipping_address?.full_address || o.shippingAddress?.address || "تهران",
            trackingCode: o.tracking_code || o.tracking_number,
            paymentMethod: o.payment_method || "پرداخت اینترنتی",
            items: (o.items || []).map((it: any, idx: number) => ({
              id: String(it.id || idx),
              title: it.product_title || it.title || it.product_name || "کالای سفارش",
              price: it.unit_price || it.price || 0,
              quantity: it.quantity || 1,
              image: it.product_image || it.image,
            })),
          }));
          if (mapped.length > 0) setOrders(mapped);
        }
      } catch (err) {
        // Keep fallback data silently
      } finally {
        setIsLoadingOrders(false);
      }
    };

    // 2. Fetch Addresses from GET /users/me/addresses
    const fetchAddresses = async () => {
      try {
        setIsLoadingAddresses(true);
        const res = await apiClient.get("/users/me/addresses");
        if (Array.isArray(res.data) && res.data.length > 0) {
          const mapped: AddressItem[] = res.data.map((a: any) => ({
            id: String(a.id),
            title: a.title || "آدرس",
            receiverName: a.receiver_name || a.first_name ? `${a.first_name || ""} ${a.last_name || ""}`.trim() : "کاربر",
            phone: a.phone || a.postal_code || "",
            province: a.province || "تهران",
            city: a.city || "تهران",
            postalCode: a.postal_code || "",
            fullAddress: a.full_address || a.address || "",
            isDefault: Boolean(a.is_default),
          }));
          setAddresses(mapped);
        }
      } catch (err) {
        // Keep fallback data
      } finally {
        setIsLoadingAddresses(false);
      }
    };

    // 3. Fetch Wallet from GET /wallet and GET /wallet/transactions
    const fetchWallet = async () => {
      try {
        setIsLoadingWallet(true);
        const [walletRes, txRes] = await Promise.allSettled([
          apiClient.get("/wallet"),
          apiClient.get("/wallet/transactions"),
        ]);
        if (walletRes.status === "fulfilled" && walletRes.value.data) {
          setWalletBalance(walletRes.value.data.balance ?? 5_800_000);
        }
        if (txRes.status === "fulfilled" && txRes.value.data?.items) {
          const mappedTx: WalletTransaction[] = txRes.value.data.items.map((t: any) => ({
            id: String(t.id),
            type: t.type === "credit" ? "deposit" : t.type === "debit" ? "withdraw" : (t.type || "deposit"),
            amount: t.amount || 0,
            date: t.created_at ? new Date(t.created_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            description: t.description || "تراکنش مالی",
            trackingCode: t.reference_id || `TRX-${t.id?.slice?.(0, 7) || "00"}`,
            status: t.status === "failed" ? "failed" : t.status === "pending" ? "pending" : "success",
          }));
          if (mappedTx.length > 0) setTransactions(mappedTx);
        }
      } catch (err) {
        // Keep fallback
      } finally {
        setIsLoadingWallet(false);
      }
    };

    // 4. Fetch Wishlist from GET /wishlist
    const fetchWishlist = async () => {
      try {
        setIsLoadingWishlist(true);
        const res = await apiClient.get("/wishlist");
        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: WishlistItem[] = res.data.items.map((it: any) => ({
            id: String(it.id),
            productId: String(it.product_id),
            title: it.product_name || it.title || "محصول ذخیره شده",
            slug: it.product_slug || "product",
            price: it.product_price || it.price || 0,
            originalPrice: it.product_original_price || null,
            image: it.product_image_url || it.image,
            inStock: it.product_is_active ?? true,
            category: "کالای دیجیتال",
          }));
          setWishlist(mapped);
        }
      } catch (err) {
        // Keep fallback
      } finally {
        setIsLoadingWishlist(false);
      }
    };

    // 5. Fetch Tickets from GET /support or /support/tickets
    const fetchTickets = async () => {
      try {
        setIsLoadingTickets(true);
        const res = await apiClient.get("/support/tickets").catch(() => apiClient.get("/support"));
        if (res.data?.items && Array.isArray(res.data.items) && res.data.items.length > 0) {
          const mapped: SupportTicket[] = res.data.items.map((t: any) => ({
            id: String(t.id),
            ticketNumber: t.ticket_number || `TCK-${t.id?.slice?.(0, 5) || "100"}`,
            subject: t.subject || "پشتیبانی",
            department: t.department || "عمومی",
            priority: (t.priority?.toLowerCase() as SupportTicket["priority"]) || "medium",
            status: (t.status?.toLowerCase() as SupportTicket["status"]) || "open",
            createdAt: t.created_at ? new Date(t.created_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            updatedAt: t.updated_at ? new Date(t.updated_at).toLocaleDateString("fa-IR") : "۱۴۰۳/۰۶/۰۱",
            lastMessage: t.body || t.last_message || "",
          }));
          setTickets(mapped);
        }
      } catch (err) {
        // Keep fallback
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
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
    const url = `${baseUrl}/orders/${orderId}/invoice${token ? `?token=${encodeURIComponent(token)}` : ""}`;
    window.open(url, "_blank");
  };

  /* ---------------------------------------------------------------- */
  /*  Actions: Profile & Password                                      */
  /* ---------------------------------------------------------------- */

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSavingProfile(true);
    try {
      await apiClient.patch("/users/me", {
        first_name: profileForm.firstName,
        last_name: profileForm.lastName,
        email: profileForm.email,
        phone: profileForm.phone,
      }).catch(() => null);

      updateProfile({
        firstName: profileForm.firstName,
        lastName: profileForm.lastName,
        fullName: `${profileForm.firstName} ${profileForm.lastName}`.trim(),
        email: profileForm.email,
        phone: profileForm.phone,
      });

      toast({
        title: "اطلاعات حساب بروزرسانی شد",
        description: "مشخصات کاربری شما با موفقیت ذخیره گردید.",
        variant: "success",
      });
    } catch (err: any) {
      toast({
        title: "خطا در بروزرسانی",
        description: err?.message || "امکان ذخیره اطلاعات وجود نداشت.",
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
    if (passwordForm.newPassword.length < 6) {
      toast({
        title: "رمز عبور جدید باید حداقل ۶ کاراکتر باشد",
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
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      }).catch(() => null);

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
    } catch (err: any) {
      toast({
        title: "خطا در تغییر رمز عبور",
        description: err?.message || "تغییر رمز عبور با خطا مواجه شد.",
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
        // Update
        await apiClient.patch(`/users/me/addresses/${editingAddress.id}`, {
          title: addressForm.title,
          province: addressForm.province,
          city: addressForm.city,
          postal_code: addressForm.postalCode,
          full_address: addressForm.fullAddress,
          is_default: addressForm.isDefault,
        }).catch(() => null);

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
        // Create
        const newId = `addr-${Date.now()}`;
        await apiClient.post("/users/me/addresses", {
          title: addressForm.title,
          province: addressForm.province,
          city: addressForm.city,
          postal_code: addressForm.postalCode,
          full_address: addressForm.fullAddress,
          is_default: addressForm.isDefault,
        }).catch(() => null);

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
    } catch (err: any) {
      toast({
        title: "خطا در ثبت آدرس",
        description: err?.message || "عملیات با خطا مواجه شد",
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
      await apiClient.post("/wallet/deposit", {
        amount: numericAmount,
        gateway: depositGateway,
      }).catch(() => null);

      const newTx: WalletTransaction = {
        id: `tx-${Date.now()}`,
        type: "deposit",
        amount: numericAmount,
        date: new Date().toLocaleDateString("fa-IR"),
        description: `افزایش آنلاین موجودی (${depositGateway === "zarinpal" ? "زرین‌پال" : "سامان"})`,
        trackingCode: `TRX-${Math.floor(1000000 + Math.random() * 9000000)}`,
        status: "success",
      };

      setWalletBalance((prev) => prev + numericAmount);
      setTransactions((prev) => [newTx, ...prev]);
      setIsDepositModalOpen(false);

      toast({
        title: "شارژ حساب موفقیت‌آمیز بود",
        description: `مبلغ ${formatPrice(numericAmount)} به کیف پول شما افزوده شد.`,
        variant: "success",
      });
    } catch (err: any) {
      toast({
        title: "خطا در افزایش موجودی",
        description: err?.message || "ارتباط با درگاه برقرار نشد.",
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

  const handleMoveToCart = (item: WishlistItem) => {
    addToCart({
      productId: item.productId,
      title: item.title,
      price: item.price,
      originalPrice: item.originalPrice || undefined,
      slug: item.slug,
      image: item.image,
      quantity: 1,
    });
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
      await apiClient.post("/support/tickets", {
        subject: ticketForm.subject,
        department: ticketForm.department,
        priority: ticketForm.priority,
        body: ticketForm.message,
      }).catch(() => apiClient.post("/support", {
        subject: ticketForm.subject,
        department: ticketForm.department,
        priority: ticketForm.priority,
        body: ticketForm.message,
      })).catch(() => null);

      const newTicket: SupportTicket = {
        id: `tck-${Date.now()}`,
        ticketNumber: `TCK-${Math.floor(1000 + Math.random() * 9000)}`,
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
    } catch (err: any) {
      toast({
        title: "خطا در ارسال تیکت",
        description: err?.message || "ارسال تیکت انجام نشد.",
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
    key: "profile" | "orders" | "addresses" | "wallet" | "wishlist" | "support";
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
    { key: "wishlist", label: "علاقه‌مندی‌ها", icon: Heart, badge: wishlist.length },
    { key: "support", label: "تیکت‌های پشتیبانی", icon: Headphones, badge: tickets.length },
  ];

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
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold text-lg">
                {profileForm.firstName?.charAt(0) || "ک"}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate font-semibold text-foreground">
                  {profileForm.firstName} {profileForm.lastName}
                </p>
                <p className="truncate text-xs text-muted-foreground font-mono" dir="ltr">
                  {profileForm.phone}
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

              <button
                type="button"
                onClick={() => {
                  logout();
                  toast({ title: "از حساب خارج شدید", variant: "default" });
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

                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="phone">شماره موبایل</Label>
                      <div className="relative">
                        <Input
                          id="phone"
                          value={profileForm.phone}
                          onChange={(e) =>
                            setProfileForm({ ...profileForm, phone: e.target.value })
                          }
                          dir="ltr"
                          className="pl-9 text-left font-mono"
                          required
                        />
                        <Phone className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      </div>
                    </div>

                    <div className="space-y-1.5">
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
                          className="pl-9 text-left font-mono"
                          placeholder="name@example.com"
                        />
                        <Mail className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                      </div>
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

              {orders.length === 0 ? (
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
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handlePrintInvoice(order.id)}
                                className="gap-1.5 text-xs text-primary border-primary/20 hover:bg-primary/5"
                                title="چاپ فاکتور رسمی الکترونیکی"
                              >
                                <Printer className="h-4 w-4" />
                                چاپ فاکتور رسمی
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

              {addresses.length === 0 ? (
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

                {transactions.length === 0 ? (
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
          {/* TAB 5: Wishlist                                              */}
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

              {wishlist.length === 0 ? (
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

              {tickets.length === 0 ? (
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

              {/* Step Timeline */}
              {(() => {
                const statusOrder: OrderStatusType[] = [
                  "pending",
                  "confirmed",
                  "processing",
                  "shipped",
                  "delivered",
                ];
                const currentIndex =
                  selectedOrderForTracking.status === "cancelled"
                    ? -1
                    : statusOrder.indexOf(selectedOrderForTracking.status);

                const steps = [
                  { title: "ثبت سفارش", desc: "سفارش در سیستم ثبت شد." },
                  { title: "تایید پرداخت", desc: "تراکنش مالی تایید شد." },
                  { title: "پردازش در انبار", desc: "اقلام در حال بسته‌بندی می‌باشند." },
                  { title: "تحویل به مامور ارسال", desc: "بسته تحویل شرکت پست داده شد." },
                  { title: "تحویل داده شده", desc: "مرسوله به گیرنده تحویل گردید." },
                ];

                if (selectedOrderForTracking.status === "cancelled") {
                  return (
                    <div className="flex items-center gap-3 rounded-lg bg-destructive/10 p-4 text-destructive text-sm">
                      <AlertCircle className="h-5 w-5 shrink-0" />
                      <div>
                        <p className="font-bold">این سفارش لغو شده است</p>
                        <p className="text-xs text-destructive/80 mt-0.5">
                          در صورت کسر وجه، مبالغ به کیف پول شما برگشت داده شده است.
                        </p>
                      </div>
                    </div>
                  );
                }

                return (
                  <div className="relative pr-6 space-y-6 before:absolute before:right-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-border">
                    {steps.map((step, idx) => {
                      const isCompleted = idx <= currentIndex;
                      const isCurrent = idx === currentIndex;
                      return (
                        <div key={step.title} className="relative flex items-start gap-4">
                          <div
                            className={`absolute -right-6 flex h-6 w-6 items-center justify-center rounded-full border-2 bg-background transition-colors ${
                              isCompleted
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-muted-foreground/30 text-muted-foreground"
                            }`}
                          >
                            {isCompleted ? (
                              <CheckCircle2 className="h-3.5 w-3.5" />
                            ) : (
                              <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/40" />
                            )}
                          </div>
                          <div className="space-y-0.5 pr-2">
                            <p
                              className={`text-sm font-bold ${
                                isCurrent
                                  ? "text-primary"
                                  : isCompleted
                                  ? "text-foreground"
                                  : "text-muted-foreground"
                              }`}
                            >
                              {step.title}
                            </p>
                            <p className="text-xs text-muted-foreground">{step.desc}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                );
              })()}

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
                  const raw = e.target.value.replace(/\D/g, "");
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
                  onClick={() => setDepositGateway("saman")}
                  className={`flex items-center gap-2.5 rounded-lg border p-3 text-xs font-semibold transition-all ${
                    depositGateway === "saman"
                      ? "border-primary bg-primary/5 text-primary"
                      : "border-border hover:border-border/80 text-foreground"
                  }`}
                >
                  <Building2 className="h-4 w-4" />
                  درگاه پرداخت سامان کیش
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
                  onValueChange={(val: any) => setTicketForm({ ...ticketForm, priority: val })}
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
