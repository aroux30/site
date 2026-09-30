"use client";

/**
 * Client-side routing config hook (permalink structure, category/tag bases).
 *
 * Storefront link builders call this so a customised permalink structure
 * changes the URLs the site actually links to — not just the ones it can
 * resolve. The config is fetched once per page load (module-level cache in
 * lib/routing.ts) and falls back to the canonical defaults on any failure,
 * so an API outage degrades to today's URLs rather than broken links.
 */

import { useEffect, useState } from "react";

import { DEFAULT_ROUTING, type RoutingConfig } from "@/lib/permalinks";
import { getCachedRoutingConfig } from "@/lib/routing";

export function useRoutingConfig(): RoutingConfig {
  const [config, setConfig] = useState<RoutingConfig>(DEFAULT_ROUTING);

  useEffect(() => {
    let mounted = true;
    void getCachedRoutingConfig().then((next) => {
      if (mounted) setConfig(next);
    });
    return () => {
      mounted = false;
    };
  }, []);

  return config;
}
