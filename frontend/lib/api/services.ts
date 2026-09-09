import apiClient from "./client";

export interface ApiCategory {
  id: string;
  parent_id?: string | null;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  position?: number;
  is_active: boolean;
}

export interface ApiCategoryListResponse {
  items: ApiCategory[];
  meta: ApiPaginationMeta;
}

export interface ApiBrand {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  logo_url?: string | null;
  website_url?: string | null;
  is_active: boolean;
}

export interface ApiBrandListResponse {
  items: ApiBrand[];
  meta: ApiPaginationMeta;
}

export interface ApiPaginationMeta {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
  next_cursor?: string | null;
}

export interface ApiProduct {
  id: string;
  name: string;
  slug: string;
  category_id: string;
  brand_id?: string | null;
  short_description?: string | null;
  description?: string | null;
  product_type?: string;
  status?: string;
  is_active: boolean;
  is_featured: boolean;
  primary_image_url?: string | null;
  min_price?: number | null;
  max_price?: number | null;
  variant_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface ApiProductVariant {
  id: string;
  product_id: string;
  sku: string;
  barcode?: string | null;
  price: number;
  compare_at_price?: number | null;
  cost?: number | null;
  weight?: number | null;
  is_active: boolean;
  position: number;
  attributes?: Record<string, string | number | boolean> | null;
  created_at?: string;
  updated_at?: string;
}

export interface ApiProductImage {
  id: string;
  product_id: string;
  variant_id?: string | null;
  url: string;
  alt_text?: string | null;
  position: number;
  is_primary: boolean;
}

export interface ApiProductAttribute {
  id: string;
  product_id: string;
  attribute_id: string;
  attribute_value_id: string;
  attribute_name?: string | null;
  attribute_value?: string | null;
}

export interface ApiProductDetail extends ApiProduct {
  category?: ApiCategory | null;
  brand?: ApiBrand | null;
  variants: ApiProductVariant[];
  images: ApiProductImage[];
  tags: Array<{ id: string; name: string; slug: string }>;
  product_attributes: ApiProductAttribute[];
}

export interface ApiProductListResponse {
  items: ApiProduct[];
  meta: ApiPaginationMeta;
}

export interface ProductQueryParams {
  q?: string;
  category_id?: string;
  category_slug?: string;
  brand_id?: string;
  brand_slug?: string;
  status?: string;
  is_active?: boolean;
  is_featured?: boolean;
  min_price?: number;
  max_price?: number;
  sort_by?: "name" | "price" | "created_at" | "updated_at" | "position";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

export interface SearchSuggestionItem {
  text: string;
  score?: number | null;
  product_id?: string | null;
  image_url?: string | null;
}

export interface SuggestApiResponse {
  suggestions: SearchSuggestionItem[];
  query: string;
}

export interface ApiReviewUser {
  id: string;
  display_name?: string | null;
}

export interface ApiReviewItem {
  id: string;
  user: ApiReviewUser;
  product_id: string;
  rating: number;
  title?: string | null;
  body?: string | null;
  pros?: string[] | null;
  cons?: string[] | null;
  is_verified_purchase: boolean;
  helpful_count: number;
  unhelpful_count: number;
  created_at: string;
}

export interface ApiReviewStats {
  average_rating: number;
  total_reviews: number;
  distribution: {
    star_1: number;
    star_2: number;
    star_3: number;
    star_4: number;
    star_5: number;
  };
  verified_count: number;
}

export interface ApiReviewListResponse {
  reviews: ApiReviewItem[];
  total: number;
  page: number;
  size: number;
  total_pages: number;
  stats: ApiReviewStats;
}

export interface CreateReviewInput {
  product_id: string;
  rating: number;
  title?: string;
  body?: string;
  pros?: string[];
  cons?: string[];
}

/* -------------------------------------------------------------------------- */
/*                               API Operations                               */
/* -------------------------------------------------------------------------- */

export async function fetchCategories(params?: {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}): Promise<ApiCategoryListResponse> {
  const { data } = await apiClient.get<ApiCategoryListResponse>(
    "/catalog/categories",
    { params },
  );
  return data;
}

export async function fetchBrands(params?: {
  is_active?: boolean;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<ApiBrandListResponse> {
  const { data } = await apiClient.get<ApiBrandListResponse>("/catalog/brands", {
    params,
  });
  return data;
}

export async function fetchProducts(
  params?: ProductQueryParams,
): Promise<ApiProductListResponse> {
  const { data } = await apiClient.get<ApiProductListResponse>(
    "/catalog/products",
    { params },
  );
  return data;
}

export async function fetchProductBySlug(
  slug: string,
): Promise<ApiProductDetail> {
  try {
    const { data } = await apiClient.get<ApiProductDetail>(
      `/catalog/products/by-slug/${encodeURIComponent(slug)}`,
    );
    return data;
  } catch (error) {
    // If slug lookup fails, attempt fetching by ID if it's a valid UUID
    const isUuid =
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
        slug,
      );
    if (isUuid) {
      const { data } = await apiClient.get<ApiProductDetail>(
        `/catalog/products/${slug}`,
      );
      return data;
    }
    throw error;
  }
}

export async function fetchProductById(id: string): Promise<ApiProductDetail> {
  const { data } = await apiClient.get<ApiProductDetail>(
    `/catalog/products/${id}`,
  );
  return data;
}

export async function fetchSearchSuggestions(
  q: string,
  size: number = 6,
): Promise<SuggestApiResponse> {
  const { data } = await apiClient.get<SuggestApiResponse>("/search/suggest", {
    params: { q, size },
  });
  return data;
}

export async function fetchReviews(
  productId: string,
  params?: { sort?: string; page?: number; size?: number },
): Promise<ApiReviewListResponse> {
  try {
    const { data } = await apiClient.get<ApiReviewListResponse>("/reviews", {
      params: { product_id: productId, ...params },
    });
    return data;
  } catch (err) {
    // Fallback to product-scoped route if root reviews route failed
    const { data } = await apiClient.get<ApiReviewListResponse>(
      `/reviews/products/${productId}/reviews`,
      { params },
    );
    return data;
  }
}

export async function postReview(
  review: CreateReviewInput,
): Promise<ApiReviewItem> {
  try {
    const { data } = await apiClient.post<ApiReviewItem>("/reviews", review);
    return data;
  } catch (err) {
    // Fallback to product-scoped route
    const { data } = await apiClient.post<ApiReviewItem>(
      `/reviews/products/${review.product_id}/reviews`,
      review,
    );
    return data;
  }
}

export async function addToWishlistApi(
  productId: string,
): Promise<{ id: string; product_id: string }> {
  const { data } = await apiClient.post<{ id: string; product_id: string }>(
    "/wishlist/items",
    { product_id: productId },
  );
  return data;
}

export async function removeFromWishlistApi(
  productId: string,
): Promise<void> {
  await apiClient.delete(`/wishlist/items/${productId}`);
}

export async function checkWishlistApi(
  productId: string,
): Promise<{ in_wishlist: boolean }> {
  const { data } = await apiClient.get<{ in_wishlist: boolean }>(
    `/wishlist/check/${productId}`,
  );
  return data;
}

export * from "./blog";
