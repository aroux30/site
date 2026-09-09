import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import {
  fetchProducts,
  fetchProductBySlug,
  fetchCategories,
  fetchBrands,
  fetchReviews,
  postReview,
  addToWishlistApi,
  removeFromWishlistApi,
  type ProductQueryParams,
  type ApiProductListResponse,
  type ApiProductDetail,
  type ApiCategoryListResponse,
  type ApiBrandListResponse,
  type ApiReviewListResponse,
  type ApiReviewItem,
  type CreateReviewInput,
} from "./services";
import {
  fetchBlogPosts,
  fetchBlogPostBySlug,
  type BlogQueryParams,
  type BlogListResponse,
  type BlogPost,
} from "./blog";
import apiClient from "./client";

/* -------------------------------------------------------------------------- */
/*                            Query Key Factory                                */
/* -------------------------------------------------------------------------- */

export const queryKeys = {
  products: {
    all: ["products"] as const,
    list: (params?: ProductQueryParams) =>
      ["products", "list", params] as const,
    detail: (slug: string) => ["products", "detail", slug] as const,
  },
  categories: {
    all: ["categories"] as const,
    tree: ["categories", "tree"] as const,
  },
  brands: {
    all: ["brands"] as const,
  },
  cart: {
    current: ["cart"] as const,
  },
  orders: {
    all: ["orders"] as const,
    detail: (id: string) => ["orders", id] as const,
  },
  wishlist: {
    current: ["wishlist"] as const,
  },
  notifications: {
    all: ["notifications"] as const,
  },
  wallet: {
    balance: ["wallet"] as const,
    transactions: ["wallet", "transactions"] as const,
  },
  reviews: {
    byProduct: (productId: string) => ["reviews", productId] as const,
  },
  blog: {
    posts: (params?: BlogQueryParams) => ["blog", "posts", params] as const,
    post: (slug: string) => ["blog", "post", slug] as const,
    categories: ["blog", "categories"] as const,
  },
};

/* -------------------------------------------------------------------------- */
/*                            Query Hooks                                      */
/* -------------------------------------------------------------------------- */

/** Fetch paginated product list. staleTime: 60s */
export function useProducts(params?: ProductQueryParams) {
  return useQuery<ApiProductListResponse>({
    queryKey: queryKeys.products.list(params),
    queryFn: () => fetchProducts(params),
    staleTime: 60_000,
  });
}

/** Fetch a single product by slug. staleTime: 5min */
export function useProduct(slug: string) {
  return useQuery<ApiProductDetail>({
    queryKey: queryKeys.products.detail(slug),
    queryFn: () => fetchProductBySlug(slug),
    staleTime: 5 * 60_000,
    enabled: !!slug,
  });
}

/** Fetch product categories. staleTime: 10min */
export function useCategories(params?: {
  is_active?: boolean;
  page?: number;
  page_size?: number;
}) {
  return useQuery<ApiCategoryListResponse>({
    queryKey: queryKeys.categories.all,
    queryFn: () => fetchCategories(params),
    staleTime: 10 * 60_000,
  });
}

/** Fetch brands. staleTime: 10min */
export function useBrands(params?: {
  is_active?: boolean;
  q?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery<ApiBrandListResponse>({
    queryKey: queryKeys.brands.all,
    queryFn: () => fetchBrands(params),
    staleTime: 10 * 60_000,
  });
}

/** Fetch cart. staleTime: 30s, refetchOnWindowFocus: true */
export function useCart() {
  return useQuery({
    queryKey: queryKeys.cart.current,
    queryFn: async () => {
      const { data } = await apiClient.get("/cart");
      return data;
    },
    staleTime: 30_000,
    refetchOnWindowFocus: true,
  });
}

/** Fetch orders. staleTime: 60s */
export function useOrders(params?: {
  page?: number;
  page_size?: number;
  status?: string;
}) {
  return useQuery({
    queryKey: queryKeys.orders.all,
    queryFn: async () => {
      const { data } = await apiClient.get("/orders", { params });
      return data;
    },
    staleTime: 60_000,
  });
}

/** Fetch wishlist */
export function useWishlist() {
  return useQuery({
    queryKey: queryKeys.wishlist.current,
    queryFn: async () => {
      const { data } = await apiClient.get("/wishlist");
      return data;
    },
  });
}

/** Fetch wallet balance */
export function useWallet() {
  return useQuery({
    queryKey: queryKeys.wallet.balance,
    queryFn: async () => {
      const { data } = await apiClient.get("/wallet");
      return data;
    },
  });
}

/** Fetch notifications */
export function useNotifications() {
  return useQuery({
    queryKey: queryKeys.notifications.all,
    queryFn: async () => {
      const { data } = await apiClient.get("/notifications");
      return data;
    },
  });
}

/** Fetch reviews by product ID */
export function useReviews(
  productId: string,
  params?: { sort?: string; page?: number; size?: number },
) {
  return useQuery<ApiReviewListResponse>({
    queryKey: queryKeys.reviews.byProduct(productId),
    queryFn: () => fetchReviews(productId, params),
    enabled: !!productId,
  });
}

/** Fetch paginated blog posts */
export function useBlogPosts(params?: BlogQueryParams) {
  return useQuery<BlogListResponse>({
    queryKey: queryKeys.blog.posts(params),
    queryFn: () => fetchBlogPosts(params),
  });
}

/** Fetch a single blog post by slug */
export function useBlogPost(slug: string) {
  return useQuery<BlogPost>({
    queryKey: queryKeys.blog.post(slug),
    queryFn: () => fetchBlogPostBySlug(slug),
    enabled: !!slug,
  });
}

/* -------------------------------------------------------------------------- */
/*                            Mutation Hooks                                   */
/* -------------------------------------------------------------------------- */

/** POST /cart/items — add item to cart, invalidates cart query */
export function useAddToCart() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (item: {
      product_id: string;
      variant_id?: string;
      quantity?: number;
    }) => {
      const { data } = await apiClient.post("/cart/items", item);
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cart.current });
    },
  });
}

/** PATCH /cart/items/{id} — update cart item, invalidates cart */
export function useUpdateCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      id,
      quantity,
    }: {
      id: string;
      quantity: number;
    }) => {
      const { data } = await apiClient.patch(`/cart/items/${id}`, { quantity });
      return data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cart.current });
    },
  });
}

/** DELETE /cart/items/{id} — remove cart item, invalidates cart */
export function useRemoveCartItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/cart/items/${id}`);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.cart.current });
    },
  });
}

/** POST/DELETE /wishlist/items — toggle wishlist item, invalidates wishlist */
export function useToggleWishlist() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      productId,
      isWishlisted,
    }: {
      productId: string;
      isWishlisted: boolean;
    }) => {
      if (isWishlisted) {
        await removeFromWishlistApi(productId);
      } else {
        await addToWishlistApi(productId);
      }
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.wishlist.current,
      });
    },
  });
}

/** POST /reviews — submit a review, invalidates reviews for that product */
export function useSubmitReview() {
  const queryClient = useQueryClient();
  return useMutation<ApiReviewItem, unknown, CreateReviewInput>({
    mutationFn: (review: CreateReviewInput) => postReview(review),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.reviews.byProduct(variables.product_id),
      });
    },
  });
}
