/**
 * Search Utilities, Persian Normalization & History Manager (Sprint 5)
 */

import { normalizeDigits } from "./dynamic-fields";

export const SEARCH_HISTORY_KEY = "karta_recent_searches";
export const MAX_HISTORY_ITEMS = 8;

export type SearchSortOption = "newest" | "price_asc" | "price_desc" | "popular";

export interface SearchFilters {
  query: string;
  category?: string;
  minPrice?: number;
  maxPrice?: number;
  inStockOnly?: boolean;
  sortBy?: SearchSortOption;
}

/**
 * Normalizes Persian search terms:
 * - Unifies Arabic/Persian letters (ی/ي, ک/ك, ه/ة)
 * - Standardizes Zero-Width Non-Joiner (ZWNJ / نیم‌فاصله: ‌)
 * - Converts Persian/Arabic digits to ASCII for uniform matching
 * - Collapses redundant whitespace
 */
export function normalizePersianSearch(term: string | null | undefined): string {
  if (!term) return "";

  let str = String(term);

  // Convert Persian/Arabic digits
  str = normalizeDigits(str);

  // Unify Arabic specific letters with standard Persian
  str = str
    .replace(/ي/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/ة/g, "ه")
    .replace(/[ً-ٟ]/g, ""); // Remove Arabic diacritics (harakat)

  // Standardize multiple spaces and collapse space around zero-width non-joiner
  str = str
    .replace(/\s*‌\s*/g, "‌") // Clean whitespace around ZWNJ
    .replace(/[​‍‎‏﻿]/g, "") // Remove unwanted invisible control chars
    .replace(/\s+/g, " ") // Collapse multiple spaces
    .trim();

  return str;
}

/**
 * Generates an alternative query variant swapping spaces and ZWNJ (‌)
 * for flexible fuzzy matching of compound Persian words (e.g. "هدفون بی سیم" vs "هدفون بی‌سیم").
 */
export function getFuzzySearchVariants(query: string): string[] {
  const normalized = normalizePersianSearch(query);
  if (!normalized) return [];

  const variants = new Set<string>();
  variants.add(normalized);

  // Variant with space instead of ZWNJ
  if (normalized.includes("‌")) {
    variants.add(normalized.replace(/‌/g, " "));
  }

  // Variant with ZWNJ between words
  if (normalized.includes(" ")) {
    variants.add(normalized.replace(/ /g, "‌"));
  }

  return Array.from(variants);
}

/**
 * Safe retrieval of localStorage across browser and test environments.
 */
function getStorage(): Storage | null {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      return window.localStorage;
    }
    if (typeof localStorage !== "undefined") {
      return localStorage;
    }
  } catch {
    return null;
  }
  return null;
}

/**
 * Safe client-side retrieval of search history from localStorage.
 */
export function getSearchHistory(): string[] {
  const storage = getStorage();
  if (!storage) return [];
  try {
    const raw = storage.getItem(SEARCH_HISTORY_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((t) => typeof t === "string" && t.trim()) : [];
  } catch {
    return [];
  }
}

/**
 * Adds a query to search history, deduplicating and maintaining newest on top.
 */
export function addSearchHistory(query: string): string[] {
  const clean = normalizePersianSearch(query);
  if (!clean || clean.length < 2) return getSearchHistory();
  const storage = getStorage();
  if (!storage) return [clean];

  try {
    const existing = getSearchHistory();
    const filtered = existing.filter((item) => item.toLowerCase() !== clean.toLowerCase());
    const updated = [clean, ...filtered].slice(0, MAX_HISTORY_ITEMS);
    storage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
    return updated;
  } catch {
    return [clean];
  }
}

/**
 * Removes a single entry from search history.
 */
export function removeSearchHistory(query: string): string[] {
  const storage = getStorage();
  if (!storage) return [];
  try {
    const existing = getSearchHistory();
    const updated = existing.filter((item) => item.toLowerCase() !== query.toLowerCase().trim());
    storage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
    return updated;
  } catch {
    return [];
  }
}

/**
 * Clears entire search history.
 */
export function clearSearchHistory(): void {
  const storage = getStorage();
  if (!storage) return;
  try {
    storage.removeItem(SEARCH_HISTORY_KEY);
  } catch {
    // ignore
  }
}
