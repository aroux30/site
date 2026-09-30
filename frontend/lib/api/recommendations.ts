import apiClient from "./client";

// --- Types ---

export interface ProductRecommendation {
  id: number;
  title: string;
  slug: string;
  price: number;
  original_price?: number;
  image_url?: string;
  rating?: number;
  review_count?: number;
}

// --- API ---

export const recommendationsApi = {
  /** محصولات مشابه */
  getSimilar: async (productId: number, limit = 8): Promise<ProductRecommendation[]> => {
    const res = await apiClient.get<{ items: ProductRecommendation[] }>(
      `/recommendations/similar/${productId}`,
      { params: { limit } },
    );
    return res.data.items ?? (res.data as unknown as ProductRecommendation[]);
  },

  /** اغلب با هم خریده می‌شوند */
  getFrequentlyBoughtTogether: async (productId: number): Promise<ProductRecommendation[]> => {
    const res = await apiClient.get<{ items: ProductRecommendation[] }>(
      `/recommendations/frequently-bought-together/${productId}`,
    );
    return res.data.items ?? (res.data as unknown as ProductRecommendation[]);
  },

  /** محصولات ترند */
  getTrending: async (limit = 12): Promise<ProductRecommendation[]> => {
    const res = await apiClient.get<{ items: ProductRecommendation[] }>(
      "/recommendations/trending",
      { params: { limit } },
    );
    return res.data.items ?? (res.data as unknown as ProductRecommendation[]);
  },

  /** پیشنهاد شخصی‌سازی‌شده */
  getForYou: async (limit = 12): Promise<ProductRecommendation[]> => {
    const res = await apiClient.get<{ items: ProductRecommendation[] }>(
      "/recommendations/for-you",
      { params: { limit } },
    );
    return res.data.items ?? (res.data as unknown as ProductRecommendation[]);
  },
};
