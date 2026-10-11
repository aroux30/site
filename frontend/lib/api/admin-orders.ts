/**
 * The admin orders API — one typed client for the list, board and drawer.
 *
 * Contract: backend/app/modules/orders/api/routes.py
 *   GET   /orders/admin/orders              → OrderListResponse (paged, filterable)
 *   GET   /orders/admin/orders/stats        → AdminOrderStatsResponse (whole-table per-status)
 *   GET   /orders/admin/orders/{id}         → AdminOrderDetailResponse (unmasked addr + payments)
 *   PATCH /orders/admin/orders/{id}/status  → OrderResponse (single transition)
 *   POST  /orders/admin/orders/bulk/status  → OrderBulkStatusResult (per-order outcomes)
 *
 * Facts this module is explicit about, learned from the old pages:
 *  - The list rows carry NO payment field. The old kanban defaulted every
 *    order to "پرداخت شده"; here paymentStatus is derived only when payment
 *    rows exist (detail endpoint), otherwise "unpaid".
 *  - All amounts are integer Rials; conversion to Toman happens at render
 *    time via `rialsToToman`.
 *  - The list meta field is `total_items` (not `total`); the old page read
 *    `meta.total` and silently showed "0" totals in the pager.
 *  - `customer_name` may legitimately be null (accounts without a profile);
 *    callers render "—" rather than inventing a name.
 */

import apiClient from "./client";
import type { OrderStatus } from "@/lib/admin/order-domain";

// ── Response shapes (mirrors of the backend schemas) ──────────────────────

export interface AdminOrderItem {
  id: string;
  variantId: string;
  productName: string;
  variantInfo: string | null;
  sku: string;
  quantity: number;
  unitPriceRial: number;
  totalPriceRial: number;
  /** Karta category-field answers captured at checkout, when present. */
  customFields: Record<string, unknown> | null;
}

export interface AdminOrderRow {
  id: string;
  orderNumber: string;
  status: OrderStatus;
  userId: string;
  subtotalRial: number;
  shippingCostRial: number;
  taxRial: number;
  discountRial: number;
  totalRial: number;
  createdAt: string;
  updatedAt: string;
  itemsCount: number;
  items: AdminOrderItem[];
  customerName: string | null;
  customerPhone: string | null;
}

export interface AdminOrderPage {
  items: AdminOrderRow[];
  total: number;
  totalPages: number;
  page: number;
}

export interface AdminOrderStatusCount {
  status: OrderStatus;
  count: number;
  totalRial: number;
}

export interface AdminOrderStats {
  byStatus: Map<OrderStatus, AdminOrderStatusCount>;
  totalOrders: number;
  totalRevenueRial: number;
}

export interface AdminOrderPayment {
  id: string;
  amountRial: number;
  status: string;
  provider: string;
  providerTransactionId: string | null;
  createdAt: string;
}

export interface AdminOrderTimelineEvent {
  id: string;
  fromStatus: string | null;
  toStatus: string;
  reason: string | null;
  actorId: string | null;
  createdAt: string;
}

export interface AdminOrderDetail {
  id: string;
  orderNumber: string;
  status: OrderStatus;
  userId: string;
  subtotalRial: number;
  shippingCostRial: number;
  taxRial: number;
  discountRial: number;
  totalRial: number;
  /** UNMASKED on this admin route (the customer route masks street detail). */
  shippingAddress: {
    title?: string;
    province?: string;
    city?: string;
    district?: string;
    postalCode?: string;
    fullAddress?: string;
  } | null;
  notes: string | null;
  items: AdminOrderItem[];
  timeline: AdminOrderTimelineEvent[];
  payments: AdminOrderPayment[];
  customerName: string | null;
  customerPhone: string | null;
  createdAt: string;
  updatedAt: string;
}

// ── Wire → domain mappers ─────────────────────────────────────────────────

function mapItem(raw: Record<string, unknown>): AdminOrderItem {
  const customFields =
    raw.custom_fields && typeof raw.custom_fields === "object"
      ? (raw.custom_fields as Record<string, unknown>)
      : null;
  return {
    id: String(raw.id ?? ""),
    variantId: String(raw.variant_id ?? ""),
    productName: String(raw.product_name ?? raw.product_title ?? "—"),
    variantInfo: (raw.variant_info as string | null) ?? null,
    sku: String(raw.sku ?? "—"),
    quantity: Number(raw.quantity ?? 1),
    unitPriceRial: Number(raw.unit_price ?? 0),
    totalPriceRial: Number(raw.total_price ?? 0),
    customFields,
  };
}

function mapRow(raw: Record<string, unknown>): AdminOrderRow {
  const meta = raw as {
    id: string;
    order_number?: string;
    status?: string;
    user_id?: string;
    subtotal?: number;
    shipping_cost?: number;
    tax?: number;
    discount_amount?: number;
    total?: number;
    created_at?: string;
    updated_at?: string;
    items_count?: number | null;
    items?: Record<string, unknown>[] | null;
    customer_name?: string | null;
    customer_phone?: string | null;
  };
  const items = (meta.items ?? []).map(mapItem);
  return {
    id: String(meta.id),
    orderNumber: meta.order_number ?? `ORD-${String(meta.id).slice(0, 8)}`,
    status: (meta.status ?? "pending") as OrderStatus,
    userId: String(meta.user_id ?? ""),
    subtotalRial: Number(meta.subtotal ?? 0),
    shippingCostRial: Number(meta.shipping_cost ?? 0),
    taxRial: Number(meta.tax ?? 0),
    discountRial: Number(meta.discount_amount ?? 0),
    totalRial: Number(meta.total ?? 0),
    createdAt: meta.created_at ?? new Date().toISOString(),
    updatedAt: meta.updated_at ?? meta.created_at ?? new Date().toISOString(),
    itemsCount:
      typeof meta.items_count === "number"
        ? meta.items_count
        : items.reduce((sum, it) => sum + it.quantity, 0),
    items,
    // null is a fact, not a gap: accounts without a profile have no name.
    customerName: meta.customer_name ?? null,
    customerPhone: meta.customer_phone ?? null,
  };
}

// ── Queries ────────────────────────────────────────────────────────────────

export interface AdminOrderListParams {
  page?: number;
  pageSize?: number;
  status?: OrderStatus | "all";
  /**
   * Several statuses in ONE query — the board's «در حال پردازش» lane is
   * waiting_payment_gateway + waiting_payment_card + pending + processing. Sent as a
   * comma-separated `statuses` param so the backend counts and paginates the
   * lane as a single ordered set; fanning out to one request per status would
   * page each independently and «نمایش بیشتر» would repeat and skip rows.
   */
  statuses?: readonly OrderStatus[];
  search?: string;
}

export const adminOrdersApi = {
  /** Paged list. Status/search are applied SERVER-side. */
  async list(params: AdminOrderListParams): Promise<AdminOrderPage> {
    const qs = new URLSearchParams();
    qs.set("page", String(params.page ?? 1));
    qs.set("page_size", String(params.pageSize ?? 50));
    if (params.status && params.status !== "all") qs.set("status", params.status);
    else if (params.statuses?.length) qs.set("statuses", params.statuses.join(","));
    if (params.search?.trim()) qs.set("search", params.search.trim());

    const res = await apiClient.get(`/orders/admin/orders?${qs.toString()}`);
    const meta = (res.data?.meta ?? {}) as {
      total_items?: number;
      total_pages?: number;
      page?: number;
    };
    const items = Array.isArray(res.data?.items)
      ? (res.data.items as Record<string, unknown>[]).map(mapRow)
      : [];
    return {
      items,
      // `total_items` is the backend field; `meta.total` never existed and
      // reading it made every pager show "0 از 0".
      total: typeof meta.total_items === "number" ? meta.total_items : items.length,
      totalPages: Math.max(1, Number(meta.total_pages ?? 1) || 1),
      page: Number(meta.page ?? params.page ?? 1) || 1,
    };
  },

  /** Whole-table per-status counts/sums for the board headers. */
  async stats(): Promise<AdminOrderStats> {
    const res = await apiClient.get("/orders/admin/orders/stats");
    const rows = Array.isArray(res.data?.by_status)
      ? (res.data.by_status as { status: string; count: number; total: number }[])
      : [];
    const byStatus = new Map<OrderStatus, AdminOrderStatusCount>();
    for (const row of rows) {
      byStatus.set(row.status as OrderStatus, {
        status: row.status as OrderStatus,
        count: Number(row.count ?? 0),
        totalRial: Number(row.total ?? 0),
      });
    }
    return {
      byStatus,
      totalOrders: Number(res.data?.total_orders ?? 0),
      totalRevenueRial: Number(res.data?.total_revenue_rials ?? 0),
    };
  },

  /** Full detail: unmasked address, payments, timeline, customer identity. */
  async detail(orderId: string): Promise<AdminOrderDetail> {
    const res = await apiClient.get(`/orders/admin/orders/${orderId}`);
    const d = res.data as Record<string, unknown>;
    const addr = (d.shipping_address_snapshot ?? null) as Record<string, unknown> | null;
    return {
      id: String(d.id),
      orderNumber: String(d.order_number ?? ""),
      status: (d.status ?? "pending") as OrderStatus,
      userId: String(d.user_id ?? ""),
      subtotalRial: Number(d.subtotal ?? 0),
      shippingCostRial: Number(d.shipping_cost ?? 0),
      taxRial: Number(d.tax ?? 0),
      discountRial: Number(d.discount_amount ?? 0),
      totalRial: Number(d.total ?? 0),
      shippingAddress: addr
        ? {
            title: (addr.title as string) ?? undefined,
            province: (addr.province as string) ?? undefined,
            city: (addr.city as string) ?? undefined,
            district: (addr.district as string) ?? undefined,
            postalCode: (addr.postal_code as string) ?? undefined,
            fullAddress: (addr.full_address as string) ?? undefined,
          }
        : null,
      notes: (d.notes as string | null) ?? null,
      items: Array.isArray(d.items)
        ? (d.items as Record<string, unknown>[]).map(mapItem)
        : [],
      timeline: Array.isArray(d.timeline)
        ? (d.timeline as Record<string, unknown>[]).map((h) => ({
            id: String(h.id ?? ""),
            fromStatus: (h.from_status as string | null) ?? null,
            toStatus: String(h.to_status ?? ""),
            reason: (h.reason as string | null) ?? null,
            actorId: (h.actor_id as string | null) ?? null,
            createdAt: String(h.created_at ?? ""),
          }))
        : [],
      payments: Array.isArray(d.payments)
        ? (d.payments as Record<string, unknown>[]).map((p) => ({
            id: String(p.id ?? ""),
            amountRial: Number(p.amount ?? 0),
            status: String(p.status ?? ""),
            provider: String(p.provider ?? ""),
            providerTransactionId: (p.provider_transaction_id as string | null) ?? null,
            createdAt: String(p.created_at ?? ""),
          }))
        : [],
      customerName: (d.customer_name as string | null) ?? null,
      customerPhone: (d.customer_phone as string | null) ?? null,
      createdAt: String(d.created_at ?? ""),
      updatedAt: String(d.updated_at ?? ""),
    };
  },

  /** One transition. Throws on INVALID_STATUS_TRANSITION (surfaced by caller). */
  async updateStatus(orderId: string, status: OrderStatus, notes?: string): Promise<void> {
    await apiClient.patch(`/orders/admin/orders/${orderId}/status`, {
      status,
      ...(notes ? { notes } : {}),
    });
  },
};
