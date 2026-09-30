"use client";

import { useState, useCallback, useEffect, useMemo, useTransition } from "react";
import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { normalizePersianSearch } from "@/lib/search";
import {
  fetchFacetedSearch,
  type FacetedSearchRequest,
  type FacetedSearchResponse,
  type FacetedSearchHit,
  type FacetApi,
} from "@/lib/api/services";
import { queryKeys } from "@/lib/api/queries";

/* -------------------------------------------------------------------------- */
/*                          Filter state definition                            */
/* -------------------------------------------------------------------------- */

export interface FacetedFilterState {
  q: string;
  category: string | null;
  brand: string | null;
  minPrice: number | null;
  maxPrice: number | null;
  minRating: number | null;
  inStockOnly: boolean;
  attributes: Record<string, string[]>;
  sort: "relevance" | "price_asc" | "price_desc" | "rating" | "newest";
  page: number;
  size: number;
}

const DEFAULT_FILTERS: FacetedFilterState = {
  q: "",
  category: null,
  brand: null,
  minPrice: null,
  maxPrice: null,
  minRating: null,
  inStockOnly: false,
  attributes: {},
  sort: "relevance",
  page: 1,
  size: 20,
};

/* -------------------------------------------------------------------------- */
/*                          URL ↔ State helpers                                 */
/* -------------------------------------------------------------------------- */

function parseFiltersFromParams(searchParams: URLSearchParams): FacetedFilterState {
  const q = searchParams.get("q") || "";
  const category =
    searchParams.get("category_id") || searchParams.get("category") || null;
  const brand =
    searchParams.get("brand") || searchParams.get("brand_id") || null;
  const minPriceRaw = searchParams.get("min_price");
  const maxPriceRaw = searchParams.get("max_price");
  const minRatingRaw = searchParams.get("min_rating");
  const inStockOnly = searchParams.get("in_stock") === "true";
  const sortRaw = searchParams.get("sort") || "relevance";
  const pageRaw = searchParams.get("page");

  // Dynamic attributes: attr_color=red,blue → { color: ["red", "blue"] }
  const attributes: Record<string, string[]> = {};
  searchParams.forEach((val, key) => {
    if (key.startsWith("attr_")) {
      const attrName = key.slice(5);
      attributes[attrName] = val.split(",").filter(Boolean);
    }
  });

  return {
    q,
    category,
    brand,
    minPrice: minPriceRaw ? parseInt(minPriceRaw, 10) : null,
    maxPrice: maxPriceRaw ? parseInt(maxPriceRaw, 10) : null,
    minRating: minRatingRaw ? parseFloat(minRatingRaw) : null,
    inStockOnly,
    attributes,
    sort: sortRaw as FacetedFilterState["sort"],
    page: pageRaw ? Math.max(1, parseInt(pageRaw, 10)) : 1,
    size: 20,
  };
}

function filtersToSearchParams(state: FacetedFilterState): URLSearchParams {
  const params = new URLSearchParams();

  if (state.q.trim()) params.set("q", state.q.trim());
  if (state.category) params.set("category_id", state.category);
  if (state.brand) params.set("brand", state.brand);
  if (state.minPrice !== null && state.minPrice > 0)
    params.set("min_price", String(state.minPrice));
  if (state.maxPrice !== null)
    params.set("max_price", String(state.maxPrice));
  if (state.minRating !== null)
    params.set("min_rating", String(state.minRating));
  if (state.inStockOnly) params.set("in_stock", "true");
  if (state.sort !== "relevance") params.set("sort", state.sort);
  if (state.page > 1) params.set("page", String(state.page));

  Object.entries(state.attributes).forEach(([attr, vals]) => {
    if (vals.length > 0) params.set(`attr_${attr}`, vals.join(","));
  });

  return params;
}

/* -------------------------------------------------------------------------- */
/*                    Build the API request from filter state                   */
/* -------------------------------------------------------------------------- */

function buildApiRequest(
  state: FacetedFilterState,
  debouncedQuery: string,
): FacetedSearchRequest {
  const filters: Record<string, string[]> = {};

  if (state.category) filters.category_id = [state.category];
  if (state.brand) filters.brand = [state.brand];
  if (state.minRating !== null) filters.rating = [String(state.minRating)];
  if (state.inStockOnly) filters.in_stock = ["true"];

  // Dynamic attributes
  Object.entries(state.attributes).forEach(([attrName, vals]) => {
    if (vals.length > 0) filters[`attr:${attrName}`] = vals;
  });

  const priceRange =
    state.minPrice !== null || state.maxPrice !== null
      ? {
          min: state.minPrice ?? undefined,
          max: state.maxPrice ?? undefined,
        }
      : null;

  return {
    query: normalizePersianSearch(debouncedQuery) || "",
    filters,
    price_range: priceRange,
    page: state.page,
    size: state.size,
    sort_by: state.sort,
  };
}

/* -------------------------------------------------------------------------- */
/*                                Main hook                                    */
/* -------------------------------------------------------------------------- */

export function useFacetedSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  // Parse initial state from URL
  const parsedFilters = useMemo(
    () => parseFiltersFromParams(searchParams),
    [searchParams],
  );

  const [filters, setFilters] = useState<FacetedFilterState>(parsedFilters);
  const [debouncedQuery, setDebouncedQuery] = useState(filters.q);

  // Sync from URL when searchParams change externally
  useEffect(() => {
    setFilters(parsedFilters);
    setDebouncedQuery(parsedFilters.q);
  }, [parsedFilters]);

  // Debounce the search query (300ms)
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(filters.q), 300);
    return () => clearTimeout(timer);
  }, [filters.q]);

  // Push filter state to URL
  const syncToUrl = useCallback(
    (nextState: FacetedFilterState) => {
      startTransition(() => {
        const params = filtersToSearchParams(nextState);
        const qs = params.toString();
        router.push(`${pathname}${qs ? `?${qs}` : ""}`, { scroll: false });
      });
    },
    [pathname, router],
  );

  // Build API request payload
  const apiRequest = useMemo(
    () => buildApiRequest(filters, debouncedQuery),
    [filters, debouncedQuery],
  );

  // TanStack Query — calls POST /search/products/faceted
  const { data, isLoading, isFetching, error, refetch } =
    useQuery<FacetedSearchResponse>({
      queryKey: queryKeys.facetedSearch.query(apiRequest),
      queryFn: () => fetchFacetedSearch(apiRequest),
      staleTime: 30_000,
    });

  // ── Action dispatchers ──────────────────────────────────────────────

  const setQueryText = useCallback((q: string) => {
    setFilters((prev) => ({ ...prev, q, page: 1 }));
  }, []);

  const applyQueryText = useCallback(
    (q: string) => {
      setFilters((prev) => {
        const next = { ...prev, q, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const setCategory = useCallback(
    (catId: string | null) => {
      setFilters((prev) => {
        const next = { ...prev, category: catId, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const setBrand = useCallback(
    (brandId: string | null) => {
      setFilters((prev) => {
        const next = { ...prev, brand: brandId, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const setPriceRange = useCallback(
    (min: number | null, max: number | null) => {
      setFilters((prev) => {
        const next = { ...prev, minPrice: min, maxPrice: max, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const setRating = useCallback(
    (rating: number | null) => {
      setFilters((prev) => {
        const next = { ...prev, minRating: rating, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const toggleInStockOnly = useCallback(() => {
    setFilters((prev) => {
      const next = { ...prev, inStockOnly: !prev.inStockOnly, page: 1 };
      syncToUrl(next);
      return next;
    });
  }, [syncToUrl]);

  const toggleAttribute = useCallback(
    (attrName: string, attrVal: string) => {
      setFilters((prev) => {
        const currentVals = prev.attributes[attrName] || [];
        const exists = currentVals.includes(attrVal);
        const updated = exists
          ? currentVals.filter((v) => v !== attrVal)
          : [...currentVals, attrVal];

        const nextAttributes = { ...prev.attributes };
        if (updated.length > 0) {
          nextAttributes[attrName] = updated;
        } else {
          delete nextAttributes[attrName];
        }

        const next = { ...prev, attributes: nextAttributes, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const setSort = useCallback(
    (sort: FacetedFilterState["sort"]) => {
      setFilters((prev) => {
        const next = { ...prev, sort, page: 1 };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const setPage = useCallback(
    (page: number) => {
      setFilters((prev) => {
        const next = { ...prev, page };
        syncToUrl(next);
        return next;
      });
    },
    [syncToUrl],
  );

  const resetFilters = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setDebouncedQuery("");
    syncToUrl(DEFAULT_FILTERS);
  }, [syncToUrl]);

  // ── Derived values ──────────────────────────────────────────────────

  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (filters.q.trim()) count++;
    if (filters.category) count++;
    if (filters.brand) count++;
    if (filters.minPrice !== null || filters.maxPrice !== null) count++;
    if (filters.minRating !== null) count++;
    if (filters.inStockOnly) count++;
    Object.values(filters.attributes).forEach((v) => {
      if (v.length > 0) count++;
    });
    return count;
  }, [filters]);

  return {
    // State
    filters,
    facets: data?.facets ?? [],
    results: data?.hits ?? [],
    total: data?.total ?? 0,
    totalPages: data?.total_pages ?? 0,
    page: filters.page,

    // Loading / error
    isLoading: isLoading || isPending,
    isFetching,
    error,
    // The search backend is a separate service; when it is unreachable the
    // API answers 200 with no hits, so this must be surfaced or an outage
    // reads as "no products found".
    degraded: data?.degraded ?? false,

    // Derived
    activeFiltersCount,

    // Actions
    setQueryText,
    applyQueryText,
    setCategory,
    setBrand,
    setPriceRange,
    setRating,
    toggleInStockOnly,
    toggleAttribute,
    setSort,
    setPage,
    resetFilters,
    refetch,
  };
}
