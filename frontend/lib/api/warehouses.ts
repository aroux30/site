import apiClient from "./client";

/**
 * Warehouse catalogue API (multi-warehouse v1).
 *
 * Mirrors `/api/v1/admin/inventory/warehouses/*`. Quantities are whole units;
 * money never appears on this surface.
 */

export interface WarehouseStockSummary {
  variant_count: number;
  available: number;
  reserved: number;
  committed: number;
  damaged: number;
  incoming: number;
  total_on_hand: number;
}

export interface Warehouse {
  id: string;
  name: string;
  code: string;
  address: string | null;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  stock: WarehouseStockSummary | null;
}

export interface WarehouseListResponse {
  items: Warehouse[];
  total: number;
}

export interface WarehouseStockRow {
  warehouse_id: string;
  name: string;
  code: string;
  is_default: boolean;
  is_active: boolean;
  /** False for a warehouse id holding stock with no catalogue row. */
  is_registered: boolean;
  stock: WarehouseStockSummary;
}

export interface WarehouseStockListResponse {
  items: WarehouseStockRow[];
  total: number;
  totals: WarehouseStockSummary;
}

export interface VariantStockRow {
  warehouse_id: string;
  name: string;
  code: string;
  is_active: boolean;
  is_registered: boolean;
  available: number;
  reserved: number;
  committed: number;
  damaged: number;
  incoming: number;
  low_stock_threshold: number;
}

export interface VariantStockListResponse {
  variant_id: string;
  items: VariantStockRow[];
  total_available: number;
  total_on_hand: number;
}

export interface WarehouseCreateInput {
  name: string;
  code: string;
  address?: string | null;
  is_default?: boolean;
}

export interface WarehouseUpdateInput {
  name?: string;
  code?: string;
  address?: string | null;
  is_default?: boolean;
}

const ADMIN_INVENTORY = "/admin/inventory";

export const warehousesApi = {
  list: async (params?: { is_active?: boolean }): Promise<WarehouseListResponse> => {
    const response = await apiClient.get<WarehouseListResponse>(`${ADMIN_INVENTORY}/warehouses`, {
      params,
    });
    return response.data;
  },

  get: async (id: string): Promise<Warehouse> => {
    const response = await apiClient.get<Warehouse>(`${ADMIN_INVENTORY}/warehouses/${id}`);
    return response.data;
  },

  getDefault: async (): Promise<Warehouse | null> => {
    const response = await apiClient.get<Warehouse | null>(`${ADMIN_INVENTORY}/warehouses/default`);
    return response.data;
  },

  create: async (data: WarehouseCreateInput): Promise<Warehouse> => {
    const response = await apiClient.post<Warehouse>(`${ADMIN_INVENTORY}/warehouses`, data);
    return response.data;
  },

  update: async (id: string, data: WarehouseUpdateInput): Promise<Warehouse> => {
    const response = await apiClient.patch<Warehouse>(`${ADMIN_INVENTORY}/warehouses/${id}`, data);
    return response.data;
  },

  deactivate: async (id: string): Promise<Warehouse> => {
    const response = await apiClient.post<Warehouse>(
      `${ADMIN_INVENTORY}/warehouses/${id}/deactivate`,
    );
    return response.data;
  },

  reactivate: async (id: string): Promise<Warehouse> => {
    const response = await apiClient.post<Warehouse>(
      `${ADMIN_INVENTORY}/warehouses/${id}/reactivate`,
    );
    return response.data;
  },

  stockByWarehouse: async (): Promise<WarehouseStockListResponse> => {
    const response = await apiClient.get<WarehouseStockListResponse>(
      `${ADMIN_INVENTORY}/warehouses/stock`,
    );
    return response.data;
  },

  stockByVariant: async (variantId: string): Promise<VariantStockListResponse> => {
    const response = await apiClient.get<VariantStockListResponse>(
      `${ADMIN_INVENTORY}/warehouses/stock/variants/${variantId}`,
    );
    return response.data;
  },
};
