import apiClient from "./client";

/**
 * Block patterns — the WordPress "patterns" library for our editor.
 *
 * Patterns are static section templates registered in backend code
 * (`app/modules/content/domain/block_patterns.py`), not rows in a table, so
 * there is nothing to create or edit here. The editor's job is only to list
 * them, fill their `{{slots}}`, and paste the rendered HTML into a body.
 *
 * Contract (mirrors `BlockPatternCategoryGroup` / `BlockPatternRenderResponse`):
 *   GET  /content/block-patterns                -> bare array of category groups
 *   POST /content/block-patterns/{slug}/render  -> { slug, html, applied_variables }
 *                                                 with body { variables: {...} }
 */

export interface BlockPatternVariable {
  /** Slot name as it appears in the pattern's `{{slot}}` tokens. */
  name: string;
  /** Persian label the editor form shows. */
  label: string;
  /** Placeholder copy used when the editor leaves the field empty. */
  default: string;
}

export interface BlockPattern {
  slug: string;
  title: string;
  description: string;
  category: string;
  keywords: string[];
  variables: BlockPatternVariable[];
}

export interface BlockPatternCategoryGroup {
  category: string;
  patterns: BlockPattern[];
}

export interface BlockPatternRenderResult {
  slug: string;
  /** Ready-to-insert HTML fragment, with every slot resolved and escaped. */
  html: string;
  /** Names of the variables the editor actually supplied. */
  applied_variables: string[];
}

export const blockPatternsApi = {
  /** الگوهای بلوک، گروه‌بندی‌شده بر اساس دسته (فهرست گروه‌ها ترتیب ثبت دارند) */
  list: async (): Promise<BlockPatternCategoryGroup[]> => {
    const res = await apiClient.get<BlockPatternCategoryGroup[]>(
      "/content/block-patterns",
    );
    return Array.isArray(res.data) ? res.data : [];
  },

  /** ساخت HTML نهایی الگو با جایگزینی مقادیر واردشده در فیلدها */
  render: async (
    slug: string,
    variables: Record<string, string>,
  ): Promise<BlockPatternRenderResult> => {
    const res = await apiClient.post<BlockPatternRenderResult>(
      `/content/block-patterns/${slug}/render`,
      { variables },
    );
    return res.data;
  },
};
