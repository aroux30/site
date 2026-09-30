"use client";

/**
 * Language switcher for content pages (i18n).
 *
 * Renders the available translations of the current content plus its own
 * locale. Each option links straight to the sibling's canonical URL — a
 * translation is its own row with its own slug, so no locale-prefix routing
 * is needed for the switch to work.
 */

import Link from "next/link";
import { Languages } from "lucide-react";

import { localeName } from "@/lib/i18n";

export interface TranslationLink {
  locale: string;
  href: string;
  title?: string;
}

interface LanguageSwitcherProps {
  currentLocale: string;
  /** Sibling translations of the current content (its own locale excluded). */
  translations: TranslationLink[];
}

export function LanguageSwitcher({ currentLocale, translations }: LanguageSwitcherProps) {
  if (translations.length === 0) return null;

  return (
    <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs">
      <Languages className="h-3.5 w-3.5 text-muted-foreground" />
      <span className="font-semibold text-foreground">{localeName(currentLocale)}</span>
      {translations.map((t) => (
        <Link
          key={t.locale}
          href={t.href}
          title={t.title}
          className="rounded-full px-2 py-0.5 text-muted-foreground transition-colors hover:bg-primary/10 hover:text-primary"
        >
          {localeName(t.locale)}
        </Link>
      ))}
    </div>
  );
}
