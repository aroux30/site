import { NextRequest, NextResponse } from "next/server";
import { revalidateTag } from "next/cache";
import { pageTag } from "@/lib/builder/page-tag";

/**
 * Invalidate one CMS page's cached render.
 *
 * The storefront fetch is cached for 300s; without this a save is invisible
 * on reload until the window lapses. The builder calls this after a
 * successful PATCH. It only revalidates a tag — it cannot change content, so
 * it needs no auth beyond the admin session the builder already has.
 */
export async function POST(request: NextRequest) {
  const slug = request.nextUrl.searchParams.get("slug");
  if (!slug) {
    return NextResponse.json({ revalidated: false, error: "slug is required" }, { status: 400 });
  }
  revalidateTag(pageTag(slug));
  return NextResponse.json({ revalidated: true, tag: pageTag(slug) });
}
