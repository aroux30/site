export interface Product {
  id: string;
  title: string;
  slug: string;
  description: string;
  shortDescription?: string;
  price: number;
  originalPrice?: number;
  sku: string;
  barcode?: string;
  stock: number;
  isActive: boolean;
  isFeatured: boolean;

  // Media
  images: ProductImage[];
  thumbnail?: string;

  // Classification
  categoryId: string;
  category?: ProductCategory;
  brandId?: string;
  brand?: ProductBrand;
  tags: string[];

  // Variants
  variants: ProductVariant[];
  attributes: ProductAttribute[];

  // Specs & details
  type?: string;
  weight?: string | number;
  dimensions?: string;
  specifications?: Record<string, string>;

  // Reviews
  rating: number;
  reviewCount: number;

  // SEO
  metaTitle?: string;
  metaDescription?: string;

  // Timestamps
  createdAt: string;
  updatedAt: string;
}

export interface ProductImage {
  id: string;
  url: string;
  alt: string;
  order: number;
}

export interface ProductCategory {
  id: string;
  name: string;
  slug: string;
  parentId?: string;
  image?: string;
  description?: string;
  productCount?: number;
  children?: ProductCategory[];
}

export interface ProductBrand {
  id: string;
  name: string;
  slug: string;
  logo?: string;
}

export interface ProductVariant {
  id: string;
  name: string;
  sku: string;
  price: number;
  originalPrice?: number;
  stock: number;
  attributes: Record<string, string>;
}

export interface ProductAttribute {
  name: string;
  value: string;
  group?: string;
}

export interface ProductReview {
  id: string;
  userId: string;
  userName: string;
  rating: number;
  title: string;
  body: string;
  pros: string[];
  cons: string[];
  isVerifiedPurchase: boolean;
  helpfulCount: number;
  createdAt: string;
}

export interface ProductListItem {
  id: string;
  title: string;
  slug: string;
  price: number;
  originalPrice?: number;
  thumbnail?: string;
  category: string;
  brand?: string;
  rating: number;
  reviewCount: number;
  inStock: boolean;
  isFeatured: boolean;
}
