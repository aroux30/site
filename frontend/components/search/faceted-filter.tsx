"use client";

import React, { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Star,
  Package,
  RotateCcw,
} from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { toPersianDigits, formatPrice, cn } from "@/lib/utils";
import type { FacetApi, FacetBucketApi } from "@/lib/api/services";
import type { FacetedFilterState } from "@/hooks/use-faceted-search";

/* -------------------------------------------------------------------------- */
/*                          Props                                              */
/* -------------------------------------------------------------------------- */

export interface FacetedFilterProps {
  facets: FacetApi[];
  filters: FacetedFilterState;
  activeFiltersCount: number;

  onCategoryChange: (catId: string | null) => void;
  onBrandChange: (brand: string | null) => void;
  onPriceRangeChange: (min: number | null, max: number | null) => void;
  onRatingChange: (rating: number | null) => void;
  onInStockToggle: () => void;
  onAttributeToggle: (attrName: string, attrVal: string) => void;
  onResetFilters: () => void;
}

/* -------------------------------------------------------------------------- */
/*                     Collapsible Section                                     */
/* -------------------------------------------------------------------------- */

function FilterSection({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between text-sm font-bold text-foreground"
      >
        <span>{title}</span>
        {open ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      {open && <div className="mt-3">{children}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                      Bucket checkbox list                                   */
/* -------------------------------------------------------------------------- */

function BucketCheckboxList({
  buckets,
  selectedKeys,
  onToggle,
}: {
  buckets: FacetBucketApi[];
  selectedKeys: string[];
  onToggle: (key: string) => void;
}) {
  const [showAll, setShowAll] = useState(false);
  const displayBuckets = showAll ? buckets : buckets.slice(0, 8);
  const hasMore = buckets.length > 8;

  return (
    <div className="space-y-1.5 max-h-60 overflow-y-auto ps-0.5">
      {displayBuckets.map((bucket) => {
        const checked = selectedKeys.includes(bucket.key);
        return (
          <label
            key={bucket.key}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs cursor-pointer transition-colors hover:bg-muted/60",
              checked && "bg-primary/10 font-semibold text-primary",
            )}
          >
            <Checkbox
              checked={checked}
              onCheckedChange={() => onToggle(bucket.key)}
              className="h-3.5 w-3.5"
            />
            <span className="flex-1 truncate">
              {bucket.label || bucket.key}
            </span>
            <Badge
              variant="secondary"
              className="h-5 min-w-[1.5rem] rounded-md px-1.5 py-0 text-[10px] font-medium text-muted-foreground"
            >
              {toPersianDigits(bucket.doc_count)}
            </Badge>
          </label>
        );
      })}
      {hasMore && (
        <button
          type="button"
          onClick={() => setShowAll((s) => !s)}
          className="pt-1 text-[11px] font-medium text-primary hover:underline"
        >
          {showAll ? "نمایش کمتر" : `+${toPersianDigits(buckets.length - 8)} مورد دیگر`}
        </button>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                          Price Range Section                                 */
/* -------------------------------------------------------------------------- */

const MAX_PRICE_LIMIT = 150_000_000;

function PriceRangeSection({
  minPrice,
  maxPrice,
  onChange,
}: {
  minPrice: number | null;
  maxPrice: number | null;
  onChange: (min: number | null, max: number | null) => void;
}) {
  const currentMin = minPrice ?? 0;
  const currentMax = maxPrice ?? MAX_PRICE_LIMIT;

  return (
    <div className="space-y-4">
      <div className="px-1 pt-2">
        <Slider
          min={0}
          max={MAX_PRICE_LIMIT}
          step={500_000}
          value={[currentMin, currentMax]}
          onValueChange={(val) => {
            if (val.length === 2) {
              const newMin = val[0]! > 0 ? val[0]! : null;
              const newMax = val[1]! < MAX_PRICE_LIMIT ? val[1]! : null;
              onChange(newMin, newMax);
            }
          }}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-muted-foreground block mb-1">از:</span>
          <div className="rounded-lg border border-border p-2 bg-muted/30 font-mono text-center">
            {formatPrice(currentMin)}
          </div>
        </div>
        <div>
          <span className="text-muted-foreground block mb-1">تا:</span>
          <div className="rounded-lg border border-border p-2 bg-muted/30 font-mono text-center">
            {formatPrice(currentMax)}
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                          Rating Section                                     */
/* -------------------------------------------------------------------------- */

function RatingSection({
  buckets,
  currentRating,
  onChange,
}: {
  buckets: FacetBucketApi[];
  currentRating: number | null;
  onChange: (rating: number | null) => void;
}) {
  const ratingValues = [5, 4, 3, 2, 1];

  return (
    <div className="space-y-1.5">
      {ratingValues.map((val) => {
        const bucket = buckets.find(
          (b) => Math.floor(parseFloat(b.key)) === val,
        );
        const selected = currentRating === val;
        return (
          <label
            key={val}
            className={cn(
              "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-xs cursor-pointer transition-colors hover:bg-muted/60",
              selected && "bg-primary/10 font-semibold text-primary",
            )}
          >
            <Checkbox
              checked={selected}
              onCheckedChange={() => onChange(selected ? null : val)}
              className="h-3.5 w-3.5"
            />
            <span className="flex items-center gap-0.5 flex-1">
              {Array.from({ length: val }).map((_, i) => (
                <Star
                  key={i}
                  className="h-3 w-3 fill-amber-400 text-amber-400"
                />
              ))}
              {Array.from({ length: 5 - val }).map((_, i) => (
                <Star
                  key={`e-${i}`}
                  className="h-3 w-3 text-muted-foreground/30"
                />
              ))}
              <span className="ms-1 text-muted-foreground">و بالاتر</span>
            </span>
            {bucket && (
              <Badge
                variant="secondary"
                className="h-5 min-w-[1.5rem] rounded-md px-1.5 py-0 text-[10px] font-medium text-muted-foreground"
              >
                {toPersianDigits(bucket.doc_count)}
              </Badge>
            )}
          </label>
        );
      })}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*                     Main FacetedFilter Component                            */
/* -------------------------------------------------------------------------- */

export function FacetedFilter({
  facets,
  filters,
  activeFiltersCount,
  onCategoryChange,
  onBrandChange,
  onPriceRangeChange,
  onRatingChange,
  onInStockToggle,
  onAttributeToggle,
  onResetFilters,
}: FacetedFilterProps) {
  // Look up facets by field
  const findFacet = (field: string) =>
    facets.find((f) => f.field === field);

  const categoryFacet = findFacet("category_id");
  const brandFacet = findFacet("brand");
  const ratingFacet = findFacet("rating");
  const availabilityFacet = findFacet("availability");

  // Attribute facets are any facet whose field starts with "attr:"
  const attributeFacets = facets.filter((f) => f.field.startsWith("attr:"));

  return (
    <div className="space-y-4">
      {/* Categories */}
      {categoryFacet && categoryFacet.buckets.length > 0 && (
        <FilterSection title="دسته‌بندی">
          <BucketCheckboxList
            buckets={categoryFacet.buckets}
            selectedKeys={filters.category ? [filters.category] : []}
            onToggle={(key) =>
              onCategoryChange(filters.category === key ? null : key)
            }
          />
        </FilterSection>
      )}

      {/* Brands */}
      {brandFacet && brandFacet.buckets.length > 0 && (
        <FilterSection title="برند">
          <BucketCheckboxList
            buckets={brandFacet.buckets}
            selectedKeys={filters.brand ? [filters.brand] : []}
            onToggle={(key) =>
              onBrandChange(filters.brand === key ? null : key)
            }
          />
        </FilterSection>
      )}

      {/* Price Range */}
      <FilterSection title="محدوده قیمت (تومان)">
        <PriceRangeSection
          minPrice={filters.minPrice}
          maxPrice={filters.maxPrice}
          onChange={onPriceRangeChange}
        />
      </FilterSection>

      {/* Rating */}
      {ratingFacet && ratingFacet.buckets.length > 0 && (
        <FilterSection title="امتیاز">
          <RatingSection
            buckets={ratingFacet.buckets}
            currentRating={filters.minRating}
            onChange={onRatingChange}
          />
        </FilterSection>
      )}

      {/* In Stock Toggle */}
      {availabilityFacet && availabilityFacet.buckets.length > 0 && (
        <div className="rounded-2xl border border-border bg-card p-4 shadow-sm">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="flex items-center gap-2 text-sm font-bold text-foreground">
              <Package className="h-4 w-4 text-emerald-500" />
              فقط کالاهای موجود
            </span>
            <Switch
              checked={filters.inStockOnly}
              onCheckedChange={onInStockToggle}
            />
          </label>
          {availabilityFacet.buckets[0] && (
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              {toPersianDigits(availabilityFacet.buckets[0].doc_count)} کالای
              موجود
            </p>
          )}
        </div>
      )}

      {/* Dynamic Attribute Facets */}
      {attributeFacets.map((attrFacet) => {
        const attrName = attrFacet.field.slice(5); // strip "attr:"
        const selected = filters.attributes[attrName] || [];
        return (
          <FilterSection
            key={attrFacet.field}
            title={attrFacet.display_name}
            defaultOpen={false}
          >
            <BucketCheckboxList
              buckets={attrFacet.buckets}
              selectedKeys={selected}
              onToggle={(key) => onAttributeToggle(attrName, key)}
            />
          </FilterSection>
        );
      })}

      {/* Reset All */}
      {activeFiltersCount > 0 && (
        <Button
          variant="outline"
          size="sm"
          onClick={onResetFilters}
          className="w-full gap-2 rounded-xl text-xs text-destructive border-destructive/30 hover:bg-destructive/10 hover:text-destructive"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          پاک کردن تمام فیلترها
        </Button>
      )}
    </div>
  );
}
