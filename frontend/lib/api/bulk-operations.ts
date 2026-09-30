/**
 * Bulk admin operations — products and orders.
 *
 * Contract: backend/app/modules/catalog/api/routes.py (bulk-update,
 *           bulk-delete) + backend/app/modules/orders/api/routes.py
 *           (POST /orders/admin/orders/bulk/status)
 *
 * Two shapes of "bulk" live here and they behave differently on purpose:
 *
 * 1. **Catalog** — `bulkUpdateProducts` / `bulkDeleteProducts` are one SQL
 *    UPDATE/DELETE per row with no per-row validation. They return only a
 *    count, so a count lower than the number of ids sent means some rows did
 *    not match; there is nothing per-row to report. Nothing money-related is
 *    mutable here: status, is_active, is_featured and category_id only.
 *
 * 2. **Orders** — a status transition carries stock restock, wallet refund,
 *    outbox events and an audit row, and each order is validated on its own.
 *    `bulkUpdateOrderStatus` therefore returns the whole per-order outcome.
 *    Treat `failed > 0` as a partial run and surface the reasons: the batch
 *    really did move some orders and reject others, and reporting only
 *    "done" would hide the rejections.
 *
 * Amounts are integer rials. No money field is exposed by any method here.
 */

import apiClient from "./client";

// ── Products ─────────────────────────────────────────────────────────────

/** The product's publication state. Mirrors the backend ProductStatus enum. */
export type BulkProductStatus = "draft" | "active" | "archived";

/**
 * One product in a bulk run. Every field is optional; an omitted field is
 * left as it is. That makes a single "make these 50 active" call a
 * 50-item list of `{ id, is_active: true }` and not a read-modify-write.
 */
export interface BulkProductUpdateItem {
  id: string;
  status?: BulkProductStatus;
  is_active?: boolean;
  is_featured?: boolean;
  category_id?: string;
}

export interface ProductBulkUpdateResult {
  updated: number;
}

export interface ProductBulkDeleteResult {
  deleted: number;
}

const CATALOG_PATH = "/catalog";

// ── Orders ───────────────────────────────────────────────────────────────

export const ORDER_BULK_PATH = "/orders/admin/orders/bulk/status";

/** One order's outcome in a bulk status run. */
export interface OrderBulkStatusItem {
  order_id: string;
  order_number: string | null;
  status: string;
  from_status: string | null;
  success: boolean;
  error_code: string | null;
  detail: string | null;
}

export interface OrderBulkStatusResult {
  /** How many ids the request asked for. */
  requested: number;
  succeeded: number;
  /** Rejected orders. Non-zero means a partial run, not a failure to report. */
  failed: number;
  items: OrderBulkStatusItem[];
}

export const adminBulkApi = {
  // ── Products ───────────────────────────────────────────────────────────

  /**
   * Update up to 100 products in one call. The backend applies a single
   * change per item; there is no per-item error channel, so a `updated`
   * count below the number of items sent means some ids did not match a
   * product the caller could see.
   */
  bulkUpdateProducts: async (
    items: BulkProductUpdateItem[],
  ): Promise<ProductBulkUpdateResult> => {
    const res = await apiClient.post<ProductBulkUpdateResult>(
      `${CATALOG_PATH}/products/bulk-update`,
      { items },
    );
    return res.data;
  },

  /** Hard-delete up to 100 products. Irreversible — confirm with the count. */
  bulkDeleteProducts: async (ids: string[]): Promise<ProductBulkDeleteResult> => {
    const res = await apiClient.post<ProductBulkDeleteResult>(
      `${CATALOG_PATH}/products/bulk-delete`,
      { ids },
    );
    return res.data;
  },

  // ── Orders ────────────────────────────────────────────────────────────

  /**
   * Move up to 100 orders to one status. Every order goes through the
   * backend's single-order transition service, so an order whose move is
   * illegal is rejected on its own without blocking the rest.
   *
   * Returns 200 even when some orders were rejected — read `failed` and
   * `items[].detail` rather than assuming the batch was uniform.
   */
  bulkUpdateOrderStatus: async (
    ids: string[],
    status: string,
    notes?: string,
  ): Promise<OrderBulkStatusResult> => {
    const res = await apiClient.post<OrderBulkStatusResult>(ORDER_BULK_PATH, {
      ids,
      status,
      ...(notes ? { notes } : {}),
    });
    return res.data;
  },
};
