"use client";

import React, { useState, useEffect, useRef, useCallback, useId } from "react";
import { useRouter } from "next/navigation";
import {
  Search,
  X,
  History,
  Trash2,
  ArrowLeft,
  Loader2,
  TrendingUp,
  FileText,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  normalizePersianSearch,
  getSearchHistory,
  addSearchHistory,
  removeSearchHistory,
  clearSearchHistory,
} from "@/lib/search";
import {
  fetchSearchSuggestions,
  fetchContentSuggestions,
  contentHref,
  type SearchSuggestionItem,
} from "@/lib/api/services";

export interface LiveSearchBarProps {
  placeholder?: string;
  className?: string;
  onSearchSubmit?: (query: string) => void;
  autoFocus?: boolean;
}

type ActiveOption = {
  source: "history" | "suggestion";
  index: number;
};

function HighlightedSuggestion({ text, query }: { text: string; query: string }) {
  const normalizedQuery = normalizePersianSearch(query);
  const normalizedQueryLower = normalizedQuery.toLocaleLowerCase();
  const normalizedText = normalizePersianSearch(text);
  const matchStart = normalizedText
    .toLocaleLowerCase()
    .indexOf(normalizedQueryLower);

  if (matchStart < 0 || !normalizedQuery) {
    return <>{text}</>;
  }

  const matchEnd = matchStart + normalizedQuery.length;
  const matchedText = text.slice(matchStart, matchEnd);

  // Only use normalized offsets when they still identify the original substring.
  if (normalizePersianSearch(matchedText).toLocaleLowerCase() !== normalizedQueryLower) {
    return <>{text}</>;
  }

  return (
    <>
      {text.slice(0, matchStart)}
      <mark className="rounded-sm bg-primary/15 px-0.5 text-inherit">
        {matchedText}
      </mark>
      {text.slice(matchEnd)}
    </>
  );
}

export function LiveSearchBar({
  placeholder = "جستجوی نام کالا، برند یا دسته‌بندی...",
  className = "",
  onSearchSubmit,
  autoFocus = false,
}: LiveSearchBarProps) {
  const router = useRouter();
  const containerRef = useRef<HTMLDivElement>(null);
  const comboboxId = useId();
  const listboxId = `${comboboxId}-listbox`;

  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestionError, setSuggestionError] = useState(false);
  const [suggestions, setSuggestions] = useState<SearchSuggestionItem[]>([]);
  const [history, setHistory] = useState<string[]>([]);
  const [activeOption, setActiveOption] = useState<ActiveOption | null>(null);

  const refreshHistory = useCallback(() => {
    setHistory(getSearchHistory());
  }, []);

  const closeDropdown = useCallback(() => {
    setIsOpen(false);
    setActiveOption(null);
  }, []);

  const getOptionId = useCallback(
    (source: ActiveOption["source"], index: number) =>
      `${comboboxId}-${source}-option-${index}`,
    [comboboxId],
  );

  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  useEffect(() => {
    const clean = normalizePersianSearch(query);
    if (!clean || clean.length < 2) {
      setSuggestions([]);
      setSuggestionError(false);
      setIsLoading(false);
      return;
    }

    let isCurrent = true;
    setSuggestions([]);
    setSuggestionError(false);
    setIsLoading(true);
    const timer = setTimeout(async () => {
      try {
        // Products and content are fetched together: /search/suggest only
        // covers the catalogue, so a query for an article name suggested
        // nothing at all. One failing half must not blank the other, hence
        // the independent catch.
        const [products, content] = await Promise.allSettled([
          fetchSearchSuggestions(clean, 6),
          fetchContentSuggestions(clean, 4),
        ]);
        if (!isCurrent) return;
        const merged: SearchSuggestionItem[] = [];
        if (products.status === "fulfilled") {
          merged.push(...(products.value.suggestions ?? []));
        }
        if (content.status === "fulfilled") {
          for (const s of content.value.suggestions ?? []) {
            if (s.slug) {
              merged.push({
                text: s.text,
                score: s.score,
                content_href: contentHref({ type: s.type, slug: s.slug }),
              });
            }
          }
        }
        if (products.status === "rejected" && content.status === "rejected" && isCurrent) {
          setSuggestionError(true);
        } else {
          setSuggestions(merged);
        }
      } finally {
        if (isCurrent) {
          setIsLoading(false);
        }
      }
    }, 280);

    return () => {
      isCurrent = false;
      clearTimeout(timer);
    };
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        closeDropdown();
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [closeDropdown]);

  const executeSearch = (searchTerm: string) => {
    const clean = normalizePersianSearch(searchTerm);
    if (!clean) return;

    const updated = addSearchHistory(clean);
    setHistory(updated);
    closeDropdown();

    if (onSearchSubmit) {
      onSearchSubmit(clean);
    } else {
      router.push(`/search?q=${encodeURIComponent(clean)}`);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    executeSearch(query);
  };

  const handleClearHistoryItem = (item: string) => {
    const updated = removeSearchHistory(item);
    setHistory(updated);
    setActiveOption(null);
  };

  const handleClearAllHistory = () => {
    clearSearchHistory();
    setHistory([]);
    setActiveOption(null);
  };

  const cleanQuery = normalizePersianSearch(query);
  const showHistory = isOpen && cleanQuery.length < 2 && history.length > 0;
  const suggestionPanelOpen = isOpen && cleanQuery.length >= 2;
  const showSuggestionList =
    suggestionPanelOpen &&
    !isLoading &&
    !suggestionError &&
    suggestions.length > 0;
  const optionSource = cleanQuery.length < 2 ? "history" : "suggestion";
  const optionTexts =
    optionSource === "history"
      ? history
      : showSuggestionList
        ? suggestions.map((item) => item.text)
        : [];
  const showNoSuggestions =
    suggestionPanelOpen &&
    !isLoading &&
    !suggestionError &&
    suggestions.length === 0;
  const hasListbox = showHistory || showSuggestionList;
  const isExpanded = showHistory || suggestionPanelOpen;
  const activeOptionId =
    activeOption && activeOption.source === optionSource && hasListbox
      ? getOptionId(activeOption.source, activeOption.index)
      : undefined;

  const moveActiveOption = (direction: "next" | "previous" | "first" | "last") => {
    if (!optionTexts.length) return;

    setIsOpen(true);
    setActiveOption((current) => {
      const currentIndex =
        current?.source === optionSource ? current.index : null;
      let index: number;

      switch (direction) {
        case "first":
          index = 0;
          break;
        case "last":
          index = optionTexts.length - 1;
          break;
        case "next":
          index = currentIndex === null ? 0 : (currentIndex + 1) % optionTexts.length;
          break;
        case "previous":
          index =
            currentIndex === null
              ? optionTexts.length - 1
              : (currentIndex - 1 + optionTexts.length) % optionTexts.length;
          break;
      }

      return { source: optionSource, index };
    });
  };

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    switch (event.key) {
      case "ArrowDown":
        if (optionTexts.length) {
          event.preventDefault();
          moveActiveOption("next");
        }
        break;
      case "ArrowUp":
        if (optionTexts.length) {
          event.preventDefault();
          moveActiveOption("previous");
        }
        break;
      case "Enter": {
        const activeText =
          activeOption?.source === optionSource
            ? optionTexts[activeOption.index]
            : undefined;
        if (activeText) {
          event.preventDefault();
          executeSearch(activeText);
        }
        break;
      }
      case "Escape":
        if (isOpen) {
          event.preventDefault();
          closeDropdown();
        }
        break;
    }
  };

  return (
    <div ref={containerRef} className={`relative w-full ${className}`} dir="rtl">
      <form onSubmit={handleSubmit} className="relative w-full">
        <Search className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          type="search"
          role="combobox"
          aria-autocomplete="list"
          aria-controls={hasListbox ? listboxId : undefined}
          aria-expanded={isExpanded}
          aria-activedescendant={activeOptionId}
          aria-busy={isLoading}
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            const nextQuery = e.target.value;
            const nextCleanQuery = normalizePersianSearch(nextQuery);
            setQuery(nextQuery);
            setIsOpen(true);
            setActiveOption(null);
            setSuggestions([]);
            setSuggestionError(false);
            setIsLoading(nextCleanQuery.length >= 2);
          }}
          onFocus={() => {
            refreshHistory();
            setIsOpen(true);
            setActiveOption(null);
          }}
          onKeyDown={handleInputKeyDown}
          autoFocus={autoFocus}
          className="h-11 w-full rounded-xl border-2 border-border bg-muted/30 ps-10 pe-10 text-sm transition-colors focus:border-primary focus:bg-background"
        />

        {isLoading ? (
          <Loader2 className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 animate-spin text-muted-foreground" />
        ) : query ? (
          <button
            type="button"
            onClick={() => {
              setQuery("");
              setSuggestions([]);
              setSuggestionError(false);
              setIsLoading(false);
              setActiveOption(null);
            }}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            title="پاک کردن متن"
            aria-label="پاک کردن متن جستجو"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null}
      </form>

      {isExpanded && (
        <div className="absolute top-full z-50 mt-2 w-full animate-in zoom-in-95 rounded-2xl border border-border bg-card p-2 shadow-2xl fade-in-0">
          {showHistory && (
            <div className="space-y-1">
              <div className="flex items-center justify-between border-b border-border/40 px-3 pb-2 py-2 text-xs font-semibold text-muted-foreground">
                <span className="flex items-center gap-1.5">
                  <History className="h-3.5 w-3.5 text-primary" />
                  تاریخچه جستجوهای اخیر
                </span>
                <button
                  type="button"
                  onClick={handleClearAllHistory}
                  className="flex items-center gap-1 text-[11px] text-destructive hover:underline"
                >
                  <Trash2 className="h-3 w-3" />
                  پاک کردن همه
                </button>
              </div>

              <ul id={listboxId} role="listbox" aria-label="تاریخچه جستجوهای اخیر" className="space-y-0.5 pt-1">
                {history.map((item, index) => {
                  const optionId = getOptionId("history", index);
                  const isActive = activeOptionId === optionId;

                  return (
                    <li key={item} role="presentation" className="flex items-center gap-1">
                      <button
                        id={optionId}
                        role="option"
                        aria-selected={isActive}
                        type="button"
                        onClick={() => executeSearch(item)}
                        className={`group flex min-w-0 flex-1 items-center gap-2 rounded-lg px-3 py-2 text-start text-xs font-medium transition-colors ${
                          isActive
                            ? "bg-primary/10 text-primary"
                            : "text-foreground hover:bg-muted/70"
                        }`}
                      >
                        <History className={`h-3 w-3 transition-colors ${isActive ? "text-primary" : "text-muted-foreground group-hover:text-primary"}`} />
                        <span className="truncate">{item}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleClearHistoryItem(item)}
                        className="rounded p-1 text-muted-foreground/60 transition-colors hover:text-destructive"
                        aria-label={`حذف ${item} از تاریخچه`}
                        title="حذف از تاریخچه"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {suggestionPanelOpen && (
            <div className="space-y-1">
              <div className="flex items-center gap-1.5 border-b border-border/40 px-3 pb-2 py-1.5 text-xs font-semibold text-muted-foreground">
                <TrendingUp className="h-3.5 w-3.5 text-primary" />
                پیشنهادات لحظه‌ای جستجو
              </div>

              {isLoading && (
                <div
                  role="status"
                  aria-live="polite"
                  className="flex items-center justify-center gap-2 px-3 py-4 text-xs text-muted-foreground"
                >
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  در حال بارگذاری پیشنهادات...
                </div>
              )}

              {suggestionError && (
                <div
                  role="status"
                  aria-live="polite"
                  className="px-3 py-3 text-center text-xs text-muted-foreground"
                >
                  دریافت پیشنهادات با خطا مواجه شد. برای جستجوی دقیق دکمه اینتر را بزنید.
                </div>
              )}

              {showSuggestionList && (
                <ul id={listboxId} role="listbox" aria-label="پیشنهادات لحظه‌ای جستجو" className="space-y-0.5 pt-1">
                  {suggestions.map((item, index) => {
                    const optionId = getOptionId("suggestion", index);
                    const isActive = activeOptionId === optionId;

                    return (
                      <li key={`${item.text}-${index}`} role="presentation">
                        <button
                          id={optionId}
                          role="option"
                          aria-selected={isActive}
                          type="button"
                          // A content hit navigates straight to the article or
                          // page; a product hit runs the normal search, which
                          // is what the results grid is built for.
                          onClick={() => {
                            if (item.content_href) {
                              router.push(item.content_href);
                              setIsOpen(false);
                            } else {
                              executeSearch(item.text);
                            }
                          }}
                          className={`group flex w-full items-center justify-between rounded-lg px-3 py-2 text-start text-xs font-medium transition-colors ${
                            isActive
                              ? "bg-primary/10 text-primary"
                              : "text-foreground hover:bg-muted/70"
                          }`}
                        >
                          <span className="flex min-w-0 items-center gap-2">
                            {item.content_href ? (
                              <FileText className={`h-3.5 w-3.5 shrink-0 transition-colors ${isActive ? "text-primary" : "text-muted-foreground group-hover:text-primary"}`} />
                            ) : (
                              <Search className={`h-3.5 w-3.5 shrink-0 transition-colors ${isActive ? "text-primary" : "text-muted-foreground group-hover:text-primary"}`} />
                            )}
                            <span className="truncate">
                              <HighlightedSuggestion text={item.text} query={cleanQuery} />
                            </span>
                            {item.content_href && (
                              <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
                                مطلب
                              </span>
                            )}
                          </span>
                          <ArrowLeft className={`h-3.5 w-3.5 shrink-0 transition-all ${isActive ? "text-primary -translate-x-0.5" : "text-muted-foreground/40 group-hover:text-primary group-hover:-translate-x-0.5"}`} />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}

              {showNoSuggestions && (
                <div className="px-3 py-3 text-center text-xs text-muted-foreground">
                  موردی یافت نشد. برای جستجوی دقیق دکمه اینتر را بزنید.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
