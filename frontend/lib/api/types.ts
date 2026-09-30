/**
 * Generic API response wrapper.
 */
export interface ApiResponse<T> {
  data: T;
  message: string;
  success: boolean;
}

/**
 * Paginated API response.
 */
export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginationMeta;
  message: string;
  success: boolean;
}

/**
 * Pagination metadata.
 */
export interface PaginationMeta {
  current_page: number;
  last_page: number;
  per_page: number;
  total: number;
  from: number;
  to: number;
}

/**
 * API error response.
 */
export interface ApiError {
  status: number;
  message: string;
  errors: Record<string, string[]> | null;
}

/**
 * JWT token pair response from backend auth endpoints.
 */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

/**
 * Full user profile response directly returned by GET /auth/me and PATCH /auth/me.
 */
export interface UserProfileResponse {
  id: string;
  phone: string;
  email?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  national_code?: string | null;
  birth_date?: string | null;
  avatar_url?: string | null;
  gender?: string | null;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
}

/**
 * Legacy auth response wrapper.
 */
export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in?: number;
  user?: {
    id: string;
    name?: string;
    email?: string;
    phone: string;
    role?: "customer" | "admin" | "vendor";
  };
}

/**
 * Generic list query params.
 */
export interface ListParams {
  page?: number;
  per_page?: number;
  search?: string;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

/**
 * Product list query params.
 */
export interface ProductListParams extends ListParams {
  category_id?: string;
  min_price?: number;
  max_price?: number;
  brand?: string;
  in_stock?: boolean;
}
