"use client";

import Image from "next/image";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type {
  ApiProductVariant,
  ApiVariationAttributeGroup,
  ApiVariationAttributeOption,
} from "@/lib/api/services";

/* -------------------------------------------------------------------------- */
/*                     Variation Swatches (woo-variation-swatches parity)     */
/*                                                                            */
/* One swatch ROW per attribute group, styled by the group's `type`:          */
/*   label → text pill (the "60 UC / 325 UC / 660 UC" top-up shape),          */
/*   color → colored circle,  image → square thumbnail.                       */
/* The shopper's combination selects a variant; unavailable options render    */
/* with the plugin's cross-sign and stay unclickable.                         */
/* -------------------------------------------------------------------------- */

export interface VariationSwatchesProps {
  groups: ApiVariationAttributeGroup[];
  variants: ApiProductVariant[];
  /** Currently chosen combination: { attribute_slug: value_slug } */
  selected: Record<string, string>;
  onOptionSelect: (groupSlug: string, optionSlug: string) => void;
  className?: string;
}

/** A variant is buyable when active AND (untracked OR has sellable stock). */
function isVariantBuyable(v: ApiProductVariant): boolean {
  if (!v.is_active) return false;
  return v.available === null || v.available === undefined || v.available > 0;
}

/** Does any still-purchasable variant carry option `optionSlug` on `groupSlug`,
 *  given the selections already fixed on the OTHER groups? WooCommerce locks
 *  a dimension once chosen; the same rule keeps the matrix honest here. */
function optionAvailable(
  group: ApiVariationAttributeGroup,
  optionSlug: string,
  variants: ApiProductVariant[],
  selected: Record<string, string>,
): boolean {
  return variants.some((v) => {
    if (!isVariantBuyable(v)) return false;
    const attrs = v.attributes || {};
    if (String(attrs[group.slug]) !== optionSlug) return false;
    return Object.entries(selected).every(
      ([gSlug, vSlug]) =>
        gSlug === group.slug ||
        attrs[gSlug] === undefined ||
        String(attrs[gSlug]) === vSlug,
    );
  });
}

function SwatchTooltip({ text }: { text: string }) {
  return (
    <span className="pointer-events-none absolute bottom-full right-1/2 z-30 mb-1.5 translate-x-1/2 whitespace-nowrap rounded-lg bg-foreground px-2 py-1 text-[11px] font-medium text-background opacity-0 shadow-lg transition-opacity duration-150 group-hover:opacity-100">
      {text}
    </span>
  );
}

function OptionSwatch({
  group,
  option,
  selected,
  available,
  onSelect,
}: {
  group: ApiVariationAttributeGroup;
  option: ApiVariationAttributeOption;
  selected: boolean;
  available: boolean;
  onSelect: () => void;
}) {
  const style = group.type;
  const isRound = style === "color";

  return (
    <button
      type="button"
      onClick={() => available && onSelect()}
      disabled={!available}
      aria-pressed={selected}
      aria-label={option.value}
      title={option.tooltip || option.value}
      className={cn(
        "group relative flex items-center justify-center border-2 transition-all duration-150",
        isRound ? "h-9 w-9 rounded-full" : "h-9 min-w-[2.25rem] rounded-lg px-3",
        style === "image" && "overflow-hidden p-0",
        selected
          ? "border-primary ring-2 ring-primary/30"
          : "border-border hover:border-muted-foreground/60",
        !available && "cursor-not-allowed",
        !selected && available && "bg-card",
      )}
    >
      {/* Tooltip (plugin's flexible tooltip feature) */}
      {option.tooltip && available && <SwatchTooltip text={option.tooltip} />}

      {style === "color" && option.color ? (
        <span
          className="h-full w-full rounded-full border border-black/10"
          style={{ backgroundColor: option.color }}
          aria-hidden
        />
      ) : style === "image" && option.image_url ? (
        <span className="relative block h-full w-full" aria-hidden>
          <Image
            src={option.image_url}
            alt=""
            fill
            sizes="36px"
            className="object-cover"
          />
        </span>
      ) : (
        <span
          className={cn(
            "text-xs font-semibold",
            selected ? "text-primary" : "text-foreground",
          )}
        >
          {option.value}
        </span>
      )}

      {/* Out-of-stock cross sign (plugin default behavior) */}
      {!available && (
        <>
          <X
            className="absolute h-5 w-5 text-red-500/80"
            strokeWidth={2.5}
            aria-hidden
          />
          {!isRound && (
            <span className="sr-only">{`${option.value} — ناموجود`}</span>
          )}
        </>
      )}
    </button>
  );
}

export function VariationSwatches({
  groups,
  variants,
  selected,
  onOptionSelect,
  className,
}: VariationSwatchesProps) {
  return (
    <div className={cn("space-y-3", className)}>
      {groups.map((group) => {
        const selectedSlug = selected[group.slug];
        const selectedOption = group.options.find(
          (o) => o.slug === selectedSlug,
        );
        return (
          <div key={group.attribute_id} className="space-y-1.5">
            {/* Label + the selected value's name beside it (plugin feature:
                «نمایش نام گزینه‌ی انتخاب‌شده کنار برچسب») */}
            <span className="block text-xs font-bold text-foreground">
              {`${group.name}:`}
              {selectedOption && (
                <span className="mr-1 font-medium text-muted-foreground">
                  {selectedOption.value}
                </span>
              )}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              {group.options.map((option) => (
                <OptionSwatch
                  key={option.value_id}
                  group={group}
                  option={option}
                  selected={selectedSlug === option.slug}
                  available={optionAvailable(
                    group,
                    option.slug,
                    variants,
                    selected,
                  )}
                  onSelect={() => onOptionSelect(group.slug, option.slug)}
                />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
