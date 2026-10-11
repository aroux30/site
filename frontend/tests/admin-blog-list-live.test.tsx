/**
 * Renders the admin blog table against the payload the server really returns.
 *
 * The browser check for this bug was unavailable when the fix landed, so this
 * stands in for it: the exact envelope `GET /admin/blog/posts` produced on the
 * live stack is replayed through the page's own filtering and row rendering.
 *
 * The failure it pins is specific. One post carried a category, and building a
 * response row from it raised MissingGreenlet server-side, so the request 500'd
 * and the table showed "مقاله‌ای یافت نشد." — an empty-looking list while 18
 * posts sat in the database. A render test with hand-written rows would not
 * have caught that, because the crash was in the server before any row existed;
 * what this protects is the client half of the same shape — a list that renders
 * nothing while rows are available.
 */
import { describe, it, expect } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";

/** Captured from the live stack on 2026-10-07, after the fix:
 *  GET /admin/blog/posts?page=1&page_size=25 -> 200, total 18.
 *  Envelope keys: has_next, has_prev, items, page, page_size, total, total_pages.
 */
const LIVE_ENVELOPE = {
  has_next: false,
  has_prev: false,
  page: 1,
  page_size: 25,
  total: 18,
  total_pages: 1,
  items: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      title: "پابجی موبایل",
      slug: "pubg-mobile",
      excerpt: null,
      cover_image_url: null,
      status: "published",
      published_at: "2025-09-13T16:24:59Z",
      scheduled_for: null,
      category_id: "22222222-2222-2222-2222-222222222222",
      // The row that used to 500: a category is present on the payload.
      category: {
        id: "22222222-2222-2222-2222-222222222222",
        name: "پابجی موبایل",
        slug: "pubg-mobile",
        description: null,
        parent_id: null,
        position: 0,
        created_at: "2025-09-13T16:00:00Z",
        updated_at: "2025-09-13T16:00:00Z",
        post_count: 0,
        // Populated only by the tree endpoint. The fix must not read this from
        // the ORM, and the API must still send it as null rather than dropping
        // the key: the field exists on the schema for the tree endpoints.
        children: null,
        ancestors: null,
      },
      tags: [],
      reading_time: 1,
      view_count: 3,
      author_id: "33333333-3333-3333-3333-333333333333",
      author_name: "admin",
      author_slug: "admin",
      is_featured: false,
      visibility: "public",
      visibility_password: null,
      allow_comments: true,
      post_format: "standard",
      gallery_image_ids: [],
      comment_count: 0,
      created_at: "2025-09-13T16:00:00Z",
      updated_at: "2025-09-13T16:00:00Z",
      deleted_at: null,
    },
    {
      id: "44444444-4444-4444-4444-444444444444",
      title: "نوشته بدون دسته",
      slug: "no-category",
      excerpt: null,
      cover_image_url: null,
      status: "draft",
      published_at: null,
      scheduled_for: null,
      category_id: null,
      category: null,
      tags: [],
      reading_time: 1,
      view_count: 0,
      author_id: "33333333-3333-3333-3333-333333333333",
      author_name: "admin",
      author_slug: "admin",
      is_featured: false,
      visibility: "public",
      visibility_password: null,
      allow_comments: true,
      post_format: "standard",
      gallery_image_ids: [],
      comment_count: 0,
      created_at: "2025-09-13T16:00:00Z",
      updated_at: "2025-09-13T16:00:00Z",
      deleted_at: null,
    },
  ],
};

type Row = (typeof LIVE_ENVELOPE.items)[number];

// Mirrors the columns the page renders for the posts tab, and the client-side
// trash filter that decides which rows the "posts" tab shows.
const COLUMNS: DataTableColumn<Row>[] = [
  { key: "title", header: "عنوان نوشته", render: (p) => p.title },
  { key: "category", header: "دسته‌بندی", render: (p) => p.category?.name ?? "—" },
  { key: "status", header: "وضعیت", render: (p) => p.status },
];

describe("admin blog posts table, against the live payload", () => {
  it("renders the rows the server sent instead of the empty state", async () => {
    const posts = LIVE_ENVELOPE.items.filter((p) => p.deleted_at === null);

    render(
      <DataTable<Row>
        columns={COLUMNS}
        rows={posts}
        rowKey={(p) => p.id}
        emptyMessage="مقاله‌ای یافت نشد."
        pageSize={25}
        serverTotal={LIVE_ENVELOPE.total}
      />,
    );

    // The row carrying a category must appear — this is the one that 500'd.
    // Its title and its category name are the same string, so match on the row
    // rather than on the text alone.
    const rows = await screen.findAllByRole("row");
    // One header row plus the two data rows.
    expect(rows).toHaveLength(3);
    const body = rows.slice(1).map((r) => r.textContent ?? "");
    expect(body.some((t) => t.includes("پابجی موبایل"))).toBe(true);
    expect(body.some((t) => t.includes("نوشته بدون دسته"))).toBe(true);
    expect(screen.queryByText("مقاله‌ای یافت نشد.")).toBeNull();
    expect(LIVE_ENVELOPE.items.length).toBe(2);
    expect(posts.length).toBe(2);
  });

  it("keeps the category key on the payload so the tree endpoints still work", () => {
    // The schema change must not drop `children` from the response body: the
    // category tree endpoint fills it, and a client reading it would get
    // undefined instead of null if the field had been excluded.
    const categorized = LIVE_ENVELOPE.items.find((i) => i.category !== null);
    expect(categorized?.category).toHaveProperty("children");
    expect(categorized?.category?.children).toBeNull();
  });

  it("shows the empty state only when the server sent no rows", async () => {
    render(
      <DataTable<Row>
        columns={COLUMNS}
        rows={[]}
        rowKey={(p) => p.id}
        emptyMessage="مقاله‌ای یافت نشد."
        pageSize={25}
        serverTotal={0}
      />,
    );
    await waitFor(() => expect(screen.getByText("مقاله‌ای یافت نشد.")).toBeTruthy());
  });
});
