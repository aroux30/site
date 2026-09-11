import apiClient from "./client";

export interface BlogPostCategory {
  id: string;
  name: string;
  slug: string;
  created_at?: string;
  updated_at?: string;
  post_count?: number;
}

export interface BlogPost {
  id: string;
  author_id: string;
  author_name?: string;
  title: string;
  slug: string;
  excerpt?: string;
  content?: string;
  cover_image_url?: string;
  status: "draft" | "published" | "archived";
  published_at?: string;
  category_id?: string;
  category?: BlogPostCategory;
  reading_time?: number;
  view_count: number;
  related_posts?: BlogPost[];
  seo?: {
    title?: string;
    description?: string;
    canonical_url?: string;
    og_title?: string;
    og_description?: string;
    og_image?: string;
    schema_markup?: Record<string, unknown>;
  };
  created_at: string;
  updated_at: string;
}

export interface BlogListResponse {
  items: BlogPost[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface BlogQueryParams {
  category?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

/* -------------------------------------------------------------------------- */
/*                               Fallback Data                                */
/* -------------------------------------------------------------------------- */

export async function fetchBlogPosts(
  params?: BlogQueryParams,
): Promise<BlogListResponse> {
  try {
    const { data } = await apiClient.get<BlogListResponse>("/blog/posts", {
      params,
    });
    if (data && data.items) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch blog posts from API", error);
    }
  }
  // Honest empty response — the page renders its empty state.
  const page = params?.page || 1;
  const pageSize = params?.page_size || 9;
  return {
    items: [],
    total: 0,
    page,
    page_size: pageSize,
    total_pages: 1,
    has_next: false,
    has_prev: false,
  };
}

export async function fetchBlogPostBySlug(slug: string): Promise<BlogPost | null> {
  try {
    const { data } = await apiClient.get<BlogPost>(`/blog/posts/${slug}`);
    if (data && data.id) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch post from API", { slug, error });
    }
  }
  return null;
}

export async function fetchBlogCategories(): Promise<BlogPostCategory[]> {
  try {
    const { data } = await apiClient.get<BlogPostCategory[]>("/blog/categories");
    if (Array.isArray(data) && data.length > 0) {
      return data;
    }
  } catch (error) {
    if (process.env.NODE_ENV === "development") {
      console.warn("Could not fetch blog categories from API", error);
    }
  }
  return [];
}

